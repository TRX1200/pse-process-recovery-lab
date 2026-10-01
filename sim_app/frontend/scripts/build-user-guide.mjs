import { readFile, writeFile } from "node:fs/promises";
import { execFileSync } from "node:child_process";
import ts from "typescript";

// Generate the same complete manual offered in the UI, using the real Python schema.
// Override PYTHON when the project's Python environment is not on PATH.
const schema = JSON.parse(execFileSync(process.env.PYTHON || "python", ["-c",
  "import json; from sim_app.service import schema; print(json.dumps(schema(), ensure_ascii=True))"],
  { cwd: new URL("../../../", import.meta.url), encoding: "utf8" }));
const source = await readFile(new URL("../src/userGuide.ts", import.meta.url), "utf8");
const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
const { guideMarkdown } = await import(`data:text/javascript;base64,${Buffer.from(js).toString("base64")}`);
await writeFile(new URL("../../../docs/SIMULATOR_USER_GUIDE_KR.md", import.meta.url), guideMarkdown(schema));
console.log(`Wrote manual for ${Object.values(schema.models).reduce((n, m) => n + m.params.length, 0)} parameters.`);
