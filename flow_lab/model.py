"""Deterministic 2D process integration on an exclusive material grid.

x is horizontal, z is up, all lengths are nm. Cells are classified at their
centres. Each operation receives the previous operation's complete material
state. This is a geometric front model, not ViennaPS kinetics or device physics.
"""
from __future__ import annotations

import hashlib
import heapq
import json
import math
from numbers import Real
from pathlib import Path
import platform
import time

import numpy as np
import scipy
from scipy import ndimage

from flow_lab import VERSION

MATERIALS = [
    dict(id=0, name="Void", color="#102535", contrast=0.04),
    dict(id=1, name="Si", color="#799CB8", contrast=0.45),
    dict(id=2, name="SiGe", color="#D9B887", contrast=0.62),
    dict(id=3, name="SiO2", color="#BDC9D1", contrast=0.32),
    dict(id=4, name="HfO2", color="#F0BC54", contrast=0.75),
    dict(id=5, name="TiN", color="#86C7AA", contrast=0.90),
    dict(id=6, name="PolySi", color="#7181AA", contrast=0.50),
    dict(id=7, name="Si3N4", color="#9B91BB", contrast=0.38),
]
IDS = {m["name"]: m["id"] for m in MATERIALS}
LIMITS = dict(max_steps=24, max_cells=65536)
ASSUMPTIONS = [
    "2D material-cell geometry; x horizontal, z up, nm. Bottom is a fixed substrate reservoir; no periodic wrap.",
    "Deposition is a prescribed conformal distance offset, updating top-connected gas each half-grid distance increment; sealed voids stop coating. This is not ALD saturation/precursor transport.",
    "Directional etch consumes vertical depth in exposed columns and stops on unselected materials. Mask is an ideal vertical projection.",
    "Selective etch uses an 8-neighbour shortest-path front from accessible gas. Target speed is 1, other solids 1/selectivity; this is a geometric approximation.",
    "Stack layers are prescribed planar geometry, not epitaxial growth kinetics. Planarization removes material above a prescribed height, not a CMP mechanics model.",
    "Numerical line cuts are grid measurements. SEM mode is an illustrative contrast/blur/noise forward model, not electron scattering or calibrated metrology.",
    "No doping, diffusion, stress, contacts, Poisson/transport, Id-Vg or 3D source/drain anchoring. GAA is a gate-normal cross-section; planar example is a gate/spacer precursor, not CMOS.",
]


def presets():
    domain = dict(width_nm=320, bottom_nm=-60, top_nm=180, grid_nm=2)
    return [
        dict(id="gaa", name="GAA 단면 공정", domain=domain, steps=[
            dict(id="stack", name="Si / SiGe 적층", kind="stack", count=3, si_nm=10, sige_nm=16),
            dict(id="mask", name="패턴 마스크", kind="mask", width_nm=100, center_nm=0),
            dict(id="fin", name="방향성 식각", kind="directional_etch", amount_nm=90, material="all"),
            dict(id="strip", name="마스크 제거", kind="strip"),
            dict(id="release", name="SiGe 선택 식각", kind="selective_etch", amount_nm=54, material="SiGe", selectivity=100),
            dict(id="oxide", name="HfO2 코팅", kind="deposit", amount_nm=4, material="HfO2"),
            dict(id="metal", name="TiN 게이트", kind="deposit", amount_nm=6, material="TiN"),
        ]),
        dict(id="planar", name="평면 게이트 / Spacer", domain=domain, steps=[
            dict(id="oxide", name="게이트 절연막", kind="deposit", amount_nm=4, material="HfO2"),
            dict(id="gate", name="PolySi 증착", kind="deposit", amount_nm=40, material="PolySi"),
            dict(id="mask", name="게이트 패턴", kind="mask", width_nm=60, center_nm=0),
            dict(id="etch", name="게이트 식각", kind="directional_etch", amount_nm=44, material="PolySi"),
            dict(id="strip", name="마스크 제거", kind="strip"),
            dict(id="spacer", name="Si3N4 코팅", kind="deposit", amount_nm=10, material="Si3N4"),
            dict(id="back", name="Spacer etch-back", kind="directional_etch", amount_nm=12, material="Si3N4"),
        ]),
    ]


def schema():
    return dict(version=VERSION, materials=MATERIALS, presets=presets(), limits=LIMITS, assumptions=ASSUMPTIONS)


