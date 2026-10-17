import {useEffect,useMemo,useRef,useState} from 'react';
import {Play,Pause,Download,History,FolderOpen,X,Square,Target,Plus,ZoomIn,ZoomOut,Scan,SkipBack,SkipForward} from 'lucide-react';
import {NativeViewport} from './NativeViewport';
import {Chart} from './Chart';
import {ALDExperiments} from './ALDExperiments';
import {SequenceSettings} from './SequenceSettings';
import {SequencePractice} from './SequencePractice';
import {SequenceCompare} from './SequenceCompare';
import {SequenceRecipeLibrary} from './SequenceRecipeLibrary';
import {Modal} from './Modal';
import {useSequenceNotebook} from '../useSequenceNotebook';
import {summarizeRun,appendAttempt,targetProblem} from '../sequencePractice';
import type {Targets,PracticeScope,SavedSequenceRecipe} from '../sequencePractice';
import {isLocalWorkbench,nativeRequest,publicNativeJson,NATIVE_METRICS} from '../native';
import {exportJson,download} from '../storage';
import {STAGES,inputProblem,recipeInputs,sameInputs,sequenceCharts,stageRun} from '../sequence';
import type {ALDRecipe,ALDRecipeCatalog,SequenceJob,SequenceRun,SequenceSchema,SequenceStage} from '../sequence';
import type {NativeParameter} from '../native';
import type {Params} from '../types';
import '../sequence.css';
import '../sequenceStudio.css';

const CASES=[['reference','기준 공정'],['short-pulse','짧은 ALD 노출'],['wide-angle','넓은 이온 입사각']] as const;
const EMPTY:number[][][]=[];

