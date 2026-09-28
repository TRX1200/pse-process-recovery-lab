import { useId } from "react";
import { metricNumber } from "../storage";
import type { ModelKey, ModelResult, Params } from "../types";
import { durationOf, profileAt, stageAt, valueAt } from "../playback";

export function Reactor({
  model,
  result,
  params,
  time = null,
  motion = 0,
  playing = false,
}: {
  model: ModelKey;
  result?: ModelResult;
  params: Params;
  time?: number | null;
  motion?: number;
  playing?: boolean;
}) {
  const prefix = useId().replaceAll(":", "");
  const density =
    result?.metrics.find((metric) => metric.key === "electron_density_m3")
      ?.value ?? 0;
  const glow =
    density > 0
      ? Math.max(0.15, Math.min(0.95, (Math.log10(density) - 13) / 5))
      : 0;
  const profile = result?.spatial;
  const currentTime = time ?? durationOf(result);
  const values =
    (time === null
      ? profile?.values
      : (profileAt(result, currentTime) ?? profile?.values)) ?? [];
  const reference =
    time === null
      ? profile?.values
      : (result?.playback?.profiles_nm.at(-1) ?? profile?.values);
  const max = reference ? Math.max(...reference, 1e-9) : 1;
  const stage = stageAt(model, params, currentTime, durationOf(result));
  const pressureA = valueAt(result, "pressure", 0, currentTime) ?? 0;
  const pressureB = valueAt(result, "pressure", 1, currentTime) ?? 0;
  const pressureScale = Math.max(
    params.pressure_a_pa || 0,
    params.pressure_b_pa || 0,
    1,
  );
  // Decorative motion runs in wall-clock seconds, independently of playback speed.
  // The model's ne and Te stay at their steady values; no artificial startup ramp.
  const shimmer =
    0.88 +
    0.08 * Math.sin(motion * Math.PI * 1.1) +
    0.04 * Math.sin(motion * Math.PI * 2.3);
  const points = values
    .map(
      (value, index) =>
        `${215 + (index / Math.max(1, values.length - 1)) * 190},${294 + (value / max) * 16}`,
    )
    .join(" ");
  const stages = [
    params.pulse_a_s,
    params.purge_a_s,
    params.pulse_b_s,
    params.purge_b_s,
  ];
  const total = stages.reduce((a, b) => a + b, 0);
  return (
    <section
      className={`reactor-view ${model}`}
      aria-label={
        model === "ald" ? "ALD reactor schematic" : "Plasma reactor schematic"
      }
    >
      <div className="schematic-label">
        <span className="tiny-dot" />
        {model === "ald"
          ? "Thermal ALD · 1D channel"
          : "Global plasma · reduced order"}
        <span>{playing ? "● 재생 중 · " : ""}개념도 · 축척 아님</span>
      </div>
      <svg
        className="reactor-svg"
        viewBox="0 0 630 400"
        role="img"
        aria-label={
          model === "ald"
            ? "전구체 공급 챔버와 평행 평판 채널의 계산 두께 개념도"
            : "전자 밀도에 따른 플라즈마 밝기와 웨이퍼 표면 식각량 개념도. 입자 궤적은 풀이 결과가 아닌 방향 표시입니다."
        }
      >
        <defs>
          <linearGradient id={`${prefix}-metal`} x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stopColor="#aeb9c4" />
            <stop offset="0.12" stopColor="#e4e9ee" />
            <stop offset="0.36" stopColor="#8997a7" />
            <stop offset="0.5" stopColor="#e4e9ee" />
            <stop offset="0.8" stopColor="#aab6c2" />
            <stop offset="1" stopColor="#708094" />
          </linearGradient>
          <linearGradient id={`${prefix}-glass`} x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stopColor="#d4dfe8" stopOpacity="0.7" />
            <stop offset="0.4" stopColor="#f8fafc" stopOpacity="0.3" />
            <stop offset="1" stopColor="#bac8d8" stopOpacity="0.7" />
          </linearGradient>
          <radialGradient id={`${prefix}-plasma`}>
            <stop offset="0" stopColor="#d6b5ff" />
            <stop offset="0.45" stopColor="#aa80eb" />
            <stop offset="1" stopColor="#885dd0" stopOpacity="0" />
          </radialGradient>
          <linearGradient id={`${prefix}-wafer`} x1="0" y1="0" x2="0" y2="1">
            <stop
              offset="0"
              stopColor={model === "ald" ? "#aadbdc" : "#d1c1f5"}
            />
            <stop
              offset="1"
              stopColor={model === "ald" ? "#298e96" : "#9380c0"}
            />
          </linearGradient>
          <marker
            id={`${prefix}-arrow`}
            markerWidth="6"
            markerHeight="6"
            refX="3"
            refY="3"
            orient="auto"
          >
            <path
              d="M0 0L6 3L0 6Z"
              fill={model === "ald" ? "#4ba7ac" : "#b08adb"}
            />
          </marker>
          <clipPath id={`${prefix}-chamber`}>
            <rect x="176" y="116" width="278" height="202" rx="6" />
          </clipPath>
        </defs>
        <ellipse cx="315" cy="361" rx="159" ry="18" fill="#edf1f5" />
        <path
          d="M177 121V311Q177 343 315 343Q454 343 454 311V121"
          fill={`url(#${prefix}-metal)`}
          stroke="#718093"
          strokeWidth="1.3"
        />
        <path
          d="M192 121V308Q192 330 315 330Q439 330 439 308V121"
          fill={`url(#${prefix}-glass)`}
          stroke="#91a1b3"
        />
        <g clipPath={`url(#${prefix}-chamber)`}>
          {model === "etch" ? (
            <>
              <ellipse
                cx="315"
                cy="215"
                rx="145"
                ry="105"
                fill={`url(#${prefix}-plasma)`}
                opacity={glow * shimmer}
                transform={`translate(${Math.sin(motion * 1.7) * 7} ${Math.cos(motion * 1.2) * 3})`}
              />
              {density > 0 && (
                <>
                  <ellipse
                    cx={305 + Math.sin(motion * 1.3) * 14}
                    cy="219"
                    rx="93"
                    ry="67"
                    fill={`url(#${prefix}-plasma)`}
                    opacity={glow * 0.45}
                  />
                  {Array.from({ length: 24 }, (_, index) => (
                    <circle
                      key={`moving-${index}`}
                      cx={
                        211 +
                        ((index * 37) % 211) +
                        Math.sin(motion * 2 + index) * 5
                      }
                      cy={
                        141 +
                        ((motion * (26 + (index % 5) * 4) + index * 19) % 157)
                      }
                      r={index % 3 === 0 ? 2.4 : 1.4}
                      fill={index % 3 === 0 ? "#f8edff" : "#dcc8ff"}
                      opacity={glow * 0.9}
                    />
                  ))}
                </>
              )}
              {result && density > 0
                ? Array.from({ length: 7 }, (_, index) => (
                    <g key={index} opacity="0.8">
                      <circle
                        cx={224 + index * 30}
                        cy={178 + (index % 2) * 26}
                        r="6"
                        fill="none"
                        stroke="#956bc7"
                      />
                      <path
                        d={`M${224 + index * 30} ${174 + (index % 2) * 26}v8m-4 -4h8`}
                        stroke="#956bc7"
                        strokeWidth="1"
                      />
                      <path
                        d={`M${224 + index * 30} ${192 + (index % 2) * 26}L${228 + index * 28} 285`}
                        stroke="#a782cf"
                        strokeWidth="1.1"
                        strokeDasharray="4 5"
                        strokeDashoffset={-motion * 12}
                        markerEnd={`url(#${prefix}-arrow)`}
                      />
                    </g>
                  ))
                : null}
            </>
          ) : (
            <>
              <ellipse
                cx="287"
                cy="198"
                rx="100"
                ry="73"
                fill="#49c1c6"
                opacity={Math.min(0.4, (pressureA / pressureScale) * 0.4)}
              />
              <ellipse
                cx="346"
                cy="202"
                rx="100"
                ry="74"
                fill="#a980df"
                opacity={Math.min(0.4, (pressureB / pressureScale) * 0.4)}
              />
              {[pressureA, pressureB].map((pressure, kind) =>
                pressure > 1e-6
                  ? Array.from({ length: 10 }, (_, index) => (
                      <circle
                        key={`${kind}-${index}`}
                        cx={
                          224 + index * 20 + Math.sin(motion * 1.4 + index) * 5
                        }
                        cy={
                          145 + ((motion * 25 + index * 17 + kind * 29) % 126)
                        }
                        r="2"
                        fill={kind ? "#9067c7" : "#139da5"}
                        opacity={Math.min(0.85, pressure / pressureScale)}
                      />
                    ))
                  : null,
              )}
              <path
                d="M270 128V160M315 128V169M360 128V160"
                stroke="#60a8aa"
                strokeWidth="2"
                strokeDasharray="4 7"
                markerEnd={`url(#${prefix}-arrow)`}
              />
              <rect
                x="228"
                y="190"
                width="174"
                height="90"
                rx="5"
                fill="#e9eef2"
                stroke="#94a4b3"
              />
              <rect
                x="241"
                y="201"
                width="146"
                height="14"
                rx="2"
                fill="#fff"
                stroke="#95a7b2"
              />
              {values
                ? values.map((value, index) => (
                    <rect
                      key={index}
                      x={241 + (index / values.length) * 142}
                      y="202"
                      width={142 / values.length + 0.1}
                      height={Math.max(0, (value / max) * 5)}
                      fill="#009aa1"
                    />
                  ))
                : null}
              <path
                d="M205 209H233"
                stroke="#008b95"
                strokeWidth="2"
                markerEnd={`url(#${prefix}-arrow)`}
              />
              <text
                x="315"
                y="241"
                textAnchor="middle"
                className="reactor-small"
              >
                1D slit channel
              </text>
              <text
                x="315"
                y="259"
                textAnchor="middle"
                className="reactor-small"
              >
                L = {params.depth_um} µm · h = {params.gap_um} µm
              </text>
            </>
          )}
        </g>
        <ellipse
          cx="315"
          cy="121"
          rx="139"
          ry="30"
          fill={`url(#${prefix}-metal)`}
          stroke="#718093"
          strokeWidth="1.5"
        />
        <ellipse
          cx="315"
          cy="121"
          rx="116"
          ry="19"
          fill="#dce4ec"
          stroke="#9ba9b8"
        />
        {model === "etch" ? (
          <g>
            {[0, 1, 2, 3].map((index) => (
              <ellipse
                key={index}
                cx="315"
                cy={73 + index * 10}
                rx="77"
                ry="13"
                fill="none"
                stroke={index % 2 ? "#8d6bbc" : "#8b95a4"}
                strokeWidth="5"
              />
            ))}
            <path d="M241 73V106M390 72V110" stroke="#7f8c9d" strokeWidth="5" />
          </g>
        ) : (
          <g>
            <path
              d="M283 50V108M347 50V108"
              stroke="#8b99a7"
              strokeWidth="12"
            />
            <path d="M283 50V108" stroke="#23a1a6" strokeWidth="4" />
            <path d="M347 50V108" stroke="#9876c8" strokeWidth="4" />
            <rect x="269" y="65" width="28" height="19" rx="4" fill="#008b95" />
            <rect x="333" y="65" width="28" height="19" rx="4" fill="#9876c8" />
            <text x="283" y="39" textAnchor="middle" className="reactor-small">
              A
            </text>
            <text x="347" y="39" textAnchor="middle" className="reactor-small">
              B
            </text>
          </g>
        )}
        <path
          d="M277 332V351Q315 363 353 351V332"
          fill={`url(#${prefix}-metal)`}
          stroke="#8795a5"
        />
        <ellipse
          cx="315"
          cy="309"
          rx="110"
          ry="24"
          fill={`url(#${prefix}-metal)`}
          stroke="#718093"
        />
        <ellipse
          cx="315"
          cy="302"
          rx="99"
          ry="19"
          fill={`url(#${prefix}-wafer)`}
          stroke="#7d80a4"
        />
        {model === "etch" && points ? (
          <polyline
            points={points}
            fill="none"
            stroke="#625182"
            strokeWidth="1.5"
          />
        ) : null}
        <path
          d="M442 316H478V349"
          fill="none"
          stroke="#8897a7"
          strokeWidth="10"
        />
        <path
          d="M442 316H478V349"
          fill="none"
          stroke="#dfe5eb"
          strokeWidth="6"
        />
        <g className="reactor-annotations">
          <path d="M84 95H202L234 79" />
          <circle cx="234" cy="79" r="3" />
          <text x="22" y="73">
            {model === "etch" ? "RF source" : "Precursor delivery"}
          </text>
          <text x="22" y="90" className="annotation-value">
            {model === "etch"
              ? `${params.source_power_w} W`
              : `${params.pressure_a_pa} / ${params.pressure_b_pa} Pa`}
          </text>
          <path d="M452 160H494L510 145" />
          <circle cx="452" cy="160" r="3" />
          <text x="499" y="121">
            {model === "etch" ? "Plasma state" : "Temperature"}
          </text>
          <text x="499" y="138" className="annotation-value">
            {model === "etch"
              ? result
                ? `${metricNumber(density)} m⁻³`
                : "Awaiting run"
              : `${result?.effective.temperature_c ?? params.temperature_c} °C`}
          </text>
          <path d="M80 219H168L200 210" />
          <circle cx="200" cy="210" r="3" />
          <text x="22" y="197">
            {model === "etch" ? "e⁻ / ions" : "Surface reaction"}
          </text>
          <text x="22" y="214" className="annotation-muted">
            {model === "etch" ? "Global-state model" : "Adsorption + diffusion"}
          </text>
          <path d="M85 311H205" />
          <circle cx="205" cy="311" r="3" />
          <text x="22" y="293">
            {model === "etch" ? "Wafer response" : "Heated substrate"}
          </text>
          <text x="493" y="323">
            Pump
          </text>
        </g>
      </svg>
      {model === "ald" && total > 0 ? (
        <div className="pulse-timeline" aria-label="ALD recipe stages">
          {stages.map((duration, index) => (
            <div
              key={index}
              style={{ flexGrow: Math.max(duration, 0.1) }}
              className={`${index % 2 ? "purge-stage" : `pulse-stage pulse-${index}`} ${time !== null && stage.index === index ? "current-stage" : ""}`}
            >
              <span>{["A pulse", "Purge", "B pulse", "Purge"][index]}</span>
              <b>{duration} s</b>
            </div>
          ))}
        </div>
      ) : (
        <div className="schematic-footnote">
          밀도는 정상상태 계산 · 일렁임·입자 이동은 연출 · RF 진동 해석 아님
        </div>
      )}
      {model === "ald" && (
        <div className="schematic-footnote">
          {time === null
            ? "채널 막: 첫 사이클 × N 투영 두께"
            : "채널 막: 현재 t의 첫 사이클 성장 · 기체 색: 계산 분압 · 입자 이동은 연출"}
        </div>
      )}
    </section>
  );
}
