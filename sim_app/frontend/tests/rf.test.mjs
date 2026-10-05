import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import ts from 'typescript';
import {renderToString} from 'katex';
const source=await readFile(new URL('../src/rf.ts',import.meta.url),'utf8');
const compiled=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;
const {rfEquations,impedance}=await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);
test('RF formulas render strict KaTeX with accessible MathML',()=>{
  for(const formula of Object.values(rfEquations).flat()){
    const html=renderToString(formula,{throwOnError:true,strict:'error',trust:false,output:'htmlAndMathml'});
    assert.match(html,/katex-mathml/);assert.doesNotMatch(html,/katex-error/);
  }
});
test('RF impedance preserves the reactive sign',()=>{
  assert.equal(impedance([50,-10]),'50.00 − j10.00 Ω');
  assert.equal(impedance([50,10]),'50.00 + j10.00 Ω');
});
