import json
import re
import os
from typing import Any

from evalplus.data import get_human_eval_plus
from state import DPState, TestResult, AgentStrategy

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
PROBE_TASKS_PATH = os.path.join(DATA_DIR, "probe_tasks.json")
FAILURE_CORPUS_PATH = os.path.join(DATA_DIR, "failure_corpus.json")


def _parse_function_signature(prompt: str) -> str:
    match = re.search(r'(def \w+\([^)]*\)[^:]*:)', prompt)
    return match.group(1) if match else ""


def _build_canonical_tests(problem: dict[str, Any]) -> list[TestResult]:
    entry = problem["entry_point"]
    tests: list[TestResult] = []
    for i, args in enumerate(problem.get("base_input", [])):
        tests.append(TestResult(
            test_id=f"canonical_{i:03d}",
            input=repr(args),
            expected="",   # oracle lives in problem["test"]; filled at execution time
            actual="",
            passed=False,
            source="standard",
            error_type=None,
        ))
    return tests


def _default_strategy(role: str) -> AgentStrategy:
    return AgentStrategy(
        round_num=0,
        prompt_prefix=f"You are {'DARWIN' if role == 'generator' else 'PHOENIX'}.",
        active_vectors=[] if role == "generator" else [
            "integer_overflow", "empty_input", "type_confusion",
            "boundary_values", "unicode_injection", "deep_nesting",
        ],
        fingerprint="",
    )


def initialize_node(state: DPState) -> dict:
    dataset = get_human_eval_plus()
    task_id = state["task_id"]

    if task_id not in dataset:
        raise ValueError(f"task_id '{task_id}' not found in HumanEval+")

    problem = dataset[task_id]
    function_signature = _parse_function_signature(problem["prompt"])
    canonical_tests = _build_canonical_tests(problem)

    with open(PROBE_TASKS_PATH, "r", encoding="utf-8") as f:
        probe_tasks: list[dict] = json.load(f)

    failure_corpus: list[dict] = []
    if state.get("condition") == "B":
        with open(FAILURE_CORPUS_PATH, "r", encoding="utf-8") as f:
            failure_corpus = json.load(f)

    return {
        "problem_spec": problem["prompt"],
        "function_signature": function_signature,
        "canonical_tests": canonical_tests,
        "probe_tasks": probe_tasks,
        "failure_corpus": failure_corpus,
        "current_round": 0,
        "af_class": "pending",
        "af_score": 0.0,
        "af_delta": 0.0,
        "af_trajectory": [],
        "consecutive_improvement": 0,
        "termination_reason": "",
        "current_code": "",
        "code_versions": [],
        "test_results": [],
        "adversarial_tests": [],
        "combined_pass_at_k": 0.0,
        "adversarial_ratio": 0.0,
        "bug_rate": 0.0,
        "edge_coverage": 0.0,
        "vuln_count": 0,
        "probe_fingerprint": [],
        "injection_active": state.get("injection_active", False),
        "injected_failure_type": state.get("injected_failure_type", "none"),
        "recovery_successful": False,
        "recovery_steps": 0,
        "generator_strategy": _default_strategy("generator"),
        "breaker_strategy": _default_strategy("breaker"),
        "breaker_strategy_frozen": state.get("condition") == "D",
    }
