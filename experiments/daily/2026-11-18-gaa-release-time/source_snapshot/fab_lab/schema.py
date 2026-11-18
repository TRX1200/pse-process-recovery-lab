"""Public schema. Lengths are nm, time s, temperature K, dose cm^-2."""
from copy import deepcopy
import math

MATERIALS = [
    dict(id=0, name='Void', color='#122333'),
    dict(id=1, name='Si', color='#74a3be'),
    dict(id=2, name='SiGe', color='#cd91b6'),
    dict(id=3, name='SiO2', color='#bccbd4'),
    dict(id=4, name='HfO2', color='#eed58c'),
    dict(id=5, name='TiN', color='#69c7b2'),
    dict(id=6, name='Si3N4', color='#9989c8'),
    dict(id=7, name='Cu', color='#e69a65'),
]


def number(label, unit, default, lo, hi, help='', integer=False):
    return dict(label=label, unit=unit, default=default, min=lo, max=hi,
                help=help, integer=integer, type='number')


def choice(label, values, default, help=''):
    return dict(label=label, options=values, default=default, help=help, type='select')


MAT = lambda default: choice('재료', [m['name'] for m in MATERIALS[1:]], default)
CATALOG = {
    'mask': dict(label='입력 마스크', family='패턴 경계', description='노광 계산 없이 XY 개구를 직접 지정합니다. 다음 공정에도 유지됩니다.', fields={
        'pattern': choice('개구 모양', ['all', 'rectangle', 'lines', 'ends', 'circle'], 'rectangle'),
        'invert': choice('개구 방향', ['inside', 'outside'], 'inside', 'outside는 지정 영역을 보호하고 바깥을 엽니다.'),
        'cx': number('중심 X', 'nm', 0, -100000, 100000),
        'cy': number('중심 Y', 'nm', 0, -100000, 100000),
        'width': number('X 폭 / 원 지름', 'nm', 40, 1, 200000),
        'length': number('Y 폭 / 선 폭', 'nm', 40, 1, 200000),
        'pitch': number('선 간격', 'nm', 64, 1, 200000),
        'count': number('선 개수', '', 2, 1, 5, integer=True),
    }),
    'epitaxy': dict(label='층 성장 / Epitaxy', family='증착', description='열린 XY 영역의 가장 높은 고체 위에 수직 층을 더합니다. 결정 성장 속도·응력은 생략합니다.', fields={
        'material': MAT('Si'), 'thickness': number('성장 두께', 'nm', 8, 0, 50000)}),
    'deposit': dict(label='ALD / Conformal coating', family='증착', description='도달 가능한 기체 영역에 거리 기반 등각 코팅. 흡착 포화식으로 두께를 계산하며 수송·전구체 화학은 생략합니다.', fields={
        'material': MAT('HfO2'), 'cycles': number('사이클 수', '', 80, 0, 2000, integer=True),
        'gpc': number('포화 GPC', 'nm/cycle', .1, .001, 1000, '사용자가 지정하는 공정 계수. 장비 검증값이 아닙니다.'),
        'exposure': number('전구체 노출', 'Pa·s', 4, 0, 1000),
        'k': number('포화 계수 k', '(Pa·s)⁻¹', 1, .001, 100),
    }),
    'etch': dict(label='Dry / Selective etch', family='식각', description='속도×시간을 제거 거리로 사용. 방향성 식각은 위에서, 등방성 식각은 접근 가능한 표면에서 진행합니다.', fields={
        'material': choice('대상 재료', ['Si', 'SiGe', 'Si+SiGe', 'SiO2', 'HfO2', 'TiN', 'Si3N4', 'Cu'], 'Si'),
        'mode': choice('방향성', ['directional', 'isotropic'], 'directional'),
        'rate': number('대상 식각 속도', 'nm/s', 2, 0, 10000),
        'time': number('공정 시간', 's', 8, 0, 10000),
        'selectivity': number('대상 / 다른 재료 속도비', '', 1000, 1, 10000),
    }),
    'oxidize': dict(label='Thermal oxidation', family='산화', description='평면 Si/SiO₂ 열에 Deal–Grove 성장. A·B는 사용자 계수이며 곡면 응력·초박막 보정은 없습니다.', fields={
        'time': number('산화 시간', 's', 60, 0, 100000),
        'A': number('선형-포물선 계수 A', 'nm', 100, .001, 100000),
        'B': number('포물선 속도 계수 B', 'nm²/s', 20, 0, 100000),
    }),
    'implant': dict(label='Ion implantation', family='도핑', description='정상 입사 Gaussian 깊이 분포. Rp와 straggle은 직접 입력하며 에너지·결정 채널링 변환은 하지 않습니다.', fields={
        'species': choice('극성', ['donor', 'acceptor'], 'donor'),
        'dose': number('주입 dose', 'cm⁻²', 1e14, 0, 1e17),
        'rp': number('Projected range Rp', 'nm', 8, 0, 50000),
        'sigma': number('Straggle σ', 'nm', 4, .1, 20000),
    }),
    'anneal': dict(label='Diffusion / activation', family='열처리', description='Si 안에서만 보존형 Fick 확산. 경계 무유속, 활성화율 입력. Dref·Ea는 교정되지 않은 예시입니다.', fields={
        'temperature': number('온도', 'K', 1100, 300, 1700),
        'time': number('시간', 's', 10, 0, 3600),
        'Dref': number('1100 K 기준 확산계수', 'nm²/s', 1, 0, 10000),
        'Ea': number('활성화 에너지', 'eV', 3, 0, 6),
        'activation': number('활성화 비율', '', .8, 0, 1),
    }),
    'fill': dict(label='선택 영역 Fill / Contact', family='금속·구조', description='열린 영역에서 지정 높이 아래의 빈 셀을 채우는 이상적 충전. 핵생성·도금·void 동역학은 계산하지 않습니다.', fields={
        'material': MAT('Cu'), 'height': number('충전 상단 Z', 'nm', 80, 0, 200000)}),
    'bond': dict(label='Die stacking / ideal bond', family='패키징', description='현재 구조를 위에 복제하여 적층. SiO₂ 접합층과 아래 Cu footprint 연장으로 정렬 오차 영향을 검사합니다.', fields={
        'gap': number('접합층 높이', 'nm', 4000, 0, 50000),
        'offset_x': number('위 다이 X 정렬 오차', 'nm', 0, -50000, 50000),
        'offset_y': number('위 다이 Y 정렬 오차', 'nm', 0, -50000, 50000)}),
    'measure': dict(label='Metrology checkpoint', family='계측', description='재료 부피·단면·도핑량을 동일한 계산 격자에서 기록합니다. 측정 장비 응답은 포함하지 않습니다.', fields={}),
    'test': dict(label='IC / EDS learning test', family='검사', description='구조 검사는 계산 격자에서, MOS 전류·CMOS 전달 곡선은 독립적인 장채널 compact model에서 계산합니다.', fields={
        'kind': choice('검사 종류', ['mos_cmos', 'tsv', 'both'], 'mos_cmos'),
        'vdd': number('공급 전압', 'V', 1, .1, 5),
        'vtn': number('NMOS 문턱전압', 'V', .3, .01, 2),
        'vtp': number('PMOS |문턱전압|', 'V', .35, .01, 2),
        'mun': number('전자 이동도', 'cm²/Vs', 300, 1, 2000),
        'mup': number('정공 이동도', 'cm²/Vs', 150, 1, 2000),
        'eot': number('전기 모델 EOT', 'nm', 4, .2, 100),
        'W': number('전기 모델 유효 W', 'nm', 80, 1, 100000),
        'L': number('전기 모델 L', 'nm', 40, 1, 100000),
        'rho': number('Cu 비저항', 'Ω·m', 1.68e-8, 1e-9, 1e-5),
        'fault': choice('합성 회로 불량', ['none', 'open', 'short'], 'none'),
    }),
}
DOMAIN = {
    'nx': number('X 셀 수', '', 48, 16, 96, integer=True),
    'ny': number('Y 셀 수', '', 36, 16, 96, integer=True),
    'nz': number('Z 셀 수', '', 48, 16, 128, integer=True),
    'dx': number('등방 격자 간격', 'nm', 4, 1, 2000),
    'substrate': number('Si 기판 두께', 'nm', 24, 0, 100000),
    'box': number('매립 산화막 BOX', 'nm', 8, 0, 10000),
    'active': number('초기 Si 활성층', 'nm', 16, 0, 50000),
}


