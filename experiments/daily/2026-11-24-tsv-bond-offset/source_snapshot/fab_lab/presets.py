"""Illustrative SOI flows; starting experiments, never optimized answer recipes."""
from fab_lab.schema import step as s, validate


def gate_and_test(width=40, gate=40):
    return [
        s('mask', '마스크 해제', pattern='all'),
        s('deposit', 'Gate dielectric · HfO₂', material='HfO2'),
        s('deposit', 'Gate metal · TiN', material='TiN'),
        s('mask', 'Gate 바깥 개구', width=gate, length=1000, invert='outside'),
        s('etch', 'Gate 패턴 식각', material='TiN', rate=2, time=8),
        s('etch', 'S/D 위 절연막 개방', material='HfO2', rate=2, time=8),
        s('mask', 'n-type S/D 개구', pattern='ends', width=gate+8, length=width, cy=-32, count=1),
        s('implant', 'Donor S/D', species='donor'),
        s('mask', 'p-type S/D 개구', pattern='ends', width=gate+8, length=width, cy=32, count=1),
        s('implant', 'Acceptor S/D', species='acceptor'),
        s('anneal'),
        s('mask', 'S/D contact 개구', pattern='ends', width=64, length=width),
        s('fill', '이상적 금속 contact', material='Cu', height=112),
        s('mask', '전체 계측', pattern='all'), s('measure'), s('test'),
    ]


def presets():
    common = dict(nx=48, ny=36, nz=48, dx=4, substrate=24, box=8, active=16)
    planar = [s('mask', 'Active strip 외부 개구', pattern='lines', width=1000, length=40, invert='outside'),
              s('etch', 'SOI 소자 분리', time=8), s('mask', pattern='all'),
              s('oxidize', 'Sacrificial oxidation', time=60),
              s('etch', 'Sacrificial oxide strip', material='SiO2', mode='isotropic', rate=1, time=12)]
    fin = [s('mask', 'Fin 외부 개구', pattern='lines', width=1000, length=16, invert='outside'),
           s('etch', 'Fin 정의', rate=4, time=16)]
    gaa = []
    for i in range(3):
        gaa.extend([s('epitaxy', f'SiGe 희생층 {i+1}', material='SiGe', thickness=12),
                    s('epitaxy', f'Si 채널 {i+1}', thickness=8)])
    gaa += [s('mask', 'Stack 외부 개구', pattern='lines', width=1000, length=40, invert='outside'),
            s('etch', 'Stack mesa 정의', material='Si+SiGe', rate=4, time=15),
            s('mask', 'S/D recess 개구', pattern='ends', width=64, length=40),
            s('etch', 'S/D recess', material='Si+SiGe', rate=4, time=15),
            s('fill', '이상적 Si S/D anchor', material='Si', height=92),
            s('mask', 'Release · gate 영역', width=64, length=1000),
            s('etch', 'SiGe 채널 release', material='SiGe', mode='isotropic', rate=2, time=14, selectivity=100),
            s('measure', 'Released nanosheets 검사')]
    tsv = [s('mask', 'TSV 개구', pattern='circle', width=16000),
           s('etch', 'Through-Si etch', rate=1000, time=32),
           s('mask', pattern='all'),
           s('deposit', '이상적 TSV 절연 liner', material='SiO2', cycles=10, gpc=100, exposure=20),
           s('mask', 'Cu fill 개구', pattern='circle', width=14000),
           s('fill', '이상적 Cu fill', material='Cu', height=33000),
           s('measure', '단일 TSV 검사'), s('bond'), s('measure', '적층 / 정렬 검사'), s('test', kind='tsv')]
    raw = [
        ('cmos', 'SOI CMOS · 공정 기초', '두 활성 영역의 n/p 주입, gate 형성, 독립 CMOS compact test.', common, planar+gate_and_test()),
        ('finfet', 'FinFET · Fin & gate', 'Si fin 식각과 등각 gate. 전기 곡선은 3D 소자 해석이 아닌 별도 compact model.', {**common, 'active':64}, fin+gate_and_test(16)),
        ('gaa', 'GAA · Nanosheet release', 'Si/SiGe 적층 → mesa → S/D anchor → selective release → wrap coating.', {**common, 'active':0}, gaa+gate_and_test()),
        ('tsv', '3D Stack · TSV & bond', 'µm 규모의 관통 홀·liner·Cu·정렬 오차·연결성 검사. 이상적 fill/bond.', dict(nx=40,ny=40,nz=80,dx=1000,substrate=32000,box=0,active=0),tsv),
    ]
    return [dict(id=k, title=title, description=desc, request=validate(dict(model='fab',name=title,domain=d,steps=steps)))
            for k,title,desc,d,steps in raw]
