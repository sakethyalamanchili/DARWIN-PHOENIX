"""
Experiment 3: Behavioral Fingerprinting (v2 - clean rewrite)
=============================================================
Runs DARWIN-PHOENIX in Condition C ONLY (164 HumanEval+ tasks).

Fingerprint metric: TF-IDF cosine distance between Round 1 code and Round N code.
Measures whether co-evolutionary pressure causes the generator to meaningfully
drift its coding strategy across rounds.

Fixes over v1:
  - Removed broken probe_executor_node (accessed wrong probe_tasks keys)
  - Uses code_versions from final state instead (no sandbox dependency)
  - _invoke_with_retry handles TimeoutError + OpenRouter RateLimitError
  - All LLM calls go through timed_completion (120s wall-clock timeout)
  - Resume via FINAL sentinel rows

Outputs:
  results/exp3_results.csv     -- per-task per-round cosine distance
  results/exp3_fingerprint.jsonl -- code versions for post-hoc analysis
"""

import argparse
import csv
import json
import logging
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_distances
except ImportError:
    print("FATAL: scikit-learn required. Run: pip install scikit-learn")
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).parent.parent))

from langgraph.graph import StateGraph, END
from nodes.initialize import initialize_node
from nodes.generator  import generator_node
from nodes.breaker    import breaker_node
from nodes.executor   import executor_node
from nodes.scorer     import scorer_node
from nodes.evolver    import evolver_node
from nodes.terminator import terminator_node
from state import DPState, AgentStrategy

# ── Constants ─────────────────────────────────────────────────────────────────
MAX_ROUNDS   = 4   # ceiling — fingerprint needs multi-round data
MIN_ROUNDS   = 2   # floor  — 2 rounds sufficient for drift signal
MAX_RETRIES  = 6
BASE_BACKOFF = 2.0
MAX_BACKOFF  = 120.0
TASK_LIMIT   = 50  # sample size (first N tasks); matches Exp 2 design
WORKERS      = 4   # parallel task workers

RESULTS_DIR  = Path(__file__).parent.parent / "results"
RESULTS_CSV  = RESULTS_DIR / "exp3_results.csv"
RESULTS_JSONL= RESULTS_DIR / "exp3_fingerprint.jsonl"
LOG_FILE     = RESULTS_DIR / "exp3_runner.log"

CSV_HEADERS = [
    "task_id", "condition", "round_num",
    "fingerprint_distance", "af_class", "wall_time_s", "timestamp",
]

# ── Logging ───────────────────────────────────────────────────────────────────
def _setup_logging() -> logging.Logger:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    fmt = "%(asctime)s  %(levelname)-8s  %(message)s"
    logging.basicConfig(
        level=logging.INFO, format=fmt,
        handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8")]
    )
    log = logging.getLogger("exp3")
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.WARNING)
    ch.setFormatter(logging.Formatter(fmt))
    log.addHandler(ch)
    return log

log = _setup_logging()

_csv_lock  = threading.Lock()
_jsonl_lock = threading.Lock()

# ── Resume helpers ────────────────────────────────────────────────────────────
def _load_completed() -> set[str]:
    done = set()
    if not RESULTS_CSV.exists():
        return done
    with RESULTS_CSV.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("round_num") == "FINAL" and row.get("fingerprint_distance") != "ERROR":
                done.add(row["task_id"])
    return done

def _ensure_outputs() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    if not RESULTS_CSV.exists():
        with RESULTS_CSV.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(CSV_HEADERS)
    if not RESULTS_JSONL.exists():
        RESULTS_JSONL.touch()

def _append_row(row: dict) -> None:
    with _csv_lock:
        with RESULTS_CSV.open("a", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=CSV_HEADERS).writerow(row)

def _append_jsonl(record: dict) -> None:
    with _jsonl_lock:
        with RESULTS_JSONL.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=True) + "\n")

