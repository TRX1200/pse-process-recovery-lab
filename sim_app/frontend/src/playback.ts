import type { ModelKey, ModelResult, Params, Series } from "./types";

/** Only a physical time axis may be revealed by the shared playback clock. */
export function isTimeSeries(series: Series): boolean {
  return series.x_label === "시간 (s)";
}

export function durationOf(result?: ModelResult): number {
  if (!result || result.effective.status === "outside_rate_fit") return 0;
  return Math.max(
    0,
    ...result.series
      .filter(isTimeSeries)
      .flatMap((s) => s.x)
      .filter(Number.isFinite),
  );
}

export function interpolate(
  x: number[],
  values: number[],
  time: number,
): number | null {
  if (!x.length || x.length !== values.length || !Number.isFinite(time))
    return null;
  if (time < x[0] || time > x[x.length - 1]) return null;
  let index = 0;
  while (index + 1 < x.length && x[index + 1] <= time) index++;
  const value = values[index];
  if (!Number.isFinite(value)) return null;
  if (index === x.length - 1 || x[index] === time) return value;
  const next = values[index + 1];
  const span = x[index + 1] - x[index];
  if (!Number.isFinite(next) || span <= 0) return null;
  return value + ((next - value) * (time - x[index])) / span;
}

export function valueAt(
  result: ModelResult | undefined,
  key: string,
  line: number,
  time: number,
): number | null {
  const series = result?.series.find((s) => s.key === key && isTimeSeries(s));
  return series && series.lines[line]
    ? interpolate(series.x, series.lines[line].values, time)
    : null;
}

/** Never fabricate geometry by scaling a final spatial profile with t / T. */
export function profileAt(
  result: ModelResult | undefined,
  time: number,
): number[] | undefined {
  const frames = result?.playback;
  if (
    !frames ||
    !frames.time_s.length ||
    frames.profiles_nm.length !== frames.time_s.length
  )
    return undefined;
  const count = frames.profiles_nm[0].length;
  if (frames.profiles_nm.some((frame) => frame.length !== count))
    return undefined;
  const values = Array.from({ length: count }, (_, index) =>
    interpolate(
      frames.time_s,
      frames.profiles_nm.map((frame) => frame[index]),
      time,
    ),
  );
  return values.some((value) => value === null)
    ? undefined
    : (values as number[]);
}

export function stageAt(
  model: ModelKey,
  params: Params,
  time: number,
  duration: number,
): { index: number; label: string } {
  if (duration <= 0) return { index: -1, label: "시간 구간 없음" };
  if (time >= duration)
    return {
      index: -1,
      label: model === "ald" ? "첫 사이클 완료" : "처리 완료",
    };
  if (model === "etch") return { index: 0, label: "정상 플라즈마 · 표면 처리" };
  let end = 0;
  const durations = [
    params.pulse_a_s,
    params.purge_a_s,
    params.pulse_b_s,
    params.purge_b_s,
  ];
  const labels = ["A 주입", "A 뒤 퍼지", "B 주입", "B 뒤 퍼지"];
  for (let index = 0; index < durations.length; index++) {
    end += durations[index];
    if (time < end) return { index, label: labels[index] };
  }
  return { index: -1, label: "첫 사이클 완료" };
}

export function advanceTime(
  time: number,
  elapsedSeconds: number,
  speed: number,
  duration: number,
): number {
  return Math.min(
    duration,
    Math.max(0, time + Math.max(0, elapsedSeconds) * speed),
  );
}
