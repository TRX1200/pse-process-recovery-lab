import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import ts from "typescript";

// Compile the pure TS module with the project's existing compiler; no test framework dependency.
const source = await readFile(
  new URL("../src/storage.ts", import.meta.url),
  "utf8",
);
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    target: ts.ScriptTarget.ES2022,
    module: ts.ModuleKind.ESNext,
  },
}).outputText;
const storage = await import(
  `data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`
);

const schema = {
  models: {
    ald: {
      params: [
        {
          key: "cycles",
          min: 1,
          max: 150,
          default: 50,
          label: "Cycles",
          unit: "cycle",
        },
        {
          key: "pulse_a_s",
          min: 0,
          max: 5,
          default: 0.5,
          label: "Pulse A",
          unit: "s",
        },
      ],
      faults: [{ id: "none" }],
    },
  },
};
const recipe = {
  format: "process-studio-recipe-v1",
  name: "Test",
  model: "ald",
  params: { cycles: 50, pulse_a_s: 0.5 },
  fault: "none",
};

test("recipe import preserves valid inputs and rejects missing, nonfinite and unknown parameters", () => {
  assert.deepEqual(
    storage.validateRecipe(recipe, schema).params,
    recipe.params,
  );
  for (const params of [
    { cycles: 50 },
    { cycles: Infinity, pulse_a_s: 0.5 },
    { cycles: 50, pulse_a_s: 0.5, injected: 1 },
  ]) {
    assert.throws(() => storage.validateRecipe({ ...recipe, params }, schema));
  }
});

test("recipe import rejects fractional ALD cycles and invalid fault modes", () => {
  assert.throws(() =>
    storage.validateRecipe(
      { ...recipe, params: { ...recipe.params, cycles: 2.5 } },
      schema,
    ),
  );
  assert.throws(() =>
    storage.validateRecipe({ ...recipe, fault: "unknown" }, schema),
  );
});

test("metric validity separates physically off zero from unsupported fit and undefined ratios", () => {
  assert.equal(
    storage.metricValidity("etch_depth_nm", [], { status: "off" }),
    "valid",
  );
  assert.equal(
    storage.metricValidity("etch_depth_nm", [], { status: "outside_rate_fit" }),
    "outside_rate_fit",
  );
  assert.equal(
    storage.metricValidity("selectivity", [], { selectivity_defined: false }),
    "undefined_ratio",
  );
  assert.equal(
    storage.metricValidity(
      "conformality_pct",
      [{ key: "top_thickness_nm", value: 0 }],
      {},
    ),
    "no_growth",
  );
});

test("near-zero baseline displays an absolute difference rather than an explosive percentage", () => {
  const label = storage.comparisonLabel(0.000295, 1e-17, "Pa·s");
  assert.match(label, /Δ \+2.95e-4 Pa·s/);
  assert.doesNotMatch(label, /%/);
  assert.match(storage.comparisonLabel(2, 0, "nm"), /Δ \+2 nm/);
  assert.equal(storage.comparisonLabel(110, 100, "nm"), "+10% vs baseline");
});

test("axis labels retain distinct ticks for small parameter changes", () => {
  const labels = [4.99996, 4.99997, 4.99998, 4.99999, 5].map((value) =>
    storage.axisTick(value, 0.00001),
  );
  assert.equal(new Set(labels).size, 5);
  assert.notEqual(
    storage.axisTick(1.001e-7, 1e-10),
    storage.axisTick(1.002e-7, 1e-10),
  );
  assert.equal(storage.axisTick(0, 1), "0");
});

test("CSV exports blank unsupported and undefined values with model and baseline provenance", async () => {
  let captured;
  const originalURL = URL.createObjectURL;
  const originalRevoke = URL.revokeObjectURL;
  URL.createObjectURL = (blob) => {
    captured = blob;
    return "blob:test";
  };
  URL.revokeObjectURL = () => {};
  globalThis.document = {
    body: { appendChild() {} },
    createElement: () => ({ click() {}, remove() {} }),
  };
  try {
    const result = {
      model_version: "test-model",
      metrics: [
        { key: "etch_depth_nm", value: 0, unit: "nm" },
        { key: "selectivity", value: 0, unit: "" },
      ],
      series: [
        {
          key: "depth",
          x: [0, 1],
          x_label: "s",
          y_label: "nm",
          lines: [{ name: "target", values: [0, 0] }],
        },
      ],
      effective: { status: "outside_rate_fit", selectivity_defined: false },
    };
    storage.exportRunCsv({
      run_id: "test-run",
      model: "etch",
      fault: "delivery_loss",
      result,
      baseline: {
        ...result,
        effective: { status: "off", selectivity_defined: false },
      },
    });
    const csv = await captured.text();
    assert.match(csv, /"model_version"/);
    assert.match(
      csv,
      /"test-model","delivery_loss","result_metric","etch_depth_nm","","","","","nm","outside_rate_fit"/,
    );
    assert.match(
      csv,
      /"test-model","none","baseline_metric","etch_depth_nm","","","0","","nm","valid"/,
    );
    assert.match(
      csv,
      /"baseline_metric","selectivity","","","","","","undefined_ratio"/,
    );
  } finally {
    URL.createObjectURL = originalURL;
    // download() defers revoke by 1 second, so retain the harmless revoke stub for that URL.
    setTimeout(() => {
      URL.revokeObjectURL = originalRevoke;
    }, 1100);
    delete globalThis.document;
  }
});
