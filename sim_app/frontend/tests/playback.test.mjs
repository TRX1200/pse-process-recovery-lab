import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import ts from "typescript";
const source = await readFile(
  new URL("../src/playback.ts", import.meta.url),
  "utf8",
);
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    target: ts.ScriptTarget.ES2022,
    module: ts.ModuleKind.ESNext,
  },
}).outputText;
const player = await import(
  `data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`
);

test("time playback interpolates endpoints and never extrapolates another recipe", () => {
  assert.equal(player.interpolate([0, 2, 4], [0, 10, 14], 1), 5);
  assert.equal(player.interpolate([0, 2, 4], [0, 10, 14], 4), 14);
  assert.equal(player.interpolate([0, 2], [0, 10], 3), null);
  assert.equal(player.interpolate([0, 2], [0, NaN], 1), null);
  assert.equal(player.interpolate([0, 0], [0, 0], 0), 0);
});
test("only time axes influence playback duration, and invalid results are disabled", () => {
  const result = {
    effective: {},
    series: [
      { x_label: "시간 (s)", x: [0, 4] },
      { x_label: "이온 에너지 (eV)", x: [0, 600] },
    ],
  };
  assert.equal(player.durationOf(result), 4);
  assert.equal(player.isTimeSeries(result.series[1]), false);
  assert.equal(
    player.durationOf({ ...result, effective: { status: "outside_rate_fit" } }),
    0,
  );
});
test("ALD phase switches at true recipe boundaries and skips zero-length phases", () => {
  const params = {
    pulse_a_s: 0.5,
    purge_a_s: 1.5,
    pulse_b_s: 0.5,
    purge_b_s: 1.5,
  };
  assert.equal(player.stageAt("ald", params, 0, 4).index, 0);
  assert.equal(player.stageAt("ald", params, 0.5, 4).index, 1);
  assert.equal(player.stageAt("ald", params, 2, 4).index, 2);
  assert.equal(player.stageAt("ald", params, 4, 4).index, -1);
  assert.equal(
    player.stageAt("ald", { ...params, pulse_a_s: 0 }, 0, 3.5).index,
    1,
  );
});
test("spatial playback follows solved frames rather than t/T times final geometry", () => {
  const result = {
    playback: {
      time_s: [0, 1, 2],
      profiles_nm: [
        [0, 0],
        [4, 0],
        [5, 3],
      ],
    },
  };
  assert.deepEqual(player.profileAt(result, 0.5), [2, 0]);
  assert.deepEqual(player.profileAt(result, 2), [5, 3]);
  assert.equal(player.profileAt({}, 1), undefined);
});
test("playback speed preserves physical seconds and stops at the endpoint", () => {
  assert.equal(player.advanceTime(2, 0.5, 5, 60), 4.5);
  assert.equal(player.advanceTime(59, 1, 5, 60), 60);
  assert.equal(player.advanceTime(2, -1, 5, 60), 2);
});
