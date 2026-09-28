"""Educational thermal ALD: chamber delivery, reactive diffusion and surface turnover.

The generic kinetic constants are assumptions, not an identified material recipe.
See docs/ALD_MODEL.md for equations, units, boundaries and validation limits.
"""

from __future__ import annotations

import math
from numbers import Real
from typing import Any

import numpy as np
from scipy.integrate import quad, solve_ivp
from scipy.sparse import lil_matrix

MODEL_VERSION = "ald-reactive-diffusion-1.0.1"
KB = 1.380649e-23
AMU = 1.66053906660e-27
EV = 1.602176634e-19
REFERENCE_T_K = 473.15
MOLECULE_MASS_A = 72.0 * AMU
MOLECULE_MASS_B = 18.0 * AMU


def _param(key: str, label: str, unit: str, low: float, high: float,
           step: float, default: float, group: str, description: str) -> dict:
    return {"key": key, "label": label, "unit": unit, "min": low,
            "max": high, "step": step, "default": default,
            "group": group, "description": description}


PARAMS = [
    _param("pulse_a_s", "A 주입", "s", 0, 5, 0.05, 0.5, "Recipe", "전구체 A 밸브 개방 시간"),
    _param("purge_a_s", "A 뒤 퍼지", "s", 0, 8, 0.1, 1.5, "Recipe", "A 공급 차단 후 배기 시간"),
    _param("pulse_b_s", "B 주입", "s", 0, 5, 0.05, 0.5, "Recipe", "반응물 B 밸브 개방 시간"),
    _param("purge_b_s", "B 뒤 퍼지", "s", 0, 8, 0.1, 1.5, "Recipe", "B 공급 차단 후 배기 시간"),
    _param("pressure_a_pa", "A 목표 분압", "Pa", 0, 200, 1, 20, "Recipe", "주입 시 챔버 A 분압의 목표값; 총압과 다름"),
    _param("pressure_b_pa", "B 목표 분압", "Pa", 0, 200, 1, 30, "Recipe", "주입 시 챔버 B 분압의 목표값"),
    _param("temperature_c", "공정 온도", "°C", 100, 350, 5, 200, "Recipe", "균일 온도 가정; 실제 재료의 ALD window를 보증하지 않음"),
    _param("cycles", "반복 횟수", "cycle", 1, 150, 1, 50, "Recipe", "대표 한 사이클 결과의 선형 투영; 다중 사이클 독립 계산 아님"),
    _param("depth_um", "채널 깊이", "µm", 1, 200, 1, 40, "Chamber", "입구 x=0, 막힌 끝 x=L인 평행 평판 채널"),
    _param("gap_um", "채널 간격", "µm", 0.05, 2, 0.05, 0.2, "Chamber", "두 반응 벽 사이 초기 간격; 계산 중 고정"),
    _param("residence_time_s", "챔버 응답 시간", "s", 0.02, 2, 0.02, 0.15, "Chamber", "집중정수 분압 상승·배기 시정수"),
    _param("sticking_a", "A 유효 부착 확률", "", 0.00001, 0.01, 0.00001, 0.001, "Advanced", "200 °C 기준 가정값; 표면 화학을 묶은 유효 계수"),
    _param("sticking_b", "B 유효 반응 확률", "", 0.00001, 0.01, 0.00001, 0.0005, "Advanced", "200 °C 기준 가정값; A 종결 표면에 반응"),
    _param("site_density_nm2", "표면 자리 밀도", "nm⁻²", 1, 10, 0.5, 5, "Advanced", "기체 소모와 피복률을 연결하는 유효 반응 자리 밀도"),
    _param("gpc_saturated_nm", "포화 성장 환산량", "nm/cycle", 0.02, 0.2, 0.01, 0.1, "Advanced", "표면 1회 A→B 전환당 두께 환산값; 특정 재료 실측값 아님"),
    _param("activation_ev", "유효 활성화 에너지", "eV", 0, 0.3, 0.01, 0.12, "Advanced", "가정된 Arrhenius 온도 의존성; 탈착·열분해 미포함"),
    _param("fault_severity", "이상 강도", "", 0, 1, 0.05, 0.35, "Advanced", "선택한 이상 모드가 상류 공급·배기·온도에 작용하는 정도"),
]

