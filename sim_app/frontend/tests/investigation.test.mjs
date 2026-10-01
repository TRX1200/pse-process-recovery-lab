import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import ts from "typescript";

async function compiledUrl(path, replacements = {}) {
  const source = await readFile(new URL(path, import.meta.url), "utf8");
  let compiled = ts.transpileModule(source, {
    compilerOptions: {
      target: ts.ScriptTarget.ES2022,
      module: ts.ModuleKind.ESNext,
    },
  }).outputText;
  for (const [specifier, resolved] of Object.entries(replacements))
    compiled = compiled.replaceAll(`"${specifier}"`, JSON.stringify(resolved));
  return `data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`;
}

const playbackUrl = await compiledUrl("../src/playback.ts");
const investigation = await import(
  await compiledUrl("../src/investigation.ts", { "./playback": playbackUrl })
);

function parameter(key, value, min, max) {
  return {
    key,
    default: value,
    min,
    max,
    label: key,
    unit: "",
    step: 1,
    group: "Recipe",
    description: "Test parameter",
  };
}
const schemas = {
  etch: {
    params: [
      parameter("source_power_w", 600, 0, 3000),
      parameter("pressure_mtorr", 20, 1, 150),
      parameter("fault_severity", 0.35, 0, 1),
    ],
    faults: [{ id: "none" }, { id: "rf_mismatch" }],
  },
  ald: {
    params: [
      parameter("pulse_a_s", 0.5, 0, 5),
      parameter("purge_a_s", 1.5, 0, 8),
      parameter("pulse_b_s", 0.5, 0, 5),
      parameter("purge_b_s", 1.5, 0, 8),
      parameter("cycles", 50, 1, 150),
      parameter("fault_severity", 0.35, 0, 1),
    ],
    faults: [{ id: "none" }, { id: "purge_restriction" }],
  },
};

test("fault and intervention comparisons isolate changes and leave defaults untouched", () => {
  for (const model of ["etch", "ald"]) {
    const schema = structuredClone(schemas[model]);
    const settings = { severity: 0.5, action: model === "etch" ? 1200 : 4 };
    const before = structuredClone(schema);
    const plan = investigation.createInvestigationPlan(model, schema, settings);
    assert.equal(plan.length, 3);
    assert.equal(plan[0].fault, "none");
    assert.equal(plan[1].fault, plan[2].fault);
    assert.deepEqual(plan[0].params, plan[1].params);
    assert.deepEqual(
      Object.keys(plan[2].params).filter(
        (key) => plan[1].params[key] !== plan[2].params[key],
      ),
      model === "etch" ? ["source_power_w"] : ["purge_a_s", "purge_b_s"],
    );
    assert.equal(plan[1].params.fault_severity, 0.5);
    assert.equal(plan[2].params.fault_severity, 0.5);
    plan[0].params.fault_severity = 0;
    assert.equal(plan[1].params.fault_severity, 0.5);
    assert.deepEqual(schema, before);
  }
});

test("defaults and input validation respect schema bounds, finite values, and ALD integer cycles", () => {
  assert.deepEqual(
    investigation.defaultInvestigationSettings("etch", schemas.etch),
    { severity: 0.35, action: 923.08 },
  );
  assert.deepEqual(
    investigation.defaultInvestigationSettings("ald", schemas.ald),
    { severity: 0.35, action: 3 },
  );
  for (const severity of [NaN, Infinity, -0.01, 0.80001, "0.35"])
    assert.throws(() =>
      investigation.createInvestigationPlan("etch", schemas.etch, {
        severity,
        action: 600,
      }),
    );
  for (const action of [NaN, Infinity, -1, 3001, "600"])
    assert.throws(() =>
      investigation.createInvestigationPlan("etch", schemas.etch, {
        severity: 0.35,
        action,
      }),
    );
  const limited = structuredClone(schemas.ald);
  limited.params.find((item) => item.key === "purge_b_s").max = 2;
  assert.throws(() =>
    investigation.createInvestigationPlan("ald", limited, {
      severity: 0.35,
      action: 3,
    }),
  );
  const fractional = structuredClone(schemas.ald);
  fractional.params.find((item) => item.key === "cycles").default = 50.5;
  assert.throws(() =>
    investigation.createInvestigationPlan("ald", fractional, {
      severity: 0.35,
      action: 3,
    }),
  );
  for (const severity of [0, 0.8])
    assert.doesNotThrow(() =>
      investigation.createInvestigationPlan("etch", schemas.etch, {
        severity,
        action: 3000,
      }),
    );
});

test("bounded interpolation preserves exact samples and cannot extrapolate or bridge missing data", () => {
  const at = investigation.interpolateWithinDomain;
  assert.equal(at([0, 2, 4], [1, 5, 9], 1), 3);
  assert.equal(at([0, 2, 4], [1, 5, 9], 4), 9);
  for (const t of [-1, 4.00001, NaN])
    assert.ok(Number.isNaN(at([0, 2, 4], [1, 5, 9], t)));
  assert.ok(Number.isNaN(at([0, 2, 4], [1, NaN, 9], 1)));
  assert.ok(Number.isNaN(at([0, 0, 1], [1, 2, 3], 0)));
  assert.ok(Number.isNaN(at([0, 2, 1], [1, 2, 3], 0.5)));
  assert.ok(Number.isNaN(at([0, Infinity], [1, 2], 1)));
  assert.ok(Number.isNaN(at([0, 1], [1], 0)));
  assert.ok(Number.isNaN(at([], [], 0)));
  assert.equal(at([2], [7], 2), 7);
  assert.ok(Number.isNaN(at([2], [7], 3)));
});

function aldRun(x, values, effective = {}) {
  return {
    model: "ald",
    result: {
      effective,
      series: [
        {
          key: "pressure",
          x_label: "시간 (s)",
          x,
          lines: [
            { name: "A", values: x.map(() => 99) },
            { name: "B", values },
          ],
        },
      ],
    },
  };
}

test("comparison uses a union time grid with no tail past a shorter ALD cycle", () => {
  const series = investigation.comparisonSeries("ald", [
    aldRun([0, 1, 2], [0, 2, 0]),
    aldRun([0, 0.5, 3], [0, 1, 6]),
    aldRun([0, 2, 4], [0, 4, 0]),
  ]);
  assert.deepEqual(series.x, [0, 0.5, 1, 2, 3, 4]);
  assert.deepEqual(series.lines[0].values.slice(0, 4), [0, 1, 2, 0]);
  assert.ok(series.lines[0].values.slice(4).every(Number.isNaN));
  assert.equal(series.lines[1].values[2], 2);
  assert.equal(series.lines[1].values[4], 6);
  assert.ok(Number.isNaN(series.lines[1].values[5]));
  assert.deepEqual(series.lines[2].values, [0, 1, 2, 4, 2, 0]);
  assert.deepEqual(
    series.lines.map((line) => line.name),
    ["기준", "배기 지연", "퍼지 연장"],
  );
});

test("invalid or mismatched model results are not presented as comparison curves", () => {
  assert.equal(
    investigation.comparisonSeries("etch", [aldRun([0, 1], [0, 1])]),
    null,
  );
  assert.equal(investigation.comparisonSeries("ald", []), null);
  assert.equal(
    investigation.comparisonSeries("ald", [
      aldRun([0, 1], [0, 1], { status: "outside_rate_fit" }),
    ]),
    null,
  );
  const series = investigation.comparisonSeries("ald", [
    aldRun([0, 1], [0, 1]),
    aldRun([0, 1], [0, 1], { status: "outside_rate_fit" }),
  ]);
  assert.ok(series.lines[1].values.every(Number.isNaN));
});
