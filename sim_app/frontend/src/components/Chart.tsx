import { axisTick } from "../storage";
import { interpolate } from "../playback";
import { useId } from "react";
import type { Series } from "../types";

const COLORS = ["#344b5b", "#ae492f", "#728d9c", "#997849"];

function pathData(
  x: number[],
  values: number[],
  px: (x: number) => number,
  py: (y: number) => number,
): string {
  let connected = false;
  return values
    .map((value, index) => {
      if (!Number.isFinite(value) || !Number.isFinite(x[index])) {
        connected = false;
        return "";
      }
      const command = connected ? "L" : "M";
      connected = true;
      return `${command}${px(x[index]).toFixed(2)},${py(value).toFixed(2)}`;
    })
    .join(" ");
}

export function Chart({
  series,
  baseline,
  compact = false,
  time,
  staticLabel = false,
}: {
  series: Series;
  baseline?: Series;
  compact?: boolean;
  time?: number | null;
  staticLabel?: boolean | string;
}) {
  const clipId = useId().replaceAll(":", "");
  const width = 600;
  const height = compact ? 235 : 275;
  const pad = { left: 68, right: 18, top: 18, bottom: 52 };
  const datasets = [
    ...series.lines.map((line, index) => ({
      ...line,
      x: series.x,
      color: COLORS[index % COLORS.length],
      baseline: false,
    })),
    ...(baseline?.lines.map((line, index) => ({
      ...line,
      x: baseline.x,
      color: COLORS[index % COLORS.length],
      baseline: true,
    })) ?? []),
  ];
  const xs = datasets.flatMap((line) => line.x).filter(Number.isFinite);
  const ys = datasets.flatMap((line) => line.values).filter(Number.isFinite);
  if (!xs.length || !ys.length)
    return (
      <section className="plot">
        <h3>{series.title}</h3>
        <p className="muted">표시할 계산 결과가 없습니다.</p>
      </section>
    );
  const xMin = Math.min(...xs);
  const xMax = Math.max(...xs);
  const dataYMin = Math.min(...ys);
  const dataYMax = Math.max(...ys);
  const ySpan = dataYMax - dataYMin || Math.abs(dataYMax) * 0.2 || 1;
  // Use a zero baseline for nonnegative physical responses so a saturated,
  // nearly constant signal cannot be visually exaggerated by automatic zoom.
  const yMin = dataYMin >= 0 ? 0 : dataYMin - ySpan * 0.08;
  const yMax =
    dataYMax + Math.max(ySpan * 0.1, Math.abs(dataYMax) * 0.05, 1e-15);
  const px = (x: number) =>
    pad.left +
    ((x - xMin) / (xMax - xMin || 1)) * (width - pad.left - pad.right);
  const py = (y: number) =>
    height -
    pad.bottom -
    ((y - yMin) / (yMax - yMin)) * (height - pad.top - pad.bottom);
  return (
    <section className="plot">
      <div className="plot-heading">
        <h3>{series.title}</h3>
        <div className="plot-legend">
          {series.lines.map((line, index) => (
            <span key={line.name}>
              <i style={{ background: COLORS[index % COLORS.length] }} />
              {line.name}
            </span>
          ))}
          {baseline && <span className="baseline-legend">--- 정상 기준</span>}
        </div>
      </div>
      {staticLabel && (
        <span className="static-plot-label">
          {typeof staticLabel==='string'?staticLabel:'종점 / 조건 곡선 · 시간축 아님'}
        </span>
      )}
      <svg
        className="chart-svg"
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={`${series.title}. 가로축 ${series.x_label}, 세로축 ${series.y_label}`}
      >
        <defs>
          <clipPath id={clipId}>
            <rect
              x={pad.left - 2}
              y={pad.top - 4}
              width={
                time == null
                  ? width
                  : Math.max(
                      0,
                      Math.min(width - pad.right, px(time)) - pad.left,
                    ) + 2
              }
              height={height - pad.bottom - pad.top + 8}
            />
          </clipPath>
        </defs>
        {Array.from({ length: 5 }, (_, index) => {
          const x = xMin + ((xMax - xMin) * index) / 4;
          const y = yMin + ((yMax - yMin) * index) / 4;
          return (
            <g key={index}>
              <line
                className="grid-line"
                x1={pad.left}
                y1={py(y)}
                x2={width - pad.right}
                y2={py(y)}
              />
              <line
                className="grid-line"
                x1={px(x)}
                y1={pad.top}
                x2={px(x)}
                y2={height - pad.bottom}
              />
              <text
                className="axis-tick"
                x={pad.left - 9}
                y={py(y) + 4}
                textAnchor="end"
              >
                {axisTick(y, (yMax - yMin) / 4)}
              </text>
              <text
                className="axis-tick"
                x={px(x)}
                y={height - pad.bottom + 20}
                textAnchor="middle"
              >
                {axisTick(x, (xMax - xMin) / 4)}
              </text>
            </g>
          );
        })}
        <line
          className="axis-line"
          x1={pad.left}
          y1={height - pad.bottom}
          x2={width - pad.right}
          y2={height - pad.bottom}
        />
        {datasets.map((line, index) => (
          <g key={`${line.name}-${index}`} clipPath={`url(#${clipId})`}>
            <path
              d={pathData(line.x, line.values, px, py)}
              fill="none"
              stroke={line.color}
              strokeWidth={line.baseline ? 1.7 : 2.6}
              strokeDasharray={
                line.baseline ? "7 5" : index === 2 ? "3 4" : undefined
              }
              opacity={line.baseline ? 0.55 : 1}
              strokeLinejoin="round"
            >
              <title>
                {line.name}
                {line.baseline ? " · 정상 기준" : ""}
              </title>
            </path>
            {line.values.length <= 21
              ? line.values.map((value, i) =>
                  Number.isFinite(value) && Number.isFinite(line.x[i]) ? (
                    <circle
                      key={i}
                      cx={px(line.x[i])}
                      cy={py(value)}
                      r="3"
                      fill={line.color}
                    >
                      <title>
                        {line.x[i]}: {value}
                      </title>
                    </circle>
                  ) : null,
                )
              : null}
          </g>
        ))}
        {time != null && time >= xMin && time <= xMax && (
          <g className="time-cursor">
            <line
              x1={px(time)}
              x2={px(time)}
              y1={pad.top}
              y2={height - pad.bottom}
              stroke="#ae492f"
              strokeWidth="1.4"
              strokeDasharray="3 4"
            />
            {datasets.map((line, index) => {
              const value = interpolate(line.x, line.values, time);
              return value === null ? null : (
                <circle
                  key={index}
                  cx={px(time)}
                  cy={py(value)}
                  r={line.baseline ? 3 : 4}
                  fill={line.color}
                  stroke="white"
                  strokeWidth="1.5"
                  opacity={line.baseline ? 0.6 : 1}
                >
                  <title>
                    {line.name}: {value}
                  </title>
                </circle>
              );
            })}
          </g>
        )}
        <text
          className="axis-label"
          x={(width + pad.left) / 2}
          y={height - 8}
          textAnchor="middle"
        >
          {series.x_label}
        </text>
        <text
          className="axis-label"
          transform={`translate(15 ${(height - pad.bottom) / 2}) rotate(-90)`}
          textAnchor="middle"
        >
          {series.y_label}
        </text>
      </svg>
    </section>
  );
}
