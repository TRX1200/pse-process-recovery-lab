import type { ModelKey, Params } from "./types";

export interface NativeParameter {
  key: string; label: string; unit: string; default: number; min: number; max: number;
  group: string; description: string; integer: boolean;
}
export interface NativeSchema {
  version: string;
  models: Record<ModelKey, { label: string; engine: string; params: NativeParameter[] }>;
  sources: { title: string; url: string }[];
}
export type Contour = number[][];
export interface NativeFrame {
  at: number; label: string;
  layers: { material: string; paths_nm: Contour[] }[];
  metrics: Record<string, number>;
}
export interface NativeRun {
  format: "native-feature-run-v1";
  model: ModelKey; run_hash: string; params: Params;
  environment: Record<string, string | number>;
  implementation: string; numerics: Record<string, unknown>;
  frames: NativeFrame[]; axis_unit: "s" | "cycle"; elapsed_s: number;
  warnings: string[]; assumptions: string[];
  sources: { title: string; url: string }[];
  validation: Record<string, string>;
}
export interface NativeJob {
  id: string; model: ModelKey; state: "queued" | "running" | "complete" | "failed" | "cancelled";
  progress: number; elapsed_s?: number; error?: string; last_frame?: NativeFrame; initial_frame?: NativeFrame;
  result_sha256?: string;
}

export const GROUP_NAMES: Record<string, string> = {
  geometry: "구조", recipe: "공정 조건", boundary: "입사 경계조건",
  kinetics: "표면 반응 계수", numerics: "수치 해석 설정",
};
export const NATIVE_METRICS: Record<string, [string, string]> = {
  center_depth_nm: ["중앙 식각 깊이", "nm"], width_half_depth_nm: ["절반 깊이의 폭", "nm"],
  mask_loss_nm: ["마스크 손실", "nm"], top_film_nm: ["상단 막 두께", "nm"],
  bottom_film_nm: ["바닥 막 두께", "nm"], bottom_top_pct: ["바닥 / 상단", "%"],
  mid_gap_nm: ["중간 깊이의 통로", "nm"], minimum_gap_nm: ["샘플 위치 최소 통로", "nm"],
};
export const isLocalWorkbench = () => ["127.0.0.1", "localhost"].includes(window.location.hostname);
export async function nativeRequest<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api/native/${path}`, body === undefined ? undefined : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(data?.error ?? `Native API ${response.status}`);
  }
  return response.json() as Promise<T>;
}
export async function publicNativeJson<T>(name: string): Promise<T> {
  const response = await fetch(`${import.meta.env.BASE_URL}native/${name}.json`);
  if (!response.ok) throw new Error("저장된 예제를 불러오지 못했습니다.");
  return response.json() as Promise<T>;
}
export function defaultNativeParams(schema: NativeSchema, model: ModelKey): Params {
  return Object.fromEntries(schema.models[model].params.map(p => [p.key, p.default]));
}
export function compatibleGeometry(a: NativeRun, b: NativeRun): boolean {
  return a.model === b.model && ["pitch_nm", "width_nm", a.model === "ald" ? "depth_nm" : "mask_nm"]
    .every(key => a.params[key] === b.params[key]);
}
export function extentOf(frames: NativeFrame[], pitch: number): [number, number, number, number] {
  let low = 0, high = 0;
  for (const frame of frames) for (const layer of frame.layers) for (const path of layer.paths_nm)
    for (const [, y] of path) { low = Math.min(low, y); high = Math.max(high, y); }
  const margin = Math.max(20, (high - low) * .1);
  return [-pitch / 2, pitch / 2, low - margin, high + margin];
}

export function contourPath(paths: Contour[], x: (n: number) => number, y: (n: number) => number,
  bottom: number, fill: boolean): string {
  return paths.filter(p => p.length > 1).map(path => {
    const first = path[0], last = path[path.length - 1];
    const closed = Math.hypot(first[0] - last[0], first[1] - last[1]) < 1e-6;
    const d = path.map(([px, py], i) => `${i ? "L" : "M"}${x(px).toFixed(3)},${y(py).toFixed(3)}`).join(" ");
    return d + (closed ? " Z" : fill ? ` L${x(last[0])},${y(bottom)} L${x(first[0])},${y(bottom)} Z` : "");
  }).join(" ");
}
