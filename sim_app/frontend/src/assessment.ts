import type { ModelKey, ModelResult, Params, Simulation } from "./types";

export const ASSESSMENT_VERSION = "process-spec-review-1.0";
export type CheckStatus = "pass" | "fail" | "unavailable";
export interface ProcessSpec {
  model: ModelKey;
  origin: "project-example" | "user";
  values: Record<string, number>;
}
export interface SpecField {
  key: string;
  label: string;
  unit: string;
  min: number;
  max: number;
  step: number | "any";
  initial: number;
}
export interface SpecCheck {
  key: string;
  label: string;
  unit: string;
  value: number | null;
  lower: number | null;
  upper: number | null;
  status: CheckStatus;
  definition: string;
  nextCheck: string;
}
export interface Assessment {
  status: "within_spec" | "outside_spec" | "incomplete";
  checks: SpecCheck[];
  blockers: string[];
  unmodeled: string[];
}
export interface AssessmentBaseline {
  label: string;
  run_id: string | null;
  params: Params;
  result: ModelResult;
}

// Demonstration requirements, chosen for the teaching exercise. They are neither
// industry acceptance limits nor coefficients fitted to equipment data.
export const SPEC_FIELDS: Record<ModelKey, SpecField[]> = {
  etch: [
    {
      key: "target_nm",
      label: "목표 평균 깊이",
      unit: "nm",
      min: 0.001,
      max: 1e6,
      step: "any",
      initial: 30,
    },
    {
      key: "tolerance_nm",
      label: "깊이 허용 편차 ±",
      unit: "nm",
      min: 0,
      max: 1e6,
      step: 0.1,
      initial: 3,
    },
    {
      key: "max_nonuniformity_pct",
      label: "비균일도 상한",
      unit: "%",
      min: 0,
      max: 100,
      step: 0.1,
      initial: 5,
    },
    {
      key: "max_mask_loss_nm",
      label: "마스크 손실 상한",
      unit: "nm",
      min: 0,
      max: 1e6,
      step: 0.1,
      initial: 3,
    },
    {
      key: "min_selectivity",
      label: "정상 선택비 하한",
      unit: "ratio",
      min: 0,
      max: 1e6,
      step: 0.1,
      initial: 10,
    },
    {
      key: "max_time_s",
      label: "처리 시간 상한",
      unit: "s",
      min: 0.001,
      max: 1e6,
      step: 1,
      initial: 90,
    },
  ],
  ald: [
    {
      key: "target_nm",
      label: "목표 입구 쪽 투영 두께",
      unit: "nm",
      min: 0.001,
      max: 1e6,
      step: 0.1,
      initial: 5,
    },
    {
      key: "tolerance_nm",
      label: "두께 허용 편차 ±",
      unit: "nm",
      min: 0,
      max: 1e6,
      step: 0.1,
      initial: 0.5,
    },
    {
      key: "min_conformality_pct",
      label: "깊은 곳 / 입구 쪽 하한",
      unit: "%",
      min: 0,
      max: 100,
      step: 0.1,
      initial: 95,
    },
    {
      key: "max_overlap_pa_s",
      label: "A/B 중첩 지표 상한",
      unit: "Pa·s",
      min: 0,
      max: 1e6,
      step: 0.001,
      initial: 0.02,
    },
    {
      key: "max_residual_pa",
      label: "종료 잔류 분압 상한",
      unit: "Pa",
      min: 0,
      max: 1e6,
      step: 0.001,
      initial: 0.01,
    },
    {
      key: "max_time_s",
      label: "사이클 시간 상한",
      unit: "s",
      min: 0.001,
      max: 1e6,
      step: 0.1,
      initial: 6,
    },
  ],
};

export const STATUS_LABELS = {
  within_spec: "계산 가능한 항목 충족",
  outside_spec: "설정 규격 미달",
  incomplete: "판정 보류",
};
export const CHECK_LABELS = {
  pass: "충족",
  fail: "미달",
  unavailable: "평가 불가",
};
export const UNMODELED: Record<ModelKey, string[]> = {
  etch: [
    "CD·측벽 각도·ARDE: 패턴 형상 해석 없음",
    "잔사·거칠기·플라즈마 손상: 해당 물성·반응 모델 없음",
    "하부막 손실·마스크 관통·엔드포인트: 다층막 전환 모델 없음",
    "웨이퍼 간 재현성·수율·Cpk: 반복 실측 데이터 없음",
  ],
  ald: [
    "막 조성·불순물·밀도·응력·전기적 특성: 해당 물성 모델 없음",
    "핵생성·사이클 누적·채널 좁아짐: 첫 사이클 × N 투영에 미포함",
    "실제 ALD window·자기 제한성 검증: 온도·노출량 스윕과 실측 비교 필요",
    "웨이퍼 간 재현성·수율·Cpk: 반복 실측 데이터 없음",
  ],
};

