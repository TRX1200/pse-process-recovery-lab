"""Deterministic Ar global-plasma / generic reactive etch teaching model.

SI units internally; electron temperatures and particle energies use eV.
See docs/ETCH_MODEL.md for equations, references and uncalibrated closures.
"""

from __future__ import annotations

import math
from numbers import Real
from typing import Any

MODEL_VERSION = "etch-ar-global-0.1.1"
E_CHARGE = 1.602176634e-19
K_B = 1.380649e-23
M_E = 9.1093837139e-31
AMU = 1.66053906892e-27
M_AR = 39.948 * AMU
EPSILON_0 = 8.8541878128e-12
MTORR_TO_PA = 133.322387415 / 1000.0
# sccm explicitly uses 273.15 K and 101325 Pa standard conditions.
PARTICLES_PER_SCCM_S = 101325.0 / (K_B * 273.15) * 1e-6 / 60.0


def _param(key: str, label: str, unit: str, low: float, high: float,
           step: float, default: float, group: str, description: str) -> dict:
    return dict(key=key, label=label, unit=unit, min=low, max=high,
                step=step, default=default, group=group, description=description)


PARAMS = [
    _param("source_power_w", "소스 전력", "W", 0, 3000, 10, 600, "Recipe", "발진기 전력. 반사·결합·듀티를 거쳐 흡수 전력을 계산합니다."),
    _param("pressure_mtorr", "압력 설정", "mTorr", 1, 150, 1, 20, "Recipe", "정압 제어 가정. 압력 고장은 실제 압력에 적용됩니다."),
    _param("flow_sccm", "총 유량", "sccm", 1, 500, 1, 100, "Recipe", "273.15 K, 1 atm 기준. 체류 시간과 반응 가스 공급량을 바꿉니다."),
    _param("reactive_fraction", "반응 가스 몰분율", "fraction", 0, .2, .005, .04, "Recipe", "Ar 내 가상 X2 첨가. 실제 SF6/CF4 반응망이 아니며 0.05 초과는 희석 가정에 주의합니다."),
    _param("bias_voltage_v", "바이어스 크기", "V", 0, 500, 5, 120, "Recipe", "웨이퍼의 음의 DC 바이어스 절댓값. RF 파형·IEDF는 풀지 않습니다."),
    _param("process_time_s", "처리 시간", "s", 0, 600, 1, 60, "Recipe", "정상 플라즈마에 초기 피복률 0인 표면을 노출하는 시간입니다."),
    _param("source_duty", "소스 듀티", "fraction", 0, 1, .05, 1, "Recipe", "평균 흡수 전력 근사이며 펄스별 켜짐·꺼짐 응답은 계산하지 않습니다."),
    _param("fault_severity", "고장 강도", "fraction", 0, 1, .05, .35, "Recipe", "선택한 고장의 상류 물리 조건 변화량입니다. 0은 정상과 같습니다."),
    _param("reflected_fraction", "RF 반사 전력 비율", "fraction", 0, 1, .01, .04, "Chamber", "반사 전력/순방향 전력. 1이면 소스 흡수 전력이 0입니다."),
    _param("coupling_efficiency", "전력 결합 효율", "fraction", 0, 1, .01, .75, "Chamber", "전달된 소스 전력 중 전자계 흡수 비율. 임피던스는 계산하지 않습니다."),
    _param("gas_temperature_k", "기체 온도", "K", 250, 800, 10, 350, "Chamber", "중성 기체 온도 입력. 열전달 방정식으로 예측하지 않습니다."),
    _param("radius_mm", "챔버 반경", "mm", 80, 300, 5, 180, "Chamber", "원통형 플라즈마 유효 반경입니다."),
    _param("height_mm", "플라즈마 높이", "mm", 30, 300, 5, 100, "Chamber", "원통형 플라즈마 유효 높이입니다."),
    _param("wall_recombination", "벽 라디칼 손실 확률", "fraction", .001, 1, .005, .05, "Chamber", "벽에서 X가 제거될 확률. 재결합 생성물은 반응망에 재주입하지 않습니다."),
    _param("radial_nonuniformity", "가정한 이온 플럭스 편차", "fraction", 0, .5, .01, .12, "Chamber", "면적 평균이 1인 포물선 이온 플럭스 분포의 계수. 공간 PDE 결과가 아닙니다."),
    _param("ion_cross_section_1e19_m2", "이온-중성 충돌 단면적", "10^-19 m²", 1, 30, .5, 10, "Advanced", "일정한 유효 Ar 충돌 단면적 가정. 실제 에너지 의존 단면적이 아닙니다."),
    _param("radical_mass_amu", "가상 라디칼 질량", "u", 1, 100, 1, 19, "Advanced", "열운동 플럭스를 계산하는 X의 질량. 19는 F와 유사한 질량일 뿐 F 화학 모델은 아닙니다."),
    _param("dissociation_prefactor_1e14_m3_s", "해리 계수 전인자", "10^-14 m³/s", .01, 10, .1, 2, "Advanced", "가상 X2의 k_d = A exp(-E_d/Te). 문헌 보정 전인 조정 계수입니다."),
    _param("dissociation_threshold_ev", "해리 에너지 계수", "eV", 1, 15, .5, 5, "Advanced", "가상 반응의 속도 계수와 에너지 손실에 쓰는 가정값입니다."),
    _param("sticking_probability", "표면 반응 흡착 확률", "fraction", 0, 1, .01, .15, "Advanced", "X가 비어 있는 표면 반응 자리에 흡착할 확률입니다."),
    _param("surface_site_density_1e18_m2", "표면 자리 밀도", "10^18 m^-2", 1, 20, .5, 7, "Advanced", "표면 피복률 방정식의 단위 면적당 반응 자리 수입니다."),
    _param("thermal_desorption_s", "열적 탈착 계수", "s^-1", 0, 20, .1, .1, "Advanced", "기판 온도 의존성을 대신하는 입력 계수. 온도 예측은 없습니다."),
    _param("chemical_rate_s", "자발적 표면 제거 계수", "s^-1", 0, 20, .1, 2, "Advanced", "피복된 자리의 자발적 제거 속도. 특정 재료의 측정값이 아닙니다."),
    _param("etch_yield_scale", "이온 보조 제거 계수", "atoms/ion", 0, 5, .05, 1.5, "Advanced", "Y = 계수 × max(sqrt(E/Eth)-1,0). 일반화한 교육용 반응 수율입니다."),
    _param("etch_threshold_ev", "이온 보조 문턱", "eV", 1, 100, 1, 20, "Advanced", "가정한 이온 보조 반응 문턱 에너지입니다."),
    _param("sputter_yield_scale", "타깃 스퍼터 계수", "atoms/ion", 0, 1, .01, .15, "Advanced", "피복되지 않은 표면에도 작동하는 일반화한 물리 제거 계수입니다."),
    _param("sputter_threshold_ev", "타깃 스퍼터 문턱", "eV", 1, 300, 5, 60, "Advanced", "타깃의 가정한 물리적 제거 문턱입니다."),
    _param("mask_yield_scale", "마스크 스퍼터 계수", "atoms/ion", 0, 1, .01, .05, "Advanced", "마스크의 일반화한 물리 제거 계수입니다."),
    _param("mask_threshold_ev", "마스크 스퍼터 문턱", "eV", 1, 300, 5, 40, "Advanced", "가정한 마스크 제거 문턱입니다."),
    _param("target_density_1e28_m3", "타깃 원자 밀도", "10^28 m^-3", 1, 10, .1, 5, "Advanced", "제거 원자 플럭스를 두께로 변환합니다. 기본값은 Si와 비슷한 크기의 가정값입니다."),
    _param("mask_density_1e28_m3", "마스크 원자 밀도", "10^28 m^-3", 1, 10, .1, 5, "Advanced", "마스크 제거량의 두께 환산에 쓰는 가정값입니다."),
]

