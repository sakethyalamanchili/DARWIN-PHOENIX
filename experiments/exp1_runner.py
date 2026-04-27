"""
Experiment 1: Baseline Antifragility
=====================================
Runs all 164 HumanEval+ problems × 4 conditions (A, B, C, D).

Records per-run:
  - af_score            : composite antifragility score
  - combined_pass_at_k  : pass@k across all tests
  - af_class            : brittle / correct / robust / antifragile / degraded
  - rounds_taken        : current_round in final state

Output  : results/exp1_results.csv   (incremental write — safe to Ctrl-C and resume)
Log     : results/exp1_runner.log

Features
--------
- Resume support : already-completed (task_id, condition) pairs are skipped on restart.
- Progress bar   : tqdm outer bar (tasks) + inner bar (conditions).
- Retry logic    : exponential backoff on Groq RateLimitError / HTTP 429.
                   Base 2 s → doubles each attempt, capped at 120 s, max 6 retries.

Usage
-----
    python experiments/exp1_runner.py [--max-rounds N] [--dry-run]

    --max-rounds N   Override MAX_ROUNDS (default 10). Useful for quick test: 2.
    --dry-run        Print the task list only; do not call the graph.
"""

import argparse
import csv
import logging
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# ── Optional tqdm with graceful fallback ──────────────────────────────────────
try:
    from tqdm import tqdm as _tqdm
    def _make_bar(iterable, **kwargs):
        return _tqdm(iterable, **kwargs)
except ImportError:
    class _FallbackBar:
        """Minimal no-op progress bar when tqdm is not installed."""
        def __init__(self, iterable, total=None, desc="", leave=True, **_):
            self._it   = iter(iterable)
            self._n    = 0
            self._total = total or "?"
            self._desc  = desc
        def __iter__(self):
            return self
        def __next__(self):
            val = next(self._it)
            self._n += 1
            print(f"\r{self._desc}: {self._n}/{self._total}", end="", flush=True)
            return val
        def __enter__(self):  return self
        def __exit__(self, *_): print()
        def set_postfix_str(self, s="", **__): pass
        def close(self): pass
    def _make_bar(iterable, **kwargs):
        return _FallbackBar(iterable, **kwargs)

# ── Project imports ───────────────────────────────────────────────────────────
from groq import RateLimitError as _GroqRateLimitError

from graph import darwin_phoenix
from state import DPState, AgentStrategy

# ── Constants ─────────────────────────────────────────────────────────────────
CONDITIONS   = ["A", "B", "C", "D"]
MAX_ROUNDS   = 10                     # overridable via --max-rounds
RESULTS_DIR  = Path(__file__).parent.parent / "results"
RESULTS_FILE = RESULTS_DIR / "exp1_results.csv"
LOG_FILE     = RESULTS_DIR / "exp1_runner.log"

# Retry — exponential backoff on rate-limit errors
MAX_RETRIES  = 6
BASE_BACKOFF = 2.0    # seconds
MAX_BACKOFF  = 120.0  # cap at 2 minutes

CSV_HEADERS = [
    "task_id",
    "condition",
    "af_class",
    "af_score",
    "combined_pass_at_k",
    "adversarial_ratio",
    "rounds_taken",
    "termination_reason",
    "wall_time_s",
    "timestamp",
]


# ── Logging ───────────────────────────────────────────────────────────────────
def _setup_logging() -> logging.Logger:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    fmt = "%(asctime)s  %(levelname)-8s  %(message)s"
    handlers: list[logging.Handler] = [
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ]
    logging.basicConfig(level=logging.INFO, format=fmt, handlers=handlers)
    log = logging.getLogger("exp1")
    # Also echo INFO+ to stdout without duplicating file handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.WARNING)   # only warnings+ to avoid cluttering tqdm
    console.setFormatter(logging.Formatter(fmt))
    log.addHandler(console)
    return log


log = _setup_logging()


# ── Resume support ────────────────────────────────────────────────────────────
def _load_completed(retry_errors: bool = False) -> set[tuple[str, str]]:
    """Return set of (task_id, condition) pairs already written to the CSV.
    If retry_errors=True, ERROR rows are excluded so they get re-run."""
    done: set[tuple[str, str]] = set()
    if not RESULTS_FILE.exists():
        return done
    with RESULTS_FILE.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if retry_errors and row.get("af_class") == "ERROR":
                continue
            done.add((row["task_id"], row["condition"]))
    return done


def _strip_error_rows() -> int:
    """Rewrite CSV keeping only non-ERROR rows. Returns count removed."""
    if not RESULTS_FILE.exists():
        return 0
    with RESULTS_FILE.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    good = [r for r in rows if r.get("af_class") != "ERROR"]
    removed = len(rows) - len(good)
    with RESULTS_FILE.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        w.writeheader()
        w.writerows(good)
    return removed


def _ensure_csv_header() -> None:
    """Write CSV header if the file doesn't exist yet."""
    if not RESULTS_FILE.exists():
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        with RESULTS_FILE.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(CSV_HEADERS)


