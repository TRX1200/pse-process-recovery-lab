import {Download,Plus,Table2,X} from 'lucide-react';
import type {RunRecord} from '../sequencePractice';
import {recordCsv} from '../sequencePractice';
import {download} from '../storage';
import {SHORT_LABELS} from '../sequenceControls';
import type {NativeParameter} from '../native';

const METRICS=[['etch','center_depth_nm','식각 깊이','nm'],['etch','width_half_depth_nm','식각 폭','nm'],['etch','mask_loss_nm','마스크 소모','nm'],['ald','top_film_nm','상단 두께','nm'],['ald','bottom_film_nm','바닥 두께','nm'],['ald','bottom_top_pct','바닥 / 상단','%'],['ald','mid_gap_nm','통로 폭','nm']] as const;
export function SequenceCompare({records,current,fields,onAdd,onRemove}:{records:RunRecord[];current:RunRecord;fields:NativeParameter[];onAdd:()=>void;onRemove:(hash:string)=>void}){
  const changed=fields.filter(f=>records.length>1&&records.some(r=>r.params[f.key]!==records[0].params[f.key]));
  return <div className="seq-comparison seq-scroll"><div className="seq-panel-heading"><div><h2><Table2 size={19}/>실험 비교표</h2><p>완료된 결과를 최대 6개까지 모아 조건과 지표를 비교하세요.</p></div><button className="seq-accent" onClick={onAdd} disabled={records.length>=6||records.some(r=>r.hash===current.hash)}><Plus size={14}/>현재 결과 담기</button></div>
    {records.length===0?<div className="seq-empty"><Table2 size={34}/><h3>첫 결과를 비교표에 담아보세요</h3><p>조건을 바꿔 다시 계산한 다음 결과를 추가하면 차이가 표시됩니다.</p></div>:<>
      <div className="seq-table-wrap"><table className="seq-comparison-table"><thead><tr><th>측정 지표</th>{records.map((r,i)=><th key={r.hash}><span>{i===0?'기준':'비교 '+i} · {r.hash.slice(0,6)}<button aria-label={`비교 결과 ${r.hash.slice(0,6)} 제거`} onClick={()=>onRemove(r.hash)}><X size={12}/></button></span><small>{r.source==='example'?'저장 예제':'로컬 계산'}</small></th>)}</tr></thead><tbody>{METRICS.map(([stage,key,label,unit])=><tr key={key}><th>{label}<small>{unit}</small></th>{records.map((r,i)=>{const value=r[stage][key],base=records[0][stage][key];return <td key={r.hash}>{value==null?'—':value.toFixed(2)}{i>0&&value!=null&&base!=null&&<small className="seq-delta">{value-base>=0?'+':''}{(value-base).toFixed(2)} {unit}</small>}</td>;})}</tr>)}
      <tr className="seq-table-divider"><th colSpan={records.length+1}>변경한 입력 {changed.length}개 · 첫 결과 기준</th></tr>{changed.map(f=><tr key={f.key}><th>{SHORT_LABELS[f.key]??f.label}<small>{f.unit}</small></th>{records.map(r=><td key={r.hash} data-changed={r.params[f.key]!==records[0].params[f.key]}>{r.params[f.key]}</td>)}</tr>)}
      </tbody></table></div><div className="seq-comparison-footer"><p>여러 조건이 달라지면 단일 변수의 효과로 해석할 수 없습니다. CSV에 전체 입력과 실행 해시를 포함합니다.</p><button onClick={()=>download('process-comparison.csv',recordCsv(records),'text/csv')}><Download size={14}/>비교 CSV</button></div>
    </>}</div>;
}
