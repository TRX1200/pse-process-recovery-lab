"""Export measured numerical errors, not a claim of process calibration."""
from datetime import datetime, timezone
from pathlib import Path
from native_lab.engine import simulate, environment
from native_lab.storage import write_json
from native_lab.tests.test_native import planar_ald


def main():
    checks, raw = [], {}
    coarse, oracle = planar_ald(.002)
    fine, _ = planar_ald(.0005)
    raw["planar_langmuir"] = dict(coarse_nm=coarse, fine_nm=fine, analytic_nm=oracle,
                                   coarse_dt_s=.002, fine_dt_s=.0005)
    error = 100*abs(fine-oracle)/oracle
    checks.append(dict(name="ALD 평면 해석해 비교", result=f"오차 {error:.3f}%",
                       detail="독립적인 Langmuir 닫힌 해와 평균 성장량 비교. 실측 비교 아님."))
    checks.append(dict(name="피복률 시간 간격", result="감소 확인" if abs(fine-oracle) < abs(coarse-oracle) else "재검토 필요",
                       detail=f"2 → 0.5 ms: 오차 {abs(coarse-oracle):.5f} → {abs(fine-oracle):.5f} nm."))
    base = dict(duration_s=1, output_steps=4, rays_per_point=500)
    a = simulate(dict(model="etch", params={**base, "grid_nm": 5}))
    b = simulate(dict(model="etch", params={**base, "grid_nm": 2.5}))
    am, bm = a["frames"][-1]["metrics"], b["frames"][-1]["metrics"]
    raw["etch_grid"] = dict(coarse=am, fine=bm, coarse_hash=a["run_hash"], fine_hash=b["run_hash"], params=base)
    difference = 100*abs(am["center_depth_nm"]-bm["center_depth_nm"])/bm["center_depth_nm"]
    checks.append(dict(name="Etch 격자 민감도", result=f"깊이 차이 {difference:.2f}%",
                       detail="5 → 2.5 nm, 동일 1 s 조건. 두 격자 비교이며 완전한 수렴 판정은 아님."))
    c = simulate(dict(model="etch", params={**base, "grid_nm": 5, "seed": 20261004}))
    cm = c["frames"][-1]["metrics"]
    seed_diff = 100*abs(am["center_depth_nm"]-cm["center_depth_nm"])/am["center_depth_nm"]
    raw["etch_seed"] = dict(other=cm, seed=20261004, run_hash=c["run_hash"])
    checks.append(dict(name="Monte Carlo 시드 민감도", result=f"깊이 차이 {seed_diff:.2f}%",
                       detail="두 시드의 비교. 신뢰구간이나 물리적 거칠기 측정은 아님."))
    checks.append(dict(name="실험 데이터 / 실제 장비", result="미검증",
                       detail="재료별 보정·독립 실측 대조 전입니다. 예제 형상은 측정 결과가 아닙니다."))
    result = dict(generated_at=datetime.now(timezone.utc).isoformat(), environment=environment(), checks=checks, raw=raw)
    target = Path(__file__).resolve().parents[1] / "sim_app/frontend/public/native/validation.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    write_json(target, result)
    for check in checks:
        print(check, flush=True)


if __name__ == "__main__":
    main()
