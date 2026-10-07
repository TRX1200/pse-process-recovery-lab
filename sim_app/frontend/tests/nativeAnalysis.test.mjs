import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import ts from 'typescript';
const source=await readFile(new URL('../src/nativeAnalysis.ts',import.meta.url),'utf8');
const compiled=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;
const {defaultGoal,targetPaths,analyzeFrame,evaluateNative,contourError,nativeCharts,goalError,parseGoalDraft}=await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);
const flat=y=>[[[-200,y],[200,y]]];
const trench=(d,w)=>[[[-200,0],[-w/2,0],[-w/2,-d],[w/2,-d],[w/2,0],[200,0]]];
const frame=(at,paths,metrics={})=>({at,label:'test',layers:[{material:'Si',paths_nm:paths}],metrics});
const fixture=(model='etch',profile=0)=>({model,params:{surface_profile:profile,pitch_nm:400,width_nm:100,depth_nm:240,grid_nm:2},frames:[frame(0,profile===1?flat(0):trench(240,100))],axis_unit:model==='etch'?'s':'cycle',warnings:[]});
const review=(run,goal,f=run.frames.at(-1))=>evaluateNative(run,f,goal,analyzeFrame(run,f,targetPaths(run,goal)));

test('identical geometry has zero contour error; a planar translation has its exact distance',()=>{
  assert.ok(contourError(trench(240,100),trench(240,100))<1e-10);
  assert.ok(Math.abs(contourError(flat(0),flat(10))-10)<1e-12);
  assert.equal(contourError([],flat(0)),null);
});
test('etch target is total depth rather than additional removal from an existing trench',()=>{
  const r=fixture(),g=defaultGoal('etch',2);g.advance_nm=250;
  assert.equal(Math.min(...targetPaths(r,g).flat().map(p=>p[1])),-250);
});
test('ideal rectangular etch meets independently specified depth, CD, and roughness',()=>{
  const r=fixture(),g=defaultGoal('etch',0);
  r.frames.push(frame(5,trench(250,100),{center_depth_nm:250,width_half_depth_nm:100}));
  assert.equal(review(r,g).status,'pass');
  const stricter={...g,advance_nm:300};assert.equal(review(r,stricter).rows.find(v=>v.key==='center_depth_nm').status,'fail');
});
test('missing geometry and undefined wall metrics never become a passing zero',()=>{
  const r=fixture(),g=defaultGoal('etch',0);r.frames.push(frame(5,[],{}));
  const v=review(r,g);assert.equal(v.status,'unknown');assert.ok(v.rows.every(row=>row.value===null));
});
test('mask union above the original Si plane is excluded from etch target distance',()=>{
  const r=fixture(),g=defaultGoal('etch',0);
  r.frames.push(frame(5,[[[-200,80],[-50,80],[-50,-250],[50,-250],[50,80],[200,80]]],{center_depth_nm:250,width_half_depth_nm:100}));
  const a=analyzeFrame(r,r.frames[1],targetPaths(r,g));assert.ok(a.metrics.target_rms_nm<1e-10);
  assert.equal(Math.max(...a.top.y),0);
});
test('invalid goals disable shape and all verdicts without changing numerical data',()=>{
  const r=fixture(),snapshot=structuredClone(r),g=defaultGoal('etch',0);
  for(const invalid of [{...g,advance_nm:NaN},{...g,tolerance_nm:-1},{...g,width_nm:399}]){
    assert.ok(goalError(r,invalid));assert.deepEqual(targetPaths(r,invalid),[]);assert.ok(review(r,invalid).rows.every(v=>v.status==='unknown'));
  }
  assert.deepEqual(r,snapshot);
});
test('zero ALD film has undefined bottom-to-top coverage; impossible closed target is rejected',()=>{
  const r=fixture('ald'),g=defaultGoal('ald',0);r.frames[0].metrics={top_film_nm:0,bottom_top_pct:0};
  assert.equal(review(r,g).rows.find(v=>v.key==='bottom_top_pct').value,null);
  assert.ok(goalError(r,{...g,advance_nm:50}));
});
test('ALD geometric offset thickens a flat plane exactly and narrows a rectangular opening',()=>{
  const r=fixture('ald'),g={...defaultGoal('ald',0),advance_nm:10};
  const target=targetPaths(r,g)[0];assert.deepEqual(target,[[-200,10],[-40,10],[-40,-230],[40,-230],[40,10],[200,10]]);
  r.params.surface_profile=1;r.frames=[frame(0,flat(0))];
  assert.deepEqual(targetPaths(r,g),flat(10));
});
test('sinusoidal planar roughness equals A/sqrt(2) and is invariant to vertical removal',()=>{
  const r=fixture('etch',1),g=defaultGoal('etch',1);
  const wave=shift=>[Array.from({length:4097},(_,i)=>{const x=-200+i*400/4096;return [x,8*Math.cos(2*Math.PI*3*x/400)+shift];})];
  r.frames=[frame(0,wave(0)),frame(1,wave(-10))];
  const a=analyzeFrame(r,r.frames[1],targetPaths(r,g));
  assert.ok(Math.abs(a.metrics.roughness_rq_nm-8/Math.sqrt(2))<.001);
  assert.ok(Math.abs(a.metrics.mean_advance_nm-10)<1e-10);
});
test('straight tilted walls have zero detrended Rq and scallop ROI stays fixed during etch',()=>{
  const r=fixture('etch',2),g=defaultGoal('etch',2);
  r.frames.push(frame(1,[[[-200,0],[-60,0],[-40,-300],[40,-300],[60,0],[200,0]]],{center_depth_nm:300}));
  const a=analyzeFrame(r,r.frames[1],targetPaths(r,g));
  assert.ok(a.metrics.wall_rq_nm<1e-12);assert.equal(a.wall.depth[0],24);assert.equal(a.wall.depth.at(-1),216);
});
test('chart rates use actual nonuniform intervals; the first rate is not invented',()=>{
  const r=fixture('etch',1),g=defaultGoal('etch',1);r.frames=[frame(0,flat(0)),frame(2,flat(-4)),frame(5,flat(-10))];
  const a=r.frames.map(f=>analyzeFrame(r,f,targetPaths(r,g))),charts=nativeCharts(r,g,a,2);
  const values=charts.history.find(c=>c.key==='rate').lines[0].values;
  assert.ok(Number.isNaN(values[0]));assert.deepEqual(values.slice(1),[2,2]);
  assert.equal(charts.history.length+charts.spatial.length,6);assert.equal(charts.spatial[0].x_label,'x / nm');
});
test('strict subgrid targets warn and intermediate frames are labelled',()=>{
  const r=fixture(),g={...defaultGoal('etch',0),roughness_nm:0};r.frames.push(frame(1,trench(250,100)));
  const v=review(r,g,r.frames[0]);assert.ok(v.warnings.some(s=>s.includes('격자')));assert.ok(v.warnings.some(s=>s.includes('중간')));
});
test('evaluation captures goals by value so later edits do not rewrite a saved judgement',()=>{
  const r=fixture(),g=defaultGoal('etch',0),v=review(r,g);g.advance_nm=1000;assert.equal(v.goal.advance_nm,250);
});
test('session goal drafts reject malformed fields, nonfinite numbers and unrelated keys',()=>{
  const g=defaultGoal('ald',1);
  assert.deepEqual(parseGoalDraft('{invalid'),{});
  const raw=JSON.stringify({'ald-1':{...g,extra:'drop'},'etch-2':{...g,advance_nm:NaN},'other':g});
  assert.deepEqual(parseGoalDraft(raw),{'ald-1':g});
});
for(const model of ['etch','ald'])test(`${model} recorded ripple/scallop Rq agrees with native engine measurements`,async()=>{
  for(const profile of ['ripple','scallop']){
    const r=JSON.parse(await readFile(new URL(`../public/native/${model}-${profile}.json`,import.meta.url),'utf8'));
    const g=defaultGoal(model,r.params.surface_profile),target=targetPaths(r,g);
    for(const f of r.frames){const a=analyzeFrame(r,f,target);for(const key of profile==='ripple'?['roughness_rq_nm','mean_advance_nm']:['left_wall_rq_nm','right_wall_rq_nm']){
      if(f.metrics[key]===null)assert.equal(a.metrics[key],null);else assert.ok(Math.abs(a.metrics[key]-f.metrics[key])<1e-6,`${model}/${profile}/${key}: ${a.metrics[key]} != ${f.metrics[key]}`);
    }}
  }
});
test('all eight stored examples produce finite-or-null review values and separate spatial charts',async()=>{
  for(const model of ['etch','ald'])for(const variant of ['reference','variant','ripple','scallop']){
    const r=JSON.parse(await readFile(new URL(`../public/native/${model}-${variant}.json`,import.meta.url),'utf8'));
    const g=defaultGoal(model,r.params.surface_profile??0),target=targetPaths(r,g),a=r.frames.map(f=>analyzeFrame(r,f,target));
    const charts=nativeCharts(r,g,a,a.length-1),v=evaluateNative(r,r.frames.at(-1),g,a.at(-1));
    assert.ok(v.rows.every(row=>row.value===null||Number.isFinite(row.value)));
    assert.equal(charts.spatial.length,2);assert.ok(charts.history.length>=4);
    assert.ok(target.flat().every(point=>point.every(Number.isFinite)));
  }
});
