import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import ts from 'typescript';
const source=await readFile(new URL('../src/projectReport.ts',import.meta.url),'utf8');
const compiled=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;
const {appendSnapshot,emptyReport,reportCsv,reportMarkdown,comparisonReason}=await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);
const snapshot=()=>({kind:'native-etch',label:'Sample',source_id:'source-hash',version:'0.2.0',evidence:'simulation',provenance:'local calculation',inputs:{surface_profile:1,pitch_nm:400,corrugation_amplitude_nm:8,corrugation_count:3},metrics:[{key:'rq',label:'Rq',unit:'nm',value:5.6}],assumptions:['Prescribed geometry']});
test('report capture freezes inputs and preserves existing operator notes',()=>{
  const s=snapshot(),r=appendSnapshot(emptyReport(),s,'1','now');
  r.entries[0].note='My observation';s.inputs.pitch_nm=900;s.metrics[0].value=99;
  const next=appendSnapshot(r,snapshot(),'2','later');
  assert.equal(next.entries[0].inputs.pitch_nm,400);assert.equal(next.entries[0].metrics[0].value,5.6);assert.equal(next.entries[0].note,'My observation');
});
test('unavailable metrics remain blank in CSV and spreadsheet formulas are escaped',()=>{
  const s=snapshot();s.label='=1+1';s.metrics[0].value=null;
  const r=appendSnapshot(emptyReport(),s,'1','now');
  assert.match(reportCsv(r),/"'=1\+1"/);assert.match(reportCsv(r),/"Rq","","nm"/);assert.match(reportMarkdown(r),/계산 불가/);
});
test('comparison rejects different physics or geometry while allowing grid refinement',()=>{
  const a=appendSnapshot(emptyReport(),snapshot(),'1','now').entries[0];
  const b=structuredClone(a);b.inputs.grid_nm=4;
  assert.equal(comparisonReason(a,b),null);b.inputs.corrugation_amplitude_nm=10;assert.ok(comparisonReason(a,b));
  b.inputs={...a.inputs};b.kind='rf-coupled';assert.ok(comparisonReason(a,b));
});
test('Markdown retains provenance, operator conclusions, inputs and model boundary',()=>{
  const r=appendSnapshot(emptyReport(),snapshot(),'1','now');r.discussion='Needs grid comparison';
  const md=reportMarkdown(r);assert.match(md,/source-hash/);assert.match(md,/local calculation/);assert.match(md,/corrugation_amplitude_nm/);assert.match(md,/Needs grid comparison/);assert.match(md,/Bosch/);
});
