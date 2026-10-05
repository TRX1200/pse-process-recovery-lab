import { useId } from 'react';
import { impedance } from '../rf';
import type { RFPoint, RFRun } from '../rf';

export function RFCircuit({run, point}: {run: RFRun; point: RFPoint}) {
  return <svg className="rf-circuit" viewBox="0 0 850 260" role="img" aria-label="50옴 급전선, 병렬 커패시터, 직렬 코일과 커패시터, 플라즈마 부하 회로">
    <g stroke="#c7d7e1" strokeWidth="2" fill="none">
      <circle cx="62" cy="94" r="26"/><path d="M42 94q10 -23 20 0t20 0M88 94H340M405 94h68M489 94h103M736 94h53v105H62v-79M260 94v45m-18 0h36m-36 10h36m-18 0v50M340 94c0 -26 16 -26 16 0c0 -26 16 -26 16 0c0 -26 16 -26 16 0c0 -26 17 -26 17 0M473 76v36m16 -36v36"/>
      <rect x="592" y="62" width="144" height="65" rx="3"/>
    </g>
    <g fill="#e2eaf0" fontSize="14" textAnchor="middle">
      <text x="66" y="37">{run.params.frequency_mhz} MHz</text><text x="66" y="239">{run.params.forward_w} W · 50 Ω</text>
      <text x="171" y="66">급전선 {run.params.cable_m} m</text>
      <text x="260" y="229">Cₚ {point.cp_pf.toFixed(1)} pF</text>
      <text x="371" y="51">L {run.params.coil_uh} µH</text><text x="485" y="51">Cₛ {point.cs_pf.toFixed(1)} pF</text>
      <text x="664" y="88">PLASMA</text><text x="664" y="109" fontSize="12">Rᵦ + jωLᵦ + 1/jωCsh</text>
      <text x="662" y="164" fill="#e4bc79">{impedance(point.z_load)}</text>
      <text x="476" y="237" fill="#a4b8c5" fontSize="12">입력 Z = {impedance(point.z_generator)}</text>
    </g>
  </svg>;
}

export function SmithChart({run}: {run: RFRun}) {
  const id = useId().replaceAll(':','');
  const x = (v: number) => 220+160*v, y = (v: number) => 200-160*v;
  const curve = (points: number[][]) => points.map(([r,i],k)=>`${k?'L':'M'}${x(r)},${y(i)}`).join(' ');
  const grids = [.2,.5,1,2,5];
  return <section className="rf-plot"><h3>Smith chart <small>발생기 기준면 · Z₀ = 50 Ω</small></h3>
    <svg viewBox="0 0 440 414" role="img" aria-label="Smith chart의 수동 및 자동 정합 주파수 궤적">
      <defs><clipPath id={id}><circle cx="220" cy="200" r="160"/></clipPath></defs>
      <circle cx="220" cy="200" r="160" fill="#f8faf9" stroke="#899dA8"/><path d="M60 200H380" stroke="#bac5ca"/>
      <g clipPath={`url(#${id})`} fill="none" stroke="#d3dcdf" strokeWidth=".8">
        {grids.map(r=><circle key={r} cx={x(r/(1+r))} cy="200" r={160/(1+r)}/>)}
        {grids.flatMap(v=>[v,-v]).map(v=><path key={v} d={curve(Array.from({length:160},(_,i)=>{const r=(i/159)**2*70; const d=(r+1)**2+v*v; return [(r*r+v*v-1)/d,2*v/d];}))}/>)}
      </g>
      <path d={curve(run.frequency.manual.map(p=>p.gamma))} fill="none" stroke="#344b5b" strokeWidth="2"/>
      <path d={curve(run.frequency.matched.map(p=>p.gamma))} fill="none" stroke="#ae492f" strokeWidth="2"/>
      {[run.manual,run.matched].map((p,i)=><circle key={i} cx={x(p.gamma[0])} cy={y(p.gamma[1])} r="5" fill={i?'#ae492f':'#344b5b'} stroke="white"><title>{i?'자동':'수동'}: {impedance(p.z_generator)}</title></circle>)}
      <g fill="#647987" fontSize="12" textAnchor="middle"><text x="220" y="24">+jX · 유도성</text><text x="220" y="384">−jX · 용량성</text><text x="224" y="216">50 Ω</text><text x="220" y="407">청색: 수동 · 주황: 자동 정합 · 점: 설정 주파수</text></g>
    </svg>
  </section>;
}

export function MatchMap({run, onSelect}: {run:RFRun; onSelect?: (cp:number, cs:number)=>void}) {
  const map=run.heatmap, n=map.cp_pf.length, step=300/n;
  const coord=(v:number)=> (Math.log(v/10)/Math.log(300)*(n-1)+.5)*step;
  return <section className="rf-plot"><h3>매칭 영역 <small>색: 반사 전력 비율 · C 범위 10–3000 pF</small></h3>
    <svg viewBox="0 0 440 414" role="img" aria-label="Cp와 Cs에 따른 반사 전력 지도">
      {map.reflected_pct.flatMap((row,j)=>row.map((v,i)=><rect key={`${i}-${j}`} x={75+i*step} y={345-(j+1)*step} width={step+.15} height={step+.15} fill={`hsl(15 46% ${96-.6*v}%)`} onClick={()=>onSelect?.(map.cp_pf[i],map.cs_pf[j])} style={{cursor:onSelect?'pointer':'default'}}><title>{`Cp ${map.cp_pf[i].toFixed(1)} / Cs ${map.cs_pf[j].toFixed(1)} pF · 반사 ${v.toFixed(2)}%`}</title></rect>))}
      {[run.manual,run.matched].map((p,i)=><circle key={i} cx={75+coord(p.cp_pf)} cy={345-coord(p.cs_pf)} r="5" fill={i?'#fff':'#213e50'} stroke={i?'#213e50':'#fff'} strokeWidth="2"/>)}
      <g fontSize="12" fill="#647987" textAnchor="middle">{[10,100,1000,3000].map(v=><g key={v}><text x={75+coord(v)} y="365">{v}</text><text x="55" y={349-coord(v)}>{v}</text></g>)}<text x="225" y="390">병렬 Cₚ / pF · 로그 축</text><text x="15" y="200" transform="rotate(-90 15 200)">직렬 Cₛ / pF · 로그 축</text></g>
    </svg><p>밝음 0% → 어두움 100%. 흰 점: 자동 정합. {onSelect?'맵을 눌러 C를 선택한 뒤 계산하세요.':''}</p>
  </section>;
}
