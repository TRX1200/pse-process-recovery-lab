"""One job per interpreter isolates native dimensions, units and random state."""
from __future__ import annotations
import argparse
import hashlib
import time
import traceback
from pathlib import Path
from native_lab.storage import read_json, write_json


def run(run_dir):
    directory = Path(run_dir).resolve()
    request = read_json(directory / "request.json")
    started = time.time()
    status = {"id": directory.name, "state": "running", "progress": 0,
              "started_at": started, "model": request["model"]}
    write_json(directory / "status.json", status)
    try:
        from native_lab.engine import simulate

        def progress(fraction, frame):
            if fraction == 0:
                status["initial_frame"] = frame
            status.update(progress=fraction, last_frame=frame, elapsed_s=time.time()-started)
            write_json(directory / "status.json", status)

        result = simulate(request, directory, progress)
        write_json(directory / "result.json", result)
        digest = hashlib.sha256((directory / "result.json").read_bytes()).hexdigest()
        status.pop("last_frame", None)
        status.pop("initial_frame", None)
        status.update(state="complete", progress=1, elapsed_s=time.time()-started,
                      result_sha256=digest, run_hash=result["run_hash"])
        write_json(directory / "status.json", status)
    except Exception as exc:
        traceback.print_exc()
        status.pop("last_frame", None)
        status.pop("initial_frame", None)
        status.update(state="failed", error=f"{type(exc).__name__}: {exc}", elapsed_s=time.time()-started)
        write_json(directory / "status.json", status)
        return 1
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    raise SystemExit(run(parser.parse_args().run_dir))
