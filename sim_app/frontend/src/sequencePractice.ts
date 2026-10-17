import type {Params} from './types';
import type {SequenceRun} from './sequence';

export type PracticeScope = 'etch' | 'ald' | 'both';
export interface Targets {
  depth:number; depthTolerance:number; width:number; widthTolerance:number;
  maskLoss:number; film:number; filmTolerance:number; conformity:number; gap:number;
}
// Output objectives only. No recipes, solver calls, fitted values, or inverse model.
// These are practice specifications, not guaranteed-feasible equipment specifications.
export const INITIAL_TARGETS:Targets = {
  depth:200,depthTolerance:20,width:80,widthTolerance:10,maskLoss:10,
  film:12,filmTolerance:1,conformity:95,gap:60,
};
export const TARGET_FIELDS:{key:keyof Targets;label:string;unit:string;stage:'etch'|'ald';max:number}[] = [
  {key:'depth',label:'식각 깊이 목표',unit:'nm',stage:'etch',max:5000},
  {key:'depthTolerance',label:'깊이 허용 오차 ±',unit:'nm',stage:'etch',max:5000},
  {key:'width',label:'절반 깊이 폭 목표',unit:'nm',stage:'etch',max:5000},
  {key:'widthTolerance',label:'폭 허용 오차 ±',unit:'nm',stage:'etch',max:5000},
  {key:'maskLoss',label:'마스크 소모 상한',unit:'nm',stage:'etch',max:5000},
  {key:'film',label:'상단 막 두께 목표',unit:'nm',stage:'ald',max:500},
  {key:'filmTolerance',label:'막 두께 허용 오차 ±',unit:'nm',stage:'ald',max:500},
  {key:'conformity',label:'바닥/상단 두께비 하한',unit:'%',stage:'ald',max:100},
  {key:'gap',label:'중간 깊이 통로 하한',unit:'nm',stage:'ald',max:5000},
];
export interface RunRecord {
  hash:string; label:string; created:string; source:'local'|'example'; params:Params;
  etch:Record<string,number|null>; ald:Record<string,number|null>;
  elapsed:number; implementation:string; warnings:string[]; handoff:boolean;
}
export interface Attempt extends RunRecord {jobId:string; note:string}
export interface Practice {
  id:string; title:string; scope:PracticeScope; targets:Targets; started:string;
  ended?:string; attempts:Attempt[];
}
export interface SavedSequenceRecipe {id:string;name:string;note:string;params:Params;created:string}
export interface PracticeStore {
  version:1; activeId:string|null; sessions:Practice[]; recipes:SavedSequenceRecipe[]; comparisons:RunRecord[];
  pending?:{jobId:string;sessionId:string;note:string};
}
export const PRACTICE_KEY='process-lab.sequence-practice.v1';
export const emptyPracticeStore=():PracticeStore=>({version:1,activeId:null,sessions:[],recipes:[],comparisons:[]});
export function targetProblem(targets:Targets):string|null {
  for(const f of TARGET_FIELDS){
    const v=targets[f.key];
    if(!Number.isFinite(v)||v<0||v>f.max)return `${f.label}: 0–${f.max} ${f.unit} 범위로 입력하세요.`;
  }
  if(targets.depth<=0||targets.width<=0||targets.film<=0)return '깊이, 폭, 막 두께 목표는 0보다 커야 합니다.';
  if(targets.depthTolerance>=targets.depth||targets.widthTolerance>=targets.width||targets.filmTolerance>=targets.film)
    return '허용 오차는 해당 목표값보다 작아야 합니다.';
  return null;
}
export function summarizeRun(run:SequenceRun,source:RunRecord['source'],created:string):RunRecord {
  const clean=(metrics:Record<string,number|null>)=>Object.fromEntries(Object.entries(metrics).map(([k,v])=>[k,typeof v==='number'&&Number.isFinite(v)?v:null]));
  const ald=clean(run.ald.frames.at(-1)!.metrics);
  if((ald.top_film_nm??0)<=1e-6)ald.bottom_top_pct=null;
  return {hash:run.run_hash,label:`Run ${run.run_hash.slice(0,6)}`,created,source,
    params:{...run.request.params},etch:clean(run.etch.frames.at(-1)!.metrics),ald,
    elapsed:run.elapsed_s,implementation:run.implementation,warnings:[...run.warnings],handoff:run.handoff.si_contour_preserved};
}
export interface Check {stage:'etch'|'ald';label:string;unit:string;actual:number|null;low:number|null;high:number|null;pass:boolean|null}
export function assess(record:RunRecord,targets:Targets,scope:PracticeScope):Check[] {
  if(targetProblem(targets))return [];
  const check=(stage:'etch'|'ald',key:string,label:string,unit:string,low:number|null,high:number|null):Check=>{
    const value=record[stage][key];
    const actual=typeof value==='number'&&Number.isFinite(value)?value:null;
    return {stage,label,unit,actual,low,high,pass:actual===null?null:
      (low===null||actual>=low-1e-9)&&(high===null||actual<=high+1e-9)};
  };
  const t=targets;
  return [
    check('etch','center_depth_nm','중앙 식각 깊이','nm',t.depth-t.depthTolerance,t.depth+t.depthTolerance),
    check('etch','width_half_depth_nm','절반 깊이의 폭','nm',t.width-t.widthTolerance,t.width+t.widthTolerance),
    check('etch','mask_loss_nm','마스크 소모','nm',null,t.maskLoss),
    check('ald','top_film_nm','상단 막 두께','nm',t.film-t.filmTolerance,t.film+t.filmTolerance),
    check('ald','bottom_top_pct','바닥 / 상단 두께비','%',t.conformity,null),
    check('ald','mid_gap_nm','중간 깊이의 통로','nm',t.gap,null),
  ].filter(c=>scope==='both'||c.stage===scope);
}
export function appendAttempt(store:PracticeStore,sessionId:string,record:RunRecord,jobId:string,note:string):PracticeStore {
  // Only the completion callback for a newly submitted local job calls this function.
  if(record.source!=='local')throw new Error('저장 예제는 과제 시도로 기록할 수 없습니다.');
  return {...store,sessions:store.sessions.map(s=>s.id!==sessionId||s.ended||s.attempts.some(a=>a.jobId===jobId)?s:
    {...s,attempts:[...s.attempts,{...record,params:{...record.params},etch:{...record.etch},ald:{...record.ald},warnings:[...record.warnings],jobId,note:note.slice(0,500)}]})};
}
const object=(v:unknown):v is Record<string,unknown>=>!!v&&typeof v==='object'&&!Array.isArray(v);
const numericMap=(v:unknown,nullable=false)=>object(v)&&Object.values(v).every(n=>(nullable&&n===null)||(typeof n==='number'&&Number.isFinite(n)));
function validRecord(v:unknown):v is RunRecord {
  return object(v)&&typeof v.hash==='string'&&typeof v.label==='string'&&typeof v.created==='string'&&
    (v.source==='local'||v.source==='example')&&numericMap(v.params)&&numericMap(v.etch,true)&&numericMap(v.ald,true)&&
    typeof v.elapsed==='number'&&Number.isFinite(v.elapsed)&&typeof v.implementation==='string'&&
    typeof v.handoff==='boolean'&&Array.isArray(v.warnings)&&v.warnings.every(x=>typeof x==='string');
}
export function parsePracticeStore(raw:string|null):PracticeStore {
  if(raw===null)return emptyPracticeStore();
  const v:unknown=JSON.parse(raw);
  if(!object(v)||v.version!==1||!Array.isArray(v.sessions)||!Array.isArray(v.recipes)||!Array.isArray(v.comparisons))
    throw new Error('저장한 연습 기록의 형식을 읽을 수 없습니다.');
  for(const s of v.sessions){
    if(!object(s)||typeof s.id!=='string'||typeof s.title!=='string'||typeof s.started!=='string'||
      !['etch','ald','both'].includes(String(s.scope))||!object(s.targets)||targetProblem(s.targets as unknown as Targets)||
      (s.ended!==undefined&&typeof s.ended!=='string')||!Array.isArray(s.attempts)||
      !s.attempts.every(a=>validRecord(a)&&a.source==='local'&&object(a)&&typeof a.jobId==='string'&&typeof a.note==='string'))
      throw new Error('과제 기록이 손상되었습니다. 원본 저장값은 덮어쓰지 않았습니다.');
  }
  if(v.activeId!==null&&(typeof v.activeId!=='string'||!v.sessions.some(s=>s.id===v.activeId&&!s.ended)))
    throw new Error('진행 중인 과제를 찾을 수 없습니다.');
  if(v.pending!==undefined&&(!object(v.pending)||typeof v.pending.jobId!=='string'||typeof v.pending.sessionId!=='string'||typeof v.pending.note!=='string'))
    throw new Error('진행 중인 계산 기록이 손상되었습니다.');
  if(!v.comparisons.every(validRecord)||!v.recipes.every(r=>object(r)&&typeof r.id==='string'&&typeof r.name==='string'&&
    typeof r.note==='string'&&typeof r.created==='string'&&numericMap(r.params)))throw new Error('레시피 또는 비교 기록을 읽을 수 없습니다.');
  return v as unknown as PracticeStore;
}
export function recordCsv(records:RunRecord[]):string {
  const keys=[...new Set(records.flatMap(r=>Object.keys(r.params)))];
  const metricKeys=['center_depth_nm','width_half_depth_nm','mask_loss_nm','top_film_nm','bottom_film_nm','bottom_top_pct','mid_gap_nm'];
  const cell=(value:unknown)=>{
    const text=String(value??'');
    // A name typed by a user must not become an Excel formula on CSV import.
    const safe=typeof value==='string'&&/^[=+\-@\t\r]/.test(text)?`'${text}`:text;
    return `"${safe.replaceAll('"','""')}"`;
  };
  return [['label','run_hash','source','created','implementation',...keys,...metricKeys],
    ...records.map(r=>[r.label,r.hash,r.source,r.created,r.implementation,...keys.map(k=>r.params[k]),
      ...metricKeys.map(k=>Object.hasOwn(r.etch,k)?r.etch[k]:r.ald[k])])].map(row=>row.map(cell).join(',')).join('\n');
}
