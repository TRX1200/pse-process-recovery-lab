import { profileAt } from "./playback";
import type { ModelKey, ModelResult, Params } from "./types";

export interface SurfaceDomain {
  x: number[];
  xMin: number;
  xMax: number;
  endTime: number;
  maxNm: number;
  depthAxisNm: number;
  filmGain: number;
  gapNm: number;
}

function niceCeiling(value: number): number {
  const power = 10 ** Math.floor(Math.log10(value));
  return ([1, 2, 5, 10].find((factor) => factor * power >= value) ?? 10) * power;
}

/** Validate solved display frames once per run; never substitute an N-cycle projection. */
export function surfaceDomain(
  model: ModelKey,
  result: ModelResult,
  params: Params,
): SurfaceDomain | null {
  const frames = result.playback;
  const x = result.spatial.x;
  if (
    result.effective.status === "outside_rate_fit" ||
    result.spatial.kind !== model ||
    frames?.profile_basis !== (model === "ald" ? "first_cycle_growth" : "etch_depth") ||
    !frames.time_s.length ||
    frames.time_s[0] !== 0 ||
    frames.time_s.length !== frames.profiles_nm.length ||
    x.length < 2 ||
    x.some((v, i) => !Number.isFinite(v) || (i > 0 && v <= x[i - 1])) ||
    frames.time_s.some((v, i) => !Number.isFinite(v) || (i > 0 && v <= frames.time_s[i - 1]))
  ) return null;
  let maxNm = 0;
  for (const row of frames.profiles_nm) {
    if (row.length !== x.length) return null;
    for (const v of row) {
      // Tiny negative solver roundoff is hidden, not interpreted as deposition/removal.
      if (!Number.isFinite(v) || v < -1e-10) return null;
      maxNm = Math.max(maxNm, v);
    }
  }
  const gapNm = model === "ald" ? params.gap_um * 1000 : 0;
  const xMin = model === "ald" ? 0 : x[0];
  const xMax = model === "ald" ? params.depth_um : x[x.length - 1];
  if (!Number.isFinite(xMax) || xMax <= xMin ||
      (model === "ald" && (!Number.isFinite(gapNm) || gapNm <= 0 || x[0] <= 0 || x[x.length - 1] >= xMax))) return null;
  // Default recipes share 100x film magnification. Reduce only to keep the drawing open;
  // a gain below one is possible and never implies a simulated pinch-off event.
  const filmGain = model === "ald" && maxNm > 0 ? Math.min(100, gapNm * 0.28 / maxNm) : 100;
  return {
    x, xMin, xMax, gapNm, maxNm, filmGain,
    depthAxisNm: niceCeiling(Math.max(maxNm * 1.15, 1)),
    endTime: frames.time_s[frames.time_s.length - 1],
  };
}

export function surfaceFrame(result: ModelResult, domain: SurfaceDomain, time: number): number[] | null {
  if (!Number.isFinite(time) || time < 0 || time > domain.endTime) return null;
  const values = profileAt(result, time);
  if (!values || values.length !== domain.x.length || values.some((v) => !Number.isFinite(v) || v < -1e-10)) return null;
  return values.map((v) => Math.max(0, v));
}

/** Finite-volume ALD values live at cell centres; extend each to its cell faces. */
export function cellEdges(domain: SurfaceDomain): number[] {
  return [domain.xMin, ...domain.x.slice(1).map((v, i) => (v + domain.x[i]) / 2), domain.xMax];
}
