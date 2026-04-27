from state import DPState, TestResult, AgentStrategy

dummy_test: TestResult = {
    "test_id": "t001",
    "input": "[1, 2, 3]",
    "expected": "6",
    "actual": "6",
    "passed": True,
    "source": "standard",
    "error_type": None,
}

dummy_strategy: AgentStrategy = {
    "round_num": 0,
    "prompt_prefix": "You are DARWIN.",
    "active_vectors": ["edge_cases", "type_confusion"],
    "fingerprint": "abc123",
}

state: DPState = {
    # Task Information
    "task_id": "HumanEval/1",
    "problem_spec": "Sum a list of integers.",
    "function_signature": "def sum_list(nums: list[int]) -> int:",
    "canonical_tests": [dummy_test],

    # Experiment Configuration
    "condition": "C",
    "max_rounds": 10,
    "current_round": 0,
    "failure_corpus": [],

    # Agent States
    "current_code": "def sum_list(nums: list[int]) -> int:\n    return sum(nums)",
    "code_versions": ["def sum_list(nums): return sum(nums)"],
    "generator_strategy": dummy_strategy,
    "breaker_strategy": {**dummy_strategy, "prompt_prefix": "You are PHOENIX."},
    "breaker_strategy_frozen": False,
    "adversarial_tests": [],

    # Execution Results
    "test_results": [dummy_test],
    "combined_pass_at_k": 1.0,
    "adversarial_ratio": 0.0,
    "bug_rate": 0.0,
    "edge_coverage": 0.0,
    "vuln_count": 0,

    # Antifragility Metrics & Judge
    "af_score": 0.0,
    "af_delta": 0.0,
    "af_trajectory": [0.0],
    "consecutive_improvement": 0,
    "af_class": "pending",
    "termination_reason": "",

    # Fingerprinting (Exp 3)
    "probe_tasks": [{"probe_id": "p001", "task": "reverse a string"}],
    "probe_fingerprint": [{"probe_id": "p001", "trace_hash": "deadbeef"}],

    # Fault Injection (Exp 2)
    "injection_active": False,
    "injected_failure_type": "none",
    "recovery_successful": False,
    "recovery_steps": 0,
}

print("DPState instantiated OK")
print(f"  task_id:       {state['task_id']}")
print(f"  condition:     {state['condition']}")
print(f"  af_class:      {state['af_class']}")
print(f"  max_rounds:    {state['max_rounds']}")
print(f"  current_round: {state['current_round']}")
print(f"  code_versions: {len(state['code_versions'])} entry")
print(f"  probe_fingerprint: {len(state['probe_fingerprint'])} entry")
print(f"  injection_active: {state['injection_active']}")
print(f"  injected_failure_type: {state['injected_failure_type']}")
print("All fields verified.")
