import {useEffect,useState} from 'react';
import {Chart} from './Chart';
import {MathBlock} from './MathBlock';
import {CaptureReport} from './ProjectReport';
import {exportJson} from '../storage';
import {rfEquations} from '../rf';
import type {RFParams,RFPoint,RFField} from '../rf';

interface PlasmaState {density_m3:number;te_ev:number;ion_flux_m2_s:number;loss_w:number;power_relative_residual:number;normalized_slope:number;circuit:RFPoint}
interface PlasmaRun {
  version:string;run_id?:string;config_hash:string;rf_params:RFParams;gas:RFParams;
  terms:{te_ev:number;collision_s:number;particle_relative_residual:number};
  manual:{status:string;selected:PlasmaState|null};matched:{status:string;selected:PlasmaState|null};
  balance_curve:{log10_density:number[];rf_bulk_w:number[];loss_w:number[]};
  sweep:{cp_pf:number;density_m3:number|null;bulk_w:number|null;reflected_pct:number|null}[];
  assumptions:string[];
}
async function sample<T>(name:string):Promise<T> {
  const response=await fetch(`${import.meta.env.BASE_URL}rf/${name}.json`);
  if(!response.ok) throw Error('결합 모델 예제를 읽지 못했습니다.');
  return response.json();
}
const f=(v:number|null|undefined,d=2)=>v==null?'—':v.toFixed(d);

