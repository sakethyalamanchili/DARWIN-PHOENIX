"""
Experiment 2: Fault Injection Stress Test (Chaos Engineering)
==============================================================
Applies three chaos failure types to Conditions A and C to measure
recovery ability of the DARWIN-PHOENIX co-evolution loop.

Failure types
-------------
hallucination : Injects 'import nonexistent_chaos_lib_xyz' into generated code
                on Round 0.  ModuleNotFoundError destroys code execution.
                Recovery = generator produces clean importable code on a later round.

ctx_overflow  : Pads problem_spec with ~5000 tokens of irrelevant Python noise
                before the generator sees it. Tests whether DARWIN can extract
                the problem from a bloated, noisy context.

timeout       : Injects 'time.sleep(6)' into the first function body on Round 0.
                Docker sandbox hard-kills at 5 s → all tests return TIMEOUT_OR_CRASH.
                Recovery = generator produces a non-sleeping function.

Chaos graph vs. main graph
---------------------------
The chaos graph differs from the main graph in two ways:
  1. route_chaos: "degraded" is NOT terminal — the loop continues so the system
     can attempt recovery. Only ("correct", "antifragile", "brittle") exit.
  2. Two extra nodes sit in the pipeline:
       initialize → [inject_context] → generator → [inject_code] → breaker → ...
     inject_context: pads problem_spec for ctx_overflow (before generator)
     inject_code: corrupts current_code for hallucination/timeout (after generator)
     Both nodes are no-ops after Round 0 — injection is single-shot.

Recovery metrics (derived from final state)
--------------------------------------------
recovery_successful : True if final af_class in ("correct", "antifragile")
recovery_steps      : final current_round (total rounds incl. injection round = 0)
                      e.g. recovery_steps=2 means clean code appeared in Round 2.

Output: results/exp2_results.csv  (incremental write, resumable)
Log:    results/exp2_runner.log

Usage
-----
    python experiments/exp2_chaos.py [--max-rounds N] [--dry-run]

    --max-rounds N   Rounds per chaos run (default: 5). Recovery needs room to happen.
    --dry-run        Print work list without running the graph.
"""

import argparse
import csv
import logging
import os
import re
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# ── Optional tqdm with graceful fallback (same pattern as exp1) ───────────────
try:
    from tqdm import tqdm as _tqdm
    def _make_bar(iterable, **kwargs):
        return _tqdm(iterable, **kwargs)
except ImportError:
    class _FallbackBar:
        def __init__(self, iterable, total=None, desc="", **_):
            self._it = iter(iterable); self._n = 0
            self._total = total or "?"; self._desc = desc
        def __iter__(self): return self
        def __next__(self):
            val = next(self._it); self._n += 1
            print(f"\r{self._desc}: {self._n}/{self._total}", end="", flush=True)
            return val
        def __enter__(self): return self
        def __exit__(self, *_): print()
        def set_postfix_str(self, s="", **__): pass
        def close(self): pass
    def _make_bar(iterable, **kwargs):
        return _FallbackBar(iterable, **kwargs)

# ── Project imports ───────────────────────────────────────────────────────────
from groq import RateLimitError as _GroqRateLimitError
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
CONDITIONS   = ["A", "C"]          # Exp 2: Conditions A and C only
FAILURE_TYPES = ["hallucination", "ctx_overflow", "timeout"]
MAX_ROUNDS   = 5                   # default: 5 gives enough room for recovery
RESULTS_DIR  = Path(__file__).parent.parent / "results"
RESULTS_FILE = RESULTS_DIR / "exp2_results.csv"
LOG_FILE     = RESULTS_DIR / "exp2_runner.log"

MAX_RETRIES  = 6
BASE_BACKOFF = 2.0
MAX_BACKOFF  = 120.0

CSV_HEADERS = [
    "task_id",
    "condition",
    "injected_failure_type",
    "af_class",
    "af_score",
    "combined_pass_at_k",
    "recovery_successful",
    "recovery_steps",
    "termination_reason",
    "wall_time_s",
    "timestamp",
]

