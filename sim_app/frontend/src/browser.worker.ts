import serviceSource from "../../service.py?raw";
import aldSource from "../../models/ald.py?raw";
import etchSource from "../../models/etch.py?raw";
import packageSource from "../../__init__.py?raw";
import modelsSource from "../../models/__init__.py?raw";

// Pinned official distribution: Python 3.14.2, NumPy 2.4.6, SciPy 1.18.0.
const INDEX_URL = "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/";
interface PythonRuntime {
  FS: {
    mkdirTree(path: string): void;
    writeFile(path: string, data: string): void;
  };
  globals: { set(key: string, value: string): void };
  loadPackage(packages: string[]): Promise<void>;
  runPythonAsync(code: string): Promise<unknown>;
}

async function initialize(): Promise<PythonRuntime> {
  const moduleUrl = `${INDEX_URL}pyodide.mjs`;
  const { loadPyodide } = await import(/* @vite-ignore */ moduleUrl);
  const python: PythonRuntime = await loadPyodide({ indexURL: INDEX_URL });
  await python.loadPackage(["numpy", "scipy"]);
  const root = "/home/pyodide/sim_app";
  python.FS.mkdirTree(`${root}/models`);
  for (const [path, source] of Object.entries({
    "__init__.py": packageSource,
    "service.py": serviceSource,
    "models/__init__.py": modelsSource,
    "models/ald.py": aldSource,
    "models/etch.py": etchSource,
  }))
    python.FS.writeFile(`${root}/${path}`, source);
  await python.runPythonAsync(`
import json, sys, numpy, scipy
from sim_app.service import schema, simulate_request, sweep_request
_operations = {"schema": lambda payload: schema(), "simulate": simulate_request, "sweep": sweep_request}
_environment = {"engine": "Pyodide", "pyodide": "314.0.7", "python": sys.version.split()[0], "numpy": numpy.__version__, "scipy": scipy.__version__}
def _process_studio_request(operation, payload_json):
    result = _operations[operation](json.loads(payload_json))
    result["execution_environment"] = _environment
    return json.dumps(result, ensure_ascii=False, allow_nan=False)
`);
  return python;
}

let runtime: Promise<PythonRuntime> | undefined;
let queue = Promise.resolve();
self.onmessage = (
  event: MessageEvent<{ id: number; operation: string; payload?: unknown }>,
) => {
  const { id, operation, payload } = event.data;
  // Serialize access to Python globals even when StrictMode starts two requests.
  queue = queue.then(async () => {
    try {
      if (!["schema", "simulate", "sweep"].includes(operation))
        throw new Error("Unknown operation");
      runtime ??= initialize().catch((error) => {
        runtime = undefined;
        throw error;
      });
      const python = await runtime;
      python.globals.set("_request_operation", operation);
      python.globals.set("_request_payload", JSON.stringify(payload ?? null));
      const json = await python.runPythonAsync(
        "_process_studio_request(_request_operation, _request_payload)",
      );
      if (typeof json !== "string") throw new Error("Invalid Python response");
      self.postMessage({ id, result: JSON.parse(json) });
    } catch (error) {
      self.postMessage({
        id,
        error:
          error instanceof Error
            ? error.message
            : "브라우저 Python 계산에 실패했습니다.",
      });
    }
  });
};
