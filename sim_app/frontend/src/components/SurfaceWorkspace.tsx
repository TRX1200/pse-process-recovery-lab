import type { ModelKey, ModelSchema, Params, Simulation } from "../types";
import type { usePlayback } from "../usePlayback";
import { durationOf } from "../playback";
import { QUICK_KEYS, PARAMETER_TIPS } from "../userGuide";
import { SurfaceSection } from "./SurfaceSection";
import { Playback } from "./Playback";
import { Chart } from "./Chart";

export function SurfaceWorkspace({ model, schema, params, fault, run, pending, busy, controller, onChange, onFault, onRun, onEditAll, onGuide }: {
  model: ModelKey;
  schema: ModelSchema;
  params: Params;
  fault: string;
  run: Simulation | null;
  pending: boolean;
  busy: boolean;
  controller: ReturnType<typeof usePlayback>;
  onChange: (key: string, value: number) => void;
  onFault: (fault: string) => void;
  onRun: () => void;
  onEditAll: () => void;
  onGuide: () => void;
}) {
  const current = run?.model === model ? run : null;
  const valid = current && current.result.effective.status !== "outside_rate_fit";
  const quick = QUICK_KEYS[model].map(key => schema.params.find(p => p.key === key)!);
  const severity = schema.params.find(p => p.key === "fault_severity")!;
  const curves = current?.result.series.filter(s => (model === "ald" ? ["growth", "coverage", "pressure"] : ["depth", "coverage"]).includes(s.key)) ?? [];
  return (
    <div className="surface-workspace">
      <div className="surface-run-bar">
        <span>{current ? `표시 중: ${schema.faults.find(f => f.id === current.fault)?.label} · run ${current.run_id}` : "첫 계산 전 · 아래 기본 조건으로 시작하세요"}</span>
        <button className="text-action" onClick={onGuide} disabled={busy}>사용 설명서 ↗</button>
      </div>
      {pending && <p className="pending-banner" role="status">입력이 변경되었습니다. 단면과 그래프는 이전 실행 결과입니다. 다시 계산하면 반영됩니다.</p>}
      {valid ? <>
        <Playback model={model} result={current.result} params={current.params} duration={durationOf(current.result)} controller={controller} compact />
        <SurfaceSection run={current} time={controller.time} focus />
      </> : <div className="surface-empty">
        <h2>{current ? "이 조건은 모델 적용 범위 밖입니다" : "표면 변화를 관찰할 준비가 됐습니다"}</h2>
        <p>{current ? "허용 범위의 입력도 물리 모델에서는 계산 불가일 수 있습니다. 전체 조건 편집에서 진단을 확인하세요." : "핵심 조건을 확인하고 계산하면 이 영역에 시간별 공정 단면이 크게 표시됩니다."}</p>
        {current ? <button className="button secondary" onClick={onEditAll}>진단·전체 조건 보기</button> : <button className="button primary" disabled={busy} onClick={onRun}>{busy ? "계산 중…" : "현재 조건으로 첫 계산"}</button>}
      </div>}
      <form className="surface-quick-form" onSubmit={e => { e.preventDefault(); onRun(); }}>
        <div className="surface-input-heading"><h2>먼저 조절할 조건 4개</h2><button className="text-action" type="button" onClick={onEditAll} disabled={busy}>전체 조건 편집 ↗</button></div>
        <fieldset disabled={busy}>
          <div className="surface-quick-grid">{quick.map(p => <label key={p.key}>
            <span>{p.label} <small>{p.unit}</small></span>
            <input aria-label={p.label} aria-describedby={`surface-help-${p.key}`} type="number" required min={p.min} max={p.max} step="any" value={params[p.key]} onChange={e => { if (e.target.value !== "") onChange(p.key, Number(e.target.value)); }} />
            <small id={`surface-help-${p.key}`}>{PARAMETER_TIPS[model][p.key]}</small>
          </label>)}</div>
          <div className="surface-fault-inputs">
            <label>이상 조건<select value={fault} onChange={e => onFault(e.target.value)}>{schema.faults.map(f => <option key={f.id} value={f.id}>{f.label}</option>)}</select></label>
            <label>이상 강도<input aria-label="표면 관찰 이상 강도" type="number" required min={severity.min} max={severity.max} step="any" value={params.fault_severity} disabled={fault === "none"} onChange={e => { if (e.target.value !== "") onChange("fault_severity", Number(e.target.value)); }} /></label>
            <button className="button primary" type="submit">{busy ? "계산 중…" : "조건 적용 · 계산 · 재생"}</button>
          </div>
          <p className="surface-input-note">여기에 없는 조건은 현재 레시피 값을 유지합니다. 전체 조건 편집에서 확인·초기화할 수 있습니다.</p>
        </fieldset>
      </form>
      {valid && <section className="surface-time-plots" aria-label="단면과 연결된 시간 그래프"><h2>같은 시각의 공정 응답</h2><div>{curves.map(series => <Chart key={series.key} series={series} time={controller.time} compact />)}</div></section>}
    </div>
  );
}