# ── ctx_overflow noise block (~5000 tokens @ ~4 chars/token) ─────────────────
# 400 lines × 50 chars ≈ 20 000 chars ≈ 5 000 tokens
_CTX_NOISE_LINES = [
    f"# legacy_util_{i:04d} = lambda x, y=None: x  # deprecated, do not use"
    for i in range(400)
]
_CTX_OVERFLOW_PREFIX = (
    "# === CONTEXT DUMP: Legacy utility module (ignore — focus on the problem below) ===\n"
    + "\n".join(_CTX_NOISE_LINES)
    + "\n# === END CONTEXT DUMP ===\n\n"
)

# ── Logging ───────────────────────────────────────────────────────────────────
def _setup_logging() -> logging.Logger:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    fmt = "%(asctime)s  %(levelname)-8s  %(message)s"
    logging.basicConfig(
        level=logging.INFO, format=fmt,
        handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8")],
    )
    log = logging.getLogger("exp2")
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.WARNING)
    console.setFormatter(logging.Formatter(fmt))
    log.addHandler(console)
    return log

log = _setup_logging()

# ── Resume helpers (same pattern as exp1) ─────────────────────────────────────
def _load_completed() -> set[tuple[str, str, str]]:
    """Return set of (task_id, condition, failure_type) already in the CSV."""
    done: set[tuple[str, str, str]] = set()
    if not RESULTS_FILE.exists():
        return done
    with RESULTS_FILE.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            done.add((row["task_id"], row["condition"], row["injected_failure_type"]))
    return done

def _ensure_csv_header() -> None:
    if not RESULTS_FILE.exists():
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        with RESULTS_FILE.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(CSV_HEADERS)