# ── TF-IDF fingerprint distance ───────────────────────────────────────────────
def _code_distances(code_versions: list[str]) -> dict[int, float]:
    """
    Compute TF-IDF cosine distance between Round 1 code and Round N code.
    Returns {round_num: distance} where round_num starts at 1.
    Round 1 is always 0.0 by definition.
    Skips empty/whitespace versions (content-filter blanks).
    """
    if not code_versions:
        return {}

    # Filter empty/whitespace versions then cap at MAX_ROUNDS
    versions = [v for v in code_versions if v and v.strip()][:MAX_ROUNDS]

    if not versions:
        return {}

    if len(versions) == 1:
        return {1: 0.0}

    vec = TfidfVectorizer(analyzer="word", token_pattern=r"[A-Za-z_]\w*|\S")
    try:
        X = vec.fit_transform(versions)
    except ValueError:
        return {i + 1: 0.0 for i in range(len(versions))}

    distances = {}
    for i in range(len(versions)):
        dist = float(cosine_distances(X[0], X[i])[0][0])
        distances[i + 1] = dist

    return distances

# ── Graph (Condition C, no probe node) ────────────────────────────────────────
def _route(state: DPState) -> str:
    af_class      = state.get("af_class", "pending")
    current_round = state.get("current_round", 0)
    max_rounds    = state.get("max_rounds", MAX_ROUNDS)
    # Always run at least MIN_ROUNDS for meaningful drift data
    if current_round < MIN_ROUNDS:
        return "loop"
    # After min rounds: terminate on success/brittle; let degraded continue trying
    if af_class in ("antifragile", "correct", "brittle"):
        return "done"
    if current_round >= max_rounds:
        return "done"
    return "loop"

def _build_graph():
    b = StateGraph(DPState)
    b.add_node("initialize",  initialize_node)
    b.add_node("generator",   generator_node)
    b.add_node("breaker",     breaker_node)
    b.add_node("executor",    executor_node)
    b.add_node("scorer",      scorer_node)
    b.add_node("evolver",     evolver_node)
    b.add_node("terminator",  terminator_node)
    b.set_entry_point("initialize")
    b.add_edge("initialize", "generator")
    b.add_edge("generator",  "breaker")
    b.add_edge("breaker",    "executor")
    b.add_edge("executor",   "scorer")
    b.add_edge("scorer",     "evolver")
    b.add_edge("evolver",    "terminator")
    b.add_conditional_edges("terminator", _route, {"loop": "generator", "done": END})
    return b.compile()

_graph = _build_graph()

# ── Invocation with backoff ───────────────────────────────────────────────────
def _invoke_with_retry(state: DPState, label: str) -> dict:
    # Import both Groq and OpenAI rate-limit errors — works for either provider
    rate_limit_types = []
    try:
        from groq import RateLimitError as _GRL; rate_limit_types.append(_GRL)
    except ImportError:
        pass
    try:
        from openai import RateLimitError as _ORL; rate_limit_types.append(_ORL)
    except ImportError:
        pass
    rate_limit_tuple = tuple(rate_limit_types) if rate_limit_types else (Exception,)

    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return _graph.invoke(state)
        except rate_limit_tuple as exc:
            last_exc = exc
            if attempt == MAX_RETRIES:
                break
            sleep_s = min(BASE_BACKOFF * (2 ** (attempt - 1)) * random.uniform(0.75, 1.25), MAX_BACKOFF)
            log.warning("%s | RateLimitError attempt %d/%d — sleep %.1fs", label, attempt, MAX_RETRIES, sleep_s)
            time.sleep(sleep_s)
        except TimeoutError as exc:
            last_exc = exc
            if attempt == MAX_RETRIES:
                break
            sleep_s = min(BASE_BACKOFF * (2 ** (attempt - 1)) * random.uniform(0.75, 1.25), MAX_BACKOFF)
            log.warning("%s | TimeoutError attempt %d/%d — sleep %.1fs", label, attempt, MAX_RETRIES, sleep_s)
            time.sleep(sleep_s)
        except Exception as exc:
            log.error("%s | Graph error: %s", label, exc)
            raise

    log.error("%s | All %d retries exhausted", label, MAX_RETRIES)
    raise last_exc

# ── Task state factory ────────────────────────────────────────────────────────
def _make_state(task_id: str, max_rounds: int) -> DPState:
    return DPState(
        task_id=task_id,
        problem_spec="", function_signature="", canonical_tests=[],
        condition="C", max_rounds=max_rounds, current_round=0, failure_corpus=[],
        current_code="", code_versions=[],
        generator_strategy=AgentStrategy(round_num=0, prompt_prefix="", active_vectors=[], fingerprint=""),
        breaker_strategy=AgentStrategy(round_num=0, prompt_prefix="", active_vectors=[], fingerprint=""),
        breaker_strategy_frozen=False, adversarial_tests=[], test_results=[],
        combined_pass_at_k=0.0, adversarial_ratio=0.0, bug_rate=0.0,
        edge_coverage=0.0, vuln_count=0,
        af_score=0.0, af_delta=0.0, af_trajectory=[], consecutive_improvement=0,
        af_class="pending", termination_reason="",
        probe_tasks=[], probe_fingerprint=[],
        injection_active=False, injected_failure_type="none",
        recovery_successful=False, recovery_steps=0,
    )

