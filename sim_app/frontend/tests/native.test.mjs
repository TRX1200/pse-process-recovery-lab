import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import ts from "typescript";

const src = await readFile(new URL("../src/native.ts", import.meta.url), "utf8");
const compiled = ts.transpileModule(src, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } }).outputText;
const { contourPath, extentOf, compatibleGeometry } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`);

test("native contours retain closed holes and use substrate closure only on open boundaries", () => {
  const paths = [[[0, 0], [1, -1], [2, 0]], [[.5, -.5], [1, -.8], [1.5, -.5], [.5, -.5]]];
  const d = contourPath(paths, x => x, y => y, -10, true);
  assert.equal((d.match(/ Z/g) ?? []).length, 2);
  assert.equal((d.match(/-10/g) ?? []).length, 2);
  assert.equal((contourPath(paths, x => x, y => y, -10, false).match(/-10/g) ?? []).length, 0);
});
test("viewport uses fixed bounds from all solved frames", () => {
  const frames = [0, -150].map(y => ({ layers: [{ paths_nm: [[[-100, 0], [0, y], [100, 0]]] }] }));
  assert.deepEqual(extentOf(frames, 200), [-100, 100, -170, 20]);
});
test("comparisons reject different geometry and processes", () => {
  const a = { model: "etch", params: { pitch_nm: 400, width_nm: 100, mask_nm: 80 } };
  assert.equal(compatibleGeometry(a, structuredClone(a)), true);
  assert.equal(compatibleGeometry(a, { ...a, params: { ...a.params, width_nm: 200 } }), false);
  assert.equal(compatibleGeometry(a, { ...a, model: "ald" }), false);
});
