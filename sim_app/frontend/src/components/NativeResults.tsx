import {useMemo} from 'react';
import {Download,Pause,Play} from 'lucide-react';
import {Chart} from './Chart';
import {NativeViewport} from './NativeViewport';
import {CaptureReport} from './ProjectReport';
import {exportJson,download} from '../storage';
import {NATIVE_METRICS} from '../native';
import type {NativeRun,NativeFrame} from '../native';
import {analyzeFrame,defaultGoal,evaluateNative,goalError,goalFields,nativeCharts,profileOf,targetPaths} from '../nativeAnalysis';
import type {NativeGoal} from '../nativeAnalysis';
import '../nativeReview.css';

const STATUS={pass:'목표 충족',fail:'목표 미달',unknown:'평가 불가'};
export const SPECIMENS=[
  {title:'패턴 / 평활 트렌치',question:'Etch: 깊이·폭 / ALD: 바닥 피복',path:'M5 16H35V48H65V16H95'},
  {title:'평면 요철',question:'초기 ripple의 거칠기와 평탄화',path:'M5 32Q12 14 20 32T35 32T50 32T65 32T80 32T95 32'},
  {title:'요철 측벽',question:'측벽 scallop 변화와 막의 피복',path:'M5 16H35Q27 22 35 28Q27 34 35 40V50H65V40Q73 34 65 28Q73 22 65 16H95'},
];
export function SpecimenGuide({profile}:{profile:number}) {
  return <details className="native-specimens"><summary>왜 초기 형상이 3개인가요?</summary>
    <p>세 단계가 아니라 <strong>서로 다른 질문을 위한 시험 시편</strong>입니다. 공정 입력에서 초기 형상을 선택하고 계산하거나, 저장된 예제를 열어 비교하세요.</p>
    <div>{SPECIMENS.map((s,i)=><article key={s.title} data-selected={profile===i}><svg viewBox="0 0 100 65" aria-hidden="true"><path d={s.path} fill="none" stroke="currentColor" strokeWidth="2"/></svg><strong>{i+1}. {s.title}</strong><span>{s.question}</span></article>)}</div>
  </details>;
}

