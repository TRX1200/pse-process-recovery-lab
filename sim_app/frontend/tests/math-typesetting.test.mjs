import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { renderToString } from "katex";
import ts from "typescript";

const source = await readFile(
  new URL("../src/modelEquations.ts", import.meta.url),
  "utf8",
);
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    target: ts.ScriptTarget.ES2022,
    module: ts.ModuleKind.ESNext,
  },
}).outputText;
const { modelEquations } = await import(
  `data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`
);

// Validate every displayed formula, including macros and accessible output.
// These checks establish typesetting, not physical validation of the model.
for (const [model, groups] of Object.entries(modelEquations)) {
  test(`${model.toUpperCase()} equations compile strictly with visible math and MathML`, () => {
    assert.ok(Object.keys(groups).length > 0);
    for (const [group, expressions] of Object.entries(groups)) {
      assert.ok(expressions.length > 0, group);
      for (const expression of expressions) {
        const html = renderToString(expression, {
          displayMode: true,
          output: "htmlAndMathml",
          throwOnError: true,
          strict: "error",
          trust: false,
        });
        assert.match(html, /class="katex-mathml"/, `${group}: MathML`);
        assert.match(html, /<math[^>]*display="block"/, `${group}: block math`);
        assert.match(
          html,
          /class="katex-html" aria-hidden="true"/,
          `${group}: visual math`,
        );
        assert.doesNotMatch(html, /katex-error|<script|<iframe/, group);
      }
    }
  });
}
