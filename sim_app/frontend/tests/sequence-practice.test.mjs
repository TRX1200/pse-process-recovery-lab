import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import ts from 'typescript';

const source=await readFile(new URL('../src/sequencePractice.ts',import.meta.url),'utf8');
const compiled=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;
const {INITIAL_TARGETS,targetProblem,summarizeRun,assess,appendAttempt,parsePracticeStore,emptyPracticeStore,recordCsv}=await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);
// Artificial metric values exercise the rubric. They are not solver output or a recipe solution.
const fixture=()=>({hash:'synthetic-qa',label:'QA',created:'2026-10-17T00:00:00Z',source:'local',
  params:{seed:42,grid_nm:2,cycles:1},etch:{center_depth_nm:200,width_half_depth_nm:80,mask_loss_nm:10},
  ald:{top_film_nm:12,bottom_film_nm:11.4,bottom_top_pct:95,mid_gap_nm:60},elapsed:1,
  implementation:'test fixture',warnings:[],handoff:true});
const notebook=()=>({...emptyPracticeStore(),activeId:'task-1',sessions:[{id:'task-1',title:'QA',scope:'both',targets:{...INITIAL_TARGETS},started:'2026-10-17T00:00:00Z',attempts:[]}]});

test('objectives reject nonfinite values, impossible tolerances and invalid percentage ranges',()=>{
  assert.equal(targetProblem(INITIAL_TARGETS),null);
  for(const patch of [{depth:NaN},{film:Infinity},{gap:-1},{film:0},{conformity:101},{depthTolerance:200},{filmTolerance:12}])
    assert.ok(targetProblem({...INITIAL_TARGETS,...patch}));
  assert.equal(targetProblem({...INITIAL_TARGETS,depthTolerance:0,maskLoss:0}),null);
});

test('stage-specific grading uses inclusive limits and never treats missing data as zero',()=>{
  const record=fixture();
  record.etch.center_depth_nm=180;
  record.etch.width_half_depth_nm=90;
  assert.equal(assess(record,INITIAL_TARGETS,'etch').length,3);
  assert.ok(assess(record,INITIAL_TARGETS,'both').every(c=>c.pass));
  record.etch.center_depth_nm=179.99;
  record.ald.mid_gap_nm=null;
  record.ald.top_film_nm=NaN;
  const result=assess(record,INITIAL_TARGETS,'both');
  assert.deepEqual(result.map(c=>c.pass),[false,true,true,null,true,null]);
  record.etch.mask_loss_nm=0;
  assert.equal(assess(record,INITIAL_TARGETS,'etch')[2].actual,0);
  assert.deepEqual(assess(record,{...INITIAL_TARGETS,depth:NaN},'both'),[]);
});

test('summary preserves completed-run inputs and marks zero-growth conformity unknown',async()=>{
  const run=JSON.parse(await readFile(new URL('../public/native/sequence-reference.json',import.meta.url),'utf8'));
  const original=JSON.stringify(run);
  const summary=summarizeRun(run,'example','QA-time');
  assert.deepEqual(summary.params,run.request.params);
  summary.params.seed=-1;
  summary.warnings.push('QA');
  assert.equal(JSON.stringify(run),original);
  run.ald.frames.at(-1).metrics.top_film_nm=0;
  run.ald.frames.at(-1).metrics.bottom_top_pct=100;
  run.etch.frames.at(-1).metrics.center_depth_nm=Infinity;
  const empty=summarizeRun(run,'local','QA-time');
  assert.equal(empty.ald.bottom_top_pct,null);
  assert.equal(empty.etch.center_depth_nm,null);
  assert.equal(assess(empty,INITIAL_TARGETS,'ald')[1].pass,null);
});

test('attempt ledger requires new local jobs and leaves fixed objectives and previous history intact',()=>{
  const initial=notebook();
  const before=JSON.stringify(initial);
  const record=fixture();
  assert.throws(()=>appendAttempt(initial,'task-1',{...record,source:'example'},'job-a',''));
  const first=appendAttempt(initial,'task-1',record,'job-a','Hypothesis');
  assert.equal(JSON.stringify(initial),before);
  assert.equal(first.sessions[0].attempts.length,1);
  assert.deepEqual(first.sessions[0].targets,INITIAL_TARGETS);
  const duplicate=appendAttempt(first,'task-1',record,'job-a','duplicate callback');
  assert.equal(duplicate.sessions[0].attempts.length,1);
  const repeat=appendAttempt(first,'task-1',record,'job-b','same inputs, new job');
  assert.equal(repeat.sessions[0].attempts.length,2);
  record.params.cycles=999;
  record.etch.center_depth_nm=0;
  assert.equal(first.sessions[0].attempts[0].params.cycles,1);
  assert.equal(first.sessions[0].attempts[0].etch.center_depth_nm,200);
  const ended={...repeat,activeId:null,sessions:repeat.sessions.map(s=>({...s,ended:'QA-end'}))};
  assert.equal(appendAttempt(ended,'task-1',fixture(),'job-c','').sessions[0].attempts.length,2);
});

test('saved ledger round trips pending jobs and rejects malformed or falsely credited example attempts',()=>{
  const store=appendAttempt(notebook(),'task-1',fixture(),'job-a','test');
  store.pending={jobId:'job-b',sessionId:'task-1',note:'next'};
  store.recipes.push({id:'recipe-a',name:'Saved inputs',note:'',params:{seed:42},created:'QA'});
  store.comparisons.push({...fixture(),source:'example'});
  assert.deepEqual(parsePracticeStore(JSON.stringify(store)),store);
  assert.deepEqual(parsePracticeStore(null),emptyPracticeStore());
  assert.throws(()=>parsePracticeStore('{'));
  for(const mutate of [v=>v.version=2,v=>v.activeId='missing',v=>v.sessions[0].targets.depth=null,
    v=>v.sessions[0].attempts[0].source='example',v=>v.recipes[0].params.seed='oops']){
    const bad=structuredClone(store);mutate(bad);assert.throws(()=>parsePracticeStore(JSON.stringify(bad)));
  }
});

test('CSV includes complete input union, literal zero, missing values and escaped user text',()=>{
  const a=fixture(),b=fixture();
  a.label='=1+1';a.etch.mask_loss_nm=0;a.ald.mid_gap_nm=null;
  b.label='A, "B"';b.params.extra=-2;
  const csv=recordCsv([a,b]);
  assert.ok(csv.includes('"extra"'));
  assert.ok(csv.includes('"\'=1+1"'));
  assert.ok(csv.includes('"A, ""B"""'));
  assert.ok(csv.includes('"0"'));
  assert.ok(csv.includes('"-2"'));
  assert.ok(!csv.includes('null'));
});