FAULTS = [
    {"id": "none", "label": "정상", "description": "설정값 그대로 계산"},
    {"id": "precursor_starvation", "label": "전구체 공급 저하", "description": "A의 실제 목표 분압을 (1−강도)배로 감소"},
    {"id": "purge_restriction", "label": "배기 응답 지연", "description": "밸브 차단 후 배기 시정수를 (1+8×강도)배로 증가"},
    {"id": "heater_drift", "label": "히터 온도 하락", "description": "실제 온도가 설정값보다 최대 60 °C 낮아짐"},
]


def _validate(params: dict, fault: str) -> dict[str, float]:
    if not isinstance(params, dict):
        raise ValueError("params must be a dictionary")
    known = {item["key"]: item for item in PARAMS}
    unknown = set(params) - known.keys()
    if unknown:
        raise ValueError(f"Unknown ALD parameters: {sorted(str(k) for k in unknown)}")
    if not isinstance(fault, str) or fault not in {item["id"] for item in FAULTS}:
        raise ValueError(f"Unknown ALD fault: {fault}")
    result = {}
    for key, spec in known.items():
        value = params.get(key, spec["default"])
        if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
            raise ValueError(f"{key} must be a finite real number")
        if not spec["min"] <= value <= spec["max"]:
            raise ValueError(f"{key} must be between {spec['min']} and {spec['max']}")
        result[key] = float(value)
    if not result["cycles"].is_integer():
        raise ValueError("cycles must be an integer")
    if sum(result[k] for k in ("pulse_a_s", "purge_a_s", "pulse_b_s", "purge_b_s")) <= 0:
        raise ValueError("At least one recipe stage must have a positive duration")
    return result


def _jacobian_pattern(n: int):
    """Sparse dependencies of chamber pressures, gas fields, coverage and growth."""
    size = 2 + 4 * n
    matrix = lil_matrix((size, size), dtype=int)
    matrix[0, 0] = matrix[1, 1] = 1
    for i in range(n):
        pa, pb, theta, growth = 2 + i, 2 + n + i, 2 + 2 * n + i, 2 + 3 * n + i
        for gas, chamber in ((pa, 0), (pb, 1)):
            matrix[gas, gas] = matrix[gas, theta] = 1
            if i:
                matrix[gas, gas - 1] = 1
            else:
                matrix[gas, chamber] = 1
            if i < n - 1:
                matrix[gas, gas + 1] = 1
        for row in (theta, growth):
            matrix[row, pa] = matrix[row, pb] = matrix[row, theta] = 1
    return matrix.tocsr()


