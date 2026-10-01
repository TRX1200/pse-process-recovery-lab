import { useMemo, useRef } from "react";
import { Download } from "lucide-react";
import { download, metricNumber } from "../storage";
import { cellEdges, surfaceDomain, surfaceFrame } from "../surface";
import { durationOf, stageAt } from "../playback";
import type { Simulation } from "../types";

const INK = "#26333b";
const MUTED = "#62717b";
const FILM = "#16827f";
const ETCH = "#ae492f";
const LEFT = 90;
const RIGHT = 820;
const TOP = 98;
const BOTTOM = 272;
const fmt = (v: number) => metricNumber(v, 4);

export function SurfaceSection({ run, time }: { run: Simulation; time: number | null }) {
  const { model, result, params } = run;
  const svg = useRef<SVGSVGElement>(null);
  const domain = useMemo(() => surfaceDomain(model, result, params), [model, result, params]);
  const currentTime = time ?? durationOf(result);
  const values = domain ? surfaceFrame(result, domain, currentTime) : null;
  if (!domain || !values) return (
    <section className="surface-panel" aria-label="표면 변화">
      <h2>표면 변화</h2>
      <p>이 실행에는 표시 가능한 시간별 표면 데이터가 없습니다. 레시피를 다시 계산해 주세요.</p>
    </section>
  );
  const ald = model === "ald";
  const middle = Math.floor(values.length / 2);
  const xPx = (x: number) => LEFT + (x - domain.xMin) / (domain.xMax - domain.xMin) * (RIGHT - LEFT);
  const yPx = (depth: number) => TOP + depth / domain.depthAxisNm * (BOTTOM - TOP);
  const edges = cellEdges(domain);
  const line = values.map((v, i) => `${xPx(domain.x[i]).toFixed(2)},${yPx(v).toFixed(2)}`).join(" ");
  const stage = stageAt(model, params, currentTime, domain.endTime);
  const probes = ald
    ? [{ label: "입구 쪽 셀", index: 0 }, { label: "깊은 곳 셀", index: values.length - 1 }]
    : [{ label: "왼쪽 가장자리", index: 0 }, { label: "웨이퍼 중심", index: middle }, { label: "오른쪽 가장자리", index: values.length - 1 }];
  const description = ald
    ? "첫 사이클의 계산된 막 두께를 채널 양쪽 벽에 표시합니다. 막 두께는 확대했고 채널 길이와 간격은 서로 다른 축척입니다."
    : "처음 평평했던 표면에서 계산된 제거 깊이만큼 내려갑니다. 가로는 웨이퍼 위치 mm, 세로는 제거 깊이 nm로 축척이 다릅니다.";

  function saveFrame() {
    if (!svg.current) return;
    const copy = svg.current.cloneNode(true) as SVGSVGElement;
    copy.setAttribute("xmlns", "http://www.w3.org/2000/svg");
    copy.setAttribute("width", "900");
    copy.setAttribute("height", "390");
    const metadata = document.createElementNS("http://www.w3.org/2000/svg", "metadata");
    metadata.textContent = JSON.stringify({
      format: "process-studio-surface-frame-v1", run_id: run.run_id,
      model_version: result.model_version, model, params, fault: run.fault,
      time_s: currentTime, profile_basis: result.playback?.profile_basis,
      x: domain!.x, x_unit: ald ? "um" : "mm", values_nm: values,
      film_display_gain: ald ? domain!.filmGain : null,
      evidence: "Reduced-model calculation; unequal axis scales; no equipment validation.",
    });
    copy.prepend(metadata);
    download(`surface-${model}-${run.run_id}-${currentTime.toFixed(3)}s.svg`, new XMLSerializer().serializeToString(copy), "image/svg+xml;charset=utf-8");
  }

  return (
    <section className="surface-panel" aria-label="표면 변화">
      <header className="surface-heading">
        <div><span className="surface-eyebrow">SURFACE / {ald ? "DEPOSITION" : "REMOVAL"}</span>
          <h2>{ald ? "채널 안쪽에 막이 자라는 과정" : "웨이퍼 표면이 깎이는 과정"}</h2></div>
        <button className="button secondary small" onClick={saveFrame}><Download size={15} />현재 단면 SVG 저장</button>
      </header>
      <p className="surface-intro">{description}</p>
      <div className="surface-drawing-scroll">
        <svg ref={svg} viewBox="0 0 900 390" role="img"
          aria-label={`${ald ? "ALD 채널 막 성장" : "Etch 웨이퍼 표면 제거"} 단면, ${currentTime.toFixed(2)}초`}
          fontFamily="Arial, 'Malgun Gothic', sans-serif" fontSize="13" fill={INK}>
          <title>{ald ? "ALD first-cycle film growth" : "Etch wafer surface recession"} — t={currentTime.toFixed(3)} s</title>
          <desc>{description} {result.playback?.description}</desc>
          <rect width="900" height="390" fill="#fbfcfc" />
          <text x="28" y="28" fontWeight="700" fontSize="15">{ald ? "THERMAL ALD · 채널 단면" : "PLASMA ETCH · 웨이퍼 지름 방향 단면"}</text>
          <text x="872" y="28" textAnchor="end" fontFamily="monospace">t = {currentTime.toFixed(3)} s</text>
          <text x="28" y="51" fill={MUTED}>{ald ? `${stage.label} · 첫 사이클만 재생` : result.effective.status === "off" ? "플라즈마 꺼짐 · 계산된 표면 제거량 표시" : "정상 플라즈마 아래의 표면 반응 · 패턴 없는 표면"}</text>
          {ald ? <>
            <rect x={LEFT} y="74" width={RIGHT - LEFT + 14} height="24" fill="#cbd2d5" />
            <rect x={LEFT} y={BOTTOM} width={RIGHT - LEFT + 14} height="24" fill="#cbd2d5" />
            <rect x={RIGHT} y={TOP} width="14" height={BOTTOM - TOP} fill="#cbd2d5" />
            {values.map((v, i) => {
              const h = v * domain.filmGain / domain.gapNm * (BOTTOM - TOP);
              return <g key={i} fill={FILM}>
                <rect x={xPx(edges[i])} y={TOP} width={xPx(edges[i + 1]) - xPx(edges[i])} height={h} />
                <rect x={xPx(edges[i])} y={BOTTOM - h} width={xPx(edges[i + 1]) - xPx(edges[i])} height={h} />
              </g>;
            })}
            <path d={`M${LEFT} ${TOP}H${RIGHT}M${LEFT} ${BOTTOM}H${RIGHT}`} stroke="#798991" strokeDasharray="5 4" fill="none" />
            <path d="M28 186H75L67 181M75 186L67 191" stroke={FILM} fill="none" strokeWidth="2" />
            <text x="28" y="169" fill={MUTED}>입구</text>
            <text x="796" y="184" textAnchor="end" fill={MUTED}>막힌 끝</text>
            <text x="455" y="175" textAnchor="middle" fontSize="15">초기 채널 간격 {fmt(domain.gapNm)} nm</text>
            <text x="455" y="200" textAnchor="middle" fill={FILM}>막 두께 표시 ×{fmt(domain.filmGain)} · 재생 동안 고정</text>
            <text x="105" y="69" fontSize="12" fill={FILM}>입구 쪽 {fmt(values[0])} nm</text>
            <text x="805" y="69" fontSize="12" textAnchor="end" fill={FILM}>깊은 곳 {fmt(values[values.length - 1])} nm</text>
            <text x="105" y="91" fontSize="12" fill="#43535d">기판</text>
            <text x="105" y="291" fontSize="12" fill="#43535d">기판</text>
          </> : <>
            {[0, 0.25, 0.5, 0.75, 1].map((fraction) => <g key={fraction}>
              <path d={`M${LEFT} ${TOP + fraction * (BOTTOM - TOP)}H${RIGHT}`} stroke="#e1e5e7" fill="none" />
              <text x="78" y={TOP + fraction * (BOTTOM - TOP) + 4} textAnchor="end" fill={MUTED}>{fmt(domain.depthAxisNm * fraction)}</text>
            </g>)}
            <polygon points={`${LEFT},${TOP} ${line} ${RIGHT},${TOP}`} fill="#efd9d1" />
            <polygon points={`${line} ${RIGHT},${BOTTOM} ${LEFT},${BOTTOM}`} fill="#cbd2d5" />
            <path d={`M${LEFT} ${TOP}H${RIGHT}`} fill="none" stroke="#798991" strokeDasharray="5 4" />
            <polyline data-surface-profile="etch" points={line} fill="none" stroke={ETCH} strokeWidth="2.5" />
            <text x={LEFT} y="82" fill={MUTED}>점선: 초기 표면</text>
            <text x="30" y="210" transform="rotate(-90 30 210)" textAnchor="middle" fill={MUTED}>제거 깊이 / nm ↓</text>
            <text x="455" y="291" textAnchor="middle" fill={MUTED}>색칠한 아래 영역: 남은 재료 · 바닥은 표시 범위</text>
          </>}
          {[0, 0.25, 0.5, 0.75, 1].map((fraction) => <g key={fraction}>
            <path d={`M${LEFT + fraction * (RIGHT - LEFT)} 302v5`} stroke="#7a8992" />
            <text x={LEFT + fraction * (RIGHT - LEFT)} y="324" textAnchor="middle" fill={MUTED}>{fmt(domain.xMin + fraction * (domain.xMax - domain.xMin))}</text>
          </g>)}
          <text x="455" y="346" textAnchor="middle">{ald ? "채널 깊이 / µm →" : "웨이퍼 위치 / mm →"}</text>
          <text x="28" y="375" fontSize="11" fill={MUTED}>{ald ? "계산: 1D 셀 성장 · 양 벽에 같은 값 · N회 진화·끝벽 성장 미계산" : "계산: 가정한 방사형 플럭스의 제거량 · 측벽·언더컷 미계산"} · 축척 다름</text>
          <text x="872" y="375" fontSize="11" textAnchor="end" fill={MUTED}>run {run.run_id}</text>
        </svg>
      </div>
      <p className="surface-scroll-hint">단면을 좌우로 움직여 전체를 볼 수 있습니다.</p>
      <div className="surface-readouts">
        {probes.map(({ label, index }) => <div key={label}><span>{label} <small>{fmt(domain.x[index])} {ald ? "µm" : "mm"}</small></span>
          <strong>{fmt(values[index])} <small>nm</small></strong></div>)}
      </div>
      <p className="surface-caption">{ald
        ? "초록 영역은 누적 성장량입니다. 기본 100배 표시이며 영역을 넘으면 배율을 낮춥니다. 비교할 때 표시 배율과 실제 nm 값을 확인하세요. 계단 모양은 셀별 표시이며 거칠기 예측이 아닙니다. A 피복률은 아래 그래프에 표시하고, 계산에 쓰는 채널 형상은 고정합니다."
        : "붉은 영역은 제거된 재료, 회색은 남은 재료입니다. 거의 평평하게 보이면 위치별 차이가 작은 것입니다. 깊이 축은 한 실행의 모든 시각에 동일하게 적용됩니다."}
        {" "}위 재생 막대로 시각을 바꾸면 단면과 시간 그래프가 함께 갱신됩니다.</p>
    </section>
  );
}
