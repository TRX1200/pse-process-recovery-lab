"""Reproducible ALD input experiments; no solver results are generated here."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from native_lab.sequence_schema import FIELDS, validate_sequence


# Proposed study conditions, not calibrated equipment recipes. Each case is
# normalized independently so applying one never inherits the previous UI input.
BASE = {"duration_s": 5, "cycles": 160, "pulse_s": 0.02,
        "pressure_pa": 3, "width_nm": 100, "rays_per_point": 300}
CASES = [
    ("D01", "기준 증착", None, {},
     "기준 조건에서 상단과 바닥에 얼마나 성장하는가?",
     "막 두께와 통로 폭을 기록해 나머지 실험의 비교 기준을 만든다.",
     "상단·바닥 두께, 두께비, 완료 사이클, 중간·최소 통로 폭"),
    ("D02", "짧은 노출", "D01", {"pulse_s": 0.005},
     "전구체 노출이 부족하면 두께와 바닥 피복은 어떻게 달라지는가?",
     "짧은 노출에서 성장량이 감소하는지, 바닥/상단 비도 달라지는지 확인한다.",
     "막 두께와 두께비; 얇은 막은 격자 민감도도 확인"),
    ("D03", "긴 노출", "D01", {"pulse_s": 0.1},
     "노출을 5배 늘려도 성장량이 5배 증가하는가?",
     "피복 포화로 노출 증가 대비 성장 증가가 둔화되는지 확인한다.",
     "상단 두께/완료 사이클, 바닥/상단 비; 포화 여부"),
    ("D04", "낮은 분압", "D01", {"pressure_pa": 1},
     "같은 노출 시간에 TMA 공급을 줄이면 무엇이 달라지는가?",
     "입구 열 플럭스 감소에 따른 막 두께와 깊이 방향 피복 변화를 확인한다.",
     "상단·바닥 두께와 두께비"),
    ("D05", "높은 분압", "D01", {"pressure_pa": 6},
     "TMA 분압을 높이면 바닥 성장도 함께 개선되는가?",
     "공급 증가가 바닥 성장에 미치는 효과와 포화에 따른 한계를 확인한다.",
     "D04–D01–D05의 분압별 두께와 두께비"),
    ("D06", "80 사이클", "D01", {"cycles": 80},
     "사이클을 절반으로 줄이면 막 두께도 절반인가?",
     "초기 성장 구간의 겉보기 GPC와 통로 폭을 기준 조건과 비교한다.",
     "상단 두께/완료 사이클, 중간·최소 통로 폭"),
    ("D07", "320 사이클", "D01", {"cycles": 320},
     "두껍게 증착할 때 통로가 얼마나 좁아지는가?",
     "성장에 따른 형상 변화가 바닥 수송을 제한하는지 확인한다. 통로가 좁아지면 조기 종료할 수 있다.",
     "최소 통로 폭, 두께비 이력, 요청/완료 사이클 차이"),
    ("D08", "같은 P×t, 다른 조합", "D01", {"pressure_pa": 6, "pulse_s": 0.01},
     "3 Pa × 0.02 s와 6 Pa × 0.01 s는 같은 결과인가?",
     "명목 노출량 0.06 Pa·s를 맞춘 두 조건을 비교한다. 탈착과 수송 때문에 동일한 성장을 보장하지 않는다.",
     "상단·바닥 두께 차이; 두 변수를 함께 바꾼 비교"),
    ("D09", "좁은 개구", "D01", {"width_nm": 60},
     "같은 식각·증착 레시피를 좁은 개구에 적용하면?",
     "개구 변경으로 식각 형상도 달라진다. 실제 식각 깊이와 폭을 먼저 읽고 바닥 피복과 통로 축소를 비교한다.",
     "Strip 단면, 식각 깊이, 바닥/상단 비, 최소 통로 폭"),
    ("D10", "좁은 개구 + 긴 노출", "D09", {"width_nm": 60, "pulse_s": 0.1},
     "좁은 구조에서 노출 연장이 바닥 증착을 개선하는가?",
     "D09와 비교해 바닥 두께 증가와 통로 축소의 상충 관계를 확인한다. 개선 여부는 계산 후 판단한다.",
     "D09 대비 바닥 두께·두께비·최소 통로 폭"),
]


def catalog():
    recipes = []
    for key, title, compare_to, changes, question, hypothesis, observe in CASES:
        request = validate_sequence({"model": "sequence", "params": {**BASE, **changes}})
        params = request["params"]
        comparison = next((r for r in recipes if r["id"] == compare_to), None)
        changed = [f["key"] for f in FIELDS
                   if comparison and params[f["key"]] != comparison["request"]["params"][f["key"]]]
        recipes.append(dict(id=key, title=title, compare_to=compare_to,
                            changed_keys=changed, request=request, question=question,
                            hypothesis=hypothesis, observe=observe))
    return {"format": "native-ald-experiments-v1", "kind": "input_presets",
            "recipes": recipes}


def build():
    target = Path(__file__).resolve().parents[1] / "sim_app/frontend/public/native"
    target.mkdir(parents=True, exist_ok=True)
    data = catalog()
    (target / "ald-recipes.json").write_text(
        json.dumps(data, ensure_ascii=False, allow_nan=False, indent=2) + "\n", encoding="utf-8")
    keys = [f["key"] for f in FIELDS]
    # UTF-8 BOM keeps Korean text readable when opened directly in Excel.
    with (target / "ald-experiments.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["id", "title", "compare_to", "changed_keys", "evidence",
                         "question", "hypothesis", "observe", *keys])
        for recipe in data["recipes"]:
            writer.writerow([recipe["id"], recipe["title"], recipe["compare_to"] or "",
                             ";".join(recipe["changed_keys"]), "input preset; not a computed result",
                             recipe["question"], recipe["hypothesis"], recipe["observe"],
                             *(recipe["request"]["params"][k] for k in keys)])


if __name__ == "__main__":
    build()
