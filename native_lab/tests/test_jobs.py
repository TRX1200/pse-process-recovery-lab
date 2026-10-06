import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock
from native_lab.jobs import JobManager, BusyError
from native_lab.storage import read_json


class JobTests(unittest.TestCase):
    def test_completion_waits_for_worker_exit(self):
        with tempfile.TemporaryDirectory() as temp:
            manager=JobManager(Path(temp))
            job_id='a'*32
            directory=Path(temp)/job_id
            directory.mkdir()
            (directory/'status.json').write_text('{"state":"complete","progress":1}')
            process,log=Mock(),Mock()
            process.poll.return_value=None
            manager.active=(job_id,process,log,time.monotonic())
            try:
                self.assertEqual(manager.status(job_id)['state'],'running')
                process.poll.return_value=0
                self.assertEqual(manager.status(job_id)['state'],'complete')
                log.close.assert_called_once()
            finally:
                process.poll.return_value=0
                manager.close()

    def test_timeout_without_browser_polling(self):
        with tempfile.TemporaryDirectory() as temp:
            manager = JobManager(Path(temp), timeout_s=.05)
            try:
                job = manager.submit({"model": "etch", "params": {"duration_s": 30}})
                # Read disk directly so this test does not trigger status/_refresh.
                for _ in range(60):
                    state = read_json(Path(temp) / job["id"] / "status.json")
                    if state["state"] == "failed":
                        break
                    time.sleep(.1)
                self.assertEqual(state["state"], "failed", state)
                self.assertIn("limit", state["error"])
            finally:
                manager.close()

    def test_busy_cancel_and_input_retention(self):
        with tempfile.TemporaryDirectory() as temp:
            manager = JobManager(Path(temp))
            try:
                job = manager.submit({"model": "etch", "params": {"duration_s": 30}})
                with self.assertRaises(BusyError):
                    manager.submit({"model": "ald"})
                manager.cancel(job["id"])
                self.assertEqual(manager.status(job["id"])["state"], "cancelled")
                self.assertEqual(read_json(Path(temp) / job["id"] / "request.json")["params"]["duration_s"], 30)
                with self.assertRaises(ValueError):
                    manager.directory("../../other")
            finally:
                manager.close()

    def test_job_result_and_worker_files(self):
        with tempfile.TemporaryDirectory() as temp:
            manager = JobManager(Path(temp))
            try:
                job = manager.submit({"model": "ald", "params": {"cycles": 1, "pulse_s": 0}})
                for _ in range(100):
                    state = manager.status(job["id"])
                    if state["state"] not in ("running", "queued"):
                        break
                    time.sleep(.05)
                self.assertEqual(state["state"], "complete", state)
                result = manager.result(job["id"])
                self.assertEqual(result["frames"][0]["layers"], result["frames"][-1]["layers"])
                directory = Path(temp) / job["id"]
                self.assertTrue(list(directory.glob("final_surface*")))
                self.assertTrue(list(directory.glob("final_levelset*")))
                self.assertTrue((directory / "worker.log").is_file())
                manual = Path(temp) / "manual-etch"
                manual.mkdir()
                (manual / "status.json").write_text('{"state":"complete"}')
                self.assertEqual([r["id"] for r in manager.recent()], [job["id"]])
            finally:
                manager.close()


if __name__ == "__main__":
    unittest.main()
