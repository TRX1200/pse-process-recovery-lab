import { useState } from "react";
import { ArrowRight, Download, LoaderCircle } from "lucide-react";
import { runSweep } from "../api";
import { exportJson, metricNumber, metricValidity } from "../storage";
import type { ModelKey, ModelSchema, Params, Series, Sweep } from "../types";
import { Chart } from "./Chart";

export function SweepPanel({
  model,
  schema,
  params,
  fault,
}: {
  model: ModelKey;
  schema: ModelSchema;
  params: Params;
  fault: string;
}) {
  const [key, setKey] = useState(schema.params[0].key);
  const parameter = schema.params.find((item) => item.key === key)!;
  const [start, setStart] = useState(
    Math.max(parameter.min, params[key] * 0.5),
  );
  const [end, setEnd] = useState(
    Math.min(parameter.max, params[key] * 1.5 || parameter.max / 2),
  );
  const [count, setCount] = useState(5);
  const [result, setResult] = useState<Sweep | null>(null);
  const [metricKey, setMetricKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [executed, setExecuted] = useState("");
  const settings = JSON.stringify({
    model,
    params,
    fault,
    key,
    start,
    end,
    count,
  });
  const metric =
    result?.runs[0]?.metrics.find((item) => item.key === metricKey) ??
    result?.runs[0]?.metrics[0];
  const chart: Series | null =
    result && metric
      ? {
          key: "sweep",
          title: `${metric.label} · Parameter sweep`,
          x_label: `${schema.params.find((item) => item.key === result.parameter)?.label ?? result.parameter} (${result.unit})`,
          y_label: metric.unit,
          x: result.runs.map((run) => run.input),
          lines: [
            {
              name: metric.label,
              values: result.runs.map((run) =>
                metricValidity(metric.key, run.metrics, run.effective) ===
                "valid"
                  ? (run.metrics.find((item) => item.key === metric.key)
                      ?.value ?? NaN)
                  : NaN,
              ),
            },
          ],
        }
      : null;
  async function execute() {
    setBusy(true);
    setError("");
    try {
      if (end <= start) throw new Error("끝 값은 시작 값보다 커야 합니다.");
      const values = Array.from({ length: count }, (_, index) =>
        Number((start + ((end - start) * index) / (count - 1)).toPrecision(10)),
      );
      if (key === "cycles" && values.some((value) => !Number.isInteger(value)))
        throw new Error("반복 횟수는 모든 sweep 지점에서 정수여야 합니다.");
      const response = await runSweep(model, params, fault, key, values);
      setResult(response);
      setMetricKey(response.runs[0]?.metrics[0]?.key ?? "");
      setExecuted(settings);
    } catch (error) {
      setError(error instanceof Error ? error.message : "Sweep 계산 실패");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="sweep-panel">
      <div className="section-heading">
        <div>
          <h2>Parameter sweep</h2>
          <p>다른 조건을 고정하고, 한 파라미터의 영향을 비교합니다.</p>
        </div>
        {result && (
          <button
            className="button secondary small"
            onClick={() =>
              exportJson(`sweep-${model}-${result.parameter}.json`, result)
            }
          >
            <Download size={15} />
            JSON
          </button>
        )}
      </div>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void execute();
        }}
      >
        <fieldset disabled={busy} className="sweep-controls">
          <label>
            변경할 파라미터
            <select
              value={key}
              onChange={(event) => {
                const p = schema.params.find(
                  (item) => item.key === event.target.value,
                )!;
                setKey(p.key);
                setStart(p.min);
                setEnd(Math.min(p.max, params[p.key] * 2 || p.max));
              }}
            >
              {schema.params.map((parameter) => (
                <option key={parameter.key} value={parameter.key}>
                  {parameter.label} ({parameter.unit || "−"})
                </option>
              ))}
            </select>
          </label>
          <label>
            시작
            <input
              type="number"
              min={parameter.min}
              max={parameter.max}
              step="any"
              required
              value={start}
              onChange={(event) => setStart(Number(event.target.value))}
            />
          </label>
          <ArrowRight size={17} />
          <label>
            끝
            <input
              type="number"
              min={parameter.min}
              max={parameter.max}
              step="any"
              required
              value={end}
              onChange={(event) => setEnd(Number(event.target.value))}
            />
          </label>
          <label>
            계산 지점
            <input
              type="number"
              min={2}
              max={11}
              step={1}
              value={count}
              onChange={(event) => setCount(Number(event.target.value))}
            />
          </label>
          <button className="button primary" type="submit">
            {busy ? (
              <LoaderCircle size={16} className="spin" />
            ) : (
              <ArrowRight size={16} />
            )}
            {busy ? "계산 중…" : "Run sweep"}
          </button>
        </fieldset>
      </form>
      <p className="subtle-note">
        현재 레시피와 고장 설정을 적용합니다. 무차원 모델 계수도 탐색할 수
        있습니다.
      </p>
      {error && (
        <div className="error-banner" role="alert">
          {error}
        </div>
      )}
      {result && executed !== settings && (
        <div className="pending-banner">
          조건이 변경되었습니다. 아래는 이전 sweep 결과입니다.
        </div>
      )}
      {result && metric ? (
        <>
          <label className="metric-select">
            결과 지표
            <select
              value={metric.key}
              onChange={(event) => setMetricKey(event.target.value)}
            >
              {result.runs[0].metrics.map((item) => (
                <option value={item.key} key={item.key}>
                  {item.label} ({item.unit || "−"})
                </option>
              ))}
            </select>
          </label>
          {result.runs.some(
            (run) =>
              metricValidity(metric.key, run.metrics, run.effective) !==
              "valid",
          ) && (
            <div className="pending-banner">
              모델 적용 범위 밖이거나 정의되지 않은 값은 그래프에서
              제외했습니다.
            </div>
          )}
          {chart && <Chart series={chart} />}
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>입력 ({result.unit})</th>
                  <th>
                    {metric.label} ({metric.unit})
                  </th>
                  <th>상태</th>
                </tr>
              </thead>
              <tbody>
                {result.runs.map((run, index) => {
                  const validity = metricValidity(
                    metric.key,
                    run.metrics,
                    run.effective,
                  );
                  const labels = {
                    valid: "계산 완료",
                    outside_rate_fit: "모델 범위 밖",
                    undefined_ratio: "정의 불가",
                    no_growth: "성장 없음",
                  };
                  const value = run.metrics.find(
                    (item) => item.key === metric.key,
                  )?.value;
                  return (
                    <tr key={index}>
                      <td title={String(run.input)}>
                        {metricNumber(run.input, 8)}
                      </td>
                      <td
                        title={
                          validity === "valid"
                            ? `계산값: ${value}`
                            : labels[validity]
                        }
                      >
                        {validity === "valid" && value !== undefined
                          ? Number(value.toPrecision(8)).toString()
                          : "—"}
                      </td>
                      <td>{labels[validity]}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      ) : (
        <div className="workflow-empty">
          <div className="sweep-lines">
            <i />
            <i />
            <i />
          </div>
          <h3>한 번의 실험에서, 민감도까지.</h3>
          <p>시작 · 끝 값과 계산 지점을 정해 첫 sweep을 실행하세요.</p>
        </div>
      )}
    </section>
  );
}