interface Props {
  run:NativeRun; frame:NativeFrame; reference:NativeRun|null; active:boolean; recorded:boolean;
  index:number; playing:boolean; onPlay:()=>void; onFrame:(index:number)=>void;
  goal:NativeGoal; onGoal:(goal:NativeGoal)=>void;
  showInitial:boolean; onInitial:(value:boolean)=>void; showMesh:boolean; onMesh:(value:boolean)=>void;
  showParticles:boolean; onParticles:(value:boolean)=>void; zoom:number; onZoom:(value:number)=>void;
  onReference:(run:NativeRun|null)=>void; sourceLabel:string;
}
export function NativeResults({run,frame,reference,active,recorded,index,playing,onPlay,onFrame,goal,onGoal,
  showInitial,onInitial,showMesh,onMesh,showParticles,onParticles,zoom,onZoom,onReference,sourceLabel}:Props) {
  const profile=profileOf(run),error=goalError(run,goal);
  const target=useMemo(()=>targetPaths(run,goal),[run,goal]);
  const analyses=useMemo(()=>run.frames.map(f=>analyzeFrame(run,f,target)),[run,target]);
  const currentIndex=active?run.frames.length-1:Math.min(index,run.frames.length-1);
  const review=evaluateNative(run,frame,goal,analyses[currentIndex]);
  const finalReview=evaluateNative(run,run.frames.at(-1)!,goal,analyses.at(-1)!);
  const charts=useMemo(()=>nativeCharts(run,goal,analyses,currentIndex),[run,goal,analyses,currentIndex]);
  const intermediate=active||currentIndex<run.frames.length-1;
  const specimen=SPECIMENS[profile]?.title??'시편';
  const evaluation={...review,run_hash:run.run_hash,params:run.params,frame_index:currentIndex,axis_unit:run.axis_unit,
    phase:intermediate?'intermediate':'final',evidence:'simulation',numerics:run.numerics,environment:run.environment};
  function saveSvg(){
    const svg=document.querySelector('.native-viewport');if(!svg)return;
    const copy=svg.cloneNode(true) as SVGElement;copy.setAttribute('xmlns','http://www.w3.org/2000/svg');
    // Illustrative particles are excluded from the scientific geometry export.
    copy.querySelectorAll('[data-process-illustration]').forEach(n=>n.remove());
    const metadata=document.createElementNS('http://www.w3.org/2000/svg','metadata');
    metadata.textContent=JSON.stringify({...evaluation,implementation:run.implementation,view:{zoom,showInitial,showMesh,illustrative_particles:false},reference:reference?{run_hash:reference.run_hash,params:reference.params}:null});
    copy.prepend(metadata);download(`surface-${run.run_hash.slice(0,10)}-${currentIndex}.svg`,new XMLSerializer().serializeToString(copy),'image/svg+xml');
  }
  return <>
    <div className="native-result-toolbar"><span className="native-source-label">{sourceLabel}</span><code>{run.run_hash.slice(0,10)}</code>
      <button disabled={active} onClick={()=>exportJson(`native-${run.model}-${run.run_hash.slice(0,10)}.json`,run)}><Download size={14}/>전체 결과</button>
      <button disabled={active} onClick={()=>onReference(run)}>비교 기준으로 고정</button>
      <button disabled={active} onClick={saveSvg}>현재 단면 SVG</button>
      <button disabled={active||!!error} onClick={()=>exportJson(`review-${run.run_hash.slice(0,10)}-${currentIndex}.json`,evaluation)}>현재 평가 JSON</button>
      <CaptureReport key={JSON.stringify(goal)} disabled={active||!!error} snapshot={{kind:`native-${run.model}`,label:`${run.model.toUpperCase()} · ${specimen} · ${STATUS[finalReview.status]}`,source_id:run.run_hash,version:run.implementation,evidence:'simulation',provenance:recorded?'recorded example':'local calculation',
        inputs:{surface_profile:0,...run.params,...Object.fromEntries(Object.entries(goal).map(([k,v])=>[`target.${k}`,v]))},
        metrics:Object.entries(analyses.at(-1)!.metrics).map(([key,value])=>({key,label:NATIVE_METRICS[key]?.[0]??finalReview.rows.find(r=>r.key===key)?.label??key,unit:NATIVE_METRICS[key]?.[1]??(key.endsWith('_nm')?'nm':''),value})),
        assumptions:[...run.assumptions,'목표 판정은 사용자가 설정한 기준에 대한 모델 결과 비교이며 실제 장비 공정의 합격 판정이 아닙니다.'],numerics:{environment:run.environment,numerics:run.numerics,target_review:finalReview}}}/>
    </div>
    <SpecimenGuide profile={profile}/>
    <details className="native-goals" open>
      <summary><span>01 · 목표 설정</span><small>{specimen} · 사용자 기준</small></summary>
      <p>붉은 주황색 선은 <strong>달성하려는 최종 단면</strong>입니다. 기본값은 학습 예시이며 장비 사양이 아닙니다. 목표를 바꾸면 현재 결과를 다시 평가합니다. 공정 형상은 Run simulation으로만 바뀝니다.</p>
      <div className="native-goal-fields">{goalFields(run.model,profile).map(f=><label key={f.key}><span>{f.label}<small>{f.unit}</small></span><input aria-label={f.label} type="number" min={f.min} max={f.max} step="any" disabled={active} value={Number.isFinite(goal[f.key])?goal[f.key]:''} onChange={e=>onGoal({...goal,[f.key]:e.target.value===''?NaN:Number(e.target.value)})}/></label>)}</div>
      <div className="native-goal-footer">{run.model==='ald'&&profile===1&&<label>목표 표면 <select aria-label="ALD 목표 표면" value={goal.coating} disabled={active} onChange={e=>onGoal({...goal,coating:e.target.value as NativeGoal['coating']})}><option value="conformal">초기 요철을 따라 일정 두께로 코팅</option><option value="flat">평탄한 최종 표면</option></select></label>}
        <button disabled={active} onClick={()=>onGoal(defaultGoal(run.model,profile))}>학습 예시값 복원</button></div>
      <p className="native-goal-definition">{run.model==='etch'?(profile===1?'제거량은 초기 평균면 대비 값입니다.':'최종 깊이는 y = 0부터의 총 깊이입니다. 요철 측벽 시편의 초기 깊이도 포함합니다.'):'목표선은 초기 Si 경계를 막 두께만큼 이동한 기하학적 안내선입니다. 평면 요철의 두께 평가는 평균 높이 증가, 트렌치의 평가는 상단 두께입니다.'} 현재 표시된 시편에 적용됩니다.</p>
      {error&&<p className="native-warning" role="alert">{error} 목표선과 판정을 보류합니다.</p>}
    </details>
    <div className="native-section-heading"><h2>02 · 공정 단면</h2><span>실제 계산 프레임 · x/y 동일 축척</span></div>
    <div className="native-view-options"><label><input type="checkbox" checked={showInitial} onChange={e=>onInitial(e.target.checked)}/>초기 형상</label><label><input type="checkbox" checked={showMesh} onChange={e=>onMesh(e.target.checked)}/>계산 표면점</label>
      <label><input type="checkbox" checked={showParticles} onChange={e=>onParticles(e.target.checked)}/>입자 / 반응 설명</label>
      <label>확대 <select aria-label="단면 확대" value={zoom} onChange={e=>onZoom(Number(e.target.value))}><option value="1">1×</option><option value="1.5">1.5×</option><option value="2">2×</option></select></label>
      {reference&&<button onClick={()=>onReference(null)}>비교선 지우기</button>}</div>
    <NativeViewport run={run} frame={frame} reference={reference} initial={showInitial} mesh={showMesh} zoom={zoom} target={target} particles={showParticles} playing={playing||active}/>
    <div className="native-legend"><span className="silicon">Si 기판</span>{run.model==='ald'?<span className="film">Al₂O₃ 막</span>:profile===0?<span className="mask">유효 마스크</span>:null}<span className="target">붉은 주황선: 사용자 목표</span><span>흰 점선: 초기 형상</span>{reference&&<span className="comparison">파란 점선: 비교 기준</span>}</div>
    <div className="native-playback"><button disabled={active} aria-label={playing?'단면 재생 일시정지':'단면 재생'} onClick={onPlay}>{playing?<Pause size={18}/>:<Play size={18}/>}</button>
      <input type="range" aria-label="계산 프레임" min="0" max={run.frames.length-1} step="1" value={currentIndex} disabled={active} onChange={e=>onFrame(Number(e.target.value))}/><output>{frame.at.toFixed(run.axis_unit==='s'?2:0)} {run.axis_unit}</output></div>
    <p className="native-frame-note">프레임 {currentIndex+1} / {run.frames.length} · 재생은 계산 이력을 0.65초 간격으로 보여줍니다. 실제 공정 시간과 재생 시간은 다릅니다. 입자·발광은 반응 설명용이며 궤적 계산 결과가 아닙니다. 보고서에는 최종 평가가 기록됩니다.</p>
    {profile>0&&<p className="native-warning">{profile===1?'초기 ripple':'초기 scallop'}이 이후 공정에서 어떻게 변하는지 계산합니다. 자발적인 요철 발생이나 Bosch 주기를 재현하지 않습니다. 미세 요철은 아래 nm 단위 그래프에서도 확인하세요.</p>}
    <section className="native-assessment" aria-label="공정 목표 평가표">
      <div className="native-section-heading"><h2>03 · {intermediate?'중간':'최종'} 평가</h2><span className={`native-verdict ${review.status}`}>{STATUS[review.status]}</span></div>
      <p>한 항목이라도 미달이면 전체는 ‘목표 미달’입니다. 측정할 수 없는 값은 0점이나 정상으로 처리하지 않습니다. <strong>사용자 목표와의 비교이며 실제 장비의 품질 보증은 아닙니다.</strong></p>
      <div className="native-review-table"><table><thead><tr><th>평가 항목</th><th>계산값</th><th>사용자 기준</th><th>판정</th></tr></thead><tbody>{review.rows.map(r=><tr key={r.key}><th scope="row">{r.label}</th><td>{r.value===null?'측정 불가':`${r.value.toFixed(2)} ${r.unit}`}</td><td>{r.target} {r.unit}</td><td><span className={`native-verdict ${r.status}`}>{STATUS[r.status]}</span></td></tr>)}</tbody></table></div>
      <div className="native-next-checks">{review.rows.filter(r=>r.status!=='pass').map(r=><p key={r.key}><strong>{r.label} · 다음 비교</strong>{r.advice}</p>)}{review.status==='pass'&&<p>설정한 모든 기준을 충족했습니다. 조건을 조금 바꾸거나 격자·시드·입자 수를 바꿔도 결론이 유지되는지 확인하세요.</p>}</div>
      {review.warnings.map((w,i)=><p className="native-warning" key={i}>{w}</p>)}
      <details className="native-measurement-notes"><summary>엔진 원시 지표 / 비교 기준값</summary><div className="native-review-table"><table><thead><tr><th>지표</th><th>현재 시점</th>{reference&&<th>비교 기준의 최종값</th>}</tr></thead><tbody>{Object.entries(frame.metrics).map(([key,v])=>{const value=key==='bottom_top_pct'&&(frame.metrics.top_film_nm??0)<=1e-6?null:v;const baseline=key==='bottom_top_pct'&&(reference?.frames.at(-1)!.metrics.top_film_nm??0)<=1e-6?null:reference?.frames.at(-1)!.metrics[key];return <tr key={key}><th>{NATIVE_METRICS[key]?.[0]??key}</th><td>{value===null?'측정 불가':value.toFixed(3)} {NATIVE_METRICS[key]?.[1]}</td>{reference&&<td>{baseline==null?'측정 불가':baseline.toFixed(3)} {NATIVE_METRICS[key]?.[1]}</td>}</tr>;})}</tbody></table></div></details>
      <details className="native-measurement-notes"><summary>측정 위치와 평가 수식</summary><p>Rq = √mean((h − 평균면)²). 평면은 전체 폭의 256개 중점, 바닥은 초기 개구 폭 중앙 60%의 65개 중점을 사용합니다. 측벽은 깊이 10–90%의 161개 위치에서 직선 기울기를 제거합니다. 요철 측벽·ALD는 초기 깊이를 고정하고, 패턴 Etch는 각 시점의 깊이를 사용합니다.</p><p>목표 단면 RMS = √mean(d²). 실제→목표와 목표→실제 각각 97개 등간격 호 길이 표본에서 가장 가까운 선분까지의 거리를 합칩니다. 국소 결함의 최댓값이 아니므로 단면과 깊이별 그래프도 확인하세요. 패턴 Etch는 Si level set에 포함된 마스크 윗부분을 제외하고 보호된 기판 면을 y = 0으로 비교합니다. ALD 목표선은 법선 이동과 제한된 모서리 연결을 사용한 설계 안내선이며 별도의 성장 해석이 아닙니다.</p><p>그래프의 성장률은 완료 구간의 Δh / Δt 또는 Δh / Δcycle입니다. ALD 깊이별 막 거리는 기판까지의 최단 거리이며 정확한 국소 법선 두께와 다를 수 있습니다. 격자 {run.params.grid_nm} nm · 입자 수 {run.params.rays_per_point} / 표면점 · seed {run.params.seed}.</p></details>
    </section>
    <div className="native-section-heading"><h2>04 · 공정 진단 그래프</h2><span>{charts.history.length+charts.spatial.length}개 · 현재 재생 위치와 연동</span></div>
    <p className="native-chart-note">상단 그래프는 시간 / 사이클 이력, 하단 두 그래프는 현재 단면의 공간 분포입니다. 끊긴 구간은 측정 불가입니다.</p>
    <div className="native-chart-grid">{charts.history.map(series=><Chart key={series.key} series={series} time={frame.at}/>)}{charts.spatial.map(series=><Chart key={series.key} series={series} staticLabel={`단면 ${frame.at.toFixed(2)} ${run.axis_unit}`}/>)}</div>
  </>;
}
