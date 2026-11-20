"""Steady Ar global balance coupled to the existing linear RF one-port.

This closure solves density rather than prescribing it. Sheath capacitance is
still prescribed; ignition, nonlinear RF sheaths and gas chemistry are absent.
Units: SI internally, Te in eV, phasors RMS with exp(+jwt).
"""
from __future__ import annotations

import hashlib
import json
import math
from numbers import Real

import numpy as np
from scipy.optimize import brentq, least_squares

from rf_lab.model import E, ME, field, point, validate
from sim_app.models.etch import _rates, M_AR, K_B, MTORR_TO_PA

VERSION = 'rf-ar-balance-0.1.0'
FIELDS = [
    field('pressure_mtorr', 'Ar 압력', 'mTorr', 20, 1, 150, 'gas', '중성 기체 고갈이 없는 순수 Ar. 반응 가스는 제외.'),
    field('gas_temperature_k', 'Ar 기체 온도', 'K', 350, 250, 800, 'gas', '고정 온도. 열전달 방정식은 계산하지 않습니다.'),
    field('ion_cross_section_1e19_m2', '유효 이온 충돌 단면적', '10⁻¹⁹ m²', 10, 1, 30, 'gas', '벽 손실 면적의 경험적 h 계수에 쓰는 일정 단면적.'),
]
ASSUMPTIONS = [
    'Pure Ar, Maxwellian 1-7 eV rate fits, cylindrical uniform bulk, fixed neutral gas density.',
    'Te follows particle balance; density follows circuit bulk heating = global loss. Te does not vary with power in this closure.',
    'Momentum loss uses ng*K_el + mean electron speed / bulk length. Fixed linear sheath C; no RF sheath harmonics or DC self-bias.',
    'Search 1e12 to min(1e20, 0.02*ng) m^-3. Highest density root with negative d(Pbulk-Ploss)/dn is selected.',
    'Negative scalar power-balance slope is a local closure criterion, not proof of discharge stability or ignition.',
    'No root means no accepted root within this model and search interval, not a prediction of physical extinction.',
    'Ion flux is an Ar wall-edge estimate. It is not automatically converted into SF6/O2 flux, etch rate, or thermal ALD growth.',
]


def validate_gas(raw):
    if not isinstance(raw, dict) or set(raw) - {f['key'] for f in FIELDS}:
        raise ValueError('Unknown Ar balance parameter')
    result = {}
    for f in FIELDS:
        value = raw.get(f['key'], f['default'])
        if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
            raise ValueError(f"{f['key']}: finite number required")
        if not f['min'] <= value <= f['max']:
            raise ValueError(f"{f['key']}: out of range")
        result[f['key']] = float(value)
    return result


def global_terms(rf, gas):
    area = rf['area_cm2'] * 1e-4
    length = rf['bulk_mm'] * 1e-3
    radius = math.sqrt(area / math.pi)
    volume = area * length
    ng = gas['pressure_mtorr'] * MTORR_TO_PA / (K_B * gas['gas_temperature_k'])
    mean_free_path = 1 / (ng * gas['ion_cross_section_1e19_m2'] * 1e-19)
    # Same wall-edge approximation as the existing Ar learning model.
    h_l = .86 / math.sqrt(3 + length / (2 * mean_free_path))
    h_r = .80 / math.sqrt(4 + radius / mean_free_path)
    effective_area = 2 * math.pi * (h_l * radius**2 + h_r * radius * length)

    def particle(te):
        return ng * _rates(te)[0] - math.sqrt(E * te / M_AR) * effective_area / volume

    if not particle(1) <= 0 <= particle(7):
        raise ValueError('Ar 입자 수지 해가 1–7 eV 속도식 범위 밖입니다. 가스·기하 조건을 바꾸세요.')
    te = brentq(particle, 1, 7, xtol=1e-12)
    kiz, kex, kel = _rates(te)
    u_b = math.sqrt(E * te / M_AR)
    collision_ev = 15.76 + 12.14 * kex / kiz + 3 * ME / M_AR * te * kel / kiz
    # Maxwellian electrons: 2 Te; floating ion wall loss ~5.2 Te, as in the
    # pre-existing Ar global model. Fixed closure, not an RF sheath solution.
    pair_energy_ev = collision_ev + 7.2 * te
    coefficient = E * u_b * effective_area * pair_energy_ev
    nu = ng * kel + math.sqrt(8 * E * te / (math.pi * ME)) / length
    return dict(te_ev=te, neutral_density_m3=ng, volume_m3=volume,
                effective_area_m2=effective_area, h_l=h_l, bohm_speed_m_s=u_b,
                collision_s=nu, loss_w_per_m3=coefficient, pair_energy_ev=pair_energy_ev,
                particle_relative_residual=abs(particle(te)) / (ng * kiz),
                density_low=1e12, density_high=min(1e20, .02 * ng))


def circuit_at(rf, terms, density, cp=None, cs=None):
    state = {**rf, 'density_1e15_m3': density / 1e15,
             'collision_1e8_s': terms['collision_s'] / 1e8}
    return point(state, cp_pf=cp, cs_pf=cs)


