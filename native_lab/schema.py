"""Public input contract; importing it does not load the native solver."""
from __future__ import annotations

import math
from numbers import Real
from native_lab import VERSION


def field(key, label, unit, default, low, high, group, description, integer=False):
    return dict(key=key, label=label, unit=unit, default=default, min=low,
                max=high, group=group, description=description, integer=integer)


COMMON = [
    field("width_nm", "개구 폭", "nm", 100, 30, 1000, "geometry", "홈 또는 마스크 개구부의 초기 폭."),
    field("pitch_nm", "계산 영역 폭", "nm", 400, 120, 3000, "geometry", "좌우 반사 경계 사이 거리. 옆 패턴의 대칭 반복을 가정합니다."),
    field("grid_nm", "격자 간격", "nm", 5, 2, 30, "numerics", "작을수록 형상 해상도와 계산 비용이 증가합니다."),
    field("rays_per_point", "표면점당 입자 수", "rays", 300, 100, 3000, "numerics", "Monte Carlo flux 표본 수. 늘려서 표본 잡음의 영향을 확인하세요.", True),
    field("seed", "난수 시드", "", 20261003, 0, 2147483647, "numerics", "동일 버전·단일 스레드·동일 조건에서 재현성 확인에 사용합니다.", True),
]
ETCH = COMMON + [
    field("mask_nm", "마스크 두께", "nm", 80, 20, 500, "geometry", "기판 위 보호 마스크. 기본 엔진의 유효 마스크 재료를 사용합니다."),
    field("duration_s", "식각 시간", "s", 5, 0, 30, "recipe", "정상 입사 플럭스를 유지하는 시간. 점화 과도응답은 포함하지 않습니다."),
    field("ion_flux", "입사 이온 플럭스", "10¹⁵ cm⁻² s⁻¹", 12, 0, 40, "boundary", "구조 입구의 경계조건. RF 전력 W와 동일하지 않습니다."),
    field("fluorine_flux", "F 라디칼 플럭스", "10¹⁵ cm⁻² s⁻¹", 1800, 0, 4000, "boundary", "SF₆/O₂ 모델의 식각종 공급량. sccm을 직접 변환한 값이 아닙니다."),
    field("oxygen_flux", "O 패시베이션 플럭스", "10¹⁵ cm⁻² s⁻¹", 100, 0, 500, "boundary", "산소계 표면 보호 반응의 공급량."),
    field("energy_ev", "평균 이온 에너지", "eV", 100, 20, 250, "boundary", "입사 이온 에너지 분포의 평균. 바이어스 전압과 일대일 대응하지 않습니다."),
    field("energy_sigma_ev", "에너지 표준편차", "eV", 10, 0, 50, "boundary", "입사 에너지 분포 폭."),
    field("ion_exponent", "이온 방향성 지수", "cosⁿ θ", 500, 5, 1000, "boundary", "클수록 수직 입사에 집중됩니다. 압력으로부터 계산한 값은 아닙니다."),
    field("output_steps", "시간 구간 수", "", 12, 4, 30, "numerics", "각 구간을 CFL 제한으로 계산하고 끝 형상을 저장합니다. 구간마다 seed+i를 사용합니다.", True),
]
ALD = COMMON + [
    field("depth_nm", "초기 홈 깊이", "nm", 600, 100, 3000, "geometry", "초기 실리콘 홈의 깊이. 형상은 각 성장 묶음 후 다시 계산됩니다."),
    field("cycles", "ALD 사이클 수", "cycles", 200, 1, 500, "recipe", "TMA 제한 반응을 대표하며 반대 반응과 퍼지는 완결된다고 가정합니다.", True),
    field("pulse_s", "제한 반응물 노출 시간", "s", 0.05, 0, 0.5, "recipe", "한 사이클의 TMA 노출. 전체 사이클 시간과 다릅니다."),
    field("pressure_pa", "TMA 입구 분압", "Pa", 3, 0, 10, "recipe", "입구 Maxwellian 열 플럭스로 변환합니다. 챔버 총압과 다릅니다."),
    field("temperature_c", "균일 온도", "°C", 300, 150, 350, "recipe", "기체 열속도 계산에 사용. 계수의 온도 의존성은 아직 보정하지 않았습니다."),
    field("sticking", "빈 자리 부착 확률", "", 0.0075, 0.0001, 0.1, "kinetics", "Aguinsky et al. Table 2 TMA 모델 계수. 새 장비에 보정된 값은 아닙니다."),
    field("evaporation_flux", "탈착 플럭스", "10¹⁹ m⁻² s⁻¹", 3, 0, 10, "kinetics", "Aguinsky et al. Table 2 기본값. 피복률과 곱해 탈착 손실을 계산합니다."),
    field("site_density_nm2", "반응 자리 밀도", "nm⁻²", 5, 1, 10, "kinetics", "현재 연구 가정값. 논문의 실험 피팅을 재현했다고 주장하지 않습니다."),
    field("gpc_nm", "완전 피복 시 성장량", "nm/cycle", 0.112, 0.03, 0.2, "kinetics", "포화 성장 환산값. 실제 성장은 위치별 피복률과 곱해집니다."),
    field("bundle_cycles", "형상 갱신 최대 묶음", "cycles", 20, 1, 50, "numerics", "한 번의 표면 이동을 0.4격자 이하로 자동 제한합니다. 원자별 계산은 아닙니다.", True),
    field("coverage_dt_s", "피복률 최대 시간 간격", "s", 0.001, 0.0001, 0.005, "numerics", "반응 속도를 고려해 더 작은 간격으로 자동 제한합니다."),
]
SOURCES = [
    {"title": "ViennaPS 4.6.2 source", "url": "https://github.com/ViennaTools/ViennaPS/tree/v4.6.2"},
    {"title": "SF₆/O₂ feature-scale model", "url": "https://doi.org/10.1116/1.1830495"},
    {"title": "Aguinsky et al. (2022), ALD coverage / Table 2", "url": "https://arxiv.org/abs/2210.00749"},
]


