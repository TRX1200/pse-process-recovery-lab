import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import ts from 'typescript';
const source=await readFile(new URL('../src/sequenceControls.ts',import.meta.url),'utf8');
const compiled=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;
const {QUICK_KEYS,adjustedValue,controlFields,changedFields}=await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);
const schema=JSON.parse(await readFile(new URL('../public/native/schema.json',import.meta.url),'utf8'));
const fields=schema.models.sequence.params;
const spec=key=>fields.find(f=>f.key===key);

test('compact settings keep every schema parameter accessible and quick controls use the same fields',()=>{
  const grouped=['geometry','etch','ald','numerics'].flatMap(group=>controlFields(fields,group));
  assert.deepEqual(grouped.map(f=>f.key).sort(),fields.map(f=>f.key).sort());
  const quick=controlFields(fields,'quick');
  assert.equal(quick.length,8);
  assert.deepEqual(quick.map(f=>f.key),[...QUICK_KEYS]);
  for(const field of quick)assert.strictEqual(field,spec(field.key));
  for(const group of ['geometry','etch','ald','numerics']){
    assert.ok(Math.ceil(controlFields(fields,group).length/6)<=2);
  }
});

test('step controls preserve schema units, integer cycles, small decimals and bounds',()=>{
  assert.equal(adjustedValue(spec('pulse_s'),.02,1),.025);
  assert.equal(adjustedValue(spec('pressure_pa'),3,-1),2.5);
  assert.equal(adjustedValue(spec('cycles'),160,1),170);
  assert.equal(adjustedValue(spec('grid_nm'),5,-1),4.5);
  assert.equal(adjustedValue(spec('coverage_dt_s'),.001,-1),.0009);
  for(const field of fields){
    assert.equal(adjustedValue(field,field.min,-1),field.min);
    assert.equal(adjustedValue(field,field.max,1),field.max);
    assert.ok(Number.isFinite(adjustedValue(field,NaN,1)));
    if(field.integer)assert.ok(Number.isInteger(adjustedValue(field,field.default,1)));
  }
});

test('input change count tracks edits without mutating the completed run',()=>{
  const baseline=Object.fromEntries(fields.map(f=>[f.key,f.default]));
  const before=JSON.stringify(baseline);
  assert.equal(changedFields(fields,{...baseline},baseline),0);
  assert.equal(changedFields(fields,{...baseline,pulse_s:NaN},baseline),1);
  assert.equal(changedFields(fields,{...baseline,pulse_s:.02,cycles:160},baseline),2);
  assert.equal(JSON.stringify(baseline),before);
});
