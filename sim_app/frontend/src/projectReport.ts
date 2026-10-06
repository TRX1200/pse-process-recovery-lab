export interface ReportMetric {key:string; label:string; unit:string; value:number|null}
export interface ReportSnapshot {
  kind:string; label:string; source_id:string; version:string; evidence:'simulation';
  provenance:'local calculation'|'recorded example'; inputs:Record<string,number|string>;
  metrics:ReportMetric[]; assumptions:string[]; numerics?:unknown;
}
export interface ReportEntry extends ReportSnapshot {record_id:string; saved_at:string; note:string}
export interface ProjectReport {
  format:'process-project-report-v1'; title:string; author:string; objective:string;
  hypothesis:string; discussion:string; next_measurement:string; entries:ReportEntry[];
}
export const REPORT_KEY='process-project-report.v1';
export function emptyReport():ProjectReport {
  return {format:'process-project-report-v1',title:'RF 매칭과 공정 형상 비교 실험',author:'',objective:'',hypothesis:'',discussion:'',next_measurement:'',entries:[]};
}
export function appendSnapshot(report:ProjectReport, snapshot:ReportSnapshot, id:string, time:string):ProjectReport {
  if(report.entries.length>=50) throw Error('최대 50개까지 기록합니다. 먼저 보고서를 내려받고 불필요한 항목을 제외하세요.');
  if(snapshot.metrics.some(m=>m.value!==null&&!Number.isFinite(m.value))) throw Error('비유한 지표를 기록할 수 없습니다.');
  const entry=JSON.parse(JSON.stringify({...snapshot,record_id:id,saved_at:time,note:''})) as ReportEntry;
  return {...report,entries:[...report.entries,entry]};
}
export function readReport():ProjectReport {
  const raw=localStorage.getItem(REPORT_KEY);
  if(!raw) return emptyReport();
  const data=JSON.parse(raw) as ProjectReport;
  if(data.format!=='process-project-report-v1'||!Array.isArray(data.entries)) throw Error('저장된 보고서 형식을 읽지 못했습니다. 브라우저 저장소를 덮어쓰지 않습니다.');
  return data;
}
export function captureReport(snapshot:ReportSnapshot):void {
  const report=appendSnapshot(readReport(),snapshot,crypto.randomUUID(),new Date().toISOString());
  localStorage.setItem(REPORT_KEY,JSON.stringify(report));
}
export function comparisonReason(a:ReportEntry,b:ReportEntry):string|null {
  if(a.kind!==b.kind) return '서로 다른 모델의 지표를 직접 비교하지 않습니다.';
  if(a.version!==b.version) return '모델 버전이 다릅니다. 버전 차이부터 확인하세요.';
  if(a.kind.startsWith('native')) {
    const profile=a.inputs.surface_profile??0;
    const keys=profile===1?['pitch_nm','corrugation_amplitude_nm','corrugation_count']:
      profile===2?['pitch_nm','width_nm','depth_nm','corrugation_amplitude_nm','corrugation_count']:
      ['pitch_nm','width_nm',a.kind==='native-ald'?'depth_nm':'mask_nm'];
    if(profile!==(b.inputs.surface_profile??0)||keys.some(k=>a.inputs[k]!==b.inputs[k])) return '초기 형상이 다릅니다. 같은 초기 형상을 고정한 효과 비교가 아닙니다.';
  }
  return null;
}
function csvCell(value:unknown):string {
  let text=value==null?'':String(value);
  if(typeof value==='string'&&/^[=+\-@\t\r]/.test(text)) text="'"+text;
  return '"'+text.replaceAll('"','""')+'"';
}
export function reportCsv(report:ProjectReport):string {
  const rows:unknown[][]=[['record_id','kind','source_id','label','provenance','metric','value','unit','note']];
  for(const e of report.entries) for(const m of e.metrics) rows.push([e.record_id,e.kind,e.source_id,e.label,e.provenance,m.label,m.value,m.unit,e.note]);
  return '\ufeff'+rows.map(r=>r.map(csvCell).join(',')).join('\r\n');
}
function cell(s:unknown):string {return String(s??'—').replaceAll('|','\\|').replaceAll('\n',' ');}
export function reportMarkdown(report:ProjectReport):string {
  const lines=[`# ${report.title}`,'',`작성자: ${report.author||'[직접 작성]'}`,'',
    '**모든 결과는 시뮬레이션이며 실제 장비 측정이 아닙니다.** 코드·수치 검증과 물리 검증을 구분합니다.','',
    '## 연구 질문',report.objective||'[직접 작성]','','## 사전 가설',report.hypothesis||'[직접 작성]','',
    '## 계산 결과와 실행 근거'];
  for(const [i,e] of report.entries.entries()) {
    lines.push('',`### ${i+1}. ${e.label}`,'',`모델: ${e.kind} / ${e.version}`,
      `근거: ${e.provenance}; simulation`, `실행/설정 식별자: \`${e.source_id}\``,
      `기록 시각(UTC): ${e.saved_at}`,'','| 지표 | 값 | 단위 |','|---|---:|---|',
      ...e.metrics.map(m=>`| ${cell(m.label)} | ${m.value===null?'계산 불가':m.value.toPrecision(7)} | ${cell(m.unit)} |`),
      '','입력:','','| 변수 | 값 |','|---|---:|',...Object.entries(e.inputs).map(([k,v])=>`| ${cell(k)} | ${cell(v)} |`),
      '',`내 해석: ${e.note||'[직접 작성]'}`,'','가정과 범위:',...e.assumptions.map(a=>`- ${a}`));
    if(e.numerics) lines.push('','수치 설정 / 환경:','```json',JSON.stringify(e.numerics,null,2),'```');
  }
  lines.push('','## 논의',report.discussion||'[지지/기각된 가설, 대안 원인, 수치 민감도를 직접 작성]',
    '','## 추가로 필요한 실제 측정',report.next_measurement||'[RF V/I, 반사 전력, 플라즈마 진단, 단면 계측 등 필요한 근거를 직접 작성]',
    '','## 공통 한계','RF–Ar 결합은 선형 회로와 0D 정상 수지입니다. 비선형 쉬스·점화는 제외합니다.',
    '표면 요철과 scallop은 초기 조건입니다. 자발적 ripple/Bosch 생성 기구를 검증한 결과가 아닙니다.',
    'Ar 이온 플럭스를 SF6/O2 화학 또는 thermal ALD 성장률로 직접 환산하지 않습니다.',
    '형상 변화에는 격자·입자 표본 오차가 포함됩니다. 원시 JSON 및 단면 SVG를 함께 보관하세요.');
  return lines.join('\n');
}