def _solve_cycle(p: dict[str, float], fault: str, *, cells: int = 36,
                 rtol: float = 2e-7) -> dict[str, Any]:
    """Finite-volume diffusion plus two-state Langmuir kinetics, integrated by BDF.

    The first spatial point is a cell centre, not the mathematical entrance.
    B consumes A-terminated sites; growth counts B conversions, not imposed KPIs.
    """
    if cells < 4 or cells > 160:
        raise ValueError("cells must be between 4 and 160")
    n = cells
    severity = p["fault_severity"]
    target_a = p["pressure_a_pa"] * (1 - severity if fault == "precursor_starvation" else 1)
    target_b = p["pressure_b_pa"]
    temperature_c = p["temperature_c"] - (60 * severity if fault == "heater_drift" else 0)
    temperature = temperature_c + 273.15
    fill_tau = p["residence_time_s"]
    pump_tau = fill_tau * (1 + 8 * severity if fault == "purge_restriction" else 1)
    gap = p["gap_um"] * 1e-6
    length = p["depth_um"] * 1e-6
    dx = length / n
    site_density = p["site_density_nm2"] * 1e18
    thermal_factor = math.exp(-p["activation_ev"] * EV / KB * (1 / temperature - 1 / REFERENCE_T_K))
    effective_sticking_a = p["sticking_a"] * thermal_factor
    effective_sticking_b = p["sticking_b"] * thermal_factor
    if max(effective_sticking_a, effective_sticking_b) > 1:
        raise ValueError("Temperature-adjusted sticking probability exceeds one")
    k_a = effective_sticking_a / (site_density * math.sqrt(2 * math.pi * MOLECULE_MASS_A * KB * temperature))
    k_b = effective_sticking_b / (site_density * math.sqrt(2 * math.pi * MOLECULE_MASS_B * KB * temperature))
    # Wide slit: hydraulic diameter ~ 2*gap, D_K = d_h * mean_speed / 3.
    d_a = 2 * gap / 3 * math.sqrt(8 * KB * temperature / (math.pi * MOLECULE_MASS_A))
    d_b = 2 * gap / 3 * math.sqrt(8 * KB * temperature / (math.pi * MOLECULE_MASS_B))
    capacity_pa = 2 / gap * site_density * KB * temperature
    stages = [
        ("A pulse", p["pulse_a_s"], target_a, 0.0),
        ("A purge", p["purge_a_s"], 0.0, 0.0),
        ("B pulse", p["pulse_b_s"], 0.0, target_b),
        ("B purge", p["purge_b_s"], 0.0, 0.0),
    ]
    initial = np.zeros(2 + 4 * n)
    all_t, all_y, stage_ends = [0.0], [initial.copy()], []
    start = 0.0
    overlap_pa_s = 0.0
    chamber_exact = [0.0, 0.0]
    sparsity = _jacobian_pattern(n)

    def laplacian(field: np.ndarray, boundary: float) -> np.ndarray:
        out = np.empty(n)
        out[1:-1] = field[:-2] - 2 * field[1:-1] + field[2:]
        # Half-cell Dirichlet inlet; zero flux at the closed far end.
        out[0] = 2 * boundary - 3 * field[0] + field[1]
        out[-1] = field[-2] - field[-1]
        return out / dx**2

    for name, duration, input_a, input_b in stages:
        if duration <= 0:
            stage_ends.append({"stage": name, "time_s": start})
            continue

        # Integrate the indicator from the analytic chamber response, not from
        # sparsely plotted samples that may miss a fast overlap transient.
        tau_a = fill_tau if input_a > 0 else pump_tau
        tau_b = fill_tau if input_b > 0 else pump_tau

        def overlap_at(time: float) -> float:
            pa = input_a + (chamber_exact[0] - input_a) * math.exp(-time / tau_a)
            pb = input_b + (chamber_exact[1] - input_b) * math.exp(-time / tau_b)
            return min(pa, pb)

        breakpoints = sorted({tau * multiple for tau in (tau_a, tau_b)
                              for multiple in (0.25, 0.5, 1, 2, 4, 8, 16, 32)
                              if tau * multiple < duration})
        overlap_pa_s += quad(overlap_at, 0, duration, points=breakpoints,
                             epsabs=1e-9, epsrel=1e-7, limit=100)[0]
        chamber_exact = [input_a + (chamber_exact[0] - input_a) * math.exp(-duration / tau_a),
                         input_b + (chamber_exact[1] - input_b) * math.exp(-duration / tau_b)]

        def rhs(_time: float, state: np.ndarray) -> np.ndarray:
            ca, cb = state[:2]
            pa = state[2:2 + n]
            pb = state[2 + n:2 + 2 * n]
            theta = state[2 + 2 * n:2 + 3 * n]
            reaction_a = k_a * pa * (1 - theta)
            reaction_b = k_b * pb * theta
            derivative = np.empty_like(state)
            derivative[0] = (input_a - ca) / (fill_tau if input_a > 0 else pump_tau)
            derivative[1] = (input_b - cb) / (fill_tau if input_b > 0 else pump_tau)
            derivative[2:2 + n] = d_a * laplacian(pa, ca) - capacity_pa * reaction_a
            derivative[2 + n:2 + 2 * n] = d_b * laplacian(pb, cb) - capacity_pa * reaction_b
            derivative[2 + 2 * n:2 + 3 * n] = reaction_a - reaction_b
            derivative[2 + 3 * n:] = reaction_b
            return derivative

        sample_times = np.linspace(start, start + duration, 49)[1:]
        solution = solve_ivp(rhs, (start, start + duration), initial, method="BDF",
                             t_eval=sample_times, rtol=rtol, atol=1e-9,
                             jac_sparsity=sparsity, max_step=duration / 12)
        if not solution.success:
            raise RuntimeError(f"ALD integration failed: {solution.message}")
        initial = solution.y[:, -1]
        all_t.extend(solution.t.tolist())
        all_y.extend(solution.y.T)
        start += duration
        stage_ends.append({"stage": name, "time_s": start})
    states = np.array(all_y)
    if not np.isfinite(states).all():
        raise RuntimeError("ALD integration returned non-finite values")
    theta_history = states[:, 2 + 2 * n:2 + 3 * n]
    # Never conceal significant unphysical integration results by clipping.
    if states[:, :2 + 2 * n].min() < -1e-5 or theta_history.min() < -1e-6 or theta_history.max() > 1 + 1e-6:
        raise RuntimeError("ALD integration violated pressure/coverage bounds: "
                           f"p_min={states[:, :2 + 2 * n].min():.3g}, "
                           f"theta_min={theta_history.min():.3g}, theta_max={theta_history.max():.9g}")
    growth = states[:, 2 + 3 * n:] * p["gpc_saturated_nm"]
    return {
        "time": np.array(all_t), "states": states, "growth": growth,
        "x_um": (np.arange(n) + 0.5) * dx * 1e6,
        "cells": n, "stages": stage_ends, "overlap_pa_s": overlap_pa_s,
        "effective": {"temperature_c": temperature_c, "pressure_a_pa": target_a,
                      "pressure_b_pa": target_b, "fill_tau_s": fill_tau,
                      "pump_tau_s": pump_tau, "diffusivity_a_m2_s": d_a,
                      "diffusivity_b_m2_s": d_b, "sticking_a": effective_sticking_a,
                      "sticking_b": effective_sticking_b, "cells": n,
                      "rtol": rtol, "atol": 1e-9, "fault": fault},
    }


