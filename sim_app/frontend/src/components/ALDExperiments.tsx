import {useState} from 'react';
import {download,exportJson} from '../storage';
import {sameInputs} from '../sequence';
import type {ALDRecipe,ALDRecipeCatalog} from '../sequence';
import type {NativeParameter} from '../native';
import type {Params} from '../types';

const SUMMARY_KEYS=['pressure_pa','pulse_s','cycles','width_nm'] as const;

export function ALDExperiments({catalog,fields,params,resultParams,disabled,error,selected,onSelect,onApply}:{
  catalog:ALDRecipeCatalog|null;fields:NativeParameter[];params:Params;resultParams:Params;
  disabled:boolean;error:string;selected:string;onSelect:(id:string)=>void;onApply:(recipe:ALDRecipe)=>void;
}){
  const [exportError,setExportError]=useState('');
  async function saveMatrix(){
    setExportError('');
    try{
      const response=await fetch(`${import.meta.env.BASE_URL}native/ald-experiments.csv`);
      if(!response.ok)throw new Error(`HTTP ${response.status}`);
      const text=await response.text();
      download('ald-experiments.csv','\uFEFF'+text.replace(/^\uFEFF/,''),'text/csv;charset=utf-8');
    }catch(e){setExportError(`실험표 다운로드 실패: ${String(e)}`);}
  }
  if(!catalog)return <div className="seq-scroll"><p role={error?'alert':undefined}>{error||'증착 실험을 불러옵니다…'}</p></div>;
  const recipe=catalog.recipes.find(r=>r.id===selected)??catalog.recipes[0];
  const p=recipe.request.params;
  const reference=catalog.recipes.find(r=>r.id===recipe.compare_to);
  const applied=sameInputs(params,p),computed=sameInputs(resultParams,p);
  const spec=(key:string)=>fields.find(f=>f.key===key);
  return <div className="ald-experiments">
    <nav className="ald-recipe-nav" aria-label="증착 실험 선택">{catalog.recipes.map(r=><button key={r.id} aria-label={`${r.id} ${r.title}`} aria-pressed={r.id===recipe.id} title={r.title} onClick={()=>onSelect(r.id)}>{r.id}</button>)}</nav>
    <article className="ald-recipe-card">
      <header><span>{recipe.id} / 10</span><h2>{recipe.title}</h2><p>{recipe.question}</p></header>
      <dl className="ald-recipe-values">{SUMMARY_KEYS.map(key=><div key={key} data-changed={recipe.changed_keys.includes(key)}><dt>{spec(key)?.label}</dt><dd>{p[key]}<small>{spec(key)?.unit}</small></dd></div>)}</dl>
      <div className="ald-recipe-comparison"><strong>{reference?`${reference.id} 대비 변경`:'모든 비교의 기준'}</strong><span>{reference?recipe.changed_keys.map(key=>`${spec(key)?.label}: ${reference.request.params[key]} → ${p[key]} ${spec(key)?.unit}`).join(' / '):'식각 5 s · 온도 300 °C · 격자 5 nm · 300 rays · 고정 시드'}</span></div>
      <div className="ald-recipe-reason"><div><h3>확인할 가설</h3><p>{recipe.hypothesis}</p></div><div><h3>결과에서 볼 것</h3><p>{recipe.observe}</p></div></div>
      <p className="ald-recipe-status" role="status">{applied?(computed?'이 입력과 일치하는 계산 결과가 표시 중입니다.':'입력 적용됨 · 설정창의 ‘연속 공정 계산’으로 결과를 확인하세요.'):'아직 적용 전 · 조건 적용 시 구조·식각·수치 설정까지 이 레시피 값으로 바뀝니다.'}</p>
      {exportError&&<p role="alert" className="seq-warning">{exportError}</p>}
      <div className="ald-recipe-actions"><button className="ald-apply" disabled={disabled} onClick={()=>onApply(recipe)}>이 조건 적용</button><button onClick={()=>exportJson(`ald-${recipe.id}-input.json`,recipe.request)}>입력 JSON</button><button onClick={()=>void saveMatrix()}>실험표 CSV</button><a href="https://github.com/TRX1200/pse-process-recovery-lab/blob/main/docs/ALD_EXPERIMENTS_KR.md" target="_blank" rel="noreferrer">실험 설명서</a></div>
    </article>
    <p className="ald-recipe-footnote">먼저 D01을 계산해 ‘현재 결과 비교 고정’을 누르세요. D10은 D09와 비교합니다. 가설은 미검증이며, 새 결과는 실제 계산 후 생성됩니다.</p>
  </div>;
}
