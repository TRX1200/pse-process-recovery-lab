import {useEffect,useState} from 'react';
import {download,exportJson} from '../storage';
import {captureReport,readReport,emptyReport,REPORT_KEY,reportCsv,reportMarkdown,comparisonReason} from '../projectReport';
import type {ProjectReport as Report,ReportSnapshot} from '../projectReport';
import '../report.css';

export function CaptureReport({snapshot,disabled=false}:{snapshot:ReportSnapshot;disabled?:boolean}) {
  const [status,setStatus]=useState('');
  useEffect(()=>setStatus(''),[snapshot.source_id,snapshot.label]);
  return <span className="capture-report"><button disabled={disabled} onClick={()=>{try{captureReport(snapshot);setStatus('보고서에 추가했습니다. 상단 ‘실험 보고서’에서 메모를 작성하세요.');}catch(e){setStatus(String(e));}}}>보고서에 담기</button>{status&&<small role="status">{status}</small>}</span>;
}

export function ProjectReport() {
  const [loaded]=useState(()=>{try{return {report:readReport(),error:''};}catch(e){return {report:emptyReport(),error:String(e)};}});
  const [error,setError]=useState(loaded.error);
  const [report,setReport]=useState<Report>(loaded.report);
  const [selected,setSelected]=useState<string[]>([]);
  function update(next:Report) {try{localStorage.setItem(REPORT_KEY,JSON.stringify(next));setReport(next);setError('');}catch(e){setError(String(e));}}
  const pair=selected.map(id=>report.entries.find(e=>e.record_id===id)).filter(e=>!!e);
  const reason=pair.length===2?comparisonReason(pair[0],pair[1]):null;
  if(loaded.error) return <section className="project-report"><h1>개인 프로젝트 보고서</h1><p role="alert">{loaded.error}</p><p>기존 저장 내용을 보존했습니다. 저장 형식을 확인한 뒤 다시 여세요.</p></section>;
  return <section className="project-report"><header><span>EXPERIMENT NOTEBOOK</span><h1>개인 프로젝트 보고서</h1><p>계산 화면의 ‘보고서에 담기’로 조건과 결과를 고정하고, 가설·해석은 직접 작성합니다.</p></header>
    {error&&<p role="alert">{error}</p>}
    <p className="native-warning">이 브라우저에 저장됩니다. 작업을 마치면 Markdown·CSV·JSON을 내려받으세요. 로컬과 공개 사이트의 기록은 별도입니다.</p>
    <div className="report-fields"><label>제목<input value={report.title} onChange={e=>update({...report,title:e.target.value})}/></label><label>작성자<input value={report.author} onChange={e=>update({...report,author:e.target.value})}/></label></div>
    {([['objective','연구 질문'],['hypothesis','실험 전 가설'],['discussion','내 해석과 대안 원인'],['next_measurement','추가로 필요한 실제 측정']] as const).map(([key,label])=><label className="report-text" key={key}>{label}<textarea rows={3} value={report[key]} onChange={e=>update({...report,[key]:e.target.value})}/></label>)}
    <div className="report-actions"><button onClick={()=>download('process-project-report.md',reportMarkdown(report),'text/markdown;charset=utf-8')}>보고서 Markdown</button><button onClick={()=>download('process-project-metrics.csv',reportCsv(report),'text/csv;charset=utf-8')}>지표 CSV</button><button onClick={()=>exportJson('process-project-report.json',report)}>전체 기록 JSON</button></div>
    <h2>기록한 실험 · {report.entries.length}</h2><p>두 항목을 선택하면 입력 차이와 지표의 절대 차이를 확인할 수 있습니다.</p>
    {!report.entries.length&&<p>아직 기록이 없습니다. RF 또는 형상 계산 결과에서 ‘보고서에 담기’를 누르세요.</p>}
    {report.entries.map((entry,i)=><article className="report-entry" key={entry.record_id}><header><label><input type="checkbox" aria-label={`실험 ${i+1} 비교 선택`} checked={selected.includes(entry.record_id)} disabled={!selected.includes(entry.record_id)&&selected.length===2} onChange={e=>setSelected(e.target.checked?[...selected,entry.record_id]:selected.filter(id=>id!==entry.record_id))}/>{i+1}. {entry.label}</label><button onClick={()=>{update({...report,entries:report.entries.filter(e=>e.record_id!==entry.record_id)});setSelected(selected.filter(id=>id!==entry.record_id));}}>보고서에서 제외</button></header><small>{entry.version} · {entry.provenance} · {entry.source_id.slice(0,16)}</small>
      <div className="rf-table-scroll"><table><thead><tr><th>지표</th><th>값</th><th>단위</th></tr></thead><tbody>{entry.metrics.map(m=><tr key={m.key}><td>{m.label}</td><td>{m.value===null?'—':m.value.toPrecision(5)}</td><td>{m.unit}</td></tr>)}</tbody></table></div>
      <label className="report-text">이 실험의 해석<textarea rows={2} value={entry.note} onChange={event=>update({...report,entries:report.entries.map(e=>e.record_id===entry.record_id?{...e,note:event.target.value}:e)})}/></label><details><summary>고정된 입력과 계산 가정</summary><pre>{JSON.stringify(entry.inputs,null,2)}</pre><ul>{entry.assumptions.map(a=><li key={a}>{a}</li>)}</ul></details></article>)}
    {pair.length===2&&<article className="report-comparison"><h2>선택한 두 실험 비교</h2>{reason?<p className="native-warning">{reason}</p>:<><p>차이 = 두 번째 선택 − 첫 번째 선택. 동일한 지표·단위끼리 비교합니다.</p><table><thead><tr><th>지표</th><th>절대 차이</th><th>단위</th></tr></thead><tbody>{pair[0].metrics.map(m=>{const other=pair[1].metrics.find(v=>v.key===m.key&&v.unit===m.unit);return other&&m.value!==null&&other.value!==null?<tr key={m.key}><td>{m.label}</td><td>{(other.value-m.value).toPrecision(5)}</td><td>{m.unit}</td></tr>:null;})}</tbody></table></>}
      <h3>달라진 입력</h3><ul>{[...new Set([...Object.keys(pair[0].inputs),...Object.keys(pair[1].inputs)])].filter(k=>pair[0].inputs[k]!==pair[1].inputs[k]).map(k=><li key={k}>{k}: {String(pair[0].inputs[k])} → {String(pair[1].inputs[k])}</li>)}</ul></article>}
  </section>;
}
