import {useEffect,useMemo,useState} from 'react';
import {Play,Pause,Download,Square} from 'lucide-react';
import {NativeViewport} from './NativeViewport';
import {Chart} from './Chart';
import {ALDExperiments} from './ALDExperiments';
import {isLocalWorkbench,nativeRequest,publicNativeJson,NATIVE_METRICS} from '../native';
import {exportJson,download} from '../storage';
import {GROUPS,STAGES,inputProblem,recipeInputs,sameInputs,sequenceCharts,stageRun} from '../sequence';
import type {ALDRecipe,ALDRecipeCatalog,SequenceJob,SequenceRun,SequenceSchema,SequenceStage} from '../sequence';
import type {NativeParameter} from '../native';
import type {Params} from '../types';
import '../sequence.css';

const CASES=[['reference','기준 공정'],['short-pulse','짧은 ALD 노출'],['wide-angle','넓은 이온 입사각']] as const;
const EMPTY:number[][][]=[];

export function SequenceWorkbench({setBusy}:{setBusy:(v:boolean)=>void}){
  const [fields,setFields]=useState<NativeParameter[]>([]);
  const [run,setRun]=useState<SequenceRun|null>(null);
  const [reference,setReference]=useState<SequenceRun|null>(null);
  const [params,setParams]=useState<Params>({});
  const [stage,setStage]=useState<SequenceStage>('ald');
  const [group,setGroup]=useState<keyof typeof GROUPS>('etch');
  const [page,setPage]=useState<'section'|'charts'|'recipes'|'model'>('section');
  const [recipes,setRecipes]=useState<ALDRecipeCatalog|null>(null),[recipeError,setRecipeError]=useState('');
  const [recipeId,setRecipeId]=useState('D01');
  const [mobile,setMobile]=useState<'result'|'setup'>('result');
  const [index,setIndex]=useState(0),[chart,setChart]=useState(0);
  const [mesh,setMesh]=useState(false),[initial,setInitial]=useState(false);
  const [playing,setPlaying]=useState(false),[available,setAvailable]=useState(false);
  const [job,setJob]=useState<SequenceJob|null>(null);
  const [loading,setLoading]=useState(true),[submitting,setSubmitting]=useState(false);
  const [recorded,setRecorded]=useState(true),[error,setError]=useState('');
  const [history,setHistory]=useState<SequenceJob[]>([]);
  const active=submitting||job?.state==='running'||job?.state==='queued';
  const selected=useMemo(()=>run?stageRun(run,stage):null,[run,stage]);
  const comparative=useMemo(()=>reference?stageRun(reference,stage):null,[reference,stage]);
  const frame=selected?.frames[Math.min(index,selected.frames.length-1)];
  const charts=useMemo(()=>run?sequenceCharts(run,stage):[],[run,stage]);
  const baselineCharts=useMemo(()=>reference?sequenceCharts(reference,stage):[],[reference,stage]);
  const bounds=useMemo(()=>run?[...run.etch.frames,run.strip,...run.ald.frames,
    ...(reference?[...reference.etch.frames,...reference.ald.frames]:[])]:[],[run,reference]);
  const problem=fields.length?inputProblem(fields,params):null;
  const stale=!!run&&!sameInputs(params,run.request.params);

  function accept(result:SequenceRun,isRecorded:boolean){
    setRun(result);setParams(result.request.params);setStage('ald');
    setIndex(result.ald.frames.length-1);setPlaying(false);setRecorded(isRecorded);setJob(null);
  }
  useEffect(()=>{
    let alive=true;
    void Promise.all([publicNativeJson<SequenceSchema>('schema'),publicNativeJson<SequenceRun>('sequence-reference')])
      .then(([schema,result])=>{if(alive){setFields(schema.models.sequence.params);accept(result,true);}})
      .catch(e=>{if(alive)setError(String(e));}).finally(()=>{if(alive)setLoading(false);});
    void publicNativeJson<ALDRecipeCatalog>('ald-recipes')
      .then(data=>{if(alive)setRecipes(data);})
      .catch(e=>{if(alive)setRecipeError(`실험 입력을 불러오지 못했습니다: ${String(e)}`);});
    if(isLocalWorkbench())void nativeRequest<SequenceSchema>('schema')
      .then(s=>{if(alive)setAvailable(!!s.models.sequence);}).catch(()=>{});
    return()=>{alive=false;};
  },[]);
  useEffect(()=>{
    if(!playing||!selected||active)return;
    const timer=setInterval(()=>setIndex(i=>{
      if(i>=selected.frames.length-1){setPlaying(false);return i;}
      return i+1;
    }),500);
    return()=>clearInterval(timer);
  },[playing,selected,active]);
  useEffect(()=>{
    if(!job?.id||!active)return;
    let disposed=false;
    let timer:ReturnType<typeof setTimeout>;
    async function poll(){
      try{
        const status=await nativeRequest<SequenceJob>(`jobs/${job!.id}`);
        if(disposed)return;
        if(status.state==='complete'){
          const result=await nativeRequest<SequenceRun>(`jobs/${status.id}/result`);
          if(disposed)return;
          accept(result,false);setBusy(false);
        }else if(status.state==='failed'||status.state==='cancelled'){
          setJob(status);setBusy(false);if(status.error)setError(status.error);
        }else{setJob(status);timer=setTimeout(poll,800);}
      }catch(e){if(!disposed){setError(`상태 확인 실패: ${String(e)}. 실행 기록에서 다시 확인하세요.`);setJob(null);setBusy(false);}}
    }
    timer=setTimeout(poll,400);
    return()=>{disposed=true;clearTimeout(timer);};
  },[job?.id,active,setBusy]);

  async function loadCase(name:string){
    setLoading(true);setPlaying(false);setError('');
    try{accept(await publicNativeJson<SequenceRun>(`sequence-${name}`),true);}
    catch(e){setError(String(e));}finally{setLoading(false);}
  }
  async function execute(){
    if(active||!available||problem)return;
    setError('');setSubmitting(true);setPlaying(false);setPage('section');setBusy(true);
    try{setJob(await nativeRequest<SequenceJob>('jobs',{model:'sequence',params}));}
    catch(e){setError(String(e));setBusy(false);}finally{setSubmitting(false);}
  }
  async function cancel(){
    if(!job)return;
    try{setJob(await nativeRequest<SequenceJob>(`jobs/${job.id}/cancel`,{}));setBusy(false);}
    catch(e){setError(String(e));}
  }
  async function loadHistory(){
    try{setHistory((await nativeRequest<{jobs:SequenceJob[]}>('jobs')).jobs.filter(j=>j.model==='sequence'));}
    catch(e){setError(String(e));}
  }
  async function openHistory(id:string){
    setLoading(true);
    try{accept(await nativeRequest<SequenceRun>(`jobs/${id}/result`),false);setHistory([]);}
    catch(e){setError(String(e));}finally{setLoading(false);}
  }
  function chooseStage(next:SequenceStage){
    setStage(next);setPlaying(false);setChart(0);
    if(run)setIndex(stageRun(run,next).frames.length-1);
  }
  function applyRecipe(recipe:ALDRecipe){
    if(active||loading)return;
    try{
      setParams(recipeInputs(recipe,fields));setGroup('ald');chooseStage('ald');setError('');
    }catch(e){setError(String(e));}
  }
  function saveSvg(){
    const svg=document.querySelector('.sequence-workbench .native-viewport');if(!svg||!run)return;
    const copy=svg.cloneNode(true) as SVGElement;
    copy.setAttribute('xmlns','http://www.w3.org/2000/svg');
    const metadata=document.createElementNS('http://www.w3.org/2000/svg','metadata');
    metadata.textContent=JSON.stringify({run_hash:run.run_hash,stage,frame:index,request:run.request,
      environment:run.environment,handoff:run.handoff,reference:reference?.run_hash??null,
      evidence:'computed 2D native contours; not equipment validation'});
    copy.prepend(metadata);
    download(`process-${stage}-${run.run_hash.slice(0,8)}.svg`,new XMLSerializer().serializeToString(copy),'image/svg+xml');
  }
  function saveCsv(){
    if(!selected||!run)return;
    const keys=[...new Set(selected.frames.flatMap(f=>Object.keys(f.metrics)))];
    const rows=[['run_hash','stage','at','axis_unit',...keys],...selected.frames.map(f=>
      [run.run_hash,stage,f.at,stage==='strip'?'instant':selected.axis_unit,...keys.map(k=>
        k==='bottom_top_pct'&&(f.metrics.top_film_nm??0)<=1e-6?'':f.metrics[k]??'')])];
    download(`process-${stage}-${run.run_hash.slice(0,8)}.csv`,rows.map(row=>row.join(',')).join('\n'),'text/csv');
  }
  if(!run||!selected||!frame)return <section className="sequence-workbench"><p>{error||'물리 공정 계산 예제를 불러옵니다…'}</p></section>;
  const metricKeys=stage==='ald'?['top_film_nm','bottom_film_nm','bottom_top_pct','mid_gap_nm']:
    stage==='strip'?['center_depth_nm','width_half_depth_nm']:['center_depth_nm','width_half_depth_nm','mask_loss_nm'];
  return <section className="sequence-workbench" data-mobile-pane={mobile}>
    <header className="seq-header"><div><span>PROCESS SIMULATION / 2D</span><h1>Si Etch → Strip → Al₂O₃ ALD</h1></div>
      <div className="seq-connection">{available?'● 로컬 ViennaPS 연결':'저장된 계산 예제'}<small>입자 수송 · 표면 반응 · Level set</small></div></header>
    <div className="seq-toolbar"><label>계산 예제 <select aria-label="연속공정 예제" disabled={active||loading} value="" onChange={e=>void loadCase(e.target.value)}><option value="" disabled>계산 예제 선택</option>{CASES.map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label>
      <button disabled={active||loading} onClick={()=>setReference(run)}>현재 결과 비교 고정</button>{reference&&<button onClick={()=>setReference(null)}>비교 해제</button>}
      <button disabled={active||loading} onClick={()=>exportJson(`process-${run.run_hash.slice(0,8)}.json`,run)}><Download size={14}/>결과 JSON</button>
      <button disabled={active||loading||page!=='section'} onClick={saveSvg}>단면 SVG</button><button disabled={active||loading} onClick={saveCsv}>지표 CSV</button>
      {available&&<button disabled={active||loading} onClick={()=>void loadHistory()}>실행 기록</button>}
      <button className="seq-primary" disabled={!available||active||loading||!!problem} onClick={()=>void execute()}><Play size={14}/>연속 공정 계산</button>{active&&<button onClick={()=>void cancel()}><Square size={13}/>중단</button>}
    </div>
    {(error||problem)&&<p className="seq-warning" role="alert">{error||problem}</p>}
    {active?<div className="seq-notice">새 계산 {Math.round((job?.progress??0)*100)}% · {job?.last_frame?.stage??'준비'} · 화면은 직전 완료 결과입니다.<progress max="1" value={job?.progress??0}/></div>:
      stale?<p className="seq-notice">입력 조건을 변경했습니다. 아래 단면은 직전 계산이며, 새 조건은 ‘연속 공정 계산’으로 반영됩니다.</p>:
      <p className="seq-notice">{recorded?'저장된 Python 계산':'이번 로컬 계산'} · Etch {run.request.params.duration_s} s → 이상적 Strip → ALD {run.request.params.cycles} cycles / 노출 {run.request.params.pulse_s} s{!available?' · 새 조건 계산은 로컬 Python 서버에서 가능합니다.':''}</p>}
    {history.length>0&&<div className="seq-history"><button onClick={()=>setHistory([])}>기록 닫기</button>{history.map(h=><button key={h.id} disabled={h.state!=='complete'||loading} onClick={()=>void openHistory(h.id)}>{h.id.slice(0,8)} · {h.state}</button>)}</div>}
    <nav className="seq-mobile"><button aria-pressed={mobile==='result'} onClick={()=>setMobile('result')}>단면 / 결과</button><button aria-pressed={mobile==='setup'} onClick={()=>setMobile('setup')}>공정 조건</button></nav>
    <div className="seq-layout"><aside className="seq-steps"><h2>공정 순서</h2>{STAGES.map((s,i)=><button key={s.key} aria-pressed={stage===s.key} onClick={()=>chooseStage(s.key)}><b>0{i+1}</b><span>{s.name}<small>{s.detail}</small></span></button>)}
      <div className="seq-handoff"><strong>공정 간 형상 전달</strong><p>식각된 Si 경계를 그대로 다음 공정에 사용합니다.</p><code>{run.handoff.geometry_sha256.slice(0,12)}</code><p>{run.handoff.si_contour_preserved?'Si 경계 일치 확인':'경계 확인 필요'}</p></div>
      <p className="seq-small">격자 {run.request.params.grid_nm} nm<br/>입자 {run.request.params.rays_per_point} / 표면점</p></aside>
      <div className="seq-result"><nav className="seq-pages" aria-label="물리 연속공정 결과">{([['section','계산 단면'],['charts','진단 그래프'],['recipes','증착 실험 10'],['model','모델 / 재현']] as const).map(([key,label])=><button key={key} aria-pressed={page===key} onClick={()=>{setPage(key);setPlaying(false);}}>{label}</button>)}</nav>
        {page==='recipes'&&<ALDExperiments catalog={recipes} fields={fields} params={params} resultParams={run.request.params} disabled={active||loading} error={recipeError} selected={recipeId} onSelect={setRecipeId} onApply={applyRecipe}/>}
        {page==='section'&&<div className="seq-section"><div className="seq-view-options"><strong>{STAGES.find(s=>s.key===stage)!.name}</strong><label><input type="checkbox" checked={mesh} onChange={e=>setMesh(e.target.checked)}/>표면 이산점</label><label><input type="checkbox" checked={initial} onChange={e=>setInitial(e.target.checked)}/>단계 시작선</label></div>
          <div className="seq-canvas"><NativeViewport run={selected} frame={frame} reference={comparative} initial={initial} mesh={mesh} zoom={1} target={EMPTY} particles={false} playing={false} technical boundsFrames={bounds}/></div>
          <div className="seq-legend"><span><i className="si"/>Si</span>{stage==='etch'&&<span><i className="mask"/>유효 마스크</span>}{stage==='ald'&&<span><i className="film"/>Al₂O₃</span>}{reference&&<span>파란 점선: 고정한 결과</span>}</div>
          <div className="seq-metrics">{metricKeys.map(key=>{const value=key==='bottom_top_pct'&&(frame.metrics.top_film_nm??0)<=1e-6?null:frame.metrics[key];return <div key={key}><span>{NATIVE_METRICS[key]?.[0]??key}</span><strong>{value==null?'—':value.toFixed(2)}<small>{NATIVE_METRICS[key]?.[1]}</small></strong></div>;})}</div>
          {stage==='ald'&&(frame.metrics.top_film_nm??0)>0&&(frame.metrics.top_film_nm??0)<2*run.request.params.grid_nm&&<p className="seq-warning">막 두께가 2격자보다 작습니다. 정량 해석 전 격자를 줄여 비교하세요.</p>}
        </div>}
        {page==='charts'&&<div className="seq-scroll"><nav className="seq-chart-tabs">{charts.map((c,i)=><button key={c.key} aria-pressed={chart===i} onClick={()=>setChart(i)}>{c.title}</button>)}</nav><Chart series={charts[chart]??charts[0]} baseline={baselineCharts[chart]} baselineLabel="고정한 비교" time={stage==='strip'?undefined:frame.at}/><p className="seq-small">{stage==='strip'?'마스크 제거에는 시간 모델이 없습니다. 여기서는 앞선 식각 이력을 표시합니다.':'곡선은 해당 단계의 계산 이력입니다. 초와 사이클은 서로 다른 축입니다.'} {reference?'점선은 고정한 비교 결과입니다.':''}</p></div>}
        {page==='model'&&<div className="seq-scroll seq-model"><h2>형상은 어떻게 계산하나</h2><p>Etch: 입사 이온·F·O 수송 → 표면 피복과 제거 속도 → Level-set 경계 이동</p><p>ALD: TMA 수송·재반사 → 자리 피복률 → GPC × 피복률 × 사이클 → 경계 이동</p><code>∂φ/∂t + Vn |∇φ| = 0</code><code>dθ/dt = [Γ β (1 − θ) − Γev θ] / Nsites</code><h3>이번 구현의 경계</h3><p>Si/SF₆–O₂와 Al₂O₃ 제한 반응 모델을 연결했습니다. HfO₂/TiN/GAA의 화학 모델, 챔버 플라즈마, 도핑 및 I–V 계산은 포함하지 않습니다.</p><p>마스크 제거는 이상적 Boolean 연산입니다. 형상은 전달하지만 잔류물, 자연 산화막, 핵생성 지연 등 표면 화학 이력은 전달하지 않습니다. 작은 요철은 수치 오차일 수 있으며, 실제 거칠기로 해석하지 않습니다.</p><h3>직접 비교할 실험</h3><ol><li>기준 결과를 비교 고정하고 이온 방향성 지수만 500 → 20으로 변경</li><li>ALD 노출 시간만 0.05 → 0.001 s로 변경</li><li>격자·입자 수·시드를 따로 바꾸어 결과 차이의 수치 민감도 확인</li></ol><p>원본 JSON에 모든 조건, 버전, 코드 해시 및 단계별 단면을 저장합니다. SVG는 현재 계산 단면이며 측정 사진이 아닙니다.</p><a href="https://github.com/TRX1200/pse-process-recovery-lab/blob/main/docs/NATIVE_SEQUENCE_KR.md" target="_blank" rel="noreferrer">모델과 재현 설명서</a></div>}
        {(page==='section'||page==='charts')&&<div className="seq-playback"><button disabled={stage==='strip'||active} aria-label={playing?'공정 이력 일시정지':'공정 이력 재생'} onClick={()=>{if(index>=selected.frames.length-1)setIndex(0);setPlaying(!playing);}}>{playing?<Pause size={15}/>:<Play size={15}/>}</button><input aria-label="연속공정 프레임" type="range" min="0" max={selected.frames.length-1} value={index} disabled={stage==='strip'||active} onChange={e=>{setPlaying(false);setIndex(Number(e.target.value));}}/><output>{stage==='strip'?'즉시 제거':`${frame.at.toFixed(stage==='etch'?2:0)} ${selected.axis_unit}`}</output></div>}
      </div>
      <aside className="seq-controls"><h2>다음 계산 조건</h2><nav>{Object.entries(GROUPS).map(([key,label])=><button key={key} aria-pressed={key===group} onClick={()=>setGroup(key as keyof typeof GROUPS)}>{label}</button>)}</nav><div className="seq-fields">{fields.filter(f=>f.group===group).map(f=><label key={f.key}><span>{f.label}<small>{f.unit}</small></span><input type="number" aria-label={f.label} disabled={active||loading} min={f.min} max={f.max} step={f.integer?1:'any'} value={Number.isFinite(params[f.key])?params[f.key]:''} onChange={e=>setParams({...params,[f.key]:e.target.value===''?NaN:Number(e.target.value)})}/><small>{f.description}</small></label>)}</div></aside>
    </div>
    <footer className="seq-footer"><span>2D 물리 모델 · 실측 미보정 · 소자 전기 특성 제외</span><span>{run.run_hash.slice(0,10)} · {run.elapsed_s.toFixed(1)} s 계산</span></footer>
    {run.warnings.length>0&&<p className="seq-warning">{run.warnings.join(' ')}</p>}
  </section>;
}
