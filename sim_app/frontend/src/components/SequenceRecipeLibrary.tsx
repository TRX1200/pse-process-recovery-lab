import {useState} from 'react';
import {Save,FolderOpen,Download} from 'lucide-react';
import type {SavedSequenceRecipe} from '../sequencePractice';
import {exportJson} from '../storage';

export function SequenceRecipeLibrary({recipes,problem,locked,onSave,onLoad}:{
  recipes:SavedSequenceRecipe[];problem:string|null;locked:boolean;
  onSave:(name:string,note:string)=>void;onLoad:(recipe:SavedSequenceRecipe)=>void;
}){
  const [name,setName]=useState(''),[note,setNote]=useState('');
  return <div className="seq-library"><p>직접 만든 입력 조건을 이 브라우저에 저장합니다. 과제의 정답을 제공하거나 자동으로 적용하지 않습니다.</p>
    <label>레시피 이름<input value={name} maxLength={80} placeholder="예: 노출 시간 비교 1" onChange={e=>setName(e.target.value)}/></label>
    <label>메모<input value={note} maxLength={500} placeholder="이 조건을 저장하는 이유" onChange={e=>setNote(e.target.value)}/></label>
    {problem&&<p role="alert" className="seq-inline-error">{problem}</p>}
    <button className="seq-accent" disabled={locked||!!problem||!name.trim()||recipes.length>=30} onClick={()=>{onSave(name.trim(),note);setName('');setNote('');}}><Save size={14}/>현재 입력 저장</button>
    <div className="seq-library-heading"><h3>내 레시피 {recipes.length} / 30</h3><button disabled={!recipes.length} onClick={()=>exportJson('my-process-recipes.json',{format:'sequence-recipes-v1',recipes})}><Download size={13}/>JSON</button></div>
    {recipes.length===0?<p className="seq-empty-small">저장한 레시피가 없습니다.</p>:<div className="seq-library-list">{[...recipes].reverse().map(r=><button key={r.id} disabled={locked} onClick={()=>onLoad(r)}><FolderOpen size={16}/><span><strong>{r.name}</strong><small>{r.params.pulse_s} s · {r.params.pressure_pa} Pa · {r.params.cycles} cycles</small>{r.note&&<small>{r.note}</small>}</span><b>불러오기</b></button>)}</div>}
  </div>;
}
