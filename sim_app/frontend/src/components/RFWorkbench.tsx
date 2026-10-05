import {useEffect, useState} from 'react';
import {Chart} from './Chart';
import {MathBlock} from './MathBlock';
import {RFCircuit, SmithChart, MatchMap} from './RFPlots';
import {exportJson} from '../storage';
import {impedance, rfEquations} from '../rf';
import type {RFRun, RFSchema, RFParams, RFPoint} from '../rf';
import '../rf.css';

const GROUPS: Record<string,string> = {source:'발생기',match:'매칭 네트워크',plasma:'플라즈마 부하',loss:'부품 손실',line:'급전선',experiment:'부하 변화 실험',limits:'비교 한계'};
const local = ['localhost','127.0.0.1'].includes(location.hostname);
async function api<T>(path:string, body?:unknown):Promise<T> {
  const r=await fetch('/api/rf/'+path, body===undefined?undefined:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const data=await r.json(); if(!r.ok) throw Error(data.error??`HTTP ${r.status}`); return data;
}
async function example<T>(name:string):Promise<T> {const r=await fetch(`${import.meta.env.BASE_URL}rf/${name}.json`); if(!r.ok) throw Error('RF 예제 파일을 읽지 못했습니다.'); return r.json();}
const number=(v:number|null|undefined,d=2)=>v==null?'—':v.toFixed(d);

export function RFWorkbench({setBusy}:{setBusy:(b:boolean)=>void}) {
  const [schema,setSchema]=useState<RFSchema|null>(null), [run,setRun]=useState<RFRun|null>(null);
  const [params,setParams]=useState<RFParams>({}), [available,setAvailable]=useState(false);
  const [working,setWorking]=useState(false), [error,setError]=useState(''), [notice,setNotice]=useState('');
  const [panel,setPanel]=useState<'circuit'|'learn'|'data'>('circuit'), [selected,setSelected]=useState<'manual'|'matched'>('manual');
  useEffect(()=>{let alive=true;
    void Promise.all([example<RFSchema>('schema'),example<RFRun>('reference')]).then(([s,r])=>{if(alive){setSchema(s);setRun(r);setParams(r.params);}}).catch(e=>{if(alive)setError(String(e));});
    if(local) void api('schema').then(()=>{if(alive)setAvailable(true);}).catch(()=>{});
    return ()=>{alive=false;};
  },[]);
  async function calculate(next=params) {setWorking(true);setBusy(true);setError('');setNotice('');try {const r=await api<RFRun>('simulate',{params:next});setRun(r);setParams(r.params);setSelected('manual');}catch(e){setError(String(e));}finally{setWorking(false);setBusy(false);}}
  async function load(name:string) {setWorking(true);setError('');try{const r=await example<RFRun>(name);setRun(r);setParams(r.params);setSelected('manual');}catch(e){setError(String(e));}finally{setWorking(false);}}
  if(!schema||!run) return <div className="native-loading">{error||'RF 작업 공간을 준비합니다…'}</div>;
  const point=run[selected], pending=JSON.stringify(params)!==JSON.stringify(run.params);
  const groups=[...new Set(schema.fields.map(f=>f.group))];
  const line=(key:'s11_db'|'bulk_w',title:string,unit:string)=>({key,title,x_label:'MHz',y_label:unit,x:run.frequency.mhz,lines:[{name:'수동 설정',values:run.frequency.manual.map(p=>key==='s11_db'?Math.max(-60,p[key]):p[key])},{name:'자동 정합',values:run.frequency.matched.map(p=>key==='s11_db'?Math.max(-60,p[key]):p[key])}]});
  const cells:[string,keyof RFPoint,string][]=[['반사 전력','reflected_pct','%'],['벌크 흡수 전력','bulk_w','W'],['코일 손실','coil_loss_w','W'],['Cₛ 전압','series_cap_rms_v','V RMS']];
  return <section className="rf-workbench">
    <header className="rf-heading"><div><span>RF ENGINEERING / PLASMA LOAD</span><h1>매칭 네트워크 실험실</h1><p>회로를 조정하고, 반사·흡수·손실을 함께 읽습니다.</p></div><div className="rf-status">{available?'Python 회로 엔진 연결됨':'공개 계산 예제'}<small>선형 정상상태 · 처방된 CCP 등가 부하</small></div></header>
    {!available&&<p className="native-launch">새 조건은 로컬 Python에서 계산합니다. 공개 화면에서는 저장된 예제와 학습 자료를 볼 수 있습니다.</p>}
    {error&&<p role="alert" className="error-banner">{error}</p>}{notice&&<p role="status" className="native-pending">{notice}</p>}
    <div className="rf-layout"><form className="native-controls" onSubmit={e=>{e.preventDefault();void calculate();}}>
      <div className="native-control-heading"><h2>회로 / 부하 설정</h2></div>
      <div className="native-run-actions"><button className="button primary" disabled={!available||working}>{working?'회로 계산 중…':'회로 계산 · 기록'}</button><button type="button" className="button secondary" disabled={!available||working||pending} onClick={()=>void calculate({...params,cp_pf:run.matched.cp_pf,cs_pf:run.matched.cs_pf})}>자동 정합값 적용 · 계산</button></div>
      {groups.map(g=><details key={g} open={g==='source'||g==='match'}><summary>{GROUPS[g]}</summary>{schema.fields.filter(f=>f.group===g).map(f=><label className="native-field" key={f.key}><span>{f.label}<small>{f.unit}</small></span><input aria-label={f.label} type="number" step="any" min={f.min} max={f.max} required disabled={!available||working} value={Number.isFinite(params[f.key])?params[f.key]:''} onChange={e=>setParams({...params,[f.key]:e.target.value===''?NaN:Number(e.target.value)})}/><small>{f.note}</small></label>)}</details>)}
    </form><div className="rf-main"><nav className="native-tabs" aria-label="RF 작업 메뉴"><button onClick={()=>setPanel('circuit')} aria-pressed={panel==='circuit'}>회로 · 매칭</button><button onClick={()=>setPanel('learn')} aria-pressed={panel==='learn'}>플라즈마 학습</button><button onClick={()=>setPanel('data')} aria-pressed={panel==='data'}>Superset 분석</button></nav>
      <div className="rf-run-label"><span>{run.run_id?'로컬 계산 · DB 기록 완료':'저장된 Python 계산 예제'}</span><code>{(run.run_id??run.config_hash).slice(0,12)}</code><button onClick={()=>exportJson(`rf-${run.config_hash.slice(0,10)}.json`,run)}>결과 JSON 저장</button></div>
      {pending&&<p className="native-pending">입력이 바뀌었습니다. 아래 결과는 이전 조건입니다. ‘회로 계산 · 기록’을 눌러 반영하세요.</p>}
      {panel==='circuit'&&<>
        <div className="rf-mode"><button aria-pressed={selected==='manual'} onClick={()=>setSelected('manual')}>수동 설정 보기</button><button aria-pressed={selected==='matched'} onClick={()=>setSelected('matched')}>자동 정합점 보기</button><span>e⁺ʲωᵗ · 전압/전류 RMS</span></div>
        <div className="rf-circuit-viewport"><RFCircuit run={run} point={point}/></div>
        <div className="native-metrics">{cells.map(([label,key,unit])=><div key={key}><span>{label}</span><strong>{number(point[key] as number)} <small>{unit}</small></strong></div>)}</div>
        <div className="rf-power"><span style={{flex:point.reflected_w,background:'#b66550'}} title={`반사 ${number(point.reflected_w)} W`}/><span style={{flex:point.bulk_w,background:'#466c78'}} title={`벌크 ${number(point.bulk_w)} W`}/><span style={{flex:point.coil_loss_w,background:'#b89a5d'}} title={`코일 손실 ${number(point.coil_loss_w)} W`}/><span style={{flex:point.capacitor_loss_w,background:'#849395'}} title={`C 손실 ${number(point.capacitor_loss_w)} W`}/></div>
        <p className="rf-caption">전력 분배: 반사 {number(point.reflected_w)} + 벌크 {number(point.bulk_w)} + 코일 {number(point.coil_loss_w)} + C {number(point.capacitor_loss_w)} = {run.params.forward_w} W · 수지 잔차 {point.power_residual_w.toExponential(1)} W</p>
        <p className="rf-caption">코일 전류 {number(point.coil_current_rms_a)} A RMS · 쉬스 등가 전압 {number(point.sheath_rms_v)} V RMS · 진행파 대비 벌크 전달 효율 {number(point.bulk_efficiency_pct)} %</p>
        {run.warnings.map(w=><p className="native-warning" key={w}>{w}</p>)}
        <div className="rf-two"><SmithChart run={run}/><MatchMap run={run} onSelect={available&&!working?(cp,cs)=>setParams({...params,cp_pf:cp,cs_pf:cs}):undefined}/></div>
        <div className="rf-two"><Chart series={line('s11_db','주파수 응답 · S₁₁','dB')} compact/><Chart series={line('bulk_w','플라즈마 벌크 흡수 전력','W')} compact/></div>
        <p className="rf-caption">S₁₁ 그래프의 표시 하한은 −60 dB입니다. JSON에는 원래 계산값을 보존합니다.</p>
        <section className="rf-experiment"><h2>전자밀도 변화 → 고정 매칭 → 재정합</h2><p>밀도만 {run.params.density_ratio}배로 바꿉니다. 자동 정합으로 손실·전압까지 이전 값으로 복구되는지 확인하세요.</p><div className="rf-table-scroll"><table><thead><tr><th>조건</th><th>반사 %</th><th>벌크 W</th><th>코일 손실 W</th><th>Cₛ RMS V</th><th>Cₚ / Cₛ pF</th></tr></thead><tbody>{run.comparison.map(p=><tr key={p.case_name}><td>{p.case_name}</td><td>{number(p.reflected_pct)}</td><td>{number(p.bulk_w)}</td><td>{number(p.coil_loss_w)}</td><td>{number(p.series_cap_rms_v)}</td><td>{number(p.cp_pf,1)} / {number(p.cs_pf,1)}</td></tr>)}</tbody></table></div></section>
        <div className="native-examples"><span>계산 예제 비교</span><button disabled={working} onClick={()=>void load('reference')}>기본 Q = 100</button><button disabled={working} onClick={()=>void load('lossy')}>코일 손실 증가 Q = 15</button></div>
        <details className="rf-wave"><summary>RF 두 주기의 전압·전류 보기</summary><p>수동 설정의 정상상태 페이저를 사인파로 재구성했습니다. 점화·펄스 과도응답을 적분한 결과가 아닙니다.</p><div className="rf-two"><Chart series={{key:'rf-v',title:'플라즈마 부하 전압',x_label:'ns',y_label:'V',x:run.waveform.time_ns,lines:[{name:'v(t)',values:run.waveform.voltage_v}]}} compact/><Chart series={{key:'rf-i',title:'플라즈마 부하 전류',x_label:'ns',y_label:'A',x:run.waveform.time_ns,lines:[{name:'i(t)',values:run.waveform.current_a}]}} compact/></div></details>
      </>}
      {panel==='learn'&&<div className="rf-learn"><h2>RF 전공에서 공정 장비로 연결하기</h2><p>먼저 50 Ω 회로를 이해하고, 부하가 시간에 따라 변하는 플라즈마라는 점을 추가합니다. 이 탭의 선형 모델은 그 연결을 공부하는 출발점입니다.</p>
        <article><h3>01 · 반사계수와 기준면</h3><MathBlock expressions={rfEquations.wave} label="반사계수와 전력"/><p>현재 발생기에서 본 입력은 {impedance(point.z_generator)}입니다. S₁₁은 복소 진폭비이고 반사 전력비는 그 절댓값의 제곱입니다. 좋은 정합은 입력의 실수부가 50 Ω, 허수부가 0에 가까워지는 상태입니다.</p></article>
        <article><h3>02 · 플라즈마가 R, L, C로 보이는 이유</h3><MathBlock expressions={rfEquations.plasma} label="플라즈마 등가회로"/><p>전자 충돌은 저항, 전자의 관성은 인덕턴스, 전극 가까이의 전하 분리층인 쉬스는 커패시턴스로 근사합니다. 현재 Rᵦ={number(point.bulk_r_ohm)} Ω, Lᵦ={number(point.bulk_l_nh)} nH, Csh={number(point.sheath_c_pf)} pF입니다.</p><p>여기서는 밀도와 쉬스 두께를 입력합니다. 실제 방전에서는 전력·밀도·쉬스가 서로 영향을 주므로, 점화나 안정성을 연구하려면 입자·에너지 수지와 비선형 쉬스를 함께 풀어야 합니다.</p></article>
        <article><h3>03 · 낮은 반사율만으로 충분할까?</h3><MathBlock expressions={rfEquations.balance} label="전력 보존"/><p>코일 Q가 낮으면 매칭기 자체에서 열로 소모되는 전력이 증가합니다. Q = 15 예제를 열어 반사율과 벌크 흡수 전력을 함께 비교하세요. C 전압·코일 전류도 확인해야 하며, 입력한 비교 한계는 실제 부품 정격 인증이 아닙니다.</p></article>
        <article><h3>04 · 급전선은 Smith chart를 어떻게 바꿀까?</h3><MathBlock expressions={rfEquations.line} label="무손실 급전선"/><p>이 모델은 50 Ω 무손실 급전선입니다. 길이를 바꾸면 발생기에서 본 위상은 회전하지만 |Γ|와 벌크 흡수 전력은 같아야 합니다. 이 한계 사례를 직접 확인할 수 있습니다.</p></article>
        <article><h3>05 · CCP, ICP와 공정 해석의 경계</h3><p>CCP는 전극 사이의 전기장과 쉬스, ICP는 코일과 유도 전기장을 통한 결합을 중심으로 설명합니다. 현재 부하는 CCP를 참고한 선형 등가회로입니다. ICP 변압기 결합, DC self-bias, 이온 에너지 분포, 전자온도, 점화와 고조파는 계산하지 않습니다.</p><p>벌크 흡수 전력이 늘었다고 식각률이 반드시 같은 비율로 증가하는 것은 아닙니다. 가스 반응, 표면 피복, 바이어스와 수송 조건이 필요하므로 ViennaPS의 입사 플럭스에 자동으로 연결하지 않았습니다.</p></article>
        <article><h3>실습 순서 · 5회</h3><ol><li>Cₚ와 Cₛ를 한 번에 하나씩 바꾸고 Smith chart 이동 방향을 기록.</li><li>자동 정합점의 반사율·손실·전압을 수동 설정과 비교.</li><li>밀도 변화 후 고정 매칭과 재정합 결과로 원인 가설 작성.</li><li>Q와 급전선 길이를 각각 바꿔 손실과 기준면 효과를 분리.</li><li>Superset에서 여러 실행을 비교하고 내 결론을 작성.</li></ol></article>
        <h3>참고 자료 / 모델 가정</h3><ul>{run.sources.map(s=><li key={s.url}><a href={s.url} target="_blank" rel="noreferrer">{s.title} ↗</a></li>)}</ul><details><summary>전체 계산 가정</summary><ul>{run.assumptions.map(a=><li key={a}>{a}</li>)}</ul></details>
      </div>}
      {panel==='data'&&<div className="rf-learn"><h2>Apache Superset · 실험 결과 분석</h2><p>회로 계산 때마다 입력·버전·원시 결과와 네 가지 조건의 지표를 로컬 분석 DB에 저장합니다. 모든 행의 근거는 simulation이며, 실제 장비 로그가 아닙니다.</p>
        {available?<div className="rf-data-actions"><a className="button primary" href="http://127.0.0.1:8088/superset/dashboard/rf-process-lab/" target="_blank" rel="noreferrer">Superset 대시보드 열기 ↗</a><button className="button secondary" disabled={working} onClick={()=>{void api('sync-process',{}).then(()=>setNotice('ALD/Etch 완료 결과를 분석 DB에 동기화했습니다. Superset 차트를 새로고침하세요.')).catch(e=>setError(String(e)));}}>ALD / Etch 결과 동기화</button></div>:<p>Superset은 별도 로컬 서비스입니다. 저장소의 RF 학습 안내에서 설치·실행 방법을 확인하세요.</p>}
        <h3>처음 살펴볼 질문</h3><ol><li>재정합 후 반사 전력은 감소했는데 코일 손실과 C 전압은 어떻게 변했는가?</li><li>코일 Q를 낮춘 실행은 같은 반사율에서도 벌크 전력이 달라지는가?</li><li>ALD의 노출 시간과 바닥/상단 막 두께비는 어떤 관계인가?</li></ol>
        <h3>SQL Lab에서 실행할 조회</h3><pre>{'SELECT case_name, reflected_pct, bulk_w,\n       coil_loss_w, series_cap_rms_v\nFROM rf_latest_cases\nORDER BY case_name;'}</pre><p>rf_cases는 모든 RF 실행, rf_latest_cases는 가장 최근 실행, process_results는 동기화한 ALD/Etch 결과입니다. 관리자 로그인 정보는 로컬 credentials 파일에만 저장됩니다.</p>
        <a href="https://github.com/TRX1200/pse-process-recovery-lab/blob/main/docs/RF_MATCHING_KR.md" target="_blank" rel="noreferrer">학습·설치·검증 설명서 ↗</a>
      </div>}
    </div></div>
  </section>;
}
