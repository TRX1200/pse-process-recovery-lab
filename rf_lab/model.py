"""RMS phasors, exp(+jwt), SI internal units, passive one-port network.

50-ohm lossless feed -> shunt Cp -> series (L, Cs) -> plasma (Rb, Lb, Csh).
Plasma state is prescribed: this is NOT a self-consistent discharge solver.
"""
from __future__ import annotations
import hashlib
import json
import math
from numbers import Real
import numpy as np
from scipy.optimize import least_squares
from rf_lab import VERSION

E = 1.602176634e-19
ME = 9.1093837139e-31
EPS0 = 8.8541878128e-12
C0 = 299792458.0
Z0 = 50.0


def field(key, label, unit, default, low, high, group, note):
    return dict(key=key, label=label, unit=unit, default=default, min=low, max=high, group=group, note=note)


FIELDS = [
    field("frequency_mhz", "RF 주파수", "MHz", 13.56, 5, 40, "source", "단일 주파수 정상상태. 고조파·펄스 점화는 제외."),
    field("forward_w", "순방향 전력", "W", 300, 0, 3000, "source", "50 Ω 발생기 기준면의 진행파 전력. 총 흡수 전력과 다릅니다."),
    field("cp_pf", "병렬 Cₚ", "pF", 500, 10, 3000, "match", "매칭기 입력에서 접지로 연결한 가변 커패시터."),
    field("cs_pf", "직렬 Cₛ", "pF", 120, 10, 3000, "match", "코일 뒤에 직렬 연결한 가변 커패시터."),
    field("coil_uh", "매칭 코일 L", "µH", 2, .1, 5, "match", "고정 코일. 손실 저항은 ωL/Q."),
    field("coil_q", "코일 Q", "", 100, 5, 10000, "loss", "주파수에 무관한 Q를 가정. 낮으면 정합돼도 코일에 전력이 소모됩니다."),
    field("capacitor_q", "커패시터 Q", "", 1000, 20, 100000, "loss", "두 매칭 커패시터의 ESR = 1/(ωCQ)."),
    field("density_1e15_m3", "전자밀도 nₑ", "10¹⁵ m⁻³", 1, .1, 100, "plasma", "처방한 균일 밀도. 흡수 전력에서 자가 일관적으로 계산한 밀도가 아닙니다."),
    field("collision_1e8_s", "유효 충돌 빈도 ν", "10⁸ s⁻¹", 2, .01, 10, "plasma", "전자 운동량 손실의 유효 계수. 압력→ν 변환은 별도 모델이 필요합니다."),
    field("bulk_mm", "벌크 길이", "mm", 30, 2, 100, "plasma", "균일 전류가 흐르는 벌크의 유효 길이."),
    field("area_cm2", "유효 전극 면적", "cm²", 200, 10, 1000, "plasma", "두 쉬스와 벌크에 같은 유효 면적을 사용합니다."),
    field("sheath_total_mm", "두 쉬스 두께 합", "mm", 1, .05, 10, "plasma", "Csh = ε₀A/(s₁+s₂). 고정된 선형 직렬 등가 커패시턴스."),
    field("cable_m", "급전선 길이", "m", .5, 0, 5, "line", "무손실 50 Ω 급전선. 반사계수 위상만 회전합니다."),
    field("velocity_factor", "급전선 속도 계수", "c 비율", .7, .4, 1, "line", "위상 속도 / 광속."),
    field("density_ratio", "부하 변화: 밀도 배수", "×", .5, .1, 3, "experiment", "기준 자동 정합 후 밀도만 바꿔 고정 매칭과 재매칭을 비교합니다."),
    field("voltage_limit_v", "학습용 Cₛ 전압 한계", "V RMS", 1000, 10, 20000, "limits", "사용자가 정한 비교 기준. 실제 부품 정격이나 안전 인증이 아닙니다."),
    field("current_limit_a", "학습용 코일 전류 한계", "A RMS", 10, .1, 100, "limits", "사용자가 정한 비교 기준. RMS/peak를 구분하세요."),
]
SOURCES = [
    {"title": "Schmidt et al. (2018): plasma bulk equivalent circuit and nonlinear coupling", "url": "https://arxiv.org/abs/1804.05638"},
    {"title": "Apache Superset documentation", "url": "https://superset.apache.org/docs/"},
]


def schema():
    return {"version": VERSION, "fields": FIELDS, "sources": SOURCES}