def number(raw, key, low, high, integer=False):
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{key}: {low}–{high} 범위의 유한한 숫자가 필요합니다.")
    if integer and int(value) != value:
        raise ValueError(f"{key}: 정수가 필요합니다.")
    return int(value) if integer else float(value)


def validate(payload):
    if not isinstance(payload, dict) or set(payload) - {"domain", "steps", "stop_after", "name"}:
        raise ValueError("domain, steps, stop_after, name 필드만 허용합니다.")
    raw = payload.get("domain")
    if not isinstance(raw, dict) or set(raw) != {"width_nm", "bottom_nm", "top_nm", "grid_nm"}:
        raise ValueError("계산 영역의 네 필드를 모두 입력하세요.")
    domain = dict(width_nm=number(raw, "width_nm", 80, 800), bottom_nm=number(raw, "bottom_nm", -200, -10),
                  top_nm=number(raw, "top_nm", 40, 500), grid_nm=number(raw, "grid_nm", 1, 10))
    dx = domain["grid_nm"]
    for length in [domain["width_nm"], domain["bottom_nm"], domain["top_nm"]]:
        if abs(length / dx - round(length / dx)) > 1e-8:
            raise ValueError("폭과 상하 경계는 격자 간격의 정수배여야 합니다.")
    if domain["width_nm"] * (domain["top_nm"]-domain["bottom_nm"]) / dx**2 > LIMITS["max_cells"]:
        raise ValueError("계산 셀 수는 65,536개 이하여야 합니다.")
    steps = payload.get("steps")
    if not isinstance(steps, list) or not 0 <= len(steps) <= LIMITS["max_steps"]:
        raise ValueError("최대 24개 공정 단계를 입력하세요.")
    name = payload.get("name", "Process flow")
    if not isinstance(name, str) or not 1 <= len(name) <= 100:
        raise ValueError("공정명은 1–100자여야 합니다.")
    normalized, ids = [], set()
    for raw in steps:
        if not isinstance(raw, dict): raise ValueError("공정 단계는 객체여야 합니다.")
        sid, title, kind = raw.get("id"), raw.get("name"), raw.get("kind")
        if not isinstance(sid, str) or not 1 <= len(sid) <= 64 or sid in ids:
            raise ValueError("중복 없는 단계 ID가 필요합니다.")
        if not isinstance(title, str) or not 1 <= len(title) <= 80: raise ValueError("단계명은 1–80자여야 합니다.")
        ids.add(sid)
        step = dict(id=sid, name=title, kind=kind)
        if kind == "stack":
            step.update(count=number(raw, "count", 1, 6, True), si_nm=number(raw, "si_nm", dx, 40), sige_nm=number(raw, "sige_nm", dx, 40))
        elif kind == "mask":
            step.update(width_nm=number(raw, "width_nm", dx, domain["width_nm"]), center_nm=number(raw, "center_nm", -domain["width_nm"]/2, domain["width_nm"]/2))
            if abs(step["center_nm"]) + step["width_nm"]/2 > domain["width_nm"]/2: raise ValueError("마스크가 영역을 벗어납니다.")
        elif kind in ("deposit", "directional_etch", "selective_etch"):
            step["amount_nm"] = number(raw, "amount_nm", 0, 250)
            material = raw.get("material")
            allowed = set(IDS)-{"Void"}
            if kind == "directional_etch": allowed.add("all")
            if not isinstance(material, str) or material not in allowed: raise ValueError("지원하지 않는 재료입니다.")
            step["material"] = material
            if kind == "selective_etch": step["selectivity"] = number(raw, "selectivity", 1, 1000)
        elif kind == "planarize":
            step["height_nm"] = number(raw, "height_nm", domain["bottom_nm"]+dx, domain["top_nm"]-dx)
        elif kind != "strip": raise ValueError("지원하지 않는 공정입니다.")
        if set(raw) != set(step): raise ValueError("누락되거나 알 수 없는 공정 필드가 있습니다.")
        normalized.append(step)
    stop = number({"stop_after": payload.get("stop_after", len(steps))}, "stop_after", 0, len(steps), True)
    return dict(name=name, domain=domain, steps=normalized, stop_after=stop)


def accessible_gas(grid):
    empty = grid == 0
    seed = np.zeros_like(empty)
    seed[-1] = empty[-1]
    return ndimage.binary_propagation(seed, mask=empty)