def simulate(params: dict, fault: str = "none") -> dict:
    """Return JSON-serializable ALD metrics, traces and the projected film profile."""
    p = _validate(params, fault)
    raw = _solve_cycle(p, fault)
    n, t, states = raw["cells"], raw["time"], raw["states"]
    cycle_growth = raw["growth"][-1]
    thickness = cycle_growth * p["cycles"]
    near, deep = float(cycle_growth[0]), float(cycle_growth[-1])
    no_growth = near < 1e-12
    conformality = 0.0 if no_growth else 100 * deep / near
    overlap = float(raw["overlap_pa_s"])
    end_pressure = float(states[-1, 0] + states[-1, 1])
    theta = states[:, 2 + 2 * n:2 + 3 * n]
    diagnostics = [
        {"level": "info", "message": "일반 열 ALD의 축약 모델입니다. 특정 장비·재료 레시피에 대한 보정이나 실험 검증은 하지 않았습니다."},
        {"level": "info", "message": f"{n}개 셀의 반응·확산을 계산했습니다. 총 두께는 초기 한 사이클 × {int(p['cycles'])}회 투영값입니다."},
    ]
    if no_growth:
        diagnostics.append({"level": "warning", "message": "성장이 거의 없어 깊은 곳/입구 쪽 두께비는 정의되지 않습니다. 표시값 0%는 무성장 상태용 값입니다."})
    if overlap > 0.02:
        diagnostics.append({"level": "warning", "message": "A/B 잔류 분압이 겹칩니다. 모델 안에서 반복 표면 반응이 생길 수 있습니다. 실제 CVD·불순물 농도를 계산한 값은 아닙니다."})
    if end_pressure > 0.01 or float(theta[-1].max()) > 0.02:
        diagnostics.append({"level": "warning", "message": "사이클 종료 시 잔류 가스 또는 미반응 표면이 있습니다. 매 사이클 깨끗한 초기 상태를 가정한 총 두께 투영은 부정확할 수 있습니다."})
    if float(thickness.max()) * 2 > p["gap_um"] * 1000 * 0.1:
        diagnostics.append({"level": "warning", "message": "양쪽 막 두께가 초기 간격의 10%를 넘습니다. 채널 좁아짐을 생략하므로 반복 횟수에 대한 선형 투영의 적용 범위를 벗어날 수 있습니다."})
    # A sharp front occupying few cells requires a user-visible mesh qualification.
    transition_cells = int(np.count_nonzero((cycle_growth > near * 0.1) & (cycle_growth < near * 0.9)))
    if not no_growth and deep / near < 0.9 and transition_cells < 5:
        diagnostics.append({"level": "warning", "message": "침투 경계가 기본 격자보다 날카롭습니다. 형상의 정량 해석 전 공간 격자 세분화 확인이 필요합니다."})

    def line(name: str, values: np.ndarray) -> dict:
        return {"name": name, "values": np.asarray(values).tolist()}

    return {
        "model_version": MODEL_VERSION,
        "metrics": [
            {"key": "top_thickness_nm", "label": "1회 × N 투영 두께", "value": float(thickness[0]), "unit": "nm", "digits": 2},
            {"key": "gpc_nm", "label": "입구 쪽 1회 성장량", "value": near, "unit": "nm/cycle", "digits": 4},
            {"key": "conformality_pct", "label": "깊은 곳 / 입구 쪽", "value": conformality, "unit": "%", "digits": 1},
            {"key": "overlap_pa_s", "label": "A/B 분압 중첩 적분", "value": overlap, "unit": "Pa·s", "digits": 3},
            {"key": "cycle_time_s", "label": "사이클 시간", "value": float(t[-1]), "unit": "s", "digits": 2},
            {"key": "residual_pressure_pa", "label": "종료 잔류 분압", "value": end_pressure, "unit": "Pa", "digits": 3},
        ],
        "series": [
            {"key": "pressure", "title": "챔버와 채널 끝의 분압", "x_label": "시간 (s)", "y_label": "분압 (Pa)", "x": t.tolist(),
             "lines": [line("챔버 A", states[:, 0]), line("챔버 B", states[:, 1]),
                       line("깊은 곳 A", states[:, 1 + n]), line("깊은 곳 B", states[:, 1 + 2 * n])]},
            {"key": "coverage", "title": "A 종결 표면의 비율", "x_label": "시간 (s)", "y_label": "피복률 (0–1)", "x": t.tolist(),
             "lines": [line("입구 쪽", theta[:, 0]), line("깊은 곳", theta[:, -1])]},
            {"key": "growth", "title": "한 사이클 동안 누적 성장", "x_label": "시간 (s)", "y_label": "성장량 (nm)", "x": t.tolist(),
             "lines": [line("입구 쪽", raw["growth"][:, 0]), line("깊은 곳", raw["growth"][:, -1])]},
            {"key": "profile", "title": "깊이별 투영 막 두께", "x_label": "채널 깊이 (µm)", "y_label": "두께 (nm)", "x": raw["x_um"].tolist(),
             "lines": [line("막 두께", thickness)]},
        ],
        "spatial": {"kind": "ald", "x": raw["x_um"].tolist(), "values": thickness.tolist(), "unit": "nm"},
        # Display samples come from the solved first cycle, not final-profile scaling.
        "playback": {
            "time_s": t[::4].tolist(),
            "profiles_nm": raw["growth"][::4].tolist(),
            "profile_basis": "first_cycle_growth",
            "description": "Solved first-cycle growth; linear interpolation between display samples. Not N-cycle evolution.",
        },
        "diagnostics": diagnostics,
        "assumptions": [
            "열 ALD, 등온·1차원 평행 평판, Knudsen 확산, 막힌 채널 끝에서 무유속.",
            "일반 A/B 2상태 표면 반응이며 탈착·부산물·응축·기상 반응은 생략.",
            "입구 쪽/깊은 곳은 첫/마지막 셀 중심값으로 정확한 경계면 값과 다름.",
            "초기 표면은 모두 반응 가능. 한 사이클 결과를 반복 횟수로 곱하며 핵생성·채널 좁아짐·사이클 간 기억은 생략.",
            "72 u / 18 u 분자량과 표면 반응 상수는 교육용 가정이며 실제 TMA/H₂O 레시피의 검증값이 아님.",
            "표시된 분압 중첩은 모델 지표이며 실제 결함률·불순물 농도·공정 합격 기준이 아님.",
        ],
        "effective": {**raw["effective"], "stage_ends": raw["stages"], "parameters": p,
                      "cycle_projection": "first_cycle_times_N", "x_location": "cell_centres"},
    }