def _append_row(row: dict) -> None:
    """Append one result row to the CSV (incremental — safe across crashes)."""
    with RESULTS_FILE.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        w.writerow(row)


# ── Initial state builder ─────────────────────────────────────────────────────
def _make_initial_state(task_id: str, condition: str, max_rounds: int) -> DPState:
    """Build a fully-initialized DPState for graph.invoke()."""
    return DPState(
        # Task (filled by initialize_node — provide correct task_id & condition)
        task_id=task_id,
        problem_spec="",
        function_signature="",
        canonical_tests=[],

        # Experiment config
        condition=condition,
        max_rounds=max_rounds,
        current_round=0,
        failure_corpus=[],           # initialize_node loads this for Cond B

        # Agent states
        current_code="",
        code_versions=[],
        generator_strategy=AgentStrategy(
            round_num=0,
            prompt_prefix="You are DARWIN, a Python code generation agent.",
            active_vectors=[],
            fingerprint="",
        ),
        breaker_strategy=AgentStrategy(
            round_num=0,
            prompt_prefix="You are PHOENIX, an adversarial code tester.",
            active_vectors=[
                "integer_overflow", "empty_input", "type_confusion",
                "boundary_values", "unicode_injection", "deep_nesting",
            ],
            fingerprint="",
        ),
        breaker_strategy_frozen=(condition == "D"),

        # Tests & results
        adversarial_tests=[],
        test_results=[],
        combined_pass_at_k=0.0,
        adversarial_ratio=0.0,
        bug_rate=0.0,
        edge_coverage=0.0,
        vuln_count=0,

        # Antifragility
        af_score=0.0,
        af_delta=0.0,
        af_trajectory=[],
        consecutive_improvement=0,
        af_class="pending",
        termination_reason="",

        # Fingerprinting (Exp 3 — initialized but not used in Exp 1)
        probe_tasks=[],              # initialize_node populates this
        probe_fingerprint=[],

        # Fault injection (Exp 2 — disabled)
        injection_active=False,
        injected_failure_type="none",
        recovery_successful=False,
        recovery_steps=0,
    )


# ── Exponential backoff retry ─────────────────────────────────────────────────
def _invoke_with_retry(
    state: DPState,
    task_label: str,
) -> dict:
    """
    Call darwin_phoenix.invoke(state) with exponential backoff on rate-limit errors.

    Retries up to MAX_RETRIES times.  Raises the final error if all retries fail.
    Adds ±25 % jitter to each sleep to stagger concurrent processes.
    """
    last_exc: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return darwin_phoenix.invoke(state)

        except _GroqRateLimitError as exc:
            last_exc = exc
            if attempt == MAX_RETRIES:
                break
            raw_sleep = BASE_BACKOFF * (2 ** (attempt - 1))
            jitter     = random.uniform(0.75, 1.25)
            sleep_s    = min(raw_sleep * jitter, MAX_BACKOFF)
            log.warning(
                "%s | RateLimitError (attempt %d/%d) — sleeping %.1f s",
                task_label, attempt, MAX_RETRIES, sleep_s,
            )
            time.sleep(sleep_s)

        except (TimeoutError, Exception) as exc:
            # Retry on timeout; re-raise immediately on other errors
            exc_name = type(exc).__name__
            if "Timeout" in exc_name or "timeout" in str(exc).lower():
                last_exc = exc
                if attempt == MAX_RETRIES:
                    break
                sleep_s = min(BASE_BACKOFF * (2 ** (attempt - 1)) * random.uniform(0.75, 1.25), MAX_BACKOFF)
                log.warning("%s | Timeout (attempt %d/%d) — retrying in %.1f s", task_label, attempt, MAX_RETRIES, sleep_s)
                time.sleep(sleep_s)
            else:
                log.error("%s | Unexpected error: %s", task_label, exc)
                raise

    log.error("%s | All %d retries exhausted. Last error: %s", task_label, MAX_RETRIES, last_exc)
    raise last_exc  # type: ignore[misc]


# ── Task list ─────────────────────────────────────────────────────────────────
def _get_task_ids() -> list[str]:
    """Return all 164 HumanEval+ task IDs sorted numerically (HumanEval/0 first, HumanEval/163 last)."""
    from evalplus.data import get_human_eval_plus
    return sorted(get_human_eval_plus().keys(), key=lambda k: int(k.split("/")[1]))


