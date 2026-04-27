"""
Watchdog for Exp 2 runner.
Monitors the exp2_chaos.py process and auto-restarts if it dies.
Checks every 60 seconds. Stops when exp2_results.csv has 300 rows (all done).

Usage:
    python watchdog_exp2.py
"""
import subprocess
import sys
import time
import csv
from pathlib import Path

RESULTS_FILE  = Path(__file__).parent / "results" / "exp2_results.csv"
RUNNER_CMD    = [
    sys.executable,
    str(Path(__file__).parent / "experiments" / "exp2_chaos.py"),
    "--max-tasks", "50",
    "--max-rounds", "3",
]
TARGET_ROWS   = 300   # 50 tasks × 2 conditions × 3 fault types
CHECK_INTERVAL = 60   # seconds between checks

def _count_data_rows() -> int:
    if not RESULTS_FILE.exists():
        return 0
    with RESULTS_FILE.open(newline="", encoding="utf-8") as f:
        return sum(1 for _ in csv.DictReader(f))

def _runner_alive(proc) -> bool:
    return proc is not None and proc.poll() is None

def _log(msg: str):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[watchdog {ts}] {msg}", flush=True)

def main():
    _log("Watchdog started. Target: 300 rows in exp2_results.csv.")
    proc = None

    while True:
        rows = _count_data_rows()
        _log(f"Progress: {rows}/{TARGET_ROWS} rows")

        if rows >= TARGET_ROWS:
            _log("Done — 300 rows written. Watchdog exiting.")
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
