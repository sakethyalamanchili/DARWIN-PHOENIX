"""
Watchdog for Exp 3 runner.
Monitors exp3_fingerprint.py and auto-restarts if it dies.
Checks every 60 seconds. Stops when all 164 tasks have FINAL rows.

Usage:
    python watchdog_exp3.py
"""
import subprocess
import sys
import time
import csv
from pathlib import Path

RESULTS_FILE   = Path(__file__).parent / "results" / "exp3_results.csv"
_VENV_PY       = Path(__file__).parent / ".venv" / "Scripts" / "python.exe"
_PYTHON        = str(_VENV_PY) if _VENV_PY.exists() else sys.executable
RUNNER_CMD     = [
    _PYTHON,
    str(Path(__file__).parent / "experiments" / "exp3_fingerprint.py"),
    "--max-rounds", "10",
]
TARGET_TASKS   = 164
CHECK_INTERVAL = 60

def _count_completed() -> int:
    if not RESULTS_FILE.exists():
        return 0
    with RESULTS_FILE.open(newline="", encoding="utf-8") as f:
        return sum(1 for row in csv.DictReader(f) if row.get("round_num") == "FINAL"
                   and row.get("fingerprint_distance") != "ERROR")

def _runner_alive(proc) -> bool:
    return proc is not None and proc.poll() is None

def _log(msg: str):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[watchdog {ts}] {msg}", flush=True)

def main():
    _log(f"Watchdog started. Target: {TARGET_TASKS} completed tasks.")
    proc = None

    while True:
        done = _count_completed()
        _log(f"Progress: {done}/{TARGET_TASKS} tasks complete")

        if done >= TARGET_TASKS:
            _log("Done — all tasks complete. Watchdog exiting.")
            if _runner_alive(proc):
                proc.terminate()
            break

        if not _runner_alive(proc):
            if proc is not None:
                _log(f"Runner exited (code={proc.returncode}). Restarting...")
            else:
                _log("Starting runner...")
            proc = subprocess.Popen(RUNNER_CMD)
            _log(f"Runner started (PID={proc.pid})")

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
