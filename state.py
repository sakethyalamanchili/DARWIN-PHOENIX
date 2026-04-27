from typing import TypedDict, List, Literal, Annotated, Optional
import operator


class TestResult(TypedDict):
    test_id: str
    input: str
    expected: str
    actual: str
    passed: bool
    source: Literal['standard', 'adversarial', 'probe']
    error_type: Optional[str]


class AgentStrategy(TypedDict):
    round_num: int
    prompt_prefix: str
    active_vectors: List[str]  # Breaker: attack categories. Generator: defense heuristics
    fingerprint: str           # Behavioral hash for Exp 3


class DPState(TypedDict):
    # Task Information
    task_id: str
    problem_spec: str
    function_signature: str
    canonical_tests: List[TestResult]

    # Experiment Configuration
    condition: Literal["A", "B", "C", "D"]
    max_rounds: int
    current_round: int
    failure_corpus: List[dict]  # Condition B only

    # Agent States
    current_code: str
    code_versions: Annotated[List[str], operator.add]
    generator_strategy: AgentStrategy
    breaker_strategy: AgentStrategy
    breaker_strategy_frozen: bool  # True in Cond D after round 1
    adversarial_tests: List[TestResult]

    # Execution Results
    test_results: List[TestResult]
    combined_pass_at_k: float
    adversarial_ratio: float
    bug_rate: float
    edge_coverage: float
    vuln_count: int

    # Antifragility Metrics & Judge
    af_score: float
    af_delta: float
    af_trajectory: Annotated[List[float], operator.add]
    consecutive_improvement: int
    af_class: Literal["brittle", "correct", "robust", "antifragile", "degraded", "pending"]
    termination_reason: str

    # Fingerprinting (Exp 3)
    probe_tasks: List[dict]
    probe_fingerprint: Annotated[List[dict], operator.add]

    # Fault Injection (Exp 2)
    injection_active: bool
    injected_failure_type: Literal["hallucination", "ctx_overflow", "contradiction", "timeout", "none"]
    recovery_successful: bool
    recovery_steps: int