# ── Runner ────────────────────────────────────────────────────────────────────
def _get_task_ids() -> list[str]:
    from evalplus.data import get_human_eval_plus
    all_ids = sorted(get_human_eval_plus().keys(), key=lambda k: int(k.split("/")[1]))
    return all_ids[:TASK_LIMIT]

def run(max_rounds: int = MAX_ROUNDS, dry_run: bool = False) -> None:
    task_ids  = _get_task_ids()
    completed = _load_completed()
    work      = [t for t in task_ids if t not in completed]

    print(f"\n{'='*65}")
    print(f"  DARWIN-PHOENIX  Experiment 3 — Behavioral Fingerprinting v2")
    print(f"{'='*65}")
    print(f"  Condition   : C (co-evolutionary)")
    print(f"  Metric      : TF-IDF cosine dist (Round1 vs RoundN code)")
    print(f"  Total tasks : {len(task_ids)}")
    print(f"  Completed   : {len(completed)}")
    print(f"  Remaining   : {len(work)}")
    print(f"{'='*65}\n")

    if dry_run:
        print(f"[dry-run] {len(work)} tasks remaining. Exiting.")
        return

    _ensure_outputs()

    def _run_task(args):
        i, task_id = args
        label = f"{task_id}|C"
        print(f"[{i}/{len(work)}] {label} START", flush=True)
        t_start = time.perf_counter()
        try:
            state = _make_state(task_id, max_rounds)
            final = _invoke_with_retry(state, label)
            wall_s = time.perf_counter() - t_start

            af_class      = final.get("af_class", "unknown")
            code_versions = final.get("code_versions", [])
            distances     = _code_distances(code_versions)
            ts            = datetime.now(timezone.utc).isoformat()

            for rn, dist in distances.items():
                _append_row({
                    "task_id": task_id, "condition": "C", "round_num": rn,
                    "fingerprint_distance": f"{dist:.6f}",
                    "af_class": af_class,
                    "wall_time_s": f"{wall_s:.2f}",
                    "timestamp": ts,
                })
            _append_row({
                "task_id": task_id, "condition": "C", "round_num": "FINAL",
                "fingerprint_distance": "", "af_class": af_class,
                "wall_time_s": f"{wall_s:.2f}", "timestamp": ts,
            })
            _append_jsonl({
                "task_id": task_id, "af_class": af_class,
                "termination_reason": final.get("termination_reason", ""),
                "code_versions": code_versions,
            })

            n_rounds = len(distances)
            max_dist = max(distances.values()) if distances else 0.0
            log.info("%-20s -> %s  rounds=%d  max_dist=%.4f  %.1fs",
                     task_id, af_class, n_rounds, max_dist, wall_s)
            print(f"[{i}/{len(work)}] {label} -> {af_class}  rounds={n_rounds}  max_dist={max_dist:.4f}  {wall_s:.1f}s", flush=True)

        except Exception as exc:
            wall_s = time.perf_counter() - t_start
            log.error("%s | FAILED: %s", label, exc)
            _append_row({
                "task_id": task_id, "condition": "C", "round_num": "FINAL",
                "fingerprint_distance": "ERROR", "af_class": "ERROR",
                "wall_time_s": f"{wall_s:.2f}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            print(f"[{i}/{len(work)}] {label} -> ERROR: {exc}", flush=True)

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(_run_task, (i, tid)): tid for i, tid in enumerate(work, 1)}
        for fut in as_completed(futures):
            fut.result()  # re-raise any unhandled exception

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Exp 3: Behavioral Fingerprinting")
    parser.add_argument("--max-rounds", type=int, default=MAX_ROUNDS)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--workers", type=int, default=WORKERS)
    args = parser.parse_args()
    WORKERS = args.workers
    run(max_rounds=args.max_rounds, dry_run=args.dry_run)
