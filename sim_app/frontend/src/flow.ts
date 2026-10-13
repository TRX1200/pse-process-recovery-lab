export type StepKind='stack'|'mask'|'strip'|'deposit'|'directional_etch'|'selective_etch'|'planarize';
export interface FlowStep {
  id:string; name:string; kind:StepKind; material?:string; amount_nm?:number;
  count?:number; si_nm?:number; sige_nm?:number; width_nm?:number; center_nm?:number;
  selectivity?:number; height_nm?:number;
}
export interface FlowDomain {width_nm:number;bottom_nm:number;top_nm:number;grid_nm:number}
export interface FlowRecipe {name:string;domain:FlowDomain;steps:FlowStep[]}
export interface FlowMaterial {id:number;name:string;color:string;contrast:number}
export interface FlowFrame {
  index:number;name:string;step:FlowStep|null;state_hash:string;parent_hash:string|null;
  spans:[number,number,number,number][];mask_columns:number[];
  metrics:{area_nm2:Record<string,number>;top_height_nm:number;surface_rq_nm:number;si_components_above_zero:number;enclosed_void_area_nm2:number};
  warnings:string[];
}
export interface FlowRun {
  format:'process-flow-run-v1';version:string;config_hash:string;run_id?:string;
  request:FlowRecipe&{stop_after:number};shape:[number,number];materials:FlowMaterial[];
  frames:FlowFrame[];assumptions:string[];elapsed_s:number;numerics:Record<string,unknown>;
}
export interface FlowSchema {version:string;materials:FlowMaterial[];presets:(FlowRecipe&{id:string})[];assumptions:string[]}
export const STEP_LABELS:Record<StepKind,string>={stack:'Si / SiGe 적층',mask:'패턴 마스크',strip:'마스크 제거',deposit:'등두께 증착',directional_etch:'방향성 식각',selective_etch:'선택 식각',planarize:'높이 절단 / 평탄화'};
export const STEP_HELP:Record<StepKind,string>={
  stack:'평탄한 표면 위에 SiGe와 Si를 교대로 쌓습니다. 초기 다층 구조를 만드는 기하학적 연산이며 에피택시 반응은 계산하지 않습니다.',
  mask:'지정한 폭의 중앙 영역을 보호합니다. 이상적인 수직 투영 마스크로, 감광액 노광·현상·마스크 침식은 계산하지 않습니다.',
  strip:'현재 투영 마스크를 제거합니다. 이후 공정은 노출된 모든 표면에 접근할 수 있습니다.',
  deposit:'외부와 연결된 빈 공간에 지정 두께로 코팅합니다. 입구가 닫힌 공동은 코팅하지 않습니다. ALD 노출·피복률 반응은 ALD / Etch 탭에서 별도로 계산합니다.',
  directional_etch:'위에서 보이는 선택 재료를 지정 깊이만큼 제거합니다. 보호된 열과 다른 재료에서 멈춥니다. 실제 이온 에너지·각도 분포 해석은 아닙니다.',
  selective_etch:'외부에서 접근 가능한 표면부터 8방향 격자로 식각 전면을 전파합니다. 선택비 100은 대상 재료의 유효 속도가 다른 재료보다 100배라는 입력 가정입니다.',
  planarize:'지정 높이보다 위에 있는 재료를 제거합니다. CMP 압력·마찰·dishing/erosion을 예측하는 모델은 아닙니다.',
};
export type NumericStepKey='amount_nm'|'count'|'si_nm'|'sige_nm'|'width_nm'|'center_nm'|'selectivity'|'height_nm';
export const STEP_FIELDS:Record<StepKind,{key:NumericStepKey;label:string;unit:string;min:number;max:number}[]>={
  stack:[{key:'count',label:'Si 시트 수',unit:'층',min:1,max:6},{key:'si_nm',label:'Si 층 두께',unit:'nm',min:1,max:40},{key:'sige_nm',label:'SiGe 층 두께',unit:'nm',min:1,max:40}],
  mask:[{key:'width_nm',label:'보호 폭',unit:'nm',min:1,max:800},{key:'center_nm',label:'중심 위치',unit:'nm',min:-400,max:400}],
  strip:[],deposit:[{key:'amount_nm',label:'증착 두께',unit:'nm',min:0,max:250}],
  directional_etch:[{key:'amount_nm',label:'식각 깊이',unit:'nm',min:0,max:250}],
  selective_etch:[{key:'amount_nm',label:'대상 재료 식각 거리',unit:'nm',min:0,max:250},{key:'selectivity',label:'대상 / 다른 재료 선택비',unit:': 1',min:1,max:1000}],
  planarize:[{key:'height_nm',label:'절단 높이',unit:'nm',min:-199,max:499}],
};
export function newStep(kind:StepKind,id:string):FlowStep {
  const base={id,kind,name:STEP_LABELS[kind]};
  switch(kind){
    case 'stack':return {...base,count:3,si_nm:10,sige_nm:16};
    case 'mask':return {...base,width_nm:100,center_nm:0};
    case 'deposit':return {...base,amount_nm:4,material:'HfO2'};
    case 'directional_etch':return {...base,amount_nm:20,material:'all'};
    case 'selective_etch':return {...base,amount_nm:54,material:'SiGe',selectivity:100};
    case 'planarize':return {...base,height_nm:40};
    default:return base;
  }
}
export function recipeKey(recipe:FlowRecipe):string {return JSON.stringify({name:recipe.name,domain:recipe.domain,steps:recipe.steps});}
export function recipeProblem(recipe:FlowRecipe):string|null {
  if(!recipe||typeof recipe.name!=='string'||!recipe.name.trim()||recipe.name.length>100||!Array.isArray(recipe.steps)||recipe.steps.length>24)return '유효한 공정명과 최대 24개 단계가 필요합니다.';
  const d=recipe.domain;
  if(!d||![d.width_nm,d.bottom_nm,d.top_nm,d.grid_nm].every(Number.isFinite))return '계산 영역을 모두 입력하세요.';
  if(d.width_nm<80||d.width_nm>800||d.bottom_nm< -200||d.bottom_nm> -10||d.top_nm<40||d.top_nm>500||d.grid_nm<1||d.grid_nm>10)return '계산 영역의 허용 범위를 확인하세요.';
  if([d.width_nm,d.bottom_nm,d.top_nm].some(v=>Math.abs(v/d.grid_nm-Math.round(v/d.grid_nm))>1e-8))return '폭과 상하 경계는 격자의 정수배로 입력하세요.';
  if(d.width_nm*(d.top_nm-d.bottom_nm)/d.grid_nm**2>65536)return '셀 수가 65,536개를 초과합니다. 격자를 키우거나 영역을 줄이세요.';
  const ids=new Set<string>();
  for(const s of recipe.steps){
    if(!s||typeof s.id!=='string'||!s.id||s.id.length>64||ids.has(s.id)||typeof s.name!=='string'||!s.name.trim()||s.name.length>80||!Object.hasOwn(STEP_LABELS,s.kind))return '단계 이름·종류·고유 ID를 확인하세요.';
    ids.add(s.id);
    for(const f of STEP_FIELDS[s.kind]){const v=s[f.key];if(typeof v!=='number'||!Number.isFinite(v)||v<f.min||v>f.max)return `${s.name}: ${f.label} 범위를 확인하세요.`;}
    if(s.kind==='stack'&&(!Number.isInteger(s.count)||s.si_nm!<d.grid_nm||s.sige_nm!<d.grid_nm))return '적층 두께는 격자 이상이고 층 수는 정수여야 합니다.';
    if(s.kind==='mask'&&(s.width_nm!<d.grid_nm||Math.abs(s.center_nm!)+s.width_nm!/2>d.width_nm/2))return '마스크가 영역을 벗어나거나 격자보다 작습니다.';
    if(['deposit','directional_etch','selective_etch'].includes(s.kind)&&!['Si','SiGe','SiO2','HfO2','TiN','PolySi','Si3N4',...(s.kind==='directional_etch'?['all']:[])].includes(s.material??''))return '지원하지 않는 재료입니다.';
  }
  return null;
}
export function parseRecipe(raw:string):FlowRecipe {
  const parsed=JSON.parse(raw);
  const candidate=parsed.format==='process-flow-recipe-v1'?parsed.recipe:parsed.format==='process-flow-run-v1'?parsed.request:parsed;
  const recipe:FlowRecipe={name:candidate?.name,domain:candidate?.domain,steps:candidate?.steps};
  const problem=recipeProblem(recipe);if(problem)throw new Error(problem);return recipe;
}
export function decodeGrid(run:FlowRun,frame:FlowFrame):Uint8Array {
  const [ny,nx]=run.shape,grid=new Uint8Array(nx*ny);
  for(const [row,col,count,material] of frame.spans)grid.fill(material,row*nx+col,row*nx+col+count);
  return grid;
}
export interface CutSegment {material:number;start_nm:number;end_nm:number;width_nm:number}
export function lineCut(run:FlowRun,grid:Uint8Array,axis:'horizontal'|'vertical',position:number):{coordinate:number;segments:CutSegment[];x:number[];ids:number[]} {
  const [ny,nx]=run.shape,d=run.request.domain,g=d.grid_nm;
  const index=Math.max(0,Math.min((axis==='horizontal'?ny:nx)-1,Math.floor((position-(axis==='horizontal'?d.bottom_nm:-d.width_nm/2))/g)));
  const origin=axis==='horizontal'?-d.width_nm/2:d.bottom_nm,length=axis==='horizontal'?nx:ny;
  const ids=Array.from({length},(_,i)=>grid[axis==='horizontal'?index*nx+i:i*nx+index]);
  const segments:CutSegment[]=[];
  for(let a=0;a<ids.length;){let b=a+1;while(b<ids.length&&ids[b]===ids[a])b++;if(ids[a])segments.push({material:ids[a],start_nm:origin+a*g,end_nm:origin+b*g,width_nm:(b-a)*g});a=b;}
  return {coordinate:(axis==='horizontal'?d.bottom_nm:-d.width_nm/2)+(index+.5)*g,segments,x:ids.map((_,i)=>origin+(i+.5)*g),ids};
}
/** Illustrative PSF + additive noise. Intensities are assumed, not calibrated SEM. */
export function virtualSEM(run:FlowRun,grid:Uint8Array,sigmaNm:number,noise:number,seed=42):Float32Array {
  const [ny,nx]=run.shape,sigma=sigmaNm/run.request.domain.grid_nm;
  const contrast=new Map(run.materials.map(m=>[m.id,m.contrast]));
  let values=Float32Array.from(grid,id=>contrast.get(id)??0);
  if(sigma>0){
    const radius=Math.ceil(sigma*3),kernel=Array.from({length:2*radius+1},(_,i)=>Math.exp(-.5*((i-radius)/sigma)**2));
    const sum=kernel.reduce((a,b)=>a+b,0);kernel.forEach((v,i)=>kernel[i]=v/sum);
    for(const horizontal of [true,false]){
      const next=new Float32Array(values.length);
      for(let r=0;r<ny;r++)for(let c=0;c<nx;c++){
        let v=0;for(let k=-radius;k<=radius;k++){
          const rr=horizontal?r:Math.max(0,Math.min(ny-1,r+k));const cc=horizontal?Math.max(0,Math.min(nx-1,c+k)):c;
          v+=values[rr*nx+cc]*kernel[k+radius];
        }next[r*nx+c]=v;
      }values=next;
    }
  }
  let state=seed>>>0;
  const random=()=>{state=(Math.imul(1664525,state)+1013904223)>>>0;return (state+.5)/4294967296;};
  return values.map(v=>Math.min(1,Math.max(0,v+noise*Math.sqrt(-2*Math.log(random()))*Math.cos(2*Math.PI*random()))));
}
export function thresholdSegments(x:number[],signal:number[],threshold:number,dx:number):{start_nm:number;end_nm:number;width_nm:number}[]{
  const segments=[];
  for(let a=0;a<signal.length;){if(signal[a]<threshold){a++;continue;}let b=a+1;while(b<signal.length&&signal[b]>=threshold)b++;
    const start=x[a]-dx/2,end=x[b-1]+dx/2;segments.push({start_nm:start,end_nm:end,width_nm:end-start});a=b;}
  return segments;
}