FAULTS = [
    {"id": "none", "label": "정상 조건", "description": "레시피와 장비 설정값을 그대로 적용합니다."},
    {"id": "rf_mismatch", "label": "RF 매칭 이탈", "description": "반사율을 r + (1-r)×강도로 높여 흡수 전력을 감소시킵니다."},
    {"id": "pressure_drift", "label": "압력 제어 편차", "description": "실제 압력을 설정값×(1+강도)로 바꿉니다."},
    {"id": "gas_starvation", "label": "반응 가스 공급 저하", "description": "반응 가스 유량을 (1-강도)배로 줄입니다. Ar 유량과 압력 제어는 유지합니다."},
    {"id": "wall_recombination", "label": "벽 상태 변화", "description": "벽 라디칼 손실 확률을 γ + (1-γ)×강도로 높입니다."},
]


def _validated(params: dict, fault: str) -> dict[str, float]:
    if not isinstance(params, dict):
        raise ValueError("params must be an object")
    specs = {p["key"]: p for p in PARAMS}
    unknown = set(params) - set(specs)
    if unknown:
        raise ValueError(f"Unknown Etch parameter(s): {sorted(map(str, unknown))}")
    if not isinstance(fault, str) or fault not in {f["id"] for f in FAULTS}:
        raise ValueError("Unknown Etch fault")
    result = {}
    for key, spec in specs.items():
        value = params.get(key, spec["default"])
        if isinstance(value, bool) or not isinstance(value, Real):
            raise ValueError(f"{key} must be a finite number")
        value = float(value)
        if not math.isfinite(value) or not spec["min"] <= value <= spec["max"]:
            raise ValueError(f"{key} must be between {spec['min']} and {spec['max']}")
        result[key] = value
    return result


