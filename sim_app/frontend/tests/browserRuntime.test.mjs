import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import ts from "typescript";

const sourceUrl = new URL("../src/browserRuntime.ts", import.meta.url);
const source = (await readFile(sourceUrl, "utf8")).replaceAll(
  "import.meta.url",
  JSON.stringify(sourceUrl.href),
);
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    target: ts.ScriptTarget.ES2022,
    module: ts.ModuleKind.ESNext,
  },
}).outputText;
const instances = [];
class FakeWorker {
  messages = [];
  terminated = false;
  constructor() {
    instances.push(this);
  }
  postMessage(message) {
    this.messages.push(message);
  }
  terminate() {
    this.terminated = true;
  }
  reply(index, response) {
    this.onmessage({ data: { id: this.messages[index].id, ...response } });
  }
}
globalThis.Worker = FakeWorker;
const { browserRequest } = await import(
  `data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`
);

test("concurrent worker requests retain their own response identity", async () => {
  const schema = browserRequest("schema");
  const run = browserRequest("simulate", { model: "etch" });
  const worker = instances.at(-1);
  assert.equal(instances.length, 1);
  worker.reply(1, { result: { run_id: "run" } });
  worker.reply(0, { result: { models: {} } });
  assert.deepEqual(await schema, { models: {} });
  assert.deepEqual(await run, { run_id: "run" });
});

test("Python validation errors reject only the matching request", async () => {
  const worker = instances.at(-1);
  const offset = worker.messages.length;
  const bad = browserRequest("simulate", { model: "unknown" });
  const good = browserRequest("schema");
  const rejection = assert.rejects(bad, /invalid model/);
  worker.reply(offset, { error: "invalid model" });
  worker.reply(offset + 1, { result: { models: {} } });
  await rejection;
  assert.deepEqual(await good, { models: {} });
});

test("a failed worker rejects queued calls and the next call can initialize again", async () => {
  const worker = instances.at(-1);
  const first = browserRequest("schema");
  const second = browserRequest("simulate", { model: "ald" });
  const rejections = Promise.all([
    assert.rejects(first, /계산 엔진/),
    assert.rejects(second, /계산 엔진/),
  ]);
  worker.onerror();
  await rejections;
  assert.equal(worker.terminated, true);
  const retry = browserRequest("schema");
  const replacement = instances.at(-1);
  assert.notEqual(worker, replacement);
  replacement.reply(0, { result: { models: {} } });
  assert.deepEqual(await retry, { models: {} });
});
