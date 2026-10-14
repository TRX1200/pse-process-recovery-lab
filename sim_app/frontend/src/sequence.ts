import type {NativeFrame, NativeJob, NativeParameter, NativeRun} from './native';
import type {Params, Series} from './types';

export type SequenceStage = 'etch'|'strip'|'ald';
export interface SequenceRun {
  format:'native-sequence-run-v1'; model:'sequence'; implementation:string; run_hash:string;
  request:{model:'sequence';params:Params}; etch:NativeRun; strip:NativeFrame; ald:NativeRun;
  handoff:{geometry_sha256:string;si_contour_preserved:boolean;derived_depth_nm:number};
  environment:Record<string,string|number>; source_sha256:Record<string,string>;
  assumptions:string[]; warnings:string[]; elapsed_s:number;
}
export type SequenceJob = Omit<NativeJob,'model'|'last_frame'> & {
  model:'sequence';last_frame?:NativeFrame & {stage:SequenceStage};
};
export interface SequenceSchema {models:{sequence:{params:NativeParameter[]}}}
export interface ALDRecipe {
  id:string;title:string;compare_to:string|null;changed_keys:string[];
  request:{model:'sequence';params:Params};question:string;hypothesis:string;observe:string;
}
export interface ALDRecipeCatalog {
  format:'native-ald-experiments-v1';kind:'input_presets';recipes:ALDRecipe[];
}
export function recipeInputs(recipe:ALDRecipe,fields:NativeParameter[]):Params {
  const params=recipe.request.params;
  if(recipe.request.model!=='sequence'||Object.keys(params).length!==fields.length||
    fields.some(f=>!Object.hasOwn(params,f.key)))throw new Error('완전한 연속공정 입력이 필요합니다.');
  const problem=inputProblem(fields,params);
  if(problem)throw new Error(problem);
  return {...params};
}
export const STAGES = [
  {key:'etch',name:'Si 식각',detail:'SF₆ / O₂ · 수송 + 표면 반응'},
  {key:'strip',name:'마스크 제거',detail:'이상적 제거 · 형상 전달'},
  {key:'ald',name:'Al₂O₃ 증착',detail:'TMA 제한 반응 · ALD'},
] as const;
export const GROUPS = {geometry:'구조',etch:'식각',ald:'ALD',numerics:'수치 설정'};
export function sameInputs(a:Params,b:Params):boolean {
  const keys=Object.keys(a);
  return keys.length===Object.keys(b).length&&keys.every(k=>a[k]===b[k]);
}
export function inputProblem(fields:NativeParameter[],params:Params):string|null {
  for(const f of fields){
    const v=params[f.key];
    if(!Number.isFinite(v)||v<f.min||v>f.max||(f.integer&&!Number.isInteger(v)))
      return `${f.label}: ${f.min}–${f.max}${f.integer?' 범위의 정수':' 범위'}를 입력하세요.`;
  }
  if(params.width_nm>params.pitch_nm*.75)return '개구 폭은 영역 폭의 75% 이하여야 합니다.';
  if(params.width_nm<params.grid_nm*6)return '개구 폭에 최소 6격자가 필요합니다.';
  if(params.mask_nm<params.grid_nm*3)return '마스크 두께에 최소 3격자가 필요합니다.';
  if(params.pitch_nm/params.grid_nm>800)return '가로 격자 수는 800 이하로 설정하세요.';
  return null;
}
export function stageRun(run:SequenceRun,stage:SequenceStage):NativeRun {
  return stage==='strip'?{...run.etch,frames:[run.strip]}:run[stage];
}
export function sequenceCharts(run:SequenceRun,stage:SequenceStage):Series[] {
  const s=stage==='ald'?run.ald:run.etch;
  const groups=stage==='ald'?
    [['상단 / 바닥 막 두께','nm',['top_film_nm','상단'],['bottom_film_nm','바닥']],
     ['바닥 / 상단 두께비','%',['bottom_top_pct','두께비']],
     ['통로 폭','nm',['mid_gap_nm','중간 깊이'],['minimum_gap_nm','샘플 최소']]]:
    [['식각 깊이','nm',['center_depth_nm','중앙']],
     ['절반 깊이의 폭','nm',['width_half_depth_nm','폭']],
     ['유효 마스크 소모','nm',['mask_loss_nm','소모']]];
  return groups.map(([title,unit,...entries],i)=>({key:`sequence-${stage}-${i}`,title:title as string,
    x_label:stage==='ald'?'ALD cycles':'Etch time (s)',y_label:unit as string,
    x:s.frames.map(f=>f.at),lines:(entries as string[][]).map(([key,name])=>({name,
      values:s.frames.map(f=>key==='bottom_top_pct'&&(f.metrics.top_film_nm??0)<=1e-6?
        NaN:f.metrics[key]??NaN)}))}));
}