def validate(raw):
    if not isinstance(raw, dict) or set(raw) - {f['key'] for f in FIELDS}:
        raise ValueError("Unknown RF parameter or invalid input object")
    p = {}
    for f in FIELDS:
        v = raw.get(f['key'], f['default'])
        if isinstance(v, bool) or not isinstance(v, Real) or not math.isfinite(v):
            raise ValueError(f"{f['key']}: finite number required")
        if not f['min'] <= v <= f['max']:
            raise ValueError(f"{f['key']}: {f['min']}–{f['max']} 범위가 필요합니다.")
        p[f['key']] = float(v)
    return p


def load_elements(p):
    area = p['area_cm2'] * 1e-4
    lb = ME * p['bulk_mm'] * 1e-3 / (p['density_1e15_m3'] * 1e15 * E**2 * area)
    return lb * p['collision_1e8_s'] * 1e8, lb, EPS0 * area / (p['sheath_total_mm'] * 1e-3)


def pair(z):
    return [float(z.real), float(z.imag)]


def point(p, frequency_mhz=None, cp_pf=None, cs_pf=None):
    """One frequency, exact linear circuit; inputs validated by public simulate()."""
    f = p['frequency_mhz'] if frequency_mhz is None else frequency_mhz
    w = 2 * math.pi * f * 1e6
    cp = (p['cp_pf'] if cp_pf is None else cp_pf) * 1e-12
    cs = (p['cs_pf'] if cs_pf is None else cs_pf) * 1e-12
    rb, lb, csh = load_elements(p)
    coil_x = w * p['coil_uh'] * 1e-6
    coil_r = coil_x / p['coil_q']
    cp_r, cs_r = 1 / (w * cp * p['capacitor_q']), 1 / (w * cs * p['capacitor_q'])
    zcp, zcs = cp_r - 1j/(w*cp), cs_r - 1j/(w*cs)
    zpl = rb + 1j*w*lb - 1j/(w*csh)
    zb = coil_r + 1j*coil_x + zcs + zpl
    zm = 1 / (1/zb + 1/zcp)
    angle = w * p['cable_m'] / (C0 * p['velocity_factor'])
    a, b, c = math.cos(angle), 1j*Z0*math.sin(angle), 1j*math.sin(angle)/Z0
    zg = (a*zm+b)/(c*zm+a)
    gamma = (zg-Z0)/(zg+Z0)
    gamma_m = (zm-Z0)/(zm+Z0)
    incident = math.sqrt(p['forward_w']*Z0)
    vg, ig = incident*(1+gamma), incident/Z0*(1-gamma)
    vm = a*vg-b*ig
    ib, icp = vm/zb, vm/zcp
    reflected = p['forward_w']*abs(gamma)**2
    bulk = abs(ib)**2*rb
    coil = abs(ib)**2*coil_r
    capacitors = abs(ib)**2*cs_r + abs(icp)**2*cp_r
    residual = p['forward_w']-reflected-bulk-coil-capacitors
    amplitude = min(abs(gamma), 1.0)
    return {"frequency_mhz": f, "cp_pf": cp*1e12, "cs_pf": cs*1e12,
            "z_load": pair(zpl), "z_match": pair(zm), "z_generator": pair(zg),
            "gamma": pair(gamma), "gamma_match": pair(gamma_m),
            "s11_db": 20*math.log10(max(amplitude, 1e-12)),
            "return_loss_db": -20*math.log10(max(amplitude, 1e-12)),
            "vswr": (1+amplitude)/(1-amplitude) if amplitude < 1 else None,
            "reflected_pct": 100*amplitude**2, "reflected_w": reflected,
            "forward_w": p['forward_w'], "accepted_w": p['forward_w']-reflected,
            "bulk_w": bulk, "coil_loss_w": coil, "capacitor_loss_w": capacitors,
            "bulk_efficiency_pct": 100*bulk/p['forward_w'] if p['forward_w'] else None,
            "coil_current_rms_a": abs(ib), "series_cap_rms_v": abs(ib*zcs),
            "sheath_rms_v": abs(ib)/(w*csh), "load_voltage": pair(ib*zpl), "load_current": pair(ib),
            "power_residual_w": residual, "bulk_r_ohm": rb, "bulk_l_nh": lb*1e9, "sheath_c_pf": csh*1e12}


