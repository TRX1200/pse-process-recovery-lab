import { Info } from "lucide-react";
import { comparisonLabel, metricNumber, metricValidity } from "../storage";
import type { ModelKey, ModelResult } from "../types";

const PRIORITY: Record<ModelKey, string[]> = {
  etch: [
    "electron_density_m3",
    "electron_temperature_ev",
    "etch_depth_nm",
    "selectivity",
  ],
  ald: ["top_thickness_nm", "gpc_nm", "conformality_pct", "overlap_pa_s"],
};

export function Metrics({
  model,
  result,
  baseline,
}: {
  model: ModelKey;
  result?: ModelResult;
  baseline?: ModelResult | null;
}) {
  const outside = result?.effective.status === "outside_rate_fit";
  const metrics = result
    ? [...result.metrics].sort((a, b) => {
        const indexA = PRIORITY[model].indexOf(a.key);
        const indexB = PRIORITY[model].indexOf(b.key);
        return (indexA < 0 ? 99 : indexA) - (indexB < 0 ? 99 : indexB);
      })
    : [];
  return (
    <section className="metrics-panel" aria-label="Model results">
      <header>
        <h2>Model results</h2>
        <span>계산된 종점 · 정상상태</span>
      </header>
      {result ? (
        <>
          <div className="metric-rows">
            {metrics.slice(0, 4).map((metric) => {
              const ref = baseline?.metrics.find(
                (other) => other.key === metric.key,
              );
              const undefinedRatio =
                metric.key === "selectivity" &&
                result.effective.selectivity_defined === false;
              const noGrowth =
                metric.key === "conformality_pct" &&
                (result.metrics.find((m) => m.key === "top_thickness_nm")
                  ?.value ?? 1) < 1e-12;
              const comparable =
                ref &&
                baseline &&
                metricValidity(
                  metric.key,
                  baseline.metrics,
                  baseline.effective,
                ) === "valid" &&
                !outside &&
                !undefinedRatio &&
                !noGrowth;
              const difference = ref ? Math.abs(metric.value - ref.value) : 0;
              return (
                <div className="metric-row" key={metric.key}>
                  <div className="metric-label">
                    {metric.label}
                    <Info size={13} aria-hidden="true" />
                  </div>
                  <div className="metric-value">
                    <strong
                      className={undefinedRatio || noGrowth ? "value-text" : ""}
                    >
                      {outside
                        ? "—"
                        : undefinedRatio
                          ? "정의 불가"
                          : noGrowth
                            ? "성장 없음"
                            : metricNumber(metric.value, metric.digits)}
                    </strong>
                    <span>{outside ? "적용 범위 밖" : metric.unit}</span>
                    {comparable && (
                      <small
                        className={
                          difference >
                          Math.max(Math.abs(ref.value) * 0.01, 1e-12)
                            ? "changed"
                            : ""
                        }
                        title="기준값 절댓값이 표시 단위에서 1e-6 미만이면 백분율 대신 절대 차이를 표시합니다."
                      >
                        {comparisonLabel(metric.value, ref.value, metric.unit)}
                      </small>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
          {metrics.length > 4 && (
            <details className="more-metrics">
              <summary>전체 결과 {metrics.length}개 보기</summary>
              <div>
                {metrics.slice(4).map((metric) => (
                  <div className="additional-metric" key={metric.key}>
                    <span>{metric.label}</span>
                    <b>
                      {outside
                        ? "—"
                        : metricNumber(metric.value, metric.digits)}{" "}
                      <small>{metric.unit}</small>
                    </b>
                  </div>
                ))}
              </div>
            </details>
          )}
        </>
      ) : (
        <div className="metrics-empty">
          <div className="empty-line" />
          <div className="empty-line short" />
          <p>
            레시피를 설정한 뒤<br />
            <strong>Run simulation</strong>을 눌러 주세요.
          </p>
          <small>모든 수치는 Python 모델의 계산 결과로 표시됩니다.</small>
        </div>
      )}
    </section>
  );
}