def conformal_deposit(grid, material, thickness, dx):
    """Offset the initial surface while closing inaccessible paths during growth.

    Half-cell distance increments resolve connectivity changes at cell scale.
    Distances always reference the initial surface to avoid repeated-stencil
    anisotropy. This remains ideal, instant transport inside accessible gas.
    """
    result = grid.copy()
    distance = ndimage.distance_transform_edt(grid == 0, sampling=dx)
    increments = max(1, math.ceil(thickness / (dx / 2)))
    for amount in np.linspace(0, thickness, increments + 1)[1:]:
        gas = accessible_gas(result)
        result[gas & (distance <= amount + 1e-9)] = material
    return result


def selective_front(grid, target, depth, selectivity, dx):
    """Weighted graph arrival distance; other materials block at infinite cost limit.

    Eight-neighbour stencil has angular discretization error. Diagonal propagation
    cannot cross a non-void corner without paying its material traversal cost.
    """
    if depth == 0: return grid.copy()
    gas = accessible_gas(grid)
    distance = np.full(grid.shape, np.inf)
    distance[gas] = 0
    rates = np.where(grid == target, 1.0, selectivity)
    rates[grid == 0] = 0
    ny, nx = grid.shape
    queue = []
    # Initiate only solid faces directly exposed to connected gas.
    faces = ndimage.binary_dilation(gas) & (grid != 0)
    for row, col in np.argwhere(faces):
        cost = dx * rates[row, col]
        if cost <= depth:
            distance[row, col] = cost
            heapq.heappush(queue, (cost, int(row), int(col)))
    while queue:
        value, row, col = heapq.heappop(queue)
        if value != distance[row, col]: continue
        for dr, dc in ((-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)):
            rr, cc = row+dr, col+dc
            if not (1 <= rr < ny and 0 <= cc < nx): continue  # fixed bottom row
            cost = rates[rr, cc]
            if dr and dc:
                cost = max(cost, min(rates[row, cc], rates[rr, col])) * math.sqrt(2)
            candidate = value + dx*cost
            if candidate <= depth and candidate < distance[rr, cc]:
                distance[rr, cc] = candidate
                heapq.heappush(queue, (candidate, rr, cc))
    result = grid.copy()
    result[(distance <= depth) & (grid != 0)] = 0
    result[0] = grid[0]
    return result


def spans(grid):
    """Lossless horizontal runs: [row from bottom, starting col, cell count, material]."""
    rows = []
    for row, values in enumerate(grid):
        changes = np.r_[0, np.flatnonzero(values[1:] != values[:-1])+1, len(values)]
        for a, b in zip(changes, changes[1:]):
            if values[a]: rows.append([int(row), int(a), int(b-a), int(values[a])])
    return rows


def measure(grid, dx, z):
    counts = np.bincount(grid.ravel(), minlength=len(MATERIALS))
    solids = grid != 0
    heights = np.where(solids, z[:,None]+dx/2, -np.inf).max(axis=0)
    mask = (grid==IDS["Si"]) & (z[:,None]>=0)
    _, components = ndimage.label(mask)
    return dict(area_nm2={m["name"]:float(counts[m["id"]]*dx**2) for m in MATERIALS[1:]},
                top_height_nm=float(heights.max()), surface_rq_nm=float(np.std(heights)),
                si_components_above_zero=int(components), enclosed_void_area_nm2=float(np.sum((grid==0)&~accessible_gas(grid))*dx**2))


