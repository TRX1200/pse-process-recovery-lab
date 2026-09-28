export type ModelKey = "ald" | "etch";
export type Params = Record<string, number>;

export interface Parameter {
  key: string;
  label: string;
  unit: string;
  min: number;
  max: number;
  step: number;
  default: number;
  group: string;
  description: string;
}

export interface Fault {
  id: string;
  label: string;
  description: string;
}

export interface ModelSchema {
  label: string;
  params: Parameter[];
  faults: Fault[];
  model_version: string;
}

export interface Schema {
  models: Record<ModelKey, ModelSchema>;
}

export interface Metric {
  key: string;
  label: string;
  value: number;
  unit: string;
  digits: number;
}

export interface Series {
  key: string;
  title: string;
  x_label: string;
  y_label: string;
  x: number[];
  lines: Array<{ name: string; values: number[] }>;
}

export interface ModelResult {
  model_version: string;
  metrics: Metric[];
  series: Series[];
  spatial: { kind: ModelKey; x: number[]; values: number[]; unit: string };
  diagnostics: Array<{ level: "info" | "warning"; message: string }>;
  assumptions: string[];
  effective: Record<string, unknown>;
}

export interface Simulation {
  run_id: string;
  created_at: string;
  model: ModelKey;
  params: Params;
  fault: string;
  result: ModelResult;
  baseline: ModelResult | null;
}

export interface Recipe {
  format: "process-studio-recipe-v1";
  name: string;
  model: ModelKey;
  params: Params;
  fault: string;
}

export interface Sweep {
  parameter: string;
  unit: string;
  runs: Array<{
    input: number;
    metrics: Metric[];
    effective: Record<string, unknown>;
    diagnostics: Array<{ level: string; message: string }>;
  }>;
}
