import { useRef, useState } from "react";
import { ArrowRight, Download, LoaderCircle, Play } from "lucide-react";
import { simulate } from "../api";
import { evaluate, STATUS_LABELS } from "../assessment";
import type { ProcessSpec } from "../assessment";
import { download, exportJson, metricNumber, metricValidity } from "../storage";
import {
  actionBounds,
  CASE_LABELS,
  CASE_METRICS,
  comparisonSeries,
  createInvestigationPlan,
  defaultInvestigationSettings,
} from "../investigation";
import type {
  InvestigationRecord,
  InvestigationSettings,
} from "../investigation";
import type { ModelKey, ModelSchema, Simulation } from "../types";
import { Chart } from "./Chart";

interface InvestigationProps {
  model: ModelKey;
  schema: ModelSchema;
  busy: boolean;
  setBusy: (busy: boolean) => void;
  record?: InvestigationRecord;
  onComplete: (record: InvestigationRecord) => void;
  onOpenRun: (
    run: Simulation,
    tab?: "process" | "assessment" | "equations",
  ) => void;
  onExplore: (tab?: "process" | "equations") => void;
  spec: ProcessSpec;
}

interface Writing {
  hypothesis: string;
  interpretation: string;
}

const noteKey = (model: ModelKey) =>
  `process-studio-investigation-notes-v1-${model}`;

function loadWriting(model: ModelKey): { notes: Writing; warning: string } {
  const empty = { hypothesis: "", interpretation: "" };
  try {
    const raw: unknown = JSON.parse(
      localStorage.getItem(noteKey(model)) ?? "null",
    );
    if (raw === null) return { notes: empty, warning: "" };
    if (
      typeof raw !== "object" ||
      !raw ||
      !("hypothesis" in raw) ||
      !("interpretation" in raw) ||
      typeof raw.hypothesis !== "string" ||
      typeof raw.interpretation !== "string"
    )
      throw new Error("Invalid note format");
    return {
      notes: { hypothesis: raw.hypothesis, interpretation: raw.interpretation },
      warning: "",
    };
  } catch {
    return {
      notes: empty,
      warning:
        "이전 메모를 읽지 못했습니다. 작성한 내용은 보고서로도 저장해 주세요.",
    };
  }
}

function metricText(
  run: Simulation | undefined,
  key: string,
  digits: number,
): string {
  if (!run) return "—";
  const { metrics, effective } = run.result;
  const validity = metricValidity(key, metrics, effective);
  if (validity !== "valid")
    return {
      outside_rate_fit: "모델 범위 밖",
      undefined_ratio: "정의 불가",
      no_growth: "성장 없음",
    }[validity];
  const value = metrics.find((item) => item.key === key)?.value;
  return value === undefined ? "—" : metricNumber(value, digits);
}

