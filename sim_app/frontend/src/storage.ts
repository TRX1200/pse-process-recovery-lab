import type { ModelSchema, Params, Recipe, Schema, Simulation } from "./types";

const RECIPE_KEY = "process-studio.recipes.v1";
const RUN_KEY = "process-studio.runs.v1";

export function defaults(schema: ModelSchema): Params {
  return Object.fromEntries(
    schema.params.map((parameter) => [parameter.key, parameter.default]),
  );
}

export function validateRecipe(value: unknown, schema: Schema): Recipe {
  if (!value || typeof value !== "object")
    throw new Error("레시피 JSON 객체가 필요합니다.");
  const recipe = value as Partial<Recipe>;
  if (recipe.format !== "process-studio-recipe-v1")
    throw new Error("지원하지 않는 레시피 형식입니다.");
  if (recipe.model !== "ald" && recipe.model !== "etch")
    throw new Error("ALD 또는 Etch 모델을 선택해 주세요.");
  if (!recipe.params || typeof recipe.params !== "object")
    throw new Error("레시피에 params가 없습니다.");
  const model = schema.models[recipe.model];
  const known = new Set(model.params.map((parameter) => parameter.key));
  if (Object.keys(recipe.params).some((key) => !known.has(key)))
    throw new Error("레시피에 지원하지 않는 파라미터가 있습니다.");
  const params: Params = {};
  for (const parameter of model.params) {
    const value = recipe.params[parameter.key];
    if (
      !Number.isFinite(value) ||
      value < parameter.min ||
      value > parameter.max
    ) {
      throw new Error(
        `${parameter.label}: ${parameter.min}–${parameter.max} ${parameter.unit} 범위의 값이 필요합니다.`,
      );
    }
    params[parameter.key] = value;
  }
  if (recipe.model === "ald" && !Number.isInteger(params.cycles))
    throw new Error("ALD 반복 횟수는 정수여야 합니다.");
  if (!model.faults.some((fault) => fault.id === recipe.fault))
    throw new Error("알 수 없는 고장 시나리오입니다.");
  return {
    format: "process-studio-recipe-v1",
    name: String(recipe.name || "Imported recipe").slice(0, 100),
    model: recipe.model,
    params,
    fault: recipe.fault!,
  };
}

export function loadRecipes(): Recipe[] {
  try {
    const stored: unknown = JSON.parse(
      localStorage.getItem(RECIPE_KEY) ?? "[]",
    );
    return Array.isArray(stored)
      ? stored
          .filter((r) => r?.format === "process-studio-recipe-v1")
          .slice(0, 20)
      : [];
  } catch {
    return [];
  }
}

export function loadRuns(): Simulation[] {
  try {
    const stored: unknown = JSON.parse(localStorage.getItem(RUN_KEY) ?? "[]");
    return Array.isArray(stored)
      ? stored
          .filter(
            (run) =>
              typeof run?.run_id === "string" &&
              Array.isArray(run?.result?.metrics),
          )
          .slice(0, 10)
      : [];
  } catch {
    return [];
  }
}

export function saveRecipes(recipes: Recipe[]): void {
  localStorage.setItem(RECIPE_KEY, JSON.stringify(recipes.slice(0, 20)));
}

export function saveRuns(runs: Simulation[]): void {
  localStorage.setItem(RUN_KEY, JSON.stringify(runs.slice(0, 10)));
}

export function download(name: string, content: string, type: string): void {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function exportJson(name: string, data: unknown): void {
  download(name, JSON.stringify(data, null, 2), "application/json");
}

function csvCell(value: unknown): string {
  return `"${String(value ?? "").replaceAll('"', '""')}"`;
}

export function exportRunCsv(run: Simulation): void {
  const rows: unknown[][] = [
    [
      "run_id",
      "model",
      "model_version",
      "fault",
      "type",
      "key",
      "line",
      "x",
      "value",
      "x_unit_or_label",
      "y_unit_or_label",
      "validity",
    ],
  ];
  for (const [kind, result] of [
    ["result", run.result],
    ["baseline", run.baseline],
  ] as const) {
    if (!result) continue;
    const provenance = [
      run.run_id,
      run.model,
      result.model_version,
      kind === "baseline" ? "none" : run.fault,
    ];
    const outside = result.effective.status === "outside_rate_fit";
    result.metrics.forEach((metric) => {
      const validity = metricValidity(
        metric.key,
        result.metrics,
        result.effective,
      );
      rows.push([
        ...provenance,
        `${kind}_metric`,
        metric.key,
        "",
        "",
        validity === "valid" ? metric.value : "",
        "",
        metric.unit,
        validity,
      ]);
    });
    result.series.forEach((series) =>
      series.lines.forEach((line) =>
        series.x.forEach((x, index) => {
          rows.push([
            ...provenance,
            `${kind}_series`,
            series.key,
            line.name,
            x,
            outside ? "" : line.values[index],
            series.x_label,
            series.y_label,
            outside ? "outside_rate_fit" : "valid",
          ]);
        }),
      ),
    );
  }
  download(
    `${run.run_id}.csv`,
    "\uFEFF" + rows.map((row) => row.map(csvCell).join(",")).join("\r\n"),
    "text/csv;charset=utf-8",
  );
}

export function metricValidity(
  key: string,
  metrics: { key: string; value: number }[],
  effective: Record<string, unknown>,
): "valid" | "outside_rate_fit" | "undefined_ratio" | "no_growth" {
  if (effective.status === "outside_rate_fit") return "outside_rate_fit";
  if (key === "selectivity" && effective.selectivity_defined === false)
    return "undefined_ratio";
  if (
    key === "conformality_pct" &&
    (metrics.find((metric) => metric.key === "top_thickness_nm")?.value ?? 1) <
      1e-12
  )
    return "no_growth";
  return "valid";
}

export function metricNumber(value: number, digits = 2): string {
  if (!Number.isFinite(value)) return "—";
  if (Math.abs(value) >= 1e5 || (value !== 0 && Math.abs(value) < 0.001))
    return value.toExponential(Math.min(digits, 2));
  return value.toLocaleString("en-US", { maximumFractionDigits: digits });
}

export function comparisonLabel(
  value: number,
  reference: number,
  unit: string,
): string {
  // Display-only threshold in the metric's reported unit; it does not modify model outputs.
  // A near-zero denominator makes percentages numerically large but physically unhelpful.
  const absolute = value - reference;
  if (Math.abs(reference) < 1e-6)
    return `Δ ${absolute > 0 ? "+" : ""}${metricNumber(absolute, 3)} ${unit} · 기준≈0`;
  const percent = (100 * absolute) / Math.abs(reference);
  return `${percent > 0 ? "+" : ""}${metricNumber(percent, 1)}% vs baseline`;
}

export function axisTick(value: number, step: number): string {
  if (!Number.isFinite(value)) return "—";
  if (value === 0) return "0";
  const magnitude = Math.abs(value);
  const safeStep = Math.max(Math.abs(step), Number.MIN_VALUE);
  if (magnitude >= 1e6 || magnitude < 1e-3) {
    const digits = Math.max(
      0,
      Math.min(9, Math.ceil(Math.log10(magnitude) - Math.log10(safeStep)) + 1),
    );
    return value.toExponential(digits);
  }
  const digits = Math.max(
    0,
    Math.min(10, -Math.floor(Math.log10(safeStep)) + 1),
  );
  return value.toLocaleString("en-US", { maximumFractionDigits: digits });
}