def simulate(payload):
    request = validate(payload)
    started = time.perf_counter()
    d = request["domain"]; dx=d["grid_nm"]
    nx=round(d["width_nm"]/dx); ny=round((d["top_nm"]-d["bottom_nm"])/dx)
    x=-d["width_nm"]/2+(np.arange(nx)+.5)*dx
    z=d["bottom_nm"]+(np.arange(ny)+.5)*dx
    grid=np.zeros((ny,nx),dtype=np.uint8);grid[z<0,:]=IDS["Si"]
    mask=None
    frames=[]
    def snapshot(title, step, previous, warnings):
        identity=hashlib.sha256(json.dumps(d,sort_keys=True).encode()+grid.tobytes()+(b'' if mask is None else mask.tobytes())).hexdigest()
        frames.append(dict(index=len(frames), name=title, step=step, state_hash=identity, parent_hash=previous,
                           spans=spans(grid), mask_columns=[] if mask is None else np.flatnonzero(mask).tolist(),
                           metrics=measure(grid,dx,z), warnings=warnings))
    snapshot("Si 기판",None,None,[])
    for step in request["steps"][:request["stop_after"]]:
        previous=frames[-1]["state_hash"];before=grid.copy();warnings=[]
        kind=step["kind"]
        if kind=="mask":
            mask=(x>=step["center_nm"]-step["width_nm"]/2)&(x<step["center_nm"]+step["width_nm"]/2)
        elif kind=="strip": mask=None
        elif kind=="stack":
            if mask is not None: raise ValueError("적층 전에 마스크를 제거하세요.")
            height=np.where(grid!=0,z[:,None]+dx/2,-np.inf).max(axis=0)
            if np.ptp(height)>1e-8: raise ValueError("적층 초기화는 평탄한 표면에서만 지원합니다.")
            top=float(height[0])
            for _ in range(step["count"]):
                for material,key in (("SiGe","sige_nm"),("Si","si_nm")):
                    thickness=round(step[key]/dx)*dx
                    if top+thickness>=d["top_nm"]-dx: raise ValueError("적층이 상단 계산 경계에 도달합니다. 영역을 높이세요.")
                    grid[(z>=top)&(z<top+thickness),:]=IDS[material];top+=thickness
            warnings.append("주어진 두께의 이상적 평탄 적층입니다. 에피택시 반응과 결함을 계산하지 않습니다.")
        elif kind=="deposit":
            if mask is not None: raise ValueError("증착 전에 마스크를 제거하세요. 마스크 위 증착/lift-off는 아직 지원하지 않습니다.")
            grid=conformal_deposit(grid,IDS[step["material"]],step["amount_nm"],dx)
            warnings.append("상단과 연결된 빈 공간에 이상적 등두께 코팅. 전구체 수송/피복률은 별도 ALD 해석에서 확인하세요.")
        elif kind=="directional_etch":
            cells=int(math.floor((step["amount_nm"]+1e-9)/dx))
            for col in range(nx):
                if mask is not None and mask[col]: continue
                indices=np.flatnonzero(grid[:,col])[::-1]
                remaining=cells
                for row in indices:
                    if row==0 or remaining<=0: break
                    if step["material"]!="all" and grid[row,col]!=IDS[step["material"]]: break
                    grid[row,col]=0;remaining-=1
        elif kind=="selective_etch":
            if mask is not None: raise ValueError("선택 식각 전에 마스크를 제거하세요. 투영 마스크의 측방 침투는 지원하지 않습니다.")
            grid=selective_front(grid,IDS[step["material"]],step["amount_nm"],step["selectivity"],dx)
            warnings.append("선택비는 사용자 입력 유효 속도비입니다. 8방향 격자 전파의 각도 오차와 격자 이하 손실을 검토하세요.")
        elif kind=="planarize":
            if mask is not None: raise ValueError("평탄화 전에 마스크를 제거하세요.")
            grid[z>=step["height_nm"],:]=0
        if np.any(grid[-1]): raise ValueError("형상이 상단 경계에 도달했습니다. 상단 여유를 늘리세요.")
        if np.any(grid[1]!=IDS["Si"]): warnings.append("하단 경계 근처까지 공정이 진행됐습니다. 기판 깊이를 늘려 확인하세요.")
        if kind not in ("mask","strip") and np.array_equal(before,grid): warnings.append("이 단계에서 해상 가능한 형상 변화가 없습니다. 노출 재료·격자·공정량을 확인하세요.")
        snapshot(step["name"],step,previous,warnings)
    identity=json.dumps(dict(request=request,version=VERSION),sort_keys=True,allow_nan=False).encode()
    return dict(format="process-flow-run-v1", version=VERSION, config_hash=hashlib.sha256(identity).hexdigest(),
                source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                environment=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__),
                request=request, shape=[ny,nx], materials=MATERIALS, frames=frames,
                assumptions=ASSUMPTIONS, elapsed_s=time.perf_counter()-started,
                numerics=dict(grid_nm=dx, determinism="no random sampling", geometry="exclusive material cells; no smoothing",
                              front="8-neighbour weighted shortest-path", deposition_increment_nm=dx/2,
                              coordinate="x horizontal, z up, nm"))
