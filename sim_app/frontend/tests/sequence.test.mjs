import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import ts from 'typescript';
const source=await readFile(new URL('../src/sequence.ts',import.meta.url),'utf8');
const compiled=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;
const {inputProblem,sameInputs,stageRun,sequenceCharts}=await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);

test('sequence input identity ignores object ordering and rejects invalid numeric inputs',()=>{
  assert.ok(sameInputs({a:1,b:2},{b:2,a:1}));
  assert.ok(!sameInputs({a:1},{a:1,b:2}));
  assert.ok(!sameInputs({a:NaN},{a:NaN}));
  const fields=[{key:'cycles',label:'cycles',min:1,max:500,integer:true}];
  assert.ok(inputProblem(fields,{cycles:1.5}));
  assert.ok(inputProblem(fields,{cycles:NaN}));
  assert.ok(inputProblem(fields,{cycles:2,width_nm:10,grid_nm:5}));
});

test('native sequence public output carries exact Si geometry and correct per-stage axes',async()=>{
  const result=JSON.parse(await readFile(new URL('../public/native/sequence-reference.json',import.meta.url),'utf8'));
  assert.equal(result.handoff.si_contour_preserved,true);
  assert.deepEqual(result.strip.layers[0],result.ald.frames[0].layers[0]);
  assert.deepEqual(result.strip.layers[0],result.ald.frames.at(-1).layers[0]);
  assert.equal(stageRun(result,'strip').frames.length,1);
  assert.equal(sequenceCharts(result,'etch')[0].x_label,'Etch time (s)');
  const charts=sequenceCharts(result,'ald');
  assert.equal(charts[0].x_label,'ALD cycles');
  assert.ok(Number.isNaN(charts[1].lines[0].values[0]));
  assert.ok(Number.isFinite(charts[1].lines[0].values.at(-1)));
});