def tune(p):
    """Bounded multistart least squares on Re/Im(Gamma), not a global proof."""
    def residual(log_caps):
        return point(p, cp_pf=math.exp(log_caps[0]), cs_pf=math.exp(log_caps[1]))['gamma_match']
    starts = [(p['cp_pf'], p['cs_pf'])] + [(x, y) for x in (40, 400, 2000) for y in (40, 200, 1500)]
    best = None
    for cp, cs in starts:
        r = least_squares(residual, np.log([cp, cs]), bounds=(math.log(10), math.log(3000)),
                          ftol=1e-10, xtol=1e-10, gtol=1e-10, max_nfev=180)
        cost = float(np.dot(r.fun, r.fun))
        if best is None or cost < best[0]:
            best = cost, np.exp(r.x), bool(r.success)
    result = point(p, cp_pf=float(best[1][0]), cs_pf=float(best[1][1]))
    result['optimizer_converged'] = best[2]
    result['match_within_1pct'] = result['reflected_pct'] < 1
    result['near_cap_bound'] = any(v < 10.01 or v > 2999 for v in best[1])
    return result


def simulate(raw):
    p = validate(raw)
    manual = point(p)
    matched = tune(p)
    shifted = {**p, 'density_1e15_m3': p['density_1e15_m3']*p['density_ratio']}
    fixed = point(shifted, cp_pf=matched['cp_pf'], cs_pf=matched['cs_pf'])
    rematched = tune(shifted)
    comparison = [dict(matched, case_name='01 기준 정합', density_1e15_m3=p['density_1e15_m3']),
                  dict(fixed, case_name='02 밀도 변화·C 고정', density_1e15_m3=shifted['density_1e15_m3']),
                  dict(rematched, case_name='03 밀도 변화·재정합', density_1e15_m3=shifted['density_1e15_m3'])]
    frequencies = np.linspace(max(1, p['frequency_mhz']*.6), p['frequency_mhz']*1.4, 181)
    frequency = {'mhz': frequencies.tolist(), 'manual': [point(p, f) for f in frequencies],
                 'matched': [point(p, f, matched['cp_pf'], matched['cs_pf']) for f in frequencies]}
    caps = np.geomspace(10, 3000, 41)
    heatmap = {'cp_pf': caps.tolist(), 'cs_pf': caps.tolist(),
               'reflected_pct': [[point(p, cp_pf=x, cs_pf=y)['reflected_pct'] for x in caps] for y in caps]}
    # Reconstructed sinusoidal steady-state phasors; not ignition/transient integration.
    phase = np.linspace(0, 4*math.pi, 181)
    waveform = {'time_ns': (phase/(2*math.pi*p['frequency_mhz']*1e6)*1e9).tolist(),
                'voltage_v': [float(math.sqrt(2)*(complex(*manual['load_voltage'])*np.exp(1j*t)).real) for t in phase],
                'current_a': [float(math.sqrt(2)*(complex(*manual['load_current'])*np.exp(1j*t)).real) for t in phase]}
    warnings = []
    if not matched['match_within_1pct']:
        warnings.append('이 토폴로지·C 범위에서 반사율 1% 미만 정합을 찾지 못했습니다. 해 존재를 보증하지 않습니다.')
    if matched['series_cap_rms_v'] > p['voltage_limit_v'] or matched['coil_current_rms_a'] > p['current_limit_a']:
        warnings.append('자동 정합점이 지정한 전압 또는 전류 비교 한계를 넘습니다. 낮은 반사율만으로 설계를 채택하지 마세요.')
    result = {'format': 'rf-matching-v1', 'version': VERSION, 'params': p,
              'config_hash': hashlib.sha256(json.dumps(p, sort_keys=True).encode()).hexdigest(),
              'manual': manual, 'matched': matched, 'comparison': comparison,
              'frequency': frequency, 'heatmap': heatmap, 'waveform': waveform, 'warnings': warnings,
              'sources': SOURCES, 'assumptions': [
                  'Linear CCP-inspired bulk R-L and fixed two-sheath equivalent C; not an ICP coil model.',
                  'Prescribed uniform density, collision frequency and sheath thickness; no ignition, self-bias, harmonics or chemistry feedback.',
                  'exp(+jwt), RMS phasors. Waveforms are reconstructed steady-state sinusoids.',
                  'Lossless 50-ohm feed line; finite constant Q for matching components. No parasitic resonances or thermal solver.',
                  'Numerical matching minimizes reflection only; voltage/current limits are checked afterwards.',
                  'No calibrated mapping to ViennaPS etch fluxes or real process yield. All cases are simulations.']}
    json.dumps(result, allow_nan=False)
    return result