def _append_row(row: dict) -> None:
    with RESULTS_FILE.open("a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=CSV_HEADERS).writerow(row)


# ── Chaos injection nodes ─────────────────────────────────────────────────────

def _inject_context_node(state: DPState) -> dict:
    """
    Runs after initialize_node, before generator_node.
    For ctx_overflow: pads problem_spec with ~5000 tokens of noise.
    For hallucination/timeout: no-op (those are injected into code after generation).
    Active only once (initialize_node always resets current_round=0, so this node
    only runs on Round 0 because the loop never returns through initialize).
    """
    if not state.get("injection_active", False):
        return {}
    if state.get("injected_failure_type") != "ctx_overflow":
        return {}
    # Prepend noise to the real problem spec so the generator sees ~5000 extra tokens
    spec = state.get("problem_spec", "")
    return {"problem_spec": _CTX_OVERFLOW_PREFIX + spec}


def _inject_code_node(state: DPState) -> dict:
    """
    Runs after generator_node, before breaker_node/executor_node.
    For hallucination: injects a bad import into current_code.
    For timeout:       injects time.sleep(6) inside the first function body.
    For ctx_overflow:  no-op (context already corrupted upstream).
    Only active on Round 0 (single-shot injection; recovery rounds are clean).
    """
    if not state.get("injection_active", False):
        return {}
    if state.get("current_round", 0) != 0:
        return {}   # injection was Round 0 only — leave recovery rounds unmodified

    failure_type = state.get("injected_failure_type", "none")
    code = state.get("current_code", "")
    if not code.strip():
        return {}

    if failure_type == "hallucination":
        # Prepend a non-existent library import — triggers ModuleNotFoundError on exec
        injected = f"import nonexistent_chaos_lib_xyz  # chaos:hallucination\n{code}"
        return {"current_code": injected}

    if failure_type == "timeout":
        # Inject a 6-second sleep inside the first function body.
        # exec() inside Docker sandbox will be killed by the 5-second hard timeout.
        injected = re.sub(
            r"(def\s+\w+\s*\([^)]*\)\s*(?:->[^:]+)?:\s*\n)",
            r"\1    import time; time.sleep(6)  # chaos:timeout\n",
            code,
            count=1,
        )
        if injected == code:
            # Fallback: prepend at file level if regex didn't match
            injected = "import time; time.sleep(6)  # chaos:timeout\n" + code
        return {"current_code": injected}

    # ctx_overflow: code injection is a no-op — problem_spec was already padded
    return {}


# ── Chaos graph ───────────────────────────────────────────────────────────────

def _build_chaos_graph():
    """
    Chaos variant of the main graph:
      - Two extra injection nodes (inject_context, inject_code)
      - route_chaos: "degraded" loops instead of terminating, so recovery can happen
    """
    builder = StateGraph(DPState)

    # Nodes
    builder.add_node("initialize",      initialize_node)
    builder.add_node("inject_context",  _inject_context_node)   # ctx_overflow hook
    builder.add_node("generator",       generator_node)
    builder.add_node("inject_code",     _inject_code_node)       # hallucination/timeout hook
    builder.add_node("breaker",         breaker_node)
    builder.add_node("executor",        executor_node)
    builder.add_node("scorer",          scorer_node)
    builder.add_node("evolver",         evolver_node)
    builder.add_node("terminator",      terminator_node)

    # Edges: inject_context sits between initialize and generator
    #        inject_code   sits between generator  and breaker
    builder.set_entry_point("initialize")
    builder.add_edge("initialize",      "inject_context")
    builder.add_edge("inject_context",  "generator")
    builder.add_edge("generator",       "inject_code")
    builder.add_edge("inject_code",     "breaker")
    builder.add_edge("breaker",         "executor")
    builder.add_edge("executor",        "scorer")
    builder.add_edge("scorer",          "evolver")
    builder.add_edge("evolver",         "terminator")

    def route_chaos(state: DPState) -> str:
        """
        KEY DIFFERENCE vs. main graph:
        "degraded" is NOT terminal here — the system is allowed to keep trying
        to recover from the injected fault.  Only clean classifications exit.
        """
        af_class      = state.get("af_class", "pending")
        current_round = state.get("current_round", 0)
        max_rounds    = state.get("max_rounds", MAX_ROUNDS)

        if af_class in ("antifragile", "correct", "brittle"):
            return "done"
        if current_round >= max_rounds:
            return "done"
        return "loop"   # "pending" AND "degraded" both continue

    builder.add_conditional_edges(
        "terminator",
        route_chaos,
        {"loop": "generator", "done": END},
    )

    return builder.compile()


# Build once at module load (expensive; contains compiled LangGraph)
_chaos_graph = _build_chaos_graph()


# ── Initial state ─────────────────────────────────────────────────────────────
def _make_initial_state(
    task_id: str,
    condition: str,
    failure_type: str,
    max_rounds: int,
) -> DPState:
    return DPState(
        task_id=task_id,
        problem_spec="",
        function_signature="",
        canonical_tests=[],
        condition=condition,
        max_rounds=max_rounds,
        current_round=0,
        failure_corpus=[],
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
        adversarial_tests=[],
        test_results=[],
        combined_pass_at_k=0.0,
        adversarial_ratio=0.0,
        bug_rate=0.0,
        edge_coverage=0.0,
        vuln_count=0,
        af_score=0.0,
        af_delta=0.0,
        af_trajectory=[],
        consecutive_improvement=0,
        af_class="pending",
        termination_reason="",
        probe_tasks=[],
        probe_fingerprint=[],
        injection_active=True,
        injected_failure_type=failure_type,
        recovery_successful=False,
        recovery_steps=0,
    )


# ── Retry (same pattern as exp1) ──────────────────────────────────────────────
def _invoke_with_retry(state: DPState, label: str) -> dict:
    """Invoke chaos graph with exponential backoff on rate-limit and timeout errors."""
    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return _chaos_graph.invoke(state)
        except _GroqRateLimitError as exc:
            last_exc = exc
            if attempt == MAX_RETRIES:
                break
            raw_sleep = BASE_BACKOFF * (2 ** (attempt - 1))
            sleep_s   = min(raw_sleep * random.uniform(0.75, 1.25), MAX_BACKOFF)
            log.warning("%s | RateLimitError (attempt %d/%d) — sleeping %.1f s",
                        label, attempt, MAX_RETRIES, sleep_s)
            time.sleep(sleep_s)
        except Exception as exc:
            exc_name = type(exc).__name__
            if "Timeout" in exc_name or "timeout" in str(exc).lower():
                last_exc = exc
                if attempt == MAX_RETRIES:
                    break
                sleep_s = min(BASE_BACKOFF * (2 ** (attempt - 1)) * random.uniform(0.75, 1.25), MAX_BACKOFF)
                log.warning("%s | Timeout (attempt %d/%d) — retrying in %.1f s",
                            label, attempt, MAX_RETRIES, sleep_s)
                time.sleep(sleep_s)
            else:
                log.error("%s | Unexpected error: %s", label, exc)
                raise
    log.error("%s | All %d retries exhausted. Last: %s", label, MAX_RETRIES, last_exc)
    raise last_exc  # type: ignore[misc]


# ── Task list ─────────────────────────────────────────────────────────────────
def _get_task_ids(max_tasks: int = 0) -> list[str]:
    """164 HumanEval+ IDs sorted numerically. If max_tasks>0, returns first N."""
    from evalplus.data import get_human_eval_plus
    ids = sorted(get_human_eval_plus().keys(), key=lambda k: int(k.split("/")[1]))
    return ids[:max_tasks] if max_tasks > 0 else ids


# ── Core runner ───────────────────────────────────────────────────────────────
def run(max_rounds: int = MAX_ROUNDS, dry_run: bool = False, max_tasks: int = 0) -> None:
    task_ids  = _get_task_ids(max_tasks)
    completed = _load_completed()

    total_runs     = len(task_ids) * len(CONDITIONS) * len(FAILURE_TYPES)
    completed_runs = sum(
        1 for tid in task_ids for cond in CONDITIONS for ft in FAILURE_TYPES
        if (tid, cond, ft) in completed
    )
    remaining_runs = total_runs - completed_runs

    print(
        f"\n{'='*65}\n"
        f"  DARWIN-PHOENIX  Experiment 2 — Fault Injection Stress Test\n"
        f"{'='*65}\n"
        f"  Tasks        : {len(task_ids)}\n"
        f"  Conditions   : {CONDITIONS}\n"
        f"  Failure types: {FAILURE_TYPES}\n"
        f"  Max rounds   : {max_rounds}\n"
        f"  Total runs   : {total_runs}  |  Done: {completed_runs}  |  Remaining: {remaining_runs}\n"
        f"  Output       : {RESULTS_FILE}\n"
        f"  Log          : {LOG_FILE}\n"
        f"{'='*65}\n"
    )

    if dry_run:
        print("[dry-run] Work list:")
        for tid in task_ids[:5]:   # show first 5 for brevity
            for cond in CONDITIONS:
                for ft in FAILURE_TYPES:
                    status = "DONE" if (tid, cond, ft) in completed else "TODO"
                    print(f"  {tid:<20} cond={cond}  fault={ft:<15}  {status}")
        print(f"  ... ({len(task_ids) - 5} more tasks)")
        return

    _ensure_csv_header()

    work = [
        (tid, cond, ft)
        for tid in task_ids
        for cond in CONDITIONS
        for ft in FAILURE_TYPES
        if (tid, cond, ft) not in completed
    ]

    errors: list[str] = []

    with _make_bar(work, total=len(work), desc="Exp 2", unit="run", leave=True) as pbar:
        for task_id, condition, failure_type in pbar:
            label = f"{task_id}|{condition}|{failure_type}"
            pbar.set_postfix_str(label)

            state   = _make_initial_state(task_id, condition, failure_type, max_rounds)
            t_start = time.perf_counter()

            try:
                final  = _invoke_with_retry(state, label)
                wall_s = time.perf_counter() - t_start

                af_class   = final.get("af_class",           "unknown")
                af_score   = final.get("af_score",            0.0)
                pass_at_k  = final.get("combined_pass_at_k",  0.0)
                rounds     = final.get("current_round",        0)
                reason     = final.get("termination_reason",  "")

                recovery_successful = af_class in ("correct", "antifragile")
                # recovery_steps = total rounds executed (injection=Round0, recovery on later rounds)
                recovery_steps      = rounds

                row = {
                    "task_id":              task_id,
                    "condition":            condition,
                    "injected_failure_type": failure_type,
                    "af_class":             af_class,
                    "af_score":             f"{af_score:.6f}",
                    "combined_pass_at_k":   f"{pass_at_k:.6f}",
                    "recovery_successful":  recovery_successful,
                    "recovery_steps":       recovery_steps,
                    "termination_reason":   reason,
                    "wall_time_s":          f"{wall_s:.2f}",
                    "timestamp":            datetime.now(timezone.utc).isoformat(),
                }
                _append_row(row)
                log.info(
                    "%-22s cond=%s fault=%-15s af=%-12s recovered=%s steps=%d (%.1fs)",
                    task_id, condition, failure_type, af_class,
                    recovery_successful, recovery_steps, wall_s,
                )

            except Exception as exc:
                wall_s  = time.perf_counter() - t_start
                err_msg = str(exc)[:120]
                log.error("%-22s cond=%s fault=%s FAILED: %s",
                          task_id, condition, failure_type, err_msg)
                errors.append(f"{label}: {err_msg}")
                _append_row({
                    "task_id":              task_id,
                    "condition":            condition,
                    "injected_failure_type": failure_type,
                    "af_class":             "ERROR",
                    "af_score":             "",
                    "combined_pass_at_k":   "",
                    "recovery_successful":  "",
                    "recovery_steps":       "",
                    "termination_reason":   err_msg,
                    "wall_time_s":          f"{wall_s:.2f}",
                    "timestamp":            datetime.now(timezone.utc).isoformat(),
                })

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'='*65}")
    print(f"  Exp 2 complete. Results -> {RESULTS_FILE}")

    results: list[dict] = []
    with RESULTS_FILE.open(newline="", encoding="utf-8") as f:
        results = [r for r in csv.DictReader(f) if r.get("af_class") not in ("ERROR", "unknown", "")]

    # Recovery rate per failure type
    print("\n  Recovery rates by failure type:")
    for ft in FAILURE_TYPES:
        ft_rows = [r for r in results if r["injected_failure_type"] == ft]
        if not ft_rows:
            continue
        recovered = sum(1 for r in ft_rows if r["recovery_successful"] == "True")
        rate = recovered / len(ft_rows) * 100
        steps_vals = [int(r["recovery_steps"]) for r in ft_rows
                      if r["recovery_successful"] == "True" and r["recovery_steps"].isdigit()]
        avg_steps  = sum(steps_vals) / len(steps_vals) if steps_vals else float("nan")
        print(f"    {ft:<16}: {recovered}/{len(ft_rows)} recovered ({rate:.1f}%) "
              f"| avg recovery_steps={avg_steps:.1f}")

    print(f"\n  Errors: {len(errors)}")
    if errors:
        for e in errors[:10]:
            print(f"    {e}")
    print(f"{'='*65}\n")


# ── CLI ───────────────────────────────────────────────────────────────────────
def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Experiment 2: Fault Injection Stress Test — Conds A & C × 3 failure types",
    )
    p.add_argument("--max-rounds", type=int, default=MAX_ROUNDS,
                   help=f"Max rounds per run (default: {MAX_ROUNDS})")
    p.add_argument("--max-tasks", type=int, default=0,
                   help="Limit to first N tasks (default: 0 = all 164). Use 50 for paper subset.")
    p.add_argument("--dry-run", action="store_true",
                   help="Print work list without invoking the graph")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run(max_rounds=args.max_rounds, dry_run=args.dry_run, max_tasks=args.max_tasks)
