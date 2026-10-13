import {useMemo} from 'react';
import type {FlowFrame,FlowRun} from '../flow';

interface Props {run:FlowRun;frame:FlowFrame;signal?:Float32Array;axis:'horizontal'|'vertical';probe:number;showProbe:boolean;onProbe:(value:number)=>void;fit:boolean}
export function FlowViewport({run,frame,signal,axis,probe,showProbe,onProbe,fit}:Props){
  const d=run.request.domain,[ny,nx]=run.shape,W=800,H=490;
  const top=fit?Math.min(d.top_nm,Math.max(45,frame.metrics.top_height_nm+24)):d.top_nm;
  const scale=Math.min((W-96)/d.width_nm,(H-76)/(top-d.bottom_nm));
  const left=(W-d.width_nm*scale)/2,bottom=H-48;
  const px=(x:number)=>left+(x+d.width_nm/2)*scale,pz=(z:number)=>bottom-(z-d.bottom_nm)*scale;
  const material=new Map(run.materials.map(m=>[m.id,m]));
  const image=useMemo(()=>{
    if(!signal)return null;
    const canvas=document.createElement('canvas');canvas.width=nx;canvas.height=ny;
    const context=canvas.getContext('2d');if(!context)return null;
    const data=context.createImageData(nx,ny);
    for(let r=0;r<ny;r++)for(let c=0;c<nx;c++){
      const offset=((ny-1-r)*nx+c)*4,v=Math.round(255*signal[r*nx+c]);data.data.set([v,v,v,255],offset);
    }context.putImageData(data,0,0);return canvas.toDataURL();
  },[signal,nx,ny]);
  const ticksX=Array.from({length:5},(_,i)=>-d.width_nm/2+i*d.width_nm/4);
  const ticksZ=Array.from({length:5},(_,i)=>d.bottom_nm+i*(top-d.bottom_nm)/4);
  return <svg className="flow-viewport" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${frame.name} · ${signal?'가상 SEM':'재료 단면'} · ${run.request.domain.grid_nm} nm 격자`} onClick={event=>{
    if(!showProbe)return;const svg=event.currentTarget;const point=svg.createSVGPoint();point.x=event.clientX;point.y=event.clientY;
    const transform=svg.getScreenCTM();if(!transform)return;const p=point.matrixTransform(transform.inverse());
    const value=axis==='horizontal'?d.bottom_nm+(bottom-p.y)/scale:-d.width_nm/2+(p.x-left)/scale;
    onProbe(Math.max(axis==='horizontal'?d.bottom_nm:-d.width_nm/2,Math.min(axis==='horizontal'?top-d.grid_nm:d.width_nm/2-d.grid_nm,value)));
  }}>
    <defs><clipPath id="flow-domain-clip"><rect x={left} y={pz(top)} width={d.width_nm*scale} height={(top-d.bottom_nm)*scale}/></clipPath></defs>
    <rect width={W} height={H} fill="#102535"/>
    <g clipPath="url(#flow-domain-clip)">
      {ticksX.map(x=><line key={x} x1={px(x)} x2={px(x)} y1={pz(top)} y2={bottom} stroke="#2a4252" strokeDasharray="3 5"/>)}
      {ticksZ.map(z=><line key={z} x1={left} x2={px(d.width_nm/2)} y1={pz(z)} y2={pz(z)} stroke="#2a4252" strokeDasharray="3 5"/>)}
      {image?<image href={image} x={left} y={pz(d.top_nm)} width={nx*d.grid_nm*scale} height={ny*d.grid_nm*scale} style={{imageRendering:'pixelated'}}/>:<g shapeRendering="crispEdges">{frame.spans.map(([row,col,count,id],i)=><rect key={i} x={px(-d.width_nm/2+col*d.grid_nm)} y={pz(d.bottom_nm+(row+1)*d.grid_nm)} width={count*d.grid_nm*scale+.02} height={d.grid_nm*scale+.02} fill={material.get(id)?.color}/>)}</g>}
      {frame.mask_columns.map(col=><rect key={col} x={px(-d.width_nm/2+col*d.grid_nm)} y={pz(frame.metrics.top_height_nm+10)} width={d.grid_nm*scale} height={5*scale} fill="#E6B2B0"/>)}
      {showProbe&&(axis==='horizontal'?<line x1={left} x2={px(d.width_nm/2)} y1={pz(probe)} y2={pz(probe)} stroke="#f39b67" strokeWidth="1.6" strokeDasharray="7 4"/>:<line x1={px(probe)} x2={px(probe)} y1={pz(top)} y2={bottom} stroke="#f39b67" strokeWidth="1.6" strokeDasharray="7 4"/>)}
    </g>
    <path d={`M${left},${pz(top)}V${bottom}H${px(d.width_nm/2)}`} stroke="#A6BECD" fill="none"/>
    {ticksX.map(x=><text key={x} x={px(x)} y={bottom+19} fill="#A6BECD" fontSize="11" textAnchor="middle">{x.toFixed(0)}</text>)}
    {ticksZ.map(z=><text key={z} x={left-10} y={pz(z)+4} fill="#A6BECD" fontSize="11" textAnchor="end">{z.toFixed(0)}</text>)}
    <text x={left} y={pz(top)-12} fill="#D3E0E8" fontSize="11">z (nm)</text><text x={px(d.width_nm/2)} y={bottom+37} fill="#D3E0E8" fontSize="11" textAnchor="end">x (nm)</text>
    <text x={px(d.width_nm/2)-8} y={pz(top)+20} fill="#A6BECD" fontSize="10" textAnchor="end">{signal?'ILLUSTRATIVE SEM / 비실측':'2D MATERIAL GEOMETRY'}</text>
  </svg>;
}
