"""Create small, labelled educational fixtures for AMK PSE study.

The etch fixture is reused unchanged. The PVD fixture models a generic conductive
film using R_sheet = rho / thickness, not a material-specific deposition process.
Latent states belong to evaluation only and are written to instructor_only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path
from statistics import mean

from run_day1 import generate as generate_day1, write_csv


def generate_pvd(seed: int) -> dict[str, list[dict]]:
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise ValueError("seed must be a non-negative integer")
    rng = random.Random(seed)
    sites, wafers, truth = [], [], []
    for i in range(45):
        case = "BASELINE" if i < 15 else "CASE_A" if i < 30 else "CASE_B"
        wafer_id = f"D{i:03}"
        # Independent wafer variation and a shared spatial thickness pattern.
        center_nm = 20 * (1 + rng.gauss(0, 0.002))
        rho_ohm_m = 2e-7 * (1.25 if case == "CASE_A" else 1) * (1+rng.gauss(0,0.004))
        monitor_bias_nm = 2.0 if case == "CASE_B" else 0.0
        rows = []
        for ix in (-1, 0, 1):
            for iy in (-1, 0, 1):
                x, y = ix*100.0, iy*100.0
                actual_nm = center_nm * (1 + .01*(x*x+y*y)/20000)
                t_nm = actual_nm + monitor_bias_nm + rng.gauss(0,.08)
                ref_nm = actual_nm + rng.gauss(0,.08)
                rs_ohm_sq = rho_ohm_m/(actual_nm*1e-9) + rng.gauss(0,.02)
                row = dict(wafer_id=wafer_id, case_id=case, wafer_index=i,
                           site_id=f"X{ix:+d}Y{iy:+d}", x_mm=x, y_mm=y,
                           thickness_monitor_nm=round(t_nm,5),
                           thickness_reference_nm=round(ref_nm,5),
                           sheet_resistance_ohm_sq=round(rs_ohm_sq,5))
                rows.append(row)
        sites.extend(rows)
        ts = [r['thickness_monitor_nm'] for r in rows]
        wafers.append(dict(wafer_id=wafer_id,case_id=case,wafer_index=i,site_count=len(rows),
                           mean_thickness_monitor_nm=round(mean(ts),5),
                           mean_thickness_reference_nm=round(mean(r['thickness_reference_nm'] for r in rows),5),
                           mean_sheet_resistance_ohm_sq=round(mean(r['sheet_resistance_ohm_sq'] for r in rows),5),
                           nu_range_pct=round(100*(max(ts)-min(ts))/(2*mean(ts)),5)))
        truth.append(dict(wafer_id=wafer_id,
                          injected_state="latent_resistivity_increase" if case=="CASE_A" else "monitor_only_thickness_bias" if case=="CASE_B" else "normal",
                          latent_resistivity_ohm_m=rho_ohm_m,
                          thickness_monitor_bias_nm=monitor_bias_nm))
    return dict(sites=sites,wafers=wafers,truth=truth)


WORKSHEET = """# AMK PSE: Etch + Deposition 판단 기록

교육용 합성 데이터. 정답 파일은 아래 가설·반증 기준을 적은 뒤 확인합니다.
이 양식은 재실행 시 덮어쓰지 않습니다.

## Etch
- BASELINE / CASE_A / CASE_B의 rate, CD bias, NU, RF ratio, 압력 차이:
- 관측한 사실 두 가지와 단위:
- 경쟁 가설 두 가지:
- 먼저 수행할 평가와 고정 조건:
- 가설을 약화시키는 결과:
- 조치 전 확인할 다른 KPI:

## PVD
- BASELINE / CASE_A / CASE_B의 두께, sheet resistance, reference 차이:
- 같은 site의 rho_apparent = R_sheet × thickness_nm × 1e-9 [ohm m]:
- 두께 변화, 재료 특성 변화, 계측 오차를 구분하는 근거:
- 지금 데이터만으로 확정할 수 없는 원인:
- 다음 평가와 반증 기준:
- 증착 시간을 늘리기 전에 확인할 제약:

## 공통 종료 기록
- Observed:
- Inferred / Assumed:
- Unknown:
- Next evaluation:
- 다음 실습에서 구현할 가장 작은 산출물:
"""


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed',type=int,default=20260928)
    parser.add_argument('--out',type=Path,default=Path('outputs/amk_day1'))
    args=parser.parse_args()
    etch=generate_day1(args.seed)
    pvd=generate_pvd(args.seed)
    outputs={
        'etch_wafer_observations.csv':etch['etch'],
        'pvd_site_observations.csv':pvd['sites'],
        'pvd_wafer_summary.csv':pvd['wafers'],
        'instructor_only/etch_truth.csv':etch['etch_truth'],
        'instructor_only/pvd_truth.csv':pvd['truth'],
    }
    args.out.mkdir(parents=True,exist_ok=True)
    manifest=dict(seed=args.seed,model='amk_etch_pvd_educational_fixture_v1',synthetic=True,
                  time_basis='wafer index within each independent case series; no real timestamps',
                  units={'thickness':'nm','sheet_resistance':'ohm/square','coordinates':'mm',
                         'rho_apparent':'ohm m','rf_ratio':'fraction, not percent'},
                  limits=['No plasma chemistry, PVD transport solver, material calibration, or intervention model.',
                          'PVD CASE_A changes latent resistivity without identifying its physical cause.',
                          'PVD reference channel is an assumed independent measurement, not validated ground truth.',
                          'Nine sites on one wafer are correlated observations, not nine independent wafers.'],
                  files=[])
    for filename,rows in outputs.items():
        path=args.out/filename
        write_csv(path,rows)
        manifest['files'].append(dict(path=filename,rows=len(rows),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    (args.out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    worksheet=args.out/'AMK_PSE_WORKSHEET.md'
    if not worksheet.exists():
        worksheet.write_text(WORKSHEET,encoding='utf-8')
    print(json.dumps({'output':str(args.out.resolve()),'rows':{k:len(v) for k,v in outputs.items()}},indent=2))


if __name__=='__main__':
    main()