def equilibrium(rf, terms, cp=None, cs=None, samples=320):
    if rf['forward_w'] == 0:
        return dict(status='off', roots=[], selected=None)
    coefficient = terms['loss_w_per_m3']

    def balance(log_n):
        density = math.exp(log_n)
        # Per-density form avoids accepting the trivial n -> 0 limit as a root.
        return circuit_at(rf, terms, density, cp, cs)['bulk_w'] / density / coefficient - 1

    logs = np.linspace(math.log(terms['density_low']), math.log(terms['density_high']), samples)
    roots = []
    for low, high in zip(logs[:-1], logs[1:]):
        if balance(low) * balance(high) > 0:
            continue
        log_n = brentq(balance, low, high, xtol=1e-11)
        n = math.exp(log_n)
        if roots and abs(math.log(n / roots[-1]['density_m3'])) < 1e-6:
            continue
        circuit = circuit_at(rf, terms, n, cp, cs)
        epsilon = 1e-4
        # d(Pbulk - n*K)/dn, normalized by K; local scalar stability only.
        derivative = (circuit_at(rf, terms, n*(1+epsilon), cp, cs)['bulk_w'] -
                      circuit_at(rf, terms, n*(1-epsilon), cp, cs)['bulk_w']) / (2*epsilon*n*coefficient) - 1
        roots.append(dict(density_m3=n, ion_flux_m2_s=n*terms['h_l']*terms['bohm_speed_m_s'],
                          te_ev=terms['te_ev'], loss_w=n*coefficient, circuit=circuit,
                          power_relative_residual=abs(balance(log_n)),
                          normalized_slope=derivative, local_slope_stable=derivative < 0))
    accepted = [r for r in roots if r['local_slope_stable']]
    return dict(status='steady' if accepted else 'no_accepted_root', roots=roots,
                selected=accepted[-1] if accepted else None)


def coupled_match(rf, terms):
    if rf['forward_w'] == 0:
        return equilibrium(rf, terms)
    lo, hi = terms['density_low'], terms['density_high']
    n_guess = min(hi*.9, max(lo*1.1, rf['forward_w']/terms['loss_w_per_m3']*.3))

    def residual(x):
        cp, cs, n = np.exp(x)
        circuit = circuit_at(rf, terms, n, cp, cs)
        ratio = circuit['bulk_w'] / (n*terms['loss_w_per_m3'])
        return [*circuit['gamma_match'], math.log(max(ratio, 1e-300))]

    candidates = []
    for cp, cs in [(rf['cp_pf'],rf['cs_pf']), (100,80), (500,150), (2000,300), (40,1500)]:
        fit = least_squares(residual, np.log([cp,cs,n_guess]),
                            bounds=(np.log([10,10,lo]), np.log([3000,3000,hi])),
                            ftol=1e-10, xtol=1e-10, gtol=1e-10, max_nfev=240)
        cp_fit, cs_fit, _ = np.exp(fit.x)
        solved = equilibrium(rf, terms, float(cp_fit), float(cs_fit))
        if solved['selected']:
            candidates.append(solved)
    return min(candidates, key=lambda r:r['selected']['circuit']['reflected_pct']) if candidates else dict(
        status='no_accepted_root', roots=[], selected=None)


def simulate(payload):
    if not isinstance(payload, dict) or set(payload) - {'rf_params','gas'} or 'rf_params' not in payload:
        raise ValueError('Expected rf_params and optional gas')
    rf, gas = validate(payload['rf_params']), validate_gas(payload.get('gas',{}))
    terms = global_terms(rf, gas)
    manual, matched = equilibrium(rf, terms), coupled_match(rf, terms)
    logs = np.linspace(math.log10(terms['density_low']), math.log10(terms['density_high']), 180)
    sweep = []
    if matched['selected']:
        chosen = matched['selected']['circuit']
        for cp in np.linspace(max(10,chosen['cp_pf']*.65),min(3000,chosen['cp_pf']*1.35),21):
            state = equilibrium(rf, terms, float(cp), chosen['cs_pf'])['selected']
            sweep.append(dict(cp_pf=float(cp), density_m3=state['density_m3'] if state else None,
                              bulk_w=state['circuit']['bulk_w'] if state else None,
                              reflected_pct=state['circuit']['reflected_pct'] if state else None))
    result = dict(format='rf-ar-coupled-v1', version=VERSION, rf_params=rf, gas=gas, terms=terms,
                  manual=manual, matched=matched, sweep=sweep,
                  balance_curve=dict(log10_density=logs.tolist(),
                      rf_bulk_w=[circuit_at(rf,terms,10**v)['bulk_w'] for v in logs],
                      loss_w=[10**v*terms['loss_w_per_m3'] for v in logs]),
                  assumptions=ASSUMPTIONS, evidence='simulation',
                  sources=[{'title':'Schmidt et al. (2018), circuit / global-balance coupling; not a reproduction',
                            'url':'https://arxiv.org/abs/1804.05638'}])
    result['config_hash'] = hashlib.sha256(json.dumps({'rf':rf,'gas':gas,'version':VERSION},sort_keys=True).encode()).hexdigest()
    json.dumps(result, allow_nan=False)
    return result
