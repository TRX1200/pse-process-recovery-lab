import {useState} from 'react';
import {Play,Square,RotateCcw,ChevronLeft,ChevronRight} from 'lucide-react';
import {CONTROL_GROUPS,SHORT_LABELS,adjustmentStep,adjustedValue,controlFields,changedFields} from '../sequenceControls';
import type {ControlGroup} from '../sequenceControls';
import {sameInputs} from '../sequence';
import type {ALDRecipe,ALDRecipeCatalog} from '../sequence';
import type {NativeParameter} from '../native';
import type {Params} from '../types';

export function SequenceSettings({fields,params,baseline,recipes,locked,active,available,problem,
  onChange,onRecipe,onRestore,onRun,onCancel,onExperiments}:{
  fields:NativeParameter[];params:Params;baseline:Params;recipes:ALDRecipeCatalog|null;
  locked:boolean;active:boolean;available:boolean;problem:string|null;
  onChange:(key:string,value:number)=>void;onRecipe:(recipe:ALDRecipe)=>void;onRestore:()=>void;
  onRun:()=>void;onCancel:()=>void;onExperiments:()=>void;
}){
  const [group,setGroup]=useState<ControlGroup>('quick');
  const [page,setPage]=useState(0),[helpKey,setHelpKey]=useState('pressure_pa');
  const all=controlFields(fields,group),size=group==='quick'?8:6;
  const pages=Math.max(1,Math.ceil(all.length/size));
  const visible=all.slice(page*size,(page+1)*size);
  const help=visible.find(f=>f.key===helpKey)??visible[0];
  const changes=changedFields(fields,params,baseline);
  const preset=recipes?.recipes.find(r=>sameInputs(r.request.params,params));
  function chooseGroup(next:ControlGroup){setGroup(next);setPage(0);}
  return <aside className="seq-settings" aria-label="공정 파라미터 설정">
    <div className="seq-settings-title"><h2>공정 조건</h2><span>{changes?`${changes}개 변경`:'계산값과 일치'}</span></div>
    <div className="seq-preset-row"><select aria-label="증착 레시피 빠른 적용" value={preset?.id??''} disabled={locked||!recipes} onChange={e=>{
      const recipe=recipes?.recipes.find(r=>r.id===e.target.value);if(recipe){onRecipe(recipe);chooseGroup('quick');}
    }}><option value="" disabled>증착 레시피 불러오기</option>{recipes?.recipes.map(r=><option key={r.id} value={r.id}>{r.id} · {r.title}</option>)}</select><button onClick={onExperiments} title="10개 실험의 가설과 비교 방법">실험 안내</button></div>
    <nav className="seq-setting-tabs" aria-label="파라미터 분류">{Object.entries(CONTROL_GROUPS).map(([key,label])=><button key={key} aria-pressed={group===key} onClick={()=>chooseGroup(key as ControlGroup)}>{label}</button>)}</nav>
    <div className="seq-settings-body">
      <div className="seq-parameter-grid">{visible.map(field=>{
        const value=params[field.key],changed=value!==baseline[field.key];
        const invalid=!Number.isFinite(value)||value<field.min||value>field.max||(field.integer&&!Number.isInteger(value));
        return <div className="seq-parameter" key={field.key} data-changed={changed} data-invalid={invalid}>
          <div className="seq-parameter-label"><label htmlFor={`seq-input-${field.key}`} title={field.label}>{SHORT_LABELS[field.key]??field.label}</label><small>{field.unit}</small><button className="seq-field-help" aria-label={`${field.label} 설명`} onClick={()=>setHelpKey(field.key)}>?</button></div>
          <div className="seq-number"><button aria-label={`${field.label} 감소`} disabled={locked} onClick={()=>{setHelpKey(field.key);onChange(field.key,adjustedValue(field,value,-1));}}>−</button><input id={`seq-input-${field.key}`} type="number" aria-label={field.label} aria-invalid={invalid} disabled={locked} min={field.min} max={field.max} step={field.integer?1:'any'} value={Number.isFinite(value)?value:''} onFocus={()=>setHelpKey(field.key)} onChange={e=>onChange(field.key,e.target.value===''?NaN:Number(e.target.value))}/><button aria-label={`${field.label} 증가`} disabled={locked} onClick={()=>{setHelpKey(field.key);onChange(field.key,adjustedValue(field,value,1));}}>+</button></div>
          {group==='quick'&&<input className="seq-adjust-slider" type="range" aria-label={`${field.label} 빠른 조절`} min={field.min} max={field.max} step={field.key==='pulse_s'?.001:field.key==='cycles'||field.key==='ion_exponent'?1:adjustmentStep(field)} value={Number.isFinite(value)?Math.min(field.max,Math.max(field.min,value)):field.default} disabled={locked} onChange={e=>{setHelpKey(field.key);onChange(field.key,Number(e.target.value));}}/>}
        </div>;
      })}</div>
      {pages>1&&<div className="seq-setting-pager"><button aria-label="이전 설정 항목" disabled={page===0} onClick={()=>setPage(p=>p-1)}><ChevronLeft size={14}/></button><span>{page+1} / {pages} · {all.length}개 항목</span><button aria-label="다음 설정 항목" disabled={page===pages-1} onClick={()=>setPage(p=>p+1)}><ChevronRight size={14}/></button></div>}
      {help&&<div className="seq-field-guide" aria-live="polite"><div><strong>{help.label}</strong><span>{help.min}–{help.max} {help.unit}</span></div><p>{help.description}</p></div>}
    </div>
    <div className="seq-settings-bottom"><button className="seq-restore" disabled={locked||!changes} onClick={onRestore}><RotateCcw size={13}/>계산값으로 되돌리기</button>
      {active?<button className="seq-run" onClick={onCancel}><Square size={14}/>계산 중단</button>:<button className="seq-run" disabled={locked||!available||!!problem} onClick={onRun}><Play size={15}/>연속 공정 계산</button>}
      {!available&&<small>새 계산은 로컬 Python 서버에서 실행합니다.</small>}
    </div>
  </aside>;
}
