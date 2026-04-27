"""
Smoke test: 5 HumanEval problems × 4 conditions via Ollama qwen2.5-coder:7b.
Verifies 7-gate logic routes correctly before touching Groq API at scale.
Masterbook Ch. 8: pass smoke test before running 10,000+ API calls.
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(__file__))

# ── Patch Groq client with fast Llama3 model ─────────────────
import os
from groq import Groq

# Use the fast Llama 3 model available on Groq for testing
FAST_MODEL = "llama-3.1-8b-instant"

import nodes.generator as _gen_mod
import nodes.breaker   as _brk_mod
import nodes.evolver   as _evo_mod

_gen_mod.GROQ_MODEL = FAST_MODEL
_brk_mod.GROQ_MODEL = FAST_MODEL
_evo_mod.GROQ_MODEL = FAST_MODEL

# ─────────────────────────────────────────────────────────────────────────────

from graph import darwin_phoenix
from state import DPState, AgentStrategy

TASK_IDS   = ["HumanEval/0", "HumanEval/1", "HumanEval/2", "HumanEval/3", "HumanEval/4"]
CONDITIONS = ["A", "B", "C", "D"]
MAX_ROUNDS = 2    # 1 full loop — enough to exercise routing


def make_initial_state(task_id: str, condition: str) -> DPState:
    gen_strat = AgentStrategy(
        round_num=0,
        prompt_prefix="You are DARWIN, a Python code generation agent.",
        active_vectors=[],
        fingerprint="",
    )
    brk_strat = AgentStrategy(
        round_num=0,
        prompt_prefix="You are PHOENIX, an adversarial code tester.",
        active_vectors=["integer_overflow", "empty_input", "type_confusion",
                        "boundary_values", "unicode_injection", "deep_nesting"],
        fingerprint="",
    )
    return DPState(
        task_id=task_id,
        problem_spec="",
        function_signature="",
        canonical_tests=[],
        condition=condition,
        max_rounds=MAX_ROUNDS,
        current_round=0,
        failure_corpus=[],
        current_code="",
        code_versions=[],
        generator_strategy=gen_strat,
        breaker_strategy=brk_strat,
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
        injection_active=False,
        injected_failure_type="none",
        recovery_successful=False,
        recovery_steps=0,
    )


def run_smoke_test():
    print("=" * 70)
    print("DARWIN-PHOENIX  Smoke Test  |  Ollama qwen2.5-coder:7b  |  2 rounds")
    print("=" * 70)
    print(f"{'TASK':<18} {'COND':<6} {'af_class':<14} {'rounds':<8} {'termination_reason'}")
    print("-" * 70)

    results = []

    for task_id in TASK_IDS:
        for condition in CONDITIONS:
            t0 = time.time()
            try:
                initial = make_initial_state(task_id, condition)
                final = darwin_phoenix.invoke(initial)
                elapsed = time.time() - t0
                af_class  = final.get("af_class", "unknown")
                rounds    = final.get("current_round", 0)
                reason    = final.get("termination_reason", "")[:45]
                results.append((task_id, condition, af_class, rounds, reason, None))
                print(f"{task_id:<18} {condition:<6} {af_class:<14} {rounds:<8} {reason}")
            except Exception as e:
                elapsed = time.time() - t0
                err = str(e)[:50]
                results.append((task_id, condition, "ERROR", 0, err, str(e)))
                print(f"{task_id:<18} {condition:<6} {'ERROR':<14} {'—':<8} {err}")

    print("=" * 70)

    # Summary
    errors  = [r for r in results if r[2] == "ERROR"]
    classes = [r[2] for r in results if r[2] != "ERROR"]
    print(f"\nSummary: {len(results)} runs | {len(errors)} errors")
    print(f"af_class distribution: { {c: classes.count(c) for c in set(classes)} }")

    # Gate routing check: degraded/pending must NOT appear in final state
    bad_finals = [r for r in results if r[2] in ("pending",)]
    if bad_finals:
        print(f"\nWARNING: {len(bad_finals)} run(s) ended in 'pending' — graph didn't terminate properly")
    else:
        print("\n7-gate routing: OK — no runs stuck in 'pending'")


if __name__ == "__main__":
    run_smoke_test()