# ── Core runner ───────────────────────────────────────────────────────────────
def run(max_rounds: int = MAX_ROUNDS, dry_run: bool = False, retry_errors: bool = False) -> None:
    if retry_errors:
        removed = _strip_error_rows()
        print(f"  [--retry-errors] Stripped {removed} ERROR rows from CSV — will re-run them.")
    task_ids  = _get_task_ids()
    completed = _load_completed(retry_errors=retry_errors)

    total_runs     = len(task_ids) * len(CONDITIONS)
    completed_runs = sum(
        1 for tid in task_ids for cond in CONDITIONS
        if (tid, cond) in completed
    )
    remaining_runs = total_runs - completed_runs

    print(
        f"\n{'='*65}\n"
        f"  DARWIN-PHOENIX  Experiment 1 — Baseline Antifragility\n"
        f"{'='*65}\n"
        f"  Tasks      : {len(task_ids)}  (HumanEval/0 – HumanEval/{len(task_ids)-1})\n"
        f"  Conditions : {CONDITIONS}\n"
        f"  Max rounds : {max_rounds}\n"
        f"  Total runs : {total_runs}  |  Already done: {completed_runs}  |  Remaining: {remaining_runs}\n"
        f"  Output     : {RESULTS_FILE}\n"
        f"  Log        : {LOG_FILE}\n"
        f"{'='*65}\n"
    )

    if dry_run:
        print("[dry-run] Task list:")
        for tid in task_ids:
            for cond in CONDITIONS:
                status = "DONE" if (tid, cond) in completed else "TODO"
                print(f"  {tid:<20} cond={cond}  {status}")
        return

    _ensure_csv_header()

    # Flat work list — only remaining items
    work = [
        (tid, cond)
        for tid in task_ids
        for cond in CONDITIONS
        if (tid, cond) not in completed
    ]

    errors: list[str] = []

    with _make_bar(work, total=len(work), desc="Exp 1", unit="run", leave=True) as pbar:
        for task_id, condition in pbar:
            label = f"{task_id}|{condition}"
            pbar.set_postfix_str(label)

            state   = _make_initial_state(task_id, condition, max_rounds)
            t_start = time.perf_counter()

            try:
                final   = _invoke_with_retry(state, label)
                wall_s  = time.perf_counter() - t_start

                af_class    = final.get("af_class",           "unknown")
                af_score    = final.get("af_score",           0.0)
                pass_at_k   = final.get("combined_pass_at_k", 0.0)
                adv_ratio   = final.get("adversarial_ratio",  0.0)
                rounds      = final.get("current_round",      0)
                reason      = final.get("termination_reason", "")

                row = {
                    "task_id":            task_id,
                    "condition":          condition,
                    "af_class":           af_class,
                    "af_score":           f"{af_score:.6f}",
                    "combined_pass_at_k": f"{pass_at_k:.6f}",
                    "adversarial_ratio":  f"{adv_ratio:.6f}",
                    "rounds_taken":       rounds,
                    "termination_reason": reason,
                    "wall_time_s":        f"{wall_s:.2f}",
                    "timestamp":          datetime.now(timezone.utc).isoformat(),
                }
                _append_row(row)
                log.info(
                    "%-22s cond=%s  af_class=%-12s  af_score=%.4f  rounds=%d  (%.1fs)",
                    task_id, condition, af_class, af_score, rounds, wall_s,
                )

            except Exception as exc:
                wall_s = time.perf_counter() - t_start
                err_msg = str(exc)[:120]
                log.error("%-22s cond=%s  FAILED: %s", task_id, condition, err_msg)
                errors.append(f"{label}: {err_msg}")

                # Write an ERROR sentinel row so we can identify failures in the CSV
                row = {
                    "task_id":            task_id,
                    "condition":          condition,
                    "af_class":           "ERROR",
                    "af_score":           "",
                    "combined_pass_at_k": "",
                    "adversarial_ratio":  "",
                    "rounds_taken":       "",
                    "termination_reason": err_msg,
                    "wall_time_s":        f"{wall_s:.2f}",
                    "timestamp":          datetime.now(timezone.utc).isoformat(),
                }
                _append_row(row)

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'='*65}")
    print(f"  Exp 1 complete. Results → {RESULTS_FILE}")

    # Re-read the full CSV for summary stats
    results: list[dict] = []
    with RESULTS_FILE.open(newline="", encoding="utf-8") as f:
        results = list(csv.DictReader(f))

    classes = [r["af_class"] for r in results if r["af_class"] not in ("ERROR", "unknown", "")]
    dist    = {c: classes.count(c) for c in sorted(set(classes))}
    print(f"  Total rows     : {len(results)}")
    print(f"  af_class dist  : {dist}")
    print(f"  Errors         : {len(errors)}")
    if errors:
        print("\n  [!] Failed runs:")
        for e in errors:
            print(f"      {e}")
    print(f"{'='*65}\n")


# ── CLI ───────────────────────────────────────────────────────────────────────
def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Experiment 1: Baseline Antifragility — 164 tasks × 4 conditions",
    )
    p.add_argument(
        "--max-rounds", type=int, default=MAX_ROUNDS,
        help=f"Max rounds per run (default: {MAX_ROUNDS}). Use 2 for a quick smoke check.",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Print the work list and exit without running the graph.",
    )
    p.add_argument(
        "--retry-errors", action="store_true",
        help="Strip ERROR rows from CSV and re-run those tasks.",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run(max_rounds=args.max_rounds, dry_run=args.dry_run, retry_errors=args.retry_errors)
