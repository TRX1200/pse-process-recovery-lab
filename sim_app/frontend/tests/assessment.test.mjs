import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import ts from "typescript";
const source = await readFile(
  new URL("../src/assessment.ts", import.meta.url),
  "utf8",
);
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    target: ts.ScriptTarget.ES2022,
    module: ts.ModuleKind.ESNext,
  },
}).outputText;
const a = await import(
  `data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`
);

// Hand-defined fixtures exercise decisions, not physical accuracy.
function etch(values = {}, effective = {}) {
  return {
    model_version: "etch-ar-global-0.1.1",
    metrics: Object.entries({
      etch_depth_nm: 30,
      nonuniformity_pct: 2,
      mask_loss_nm: 2,
      selectivity: 12,
      ...values,
    }).map(([key, value]) => ({ key, value })),
    effective: { status: "steady", selectivity_defined: true, ...effective },
  };
}
function ald(values = {}) {
  return {
    model_version: "ald-reactive-diffusion-1.0.1",
    metrics: Object.entries({
      top_thickness_nm: 5,
      gpc_nm: 0.1,
      conformality_pct: 98,
      overlap_pa_s: 0.001,
      residual_pressure_pa: 0.002,
      cycle_time_s: 4,
      ...values,
    }).map(([key, value]) => ({ key, value })),
    effective: {},
  };
}
const reviewEtch = (result, spec = a.defaultSpec("etch"), time = 60) =>
  a.evaluate("etch", result, { process_time_s: time }, spec);

test("spec boundaries are inclusive and no metric compensates for another failure", () => {
  const equal = etch({
    etch_depth_nm: 27,
    nonuniformity_pct: 5,
    mask_loss_nm: 3,
    selectivity: 10,
  });
  assert.equal(reviewEtch(equal, undefined, 90).status, "within_spec");
  for (const [key, value] of Object.entries({
    etch_depth_nm: 33.00001,
    nonuniformity_pct: 5.00001,
    mask_loss_nm: 3.00001,
    selectivity: 9.99999,
  })) {
    const review = reviewEtch(etch({ [key]: value }));
    assert.equal(review.status, "outside_spec", key);
    assert.equal(review.checks.filter((c) => c.status === "fail").length, 1);
  }
  assert.equal(
    reviewEtch(etch(), undefined, 91).checks.find((c) => c.key === "time")
      .status,
    "fail",
  );
});

test("off plasma cannot gain a good uniformity or infinite selectivity score", () => {
  const review = reviewEtch(
    etch(
      {
        etch_depth_nm: 0,
        nonuniformity_pct: 0,
        mask_loss_nm: 0,
        selectivity: 0,
      },
      { status: "off", selectivity_defined: false },
    ),
  );
  assert.equal(review.status, "outside_spec");
  assert.equal(review.checks.find((c) => c.key === "depth").status, "fail");
  for (const key of ["uniformity", "selectivity"])
    assert.equal(
      review.checks.find((c) => c.key === key).status,
      "unavailable",
    );
});

test("outside-fit and unsupported versions block even otherwise passing numbers", () => {
  for (const result of [
    etch({}, { status: "outside_rate_fit" }),
    { ...etch(), model_version: "future-unknown" },
    etch({}, { status: "unexpected" }),
    undefined,
  ]) {
    const review = reviewEtch(result);
    assert.equal(review.status, "incomplete");
    assert.ok(review.blockers.length);
    assert.ok(
      review.checks.every(
        (c) => c.value === null && c.status === "unavailable",
      ),
    );
  }
});

test("missing and nonfinite values produce explicit incomplete judgments", () => {
  for (const value of [undefined, NaN, Infinity, null, -1]) {
    const review = reviewEtch(etch({ mask_loss_nm: value }));
    assert.equal(review.status, "incomplete");
    assert.equal(review.checks.find((c) => c.key === "mask").value, null);
  }
});

test("ALD assesses projected thickness, conformality, overlap, residual and cycle time separately", () => {
  const spec = a.defaultSpec("ald");
  assert.equal(a.evaluate("ald", ald(), {}, spec).status, "within_spec");
  const review = a.evaluate(
    "ald",
    ald({ overlap_pa_s: 0.04, cycle_time_s: 8 }),
    {},
    spec,
  );
  assert.deepEqual(
    review.checks.filter((c) => c.status === "fail").map((c) => c.key),
    ["overlap", "time"],
  );
  const noGrowth = a.evaluate(
    "ald",
    ald({ top_thickness_nm: 0, gpc_nm: 0, conformality_pct: 0 }),
    {},
    spec,
  );
  assert.equal(
    noGrowth.checks.find((c) => c.key === "conformality").status,
    "unavailable",
  );
  assert.ok(noGrowth.unmodeled.length);
});

test("criteria must be finite, model-specific and retain a positive lower thickness bound", () => {
  for (const target of [NaN, Infinity, -1, "30", null]) {
    const spec = a.defaultSpec("etch");
    spec.values.target_nm = target;
    assert.throws(() => a.validateSpec(spec, "etch"));
  }
  const invalid = a.defaultSpec("etch");
  invalid.values.tolerance_nm = 30;
  assert.throws(() => a.validateSpec(invalid, "etch"));
  assert.throws(() => a.validateSpec(a.defaultSpec("ald"), "etch"));
  const unknown = a.defaultSpec("etch");
  unknown.values.unsupported = 1;
  assert.throws(() => a.validateSpec(unknown, "etch"));
});

test("report freezes criteria and assesses baseline using its own process time", () => {
  const run = {
    run_id: "fixture-current",
    model: "etch",
    params: { process_time_s: 60 },
    result: etch(),
    fault: "none",
    baseline: null,
  };
  const baseline = {
    label: "fixture-older",
    run_id: "fixture-old",
    params: { process_time_s: 120 },
    result: etch(),
  };
  const spec = a.defaultSpec("etch");
  const report = a.assessmentReport(
    run,
    spec,
    baseline,
    "Hypothesis and remaining evidence",
  );
  spec.values.target_nm = 40;
  assert.equal(report.spec.values.target_nm, 30);
  assert.equal(report.assessment.status, "within_spec");
  assert.equal(report.baseline.assessment.status, "outside_spec");
  assert.equal(
    report.baseline.assessment.checks.find((c) => c.key === "time").value,
    120,
  );
  assert.equal(report.run.run_id, "fixture-current");
  assert.equal(report.user_notes, "Hypothesis and remaining evidence");
  assert.doesNotThrow(() => JSON.parse(JSON.stringify(report)));
});

test("changing target re-evaluates the same result without mutating physical data", () => {
  const result = etch();
  const original = JSON.stringify(result);
  const spec = a.defaultSpec("etch");
  assert.equal(reviewEtch(result, spec).status, "within_spec");
  spec.values.target_nm = 40;
  assert.equal(reviewEtch(result, spec).status, "outside_spec");
  assert.equal(JSON.stringify(result), original);
});