export function defaultSpec(model: ModelKey): ProcessSpec {
  return {
    model,
    origin: "project-example",
    values: Object.fromEntries(
      SPEC_FIELDS[model].map((f) => [f.key, f.initial]),
    ),
  };
}

export function validateSpec(value: unknown, model: ModelKey): ProcessSpec {
  const spec = value as ProcessSpec | null;
  if (
    !spec ||
    spec.model !== model ||
    !["project-example", "user"].includes(spec.origin) ||
    !spec.values ||
    typeof spec.values !== "object"
  )
    throw new Error("규격의 모델과 형식을 확인하세요.");
  const fields = SPEC_FIELDS[model];
  if (
    Object.keys(spec.values).length !== fields.length ||
    Object.keys(spec.values).some((key) => !fields.some((f) => f.key === key))
  )
    throw new Error("지원하지 않는 규격 항목입니다.");
  for (const field of fields) {
    const number = spec.values[field.key];
    if (
      typeof number !== "number" ||
      !Number.isFinite(number) ||
      number < field.min ||
      number > field.max
    )
      throw new Error(
        `${field.label}: ${field.min}–${field.max} ${field.unit} 범위를 확인하세요.`,
      );
  }
  if (spec.values.tolerance_nm >= spec.values.target_nm)
    throw new Error("허용 편차는 목표 두께/깊이보다 작아야 합니다.");
  return { model, origin: spec.origin, values: { ...spec.values } };
}

