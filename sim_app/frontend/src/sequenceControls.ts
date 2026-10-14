import type {NativeParameter} from './native';
import type {Params} from './types';

// Display grouping and adjustment increments only; solver values stay in schema units.
export const QUICK_KEYS=['cycles','pulse_s','pressure_pa','temperature_c',
  'width_nm','duration_s','energy_ev','ion_exponent'] as const;
export const CONTROL_GROUPS={quick:'빠른 조절',geometry:'구조',etch:'식각',ald:'ALD',numerics:'수치'};
export type ControlGroup=keyof typeof CONTROL_GROUPS;
export const SHORT_LABELS:Record<string,string>={
  cycles:'증착 사이클',pulse_s:'TMA 노출',pressure_pa:'TMA 분압',temperature_c:'온도',
  width_nm:'개구 폭',duration_s:'식각 시간',energy_ev:'이온 에너지',ion_exponent:'입사 방향성',
  energy_sigma_ev:'에너지 편차',fluorine_flux:'F 플럭스',oxygen_flux:'O 플럭스',ion_flux:'이온 플럭스',
  evaporation_flux:'탈착 플럭스',site_density_nm2:'반응 자리 밀도',gpc_nm:'포화 성장량',
  sticking:'부착 확률',rays_per_point:'표면점당 입자',coverage_dt_s:'피복 시간 간격',
  bundle_cycles:'성장 최대 묶음',output_steps:'식각 저장 구간',pitch_nm:'계산 영역 폭',
};
const STEPS:Record<string,number>={cycles:10,pulse_s:.005,pressure_pa:.5,temperature_c:10,
  width_nm:10,duration_s:1,energy_ev:10,ion_exponent:25,grid_nm:.5,seed:1,
  rays_per_point:100,sticking:.0005,gpc_nm:.005,coverage_dt_s:.0001,
  evaporation_flux:.5,site_density_nm2:.5};
export function adjustmentStep(field:NativeParameter):number {
  return STEPS[field.key]??1;
}
export function adjustedValue(field:NativeParameter,value:number,direction:1|-1):number {
  const base=Number.isFinite(value)?value:field.default;
  const changed=Number((base+direction*adjustmentStep(field)).toPrecision(12));
  return Math.min(field.max,Math.max(field.min,field.integer?Math.round(changed):changed));
}
export function controlFields(fields:NativeParameter[],group:ControlGroup):NativeParameter[] {
  return group==='quick'?QUICK_KEYS.flatMap(key=>fields.filter(f=>f.key===key)):
    fields.filter(f=>f.group===group);
}
export function changedFields(fields:NativeParameter[],params:Params,baseline:Params):number {
  return fields.filter(f=>params[f.key]!==baseline[f.key]).length;
}