function reportMarkdown(
  model: ModelKey,
  record: InvestigationRecord,
  spec: ProcessSpec,
  notes: Writing,
  jsonName: string,
): string {
  const lines = [
    `# ${model === "etch" ? "RF 전달 손실과 전력 보상" : "배기 지연과 퍼지 연장"} 실험 노트`,
    "",
    "Python 축약 모델에서 가설을 비교한 학습 기록입니다. 실제 장비 고장 진단·수리 또는 공정 인증 결과가 아닙니다.",
    "",
    "## 계산 전 가설 (사용자 작성)",
    "",
    notes.hypothesis.trim() || "아직 작성하지 않았습니다.",
    "",
    "## 설정과 평가 기준",
    "",
    `이상 강도: ${record.settings.severity}; 조치 설정: ${record.settings.action} ${model === "etch" ? "W" : "s (A/B 각각)"}.`,
    "현재 화면의 규격으로 재평가한 결과입니다. 규격은 산업 합격 기준이 아닙니다.",
    "",
    "```json",
    JSON.stringify(spec, null, 2),
    "```",
    "",
    `| 지표 | ${CASE_LABELS[model].join(" | ")} |`,
    "| --- | ---: | ---: | ---: |",
    ...CASE_METRICS[model].map(
      (item) =>
        `| ${item.label} (${item.unit}) | ${record.runs.map((run) => metricText(run, item.key, item.digits)).join(" | ")} |`,
    ),
    "",
    "## 실행 이력과 전체 입력",
    "",
  ];
  record.runs.forEach((run, index) => {
    const assessment = evaluate(model, run.result, run.params, spec);
    lines.push(
      `### ${CASE_LABELS[model][index]}`,
      "",
      `- Run ID: ${run.run_id}`,
      `- Created: ${run.created_at}`,
      `- Model: ${run.result.model_version}`,
      `- Fault: ${run.fault}`,
      `- 현재 규격 판정: ${STATUS_LABELS[assessment.status]}`,
      "",
      "```json",
      JSON.stringify(run.params, null, 2),
      "```",
      "",
    );
  });
  lines.push(
    "## 내 해석 (사용자 작성)",
    "",
    notes.interpretation.trim() || "아직 작성하지 않았습니다.",
    "",
    "## 모델 범위와 원시 데이터",
    "",
    model === "etch"
      ? "0D Ar 플라즈마 수지와 가상 반응종의 표면 제거 모델입니다. 식각 시간 곡선은 균일한 대표 이온 플럭스에서의 값이며 표의 면적 평균 깊이와 다릅니다. 전력 보상은 흡수 전력을 맞추는 계산이며 RF 매칭 복구를 입증하지 않습니다."
      : "일반 열 ALD의 1D 반응·확산 모델입니다. 첫 사이클을 계산한 뒤 N회로 선형 투영하며 실제 물질의 불순물·결함을 예측하지 않습니다. 긴 퍼지가 모든 규격의 충족을 보장하지 않습니다.",
    "",
    `전체 입력·시계열·공간 분포·진단·가정·모델 버전은 같은 화면에서 JSON으로 저장하세요: ${jsonName}`,
    "",
    "보고서의 숫자는 화면 표시 자릿수로 반올림했습니다. 원시 JSON은 계산 응답의 수치 정밀도를 유지합니다.",
    "",
  );
  return lines.join("\n");
}

export function Investigation(props: InvestigationProps) {
  // Each process keeps its own notes and defaults when the user switches tabs.
  return <InvestigationNotebook key={props.model} {...props} />;
}

