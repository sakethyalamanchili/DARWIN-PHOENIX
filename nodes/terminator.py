import ast

from state import DPState, TestResult

# terminator applies deterministic 7-gate logic — no LLM prompt needed

# Gate thresholds (Masterbook Ch. 5)
_G4_ADV_THRESHOLD    = 0.80
_G5_DELTA_THRESHOLD  = 0.05
_G6_COVERAGE_THRESHOLD = 0.75
_G7_FINGERPRINT_THRESHOLD = 0.15


def _canonical_pass_at_k(test_results: list[TestResult]) -> float:
    canonical = [t for t in test_results if t["source"] == "standard"]
    if not canonical:
        return 1.0   # no canonical tests → don't penalise
    return sum(1 for t in canonical if t["passed"]) / len(canonical)


def _adversarial_pass_at_k(test_results: list[TestResult]) -> float:
    adversarial = [t for t in test_results if t["source"] == "adversarial"]
    if not adversarial:
        return 1.0   # no adversarial tests (Condition A) → don't penalise
    return sum(1 for t in adversarial if t["passed"]) / len(adversarial)


def _fingerprint_distance(probe_fingerprint: list[dict], n_probes: int) -> float:
    """Fraction of probe trace_hashes that changed vs previous round.
    Requires at least 2 rounds of fingerprints (2 × n_probes entries)."""
    if n_probes == 0 or len(probe_fingerprint) < 2 * n_probes:
        return 0.0
    prev_round = probe_fingerprint[-(2 * n_probes):-n_probes]
    curr_round = probe_fingerprint[-n_probes:]
    prev_hashes = {e.get("probe_id"): e.get("trace_hash", "") for e in prev_round}
    curr_hashes = {e.get("probe_id"): e.get("trace_hash", "") for e in curr_round}
    changed = sum(
        1 for pid, h in curr_hashes.items()
        if prev_hashes.get(pid, "") != h
    )
    return changed / n_probes


def terminator_node(state: DPState) -> dict:
    code          = state.get("current_code", "")
    test_results  = state.get("test_results", [])
    current_round = state.get("current_round", 0)
    max_rounds    = state.get("max_rounds", 10)
    vuln_count    = state.get("vuln_count", 0)
    af_delta      = state.get("af_delta", 0.0)
    edge_coverage = state.get("edge_coverage", 0.0)
    probe_fp      = state.get("probe_fingerprint", [])
    probe_tasks   = state.get("probe_tasks", [])
    consecutive   = state.get("consecutive_improvement", 0)

    # ── G1: Syntax Gate ────────────────────────────────────────────────────
    try:
        ast.parse(code)
    except SyntaxError as e:
        return {
            "af_class":              "degraded",
            "termination_reason":    f"G1_SYNTAX_ERROR: {e}",
            "consecutive_improvement": 0,
        }

    # ── G2: Canonical Gate (zero regressions) ──────────────────────────────
    canonical_k = _canonical_pass_at_k(test_results)
    if canonical_k < 1.0:
        return {
            "af_class":              "degraded",
            "termination_reason":    f"G2_CANONICAL_REGRESSION: pass@k={canonical_k:.3f}",
            "consecutive_improvement": 0,
        }

    # ── G3: Security Gate (no HIGH/MEDIUM vulns) ───────────────────────────
    if vuln_count > 0:
        return {
            "af_class":              "degraded",
            "termination_reason":    f"G3_SECURITY_FAIL: vuln_count={vuln_count}",
            "consecutive_improvement": 0,
        }

    # ── G4: Adversarial Threshold ──────────────────────────────────────────
    adversarial_k = _adversarial_pass_at_k(test_results)
    if adversarial_k < _G4_ADV_THRESHOLD:
        if current_round >= max_rounds:
            return {
                "af_class":              "correct",
                "termination_reason":    f"G4_MAX_ROUNDS: adversarial_pass@k={adversarial_k:.3f}",
                "consecutive_improvement": 0,
            }
        # Keep looping
        return {
            "af_class":              "pending",
            "termination_reason":    "",
            "consecutive_improvement": 0,
        }

    # ── G5: Improvement Gate (not plateaued) ──────────────────────────────
    new_consecutive = consecutive + 1 if af_delta >= _G5_DELTA_THRESHOLD else 0
    if af_delta < _G5_DELTA_THRESHOLD:
        return {
            "af_class":              "correct",
            "termination_reason":    f"G5_PLATEAU: af_delta={af_delta:.4f} < {_G5_DELTA_THRESHOLD}",
            "consecutive_improvement": new_consecutive,
        }

    # ── G6: Coverage Gate (attacks must be deep) ──────────────────────────
    if edge_coverage < _G6_COVERAGE_THRESHOLD:
        return {
            "af_class":              "correct",
            "termination_reason":    f"G6_SHALLOW_ATTACKS: edge_coverage={edge_coverage:.3f} < {_G6_COVERAGE_THRESHOLD}",
            "consecutive_improvement": new_consecutive,
        }

    # ── G7: Behavioral Gate (must evolve, not memorize) ───────────────────
    fp_distance = _fingerprint_distance(probe_fp, len(probe_tasks))
    if fp_distance <= _G7_FINGERPRINT_THRESHOLD:
        return {
            "af_class":              "correct",
            "termination_reason":    f"G7_MEMORIZED: fingerprint_distance={fp_distance:.4f} <= {_G7_FINGERPRINT_THRESHOLD}",
            "consecutive_improvement": new_consecutive,
        }

    # ── ALL GATES PASS → ANTIFRAGILE ──────────────────────────────────────
    return {
        "af_class":              "antifragile",
        "termination_reason":    (
            f"ALL_GATES_PASS: canonical={canonical_k:.2f} adv={adversarial_k:.2f} "
            f"delta={af_delta:.3f} cov={edge_coverage:.2f} fp_dist={fp_distance:.3f}"
        ),
        "consecutive_improvement": new_consecutive,
    }


def should_terminate(state: DPState) -> str:
    """LangGraph routing function: 'done' exits loop, 'loop' continues."""
    af_class = state.get("af_class", "pending")
    current_round = state.get("current_round", 0)
    max_rounds = state.get("max_rounds", 10)

    if af_class in ("antifragile", "correct", "brittle"):
        return "done"
    if current_round >= max_rounds:
        return "done"
    return "loop"
