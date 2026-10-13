import {useEffect,useMemo,useRef,useState} from 'react';
import {ArrowDown,ArrowLeft,ArrowRight,ArrowUp,Check,Download,Layers3,LoaderCircle,Play,Plus,RotateCcw,Trash2,Upload} from 'lucide-react';
import {Chart} from './Chart';
import {FlowViewport} from './FlowViewport';
import {decodeGrid,lineCut,newStep,parseRecipe,recipeKey,recipeProblem,STEP_FIELDS,STEP_HELP,STEP_LABELS,thresholdSegments,virtualSEM} from '../flow';
import type {FlowRecipe,FlowRun,FlowSchema,FlowStep,StepKind} from '../flow';
import {download,exportJson} from '../storage';
import {isLocalWorkbench} from '../native';
import '../flow.css';

type Panel='section'|'metrology'|'trends'|'model';
const SESSION='process-flow-draft.v1';
const publicFile=<T,>(name:string)=>fetch(`${import.meta.env.BASE_URL}flow/${name}.json`).then(async r=>{if(!r.ok)throw new Error('예제 파일을 읽지 못했습니다.');return r.json() as Promise<T>;});

export function FlowWorkbench({setBusy}:{setBusy:(busy:boolean)=>void}){
  const [schema,setSchema]=useState<FlowSchema|null>(null),[recipe,setRecipe]=useState<FlowRecipe|null>(null),[run,setRun]=useState<FlowRun|null>(null);
  const [available,setAvailable]=useState(false),[busy,setWorking]=useState(false),[error,setError]=useState('');
  const [frameIndex,setFrame]=useState(0),[selected,setSelected]=useState(0),[panel,setPanel]=useState<Panel>('section');
  const [inspector,setInspector]=useState<'step'|'domain'|'add'>('step'),[mobilePane,setMobilePane]=useState<'view'|'steps'|'settings'>('view');
  const [preset,setPreset]=useState('gaa'),[fit,setFit]=useState(true),[sem,setSem]=useState(false);
  const [axis,setAxis]=useState<'horizontal'|'vertical'>('horizontal'),[probe,setProbe]=useState(20);
  const [sigma,setSigma]=useState(2),[noise,setNoise]=useState(.02),[threshold,setThreshold]=useState(.25);
  const [measurementPage,setMeasurementPage]=useState<'dimension'|'sem'>('dimension');
  const [target,setTarget]=useState(100),[tolerance,setTolerance]=useState(4),[targetMaterial,setTargetMaterial]=useState(1);
  const upload=useRef<HTMLInputElement>(null),viewport=useRef<HTMLDivElement>(null),loadId=useRef(0);
  useEffect(()=>{let alive=true;
    void Promise.all([publicFile<FlowSchema>('schema'),publicFile<FlowRun>('gaa')]).then(([s,r])=>{
      if(!alive)return;setSchema(s);setRun(r);setFrame(r.frames.length-1);setSelected(r.request.steps.length-1);
      let draft:FlowRecipe|null=null;
      try{const raw=sessionStorage.getItem(SESSION);if(raw)draft=parseRecipe(raw);}catch{setError('저장된 입력을 읽지 못해 GAA 예제로 시작합니다.');}
      setRecipe(draft??{name:r.request.name,domain:r.request.domain,steps:r.request.steps});
    }).catch(e=>{if(alive)setError(String(e));});
    if(isLocalWorkbench())void fetch('/api/flow/schema').then(async r=>{if(r.ok){const s=await r.json();if(alive&&s.version?.startsWith('process-flow-'))setAvailable(true);}}).catch(()=>{});
    return ()=>{alive=false;loadId.current++;};
  },[]);
  useEffect(()=>{if(!recipe||recipeProblem(recipe))return;try{sessionStorage.setItem(SESSION,JSON.stringify(recipe));}catch{setError('입력 임시 저장이 제한됐습니다. 레시피 JSON으로 내보내 주세요.');}},[recipe]);
  const pending=!!run&&!!recipe&&recipeKey(recipe)!==recipeKey(run.request);
  const frame=run?.frames[Math.min(frameIndex,run.frames.length-1)];
  const grid=useMemo(()=>run&&frame?decodeGrid(run,frame):null,[run,frame]);
  const signal=useMemo(()=>run&&grid?virtualSEM(run,grid,sigma,noise):null,[run,grid,sigma,noise]);
  const cut=useMemo(()=>run&&grid?lineCut(run,grid,axis,probe):null,[run,grid,axis,probe]);
  const lineSignal=useMemo(()=>{
    if(!run||!signal||!cut)return [];
    const [ny,nx]=run.shape,d=run.request.domain;
    const index=Math.round((cut.coordinate-(axis==='horizontal'?d.bottom_nm:-d.width_nm/2))/d.grid_nm-.5);
    return Array.from({length:axis==='horizontal'?nx:ny},(_,i)=>signal[axis==='horizontal'?index*nx+i:i*nx+index]);
  },[run,signal,cut,axis]);
  const widths=useMemo(()=>run&&cut?thresholdSegments(cut.x,lineSignal,threshold,run.request.domain.grid_nm):[],[run,cut,lineSignal,threshold]);
  async function choosePreset(id:string){
    const current=++loadId.current;setWorking(true);setBusy(true);setError('');
    try{const r=await publicFile<FlowRun>(id);if(current!==loadId.current)return;setRun(r);setRecipe({name:r.request.name,domain:r.request.domain,steps:r.request.steps});setFrame(r.frames.length-1);setSelected(r.request.steps.length-1);setPreset(id);setPanel('section');setInspector('step');}
    catch(e){setError(String(e));}finally{setWorking(false);setBusy(false);}
  }
  async function execute(stop:number){
    if(!recipe||!available||busy)return;const problem=recipeProblem(recipe);if(problem){setError(problem);return;}
    setWorking(true);setBusy(true);setError('');
    try{const response=await fetch('/api/flow/simulate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...recipe,stop_after:stop})});
      const data=await response.json();if(!response.ok)throw new Error(data.error??'계산 실패');
      const r=data as FlowRun;setRun(r);setFrame(r.frames.length-1);setSelected(Math.max(0,stop-1));setMobilePane('view');
    }catch(e){setError(String(e));}finally{setWorking(false);setBusy(false);}
  }
  function editStep(changes:Partial<FlowStep>){setRecipe(r=>r?{...r,steps:r.steps.map((s,i)=>i===selected?{...s,...changes}:s)}:r);}
  function moveStep(direction:number){if(!recipe)return;const other=selected+direction;if(other<0||other>=recipe.steps.length)return;
    const steps=[...recipe.steps];[steps[selected],steps[other]]=[steps[other],steps[selected]];setRecipe({...recipe,steps});setSelected(other);}
  function showFrame(index:number){setFrame(index);if(index>0)setSelected(index-1);}
  function saveSVG(){
    if(!run||!frame)return;const original=viewport.current?.querySelector('svg');if(!original)return;
    const svg=original.cloneNode(true) as SVGElement;svg.setAttribute('xmlns','http://www.w3.org/2000/svg');
    const metadata=document.createElementNS('http://www.w3.org/2000/svg','metadata');metadata.textContent=JSON.stringify({config_hash:run.config_hash,frame:frame.index,sem:sem&&panel==='metrology',sigma_nm:sigma,noise_sigma:noise,seed:42,geometry:'grid cells',assumptions:run.assumptions});svg.prepend(metadata);
    download(`flow-${run.config_hash.slice(0,10)}-step${frame.index}.svg`,new XMLSerializer().serializeToString(svg),'image/svg+xml');
  }
  function saveCSV(){if(!run||!frame||!cut)return;
    const rows=['config_hash,frame,state_hash,axis,cut_nm,position_nm,material,sem_intensity,psf_sigma_nm,noise_sigma,seed,threshold,target_material,target_nm,tolerance_nm,grid_nm'];
    cut.x.forEach((v,i)=>rows.push([run.config_hash,frame.index,frame.state_hash,axis,cut.coordinate,v,run.materials.find(m=>m.id===cut.ids[i])?.name,lineSignal[i],sigma,noise,42,threshold,targetMaterial,Number.isFinite(target)?target:'',Number.isFinite(tolerance)?tolerance:'',run.request.domain.grid_nm].join(',')));
    download(`flow-cut-${frame.index}.csv`,'\uFEFF'+rows.join('\n'),'text/csv;charset=utf-8');
  }
  if(!schema||!recipe||!run||!frame||!cut)return <div className="flow-loading">{error||'연속공정 작업 화면을 준비합니다…'}</div>;
  const step=recipe.steps[selected],problem=recipeProblem(recipe),d=run.request.domain;
  const measured=cut.segments.filter(s=>s.material===targetMaterial);
  const match=Number.isFinite(target)&&Number.isFinite(tolerance)&&target>=0&&tolerance>=0&&measured.length===1?Math.abs(measured[0].width_nm-target)<=tolerance:null;
  const selectedFields=step?STEP_FIELDS[step.kind]:[];
  return <section className="flow-workbench" aria-label="연속공정 작업 공간" data-mobile-pane={mobilePane}>
    <div className="flow-toolbar">
      <label className="flow-preset"><span className="sr-only">공정 예제</span><select aria-label="공정 예제" value={preset} disabled={busy} onChange={e=>void choosePreset(e.target.value)}>{schema.presets.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
      <button disabled={busy||recipe.steps.length>=24} onClick={()=>{setInspector('add');setMobilePane('settings');}}><Plus size={16}/>공정 추가</button>
      <div className="flow-button-pair"><button disabled={busy||frame.index===0} onClick={()=>showFrame(frame.index-1)}><ArrowLeft size={16}/>이전 단계</button><button disabled={busy||!!problem||(!pending&&frame.index>=recipe.steps.length)||(!available&&(pending||frame.index>=run.frames.length-1))} onClick={()=>{if(!pending&&frame.index<run.frames.length-1)showFrame(frame.index+1);else void execute(Math.min(recipe.steps.length,frame.index+1));}}><ArrowRight size={16}/>다음 단계</button></div>
      <button className="flow-primary" disabled={!available||busy||!!problem} onClick={()=>void execute(recipe.steps.length)}>{busy?<LoaderCircle size={16} className="spin"/>:<Play size={16}/>}전체 실행</button>
      <button disabled={busy||!!problem} onClick={()=>exportJson('process-flow-recipe.json',{format:'process-flow-recipe-v1',recipe})}><Download size={15}/>레시피</button>
      <button disabled={busy} onClick={()=>upload.current?.click()}><Upload size={15}/>불러오기</button>
      <input type="file" ref={upload} hidden accept=".json,application/json" onChange={async e=>{const file=e.target.files?.[0];e.target.value='';if(!file)return;try{if(file.size>128*1024)throw new Error('레시피 JSON은 128 KB 이하여야 합니다.');setRecipe(parseRecipe(await file.text()));setSelected(0);setInspector('step');setError('');}catch(err){setError(String(err));}}}/>
      <button className="flow-domain-toggle" aria-pressed={inspector==='domain'} onClick={()=>{setInspector(inspector==='domain'?'step':'domain');setMobilePane('settings');}}>계산 영역</button>
    </div>
    {!available&&<div className="flow-banner">저장된 계산 예제 · 단계와 계측을 살펴볼 수 있습니다. 새 조건 실행은 최신 로컬 RF 서버가 필요합니다.</div>}
    {error&&<div className="flow-banner error" role="alert">{error}<button aria-label="오류 닫기" onClick={()=>setError('')}>×</button></div>}
    {pending&&<div className="flow-banner" role="status">입력이 변경됐습니다. 화면은 이전 계산 결과입니다. 전체 실행 또는 선택 단계까지 실행하면 새 조건을 반영합니다.</div>}
    <nav className="flow-mobile-nav" aria-label="작업 패널">{([['steps','공정 순서'],['view','단면 / 계측'],['settings','조건 설정']] as const).map(([key,label])=><button key={key} aria-pressed={mobilePane===key} onClick={()=>setMobilePane(key)}>{label}</button>)}</nav>
    <div className="flow-layout">
      <aside className="flow-sequence">
        <header><h2>Process flow</h2><span>{recipe.steps.length} steps</span></header>
        <div className="flow-step-list"><button className="flow-substrate" aria-pressed={frame.index===0} onClick={()=>showFrame(0)}><Layers3 size={17}/><span>Si 기판<small>초기 상태</small></span></button>
          {recipe.steps.map((s,i)=><button key={s.id} className="flow-step" aria-pressed={selected===i} onClick={()=>{setSelected(i);setInspector('step');if(!pending&&i+1<run.frames.length)setFrame(i+1);}}><span className={`flow-step-dot ${!pending&&i<run.frames.length-1?'complete':''}`}>{!pending&&i<run.frames.length-1?<Check size={11}/>:null}</span><span className="flow-step-number">{String(i+1).padStart(2,'0')}</span><span>{s.name}<small>{STEP_LABELS[s.kind]}</small></span></button>)}</div>
        <footer><span>선택 단계</span><div><button title="위로 이동" aria-label="공정 위로 이동" disabled={busy||selected===0||!step} onClick={()=>moveStep(-1)}><ArrowUp size={14}/></button><button title="아래로 이동" aria-label="공정 아래로 이동" disabled={busy||selected===recipe.steps.length-1||!step} onClick={()=>moveStep(1)}><ArrowDown size={14}/></button><button title="선택 단계 삭제" aria-label="선택 공정 삭제" disabled={busy||!step} onClick={()=>{setRecipe({...recipe,steps:recipe.steps.filter((_,i)=>i!==selected)});setSelected(Math.max(0,selected-1));}}><Trash2 size={14}/></button></div><p>각 단계는 앞 단계의 모든 재료와 형상을 이어받습니다.</p></footer>
      </aside>
      <div className="flow-center">
        <nav className="flow-tabs" aria-label="결과 보기">{([['section','단면'],['metrology','계측'],['trends','추이'],['model','모델']] as const).map(([key,label])=><button key={key} aria-selected={panel===key} onClick={()=>setPanel(key)}>{label}</button>)}<span>{frame.index===0?'초기 기판':`STEP ${String(frame.index).padStart(2,'0')}`} · {frame.name}</span></nav>
        <div className={`flow-content flow-content-${panel}`}>
          {(panel==='section'||panel==='metrology')&&<>
            <div className="flow-view-controls"><label><input type="checkbox" checked={fit} onChange={e=>setFit(e.target.checked)}/>형상 맞춤</label>{panel==='metrology'&&<label><input type="checkbox" checked={sem} onChange={e=>setSem(e.target.checked)}/>가상 SEM</label>}<span>{panel==='metrology'?'단면을 클릭해 계측 위치 이동':'재료 셀 원본 · x/z 동일 축척'}</span><button onClick={saveSVG}>SVG</button><button onClick={()=>exportJson(`flow-${run.config_hash.slice(0,10)}.json`,run)}>결과 JSON</button></div>
            <div className="flow-stage" ref={viewport}><FlowViewport run={run} frame={frame} signal={sem&&panel==='metrology'?signal??undefined:undefined} axis={axis} probe={cut.coordinate} showProbe={panel==='metrology'} onProbe={setProbe} fit={fit}/></div>
            {panel==='metrology'&&<div className="flow-cut-results"><div><h3>선택 위치의 재료 구간</h3><span>{axis==='horizontal'?'z':'x'} = {cut.coordinate.toFixed(1)} nm · 셀 간격 {d.grid_nm} nm</span><button onClick={saveCSV}>계측 CSV</button></div><div className="flow-cut-table"><table><thead><tr><th>재료</th><th>시작</th><th>끝</th><th>{axis==='horizontal'?'폭':'두께'}</th></tr></thead><tbody>{cut.segments.map((s,i)=><tr key={i}><td>{run.materials.find(m=>m.id===s.material)?.name}</td><td>{s.start_nm.toFixed(1)}</td><td>{s.end_nm.toFixed(1)}</td><td>{s.width_nm.toFixed(1)} nm</td></tr>)}</tbody></table></div></div>}
            {panel==='section'&&<><div className="flow-timeline" aria-label="계산 단계 선택">{run.frames.map(f=><button key={f.index} aria-current={f.index===frame.index?'step':undefined} title={f.name} onClick={()=>showFrame(f.index)}>{String(f.index).padStart(2,'0')}</button>)}</div><div className="flow-material-legend">{run.materials.filter(m=>m.id>0&&(frame.metrics.area_nm2[m.name]??0)>0).map(m=><span key={m.id}><i style={{background:m.color}}/>{m.name}</span>)}{frame.mask_columns.length>0&&<span><i style={{background:'#E6B2B0'}}/>투영 마스크</span>}</div></>}
          </>}
          {panel==='trends'&&<div className="flow-trends"><h2>공정 순서에 따른 변화</h2><p>가로축은 시간 대신 공정 단계입니다. 각 단계의 서로 다른 반응 시간을 합산하지 않습니다.</p><Chart series={{key:'flow-area',title:'재료별 단면적',x_label:'Step',y_label:'nm²',x:run.frames.map(f=>f.index),lines:run.materials.filter(m=>m.id>1&&run.frames.some(f=>f.metrics.area_nm2[m.name]>0)).map(m=>({name:m.name,values:run.frames.map(f=>f.metrics.area_nm2[m.name])}))}} staticLabel="2D 단면적"/><Chart series={{key:'flow-height',title:'최고 표면 높이',x_label:'Step',y_label:'nm',x:run.frames.map(f=>f.index),lines:[{name:'최고 높이',values:run.frames.map(f=>f.metrics.top_height_nm)}]}} staticLabel="z = 0 기준"/><table><thead><tr><th>단계</th><th>Si 연결 성분*</th><th>밀폐 공동 면적</th></tr></thead><tbody>{run.frames.map(f=><tr key={f.index}><td>{f.index}. {f.name}</td><td>{f.metrics.si_components_above_zero}</td><td>{f.metrics.enclosed_void_area_nm2.toFixed(0)} nm²</td></tr>)}</tbody></table><p>* z ≥ 0 영역의 Si 연결 성분 수입니다. 트랜지스터 수나 전기적 연결성의 판정이 아닙니다.</p></div>}
          {panel==='model'&&<div className="flow-model"><h2>공정 형상에서 소자 해석으로</h2><p>지금은 재료가 이어지는 <strong>2D 연속공정과 가상 계측</strong> 단계입니다. GAA 예제는 게이트를 가로지르는 단면으로, 채널의 양 끝 고정과 source/drain은 화면 밖의 미해석 영역입니다.</p><div className="flow-roadmap"><article><strong>현재 · 공정 구조</strong><p>다층 Si/SiGe, 패터닝, 선택 제거, 절연막·금속 코팅, spacer, 단계별 형상 및 계측.</p></article><article><strong>다음 · 소자 정의</strong><p>도핑·접촉·재료 상수·계면·메시를 정의하고 nMOS/pMOS와 3D GAA 구조를 검증해야 합니다.</p></article><article><strong>이후 · 전기적 해석</strong><p>Poisson·수송 방정식과 경계조건을 연결한 뒤 Id–Vg, 문턱전압, 누설 전류를 검증합니다. 현재 계산하지 않습니다.</p></article></div><h3>계산 규약과 모델 경계</h3><ul>{run.assumptions.map(a=><li key={a}>{a}</li>)}</ul><p>기존 ALD / Etch 탭의 ViennaPS 반응·수송 해석은 별도로 유지됩니다. 이 연속공정 경로는 단순한 재료 격자 모델이며 Silvaco TCAD와 동등한 기능·정확도를 주장하지 않습니다.</p><a href="https://github.com/TRX1200/pse-process-recovery-lab/blob/main/docs/PROCESS_FLOW_KR.md" target="_blank" rel="noreferrer">모델·검증·실습 안내 ↗</a></div>}
        </div>
      </div>
      <aside className="flow-inspector">
        {panel==='metrology'?<><header><h2>가상 계측</h2><span>Grid line cut</span></header><nav className="flow-measurement-tabs"><button aria-pressed={measurementPage==='dimension'} onClick={()=>setMeasurementPage('dimension')}>치수 / 목표</button><button aria-pressed={measurementPage==='sem'} onClick={()=>{setMeasurementPage('sem');setSem(true);}}>SEM 신호</button></nav><div className="flow-inspector-body">
          {measurementPage==='dimension'&&<>
          <label>절단 방향<select aria-label="계측 방향" value={axis} onChange={e=>{setAxis(e.target.value as typeof axis);setProbe(e.target.value==='horizontal'?20:0);}}><option value="horizontal">수평 CD · x 방향</option><option value="vertical">수직 두께 · z 방향</option></select></label>
          <label>계측 위치 (nm)<input aria-label="계측 위치" type="number" step={d.grid_nm} value={probe} min={axis==='horizontal'?d.bottom_nm:-d.width_nm/2} max={axis==='horizontal'?d.top_nm-d.grid_nm:d.width_nm/2-d.grid_nm} onChange={e=>setProbe(Number(e.target.value))}/></label>
          <label>평가 재료<select aria-label="계측 평가 재료" value={targetMaterial} onChange={e=>setTargetMaterial(Number(e.target.value))}>{run.materials.filter(m=>m.id>0).map(m=><option key={m.id} value={m.id}>{m.name}</option>)}</select></label>
          <div className="flow-field-pair"><label>목표 (nm)<input aria-label="계측 목표" type="number" min="0" value={Number.isFinite(target)?target:''} onChange={e=>setTarget(e.target.value===''?NaN:Number(e.target.value))}/></label><label>허용 ± (nm)<input aria-label="계측 허용오차" type="number" min="0" value={Number.isFinite(tolerance)?tolerance:''} onChange={e=>setTolerance(e.target.value===''?NaN:Number(e.target.value))}/></label></div>
          <p className={`flow-verdict ${match===null?'unknown':match?'pass':'fail'}`}>{match===null?'평가 불가 · 단일 재료 구간과 유효 목표 필요':match?'설정 목표 충족':'설정 목표 미달'}{measured.length===1&&<strong>{measured[0].width_nm.toFixed(1)} nm</strong>}</p><p className="flow-help">셀 경계에서 읽은 형상 치수입니다. 허용오차가 격자 {d.grid_nm} nm보다 작으면 해상도 검토가 필요합니다. 실제 장비의 합격 판정은 아닙니다.</p>
          </>}
          {measurementPage==='sem'&&<><h3>SEM 표시 조건</h3><label>PSF σ (nm)<input aria-label="SEM PSF" type="range" min="0" max="8" step=".5" value={sigma} onChange={e=>setSigma(Number(e.target.value))}/><output>{sigma.toFixed(1)} nm</output></label><label>신호 잡음 σ<input aria-label="SEM 잡음" type="range" min="0" max=".1" step=".005" value={noise} onChange={e=>setNoise(Number(e.target.value))}/><output>{noise.toFixed(3)}</output></label><label>신호 임계값<input aria-label="SEM 임계값" type="range" min=".05" max=".95" step=".01" value={threshold} onChange={e=>setThreshold(Number(e.target.value))}/><output>{threshold.toFixed(2)}</output></label>
          <Chart compact series={{key:'sem-line',title:'가상 SEM 선 신호',x_label:axis==='horizontal'?'x (nm)':'z (nm)',y_label:'a.u.',x:cut.x,lines:[{name:'가정된 신호',values:lineSignal},{name:'임계값',values:cut.x.map(()=>threshold)}]}} staticLabel="seed 42"/>
          <p className="flow-help">임계값 이상 구간: {widths.length?widths.map(w=>`${w.width_nm.toFixed(1)} nm`).join(' / '):'없음'}. 재료별 대비는 가정값이며, 이 폭은 특정 재료의 CD와 같지 않을 수 있습니다. 전자 산란·검출기 해석은 아닙니다.</p></>}
        </div></>:inspector==='add'?<><header><h2>공정 추가</h2><button onClick={()=>setInspector('step')}>닫기</button></header><div className="flow-add-list">{(Object.keys(STEP_LABELS) as StepKind[]).map(kind=><button key={kind} disabled={busy} onClick={()=>{const s=newStep(kind,`${kind}-${crypto.randomUUID()}`);const index=Math.min(selected+1,recipe.steps.length);const steps=[...recipe.steps];steps.splice(index,0,s);setRecipe({...recipe,steps});setSelected(index);setInspector('step');}}><Plus size={16}/><span>{STEP_LABELS[kind]}<small>{STEP_HELP[kind]}</small></span></button>)}</div></>:inspector==='domain'?<><header><h2>계산 영역</h2><span>nm · 정사각 격자</span></header><div className="flow-inspector-body">{([{key:'width_nm',label:'영역 폭',min:80,max:800},{key:'bottom_nm',label:'하단 z',min:-200,max:-10},{key:'top_nm',label:'상단 z',min:40,max:500},{key:'grid_nm',label:'격자 간격',min:1,max:10}] as const).map(f=><label key={f.key}>{f.label} (nm)<input aria-label={f.label} type="number" min={f.min} max={f.max} value={Number.isFinite(recipe.domain[f.key])?recipe.domain[f.key]:''} disabled={busy} onChange={e=>setRecipe({...recipe,domain:{...recipe.domain,[f.key]:e.target.value===''?NaN:Number(e.target.value)}})}/></label>)}<p className="flow-help">원래 기판 표면은 z = 0입니다. 모든 단계에 같은 격자를 사용하며 최대 65,536개 셀을 허용합니다. 작은 두께를 보려면 격자 간격도 줄여 비교하세요.</p>{problem&&<p className="flow-field-error">{problem}</p>}</div></>:<><header><h2>{step?`Step ${String(selected+1).padStart(2,'0')}`:'Process flow'}</h2><span>{step?.name??'공정을 추가하세요'}</span></header><div className="flow-inspector-body">{step?<><label>단계 이름<input aria-label="공정 단계 이름" value={step.name} maxLength={80} disabled={busy} onChange={e=>editStep({name:e.target.value})}/></label>{selectedFields.map(f=><label key={f.key}>{f.label} <span>({f.unit})</span><input aria-label={f.label} type="number" min={f.min} max={f.max} step={f.key==='count'?1:'any'} disabled={busy} value={Number.isFinite(step[f.key])?step[f.key]:''} onChange={e=>editStep({[f.key]:e.target.value===''?NaN:Number(e.target.value)})}/></label>)}{step.material&&<label>재료<select aria-label="공정 재료" value={step.material} disabled={busy} onChange={e=>editStep({material:e.target.value})}>{step.kind==='directional_etch'&&<option value="all">노출된 모든 재료</option>}{schema.materials.filter(m=>m.id>0).map(m=><option key={m.id} value={m.name}>{m.name}</option>)}</select></label>}
          <div className="flow-context"><h3>공정 도움말</h3><p>{STEP_HELP[step.kind]}</p></div>
          <button className="flow-run-step" disabled={!available||busy||!!problem} onClick={()=>void execute(selected+1)}><Play size={15}/>선택 단계까지 실행</button>{problem&&<p className="flow-field-error">{problem}</p>}
          <details className="flow-details"><summary>계산 정보 / 주의사항</summary><dl className="flow-facts"><div><dt>해석 경로</dt><dd>재료 격자 / 기하학 모델</dd></div><div><dt>입력 격자</dt><dd>{recipe.domain.grid_nm} nm</dd></div><div><dt>현재 결과</dt><dd>{run.run_id?'로컬 Python 계산':'저장된 계산 예제'}</dd></div></dl>
          {frame.warnings.map((w,i)=><p className="flow-help" key={i}>{w}</p>)}
          </details>
          <button className="flow-text-button" onClick={()=>{setRecipe({name:run.request.name,domain:run.request.domain,steps:run.request.steps});setSelected(Math.max(0,frame.index-1));}} disabled={busy||!pending}><RotateCcw size={13}/>마지막 계산 입력으로 복원</button>
        </>:<p>공정 추가에서 첫 단계를 선택하세요.</p>}</div></>}
      </aside>
    </div>
    <footer className="flow-status"><span><i className={busy?'working':''}/>{busy?'계산 중':available?'로컬 Python 연결':'저장된 예제'} · {run.version}</span><span>2D 공정 형상 / 전기적 특성 미계산</span><code>{run.config_hash.slice(0,12)}</code></footer>
  </section>;
}