function InvestigationNotebook({
  model,
  schema,
  busy,
  setBusy,
  record,
  onComplete,
  onOpenRun,
  onExplore,
  spec,
}: InvestigationProps) {
  const [settings, setSettings] = useState<InvestigationSettings>(
    () => record?.settings ?? defaultInvestigationSettings(model, schema),
  );
  const [initialWriting] = useState(() => loadWriting(model));
  const [notes, setNotes] = useState(initialWriting.notes);
  const [noteWarning, setNoteWarning] = useState(initialWriting.warning);
  const [error, setError] = useState("");
  const [progress, setProgress] = useState(0);
  const [reportName, setReportName] = useState(`${model}-investigation`);
  const inFlight = useRef(false);
  const bounds = actionBounds(model, schema);
  const completed =
    record?.runs.length === 3 && record.runs.every((run) => run.model === model)
      ? record
      : undefined;
  const runs = completed?.runs;
  const chart = runs ? comparisonSeries(model, runs) : null;
  const labels = CASE_LABELS[model];
  const pending =
    completed &&
    (completed.settings.severity !== settings.severity ||
      completed.settings.action !== settings.action);
  const defaults = Object.fromEntries(
    schema.params.map((item) => [item.key, item.default]),
  );
  const filename =
    reportName
      .trim()
      .replace(/[^\p{L}\p{N}_-]+/gu, "-")
      .slice(0, 80) || `${model}-investigation`;

  function writeNotes(next: Writing) {
    setNotes(next);
    try {
      localStorage.setItem(noteKey(model), JSON.stringify(next));
      setNoteWarning("");
    } catch {
      setNoteWarning(
        "브라우저에 메모를 저장하지 못했습니다. 화면의 내용은 보고서로 저장할 수 있습니다.",
      );
    }
  }

  async function execute() {
    if (busy || inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setError("");
    setProgress(0);
    try {
      const captured = { ...settings };
      const plan = createInvestigationPlan(model, schema, captured);
      const responses: Simulation[] = [];
      for (const [index, step] of plan.entries()) {
        setProgress(index + 1);
        responses.push(await simulate(model, step.params, step.fault));
      }
      onComplete({ settings: captured, runs: responses });
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "세 조건 비교를 완료하지 못했습니다.",
      );
    } finally {
      inFlight.current = false;
      setBusy(false);
      setProgress(0);
    }
  }

  return (
    <section
      className="investigation"
      aria-label={`${model.toUpperCase()} 공정 실험 노트`}
    >
      <header className="investigation-title">
        <h1>
          {model === "etch"
            ? "설정 전력은 같은데, 왜 식각 깊이가 달라질까?"
            : "퍼지를 늘리면 정상 응답으로 돌아올까?"}
        </h1>
        <p>
          {model === "etch"
            ? "RF 전력 전달 → 플라즈마 수지 → 표면 반응."
            : "공급·배기 응답 → 채널 수송 → 표면 반응."}
          <br />
          Python 축약 모델로 원인과 결과를 연결하는 공정 실험 노트.
        </p>
      </header>

      <div className="investigation-body">
        <form
          className="experiment-design"
          onSubmit={(event) => {
            event.preventDefault();
            void execute();
          }}
        >
          <h2>실험 설계</h2>
          <fieldset disabled={busy}>
            <ol>
              <li>
                <span className="experiment-step-number">01</span>
                <h3>기준 조건</h3>
                <p>
                  {model === "etch"
                    ? `${metricNumber(defaults.source_power_w)} W · ${metricNumber(defaults.pressure_mtorr)} mTorr · ${metricNumber(defaults.process_time_s)} s. 모델 기본값을 기준으로 고정합니다.`
                    : `A/B 주입 각각 ${metricNumber(defaults.pulse_a_s)} / ${metricNumber(defaults.pulse_b_s)} s, 퍼지 ${metricNumber(defaults.purge_a_s)} / ${metricNumber(defaults.purge_b_s)} s. 기본 레시피의 한 사이클을 계산합니다.`}
                </p>
              </li>
              <li>
                <span className="experiment-step-number">02</span>
                <h3>{model === "etch" ? "RF 전달 손실" : "배기 응답 지연"}</h3>
                <p>
                  {model === "etch"
                    ? "반사율만 높여 흡수 전력과 식각 응답의 변화를 관찰합니다."
                    : "배기 시정수만 늘립니다. 강도 0.35에서는 기본값의 3.8배입니다."}
                </p>
                <label>
                  이상 강도 (0–0.8)
                  <input
                    type="number"
                    min={0}
                    max={0.8}
                    step="any"
                    required
                    value={
                      Number.isFinite(settings.severity)
                        ? settings.severity
                        : ""
                    }
                    onChange={(event) =>
                      setSettings({
                        ...settings,
                        severity: event.target.valueAsNumber,
                      })
                    }
                  />
                </label>
              </li>
              <li>
                <span className="experiment-step-number">03</span>
                <h3>
                  {model === "etch"
                    ? "소스 전력 보상 가설"
                    : "퍼지 시간 연장 가설"}
                </h3>
                <p>
                  {model === "etch"
                    ? "같은 RF 손실을 유지한 채 설정 전력만 바꿉니다."
                    : "같은 배기 지연을 유지한 채 A/B 퍼지만 늘립니다."}
                </p>
                <label>
                  {model === "etch"
                    ? "보상 소스 전력 (W)"
                    : "A/B 뒤 퍼지 각각 (s)"}
                  <input
                    type="number"
                    min={bounds.min}
                    max={bounds.max}
                    step="any"
                    required
                    value={
                      Number.isFinite(settings.action) ? settings.action : ""
                    }
                    onChange={(event) =>
                      setSettings({
                        ...settings,
                        action: event.target.valueAsNumber,
                      })
                    }
                  />
                </label>
              </li>
            </ol>
            <button className="button primary" type="submit">
              {busy ? (
                <LoaderCircle size={16} className="spin" />
              ) : (
                <Play size={16} />
              )}
              {busy
                ? progress
                  ? `${progress}/3 조건 계산 중…`
                  : "계산 준비 중…"
                : "비교 실험 계산"}
            </button>
          </fieldset>
          <div className="experiment-actions">
            <button
              className="text-button"
              type="button"
              disabled={busy}
              onClick={() => onExplore("process")}
            >
              레시피 직접 조절 <ArrowRight size={14} />
            </button>
            <button
              className="text-button"
              type="button"
              disabled={busy}
              onClick={() => onExplore("equations")}
            >
              수식과 가정 <ArrowRight size={14} />
            </button>
          </div>
        </form>

        <div className="experiment-evidence">
          <div className="evidence-title">
            <h2>정상 · 이상 · 조치 가설 비교</h2>
            <span>{completed ? "계산 결과" : "실행 전"}</span>
          </div>
          {error && (
            <p className="error-banner" role="alert">
              {error} 새 비교는 저장되지 않았습니다.
            </p>
          )}
          {pending && (
            <p className="case-notice" role="status">
              설정이 바뀌었습니다. 아래는 이전 실행 결과입니다. 다시 실행해야 새
              조건이 반영됩니다.
            </p>
          )}
          {completed && (
            <p className="case-notice">
              표시 중인 실행: 이상 강도{" "}
              {metricNumber(completed.settings.severity, 3)} ·{" "}
              {model === "etch" ? "보상 전력" : "A/B 퍼지 각각"}{" "}
              {metricNumber(completed.settings.action, 4)} {bounds.unit}
            </p>
          )}
          <div className="case-table-scroll">
            <table className="case-table">
              <thead>
                <tr>
                  <th scope="col">관측 지표</th>
                  {labels.map((label, index) => (
                    <th scope="col" key={label}>
                      <span>{label}</span>
                      {runs && (
                        <button
                          type="button"
                          className="case-run-link"
                          disabled={busy}
                          onClick={() => onOpenRun(runs[index], "process")}
                          title={`${runs[index].run_id} · ${runs[index].result.model_version}`}
                        >
                          run {runs[index].run_id}
                        </button>
                      )}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {CASE_METRICS[model].map((item) => (
                  <tr key={item.key}>
                    <th scope="row">
                      {item.label}
                      <small>{item.unit}</small>
                    </th>
                    {labels.map((label, index) => (
                      <td
                        key={label}
                        title={
                          runs
                            ? `계산값: ${runs[index].result.metrics.find((metric) => metric.key === item.key)?.value ?? "없음"}`
                            : "아직 계산하지 않았습니다."
                        }
                      >
                        {metricText(runs?.[index], item.key, item.digits)}
                      </td>
                    ))}
                  </tr>
                ))}
                <tr>
                  <th scope="row">현재 규격 판정</th>
                  {labels.map((label, index) => (
                    <td key={label}>
                      {runs ? (
                        <button
                          type="button"
                          className="case-run-link"
                          disabled={busy}
                          onClick={() => onOpenRun(runs[index], "assessment")}
                        >
                          {
                            STATUS_LABELS[
                              evaluate(
                                model,
                                runs[index].result,
                                runs[index].params,
                                spec,
                              ).status
                            ]
                          }
                        </button>
                      ) : (
                        "—"
                      )}
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>
          <p className="case-spec-note">
            판정은 현재 설정한 프로젝트 규격에 한정됩니다. 실제 장비·재료의 합격
            인증이 아닙니다.
          </p>
          {chart ? (
            <>
              <Chart series={chart} />
              <p className="case-chart-note">
                {model === "etch"
                  ? "곡선은 균일한 대표 이온 플럭스에서의 표면 제거량입니다. 위 표의 면적 평균 깊이와 구분합니다."
                  : "각 선은 해당 조건의 사이클 종료까지만 표시합니다. 더 짧은 사이클의 끝을 임의로 연장하지 않습니다."}
              </p>
            </>
          ) : (
            <div className="comparison-empty">
              <span>
                {model === "etch" ? "식각 깊이 / nm" : "챔버 B 분압 / Pa"}
              </span>
              <p>
                {completed
                  ? "표시 가능한 시간 곡선이 없습니다. 각 실행의 적용 범위를 확인하세요."
                  : "비교 실험을 계산하면 세 조건의 응답이 표시됩니다."}
              </p>
              <small>시간 / s</small>
            </div>
          )}
        </div>
      </div>

      <div className="investigation-notebook">
        <aside>
          <h2>다음 확인</h2>
          <p>
            {model === "etch"
              ? "깊이가 기준과 가까워져도, RF 매칭 문제를 해결했다고 말할 수 있을까? 전력·마스크 손실·선택비를 함께 해석해 보세요."
              : "잔류 분압이 줄었다면 충분할까? 깊이 방향 두께비와 사이클 시간도 현재 규격을 만족하는지 확인해 보세요."}
          </p>
          <h3>실제 장비라면 추가로 볼 데이터</h3>
          <p>
            {model === "etch"
              ? "순방향·반사 전력, 매칭 위치 변화, 압력·유량 로그와 식각 후 계측. 이 항목들은 현재 실험에 실측 데이터로 연결되어 있지 않습니다."
              : "밸브 동작 시각과 분압 감쇠 로그, 입구·깊은 곳의 막 두께 계측. 이 항목들은 현재 실험에 실측 데이터로 연결되어 있지 않습니다."}
          </p>
          <p>
            {model === "etch"
              ? "전력 보상으로 흡수 전력을 맞추면 이 모델에서는 반응도 복원될 수 있습니다. 보상 결과를 RF 매칭 복구의 증거로 해석하지 않습니다."
              : "퍼지 연장은 배기 지연을 없애지 않습니다. 시간이 늘어나는 대가와 남아 있는 규격 미달을 함께 기록합니다."}
          </p>
        </aside>
        <div className="case-writing">
          <label>
            계산 전 가설
            <textarea
              rows={3}
              value={notes.hypothesis}
              onChange={(event) =>
                writeNotes({ ...notes, hypothesis: event.target.value })
              }
              placeholder="어떤 지표가 왜 변할 것으로 예상하나요? 계산 전에 내 가설을 적어 보세요."
            />
          </label>
          <label>
            내 해석
            <textarea
              rows={4}
              value={notes.interpretation}
              onChange={(event) =>
                writeNotes({ ...notes, interpretation: event.target.value })
              }
              placeholder="계산값을 근거로 가설을 판단하고, 아직 알 수 없는 점과 다음 확인을 적어 보세요."
            />
          </label>
          <p className="case-spec-note">
            메모는 이 브라우저에 저장됩니다. 가설과 해석은 직접 작성하며, 수정
            시각을 고정한 사전 등록 기록은 아닙니다.
          </p>
          {noteWarning && (
            <p className="case-notice" role="status">
              {noteWarning}
            </p>
          )}
        </div>
      </div>

      <section className="case-export" aria-label="실험 기록 저장">
        <div>
          <h2>내 실험 기록 저장</h2>
          <p>
            입력 조건 · 실행 ID · 모델 버전 · 원시 시계열 · 현재 규격 · 내가 쓴
            해석
          </p>
        </div>
        <label>
          보고서 이름
          <input
            value={reportName}
            maxLength={80}
            onChange={(event) => setReportName(event.target.value)}
          />
        </label>
        <div className="case-export-actions">
          <button
            type="button"
            className="button secondary"
            disabled={!completed || busy}
            onClick={() => {
              if (!completed) return;
              exportJson(`${filename}.json`, {
                format: "process-studio-investigation-v1",
                exported_at: new Date().toISOString(),
                model,
                settings: completed.settings,
                runs: completed.runs,
                evaluation_spec_at_export: spec,
                assessments: completed.runs.map((run) => ({
                  run_id: run.run_id,
                  review: evaluate(model, run.result, run.params, spec),
                })),
                user_notes: notes,
                evidence:
                  "Reduced-model simulation only; no equipment measurements or repair validation.",
              });
            }}
          >
            <Download size={15} />
            원시 데이터 JSON
          </button>
          <button
            type="button"
            className="button secondary"
            disabled={!completed || busy}
            onClick={() => {
              if (completed)
                download(
                  `${filename}.md`,
                  reportMarkdown(
                    model,
                    completed,
                    spec,
                    notes,
                    `${filename}.json`,
                  ),
                  "text/markdown;charset=utf-8",
                );
            }}
          >
            <Download size={15} />
            Markdown 보고서
          </button>
        </div>
      </section>

      <p className="case-scope">
        {model === "etch"
          ? "모델 범위: 0D Ar 플라즈마 수지 + 가상 반응종의 표면 제거. 방사형 이온 플럭스는 입력한 분포입니다. RF 전자기장·실제 가스 반응망·패턴 측벽 형상을 풀지 않습니다."
          : "모델 범위: 일반 열 ALD의 1D 반응·확산. 첫 사이클 결과를 N회로 선형 투영합니다. 특정 장비·재료의 검증 레시피가 아니며 불순물·결함을 예측하지 않습니다."}{" "}
        실제 장비에 보정한 TCAD가 아닌, 가정과 계산을 공개하는 학습용
        실험입니다.
      </p>
    </section>
  );
}
