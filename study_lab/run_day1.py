"""Generate deterministic educational data without third-party dependencies.

This is a learning fixture, not a validated process or equipment simulator.
Latent labels are written separately under instructor_only.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
from pathlib import Path


def generate(seed: int) -> dict[str, list[dict]]:
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise ValueError("seed must be a non-negative integer")
    rng = random.Random(seed)
    etch, etch_truth, overlay, candidates, labels = [], [], [], [], []
    for i in range(80):
        case = "BASELINE" if i < 40 else ("CASE_A" if i < 60 else "CASE_B")
        is_a, is_b = case == "CASE_A", case == "CASE_B"
        etch.append(dict(
            wafer_id=f"E{i:03}", case_id=case, wafer_index=i,
            etch_rate_nm_min=round(rng.gauss(92 if is_a else 100, 0.8), 4),
            cd_bias_nm=round(rng.gauss(1.5 if is_a else 0, 0.15), 4),
            selectivity=round(rng.gauss(9.4 if is_a else 10, 0.12), 4),
            nu_range_pct=round(rng.gauss(2.3 if is_a else 2, 0.08), 4),
            rf_reflected_ratio=round(rng.gauss(0.07 if is_a else 0.02, 0.0015), 6),
            pressure_readback_mtorr=round(rng.gauss(21.2 if is_b else 20, 0.04), 4),
            pressure_reference_mtorr=round(rng.gauss(20, 0.03), 4),
            pressure_settling_s=round(rng.gauss(1.0, 0.04), 4),
        ))
        etch_truth.append(dict(wafer_id=f"E{i:03}", injected_state=(
            "rf_delivery_loss" if is_a else "monitor_only_pressure_bias" if is_b else "normal")))
    for w in range(4):
        for ix in range(-4, 5):
            for iy in range(-4, 5):
                x, y = ix * 30.0, iy * 30.0
                if math.hypot(x, y) > 145:
                    continue
                rotation = 0.025 if w == 3 else 0.0
                overlay.append(dict(
                    wafer_id=f"L{w:02}", site_id=f"X{ix:+d}Y{iy:+d}",
                    x_mm=x, y_mm=y,
                    dx_nm=round(1.0 + 0.01*x + (0.005-rotation)*y + rng.gauss(0, 0.2), 4),
                    dy_nm=round(-0.5 + (0.003+rotation)*x - 0.008*y + rng.gauss(0, 0.2), 4),
                ))
    for w in range(10):
        split = "train" if w < 6 else "validation" if w < 8 else "test"
        for i in range(100):
            cid = f"I{w:02}_{i:03}"
            doi = rng.random() < 0.12
            radius, theta = 145 * math.sqrt(rng.random()), 2*math.pi*rng.random()
            candidates.append(dict(
                candidate_id=cid, wafer_id=f"I{w:02}", split=split,
                x_mm=round(radius*math.cos(theta), 4), y_mm=round(radius*math.sin(theta), 4),
                signal_score=round(min(100, max(0, rng.gauss(70 if doi else 40, 15))), 4),
                size_proxy=round(rng.lognormvariate(0.3 if doi else 0.0, 0.4), 4),
                background_proxy=round(rng.uniform(0.1, 1.0), 4),
            ))
            labels.append(dict(candidate_id=cid, wafer_id=f"I{w:02}", split=split, is_doi=int(doi)))
    return dict(etch=etch, etch_truth=etch_truth, overlay=overlay, candidates=candidates, labels=labels)


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError("cannot write empty data")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


WORKSHEET = """# Day 1 판단 기록

데이터는 교육용 합성 예시입니다. 먼저 이 문서를 작성한 후 instructor_only를 확인하세요.

## CASE_A
- 관측 사실과 단위:
- 가능한 원인 두 가지:
- 다음 평가와 이유:
- 가설을 약화시키는 결과:

## CASE_B
- 표시 압력과 reference 압력의 차이:
- 다른 KPI도 함께 바뀌었는가:
- 모니터 센서와 feedback 센서의 차이:
- 지금 recipe를 바꿀 근거가 충분한가:

## 추가 관찰
- overlay에서 wafer별 공간 패턴은 어떻게 다른가:
- 검사 threshold 50, 60, 70에서 검출 건수는 어떻게 달라지는가:
- 검출 건수만으로 알 수 없는 것은 무엇인가:

## 오늘의 세 줄
- Observed:
- Inferred / Assumed:
- Unknown / Next evaluation:
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=20260921)
    parser.add_argument("--out", type=Path, default=Path("outputs/day1"))
    args = parser.parse_args()
    data = generate(args.seed)
    args.out.mkdir(parents=True, exist_ok=True)
    outputs = {
        "etch_wafer_observations.csv": data["etch"],
        "overlay_sites.csv": data["overlay"],
        "inspection_candidates.csv": data["candidates"],
        "instructor_only/etch_truth.csv": data["etch_truth"],
        "instructor_only/inspection_labels.csv": data["labels"],
    }
    manifest = dict(seed=args.seed, model="educational_fixture_v1", synthetic=True,
                    time_basis="ordered wafer index; no real timestamps", files=[])
    for filename, rows in outputs.items():
        path = args.out / filename
        write_csv(path, rows)
        manifest["files"].append(dict(path=filename, rows=len(rows), sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    worksheet = args.out / "DAY1_WORKSHEET.md"
    if not worksheet.exists():
        worksheet.write_text(WORKSHEET, encoding="utf-8")
    print(json.dumps({"output": str(args.out.resolve()), "seed": args.seed,
                      "rows": {key: len(rows) for key, rows in outputs.items()}}, indent=2))


if __name__ == "__main__":
    main()