export function metricValue(
  result: ModelResult | undefined,
  key: string,
): number | null {
  const value = result?.metrics.find((metric) => metric.key === key)?.value;
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function evaluate(
  model: ModelKey,
  result: ModelResult | undefined,
  params: Params,
  spec: ProcessSpec,
): Assessment {
  const s = validateSpec(spec, model).values;
  const blockers: string[] = [];
  if (!result) blockers.push("시뮬레이션 실행 결과가 없습니다.");
  if (result?.effective.status === "outside_rate_fit")
    blockers.push(
      "속도식 적용 범위 밖: 출력 0을 합격 판정에 사용하지 않습니다.",
    );
  if (
    result &&
    model === "etch" &&
    !["steady", "off", "outside_rate_fit"].includes(
      String(result.effective.status),
    )
  )
    blockers.push("플라즈마 계산 상태를 확인할 수 없습니다.");
  const expectedVersion =
    model === "etch" ? "etch-ar-global-0.1.1" : "ald-reactive-diffusion-1.0.1";
  if (result && result.model_version !== expectedVersion)
    blockers.push(
      "이전/알 수 없는 모델 버전입니다. 현재 모델로 다시 실행하세요.",
    );
  const get = (key: string) =>
    blockers.length ? null : metricValue(result, key);
  const checks: SpecCheck[] = [];
  const check = (
    key: string,
    label: string,
    unit: string,
    value: number | null,
    lower: number | null,
    upper: number | null,
    definition: string,
    nextCheck: string,
  ) => {
    const usable =
      !blockers.length &&
      value !== null &&
      Number.isFinite(value) &&
      value >= 0;
    const status: CheckStatus = !usable
      ? "unavailable"
      : (lower !== null && value < lower) || (upper !== null && value > upper)
        ? "fail"
        : "pass";
    checks.push({
      key,
      label,
      unit,
      value: usable ? value : null,
      lower,
      upper,
      status,
      definition,
      nextCheck,
    });
  };
  if (model === "etch") {
    const depth = get("etch_depth_nm");
    check(
      "depth",
      "면적 평균 식각 깊이",
      "nm",
      depth,
      s.target_nm - s.tolerance_nm,
      s.target_nm + s.tolerance_nm,
      "종점의 면적 평균 제거량. 평균 충족은 모든 위치의 규격 충족을 뜻하지 않습니다.",
      "흡수 전력·이온/라디칼 공급과 처리 시간을 구분해 확인하세요. 시간을 늘릴 때 마스크 손실도 비교하세요.",
    );
    check(
      "uniformity",
      "깊이 비균일도",
      "%",
      depth !== null && depth > 0 ? get("nonuniformity_pct") : null,
      null,
      s.max_nonuniformity_pct,
      "NU = (dmax − dmin) / (2 × 면적 평균 깊이) × 100. 평균 깊이 0이면 정의되지 않습니다.",
      "반경별 깊이를 확인하세요. 현재 분포는 가정된 이온 플럭스이며 실제 장비에서는 wafer map과 챔버 상태가 필요합니다.",
    );
    check(
      "mask",
      "면적 평균 마스크 손실",
      "nm",
      get("mask_loss_nm"),
      null,
      s.max_mask_loss_nm,
      "이온 플럭스 × 마스크 수율 × 시간 / 마스크 원자밀도. 초기 마스크 두께·관통은 계산하지 않습니다.",
      "바이어스·이온 에너지·시간을 함께 확인하고, 낮춘 조건에서 목표 깊이가 유지되는지 시험하세요.",
    );
    check(
      "selectivity",
      "정상 선택비",
      "ratio",
      result?.effective.selectivity_defined === true
        ? get("selectivity")
        : null,
      s.min_selectivity,
      null,
      "S = 면적 평균 정상 타깃 제거율 / 정상 마스크 제거율. 분모 0은 무한 선택비로 판정하지 않습니다.",
      "타깃/마스크 제거율을 따로 보세요. 반응 가스·바이어스 변화가 각각에 미치는 영향을 비교하세요.",
    );
    check(
      "time",
      "처리 시간",
      "s",
      Number.isFinite(params.process_time_s) ? params.process_time_s : null,
      null,
      s.max_time_s,
      "노출 처리 시간만 평가합니다. 이송·안정화·세정 시간을 포함한 장비 처리량은 아닙니다.",
      "시간 보상으로 깊이를 회복해도 생산성 목표를 넘는지 확인하세요.",
    );
  } else {
    check(
      "thickness",
      "입구 쪽 투영 두께",
      "nm",
      get("top_thickness_nm"),
      s.target_nm - s.tolerance_nm,
      s.target_nm + s.tolerance_nm,
      "첫 셀의 1회 성장량 × 사이클 수. 매 사이클 진화를 직접 계산한 총 두께가 아닙니다.",
      "1회 성장량과 사이클 수를 분리해 보세요. 사이클 수 증가가 부족한 깊이 방향 피복을 해결하는지 별도로 확인하세요.",
    );
    const growth = get("gpc_nm");
    check(
      "conformality",
      "깊은 곳 / 입구 쪽",
      "%",
      growth !== null && growth >= 1e-12 ? get("conformality_pct") : null,
      s.min_conformality_pct,
      null,
      "100 × 마지막 셀 성장 / 첫 셀 성장. 입구 쪽 성장이 거의 0이면 정의되지 않습니다.",
      "A/B 노출량·채널 깊이·확산을 확인하세요. 펄스 연장 전후의 입구와 깊은 곳 성장을 각각 비교하세요.",
    );
    check(
      "overlap",
      "A/B 분압 중첩 지표",
      "Pa·s",
      get("overlap_pa_s"),
      null,
      s.max_overlap_pa_s,
      "∫ min(PA, PB) dt. 분압 중첩의 대리 지표이며 실제 CVD·불순물 농도가 아닙니다.",
      "배기 시정수와 퍼지 시간을 확인하세요. 퍼지 연장이 중첩을 줄이는 효과와 사이클 시간 증가를 함께 비교하세요.",
    );
    check(
      "residual",
      "종료 잔류 분압",
      "Pa",
      get("residual_pressure_pa"),
      null,
      s.max_residual_pa,
      "사이클 끝의 챔버 PA + PB. 잔류가 작아도 막 조성·결함까지 보증하지 않습니다.",
      "B 뒤 퍼지와 배기 응답을 점검하세요. 미반응 표면에 대한 모델 경고도 확인하세요.",
    );
    check(
      "time",
      "사이클 시간",
      "s",
      get("cycle_time_s"),
      null,
      s.max_time_s,
      "A 주입 + A 퍼지 + B 주입 + B 퍼지. 이송·안정화 시간 제외.",
      "퍼지나 펄스 연장의 효과를 두께·피복·잔류 개선과 함께 비교하세요.",
    );
  }
  const status = blockers.length
    ? "incomplete"
    : checks.some((c) => c.status === "fail")
      ? "outside_spec"
      : checks.some((c) => c.status === "unavailable")
        ? "incomplete"
        : "within_spec";
  return { status, checks, blockers, unmodeled: [...UNMODELED[model]] };
}

export function loadSpecs(): Record<ModelKey, ProcessSpec> {
  const initial = { etch: defaultSpec("etch"), ald: defaultSpec("ald") };
  try {
    const stored = JSON.parse(
      localStorage.getItem("process-studio.specs.v1") ?? "null",
    );
    if (stored)
      for (const model of ["etch", "ald"] as const)
        initial[model] = validateSpec(stored[model], model);
  } catch {
    /* Corrupt or unavailable browser storage falls back to labelled examples. */
  }
  return initial;
}

export function assessmentReport(
  run: Simulation,
  spec: ProcessSpec,
  baseline: AssessmentBaseline | null,
  userNotes: string,
) {
  const validated = validateSpec(spec, run.model);
  return {
    format: "process-studio-assessment-v1",
    assessment_version: ASSESSMENT_VERSION,
    assessed_at: new Date().toISOString(),
    spec: validated,
    scope:
      "Model-only screening of user requirements, not equipment qualification. Criteria are applied at review time, not frozen at run time.",
    run,
    assessment: evaluate(run.model, run.result, run.params, validated),
    baseline: baseline
      ? {
          ...baseline,
          assessment: evaluate(
            run.model,
            baseline.result,
            baseline.params,
            validated,
          ),
        }
      : null,
    user_notes: userNotes,
  };
}
