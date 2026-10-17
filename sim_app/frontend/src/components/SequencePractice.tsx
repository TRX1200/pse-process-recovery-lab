import {useState} from 'react';
import {Target,LockKeyhole,Check,Minus,ArrowUpRight,Download,Flag} from 'lucide-react';
import {assess,INITIAL_TARGETS,TARGET_FIELDS,targetProblem} from '../sequencePractice';
import type {Practice,PracticeScope,Targets,RunRecord} from '../sequencePractice';
import {exportJson,download} from '../storage';
import {recordCsv} from '../sequencePractice';

const SCOPE_NAMES={etch:'식각 형상 제어',ald:'ALD 피복 제어',both:'연속공정 도전'};
export function SequencePractice({practice,sessions,current,locked,onStart,onFinish,note,onNote,onInputs}:{
  practice:Practice|undefined;sessions:Practice[];current:RunRecord;locked:boolean;
  onStart:(title:string,scope:PracticeScope,targets:Targets)=>void;onFinish:()=>void;
  note:string;onNote:(value:string)=>void;onInputs:()=>void;
}){
  const [scope,setScope]=useState<PracticeScope>('etch');
  const [targets,setTargets]=useState<Targets>({...INITIAL_TARGETS});
  const [targetStage,setTargetStage]=useState<'etch'|'ald'>('etch');
  const [historyId,setHistoryId]=useState('');
  const [attemptIndex,setAttemptIndex]=useState<number|null>(null);
  const shown=practice??sessions.find(s=>s.id===historyId);
  const latest=shown?.attempts.at(-1);
  const attempt=attemptIndex===null?latest:shown?.attempts[attemptIndex];
  const checks=shown&&attempt?assess(attempt,shown.targets,shown.scope):[];
  const passed=checks.filter(c=>c.pass===true).length;
  const valid=targetProblem(targets);
  return <div className="seq-practice seq-scroll">
    <div className="seq-panel-heading"><div><h2><Target size={19}/>공정 연습 과제</h2><p>목표를 고정하고, 레시피를 직접 조절하며 반복 실험하세요.</p></div>
      <button onClick={()=>exportJson('process-practice.json',{format:'sequence-practice-export-v1',sessions})} disabled={!sessions.length}><Download size={14}/>기록 JSON</button></div>
    {!practice&&<div className="seq-task-builder">
      <nav className="seq-task-scopes" aria-label="과제 종류">{Object.entries(SCOPE_NAMES).map(([key,label])=><button key={key} aria-pressed={scope===key} onClick={()=>{setScope(key as PracticeScope);setTargetStage(key==='ald'?'ald':'etch');setHistoryId('');}}><span>{key==='etch'?'01':key==='ald'?'02':'03'}</span>{label}</button>)}</nav>
      <div className="seq-task-brief"><strong>{SCOPE_NAMES[scope]}</strong><p>{scope==='etch'?'깊이와 폭을 맞추면서 마스크 소모를 제한하세요.':scope==='ald'?'막 두께를 맞추면서 바닥 피복과 통로 폭을 확보하세요.':'하나의 식각→증착 결과에서 두 공정의 목표를 동시에 만족시키세요.'}</p></div>
      {scope==='both'&&<nav className="seq-task-stage" aria-label="목표 설정 공정"><button aria-pressed={targetStage==='etch'} onClick={()=>setTargetStage('etch')}>식각 목표</button><button aria-pressed={targetStage==='ald'} onClick={()=>setTargetStage('ald')}>ALD 목표</button></nav>}
      <div className="seq-target-fields">{TARGET_FIELDS.filter(f=>f.stage===(scope==='both'?targetStage:scope)).map(f=><label key={f.key}>{f.label}<span><input type="number" min="0" max={f.max} step="any" value={Number.isFinite(targets[f.key])?targets[f.key]:''} onChange={e=>setTargets(t=>({...t,[f.key]:e.target.value===''?NaN:Number(e.target.value)}))}/><small>{f.unit}</small></span></label>)}</div>
      {valid&&<p role="alert" className="seq-inline-error">{valid}</p>}
      <div className="seq-task-start"><p>예시 목표이며 달성 가능성은 사전 검증하지 않았습니다. 목표는 시작 전에 수정할 수 있어요. 정답 레시피·자동 튜닝은 없습니다.</p><button className="seq-accent" disabled={locked||!!valid} onClick={()=>{onStart(SCOPE_NAMES[scope],scope,{...targets});setAttemptIndex(null);}}><LockKeyhole size={14}/>목표 고정 · 도전 시작</button></div>
    </div>}
    {!practice&&sessions.length>0&&<label className="seq-archive-picker">지난 과제 <select value={historyId} onChange={e=>{setHistoryId(e.target.value);setAttemptIndex(null);}}><option value="">기록 선택</option>{[...sessions].reverse().map(s=><option key={s.id} value={s.id}>{s.title} · {s.attempts.length}회 · {new Date(s.started).toLocaleDateString('ko-KR')}</option>)}</select></label>}
    {shown&&<>
      <div className="seq-task-status"><div><span><LockKeyhole size={13}/>{shown.ended?'종료한 과제':'고정된 목표'}</span><h3>{shown.title}</h3><p>{shown.attempts.length}회 시도{attempt?` · 선택한 실행 ${attempt.hash.slice(0,8)}`:' · 아직 새 계산을 실행하지 않았습니다.'}</p></div><div className="seq-task-score"><strong>{attempt?`${passed} / ${checks.length}`:'—'}</strong><span>{attempt?'목표 충족 항목':'첫 시도를 기다리는 중'}</span></div></div>
      <div className="seq-score-list">{(attempt?checks:assess(current,shown.targets,shown.scope)).map(c=>{
        const status=!attempt?'waiting':c.pass===null?'unknown':c.pass?'pass':'fail';
        return <div key={c.stage+c.label} className="seq-score-row" data-status={status}><span className="seq-check-icon">{status==='pass'?<Check size={16}/>:status==='fail'?<ArrowUpRight size={16}/>:<Minus size={16}/>}</span><div><strong>{c.label}</strong><small>{c.stage==='etch'?'Etch':'ALD'} · {c.low===null?`≤ ${c.high}`:c.high===null?`≥ ${c.low}`:`${c.low}–${c.high}`} {c.unit}</small></div><b>{attempt&&c.actual!==null?`${c.actual.toFixed(2)} ${c.unit}`:'—'}</b><em>{status==='pass'?'충족':status==='fail'?'미달':status==='unknown'?'판정 불가':'대기'}</em></div>;
      })}</div>
      {attempt&&(!attempt.handoff||attempt.warnings.length>0||(shown.scope!=='etch'&&(attempt.ald.top_film_nm??0)<2*attempt.params.grid_nm))&&<p className="seq-warning">수치 검토 필요: {attempt.warnings.join(' ')||'형상 전달 또는 막 두께 대비 격자를 확인하세요.'} 목표 충족은 물리 정확도 검증과 다릅니다.</p>}
      {practice&&<div className="seq-hypothesis"><label>다음 시도의 가설<input maxLength={500} disabled={locked} value={note} onChange={e=>onNote(e.target.value)} placeholder="무엇을 바꾸고, 어떤 변화가 생길 것으로 예상하나요?"/></label><button onClick={onInputs}>레시피 조절<ArrowUpRight size={14}/></button></div>}
      {shown.attempts.length>0&&<div className="seq-attempt-history"><div><h3>시도 기록</h3><button onClick={()=>download('process-attempts.csv',recordCsv(shown.attempts),'text/csv')}><Download size={13}/>CSV</button></div><div className="seq-attempt-list">{shown.attempts.map((a,i)=>{const result=assess(a,shown.targets,shown.scope);return <button key={a.jobId} aria-pressed={a.jobId===attempt?.jobId} onClick={()=>setAttemptIndex(i)}><strong>#{String(i+1).padStart(2,'0')}</strong><span>{a.note||'가설 메모 없음'}<small>{a.hash.slice(0,8)} · TMA {a.params.pulse_s} s · {a.params.cycles} cycles</small></span><b>{result.filter(c=>c.pass).length}/{result.length}</b></button>;})}</div></div>}
      {practice&&<button className="seq-finish" disabled={locked} onClick={()=>{onFinish();setHistoryId(practice.id);}}><Flag size={14}/>과제 종료 · 기록 유지</button>}
    </>}
    <p className="seq-task-boundary">새 로컬 계산만 시도로 기록합니다. 예제 열기·이력 재생은 채점하지 않습니다. 마스크 제거는 이상적 연결 단계라 독립 과제에서 제외합니다. 목표값은 장비 품질 기준이 아닙니다.</p>
  </div>;
}
