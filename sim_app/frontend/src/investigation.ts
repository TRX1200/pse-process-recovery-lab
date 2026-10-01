import { interpolate } from "./playback";
import type {
  ModelKey,
  ModelSchema,
  Params,
  Series,
  Simulation,
} from "./types";

export interface InvestigationSettings {
  severity: number;
  action: number;
}

export interface InvestigationRecord {
  settings: InvestigationSettings;
  runs: Simulation[];
}

export interface InvestigationStep {
  label: string;
  fault: string;
  params: Params;
}

export const CASE_LABELS: Record<ModelKey, [string, string, string]> = {
  etch: ["기준", "RF 손실", "전력 보상"],
  ald: ["기준", "배기 지연", "퍼지 연장"],
};

export const CASE_METRICS: Record<
  ModelKey,
  Array<{
    key: string;
    label: string;
    unit: string;
    digits: number;
  }>
> = {
  etch: [
    { key: "absorbed_power_w", label: "흡수 전력", unit: "W", digits: 2 },
    {
      key: "etch_depth_nm",
      label: "면적 평균 식각 깊이",
      unit: "nm",
      digits: 3,
    },
    { key: "mask_loss_nm", label: "마스크 손실", unit: "nm", digits: 3 },
    { key: "nonuniformity_pct", label: "깊이 비균일도", unit: "%", digits: 3 },
    {
      key: "selectivity",
      label: "정상 제거율 선택비",
      unit: "ratio",
      digits: 3,
    },
  ],
  ald: [
    {
      key: "top_thickness_nm",
      label: "입구 쪽 투영 두께",
      unit: "nm",
      digits: 3,
    },
    {
      key: "conformality_pct",
      label: "깊은 곳 / 입구 쪽",
      unit: "%",
      digits: 3,
    },
    {
      key: "overlap_pa_s",
      label: "A/B 분압 중첩 적분",
      unit: "Pa·s",
      digits: 5,
    },
    {
      key: "residual_pressure_pa",
      label: "종료 잔류 분압",
      unit: "Pa",
      digits: 5,
    },
    { key: "cycle_time_s", label: "사이클 시간", unit: "s", digits: 2 },
  ],
};

function parameter(schema: ModelSchema, key: string) {
  const found = schema.params.find((item) => item.key === key);
  if (!found) throw new Error(`실험에 필요한 파라미터가 없습니다: ${key}`);
  return found;
}

export function actionBounds(model: ModelKey, schema: ModelSchema) {
  const fields =
    model === "etch"
      ? [parameter(schema, "source_power_w")]
      : [parameter(schema, "purge_a_s"), parameter(schema, "purge_b_s")];
  return {
    min: Math.max(...fields.map((field) => field.min)),
    max: Math.min(...fields.map((field) => field.max)),
    unit: model === "etch" ? "W" : "s",
  };
}

export function defaultInvestigationSettings(
  model: ModelKey,
  schema: ModelSchema,
): InvestigationSettings {
  return {
    severity: 0.35,
    action:
      model === "etch"
        ? Number(
            (parameter(schema, "source_power_w").default / 0.65).toFixed(2),
          )
        : 3,
  };
}

/** Keep the fault fixed while changing only the proposed recipe intervention. */
export function createInvestigationPlan(
  model: ModelKey,
  schema: ModelSchema,
  settings: InvestigationSettings,
): InvestigationStep[] {
  if (
    !Number.isFinite(settings.severity) ||
    settings.severity < 0 ||
    settings.severity > 0.8
  )
    throw new Error("이상 강도는 0–0.8 범위의 유한한 수여야 합니다.");
  const bounds = actionBounds(model, schema);
  if (
    !Number.isFinite(settings.action) ||
    settings.action < bounds.min ||
    settings.action > bounds.max
  )
    throw new Error(
      `조치 설정은 ${bounds.min}–${bounds.max} ${bounds.unit} 범위여야 합니다.`,
    );
  const fault = model === "etch" ? "rf_mismatch" : "purge_restriction";
  if (
    !["none", fault].every((id) => schema.faults.some((item) => item.id === id))
  )
    throw new Error("이 모델은 선택한 실험의 이상 조건을 지원하지 않습니다.");
  parameter(schema, "fault_severity");
  const defaults: Params = Object.fromEntries(
    schema.params.map((item) => [item.key, item.default]),
  );
  const baseline: Params = { ...defaults, fault_severity: settings.severity };
  const intervention: Params =
    model === "etch"
      ? { ...baseline, source_power_w: settings.action }
      : { ...baseline, purge_a_s: settings.action, purge_b_s: settings.action };
  const plan: InvestigationStep[] = [
    { label: CASE_LABELS[model][0], fault: "none", params: { ...baseline } },
    { label: CASE_LABELS[model][1], fault, params: { ...baseline } },
    { label: CASE_LABELS[model][2], fault, params: intervention },
  ];
  for (const step of plan) {
    for (const field of schema.params) {
      const value = step.params[field.key];
      if (!Number.isFinite(value) || value < field.min || value > field.max)
        throw new Error(
          `${field.label}: ${field.min}–${field.max} ${field.unit} 범위를 확인하세요.`,
        );
    }
    if (model === "ald" && !Number.isInteger(step.params.cycles))
      throw new Error("ALD 반복 횟수는 정수여야 합니다.");
  }
  return plan;
}

/** A malformed grid cannot produce a valid comparison curve. */
export function interpolateWithinDomain(
  x: number[],
  values: number[],
  time: number,
): number {
  if (
    !x.length ||
    x.length !== values.length ||
    x.some(
      (value, index) =>
        !Number.isFinite(value) || (index > 0 && value <= x[index - 1]),
    )
  )
    return NaN;
  return interpolate(x, values, time) ?? NaN;
}

/** Align solved samples without extending the end of a shorter ALD cycle. */
export function comparisonSeries(
  model: ModelKey,
  runs: Simulation[],
): Series | null {
  if (!runs.length || runs.some((run) => run.model !== model)) return null;
  const key = model === "etch" ? "depth" : "pressure";
  const lineIndex = model === "etch" ? 0 : 1;
  const sources = runs.map((run) => {
    if (run.result.effective.status === "outside_rate_fit") return undefined;
    const series = run.result.series.find(
      (item) => item.key === key && item.x_label === "시간 (s)",
    );
    const values = series?.lines[lineIndex]?.values;
    if (
      !series ||
      !values ||
      series.x.length !== values.length ||
      series.x.some(
        (x, i) => !Number.isFinite(x) || (i > 0 && x <= series.x[i - 1]),
      )
    )
      return undefined;
    return { x: series.x, values };
  });
  const x = [...new Set(sources.flatMap((source) => source?.x ?? []))].sort(
    (a, b) => a - b,
  );
  if (!x.length) return null;
  return {
    key: `investigation-${model}`,
    title:
      model === "etch" ? "시간에 따른 표면 제거" : "시간에 따른 챔버 B 분압",
    x_label: "시간 (s)",
    y_label: model === "etch" ? "식각 깊이 (nm)" : "분압 (Pa)",
    x,
    lines: sources.map((source, index) => ({
      name: CASE_LABELS[model][index] ?? `조건 ${index + 1}`,
      values: x.map((time) =>
        source ? interpolateWithinDomain(source.x, source.values, time) : NaN,
      ),
    })),
  };
}
