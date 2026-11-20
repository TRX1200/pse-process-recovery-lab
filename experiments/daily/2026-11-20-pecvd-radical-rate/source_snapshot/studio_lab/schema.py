"""Bounded 3D inputs, in nm, s and explicit incident-flux units."""
import math
from rf_lab.model import validate as validate_rf
from rf_lab.coupled import validate_gas
from studio_lab import VERSION

# Resource bounds for the local, single-thread native solver; not physical limits.
MAX_PLANE_CELLS = 20000
MAX_SURFACE_NODES = 450000
MAX_SURFACE_TRIANGLES = 900000


def field(key, label, unit, default, low, high, group, description, integer=False):
    return dict(key=key, label=label, unit=unit, default=default, min=low, max=high,
                group=group, description=description, integer=integer)


FIELDS = [
    field('duration_s', 'PECVD 시간', 's', 30, 0, 120, 'pecvd', '연속 증착 시간입니다. ALD cycle 수가 아닙니다.'),
    field('radical_rate_nm_s', '라디칼 성장 계수', 'nm/s', .8, 0, 3, 'pecvd', '정규화된 국소 라디칼 플럭스에 곱하는 속도 계수. 가스 유량에서 자동 추정하지 않습니다.'),
    field('ion_rate_nm_s', '이온 보조 성장 계수', 'nm/s', .3, 0, 2, 'pecvd', '기준 이온 플럭스 10¹⁹ m⁻²s⁻¹에서의 계수. RF 연결 시 Γᵢ/10¹⁹를 곱합니다.'),
    field('sticking', '라디칼 sticking', '', .3, .05, 1, 'pecvd', '입사 라디칼의 흡착 확률. 나머지는 확산 반사됩니다.'),
    field('etch_s', 'Etch 시간', 's', 8, 0, 30, 'etch', 'Si / SF₆–O₂ 식각 모델의 진행 시간.'),
    field('ion_flux', '독립 이온 플럭스', '10¹⁵ cm⁻²s⁻¹', 2, 0, 40, 'etch', 'RF 연결을 끈 경우에만 사용합니다.'),
    field('fluorine_flux', 'F 라디칼 플럭스', '10¹⁵ cm⁻²s⁻¹', 800, 0, 4000, 'etch', '독립적으로 지정한 경계 플럭스. Ar 모델에서 계산한 값이 아닙니다.'),
    field('oxygen_flux', 'O 패시베이션 플럭스', '10¹⁵ cm⁻²s⁻¹', 80, 0, 1000, 'etch', '독립적인 산소 공급 경계조건.'),
    field('energy_ev', '평균 이온 에너지', 'eV', 100, 20, 250, 'etch', '독립 입력. RF sheath RMS 전압을 이온 에너지로 치환하지 않습니다.'),
    field('ion_exponent', '이온 방향성 지수', '', 50, 1, 200, 'transport', '입사 cosⁿ 각도 분포. 클수록 수직 방향에 집중됩니다.'),
    field('pitch_nm', '계산 영역 X', 'nm', 600, 300, 900, 'geometry', '한 개 구조를 포함하는 도메인 폭. 양쪽 반사 경계.'),
    field('length_nm', '계산 영역 Y', 'nm', 400, 200, 700, 'geometry', '3D 도메인 길이. 양쪽 반사 경계.'),
    field('width_nm', '개구 폭 / 홀 지름', 'nm', 200, 100, 500, 'geometry', '초기 형상 치수이며 목표 치수가 아닙니다.'),
    field('depth_nm', '초기 PECVD 구조 깊이', 'nm', 200, 60, 400, 'geometry', 'PECVD 단독의 초기 깊이. 연속공정에서는 식각 결과를 그대로 이어받습니다.'),
    field('mask_nm', '식각 마스크 두께', 'nm', 60, 30, 120, 'geometry', '상류 모델의 내구성 높은 수치 마스크. 특정 실물 마스크 재료가 아닙니다.'),
    field('grid_nm', '격자 간격', 'nm', 15, 4, 30, 'numerics', '4–30 nm. 작을수록 실제 level-set 격자가 촘촘해집니다. 계산 비용이 증가하며 물리 정확도를 보증하지 않습니다.'),
    field('rays_per_point', '격자점당 ray 수', '', 150, 50, 2000, 'numerics', 'Monte Carlo 수치 잡음과 계산량을 결정합니다. 격자 비교 시 같은 값을 사용하세요.', True),
    field('output_steps', '공정당 저장 프레임', '', 8, 2, 12, 'numerics', '프레임 사이도 내부 CFL 시간 간격으로 계산합니다.', True),
    field('seed', '난수 시드', '', 42, 0, 2147483000, 'numerics', '단일 스레드, seed + 공정 프레임 번호.', True),
]


def validate(payload):
    if not isinstance(payload, dict):
        raise ValueError('Object required')
    unknown = set(payload) - {'model', 'params', 'geometry', 'coupled', 'rf', 'gas'}
    if unknown:
        raise ValueError(f'Unknown fields: {sorted(unknown)}')
    model = payload.get('model', 'pecvd')
    if model not in ('pecvd', 'etch', 'etch_pecvd'):
        raise ValueError('Choose pecvd, etch or etch_pecvd')
    geometry = payload.get('geometry', 'trench')
    if geometry not in ('trench', 'hole'):
        raise ValueError('Choose trench or hole')
    coupled = payload.get('coupled', True)
    if not isinstance(coupled, bool):
        raise ValueError('coupled must be a boolean')
    raw = payload.get('params', {})
    if not isinstance(raw, dict) or set(raw) - {f['key'] for f in FIELDS}:
        raise ValueError('Unknown process parameter')
    params = {}
    for f in FIELDS:
        value = raw.get(f['key'], f['default'])
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
            raise ValueError(f"{f['key']}: finite number required")
        if not f['min'] <= value <= f['max'] or (f['integer'] and int(value) != value):
            raise ValueError(f"{f['key']}: range {f['min']}–{f['max']}")
        params[f['key']] = int(value) if f['integer'] else float(value)
    p = params
    if p['width_nm'] < 6*p['grid_nm'] or p['mask_nm'] < 2*p['grid_nm']:
        raise ValueError('Resolve opening with ≥6 grid cells and mask with ≥2 cells')
    if p['width_nm'] > p['pitch_nm']-6*p['grid_nm']:
        raise ValueError('Opening needs at least 3 grid cells of substrate on each X side')
    if geometry == 'hole' and p['width_nm'] > p['length_nm']-6*p['grid_nm']:
        raise ValueError('Hole needs at least 3 grid cells of substrate on each Y side')
    if p['pitch_nm']*p['length_nm']/p['grid_nm']**2 > MAX_PLANE_CELLS:
        raise ValueError(f'3D budget: X×Y/grid² must be ≤{MAX_PLANE_CELLS}. Reduce domain or use coarser grid.')
    return dict(model=model, geometry=geometry, coupled=coupled, params=params,
                rf=validate_rf(payload.get('rf', {})), gas=validate_gas(payload.get('gas', {})))


def schema():
    from rf_lab.model import schema as rf_schema
    from rf_lab.coupled import FIELDS as gas_fields
    return dict(version=VERSION, fields=FIELDS, rf=rf_schema(), gas_fields=gas_fields,
                defaults=validate({}), available=True,
                limits=dict(max_plane_cells=MAX_PLANE_CELLS, max_surface_nodes=MAX_SURFACE_NODES,
                            max_surface_triangles=MAX_SURFACE_TRIANGLES, timeout_s=600))
