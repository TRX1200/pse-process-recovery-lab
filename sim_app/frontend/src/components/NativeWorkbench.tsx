import { useEffect, useMemo, useRef, useState } from "react";
import { Play, Square, RotateCcw } from "lucide-react";
import {NativeResults} from "./NativeResults";
import {defaultGoal,goalKey,parseGoalDraft,profileOf} from "../nativeAnalysis";
import type {NativeGoal} from "../nativeAnalysis";
import { compatibleGeometry, defaultNativeParams, GROUP_NAMES, isLocalWorkbench, nativeRequest,
  publicNativeJson } from "../native";
import type { NativeFrame, NativeJob, NativeRun, NativeSchema } from "../native";
import type { ModelKey, Params } from "../types";
import "../native.css";

export function NativeWorkbench({ setBusy }: { setBusy: (value: boolean) => void }) {
  const [schema, setSchema] = useState<NativeSchema | null>(null);
  const [available, setAvailable] = useState(false);
  const [model, setModel] = useState<ModelKey>("etch");
  const [params, setParams] = useState<Params>({});
  const [run, setRun] = useState<NativeRun | null>(null);
  const [reference, setReference] = useState<NativeRun | null>(null);
  const [recorded, setRecorded] = useState(true);
  const [frameIndex, setFrameIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [showInitial, setShowInitial] = useState(true);
  const [showMesh, setShowMesh] = useState(false);
  const [showParticles,setShowParticles]=useState(true);
  const [goals,setGoals]=useState<Record<string,NativeGoal>>(()=>{
    try{return parseGoalDraft(sessionStorage.getItem('native-target-drafts.v1'));}
    catch{return {}; /* Session storage can be unavailable in restricted browsers. */}
  });
  const [zoom, setZoom] = useState(1);
  const [panel, setPanel] = useState<"surface" | "evidence" | "history">("surface");
  const [job, setJob] = useState<NativeJob | null>(null);
  const [history, setHistory] = useState<NativeJob[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [validation, setValidation] = useState<{ checks: { name: string; result: string; detail: string }[] } | null>(null);
  const requestRef = useRef(0);
  const mainRef = useRef<HTMLDivElement>(null);
  const active = submitting || job?.state === "running" || job?.state === "queued";

  useEffect(()=>{
    try{sessionStorage.setItem('native-target-drafts.v1',JSON.stringify(parseGoalDraft(JSON.stringify(goals))));}
    catch{setError('목표 임시 저장을 사용할 수 없습니다. 평가 JSON이나 보고서로 목표를 보관하세요.');}
  },[goals]);

  useEffect(() => {
    let alive = true;
    async function load() {
      try {
        const base = await publicNativeJson<NativeSchema>("schema");
        if (!alive) return;
        setSchema(base); setParams(defaultNativeParams(base, "etch"));
        if (isLocalWorkbench()) {
          try {
            await nativeRequest<NativeSchema>("schema");
            if (alive) setAvailable(true);
          } catch { /* Static preview retains recorded examples and launch instructions. */ }
        }
        const example = await publicNativeJson<NativeRun>("etch-reference");
        if (alive) { setRun(example); setParams(example.params); setFrameIndex(example.frames.length - 1); }
      } catch (err) { if (alive) setError(String(err)); }
      finally { if (alive) setLoading(false); }
    }
    void load();
    void publicNativeJson<{ checks: { name: string; result: string; detail: string }[] }>("validation")
      .then(data => { if (alive) setValidation(data); }).catch(() => {});
    return () => { alive = false; requestRef.current += 1; };
  }, []);

  useEffect(() => {
    if (!playing || !run || active) return;
    const timer = window.setInterval(() => {
      setFrameIndex(index => {
        if (index >= run.frames.length - 1) { setPlaying(false); return index; }
        return index + 1;
      });
    }, 650);
    return () => window.clearInterval(timer);
  }, [playing, run, active]);

  useEffect(() => {
    if (!active || !job) return;
    let disposed = false;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const status = await nativeRequest<NativeJob>(`jobs/${job!.id}`);
        if (disposed) return;
        if (status.state === "complete") {
          const result = await nativeRequest<NativeRun>(`jobs/${status.id}/result`);
          if (disposed) return;
          setRun(result); setRecorded(false); setFrameIndex(result.frames.length - 1);
          setJob(status);
          setBusy(false); setPlaying(false);
        } else if (status.state === "failed" || status.state === "cancelled") {
          setJob(status);
          setBusy(false);
          if (status.error) setError(status.error);
        } else { setJob(status); timer = setTimeout(poll, 1000); }
      } catch (err) {
        if (disposed) return;
        setError(`상태 확인 실패: ${String(err)}. 실행 기록에서 다시 확인할 수 있습니다.`);
        setBusy(false); setJob(null);
      }
    }
    timer = setTimeout(poll, 500);
    return () => { disposed = true; clearTimeout(timer); };
  // A single polling loop owns each job, independent of progress renders.
  }, [job?.id, active, setBusy]);

  async function loadExample(next: ModelKey, variant = "reference") {
    if (active) return;
    const id = ++requestRef.current;
    setLoading(true); setPlaying(false); setError(""); setZoom(1);
    if (next !== model) setReference(null);
    try {
      const example = await publicNativeJson<NativeRun>(`${next}-${variant}`);
      if (id !== requestRef.current) return;
      setModel(next); setRun(example); setParams(example.params); setRecorded(true);
      setFrameIndex(example.frames.length - 1); setJob(null);
    } catch (err) { if (id === requestRef.current) setError(String(err)); }
    finally { if (id === requestRef.current) setLoading(false); }
  }

  async function execute(event: React.FormEvent) {
    event.preventDefault();
    if (active || !available) return;
    setBusy(true); setSubmitting(true); setError(""); setPlaying(false); setPanel("surface");
    requestAnimationFrame(() => mainRef.current?.scrollIntoView({ block: "start", behavior: "smooth" }));
    try { setJob(await nativeRequest<NativeJob>("jobs", { model, params })); }
    catch (err) { setError(String(err)); setBusy(false); }
    finally { setSubmitting(false); }
  }
  async function cancel() {
    if (!job) return;
    try { setJob(await nativeRequest<NativeJob>(`jobs/${job.id}/cancel`, {})); setBusy(false); }
    catch (err) { setError(String(err)); }
  }
  async function showHistory() {
    setPanel("history");
    if (!available) return;
    try { setHistory((await nativeRequest<{ jobs: NativeJob[] }>("jobs")).jobs); }
    catch (err) { setError(String(err)); }
  }
  async function openHistory(id: string) {
    try {
      const result = await nativeRequest<NativeRun>(`jobs/${id}/result`);
      setRun(result); setParams(result.params); setModel(result.model); setRecorded(false);
      setFrameIndex(result.frames.length - 1); setReference(null); setPanel("surface"); setJob(null);
    } catch (err) { setError(String(err)); }
  }

  const displayRun=useMemo(()=>active&&job?.last_frame&&run?{...run,run_hash:job.id,model:job.model,params,warnings:[],frames:[job.initial_frame??job.last_frame,job.last_frame]}:run,[active,job,run,params]);
  const targetKey=displayRun?goalKey(displayRun.model,profileOf(displayRun)):goalKey(model,0);
  const goal=useMemo(()=>goals[targetKey]??defaultGoal(displayRun?.model??model,displayRun?profileOf(displayRun):0),[goals,targetKey,displayRun?.model,displayRun?.params.surface_profile,model]);
  if (!schema) return <section className="native-loading"><h1>Feature Simulator</h1><p>{error || "계산 작업 화면을 준비합니다…"}</p></section>;
  const fields = schema.models[model].params;
  const pending = !!run && JSON.stringify(params) !== JSON.stringify(run.params);
  const displayFrame: NativeFrame | undefined = active && job?.last_frame ? job.last_frame : run?.frames[frameIndex];
  const comparable = displayRun && reference && compatibleGeometry(displayRun, reference) ? reference : null;
  const groups = [...new Set(fields.map(f => f.group))];
  const inputProfile=params.surface_profile??0;
  const sourceLabel = active ? job?.last_frame ? "로컬 계산 중" : "새 결과 대기 · 직전 결과 표시" : recorded ? "저장된 계산 예제" : "로컬 Python 계산 결과";
  return <section className="native-workbench">
    <header className="native-heading">
      <div><span className="native-eyebrow">FEATURE-SCALE PROCESS SIMULATION</span><h1>ALD / Etch · 형상 해석</h1>
        <p>구조와 입사 조건을 정하고, 계산된 단면으로 공정을 비교합니다.</p></div>
      <div className={`native-connection ${available ? "connected" : ""}`}><i />{available ? "Python native engine 연결됨" : "공개 예제 뷰어"}
        <small>ViennaPS 4.6.2 / ViennaLS 5.8.5 · 2D</small></div>
    </header>
    {!available && <div className="native-launch"><strong>새 조건 계산은 로컬 Python에서 실행합니다.</strong><span>아래 예제는 실제 네이티브 엔진으로 계산해 저장한 결과입니다.</span>
      <a href="https://github.com/TRX1200/pse-process-recovery-lab/blob/main/docs/NATIVE_SIMULATOR_KR.md" target="_blank" rel="noreferrer">설치·실행 안내 ↗</a></div>}
    {error && <p className="error-banner" role="alert">{error}</p>}
    {job?.state === "cancelled" && <p className="native-pending" role="status">계산을 중단했습니다. 화면에는 직전 완료 결과를 유지합니다. 입력과 중단 기록은 저장되었습니다.</p>}
    <div className="native-model-switch" aria-label="형상 해석 공정">
      <button disabled={!!active || loading} aria-pressed={model === "etch"} onClick={() => void loadExample("etch")}>Si / SF₆–O₂ Etch</button>
      <button disabled={!!active || loading} aria-pressed={model === "ald"} onClick={() => void loadExample("ald")}>Al₂O₃ / 제한 반응 ALD</button>
      <span>{model === "etch" ? "마스크 · 입자 수송 · 표면 반응 · 이동 경계" : "피복률 · 입자 재반사 · 성장 · 통로 변화"}</span>
    </div>
    <div className="native-layout">
      <form className="native-controls" onSubmit={event => void execute(event)}>
        <div className="native-control-heading"><h2>Simulation setup</h2><button type="button" title="기본 조건 복원" disabled={!!active || !available} onClick={() => { setParams(defaultNativeParams(schema, model)); setError(""); }}><RotateCcw size={15} /></button></div>
        <div className="native-run-actions"><button className="button primary" type="submit" disabled={!available || !!active || loading}><Play size={16} />Run simulation</button>
          {active && <button className="button secondary" type="button" onClick={() => void cancel()}><Square size={14} />계산 중단</button>}</div>
        <p className="native-input-hint">{model === "etch" ? "입사 플럭스·에너지는 구조 입구 경계조건입니다. RF 전력이나 sccm을 대신하는 장비 레시피가 아닙니다." : "반대 반응과 퍼지가 완료된 TMA 제한 모델입니다. 한 사이클의 전체 화학을 풀지는 않습니다."}</p>
        {groups.map(group => <details key={`${model}-${group}`} open={group === "surface" || group === "geometry" || group === "recipe" || group === "boundary"}>
          <summary>{GROUP_NAMES[group]}</summary>
          {fields.filter(f => f.group === group && !(inputProfile===0&&['corrugation_amplitude_nm','corrugation_count'].includes(f.key)) && !(inputProfile===1&&['width_nm','depth_nm'].includes(f.key)) && !(inputProfile!==0&&f.key==='mask_nm') && !(model==='etch'&&inputProfile!==2&&f.key==='depth_nm')).map(f => <label className="native-field" key={f.key}>
            <span>{f.label}<small>{f.unit}</small></span>
            {f.choices?<select aria-label={f.label} value={params[f.key]??f.default} disabled={!!active||!available||loading} onChange={e=>setParams(current=>({...current,[f.key]:Number(e.target.value),...(Number(e.target.value)>0?{grid_nm:2}: {})}))}>{f.choices.map(c=><option key={c.value} value={c.value}>{c.label}</option>)}</select>:<input type="number" aria-label={f.label} min={f.min} max={f.max} step={f.integer ? 1 : "any"} required value={params[f.key]===undefined?f.default:Number.isFinite(params[f.key])?params[f.key]:""}
              disabled={!!active || !available || loading} onChange={event => setParams(current => ({ ...current, [f.key]: event.target.value === "" ? NaN : Number(event.target.value) }))} />}
            <small>{f.description}</small>
          </label>)}
        </details>)}
      </form>
      <div className="native-main" ref={mainRef}>
        <div className="native-tabs"><button aria-pressed={panel === "surface"} onClick={() => setPanel("surface")}>단면 / 결과</button><button aria-pressed={panel === "evidence"} onClick={() => setPanel("evidence")}>계산 근거 / 검증</button><button aria-pressed={panel === "history"} onClick={() => void showHistory()}>실행 기록</button></div>
        {active && <div className="native-progress" role="status"><span>Python 계산 중 · {Math.round((job?.progress ?? 0) * 100)}% · {Math.round(job?.elapsed_s ?? 0)} s</span><progress value={job?.progress ?? 0} max="1" /><small>완료된 구간의 실제 표면을 표시합니다. 중단하면 마지막 완료 결과를 유지합니다.</small></div>}
        {panel === "surface" && run && displayFrame && displayRun ? <>
          <div className="native-examples"><span>저장된 비교 예제</span><button disabled={!!active || loading} onClick={() => void loadExample(model, "reference")}>기준 조건</button><button disabled={!!active || loading} onClick={() => void loadExample(model, "variant")}>{model === "etch" ? "방향성 감소 + O 공급 감소" : "노출 시간 감소"}</button></div>
          <div className="native-examples"><span>초기 요철 실험</span><button disabled={!!active||loading} onClick={()=>void loadExample(model,'ripple')}>표면 ripple 예제</button><button disabled={!!active||loading} onClick={()=>void loadExample(model,'scallop')}>측벽 scallop 예제</button></div>
          {pending&&!active&&<p className="native-pending">공정 입력이 바뀌었습니다. 단면·목표·평가표는 마지막 계산 시편을 표시합니다. Run simulation을 눌러 새 조건을 계산하세요.</p>}
          <NativeResults run={displayRun} frame={displayFrame} reference={comparable} active={!!active} recorded={recorded}
            index={frameIndex} playing={playing} onPlay={()=>{if(frameIndex===run.frames.length-1)setFrameIndex(0);setPlaying(!playing);}} onFrame={i=>{setPlaying(false);setFrameIndex(i);}}
            goal={goal} onGoal={value=>setGoals(current=>({...current,[targetKey]:value}))}
            showInitial={showInitial&&(!active||!!job?.initial_frame)} onInitial={setShowInitial} showMesh={showMesh} onMesh={setShowMesh}
            showParticles={showParticles} onParticles={setShowParticles} zoom={zoom} onZoom={setZoom} onReference={setReference} sourceLabel={sourceLabel}/>
        </> : panel === "surface" ? <p className="native-loading">{loading ? "계산 형상을 불러오는 중…" : "결과를 선택하거나 새 계산을 실행하세요."}</p> : null}
        {panel === "evidence" && <div className="native-evidence">
          <h2>무엇을 계산하는가</h2><p>{schema.models[model].engine}</p>
          <p>{model === "etch" ? "입사 이온·F·O의 수송과 반사 → 표면 피복률과 반응·스퍼터링 → 국소 제거 속도 → level-set 형상 갱신을 반복합니다." : "입사 TMA의 수송과 재반사 → 빈 반응 자리의 피복·탈착 → 위치별 성장량 → level-set 형상 갱신을 반복합니다. 반대 반응은 포화된다고 가정합니다."}</p>
          <div className="native-equation">{model === "etch" ? "∂φ/∂t + Vₙ |∇φ| = 0     (Vₙ < 0: 제거)" : "dθ/dt = [Γ β (1 − θ) − Γev θ] / Nsites\nΔh = GPC × θ × ΔNcycles"}</div>
          <h3>검증 상태</h3><p><strong>실제 장비·레시피와의 정량 일치: 미검증.</strong> 네이티브 해석기를 사용하는 것과 특정 장비를 재현하는 것은 서로 다른 검증 항목입니다.</p>
          {validation ? <table><thead><tr><th>확인 항목</th><th>결과</th><th>검증 범위</th></tr></thead><tbody>{validation.checks.map(c => <tr key={c.name}><td>{c.name}</td><td>{c.result}</td><td>{c.detail}</td></tr>)}</tbody></table> : <p>검증 결과 파일을 읽지 못했습니다. 저장소의 재현 명령을 확인하세요.</p>}
          <h3>현재 실행의 가정</h3><ul>{run?.assumptions.map(item => <li key={item}>{item}</li>)}</ul>
          <h3>출처와 구현</h3><ul>{schema.sources.map(source => <li key={source.url}><a href={source.url} target="_blank" rel="noreferrer">{source.title} ↗</a></li>)}</ul>
          <p>원래 해석기 저작자는 ViennaTools 연구진입니다. 이 프로젝트는 Python 실행·입력 검증·시각화·비교·검증 도구를 통합합니다.</p>
          <details><summary>현재 실행의 수치 설정 / 환경</summary><pre>{JSON.stringify({ numerics: run?.numerics, environment: run?.environment }, null, 2)}</pre></details>
        </div>}
        {panel === "history" && <div className="native-evidence"><h2>로컬 실행 기록</h2><p>입력, 진행 상태, worker.log, 최종 JSON·VTK·level set은 outputs/native_lab에 저장됩니다.</p>{!available ? <p>로컬 서버를 실행하면 기록을 확인할 수 있습니다.</p> : history.length === 0 ? <p>저장된 실행이 없습니다.</p> : <table><thead><tr><th>실행</th><th>공정</th><th>상태</th><th /></tr></thead><tbody>{history.map(item => <tr key={item.id}><td><code>{item.id.slice(0, 10)}</code></td><td>{item.model.toUpperCase()}</td><td>{item.state}</td><td><button disabled={item.state !== "complete" || !!active} onClick={() => void openHistory(item.id)}>결과 열기</button></td></tr>)}</tbody></table>}</div>}
      </div>
    </div>
  </section>;
}
