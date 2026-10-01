import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import ts from "typescript";

const source = await readFile(new URL("../src/userGuide.ts", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } }).outputText;
const guide = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`);
const document = await readFile(new URL("../../../docs/SIMULATOR_USER_GUIDE_KR.md", import.meta.url), "utf8");

for (const model of ["ald", "etch"]) {
  const python = await readFile(new URL(`../../models/${model}.py`, import.meta.url), "utf8");
  const keys = [...python.matchAll(/_param\("([a-z0-9_]+)"/g)].map(match => match[1]);
  test(`${model} manual covers every real model input and keeps only four starter knobs`, () => {
    assert.deepEqual(Object.keys(guide.PARAMETER_TIPS[model]).sort(), keys.sort());
    assert.equal(guide.QUICK_KEYS[model].length, 4);
    assert.equal(new Set(guide.QUICK_KEYS[model]).size, 4);
    for (const key of keys) {
      assert.ok(guide.PARAMETER_TIPS[model][key].length > 20, key);
      assert.ok(document.includes(`(${key})`), key);
      assert.ok(document.includes(guide.PARAMETER_TIPS[model][key]), key);
    }
    for (const key of guide.QUICK_KEYS[model]) {
      assert.ok(keys.includes(key));
      assert.equal(guide.parameterTier(model, { key, group: "Recipe" }), "먼저 조절");
    }
    assert.equal(guide.parameterTier(model, { key: "fault_severity", group: "Advanced" }), "이상 주입");
  });
}

test("downloadable manual gets defaults and units from the supplied schema, with complete guidance", () => {
  const schema = { models: Object.fromEntries(["ald", "etch"].map(model => [model, {
    label: model, model_version: "test-version", faults: [{ label: "정상", description: "변경 없음" }],
    params: [{ key: model === "ald" ? "pulse_a_s" : "bias_voltage_v", label: "검증 입력", default: 123, min: 0, max: 456, unit: "test-unit", group: "Recipe", description: "스키마 설명" }],
  }])) };
  const output = guide.guideMarkdown(schema);
  assert.ok(output.includes("기본값: 123 · 입력 범위: 0–456"));
  assert.ok(output.includes("단위: test-unit"));
  assert.ok(output.includes("모델 버전: test-version"));
  for (const section of guide.GUIDE_SECTIONS) {
    assert.ok(output.includes(`## ${section.title}`));
    for (const paragraph of section.paragraphs) assert.ok(document.includes(paragraph));
  }
  assert.ok(output.includes("트렌치 측벽·언더컷"));
  assert.ok(output.includes("실제 공정의 안전 범위"));
});
