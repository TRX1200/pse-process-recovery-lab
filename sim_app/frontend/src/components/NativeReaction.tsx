import type {CSSProperties} from 'react';
import type {NativeFrame,NativeRun} from '../native';
import {topAt} from '../nativeAnalysis';

/** Explanatory glyphs only: never mutate or interpolate the solver's geometry. */
export function NativeReaction({run,frame,x,y,playing}:{run:NativeRun;frame:NativeFrame;x:(v:number)=>number;y:(v:number)=>number;playing:boolean}) {
  const p=run.params,etch=run.model==='etch';
  const species=etch?[
    ...(p.ion_flux>0?[{name:'ion',color:'#88dce8'}]:[]),
    ...(p.fluorine_flux>0?[{name:'F',color:'#a3d5aa'}]:[]),
    ...(p.oxygen_flux>0?[{name:'O',color:'#c5b6ec'}]:[]),
  ]:p.pulse_s>0&&p.pressure_pa>0?[{name:'TMA',color:'#edc67c'}]:[];
  const paths=frame.layers.at(-1)?.paths_nm??[];
  return <g data-process-illustration="true" className={`native-reaction ${playing?'is-playing':''}`}>
    <defs><linearGradient id="native-supply-glow" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor={etch?'#6aaed2':'#dfb869'} stopOpacity=".19"/><stop offset="1" stopColor="#17222d" stopOpacity="0"/></linearGradient></defs>
    {species.length>0&&<rect x="76" y="46" width="838" height="72" fill="url(#native-supply-glow)"/>}
    <text x="90" y="65" fill={etch?'#a9d9ea':'#efd6a4'} fontSize="12">{etch?'플라즈마 유래 입자 공급 · ion / F / O':'TMA 공급 · 흡착 → 포화 → 막 성장'}</text>
    <text x="90" y="83" fill="#becbd4" fontSize="10">{species.length?'입자 수·궤적·발광은 설명용 도식':'현재 조건: 활성 공급 없음'}{etch?' · RF 해석과 자동 결합되지 않음':' · 열 ALD, 플라즈마 사용 안 함'}</text>
    {Array.from({length:21},(_,i)=>{
      if(!species.length)return null;
      const px=p.pitch_nm*(-.46+.92*(i+.5)/21),height=topAt(paths,px);if(height===null)return null;
      const hitX=x(px),hitY=y(height),startY=100;
      if(hitY<startY+15||hitX<78||hitX>912)return null;
      const s=species[i%species.length],dx=etch&&s.name==='ion'?0:12*Math.sin(i*2.4),dy=hitY-startY;
      const style={'--travel-x':`${-dx}px`,'--travel-y':`${dy}px`,animationDelay:`${-i*.29}s`,animationDuration:`${1.7+i%4*.27}s`} as CSSProperties;
      return <g key={i}>
        <g transform={`translate(${hitX+dx} ${startY})`}><g className="native-particle" style={style}>
          {s.name==='ion'?<path d="M0 -8V0m-3 -3 3 3 3 -3" stroke={s.color} strokeWidth="1.7" fill="none"/>:<><circle r={s.name==='TMA'?3.5:2.5} fill={s.color}/>{s.name==='TMA'&&<circle cx="5" cy="-3" r="1.8" fill={s.color}/>}</>}
        </g></g>
        <circle className="native-hit" cx={hitX} cy={hitY} r="4" fill="none" stroke={s.color} strokeWidth="1.1" style={{animationDelay:`${-i*.29}s`}}/>
      </g>;
    })}
  </g>;
}
