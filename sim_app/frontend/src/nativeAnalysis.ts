import type {Contour, NativeFrame, NativeRun} from './native';
import type {ModelKey, Series} from './types';

export const NATIVE_REVIEW_VERSION='native-target-review-1.0';
export interface NativeGoal {
  advance_nm:number; width_nm:number; tolerance_nm:number; width_tolerance_nm:number;
  roughness_nm:number; shape_tolerance_nm:number; conformality_pct:number; gap_nm:number;
  coating:'conformal'|'flat';
}
export interface GoalField {key:Exclude<keyof NativeGoal,'coating'>;label:string;unit:string;min:number;max:number}
export interface ReviewRow {key:string;label:string;unit:string;value:number|null;target:string;status:'pass'|'fail'|'unknown';advice:string}
export interface NativeReview {version:string;status:'pass'|'fail'|'unknown';rows:ReviewRow[];warnings:string[];goal:NativeGoal;at:number}
type XY=[number,number];
const mean=(a:number[])=>a.reduce((s,v)=>s+v,0)/a.length;
const rms=(a:number[])=>Math.sqrt(mean(a.map(v=>v*v)));
export const profileOf=(run:NativeRun)=>run.params.surface_profile??0;
export const goalKey=(model:ModelKey,profile:number)=>`${model}-${profile}`;
export function defaultGoal(model:ModelKey,profile:number):NativeGoal {
  // Learning examples, not equipment specifications or targets fitted to a run.
  return {advance_nm:model==='etch'?(profile===1?10:250):(profile===0?20:4),
    width_nm:profile===2?120:100,tolerance_nm:model==='etch'?(profile===1?2:20):2,
    width_tolerance_nm:15,roughness_nm:profile===1?6:3,shape_tolerance_nm:model==='etch'?10:3,
    conformality_pct:90,gap_nm:30,coating:'conformal'};
}
/** A bounded, versioned session draft; only recognized fields cross the boundary. */
export function parseGoalDraft(raw:string|null):Record<string,NativeGoal> {
  if(!raw)return {};
  let data:unknown;try{data=JSON.parse(raw);}catch{return {};}
  if(!data||typeof data!=='object'||Array.isArray(data))return {};
  const result:Record<string,NativeGoal>={},keys=Object.keys(defaultGoal('etch',0)) as (keyof NativeGoal)[];
  for(const [key,value] of Object.entries(data)){
    if(!/^(etch|ald)-[012]$/.test(key)||!value||typeof value!=='object'||Array.isArray(value))continue;
    if(!keys.every(k=>k==='coating'?['flat','conformal'].includes(value[k]):typeof value[k]==='number'&&Number.isFinite(value[k])))continue;
    result[key]=Object.fromEntries(keys.map(k=>[k,value[k]])) as unknown as NativeGoal;
  }
  return result;
}
export function goalFields(model:ModelKey,profile:number):GoalField[] {
  const fields:GoalField[]=[
    {key:'advance_nm',label:model==='etch'?(profile===1?'목표 평균 제거량':'목표 최종 깊이'):'목표 막 두께',unit:'nm',min:0,max:4000},
    {key:'tolerance_nm',label:model==='etch'?'깊이 / 제거량 허용오차':'막 두께 허용오차',unit:'± nm',min:.01,max:1000},
    {key:'roughness_nm',label:profile===1?'표면 Rq 상한':model==='etch'?'측벽 / 바닥 Rq 상한':'측벽 Rq 상한',unit:'nm',min:0,max:200},
    {key:'shape_tolerance_nm',label:'목표 단면 RMS 거리 상한',unit:'nm',min:.01,max:1000},
  ];
  if(model==='etch'&&profile!==1)fields.splice(2,0,
    {key:'width_nm',label:'목표 홈 폭 (CD)',unit:'nm',min:1,max:2000},
    {key:'width_tolerance_nm',label:'홈 폭 허용오차',unit:'± nm',min:.01,max:1000});
  if(model==='ald'&&profile!==1)fields.push(
    {key:'conformality_pct',label:'바닥 / 상단 두께비 하한',unit:'%',min:0,max:100},
    {key:'gap_nm',label:'남아야 할 최소 통로',unit:'nm',min:0,max:2000});
  return fields;
}
export function goalError(run:NativeRun,goal:NativeGoal):string|null {
  for(const f of goalFields(run.model,profileOf(run)))if(!Number.isFinite(goal[f.key])||goal[f.key]<f.min||goal[f.key]>f.max)return `${f.label}: ${f.min}–${f.max} ${f.unit} 범위를 입력하세요.`;
  if(!['flat','conformal'].includes(goal.coating))return '목표 코팅 형식을 선택하세요.';
  if(run.model==='etch'&&profileOf(run)!==1&&goal.width_nm>=run.params.pitch_nm*.9)return '목표 폭은 계산 영역 폭의 90%보다 작아야 합니다.';
  if(run.model==='ald'&&profileOf(run)!==1&&2*goal.advance_nm>=run.params.width_nm)return '목표 두께가 초기 개구 폭의 절반 이상입니다. 닫힌 통로의 목표 형상은 지원하지 않습니다.';
  return null;
}
export function intersections(paths:Contour[],value:number,axis:0|1):number[] {
  const hits:number[]=[];
  for(const path of paths)for(let i=1;i<path.length;i++){
    const a=path[i-1],b=path[i],delta=b[axis]-a[axis];
    if(Math.abs(delta)<1e-12)continue;
    const t=(value-a[axis])/delta;
    if(t>=-1e-10&&t<=1+1e-10)hits.push(a[1-axis]+t*(b[1-axis]-a[1-axis]));
  }
  return hits.filter(Number.isFinite).sort((a,b)=>a-b);
}
export function topAt(paths:Contour[],x:number):number|null {const hits=intersections(paths,x,0);return hits.length?hits[hits.length-1]:null;}
export function surfacePaths(run:NativeRun,frame:NativeFrame):Contour[] {
  const paths=(run.model==='etch'?frame.layers.find(l=>l.material==='Si'):frame.layers.at(-1))?.paths_nm??[];
  if(run.model!=='etch'||profileOf(run)!==0)return paths;
  // ViennaPS' Si level set includes the mask union above y=0. Compare the
  // exposed Si trench and the protected original plane, not mask height.
  return paths.map(path=>path.flatMap((b,i)=>{
    const a=path[i-1];
    const crossing=a&&a[1]*b[1]<0?[a[0]+(b[0]-a[0])*(-a[1])/(b[1]-a[1]),0]:null;
    return [...(crossing?[crossing]:[]),[b[0],Math.min(0,b[1])]];
  }));
}
function sampleTop(paths:Contour[],half:number,n=256):{x:number[];y:(number|null)[]} {
  const x=Array.from({length:n},(_,i)=>-half+2*half*(i+.5)/n);
  return {x,y:x.map(v=>topAt(paths,v))};
}
function complete(a:(number|null)[]):a is number[]{return a.length>0&&a.every(v=>v!==null&&Number.isFinite(v));}
function detrendedRq(x:number[],y:(number|null)[]):number|null {
  if(!complete(y)||x.length!==y.length||x.length<3)return null;
  const mx=mean(x),my=mean(y),xx=x.reduce((s,v)=>s+(v-mx)**2,0);
  const slope=xx?x.reduce((s,v,i)=>s+(v-mx)*(y[i]-my),0)/xx:0;
  return rms(y.map((v,i)=>v-my-slope*(x[i]-mx)));
}
export function wallProfile(paths:Contour[],depth:number):{depth:number[];left:(number|null)[];right:(number|null)[];width:(number|null)[]} {
  const d=Array.from({length:161},(_,i)=>depth*(.1+.8*i/160));
  const left:(number|null)[]=[],right:(number|null)[]=[],width:(number|null)[]=[];
  for(const v of d){const hits=intersections(paths,-v,1),l=hits.filter(x=>x<0).at(-1),r=hits.find(x=>x>=0);
    left.push(l??null);right.push(r??null);width.push(l!==undefined&&r!==undefined?r-l:null);}
  return {depth:d,left,right,width};
}
function pointDistance(p:number[],paths:Contour[]):number|null {
  let best=Infinity;
  for(const path of paths)for(let i=1;i<path.length;i++){
    const a=path[i-1],b=path[i],dx=b[0]-a[0],dy=b[1]-a[1],den=dx*dx+dy*dy;
    const t=den?Math.max(0,Math.min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/den)):0;
    best=Math.min(best,Math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy));
  }
  return Number.isFinite(best)?best:null;
}
function arclengthSamples(paths:Contour[],n=97):XY[] {
  const segments:{a:number[];b:number[];length:number}[]=[];
  for(const path of paths)for(let i=1;i<path.length;i++){
    const length=Math.hypot(path[i][0]-path[i-1][0],path[i][1]-path[i-1][1]);
    if(length>1e-12&&Number.isFinite(length))segments.push({a:path[i-1],b:path[i],length});
  }
  const total=segments.reduce((s,e)=>s+e.length,0);if(!total)return [];
  let index=0,offset=0;return Array.from({length:n},(_,i)=>{
    const at=total*(i+.5)/n;while(index<segments.length-1&&offset+segments[index].length<at){offset+=segments[index++].length;}
    const {a,b,length}=segments[index],t=(at-offset)/length;return [a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1])] as XY;
  });
}
/** Symmetric nearest-contour RMS, 97 equal-arclength samples per direction. */
export function contourError(a:Contour[],b:Contour[]):number|null {
  const sa=arclengthSamples(a),sb=arclengthSamples(b);if(!sa.length||!sb.length)return null;
  const d=[...sa.map(p=>pointDistance(p,b)),...sb.map(p=>pointDistance(p,a))];return complete(d)?rms(d):null;
}
export function targetPaths(run:NativeRun,goal:NativeGoal):Contour[] {
  if(goalError(run,goal))return [];
  const p=run.params,profile=profileOf(run),half=p.pitch_nm/2,t=goal.advance_nm;
  if(run.model==='etch')return profile===1?[[[-half,-t],[half,-t]]]:[
    [[-half,0],[-goal.width_nm/2,0],[-goal.width_nm/2,-t],[goal.width_nm/2,-t],[goal.width_nm/2,0],[half,0]]];
  if(profile===1&&goal.coating==='flat')return [[[-half,t],[half,t]]];
  // Geometric design offset, not a second deposition solver. Orient open paths
  // left-to-right so the left normal points toward the gas. Limit sharp miters.
  return (run.frames[0].layers.find(l=>l.material==='Si')?.paths_nm??[]).filter(path=>path.length>1).map(original=>{
    const path=original[0][0]<=original.at(-1)![0]?[...original]:[...original].reverse();
    const normals=path.slice(1).map((b,i)=>{const a=path[i],dx=b[0]-a[0],dy=b[1]-a[1],l=Math.hypot(dx,dy)||1;return [-dy/l,dx/l];});
    return path.map((v,i)=>{const a=normals[Math.max(0,i-1)],b=normals[Math.min(i,normals.length-1)];
      const nx=a[0]+b[0],ny=a[1]+b[1],l=Math.hypot(nx,ny)||1,den=Math.max(.5,(nx*b[0]+ny*b[1])/l);
      return [Math.max(-half,Math.min(half,v[0]+t*nx/l/den)),v[1]+t*ny/l/den];});
  });
}
export interface FrameAnalysis {
  metrics:Record<string,number|null>;top:{x:number[];y:(number|null)[]};
  wall:ReturnType<typeof wallProfile>;thickness:{depth:number[];left:(number|null)[];right:(number|null)[]};
}
export function analyzeFrame(run:NativeRun,frame:NativeFrame,target:Contour[]):FrameAnalysis {
  const p=run.params,profile=profileOf(run),paths=surfacePaths(run,frame),top=sampleTop(paths,p.pitch_nm/2);
  const metrics:Record<string,number|null>={...frame.metrics};
  if(profile===1){
    const my=complete(top.y)?mean(top.y):NaN;
    metrics.roughness_rq_nm=complete(top.y)?rms(top.y.map(y=>y-my)):null;
    // Preserve the engine's advance relative to its measured initial mean.
    if(!('mean_advance_nm' in metrics)){
      const initialTop=sampleTop(surfacePaths(run,run.frames[0]),p.pitch_nm/2);
      metrics.mean_advance_nm=complete(top.y)&&complete(initialTop.y)?(my-mean(initialTop.y))*(run.model==='etch'?-1:1):null;
    }
  }
  // Scallop measurements use the fixed initial-depth ROI, like the Python engine.
  const depth=run.model==='ald'||profile===2?p.depth_nm:(metrics.center_depth_nm??0);
  const wall=wallProfile(paths,depth);
  const enoughWall=profile!==1&&depth>2*p.grid_nm;
  metrics.left_wall_rq_nm=enoughWall?detrendedRq(wall.depth,wall.left):null;
  metrics.right_wall_rq_nm=enoughWall?detrendedRq(wall.depth,wall.right):null;
  const rq=[metrics.left_wall_rq_nm,metrics.right_wall_rq_nm];
  metrics.wall_rq_nm=complete(rq)?Math.max(...rq):null;
  const floor=sampleTop(paths,p.width_nm*.3,65);
  const floorMean=complete(floor.y)?mean(floor.y):NaN;
  metrics.floor_rq_nm=profile!==1&&complete(floor.y)?rms(floor.y.map(y=>y-floorMean)):null;
  if(run.model==='ald'&&(metrics.top_film_nm??0)<=1e-6)metrics.bottom_top_pct=null;
  if(run.model==='etch'&&profile!==1&&(metrics.center_depth_nm??0)<=1e-6)metrics.width_half_depth_nm=null;
  metrics.target_rms_nm=contourError(paths,target);
  const initial=run.frames[0].layers.find(l=>l.material==='Si')?.paths_nm??[];
  const thickness={depth:wall.depth,left:wall.left.map((x,i)=>x===null?null:pointDistance([x,-wall.depth[i]],initial)),right:wall.right.map((x,i)=>x===null?null:pointDistance([x,-wall.depth[i]],initial))};
  return {metrics,top,wall,thickness};
}
export function evaluateNative(run:NativeRun,frame:NativeFrame,goal:NativeGoal,analysis:FrameAnalysis):NativeReview {
  const profile=profileOf(run),rows:ReviewRow[]=[],warnings:string[]=[],error=goalError(run,goal);
  const add=(key:string,label:string,unit:string,target:string,pass:(v:number)=>boolean,advice:string)=>{
    const raw=analysis.metrics[key],value=raw!=null&&Number.isFinite(raw)?raw:null;
    rows.push({key,label,unit,value,target,status:error||value===null?'unknown':pass(value)?'pass':'fail',advice});
  };
  const near=(v:number,t:number,tolerance:number)=>Math.abs(v-t)<=tolerance+1e-9;
  if(run.model==='etch'){
    add(profile===1?'mean_advance_nm':'center_depth_nm',profile===1?'평균 제거량':'최종 깊이','nm',`${goal.advance_nm} ± ${goal.tolerance_nm}`,v=>near(v,goal.advance_nm,goal.tolerance_nm),'시간에 따른 진행량과 이온·F 공급을 각각 비교하세요. 원인은 이 지표 하나로 확정할 수 없습니다.');
    if(profile!==1)add('width_half_depth_nm','절반 깊이의 홈 폭','nm',`${goal.width_nm} ± ${goal.width_tolerance_nm}`,v=>near(v,goal.width_nm,goal.width_tolerance_nm),'이온 방향성과 O 공급을 한 변수씩 비교하고 측벽 프로파일을 확인하세요.');
  }else{
    add(profile===1?'mean_advance_nm':'top_film_nm',profile===1?'평균 높이 증가':'상단 막 두께','nm',`${goal.advance_nm} ± ${goal.tolerance_nm}`,v=>near(v,goal.advance_nm,goal.tolerance_nm),'사이클 수와 pulse 노출을 구분해 비교하세요. 온도는 현재 모델에서 열 플럭스만 바꿉니다.');
    if(profile!==1){
      add('bottom_top_pct','바닥 / 상단 피복','%',`≥ ${goal.conformality_pct}`,v=>v>=goal.conformality_pct,'두께가 0인 초기 프레임에서는 비율을 정의할 수 없습니다. 노출 시간과 깊이별 막 두께를 비교하세요.');
      add('minimum_gap_nm','샘플 위치 최소 통로','nm',`≥ ${goal.gap_nm}`,v=>v>=goal.gap_nm,'두꺼운 막은 통로를 좁힙니다. 목표 두께와 잔여 통로 조건을 동시에 확인하세요.');
    }
  }
  add(profile===1?'roughness_rq_nm':'wall_rq_nm',profile===1?'표면 Rq':'측벽 Rq (큰 쪽)','nm',`≤ ${goal.roughness_nm}`,v=>v<=goal.roughness_nm,'초기 요철과 최종 형상을 비교하세요. ALD는 요철을 따라 덮을 수 있습니다. grid·seed·입자 수 변화도 확인하세요.');
  if(profile!==1&&run.model==='etch')add('floor_rq_nm','중앙 바닥 Rq','nm',`≤ ${goal.roughness_nm}`,v=>v<=goal.roughness_nm,'초기 폭의 중앙 60%에서 측정합니다. 바닥 기울기·microtrench 전체를 대표하지 않으므로 단면도 확인하세요.');
  add('target_rms_nm','목표 단면 RMS 거리','nm',`≤ ${goal.shape_tolerance_nm}`,v=>v<=goal.shape_tolerance_nm,'전체 형상 차이입니다. 깊이·폭·두께·거칠기 중 무엇이 어긋나는지 위 항목과 함께 확인하세요.');
  if(error)warnings.push(error);
  if(Math.min(goal.tolerance_nm,goal.shape_tolerance_nm,goal.roughness_nm,...(run.model==='etch'&&profile!==1?[goal.width_tolerance_nm]:[]))<run.params.grid_nm)warnings.push(`격자 ${run.params.grid_nm} nm보다 작은 목표 한계가 있습니다. 수치 민감도 확인 전에는 미세 차이를 확정하지 마세요.`);
  if(run.warnings.length)warnings.push(...run.warnings);
  if(frame.at<run.frames.at(-1)!.at)warnings.push('현재 재생 시점의 중간 평가입니다. 최종 판정과 구분하세요.');
  return {version:NATIVE_REVIEW_VERSION,status:rows.some(r=>r.status==='fail')?'fail':rows.some(r=>r.status==='unknown')?'unknown':'pass',rows,warnings,goal:{...goal},at:frame.at};
}
const numbers=(v:(number|null)[])=>v.map(n=>n??NaN);
export function nativeCharts(run:NativeRun,goal:NativeGoal,analyses:FrameAnalysis[],index:number):{history:Series[];spatial:Series[]} {
  const profile=profileOf(run),a=analyses[index],x=run.frames.map(f=>f.at);
  const metric=(key:string)=>analyses.map(v=>v.metrics[key]??NaN);
  const graph=(key:string,title:string,unit:string,lines:{name:string;values:number[]}[]):Series=>({key,title,x_label:run.axis_unit,y_label:unit,x,lines});
  const movement=run.model==='etch'?(profile===1?'mean_advance_nm':'center_depth_nm'):(profile===1?'mean_advance_nm':'top_film_nm');
  const moving=metric(movement),rate=moving.map((v,i)=>i&&x[i]>x[i-1]?(v-moving[i-1])/(x[i]-x[i-1]):NaN);
  const history:Series[]=[graph('advance',run.model==='etch'?'제거 / 깊이 진행':'막 성장 진행','nm',[
    {name:'계산',values:moving},{name:'사용자 목표',values:x.map(()=>goal.advance_nm)},
    ...(run.model==='ald'&&profile!==1?[{name:'바닥 막',values:metric('bottom_film_nm')}]:[])]),
    graph('rate',run.model==='etch'?'구간 평균 식각 진행률':'구간 평균 성장량',run.model==='etch'?'nm/s':'nm/cycle',[{name:'완료 구간의 차분',values:rate}]),
    graph('roughness',profile===1?'표면 거칠기 Rq':'측벽 거칠기 Rq','nm',profile===1?[
      {name:'표면',values:metric('roughness_rq_nm')},{name:'허용 상한',values:x.map(()=>goal.roughness_nm)}]:[
      {name:'왼쪽',values:metric('left_wall_rq_nm')},{name:'오른쪽',values:metric('right_wall_rq_nm')},{name:'허용 상한',values:x.map(()=>goal.roughness_nm)}]),
    graph('target-error','목표 단면과의 거리','nm',[{name:'대칭 RMS 거리',values:metric('target_rms_nm')},{name:'허용 상한',values:x.map(()=>goal.shape_tolerance_nm)}])];
  if(profile!==1)history.push(run.model==='etch'?graph('cd','홈 폭과 목표 CD','nm',[{name:'절반 깊이 폭',values:metric('width_half_depth_nm')},{name:'목표 폭',values:x.map(()=>goal.width_nm)}]):
    graph('coverage','바닥 / 상단 피복','%',[{name:'계산',values:metric('bottom_top_pct')},{name:'하한',values:x.map(()=>goal.conformality_pct)}]));
  if(run.model==='ald'&&profile!==1)history.push(graph('gap','막 성장 후 남은 통로','nm',[{name:'최소 통로',values:metric('minimum_gap_nm')},{name:'하한',values:x.map(()=>goal.gap_nm)}]));
  if(run.model==='etch'&&profile!==1)history.push(graph('floor-roughness','중앙 바닥 거칠기 Rq','nm',[{name:'바닥',values:metric('floor_rq_nm')},{name:'허용 상한',values:x.map(()=>goal.roughness_nm)}]));
  const target=targetPaths(run,goal),initial=surfacePaths(run,run.frames[0]);
  const spatial:Series[]=[{key:'height-profile',title:profile===1?'표면 높이와 목표 · 요철 확대':'위에서 보이는 표면 높이',x_label:'x / nm',y_label:'y / nm',x:a.top.x,lines:[
    {name:'현재 계산',values:numbers(a.top.y)},{name:'목표',values:a.top.x.map(v=>topAt(target,v)??NaN)},
    {name:'초기',values:a.top.x.map(v=>topAt(initial,v)??NaN)}]}];
  if(profile===1){const my=complete(a.top.y)?mean(a.top.y):NaN;spatial.push({key:'height-residual',title:'평균면을 뺀 요철 · nm 축',x_label:'x / nm',y_label:'h − 평균(h) / nm',x:a.top.x,lines:[{name:'실제 형상 잔차',values:a.top.y.map(v=>v===null?NaN:v-my)}]});}
  else spatial.push(run.model==='etch'?{key:'depth-width',title:'깊이별 홈 폭 · 현재 프레임',x_label:'표면 아래 깊이 / nm',y_label:'폭 / nm',x:a.wall.depth,lines:[{name:'계산 CD',values:numbers(a.wall.width)},{name:'목표 폭',values:a.wall.depth.map(()=>goal.width_nm)}]}:
    {key:'wall-thickness',title:'깊이별 막–기판 최단 거리',x_label:'초기 표면 아래 깊이 / nm',y_label:'거리 / nm',x:a.thickness.depth,lines:[{name:'왼쪽',values:numbers(a.thickness.left)},{name:'오른쪽',values:numbers(a.thickness.right)},{name:'목표 두께',values:a.thickness.depth.map(()=>goal.advance_nm)}]});
  return {history,spatial};
}
