"""Bounded, local-only subprocess jobs with durable inputs and raw outputs."""
from __future__ import annotations
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
import uuid
from native_lab.schema import validate
from native_lab.storage import read_json, write_json

ROOT = Path(__file__).resolve().parents[1]
TERMINAL = {"complete", "failed", "cancelled"}


class BusyError(RuntimeError):
    pass


class JobManager:
    def __init__(self, root=None, timeout_s=1800):
        self.root = Path(root) if root else ROOT / "outputs" / "native_lab"
        self.root.mkdir(parents=True, exist_ok=True)
        self.timeout_s = timeout_s
        self.lock = threading.Lock()
        self.active = None
        self.closed = threading.Event()
        self.monitor = threading.Thread(target=self._watch, daemon=True)
        self.monitor.start()

    def _watch(self):
        while not self.closed.wait(1):
            with self.lock:
                self._refresh()

    def directory(self, job_id):
        if not isinstance(job_id, str) or not re.fullmatch(r"[0-9a-f]{32}", job_id):
            raise ValueError("Invalid job id")
        directory = self.root / job_id
        if not directory.is_dir():
            raise FileNotFoundError("Run not found")
        return directory

    def _refresh(self):
        if not self.active:
            return
        job_id, process, log, started = self.active
        code = process.poll()
        if code is None and time.monotonic() - started > self.timeout_s:
            process.terminate()
            process.wait(timeout=10)
            code = process.returncode
            path = self.directory(job_id) / "status.json"
            state = read_json(path)
            state.update(state="failed", error=f"Native calculation exceeded the {self.timeout_s:g} s limit")
            write_json(path, state)
        if code is not None:
            log.close()
            path = self.directory(job_id) / "status.json"
            state = read_json(path)
            if state["state"] not in TERMINAL:
                state.update(state="failed", error=f"Native worker exited ({code}); inspect worker.log")
                write_json(path, state)
            self.active = None

    def submit(self, payload):
        request = validate(payload)
        with self.lock:
            self._refresh()
            if self.active:
                raise BusyError("이미 계산 중입니다. 완료를 기다리거나 해당 실행을 중단하세요.")
            job_id = uuid.uuid4().hex
            directory = self.root / job_id
            directory.mkdir()
            write_json(directory / "request.json", request)
            write_json(directory / "status.json", {"id": job_id, "model": request["model"],
                                                    "state": "queued", "progress": 0})
            log = (directory / "worker.log").open("w", encoding="utf-8")
            try:
                process = subprocess.Popen(
                    [sys.executable, "-m", "native_lab.worker", "--run-dir", str(directory)],
                    cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                    env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            except OSError:
                log.close()
                raise
            self.active = (job_id, process, log, time.monotonic())
            return read_json(directory / "status.json")

    def status(self, job_id):
        with self.lock:
            self._refresh()
            state = read_json(self.directory(job_id) / "status.json")
            # The worker writes its result before the native runtime finishes
            # shutting down. Do not expose completion while its log is open.
            if state["state"] == "complete" and self.active and self.active[0] == job_id:
                return {**state, "state": "running", "phase": "finalizing"}
            # After an unclean server restart, do not claim an old worker is live.
            if state["state"] not in TERMINAL and (not self.active or self.active[0] != job_id):
                state.update(state="failed", error="서버가 이 실행을 추적하지 않습니다. 저장된 로그를 확인하세요.")
            return state

    def result(self, job_id):
        if self.status(job_id)["state"] != "complete":
            raise ValueError("Run is not complete")
        return read_json(self.directory(job_id) / "result.json")

    def cancel(self, job_id):
        with self.lock:
            self._refresh()
            directory = self.directory(job_id)
            if not self.active or self.active[0] != job_id:
                return read_json(directory / "status.json")
            _, process, log, _ = self.active
            process.terminate()
            process.wait(timeout=10)
            log.close()
            state = read_json(directory / "status.json")
            state.update(state="cancelled")
            write_json(directory / "status.json", state)
            self.active = None
            return state

    def recent(self):
        # CLI exports may share the output root but are not web-owned UUID jobs.
        owned = (p for p in self.root.glob("*/status.json") if re.fullmatch(r"[0-9a-f]{32}", p.parent.name))
        paths = sorted(owned, key=lambda p: p.stat().st_mtime, reverse=True)[:20]
        return [{k: v for k, v in self.status(p.parent.name).items() if k not in ("last_frame", "initial_frame")} for p in paths]

    def close(self):
        self.closed.set()
        self.monitor.join(timeout=12)
        if self.active:
            self.cancel(self.active[0])