def _rates(te_ev: float) -> tuple[float, float, float]:
    """Ar Maxwellian rate fits in m^3/s, restricted by the solver to 1-7 eV."""
    ionization = 2.34e-14 * te_ev ** .59 * math.exp(-17.44 / te_ev)
    excitation = 2.48e-14 * te_ev ** .33 * math.exp(-12.78 / te_ev)
    elastic = (.084 + .537 * te_ev + 1.192 * te_ev ** 2) * 1e-14
    return ionization, excitation, elastic


def _bisect(function, low: float, high: float) -> float:
    """Find the root of a bracketed monotonically increasing function."""
    for _ in range(80):
        mid = (low + high) / 2
        if function(mid) > 0:
            high = mid
        else:
            low = mid
    return (low + high) / 2


def _yield(energy_ev: float, threshold_ev: float, scale: float) -> float:
    return scale * max(math.sqrt(energy_ev / threshold_ev) - 1.0, 0.0)


def _coverage_integral(rate: float, time_s: float) -> float:
    """Integral of 1-exp(-rate*t); stable even at very short exposure."""
    x = rate * time_s
    if x < 1e-4:
        return time_s * (x / 2 - x * x / 6 + x ** 3 / 24)
    return time_s + math.expm1(-x) / rate


def simulate(params: dict, fault: str = "none") -> dict[str, Any]:
    """Solve a reduced steady plasma plus analytic surface-coverage transient."""
    p = _validated(params, fault)
    severity = p["fault_severity"]
    reflected = p["reflected_fraction"]
    pressure = p["pressure_mtorr"]
    reactive_flow = p["flow_sccm"] * p["reactive_fraction"]
    argon_flow = p["flow_sccm"] - reactive_flow
    wall_loss = p["wall_recombination"]
    if fault == "rf_mismatch":
        reflected += (1 - reflected) * severity
    elif fault == "pressure_drift":
        pressure *= 1 + severity
    elif fault == "gas_starvation":
        reactive_flow *= 1 - severity
    elif fault == "wall_recombination":
        wall_loss += (1 - wall_loss) * severity
    actual_flow = argon_flow + reactive_flow
    fraction = reactive_flow / actual_flow
    absorbed = p["source_power_w"] * (1 - reflected) * p["coupling_efficiency"] * p["source_duty"]
    radius, height = p["radius_mm"] * 1e-3, p["height_mm"] * 1e-3
    volume = math.pi * radius ** 2 * height
    area = 2 * math.pi * radius * (radius + height)
    ng = pressure * MTORR_TO_PA / (K_B * p["gas_temperature_k"])
    argon_density = ng * (1 - fraction)
    mean_free_path = 1 / (ng * p["ion_cross_section_1e19_m2"] * 1e-19)
    h_l = .86 / math.sqrt(3 + height / (2 * mean_free_path))
    h_r = .80 / math.sqrt(4 + radius / mean_free_path)
    effective_area = 2 * math.pi * (h_l * radius ** 2 + h_r * radius * height)
    residence = ng * volume / (actual_flow * PARTICLES_PER_SCCM_S)
    radical_speed = math.sqrt(8 * K_B * p["gas_temperature_k"] / (math.pi * p["radical_mass_amu"] * AMU))
    wafer_radius_mm = p["radius_mm"] * .8
    wafer_area = math.pi * (wafer_radius_mm * 1e-3) ** 2
    radical_loss = 1 / residence + wall_loss * radical_speed * (area - wafer_area) / (4 * volume)
    parent_source = reactive_flow * PARTICLES_PER_SCCM_S / volume
    diagnostics = []

    def particle_residual(te):
        return argon_density * _rates(te)[0] - math.sqrt(E_CHARGE * te / M_AR) * effective_area / volume

    bracketed = particle_residual(1.0) <= 0 <= particle_residual(7.0)
    te = ne = ion_flux = radical_density = radical_flux = energy = radical_source = 0.0
    sheath = dissociation_power = collision_energy = power_residual = balance_residual = 0.0
    status = "steady"
    if absorbed <= 0:
        status = "off"
        diagnostics.append({"level": "info", "message": "소스 흡수 전력이 0이므로 전자·이온·라디칼 생성과 식각을 0으로 계산합니다. 바이어스만으로 점화시키지 않습니다."})
    elif not bracketed:
        status = "outside_rate_fit"
        diagnostics.append({"level": "warning", "message": "1–7 eV Ar 속도식 범위에서 입자 수지 해가 없습니다. 플라즈마·식각 출력 0은 계산 불가 표시이며 실제 방전 소멸 예측이 아닙니다."})
    else:
        te = _bisect(particle_residual, 1.0, 7.0)
        u_b = math.sqrt(E_CHARGE * te / M_AR)
        k_iz, k_ex, k_el = _rates(te)
        collision_energy = 15.76 + 12.14 * k_ex / k_iz + 3 * M_E / M_AR * te * k_el / k_iz
        # 2 Te escaping electrons + 5.2 Te floating-wall ions, both in eV.
        energy_per_pair = collision_energy + 7.2 * te
        dissociation_rate = p["dissociation_prefactor_1e14_m3_s"] * 1e-14 * math.exp(-p["dissociation_threshold_ev"] / te)
        ar_power_per_density = E_CHARGE * u_b * effective_area * energy_per_pair

        def dissociations(density):
            parent_density = parent_source / (1 / residence + dissociation_rate * density)
            return dissociation_rate * density * parent_density * volume

        def power_error(density):
            return density * ar_power_per_density + E_CHARGE * p["dissociation_threshold_ev"] * dissociations(density) - absorbed

        ne = _bisect(power_error, 0.0, absorbed / ar_power_per_density)
        dissociation_power = E_CHARGE * p["dissociation_threshold_ev"] * dissociations(ne)
        radical_source = 2 * dissociations(ne) / volume
        ion_flux = h_l * ne * u_b
        # A DC Child-Langmuir scale followed by an explicitly heuristic
        # collision attenuation. This does not solve a collisional RF sheath.
        floating_drop = .5 * te * math.log(M_AR / (2 * math.pi * M_E))
        sheath_drop = p["bias_voltage_v"] + floating_drop
        sheath = math.sqrt((4 / 9) * EPSILON_0 * math.sqrt(2 * E_CHARGE / M_AR) * sheath_drop ** 1.5 / (E_CHARGE * ion_flux))
        energy = .5 * te + sheath_drop / (1 + sheath / mean_free_path)
        balance_residual = abs(particle_residual(te)) / (argon_density * k_iz)
        power_residual = abs(power_error(ne)) / absorbed

    assist_yield = _yield(energy, p["etch_threshold_ev"], p["etch_yield_scale"])
    physical_yield = _yield(energy, p["sputter_threshold_ev"], p["sputter_yield_scale"])
    mask_yield = _yield(energy, p["mask_threshold_ev"], p["mask_yield_scale"])
    sites = p["surface_site_density_1e18_m2"] * 1e18
    target_density = p["target_density_1e28_m3"] * 1e28
    mask_density = p["mask_density_1e28_m3"] * 1e28

    # q=r^2/Rw^2 is uniform in wafer area. The profile has mean exactly one.
    def radial_ion_flux(q):
        return ion_flux * (1 + p["radial_nonuniformity"] * (.5 - q))

    def wafer_radical_consumption(density):
        adsorption_rate = p["sticking_probability"] * density * radical_speed / (4 * sites)
        rates = []
        for i in range(41):
            clearance = p["chemical_rate_s"] + radial_ion_flux(i / 40) * assist_yield / sites
            denominator = adsorption_rate + p["thermal_desorption_s"] + clearance
            theta = adsorption_rate / denominator if denominator > 0 else 0.0
            rates.append(sites * theta * clearance)
        average = (sum(rates) - .5 * (rates[0] + rates[-1])) / 40
        return average * wafer_area / volume

    def radical_error(density):
        return density * radical_loss + wafer_radical_consumption(density) - radical_source

    if radical_source > 0:
        radical_density = _bisect(radical_error, 0, radical_source / radical_loss)
        radical_flux = radical_density * radical_speed / 4
    radical_residual = abs(radical_error(radical_density)) / radical_source if radical_source > 0 else 0.0
    adsorption = p["sticking_probability"] * radical_flux / sites

    def surface(local_ion_flux: float, time_s: float) -> tuple[float, float, float, float]:
        assisted = local_ion_flux * assist_yield
        removal = sites * p["chemical_rate_s"] + assisted
        decay = adsorption + p["thermal_desorption_s"] + p["chemical_rate_s"] + assisted / sites
        steady_coverage = adsorption / decay if decay > 0 else 0.0
        coverage = steady_coverage * -math.expm1(-decay * time_s)
        integrated_coverage = steady_coverage * _coverage_integral(decay, time_s) if decay > 0 else 0.0
        sputter = local_ion_flux * physical_yield
        depth = (removal * integrated_coverage + sputter * time_s) / target_density * 1e9
        rate = (removal * steady_coverage + sputter) / target_density * 1e9 * 60
        mask_depth = local_ion_flux * mask_yield / mask_density * time_s * 1e9
        return depth, rate, coverage, mask_depth

    area_samples = [surface(radial_ion_flux(i / 100), p["process_time_s"]) for i in range(101)]

    def area_mean(index):
        return (sum(row[index] for row in area_samples) - .5 * (area_samples[0][index] + area_samples[-1][index])) / 100

    depth, rate, coverage, mask_depth = (area_mean(i) for i in range(4))
    mask_rate = ion_flux * mask_yield / mask_density * 1e9 * 60
    selectivity = rate / mask_rate if mask_rate > 0 else 0.0
    nu = (max(row[0] for row in area_samples) - min(row[0] for row in area_samples)) / (2 * depth) * 100 if depth > 0 else 0.0
    base_times = [p["process_time_s"] * i / 120 for i in range(121)]
    # Resolve fast surface kinetics in the displayed trace as well as the long
    # process interval. Eight time constants cover >99.96% of the exponential
    # response; 96 intervals keep linear display interpolation below ~0.1% of
    # the equilibrium coverage. This changes sampling, not the analytic solution.
    display_decay = adsorption + p["thermal_desorption_s"] + p["chemical_rate_s"] + ion_flux * assist_yield / sites
    transient_end = min(p["process_time_s"], 8 / display_decay) if display_decay > 0 else 0
    transient_times = [transient_end * i / 96 for i in range(97)]
    times = sorted(set(base_times + transient_times))
    frame_times = sorted(set(base_times[::4] + transient_times[::4] + [p["process_time_s"]]))
    time_rows = [surface(ion_flux, t) for t in times]
    spatial_x = [wafer_radius_mm * (-1 + i / 40) for i in range(81)]
    spatial_values = [surface(radial_ion_flux((x / wafer_radius_mm) ** 2), p["process_time_s"])[0] for x in spatial_x]
    temperatures = [1 + 6 * i / 80 for i in range(81)]
    energies = [600 * i / 120 for i in range(121)]

    diagnostics.append({"level": "info", "message": "Ar 전자온도는 입자 수지, 전자밀도는 에너지 수지에서 계산합니다. 고정 압력·형상에서 전력 증가가 Te를 직접 올리지 않는 것은 이 모델의 특성입니다."})
    diagnostics.append({"level": "warning", "message": "가상 X2 반응·표면 수율·방사형 분포는 조정 가능한 가정입니다. 실제 Si/SF6·산화막/불소계 레시피나 상용 TCAD의 검증 결과가 아닙니다."})
    if mask_rate == 0:
        diagnostics.append({"level": "info", "message": "마스크 식각률이 0이므로 선택비는 정의되지 않습니다. 화면의 0은 계산 불가 표시입니다."})
    if fraction > .05:
        diagnostics.append({"level": "warning", "message": "반응 가스 분율이 5%를 초과했습니다. Ar 우세·전자 부착 무시 가정의 신뢰도가 낮아집니다."})
    if ne / argon_density > .01:
        diagnostics.append({"level": "warning", "message": "계산 전리도가 1%를 초과했습니다. 중성 기체 고갈·단계 이온화·가열을 무시한 해의 정량 해석에 주의하세요."})
    if sheath > height * .2:
        diagnostics.append({"level": "warning", "message": "추정 쉬스가 플라즈마 높이의 20%를 초과하여 벌크/얇은 쉬스 가정이 약해졌습니다."})
    if p["source_duty"] < 1 and absorbed > 0:
        diagnostics.append({"level": "info", "message": "듀티는 평균 전력에만 적용됩니다. 실제 펄스 방전의 점화·잔광·주파수 효과는 포함되지 않습니다."})

    def metric(key, label, value, unit, digits=2):
        return dict(key=key, label=label, value=value, unit=unit, digits=digits)

    return {
        "model_version": MODEL_VERSION,
        "metrics": [
            metric("etch_depth_nm", "면적 평균 식각 깊이", depth, "nm", 1),
            metric("etch_rate_nm_min", "정상 식각률", rate, "nm/min", 1),
            metric("electron_temperature_ev", "전자온도", te, "eV"),
            metric("electron_density_m3", "벌크 전자밀도", ne, "m^-3", 3),
            metric("ion_energy_ev", "평균 이온 에너지 근사", energy, "eV", 1),
            metric("selectivity", "정상 선택비" if mask_rate > 0 else "선택비 (분모 0)", selectivity, "ratio", 1),
            metric("mask_loss_nm", "마스크 손실", mask_depth, "nm", 1),
            metric("absorbed_power_w", "소스 흡수 전력", absorbed, "W", 1),
            metric("nonuniformity_pct", "깊이 비균일도", nu, "%"),
            metric("ion_flux_m2_s", "면적 평균 이온 플럭스", ion_flux, "m^-2 s^-1", 3),
            metric("radical_flux_m2_s", "라디칼 플럭스", radical_flux, "m^-2 s^-1", 3),
        ],
        "series": [
            {"key": "depth", "title": "균일 플럭스 기준 처리 깊이", "x_label": "시간 (s)", "y_label": "두께 (nm)", "x": times,
             "lines": [{"name": "타깃 제거", "values": [r[0] for r in time_rows]}, {"name": "마스크 손실", "values": [r[3] for r in time_rows]}]},
            {"key": "coverage", "title": "균일 플럭스 기준 표면 피복률", "x_label": "시간 (s)", "y_label": "피복률 (0–1)", "x": times,
             "lines": [{"name": "반응종 피복률", "values": [r[2] for r in time_rows]}]},
            {"key": "particle_balance", "title": "전자온도를 결정하는 입자 수지", "x_label": "전자온도 (eV)", "y_label": "빈도 (s^-1)", "x": temperatures,
             "lines": [{"name": "Ar 이온화", "values": [argon_density * _rates(t)[0] for t in temperatures]}, {"name": "Bohm 벽 손실", "values": [math.sqrt(E_CHARGE * t / M_AR) * effective_area / volume for t in temperatures]}]},
            {"key": "yield", "title": "가정한 에너지별 제거 수율", "x_label": "이온 에너지 (eV)", "y_label": "수율 (atoms/ion)", "x": energies,
             "lines": [{"name": "완전 피복 시 이온 보조", "values": [_yield(e, p["etch_threshold_ev"], p["etch_yield_scale"]) for e in energies]}, {"name": "타깃 스퍼터", "values": [_yield(e, p["sputter_threshold_ev"], p["sputter_yield_scale"]) for e in energies]}, {"name": "마스크 스퍼터", "values": [_yield(e, p["mask_threshold_ev"], p["mask_yield_scale"]) for e in energies]}]},
        ],
        "spatial": {"kind": "etch", "x": spatial_x, "values": spatial_values, "unit": "nm", "x_unit": "mm", "label": "가정한 방사형 플럭스에 따른 식각 깊이"},
        "playback": {
            "time_s": frame_times,
            "profiles_nm": [[surface(radial_ion_flux((x / wafer_radius_mm) ** 2), t)[0]
                             for x in spatial_x] for t in frame_times],
            "profile_basis": "etch_depth",
            "description": "Analytic surface transient under steady plasma; interpolated display samples. No ignition or RF transient.",
        },
        "diagnostics": diagnostics,
        "assumptions": [
            "Maxwellian EEDF, 1–7 eV Ar 속도식, 전기양성·준중성·낮은 전리도의 0D 모델입니다.",
            "정상 기체/플라즈마에 피복률 0의 표면을 노출합니다. 표면 피복률의 선형 ODE를 적분하며 초기 흡착의 기체 피드백은 생략합니다.",
            "X2→2X 해리·벽 손실·표면 반응은 교육용 계수이며 특정 가스의 검증된 반응망이 아닙니다.",
            "바이어스 전원은 독립적입니다. 쉬스 이온 에너지는 DC 척도와 충돌 감쇠 근사이며 RF IEDF·전자 가열을 풀지 않습니다.",
            "방사형 이온 플럭스는 면적 평균이 1인 가정 분포입니다. 전자기장·공간 플라즈마·패턴 형상 PDE는 풀지 않습니다.",
            "실제 장비 데이터와 비교 보정하지 않았습니다. 미리 정한 고장 KPI가 아니라 변경된 상류 조건으로 수지를 다시 풉니다.",
        ],
        "effective": {
            "status": status, "fault": fault, "actual_pressure_mtorr": pressure,
            "actual_flow_sccm": actual_flow, "reactive_flow_sccm": reactive_flow,
            "reactive_fraction": fraction, "reflected_fraction": reflected,
            "wall_recombination": wall_loss, "absorbed_power_w": absorbed,
            "neutral_density_m3": ng, "argon_density_m3": argon_density,
            "electron_density_m3": ne, "electron_temperature_ev": te,
            "mean_free_path_mm": mean_free_path * 1000, "sheath_scale_mm": sheath * 1000,
            "residence_time_s": residence, "radical_density_m3": radical_density,
            "ion_flux_m2_s": ion_flux, "radical_flux_m2_s": radical_flux,
            "ion_energy_ev": energy, "surface_coverage": coverage,
            "collision_energy_per_pair_ev": collision_energy,
            "dissociation_power_w": dissociation_power,
            "power_balance_relative_residual": power_residual,
            "particle_balance_relative_residual": balance_residual,
            "radical_balance_relative_residual": radical_residual,
            "wafer_radical_consumption_s": wafer_radical_consumption(radical_density) * volume,
            "radical_generation_s": radical_source * volume,
            "selectivity_defined": mask_rate > 0,
            "wafer_radius_mm_assumed": wafer_radius_mm,
            "etch_rate_nm_min": rate, "etch_depth_nm": depth, "mask_rate_nm_min": mask_rate,
        },
    }