def schema():
    return {"version": VERSION, "models": {
        "etch": {"label": "Si · SF₆/O₂ Etch", "params": ETCH,
                 "engine": "ViennaPS SF6O2Etching · Monte Carlo + level set"},
        "ald": {"label": "Al₂O₃ · TMA 제한 ALD", "params": ALD,
                "engine": "ViennaPS SingleParticleALD · Langmuir + Monte Carlo + level set"},
    }, "sources": SOURCES}


def validate(payload):
    if not isinstance(payload, dict) or set(payload) - {"model", "params"}:
        raise ValueError("Expected model and params only")
    model = payload.get("model")
    if model not in ("ald", "etch"):
        raise ValueError("model must be ald or etch")
    raw = payload.get("params", {})
    fields = ALD if model == "ald" else ETCH
    specs = {p["key"]: p for p in fields}
    if not isinstance(raw, dict) or set(raw) - specs.keys():
        raise ValueError("Unknown parameter or invalid params object")
    params = {}
    for key, spec in specs.items():
        value = raw.get(key, spec["default"])
        if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
            raise ValueError(f"{key}: finite number required")
        if not spec["min"] <= value <= spec["max"]:
            raise ValueError(f"{key}: {spec['min']}–{spec['max']} 범위가 필요합니다.")
        if spec["integer"] and int(value) != value:
            raise ValueError(f"{key}: integer required")
        params[key] = int(value) if spec["integer"] else float(value)
    if params["width_nm"] > params["pitch_nm"] * 0.75:
        raise ValueError("개구 폭은 계산 영역 폭의 75% 이하여야 합니다.")
    if params["width_nm"] < params["grid_nm"] * 6:
        raise ValueError("개구 폭에 최소 6개의 격자가 필요합니다.")
    if params["pitch_nm"] / params["grid_nm"] > 800:
        raise ValueError("가로 격자 수는 800 이하로 설정하세요.")
    if model == "ald" and params["depth_nm"] / params["grid_nm"] > 1000:
        raise ValueError("깊이 격자 수는 1000 이하로 설정하세요.")
    if model == "etch" and params["mask_nm"] < 3 * params["grid_nm"]:
        raise ValueError("마스크 두께에 최소 3개의 격자가 필요합니다.")
    return {"model": model, "params": params}
