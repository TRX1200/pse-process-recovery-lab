import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import ts from "typescript";

async function compiledUrl(path, replacements = {}) {
  const source = await readFile(new URL(path, import.meta.url), "utf8");
  let compiled = ts.transpileModule(source, {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
  }).outputText;
  for (const [specifier, resolved] of Object.entries(replacements))
    compiled = compiled.replaceAll(`"${specifier}"`, JSON.stringify(resolved));
  return `data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`;
}
const surface = await import(await compiledUrl("../src/surface.ts", {
  "./playback": await compiledUrl("../src/playback.ts"),
}));

function fixture(model = "ald") {
  return {
    effective: {}, spatial: { kind: model, x: model === "ald" ? [1, 3] : [-150, 0, 150], values: [50, 20] },
    playback: {
      profile_basis: model === "ald" ? "first_cycle_growth" : "etch_depth",
      time_s: [0, 1, 2],
      profiles_nm: model === "ald" ? [[0, 0], [0.4, 0], [0.5, 0.2]] : [[0, 0, 0], [4, 5, 4], [8, 10, 8]],
    },
  };
}
const params = { depth_um: 4, gap_um: 0.2, cycles: 100 };

test("ALD surface uses first-cycle frames, cell-centre positions, and one fixed display gain", () => {
  const result = fixture();
  const domain = surface.surfaceDomain("ald", result, params);
  assert.equal(domain.gapNm, 200);
  assert.equal(domain.maxNm, 0.5); // Not the 50 nm projection in spatial.values.
  assert.deepEqual(surface.cellEdges(domain), [0, 2, 4]);
  assert.deepEqual(surface.surfaceFrame(result, domain, 0), [0, 0]);
  assert.deepEqual(surface.surfaceFrame(result, domain, 0.5), [0.2, 0]);
  assert.deepEqual(surface.surfaceFrame(result, domain, 2), [0.5, 0.2]);
  assert.equal(domain.filmGain, 100);
  assert.equal(surface.surfaceFrame(result, domain, 3), null);
});

test("Etch surface preserves mm coordinates and nm depth, including a flat zero-removal run", () => {
  const result = fixture("etch");
  const domain = surface.surfaceDomain("etch", result, {});
  assert.equal(domain.xMin, -150);
  assert.equal(domain.xMax, 150);
  assert.equal(domain.depthAxisNm, 20);
  assert.deepEqual(surface.surfaceFrame(result, domain, 1.5), [6, 7.5, 6]);
  result.playback.profiles_nm = [[0, 0, 0], [0, 0, 0], [0, 0, 0]];
  const zero = surface.surfaceDomain("etch", result, {});
  assert.equal(zero.depthAxisNm, 1);
  assert.deepEqual(surface.surfaceFrame(result, zero, 1), [0, 0, 0]);
});

test("missing, malformed, wrong-basis, and invalid-model frames do not become plausible surfaces", () => {
  const mutations = [
    (r) => delete r.playback,
    (r) => r.playback.profile_basis = "etch_depth",
    (r) => r.playback.time_s = [0, 1, 1],
    (r) => r.playback.profiles_nm[1] = [NaN, 0],
    (r) => r.playback.profiles_nm[1] = [-0.01, 0],
    (r) => r.playback.profiles_nm[1] = [0],
    (r) => r.playback.time_s[2] = Infinity,
    (r) => r.spatial.x = [3, 1],
    (r) => r.spatial.x = [0, 3],
    (r) => r.effective.status = "outside_rate_fit",
  ];
  for (const mutate of mutations) {
    const result = fixture();
    mutate(result);
    assert.equal(surface.surfaceDomain("ald", result, params), null);
  }
  assert.equal(surface.surfaceDomain("ald", fixture(), { ...params, gap_um: 0 }), null);
});

test("solver roundoff stays at zero and thick ALD films never imply simulated pinch-off", () => {
  const result = fixture();
  result.playback.profiles_nm = [[-1e-12, 0], [100, 10], [200, 20]];
  const domain = surface.surfaceDomain("ald", result, params);
  assert.deepEqual(surface.surfaceFrame(result, domain, 0), [0, 0]);
  assert.ok(domain.maxNm * domain.filmGain * 2 < domain.gapNm);
  assert.ok(domain.filmGain < 1);
});
