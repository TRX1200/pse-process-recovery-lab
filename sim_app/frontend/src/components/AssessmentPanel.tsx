import { useState } from "react";
import {
  ArrowDownToLine,
  Check,
  ClipboardCheck,
  Info,
  TriangleAlert,
} from "lucide-react";
import {
  assessmentReport,
  CHECK_LABELS,
  defaultSpec,
  evaluate,
  SPEC_FIELDS,
  STATUS_LABELS,
  validateSpec,
} from "../assessment";
import type { AssessmentBaseline, ProcessSpec, SpecCheck } from "../assessment";
import { exportJson, metricNumber } from "../storage";
import type { ModelKey, Simulation } from "../types";

function shown(value: number | null): string {
  return value === null ? "—" : metricNumber(value, 4);
}
function bounds(check: SpecCheck): string {
  if (check.lower !== null && check.upper !== null)
    return `${shown(check.lower)}–${shown(check.upper)}`;
  return check.lower !== null
    ? `≥ ${shown(check.lower)}`
    : `≤ ${shown(check.upper)}`;
}

export function AssessmentPanel({
  model,
  run,
  spec,
  baseline,
  notes,
  onApply,
  onNotes,
}: {
  model: ModelKey;
  run: Simulation | null;
  spec: ProcessSpec;
  baseline: AssessmentBaseline | null;
  notes: string;
  onApply: (spec: ProcessSpec) => void;
  onNotes: () => void;
}) {
  const [draft, setDraft] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      Object.entries(spec.values).map(([key, value]) => [key, String(value)]),
    ),
  );
  const [error, setError] = useState("");
  const result = run?.model === model ? run.result : undefined;
  const review = evaluate(model, result, run?.params ?? {}, spec);
  const comparison = baseline
    ? evaluate(model, baseline.result, baseline.params, spec)
    : null;
  const edited = SPEC_FIELDS[model].some(
    (field) => draft[field.key] !== String(spec.values[field.key]),
  );
  const warnings =
    result?.diagnostics.filter((d) => d.level === "warning") ?? [];

  return (
    <section className="assessment-panel" aria-label="공정 평가">
      <div className={`assessment-verdict ${review.status}`}>
        <ClipboardCheck size={25} />
        <div>
          <span className="eyebrow">PROCESS REQUIREMENTS · 종점 기준</span>
          <h2>{STATUS_LABELS[review.status]}</h2>
          <p>
            {review.checks.filter((c) => c.status === "pass").length} /{" "}
            {review.checks.length} 항목 충족 ·{" "}
            {spec.origin === "project-example"
              ? "프로젝트 예제 규격"
              : "사용자 설정 규격"}
          </p>
        </div>
        <button
          className="button secondary small"
          disabled={!run || edited}
          onClick={() =>
            run &&
            exportJson(
              `${run.run_id}-assessment.json`,
              assessmentReport(run, spec, baseline, notes),
            )
          }
        >
          <ArrowDownToLine size={15} />
          평가 보고서 JSON
        </button>
      </div>
      <p className="assessment-scope">
        <Info size={15} />
        모델 내 요구조건 평가입니다. 실제 웨이퍼 합격·양산 승인·수율 판정은 아래
        미계산 항목과 실측 검증이 필요합니다.
      </p>
      {review.blockers.map((message) => (
        <p className="error-banner" key={message}>
          {message}
        </p>
      ))}

      <details className="spec-editor" open={edited || undefined}>
        <summary>
          목표 규격 설정 <span>기본값은 학습 예제 · 산업 공통 기준 아님</span>
        </summary>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            try {
              if (Object.values(draft).some((value) => !value.trim()))
                throw new Error("빈 규격 값을 채워 주세요.");
              const next = validateSpec(
                {
                  model,
                  origin: "user",
                  values: Object.fromEntries(
                    Object.entries(draft).map(([key, value]) => [
                      key,
                      Number(value),
                    ]),
                  ),
                },
                model,
              );
              onApply(next);
              setDraft(
                Object.fromEntries(
                  Object.entries(next.values).map(([key, value]) => [
                    key,
                    String(value),
                  ]),
                ),
              );
              setError("");
            } catch (err) {
              setError(
                err instanceof Error ? err.message : "규격을 확인하세요.",
              );
            }
          }}
        >
          <div className="spec-fields">
            {SPEC_FIELDS[model].map((field) => (
              <label key={field.key}>
                <span>
                  {field.label} <small>{field.unit}</small>
                </span>
                <input
                  type="number"
                  required
                  aria-label={field.label}
                  min={field.min}
                  max={field.max}
                  step="any"
                  value={draft[field.key]}
                  onChange={(event) =>
                    setDraft((current) => ({
                      ...current,
                      [field.key]: event.target.value,
                    }))
                  }
                />
              </label>
            ))}
          </div>
          <p>
            비교 실험 전에 규격을 정해 두세요. 규격 수정은 기존 결과의
            재평가이며 레시피 개선이 아닙니다. 현재 평가 규격은 브라우저에
            저장되고 보고서에 포함됩니다.
          </p>
          {edited && (
            <p className="spec-pending">
              아래 판정은 아직 이전 규격입니다. ‘규격 적용’을 누르면
              재평가합니다.
            </p>
          )}
          {error && (
            <p role="alert" className="spec-pending">
              {error}
            </p>
          )}
          <div className="spec-actions">
            <button className="button primary small" type="submit">
              규격 적용
            </button>
            <button
              className="button secondary small"
              type="button"
              onClick={() => {
                const initial = defaultSpec(model);
                onApply(initial);
                setDraft(
                  Object.fromEntries(
                    Object.entries(initial.values).map(([key, value]) => [
                      key,
                      String(value),
                    ]),
                  ),
                );
                setError("");
              }}
            >
              예제 규격 복원
            </button>
          </div>
        </form>
      </details>

      <div className="assessment-table-wrap">
        <table className="assessment-table">
          <caption>
            설정 규격과 마지막 실행의 종점 비교{" "}
            {comparison ? `· 비교: ${baseline?.label} (동일 평가 규격)` : ""}
          </caption>
          <thead>
            <tr>
              <th>평가 항목</th>
              <th>규격</th>
              <th>현재 계산값</th>
              {comparison && <th>비교 기준</th>}
              <th>판정</th>
            </tr>
          </thead>
          <tbody>
            {review.checks.map((check, index) => (
              <tr key={check.key}>
                <th scope="row">
                  {check.label}
                  <small>{check.unit}</small>
                </th>
                <td>{bounds(check)}</td>
                <td>{shown(check.value)}</td>
                {comparison && (
                  <td>
                    {shown(comparison.checks[index].value)}
                    <small>
                      {CHECK_LABELS[comparison.checks[index].status]}
                    </small>
                  </td>
                )}
                <td>
                  <span className={`check-badge ${check.status}`}>
                    {check.status === "pass" ? (
                      <Check size={13} />
                    ) : (
                      <TriangleAlert size={13} />
                    )}
                    {CHECK_LABELS[check.status]}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="assessment-next">
        <h3>판정의 근거와 다음 확인</h3>
        <p>
          아래는 관측에 따른 확인 순서입니다. 원인 확정이나 자동 최적화 결과가
          아닙니다.
        </p>
        {review.checks.map((check) => (
          <details key={check.key} open={check.status === "fail" || undefined}>
            <summary>
              <span className={`check-dot ${check.status}`} />
              {check.label} · {CHECK_LABELS[check.status]}
            </summary>
            <p>{check.definition}</p>
            <p>
              <b>다음 확인:</b> {check.nextCheck}
            </p>
          </details>
        ))}
      </div>
      <div className="assessment-bottom-grid">
        <div className="assessment-unmodeled">
          <h3>아직 평가할 수 없는 품질</h3>
          <ul>
            {review.unmodeled.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          <p>‘계산 가능한 항목 충족’이 이 항목들의 통과를 의미하지 않습니다.</p>
        </div>
        <div className="assessment-workflow">
          <h3>PSE 실험 기록으로 이어가기</h3>
          <ol>
            <li>규격과 기준 레시피를 먼저 고정</li>
            <li>미달 지표와 경쟁 원인 가설 기록</li>
            <li>한 변수를 바꾸어 가설을 구분</li>
            <li>회복된 지표와 악화된 지표를 함께 비교</li>
            <li>남은 미검증 항목과 고객에게 설명할 결론 작성</li>
          </ol>
          <button className="button secondary small" onClick={onNotes}>
            실험 메모 작성
          </button>
        </div>
      </div>
      {!!warnings.length && (
        <details className="assessment-warnings">
          <summary>
            모델 해석 경고 {warnings.length}건 · 규격 충족과 별도로 확인
          </summary>
          <ul>
            {warnings.map((w) => (
              <li key={w.message}>{w.message}</li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}
