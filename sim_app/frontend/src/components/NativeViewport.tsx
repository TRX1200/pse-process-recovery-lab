import { useMemo } from "react";
import { contourPath, extentOf } from "../native";
import type { Contour, NativeFrame, NativeRun } from "../native";
import {NativeReaction} from './NativeReaction';

const COLORS: Record<string, string> = { Si: "#72808e", Mask: "#5388a0", Al2O3: "#e6b965" };

export function NativeViewport({ run, frame, reference, initial, mesh, zoom, target, particles, playing }: {
  run: NativeRun; frame: NativeFrame; reference: NativeRun | null;
  initial: boolean; mesh: boolean; zoom: number; target:Contour[]; particles:boolean; playing:boolean;
}) {
  const bounds = useMemo(() => extentOf([...run.frames, ...(reference?.frames ?? []),{at:0,label:'target',metrics:{},layers:[{material:'target',paths_nm:target}]}], run.params.pitch_nm), [run, reference, target]);
  const [xmin, xmax, ymin, ymax] = bounds;
  const scale = Math.min(820 / (xmax - xmin), 490 / (ymax - ymin)) * zoom;
  const x = (v: number) => 490 + v * scale;
  const y = (v: number) => 300 - (v - (ymin + ymax) / 2) * scale;
  const ticksX = Array.from({ length: 5 }, (_, i) => xmin + (xmax - xmin) * i / 4);
  const ticksY = Array.from({ length: 6 }, (_, i) => ymin + (ymax - ymin) * i / 5);
  const meshPaths = frame.layers.flatMap(layer => layer.paths_nm);
  return <svg className="native-viewport" viewBox="0 0 980 620" role="img" aria-label={`${run.model === "etch" ? "식각" : "ALD"} 계산 단면 ${frame.at.toFixed(3)} ${run.axis_unit}`}>
    <defs><clipPath id="native-plot-clip"><rect x="75" y="45" width="840" height="510" /></clipPath></defs>
    <rect width="980" height="620" fill="#17222d" />
    <text x="28" y="28" fill="#b9c8d5" fontSize="13">FEATURE CROSS SECTION</text>
    <text x="950" y="28" textAnchor="end" fill="#b9c8d5" fontSize="12">x / y 동일 축척 · nm</text>
    <g clipPath="url(#native-plot-clip)">
      {ticksX.map(v => <line key={`gx${v}`} x1={x(v)} x2={x(v)} y1="45" y2="555" stroke="#293847" />)}
      {ticksY.map(v => <line key={`gy${v}`} x1="75" x2="915" y1={y(v)} y2={y(v)} stroke="#293847" />)}
      {[...frame.layers].reverse().map((layer, i) => <g key={`${layer.material}${i}`}>
        <path d={contourPath(layer.paths_nm, x, y, ymin - 10000, true)} fill={COLORS[layer.material] ?? "#888"} fillRule="evenodd" />
        <path d={contourPath(layer.paths_nm, x, y, ymin, false)} fill="none" stroke={layer.material === "Al2O3" ? "#ffe0a0" : "#bdc9d2"} strokeWidth="1.1" />
      </g>)}
      {initial && run.frames[0].layers.map((layer, i) => <path key={i} d={contourPath(layer.paths_nm, x, y, ymin, false)} fill="none" stroke="#ecf4f7" opacity=".6" strokeDasharray="5 5" strokeWidth="1" />)}
      {reference && reference.frames.at(-1)!.layers.map((layer, i) => <path key={i} d={contourPath(layer.paths_nm, x, y, ymin, false)} fill="none" stroke="#75bbed" strokeWidth="1.5" strokeDasharray="6 3" />)}
      <path data-target-contour="true" d={contourPath(target,x,y,ymin,false)} fill="none" stroke="#ff7953" strokeWidth="2.4"/>
      {mesh && meshPaths.flatMap((path, pi) => path.map(([px, py], ni) => <circle key={`${pi}-${ni}`} cx={x(px)} cy={y(py)} r="1.4" fill="#17222d" />))}
      <line x1="75" x2="915" y1={y(0)} y2={y(0)} stroke="#afc2d0" strokeDasharray="3 5" opacity=".5" />
      {particles&&<NativeReaction run={run} frame={frame} x={x} y={y} playing={playing}/>}
    </g>
    {ticksX.map(v => <text key={v} x={x(v)} y="578" textAnchor="middle" fill="#b9c8d5" fontSize="12">{v.toFixed(0)}</text>)}
    {ticksY.filter(v => y(v) >= 45 && y(v) <= 555).map(v => <text key={v} x="65" y={y(v) + 4} textAnchor="end" fill="#b9c8d5" fontSize="12">{v.toFixed(0)}</text>)}
    <text x="490" y="605" textAnchor="middle" fill="#b9c8d5" fontSize="12">x (nm)</text>
    <text x="20" y="300" fill="#b9c8d5" fontSize="12" transform="rotate(-90 20 300)">y (nm), 위쪽 +</text>
  </svg>;
}
