import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import ts from 'typescript';
const source=await readFile(new URL('../src/sequence.ts',import.meta.url),'utf8');
const compiled=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;
const {inputProblem,recipeInputs,sameInputs,stageRun,sequenceCharts}=await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);

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

test('ALD experiment inputs replace all edited fields and leave computed evidence intact',async()=>{
  const catalog=JSON.parse(await readFile(new URL('../public/native/ald-recipes.json',import.meta.url),'utf8'));
  const schema=JSON.parse(await readFile(new URL('../public/native/schema.json',import.meta.url),'utf8'));
  const fields=schema.models.sequence.params;
  const result=JSON.parse(await readFile(new URL('../public/native/sequence-reference.json',import.meta.url),'utf8'));
  const original=JSON.stringify(result);
  let inputs={...result.request.params,seed:42,width_nm:200,ion_exponent:20};
  for(const recipe of catalog.recipes){
    inputs=recipeInputs(recipe,fields);
    assert.equal(inputProblem(fields,inputs),null);
    assert.equal(inputs.seed,20261003);
    assert.equal(inputs.ion_exponent,500);
    assert.deepEqual(inputs,recipe.request.params);
    assert.notStrictEqual(inputs,recipe.request.params);
  }
  inputs=recipeInputs(catalog.recipes[0],fields);
  assert.equal(inputs.width_nm,100);
  assert.equal(inputs.pulse_s,.02);
  inputs.pressure_pa=9;
  assert.equal(catalog.recipes[0].request.params.pressure_pa,3);
  assert.equal(JSON.stringify(result),original);
  assert.ok(!sameInputs(inputs,result.request.params));
  const invalid=structuredClone(catalog.recipes[0]);
  delete invalid.request.params.seed;
  assert.throws(()=>recipeInputs(invalid,fields));
  invalid.request.params.seed=1;
  invalid.request.params.cycles=1.5;
  assert.throws(()=>recipeInputs(invalid,fields));
  invalid.request.params.cycles=160;
  invalid.request.params.unexpected=123;
  assert.throws(()=>recipeInputs(invalid,fields));
});
