export type RFParams = Record<string, number>;
export interface RFField {key: string; label: string; unit: string; default: number; min: number; max: number; group: string; note: string}
export interface RFSchema {version: string; fields: RFField[]; sources: {title: string; url: string}[]}
export interface RFPoint {
  frequency_mhz: number; cp_pf: number; cs_pf: number; z_load: number[]; z_match: number[]; z_generator: number[];
  gamma: number[]; gamma_match: number[]; s11_db: number; reflected_pct: number; reflected_w: number;
  forward_w: number; accepted_w: number; bulk_w: number; coil_loss_w: number; capacitor_loss_w: number;
  bulk_efficiency_pct: number | null; coil_current_rms_a: number; series_cap_rms_v: number;
  sheath_rms_v: number; power_residual_w: number; bulk_r_ohm: number; bulk_l_nh: number; sheath_c_pf: number;
  case_name?: string; match_within_1pct?: boolean;
}
export interface RFRun {
  version: string; params: RFParams; config_hash: string; run_id?: string; created_at?: string;
  manual: RFPoint; matched: RFPoint; comparison: RFPoint[];
  frequency: {mhz: number[]; manual: RFPoint[]; matched: RFPoint[]};
  heatmap: {cp_pf: number[]; cs_pf: number[]; reflected_pct: number[][]};
  waveform: {time_ns: number[]; voltage_v: number[]; current_a: number[]};
  warnings: string[]; assumptions: string[]; sources: {title: string; url: string}[];
}
export function impedance(z: number[]): string {return `${z[0].toFixed(2)} ${z[1] < 0 ? '−' : '+'} j${Math.abs(z[1]).toFixed(2)} Ω`;}
export const rfEquations = {
  wave: [String.raw`\Gamma=\frac{Z_{in}-Z_0}{Z_{in}+Z_0},\quad P_{ref}=|\Gamma|^2P_{fwd}`],
  plasma: [String.raw`L_b=\frac{m_e\ell_b}{n_e e^2 A},\quad R_b=\nu L_b`, String.raw`C_{sh}=\frac{\varepsilon_0 A}{s_1+s_2},\quad Z_p=R_b+j\omega L_b+\frac{1}{j\omega C_{sh}}`],
  balance: [String.raw`P_{fwd}=P_{ref}+P_{bulk}+P_L+P_C`, String.raw`P_{bulk}=|I_{bulk,rms}|^2R_b`],
  line: [String.raw`\Gamma_{gen}=\Gamma_{match}\exp(-j2\beta\ell),\quad\beta=\frac{2\pi f}{v_p}`],
};