export function CoupledPlasma({params,onParams,setBusy}:{params:RFParams;onParams:(p:RFParams)=>void;setBusy:(b:boolean)=>void}) {
  const [run,setRun]=useState<PlasmaRun|null>(null),[fields,setFields]=useState<RFField[]>([]);
  const [gas,setGas]=useState<RFParams>({}),[online,setOnline]=useState(false),[working,setWorking]=useState(false),[error,setError]=useState('');
  useEffect(()=>{let alive=true;void Promise.all([sample<{fields:RFField[]}>('coupled-schema'),sample<PlasmaRun>('coupled-reference')]).then(([s,r])=>{if(alive){setFields(s.fields);setRun(r);setGas(r.gas);}}).catch(e=>{if(alive)setError(String(e));});
    if(['localhost','127.0.0.1'].includes(location.hostname)) void fetch('/api/rf/coupled/schema').then(r=>{if(alive)setOnline(r.ok);}).catch(()=>{});
    return()=>{alive=false;};
  },[]);
  async function calculate(){setBusy(true);setWorking(true);setError('');try{
    const response=await fetch('/api/rf/coupled',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({rf_params:params,gas})});
    const data=await response.json();if(!response.ok)throw Error(data.error??'계산 실패');setRun(data);
  }catch(e){setError(String(e));}finally{setWorking(false);setBusy(false);}}
  if(!run) return <p>{error||'RF–Ar 결합 모델을 준비합니다…'}</p>;
  const states=[run.manual.selected,run.matched.selected];
  const maxDensity=Math.max(1,...states.map(s=>s?.density_m3??0));
  const pending=JSON.stringify(params)!==JSON.stringify(run.rf_params)||JSON.stringify(gas)!==JSON.stringify(run.gas);
  const selectedDensities=states.filter(s=>s!==null).map(s=>Math.log10(s.density_m3));
  const low=selectedDensities.length?Math.floor(Math.min(...selectedDensities)-.7):12;
  const high=selectedDensities.length?Math.ceil(Math.max(...selectedDensities)+.3):19;
  const indices=run.balance_curve.log10_density.map((_,i)=>i).filter(i=>run.balance_curve.log10_density[i]>=low&&run.balance_curve.log10_density[i]<=high);
  const metrics=states.flatMap((s,i)=>[
    {key:`n-${i}`,label:`${i?'재정합':'수동'} 전자밀도`,unit:'m⁻³',value:s?.density_m3??null},
    {key:`p-${i}`,label:`${i?'재정합':'수동'} 벌크 흡수`,unit:'W',value:s?.circuit.bulk_w??null},
    {key:`r-${i}`,label:`${i?'재정합':'수동'} 반사율`,unit:'%',value:s?.circuit.reflected_pct??null},
    {key:`flux-${i}`,label:`${i?'재정합':'수동'} Ar 이온 플럭스`,unit:'m⁻² s⁻¹',value:s?.ion_flux_m2_s??null},
    {key:`te-${i}`,label:`${i?'재정합':'수동'} 전자온도`,unit:'eV',value:s?.te_ev??null},
    {key:`coil-${i}`,label:`${i?'재정합':'수동'} 코일 손실`,unit:'W',value:s?.circuit.coil_loss_w??null},
    {key:`cp-${i}`,label:`${i?'재정합':'수동'} Cₚ`,unit:'pF',value:s?.circuit.cp_pf??null},
    {key:`cs-${i}`,label:`${i?'재정합':'수동'} Cₛ`,unit:'pF',value:s?.circuit.cs_pf??null},
  ]);
  return <div className="coupled-plasma"><h2>매칭 ↔ 플라즈마 · 정상 수지</h2><p>흡수 전력과 전자밀도를 함께 풉니다. 기존 입력의 전자밀도·충돌 빈도·밀도 배수는 여기서 사용하지 않습니다. 쉬스 두께는 고정 입력입니다.</p>
    {error&&<p role="alert" className="error-banner">{error}</p>}
    <div className="coupled-gas">{fields.map(field=><label key={field.key}>{field.label}<small>{field.unit}</small><input aria-label={field.label} type="number" step="any" min={field.min} max={field.max} disabled={working||!online} value={Number.isFinite(gas[field.key])?gas[field.key]:''} onChange={e=>setGas({...gas,[field.key]:e.target.value===''?NaN:Number(e.target.value)})}/></label>)}</div>
    <div className="report-actions"><button className="button primary" disabled={!online||working} onClick={()=>void calculate()}>{working?'결합 수지 계산 중…':'RF–플라즈마 함께 계산 · 기록'}</button><button disabled={working} onClick={()=>exportJson('rf-ar-coupled.json',run)}>원시 JSON</button><CaptureReport disabled={working} snapshot={{kind:'rf-coupled',label:'RF–Ar 밀도·전력 수지',source_id:run.run_id??run.config_hash,version:run.version,evidence:'simulation',provenance:run.run_id?'local calculation':'recorded example',inputs:{...run.rf_params,...Object.fromEntries(Object.entries(run.gas).map(([k,v])=>['gas.'+k,v]))},metrics,assumptions:run.assumptions,numerics:run.terms}}/></div>
    <p className="rf-caption">{run.run_id?'로컬 결합 계산 · DB 기록':'저장된 결합 계산 예제'} · {(run.run_id??run.config_hash).slice(0,12)}</p>
    {pending&&<p className="native-pending">입력이 바뀌었습니다. 아래는 마지막 결합 계산 결과입니다.</p>}
    {!online&&<p className="native-launch">새 결합 계산은 최신 로컬 RF 서버가 필요합니다. 공개 페이지는 저장된 예제를 표시합니다.</p>}
    <div className="plasma-viewport"><svg viewBox="0 0 880 285" className="plasma-comparison" role="img" aria-label="수동 매칭과 재정합의 평균 플라즈마 상태 비교">
      <rect width="880" height="285" fill="#1b2b36"/>
      {states.map((state,i)=><g key={i} transform={`translate(${i*440},0)`}>
        <text x="220" y="31" fill="#d7e4eb" fontSize="16" textAnchor="middle">{i?'재정합 + 결합 수지':'수동 C + 결합 수지'}</text>
        <rect x="75" y="55" width="290" height="112" rx="5" fill="#304957" stroke="#708b9b"/>
        <rect x="89" y="72" width="262" height="79" rx="18" fill="#82bad0" opacity={state?.density_m3? .15+.65*state.density_m3/maxDensity:0}/>
        <path d="M92 61H348M92 161H348" stroke="#cfdae0" strokeWidth="4"/>
        <text x="220" y="107" fill="#f7fbff" fontSize="20" textAnchor="middle">nₑ = {state?f(state.density_m3/1e16):'—'} × 10¹⁶ m⁻³</text>
        <text x="220" y="135" fill="#f7fbff" fontSize="13" textAnchor="middle">Tₑ = {state?f(state.te_ev):'—'} eV</text>
        <text x="220" y="198" fill="#d7e4eb" fontSize="14" textAnchor="middle">벌크 {f(state?.circuit.bulk_w)} W · 반사 {f(state?.circuit.reflected_pct)} %</text>
        <text x="220" y="223" fill="#d7e4eb" fontSize="13" textAnchor="middle">Γᵢ = {state?f(state.ion_flux_m2_s/1e19):'—'} × 10¹⁹ m⁻²s⁻¹</text>
      </g>)}
      <text x="440" y="269" fill="#9eafba" fontSize="11" textAnchor="middle">밝기: 두 해의 평균 전자밀도 상대 비교 · 공간 분포/발광/점화 영상이 아닙니다.</text>
    </svg></div>
    {states.some(s=>s===null)&&<p className="native-warning">0 전력이거나 지정한 탐색 구간에서 허용할 정상해를 찾지 못했습니다. 실제 점화·소멸 판정으로 해석하지 마세요.</p>}
    {run.matched.selected&&run.matched.selected.circuit.reflected_pct>1&&<p className="native-warning">허용 C 범위에서 찾은 재정합 해도 반사율 1%를 넘습니다. 최적화 결과가 목표 정합을 보장하지는 않습니다.</p>}
    <p>이 모델에서 Tₑ는 가스·기하의 입자 수지로 정해집니다. RF 매칭만 바꾸면 Tₑ가 일정한 것은 모델 가정의 결과입니다. 밀도와 흡수 전력은 서로 연결됩니다.</p>
    <div className="rf-table-scroll"><table><thead><tr><th>조건</th><th>Cₚ / Cₛ pF</th><th>코일 손실 W</th><th>전력 수지 상대 잔차</th></tr></thead><tbody>{states.map((s,i)=><tr key={i}><td>{i?'재정합':'수동 C'}</td><td>{f(s?.circuit.cp_pf,1)} / {f(s?.circuit.cs_pf,1)}</td><td>{f(s?.circuit.coil_loss_w)}</td><td>{s?.power_relative_residual.toExponential(2)??'—'}</td></tr>)}</tbody></table></div>
    <Chart compact series={{key:'balance',title:'수동 C에서의 가열·손실 교점',x_label:'log₁₀(nₑ / m⁻³)',y_label:'W',x:indices.map(i=>run.balance_curve.log10_density[i]),lines:[{name:'회로 벌크 가열',values:indices.map(i=>run.balance_curve.rf_bulk_w[i])},{name:'Ar 전체 손실',values:indices.map(i=>run.balance_curve.loss_w[i])}]}}/>
    {run.sweep.length>0&&<Chart compact series={{key:'cp-density',title:'재정합 Cₛ 고정 · Cₚ 스윕',x_label:'Cₚ / pF',y_label:'10¹⁶ m⁻³',x:run.sweep.map(r=>r.cp_pf),lines:[{name:'수지로 계산한 전자밀도',values:run.sweep.map(r=>r.density_m3===null?NaN:r.density_m3/1e16)}]}}/>}
    <details><summary>결합식·가정·해 선택 규칙</summary><MathBlock label="회로와 Ar 수지 결합" expressions={rfEquations.coupled}/><ul>{run.assumptions.map(a=><li key={a}>{a}</li>)}</ul><p>Ar 이온 플럭스를 SF₆/O₂ 식각 경계조건이나 thermal ALD 성장률에 자동 연결하지 않습니다.</p></details>
    <div className="native-examples"><span>결합 모델 예제</span>{[['coupled-reference','Q = 100'],['coupled-lossy','Q = 15']].map(([name,label])=><button disabled={working} key={name} onClick={()=>{void sample<PlasmaRun>(name).then(r=>{setRun(r);setGas(r.gas);onParams(r.rf_params);}).catch(e=>setError(String(e)));}}>{label}</button>)}</div>
  </div>;
}
