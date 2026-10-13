"""Persist exactly the returned flow result for reproducible local studies."""
from pathlib import Path
import uuid
from flow_lab.model import simulate
from native_lab.storage import write_json

ROOT = Path(__file__).resolve().parents[1] / "outputs" / "flow_lab"


def run_request(payload, root=None):
    result = simulate(payload)
    result["run_id"] = uuid.uuid4().hex
    folder = (Path(root) if root else ROOT) / result["run_id"]
    folder.mkdir(parents=True, exist_ok=False)
    write_json(folder / "request.json", result["request"])
    write_json(folder / "result.json", result)
    return result