export function SequenceWorkbench({setBusy}:{setBusy:(v:boolean)=>void}){
  const {notebook,updateNotebook,storageError}=useSequenceNotebook();
  const practice=notebook.sessions.find(s=>s.id===notebook.activeId);
  const pendingRef=useRef(notebook.pending);
  const [note,setNote]=useState('');
  const [fields,setFields]=useState<NativeParameter[]>([]);
  const [run,setRun]=useState<SequenceRun|null>(null);
  const [reference,setReference]=useState<SequenceRun|null>(null);
  const [params,setParams]=useState<Params>({});
  const [stage,setStage]=useState<SequenceStage>('ald');
  const [page,setPage]=useState<'section'|'charts'|'recipes'|'model'|'practice'|'compare'>('section');
  const [recipes,setRecipes]=useState<ALDRecipeCatalog|null>(null),[recipeError,setRecipeError]=useState('');
  const [recipeId,setRecipeId]=useState('D01');
  const [mobile,setMobile]=useState<'result'|'setup'>('setup');
  const [utility,setUtility]=useState<'export'|'history'|'examples'|'library'|null>(null);
  const [zoom,setZoom]=useState(1),[speed,setSpeed]=useState(1);
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
  const currentRecord=useMemo(()=>run?summarizeRun(run,recorded?'example':'local',new Date().toISOString()):null,[run,recorded]);
  const runProblem=problem||(notebook.pending&&!active?'이전 계산을 먼저 재연결하세요.':null);

  function accept(result:SequenceRun,isRecorded:boolean){
    setRun(result);setParams(result.request.params);setStage('ald');
    setIndex(result.ald.frames.length-1);setPlaying(false);setRecorded(isRecorded);setJob(null);
  }
  useEffect(()=>{
    let alive=true;
    void Promise.all([publicNativeJson<SequenceSchema>('schema'),publicNativeJson<SequenceRun>('sequence-reference')])
      .then(([schema,result])=>{if(alive){setFields(schema.models.sequence.params);accept(result,true);
        if(isLocalWorkbench()&&pendingRef.current){setJob({id:pendingRef.current.jobId,model:'sequence',state:'queued',progress:0});setBusy(true);}
      }})
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
    }),500/speed);
    return()=>clearInterval(timer);
  },[playing,selected,active,speed]);
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
          const pending=pendingRef.current;
          if(pending?.jobId===status.id){
            const record=summarizeRun(result,'local',new Date().toISOString());
            updateNotebook(previous=>({...appendAttempt(previous,pending.sessionId,record,status.id,pending.note),pending:undefined}));
            pendingRef.current=undefined;setNote('');
          }
          accept(result,false);setBusy(false);
        }else if(status.state==='failed'||status.state==='cancelled'){
          pendingRef.current=undefined;updateNotebook(previous=>({...previous,pending:undefined}));
          setJob(status);setBusy(false);if(status.error)setError(status.error);
        }else{setJob(status);timer=setTimeout(poll,800);}
      }catch(e){if(!disposed){setError(`상태 확인 실패: ${String(e)}. 실행 기록에서 다시 확인하세요.`);setJob(null);setBusy(false);}}
    }
    timer=setTimeout(poll,400);
    return()=>{disposed=true;clearTimeout(timer);};
  },[job?.id,active,setBusy]);

  async function loadCase(name:string){
    setLoading(true);setPlaying(false);setError('');
    try{accept(await publicNativeJson<SequenceRun>(`sequence-${name}`),true);setPage('section');setMobile('result');}
    catch(e){setError(String(e));}finally{setLoading(false);}
  }
  async function execute(){
    if(active||!available||runProblem)return;
    setError('');setSubmitting(true);setPlaying(false);setPage('section');setMobile('result');setBusy(true);
    try{
      const submitted=await nativeRequest<SequenceJob>('jobs',{model:'sequence',params});
      if(practice){
        const pending={jobId:submitted.id,sessionId:practice.id,note};pendingRef.current=pending;
        updateNotebook(previous=>({...previous,pending}));
      }
      setJob(submitted);
    }
    catch(e){setError(String(e));setBusy(false);}finally{setSubmitting(false);}
  }
  async function cancel(){
    if(!job)return;
    try{setJob(await nativeRequest<SequenceJob>(`jobs/${job.id}/cancel`,{}));pendingRef.current=undefined;updateNotebook(previous=>({...previous,pending:undefined}));setBusy(false);}
    catch(e){setError(String(e));}
  }
  async function loadHistory(){
    setUtility('history');
    try{setHistory((await nativeRequest<{jobs:SequenceJob[]}>('jobs')).jobs.filter(j=>j.model==='sequence'));}
    catch(e){setError(String(e));}
  }
  async function openHistory(id:string){
    setLoading(true);
    try{accept(await nativeRequest<SequenceRun>(`jobs/${id}/result`),false);setHistory([]);setUtility(null);setPage('section');setMobile('result');}
    catch(e){setError(String(e));}finally{setLoading(false);}
  }
  function chooseStage(next:SequenceStage){
    setStage(next);setPlaying(false);setChart(0);setZoom(1);
    if(run)setIndex(stageRun(run,next).frames.length-1);
  }
  function applyRecipe(recipe:ALDRecipe){
    if(active||loading||practice)return;
    try{
      setParams(recipeInputs(recipe,fields));setRecipeId(recipe.id);chooseStage('ald');setMobile('setup');setError('');
    }catch(e){setError(String(e));}
  }
  function startPractice(title:string,scope:PracticeScope,targets:Targets){
    if(active||notebook.pending||practice||targetProblem(targets))return;
    const id=crypto.randomUUID();
    updateNotebook(previous=>({...previous,activeId:id,sessions:[...previous.sessions,
      {id,title,scope,targets:{...targets},started:new Date().toISOString(),attempts:[]}]}));
    setNote('');setPage('section');setMobile('setup');chooseStage(scope==='etch'?'etch':'ald');
  }
  function finishPractice(){
    if(active||notebook.pending)return;
    updateNotebook(previous=>({...previous,activeId:null,sessions:previous.sessions.map(s=>s.id===previous.activeId?{...s,ended:new Date().toISOString()}:s)}));
  }
  function saveRecipe(name:string,recipeNote:string){
    if(problem||active)return;
    updateNotebook(previous=>previous.recipes.length>=30?previous:{...previous,recipes:[...previous.recipes,
      {id:crypto.randomUUID(),name,note:recipeNote,params:{...params},created:new Date().toISOString()}]});
  }
  function loadRecipe(recipe:SavedSequenceRecipe){
    try{
      const values=recipeInputs({request:{model:'sequence',params:recipe.params}} as ALDRecipe,fields);
      setParams(values);setUtility(null);setMobile('setup');setError('');
    }catch(e){setError(String(e));}
  }
  function addComparison(){
    if(!currentRecord)return;
    updateNotebook(previous=>previous.comparisons.length>=6||previous.comparisons.some(r=>r.hash===currentRecord.hash)?previous:
      {...previous,comparisons:[...previous.comparisons,currentRecord]});
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
    <header className="seq-header"><div><h1>공정 실험실</h1><span className="seq-subtitle">Si 식각 → Strip → Al₂O₃ ALD</span></div>
      <div className="seq-utilities"><span className="seq-connection" data-online={available}><i/>{available?'로컬 엔진 준비':'공개 예제 뷰어'}</span><button aria-label="계산 예제" title="계산 예제" disabled={active||loading} onClick={()=>setUtility('examples')}><FolderOpen size={15}/></button>{available&&<button aria-label="실행 기록" title="실행 기록" disabled={active||loading} onClick={()=>void loadHistory()}><History size={15}/></button>}<button aria-label="결과 저장" title="결과 저장" disabled={active||loading} onClick={()=>setUtility('export')}><Download size={15}/></button>{active?<button className="seq-header-run" onClick={()=>void cancel()}><Square size={14}/>중단</button>:<button className="seq-header-run" disabled={!available||loading||!!runProblem} onClick={()=>void execute()}><Play size={15}/>Run Simulation</button>}</div></header>
    {storageError&&<p className="seq-warning" role="alert">{storageError}<button onClick={()=>exportJson('process-notebook-recovery.json',notebook)}>기록 JSON</button></p>}
    {notebook.pending&&!active&&<p className="seq-warning"><button onClick={()=>{setJob({id:notebook.pending!.jobId,model:'sequence',state:'queued',progress:0});setBusy(true);setError('');}}>이전 계산 재연결</button></p>}
    {(error||problem)&&<p className="seq-warning" role="alert">{error||problem}</p>}
    {active?<div className="seq-notice">새 계산 {Math.round((job?.progress??0)*100)}% · {job?.last_frame?.stage??'준비'} · 화면은 직전 완료 결과입니다.<progress max="1" value={job?.progress??0}/></div>:
      stale?<p className="seq-notice" data-stale="true">입력 변경됨 · 화면은 직전 완료 결과입니다. Run Simulation으로 새 조건을 계산하세요.</p>:
      <p className="seq-notice">{recorded?'저장된 Python 계산':'이번 로컬 계산'} · Etch {run.request.params.duration_s} s → 이상적 Strip → ALD {run.request.params.cycles} cycles / 노출 {run.request.params.pulse_s} s{!available?' · 새 조건 계산은 로컬 Python 서버에서 가능합니다.':''}</p>}
    <nav className="seq-mobile" aria-label="작업 화면"><button aria-pressed={mobile==='setup'} onClick={()=>setMobile('setup')}>조건 조절</button><button aria-pressed={mobile==='result'&&page!=='practice'} onClick={()=>{setMobile('result');if(page==='practice')setPage('section');}}>단면 / 결과</button><button aria-pressed={mobile==='result'&&page==='practice'} onClick={()=>{setMobile('result');setPage('practice');setPlaying(false);}}>연습 과제</button></nav>
    <div className="seq-layout">
      <SequenceSettings fields={fields} params={params} baseline={run.request.params} recipes={recipes} locked={active||loading} active={active} available={available} problem={runProblem} training={!!practice}
        onChange={(key,value)=>setParams(previous=>({...previous,[key]:value}))} onRecipe={applyRecipe}
        onRestore={()=>{setParams({...run.request.params});setError('');}} onRun={()=>void execute()} onCancel={()=>void cancel()}
        onLibrary={()=>setUtility('library')} onExperiments={()=>{setPage('recipes');setMobile('result');setPlaying(false);}}/>
      <div className="seq-result"><div className="seq-result-top"><nav className="seq-stage-tabs" aria-label="공정 단계">{STAGES.map((s,i)=><button key={s.key} aria-pressed={stage===s.key} onClick={()=>{chooseStage(s.key);if(page==='recipes'||page==='model')setPage('section');}}><span>0{i+1}</span>{s.name}</button>)}</nav><div className="seq-compare"><button disabled={active||loading} onClick={()=>setReference(run)} title="지금 표시된 완료 결과를 비교 기준으로 고정">현재 결과 비교 고정</button>{reference&&<button aria-label="비교 해제" onClick={()=>setReference(null)}><X size={13}/></button>}</div></div>
        <div className="seq-mission-bar"><Target size={16}/><div><strong>{practice?practice.title:'이번 실험의 목표를 정해보세요'}</strong><span>{practice?`${practice.attempts.length}회 시도 · 목표 고정 · 정답 레시피 없음`:'식각·ALD 과제에 도전하고, 시도별 결과를 기록하세요.'}</span></div><button onClick={()=>{setPage('practice');setPlaying(false);}}>{practice?'과제 / 채점':'과제 만들기'}<Plus size={13}/></button></div>
        <nav className="seq-pages" aria-label="물리 연속공정 결과">{([['section','단면'],['charts','분석'],['practice','연습 과제'],['compare','비교표'],['recipes','실험 안내'],['model','모델']] as const).map(([key,label])=><button key={key} aria-pressed={page===key} onClick={()=>{setPage(key);setPlaying(false);}}>{label}{key==='compare'&&notebook.comparisons.length>0&&<small>{notebook.comparisons.length}</small>}</button>)}</nav>
        {page==='practice'&&currentRecord&&<SequencePractice practice={practice} sessions={notebook.sessions} current={currentRecord} locked={active||loading||!!notebook.pending} onStart={startPractice} onFinish={finishPractice} note={note} onNote={setNote} onInputs={()=>{setMobile('setup');setPage('section');}}/>}
        {page==='compare'&&currentRecord&&<SequenceCompare current={currentRecord} records={notebook.comparisons} fields={fields} onAdd={addComparison} onRemove={hash=>updateNotebook(previous=>({...previous,comparisons:previous.comparisons.filter(r=>r.hash!==hash)}))}/>}
        {page==='recipes'&&<ALDExperiments catalog={recipes} fields={fields} params={params} resultParams={run.request.params} disabled={active||loading||!!practice} error={practice?'과제 진행 중에는 예제 조건 적용을 잠급니다. 왼쪽에서 직접 조절하세요.':recipeError} selected={recipeId} onSelect={setRecipeId} onApply={applyRecipe}/>}
        {page==='section'&&<div className="seq-section"><div className="seq-view-options"><strong>{STAGES.find(s=>s.key===stage)!.name}</strong><label><input type="checkbox" checked={mesh} onChange={e=>setMesh(e.target.checked)}/>표면점</label><label><input type="checkbox" checked={initial} onChange={e=>setInitial(e.target.checked)}/>시작선</label><div className="seq-zoom"><button aria-label="단면 축소" disabled={zoom<=.75} onClick={()=>setZoom(v=>Math.max(.75,v-.25))}><ZoomOut size={14}/></button><button aria-label="단면 배율 초기화" onClick={()=>setZoom(1)}>{Math.round(zoom*100)}%</button><button aria-label="단면 확대" disabled={zoom>=2} onClick={()=>setZoom(v=>Math.min(2,v+.25))}><ZoomIn size={14}/></button><button aria-label="단면 맞춤" onClick={()=>setZoom(1)}><Scan size={14}/></button></div></div>
          <div className="seq-canvas"><NativeViewport run={selected} frame={frame} reference={comparative} initial={initial} mesh={mesh} zoom={zoom} target={EMPTY} particles={false} playing={false} boundsFrames={bounds}/></div>
          <div className="seq-legend"><span><i className="si"/>Si</span>{stage==='etch'&&<span><i className="mask"/>유효 마스크</span>}{stage==='ald'&&<span><i className="film"/>Al₂O₃</span>}{reference&&<span>파란 점선: 고정한 결과</span>}</div>
          <div className="seq-metrics">{metricKeys.map(key=>{const value=key==='bottom_top_pct'&&(frame.metrics.top_film_nm??0)<=1e-6?null:frame.metrics[key];return <div key={key}><span>{NATIVE_METRICS[key]?.[0]??key}</span><strong>{value==null?'—':value.toFixed(2)}<small>{NATIVE_METRICS[key]?.[1]}</small></strong></div>;})}</div>
          {stage==='ald'&&(frame.metrics.top_film_nm??0)>0&&(frame.metrics.top_film_nm??0)<2*run.request.params.grid_nm&&<p className="seq-warning">막 두께가 2격자보다 작습니다. 정량 해석 전 격자를 줄여 비교하세요.</p>}
        </div>}
        {page==='charts'&&<div className="seq-scroll"><nav className="seq-chart-tabs">{charts.map((c,i)=><button key={c.key} aria-pressed={chart===i} onClick={()=>setChart(i)}>{c.title}</button>)}</nav><Chart series={charts[chart]??charts[0]} baseline={baselineCharts[chart]} baselineLabel="고정한 비교" time={stage==='strip'?undefined:frame.at}/><p className="seq-small">{stage==='strip'?'마스크 제거에는 시간 모델이 없습니다. 여기서는 앞선 식각 이력을 표시합니다.':'곡선은 해당 단계의 계산 이력입니다. 초와 사이클은 서로 다른 축입니다.'} {reference?'점선은 고정한 비교 결과입니다.':''}</p></div>}
        {page==='model'&&<div className="seq-scroll seq-model"><h2>형상은 어떻게 계산하나</h2><p>Etch: 입사 이온·F·O 수송 → 표면 피복과 제거 속도 → Level-set 경계 이동</p><p>ALD: TMA 수송·재반사 → 자리 피복률 → GPC × 피복률 × 사이클 → 경계 이동</p><code>∂φ/∂t + Vn |∇φ| = 0</code><code>dθ/dt = [Γ β (1 − θ) − Γev θ] / Nsites</code><h3>이번 구현의 경계</h3><p>Si/SF₆–O₂와 Al₂O₃ 제한 반응 모델을 연결했습니다. HfO₂/TiN/GAA의 화학 모델, 챔버 플라즈마, 도핑 및 I–V 계산은 포함하지 않습니다.</p><p>마스크 제거는 이상적 Boolean 연산입니다. 형상은 전달하지만 잔류물, 자연 산화막, 핵생성 지연 등 표면 화학 이력은 전달하지 않습니다. 작은 요철은 수치 오차일 수 있으며, 실제 거칠기로 해석하지 않습니다.</p><h3>직접 비교할 실험</h3><ol><li>기준 결과를 비교 고정하고 이온 방향성 지수만 500 → 20으로 변경</li><li>ALD 노출 시간만 0.05 → 0.001 s로 변경</li><li>격자·입자 수·시드를 따로 바꾸어 결과 차이의 수치 민감도 확인</li></ol><p>원본 JSON에 모든 조건, 버전, 코드 해시 및 단계별 단면을 저장합니다. SVG는 현재 계산 단면이며 측정 사진이 아닙니다.</p><a href="https://github.com/TRX1200/pse-process-recovery-lab/blob/main/docs/NATIVE_SEQUENCE_KR.md" target="_blank" rel="noreferrer">모델과 재현 설명서</a></div>}
        {(page==='section'||page==='charts')&&<div className="seq-playback"><button disabled={stage==='strip'||active||index===0} aria-label="이전 프레임" onClick={()=>{setPlaying(false);setIndex(i=>Math.max(0,i-1));}}><SkipBack size={14}/></button><button disabled={stage==='strip'||active} aria-label={playing?'공정 이력 일시정지':'공정 이력 재생'} onClick={()=>{if(index>=selected.frames.length-1)setIndex(0);setPlaying(!playing);}}>{playing?<Pause size={15}/>:<Play size={15}/>}</button><button disabled={stage==='strip'||active||index===selected.frames.length-1} aria-label="다음 프레임" onClick={()=>{setPlaying(false);setIndex(i=>Math.min(selected.frames.length-1,i+1));}}><SkipForward size={14}/></button><input aria-label="연속공정 프레임" type="range" min="0" max={selected.frames.length-1} value={index} disabled={stage==='strip'||active} onChange={e=>{setPlaying(false);setIndex(Number(e.target.value));}}/><output>{stage==='strip'?'즉시 제거':`${frame.at.toFixed(stage==='etch'?2:0)} ${selected.axis_unit}`}</output><select aria-label="이력 재생 속도" value={speed} onChange={e=>setSpeed(Number(e.target.value))}><option value={.5}>0.5×</option><option value={1}>1×</option><option value={2}>2×</option></select></div>}
      </div>
    </div>
    <footer className="seq-footer"><span>2D 모델 · 실측 미보정 · 소자 전기 특성 제외</span><span>{run.handoff.si_contour_preserved?'Si 형상 전달 확인':'형상 확인 필요'} · {run.run_hash.slice(0,10)} · {run.elapsed_s.toFixed(1)} s</span></footer>
    {run.warnings.length>0&&<p className="seq-warning">{run.warnings.join(' ')}</p>}
    {utility==='library'&&<Modal title="내 레시피" onClose={()=>setUtility(null)}><SequenceRecipeLibrary recipes={notebook.recipes} locked={active||loading} problem={problem} onSave={saveRecipe} onLoad={loadRecipe}/></Modal>}
    {utility&&utility!=='library'&&<Modal title={utility==='export'?'계산 결과 저장':utility==='history'?'실행 기록':'저장된 계산 예제'} onClose={()=>setUtility(null)}>
      <div className="seq-utility-content">{utility==='export'?<><p>현재 표시된 완료 결과를 저장합니다. 변경한 입력은 새 계산 후 결과에 반영됩니다.</p><button onClick={()=>exportJson(`process-${run.run_hash.slice(0,8)}.json`,run)}>결과 JSON</button><button disabled={page!=='section'} onClick={saveSvg}>단면 SVG</button><button onClick={saveCsv}>지표 CSV</button>{page!=='section'&&<small>단면 SVG는 ‘계산 단면’ 탭에서 저장하세요.</small>}</>:utility==='history'?<>{history.length===0?<p>표시할 실행 기록이 없습니다.</p>:history.map(h=><button key={h.id} disabled={h.state!=='complete'||loading} onClick={()=>void openHistory(h.id)}>{h.id.slice(0,8)} · {h.state}</button>)}</>:<><p>아래 항목은 이미 계산한 결과입니다. 새 증착 조건은 왼쪽 레시피에서 고르세요.</p>{CASES.map(([key,label])=><button key={key} onClick={()=>{setUtility(null);void loadCase(key);}}>{label}</button>)}</>}</div>
    </Modal>}
  </section>;
}
