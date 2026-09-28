import { Pause, Play, RotateCcw, SkipForward } from "lucide-react";
import { metricNumber } from "../storage";
import { stageAt, valueAt } from "../playback";
import type { ModelKey, ModelResult, Params } from "../types";
import type { usePlayback } from "../usePlayback";

export function Playback({
  model,
  result,
  params,
  duration,
  controller,
}: {
  model: ModelKey;
  result: ModelResult;
  params: Params;
  duration: number;
  controller: ReturnType<typeof usePlayback>;
}) {
  const time = controller.time ?? duration;
  const stage = stageAt(model, params, time, duration);
  const label = controller.playing
    ? "재생 중"
    : time >= duration
      ? "재생 완료"
      : "일시정지";
  const values =
    model === "ald"
      ? [
          {
            label: "챔버 A",
            value: valueAt(result, "pressure", 0, time),
            unit: "Pa",
          },
          {
            label: "챔버 B",
            value: valueAt(result, "pressure", 1, time),
            unit: "Pa",
          },
          {
            label: "입구 쪽 성장",
            value: valueAt(result, "growth", 0, time),
            unit: "nm / 첫 사이클",
          },
        ]
      : [
          {
            label: "균일 플럭스 식각량",
            value: valueAt(result, "depth", 0, time),
            unit: "nm",
          },
          {
            label: "마스크 손실",
            value: valueAt(result, "depth", 1, time),
            unit: "nm",
          },
          {
            label: "표면 피복률",
            value: valueAt(result, "coverage", 0, time),
            unit: "0–1",
          },
        ];
  return (
    <section className="playback-panel" aria-label="시뮬레이션 시간 재생">
      <div className="playback-heading">
        <span
          className={`playback-status ${controller.playing ? "is-playing" : ""}`}
        >
          <i />
          {label}
        </span>
        <strong>
          {model === "ald" ? "첫 ALD 사이클" : "표면 처리 타임라인"}
        </strong>
        <span className="playback-stage">
          {result.effective.status === "off" ? "플라즈마 꺼짐" : stage.label}
        </span>
        <output aria-label="현재 시뮬레이션 시간">
          t = {time.toFixed(2)} / {duration.toFixed(2)} s
        </output>
      </div>
      <div className="playback-controls">
        <button
          className="icon-button"
          aria-label="처음으로"
          disabled={duration <= 0}
          onClick={() => controller.seek(0)}
        >
          <RotateCcw size={17} />
        </button>
        <button
          className="button primary playback-toggle"
          aria-label={controller.playing ? "재생 일시정지" : "시간 재생"}
          disabled={duration <= 0}
          onClick={controller.toggle}
        >
          {controller.playing ? <Pause size={16} /> : <Play size={16} />}
          <span>{controller.playing ? "일시정지" : "재생"}</span>
        </button>
        <input
          type="range"
          aria-label="재생 시간"
          min={0}
          max={duration || 1}
          step="any"
          value={time}
          disabled={duration <= 0}
          onChange={(event) => controller.seek(Number(event.target.value))}
        />
        <button
          className="icon-button"
          aria-label="끝으로"
          disabled={duration <= 0}
          onClick={() => controller.seek(duration)}
        >
          <SkipForward size={17} />
        </button>
        <label className="playback-speed">
          속도
          <select
            aria-label="재생 속도"
            value={controller.speed}
            onChange={(event) =>
              controller.setSpeed(Number(event.target.value))
            }
          >
            {[0.25, 0.5, 1, 2, 5, 10, 20].map((speed) => (
              <option key={speed} value={speed}>
                {speed}×
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="playback-readouts">
        {values.map((item) => (
          <div key={item.label}>
            <span>{item.label}</span>
            <b>
              {item.value === null ? "—" : metricNumber(item.value, 4)}{" "}
              <small>{item.unit}</small>
            </b>
          </div>
        ))}
      </div>
      <p className="playback-explanation">
        {model === "ald"
          ? "분압·성장 계산을 첫 사이클 시간으로 재생합니다. N회 투영 두께는 오른쪽 종점 결과입니다."
          : "식각·표면 반응은 시간 계산, 플라즈마 밀도·온도는 정상상태입니다. 빛의 일렁임·입자 이동은 설명용 효과입니다."}{" "}
        <span>
          1× = 실제 1초에 공정 1초 · 샘플 사이 선형 보간
          {controller.reduceMotion ? " · 동작 줄이기 설정 적용" : ""}
        </span>
      </p>
    </section>
  );
}