def step(op, label=None, **params):
    return dict(op=op, label=label or CATALOG[op]['label'], enabled=True,
                params={**{k: f['default'] for k, f in CATALOG[op]['fields'].items()}, **params})


def _fields(raw, fields, context):
    if not isinstance(raw, dict) or set(raw)-set(fields):
        raise ValueError(f'{context}: unknown fields or invalid object')
    result = {}
    for key, f in fields.items():
        value = raw.get(key, f['default'])
        if f['type'] == 'select':
            if value not in f['options']: raise ValueError(f'{context}.{key}: invalid choice')
        else:
            if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
                raise ValueError(f'{context}.{key}: finite number required')
            if not f['min'] <= value <= f['max'] or (f['integer'] and int(value) != value):
                raise ValueError(f'{context}.{key}: out of range')
            value = int(value) if f['integer'] else float(value)
        result[key] = value
    return result


def validate(raw):
    if not isinstance(raw, dict) or set(raw)-{'model', 'name', 'domain', 'steps'}:
        raise ValueError('Invalid Fab request')
    if raw.get('model') != 'fab': raise ValueError('model must be fab')
    name = raw.get('name', 'Experiment')
    if not isinstance(name, str) or not 1 <= len(name) <= 100: raise ValueError('Invalid name')
    d = _fields(raw.get('domain', {}), DOMAIN, 'domain')
    if d['nx']*d['ny']*d['nz'] > 450000: raise ValueError('격자 예산은 450,000 셀입니다.')
    if d['substrate']+d['box']+d['active'] >= (d['nz']-2)*d['dx']:
        raise ValueError('기판 위에 최소 2셀의 기체 공간이 필요합니다.')
    steps = raw.get('steps')
    if not isinstance(steps, list) or not 1 <= len(steps) <= 48: raise ValueError('1–48 steps required')
    normalized = []
    for s in steps:
        if not isinstance(s, dict) or set(s)-{'op', 'label', 'enabled', 'params'}:
            raise ValueError('Invalid step')
        op = s.get('op')
        if op not in CATALOG: raise ValueError('Unsupported operation (CMP/lithography excluded)')
        label = s.get('label', CATALOG[op]['label'])
        if not isinstance(label, str) or not 1 <= len(label) <= 100: raise ValueError('Invalid step label')
        if not isinstance(s.get('enabled', True), bool): raise ValueError('enabled must be boolean')
        normalized.append(dict(op=op, label=label, enabled=s.get('enabled', True),
                               params=_fields(s.get('params', {}), CATALOG[op]['fields'], op)))
    return dict(model='fab', name=name, domain=d, steps=normalized)


def schema():
    from fab_lab.presets import presets
    return deepcopy(dict(version='fab-grid-v1', materials=MATERIALS, domain=DOMAIN,
                         operations=CATALOG, presets=presets()))
