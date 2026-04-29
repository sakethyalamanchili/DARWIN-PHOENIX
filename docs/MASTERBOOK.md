# DARWIN-PHOENIX: The Complete Implementation & Research Masterbook

**Author:** Saketh Yalamanchili — M.S. Data Science & Analytics, Florida Atlantic University  
**Course:** COT6930: Generative Intelligence & Software Development Lifecycles  
**Track:** Blue Sky Track — Spring 2026  
**Status:** ALL EXPERIMENTS COMPLETE — Paper published to arXiv  
**Last Updated:** 2026-04-29 (Post publication — all 3 experiments complete, paper submitted)

---

## CHANGE LOG

| Version | Date | Change |
|---|---|---|
| v1.0 | Pre-Phase 5 | Initial Masterbook (research doc) |
| v1.1 | 2026-04-20 | **Bug Fix:** `route_verdict` — added `"degraded"` to terminal set (`graph.py:36`) |
| v1.1 | 2026-04-20 | **Bug Fix:** Condition D freeze off-by-one — `current_round > 1` → `> 0` (`breaker.py:104`) |
| v1.2 | 2026-04-20 | Masterbook updated to reflect actual codebase; Phase 6 runner specs added |
| v1.3 | 2026-04-21 | **Phase 6 complete:** all 3 experiment runners built and validated |
| v1.3 | 2026-04-21 | **Infra:** `nodes/llm_client.py` added — shared factory supporting Groq + OpenRouter |
| v1.3 | 2026-04-21 | **Fix:** Generator default model corrected to `qwen/qwen3-32b` (Groq `qwen-2.5-coder-32b` decommissioned) |
| v1.3 | 2026-04-21 | **Fix:** Breaker `_to_test_results` guards `isinstance(t, dict)` — skips int/str LLM returns |
| v1.3 | 2026-04-21 | **Fix:** Breaker `_extract_json` returns `[]` on empty response (OpenRouter content filter) |
| v1.3 | 2026-04-21 | **Perf:** OpenRouter `enable_thinking: False` disables qwen3-32b CoT — 10× latency reduction |
| v1.3 | 2026-04-21 | **Infra:** 90s hard timeout on OpenRouter client; retry logic catches `TimeoutError` |
| v1.3 | 2026-04-21 | **Runner:** `--retry-errors` flag strips ERROR rows from CSV and re-runs them |
| v1.3 | 2026-04-22 | **Exp 1:** 602/656 runs complete (91%) — preliminary results available |
| v2.0 | 2026-04-29 | **ALL EXPERIMENTS COMPLETE** — Exp 1 (656 runs), Exp 2 (300 runs), Exp 3 (50 tasks) |
| v2.0 | 2026-04-29 | **Paper:** Full LaTeX paper written (PAPER.tex), arXiv zip prepared |
| v2.0 | 2026-04-29 | **Figures:** All 4 result figures + system architecture figure generated |
| v2.0 | 2026-04-29 | **Finding:** Behavioral fingerprinting — ρ=0.720, degraded tasks 2.6× drift (p=0.0003) |
| v2.0 | 2026-04-29 | **Finding:** Degradation ordering C(6.7%) < D(7.3%) < A(9.8%) < B(11.0%) — pilot evidence |
| v2.0 | 2026-04-29 | **Finding:** Hallucination recovery step advantage Mann-Whitney p=0.010 |

---

## CHAPTER 1: Research Foundations & Theory

### 1.1 The Mechanism Question (Primary RQ)

Is adversarial pressure or failure exposure the primary mechanism behind antifragility improvement in co-evolving LLM pipelines?

Today's AI code generation pipelines are cooperative (Generator writes, Reviewer suggests). There is no intelligent adversary actively probing weaknesses. **DARWIN-PHOENIX** hypothesizes that introducing a dedicated **Breaker** agent—one that actively tries to find bugs, edge cases, and security flaws—forces the Generator to develop robust defensive strategies it would never learn from friendly feedback alone.

**The Critical Confound:** If this adversarial system produces better code, is it because of the adversarial arms race (**pressure**), or simply because the Generator was exposed to more failure examples (**exposure**)? Our 4-condition experimental design strictly isolates this variable.

### 1.2 The Four Experimental Conditions

The LangGraph state machine handles these four conditions dynamically based on the single `state["condition"]` flag set at initialization.

| Condition | Name | Graph Behavior | Expected Max Classification |
|---|---|---|---|
| **A** | Cooperative Baseline | `breaker_node` returns `[]` immediately; no adversarial tests generated | Tier 1: `correct` |
| **B** | Failure-Augmented | Breaker node is still bypassed (`adversarial_tests = []`). Generator's Round N+ prompt injects examples from static `failure_corpus` instead of live adversarial failures. Isolates **exposure without pressure**. | Tier 2: `robust` |
| **C** | Full Co-Evolution (Main) | Full adversarial loop. Both Generator and Breaker strategies update via `evolver_node` each round. | Tier 3: `antifragile` |
| **D** | Frozen Adversarial | Breaker is active in Round 1 only. From Round 2 onward (`current_round > 0` post-evolver increment), frozen Round 1 tests are replayed unchanged. `evolver_node` does NOT update breaker strategy for Condition D. Isolates **co-evolution from static adversarial**. | Tier 2: `robust` |

> **Core Thesis:** If Condition C reaches `antifragile` but Condition B plateaus at `robust`, we prove that dynamic adversarial pressure (not just failure exposure) is the necessary mechanism.

### 1.3 The Three Experiments

| Exp | Name | Conditions Run | Primary Metric | Result File |
|---|---|---|---|---|
| **1** | Baseline Antifragility | All 4 conditions × 164 HumanEval+ tasks | `af_score`, `af_class` distribution | `results/exp1_results.csv` |
| **2** | Fault Injection Stress Test | Conditions A & C with `injection_active=True` | `recovery_successful`, `recovery_steps` | `results/exp2_chaos_results.csv` |
| **3** | Behavioral Fingerprinting | Condition C, tracking `probe_fingerprint` | `fingerprint_distance` per round | `results/exp3_fingerprint.json` |

---

## CHAPTER 2: Literature Review & The Novelty Gap

| Paper | Core Contribution | Critical Gap vs. DARWIN-PHOENIX |
|---|---|---|
| **Digital Red Queen** (arxiv 2601.03335) | LLMs co-evolve programs adversarially in Corewar. | Abstract domain only. No software semantics or mechanism isolation (Cond B). |
| **Code-A1** (arxiv 2603.15611) | Dual-policy optimization (Coder + Test LLM). | Test LLM is static. No co-evolution. Does not ask the mechanism question. |
| **GASP** (arxiv 2603.15957) | Asymmetric self-play: Teacher generates harder problems. | Cooperative curriculum scheduling, not an adversarial arms race. |
| **AgentAssay** (arxiv 2603.02601) | Formal evaluation tuple for non-deterministic AI. | Evaluation framework only. Does not modify or co-evolve pipelines. Basis for `edge_coverage` metric. |
| **Behavioral Fingerprinting** (arxiv 2509.04504) | Maps execution traces to behavioral profiles. | Applied to static LLMs, not dynamic co-evolving loops. Directly adapted for Exp 3. |

---

## CHAPTER 3: System Architecture & Master Data Structures

### 3.1 The Master State Schema (`DPState`)

**File:** `state.py`

```python
from typing import TypedDict, List, Literal, Annotated, Optional
import operator

class TestResult(TypedDict):
    test_id: str
    input: str        # repr() of args, e.g. "([1, 2, 3],)"
    expected: str     # repr() of expected output; "" = pass-if-no-exception
    actual: str       # repr() of actual output or exception
    passed: bool
    source: Literal['standard', 'adversarial', 'probe']
    error_type: Optional[str]   # exception class name, or None

class AgentStrategy(TypedDict):
    round_num: int
    prompt_prefix: str
    active_vectors: List[str]   # Breaker: attack categories. Generator: defense heuristics
    fingerprint: str            # Behavioral hash for Exp 3

class DPState(TypedDict):
    # Task Information
    task_id: str
    problem_spec: str
    function_signature: str
    canonical_tests: List[TestResult]

    # Experiment Configuration
    condition: Literal["A", "B", "C", "D"]
    max_rounds: int
    current_round: int          # 0-indexed; incremented by evolver_node at end of each round
    failure_corpus: List[dict]  # Condition B only — loaded from data/failure_corpus.json

    # Agent States
    current_code: str
    code_versions: Annotated[List[str], operator.add]   # accumulates every round
    generator_strategy: AgentStrategy
    breaker_strategy: AgentStrategy
    breaker_strategy_frozen: bool   # True in Cond D (set at initialize; enforced in breaker_node)
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
    af_trajectory: Annotated[List[float], operator.add]  # accumulates every round
    consecutive_improvement: int
    af_class: Literal["brittle", "correct", "robust", "antifragile", "degraded", "pending"]
    termination_reason: str

    # Fingerprinting (Exp 3)
    probe_tasks: List[dict]
    probe_fingerprint: Annotated[List[dict], operator.add]  # accumulates every round

    # Fault Injection (Exp 2)
    injection_active: bool
    injected_failure_type: Literal["hallucination", "ctx_overflow", "contradiction", "timeout", "none"]
    recovery_successful: bool
    recovery_steps: int
```

> **Key `Annotated` fields:** `code_versions`, `af_trajectory`, and `probe_fingerprint` use `operator.add` — LangGraph **appends** updates to these lists each round rather than replacing them.

### 3.2 Graph Routing & Topology

**File:** `graph.py`

```
initialize → generator → breaker → executor → scorer → evolver → terminator
                ↑                                                      |
                └──────────────────── "loop" ──────────────────────────┘
                                                                 "done" → END
```

**Routing function (as-built, post Phase 5 fix):**
```python
def route_verdict(state: DPState) -> str:
    # "degraded" is terminal — do NOT loop on broken/insecure code
    if state["af_class"] in ("antifragile", "correct", "brittle", "degraded"):
        return "done"
    if state["current_round"] >= state["max_rounds"]:
        return "done"
    return "loop"   # only "pending" reaches here
```

> ⚠️ **Bug Fix v1.1:** Pre-fix, `"degraded"` was missing from the terminal set. The graph would loop up to `max_rounds` even when G1/G2/G3 had already failed, wasting API calls. Fixed 2026-04-20.

---

## CHAPTER 4: Node Implementation — As-Built Reference

### N1: `initialize_node` (`nodes/initialize.py`)

- Loads the HumanEval+ problem by `task_id` from `evalplus`.
- Parses `function_signature` from the problem prompt via regex.
- Builds `canonical_tests` from `problem["base_input"]` — `expected` is intentionally empty (`""`); executor marks canonical tests as passed if no exception is raised.
- Loads `probe_tasks` from `data/probe_tasks.json` (all conditions).
- Loads `failure_corpus` from `data/failure_corpus.json` **only for Condition B**.
- Sets `current_round = 0`, `af_class = "pending"`, all scores to `0.0`.
- Sets `breaker_strategy_frozen = (condition == "D")`.

### N2: `generator_node` (`nodes/generator.py`)

- **Model:** `GENERATOR_MODEL` env var, default `qwen/qwen3-32b`.
- **Round 0:** Uses `GENERATOR_ROUND_0` prompt with `problem_spec` + `function_signature`.
- **Round N+ (Condition B):** Uses `GENERATOR_ROUND_N` but injects `failure_corpus` examples (up to 2) instead of live adversarial failures.
- **Round N+ (Conditions A, C, D):** Uses `GENERATOR_ROUND_N` with actual failed tests from `test_results`.
- Strips `<think>...</think>` blocks and markdown fences from LLM output.
- Returns `current_code` (str) and `code_versions: [code]` (appended by LangGraph).

### N3: `breaker_node` (`nodes/breaker.py`)

- **Model:** `BREAKER_MODEL` env var, default `qwen/qwen3-32b` (Groq).

**Routing table (as-built, post Phase 5 fix):**

| Condition | `current_round` | Action |
|---|---|---|
| A | any | Return `{"adversarial_tests": []}` immediately |
| D | `> 0` (i.e., Round 2+) | Return frozen `state["adversarial_tests"]` unchanged |
| B, C, D Round 1 | `== 0` | Call LLM → generate adversarial tests |

> ⚠️ **Bug Fix v1.1:** Pre-fix, Condition D used `current_round > 1`, causing Round 2 to make a live LLM call instead of replaying. Fixed to `current_round > 0` (since `evolver_node` increments the round counter before the next `breaker_node` call). Fixed 2026-04-20.

- Strips `<think>` blocks, extracts last JSON fenced block, sanitizes Python literals (`None`, `True`, `sys.maxsize`).
- Partial parse fallback: extracts individual `{...}` objects when the full array fails.

### N4: `executor_node` (`nodes/executor.py`)

- **Sandbox:** `dp-sandbox` Docker image (built from `Dockerfile.sandbox`).
- **Timeout:** Hard 5-second kill via `subprocess.run(timeout=5)`.
- **Constraints:** `--network none`, `--memory 256m`, `--cpus 0.5`, runs as `sandboxuser`.
- Runs `canonical_tests + adversarial_tests` in a single container invocation.
- **Pass logic:**
  - Canonical test: passes if no exception raised (expected = `""`)
  - Adversarial test: passes if `expected` string contains the raised exception class name
- Falls back to all-failed on timeout or JSON parse error.

### N5: `scorer_node` (`nodes/scorer.py`)

**Formula (Masterbook Ch. 5):**
```
base_score = 0.35 * canonical_pass_at_k
           + 0.35 * adversarial_pass_at_k
           + 0.20 * adversarial_ratio

af_delta = base_score - prev_af_score   (prev = last element of af_trajectory, or 0.0)
af_score = base_score + 0.10 * af_delta
```

- `vuln_count`: Bandit static analysis (HIGH + MEDIUM issues), run locally.
- `edge_coverage`: branch coverage via `coverage.py` inside `dp-sandbox` (adversarial tests only).
- `af_trajectory`: appends `[af_score]` each round via `Annotated[List[float], operator.add]`.

> **Condition A note:** With no adversarial tests, `adversarial_pass_at_k = 0.0` and `adversarial_ratio = 0.0`, capping `base_score` at `0.35`. G5 plateau (`af_delta < 0.05`) will fire quickly, terminating as `"correct"`. This is intentional — Condition A is the cooperative baseline ceiling.

### N6: `evolver_node` (`nodes/evolver.py`)

- **Model:** `EVOLVER_MODEL` env var, default `llama-3.1-8b-instant` (Groq).
- Always updates `generator_strategy.active_vectors` based on failed tests.
- Updates `breaker_strategy.active_vectors` **only for Condition C**. Conditions A, B, D copy the strategy unchanged (but `round_num` increments).
- **Increments `current_round` by 1** — this is the single source of truth for round counting.

### N7: `terminator_node` (`nodes/terminator.py`)

See Chapter 5 for full gate logic.

---

## CHAPTER 5: The 7-Gate Antifragility Logic

All gates are deterministic. No LLM call. Evaluated sequentially each round.

| Gate | Name | Condition | Fail → `af_class` | Notes |
|---|---|---|---|---|
| **G1** | Syntax | `ast.parse(code)` succeeds | `"degraded"` | Immediate exit via `route_verdict` (v1.1 fix) |
| **G2** | Canonical | `canonical_pass_at_k == 1.0` | `"degraded"` | Zero regressions on HumanEval+ base tests |
| **G3** | Security | `vuln_count == 0` | `"degraded"` | Bandit HIGH/MEDIUM issues only |
| **G4** | Adversarial | `adversarial_pass_at_k >= 0.80` | `"pending"` (loop) or `"correct"` (at max_rounds) | Condition A always passes (no adversarial tests → ratio = 1.0) |
| **G5** | Improvement | `af_delta >= 0.05` | `"correct"` | Plateau detection |
| **G6** | Coverage | `edge_coverage >= 0.75` | `"correct"` | Attacks must be deep, not shallow |
| **G7** | Behavioral | `fingerprint_distance > 0.15` | `"correct"` | Must evolve reasoning, not memorize |
| **PASS** | Antifragile | All gates passed | `"antifragile"` | |

**`fingerprint_distance`** computed in `_fingerprint_distance()`: fraction of probe trace hashes that changed vs. previous round. Requires ≥ 2 rounds of `probe_fingerprint` data (skips G7 gracefully if insufficient).

---

## CHAPTER 6: Prompt Engineering Arsenal

### GENERATOR_ROUND_0

```
SYSTEM PROMPT — GENERATOR
==========================================
You are DARWIN, a Python code generation agent.
Your objective: write a Python function that:
  1. Passes the canonical test suite with 100% accuracy.
  2. Handles ALL edge cases: empty inputs, None, overflow, type mismatches, unicode, deep nesting.
  3. Contains no security vulnerabilities (no eval(), exec(), os.system(), __import__).
  4. Is readable and maintainable.

Problem Spec: {problem_spec}
{function_signature}

Output ONLY the Python function. No explanation. No markdown fences.
Include type hints and a one-line docstring.
```

### GENERATOR_ROUND_N (Rounds 1+)

```
SYSTEM PROMPT — GENERATOR (Round {current_round})
==========================================
{generator_strategy_prompt_prefix}

You are DARWIN. Your previous code iteration failed the following adversarial tests:
{failed_tests_summary}

Active defense heuristics: {generator_strategy_active_vectors}

Rewrite the function to resist these attack vectors while PRESERVING ALL canonical test cases.
Do not regress on standard functionality. Output ONLY the Python function.
```

> **Condition B substitution:** `failed_tests_summary` is replaced with `failure_corpus` examples (up to 2 entries) from `data/failure_corpus.json`.

### BREAKER

```
SYSTEM PROMPT — BREAKER
===========================
{breaker_strategy_prompt_prefix}

You are PHOENIX, an adversarial code tester. Analyze the following Python function and generate
test cases designed specifically to cause failures, crashes, or incorrect outputs.

Target Code:
{current_code}

Active attack vectors: {breaker_strategy_active_vectors}
Focus on:
  - integer_overflow: sys.maxsize, -sys.maxsize, 0
  - empty_input: [], '', None, {}, ()
  - type_confusion: wrong types (str where int expected)
  - boundary_values: fence-post conditions, off-by-one errors
  - unicode_injection: non-ASCII inputs, RTL characters
  - deep_nesting: highly nested data structures

Output ONLY a valid JSON array matching this exact schema:
[{"test_id": "adv_001", "input": "...", "expected": "...", "rationale": "..."}]
```

---

## CHAPTER 7: Compute Stack & Provider Routing

All LLM calls route through `nodes/llm_client.py`. Provider is controlled by `LLM_PROVIDER` env var.

| Role | Model (Groq name) | Env Var | Default |
|------|-------------------|---------|---------|
| Generator | `qwen/qwen3-32b` | `GENERATOR_MODEL` | `qwen/qwen3-32b` |
| Breaker | `qwen/qwen3-32b` | `BREAKER_MODEL` | `qwen/qwen3-32b` |
| Evolver | `llama-3.1-8b-instant` | `EVOLVER_MODEL` | `llama-3.1-8b-instant` |

### Provider Options

**Groq** (free tier — 6K TPM, 500K TPD limit):
- Fast for small runs; hits daily cap at ~80 tasks
- `LLM_PROVIDER=groq`, set `GROQ_API_KEY`

**OpenRouter** (pay-per-token — recommended for full experiment runs):
- No daily cap; ~$2.60 total for full Exp 1 (656 runs)
- `enable_thinking: False` auto-applied for qwen3-32b — disables chain-of-thought, reduces latency 10×
- 90s hard timeout per request with exponential backoff retry
- `LLM_PROVIDER=openrouter`, set `OPENROUTER_API_KEY`

### Environment Setup

```bash
# 1. Virtual environment
pip install uv
uv venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/Mac

# 2. Dependencies
uv pip install -r requirements.txt

# 3. .env (OpenRouter — recommended)
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=your_key_here
GENERATOR_MODEL=qwen/qwen3-32b
BREAKER_MODEL=qwen/qwen3-32b
EVOLVER_MODEL=llama-3.1-8b-instant

# 4. Docker sandbox
docker build -t dp-sandbox -f Dockerfile.sandbox .
```

### Pre-Scale Validation

```bash
# End-to-end trace on one task (color-coded LangGraph output)
python verbose_run.py HumanEval/0

# Smoke test — 5 tasks × 4 conditions (local Ollama, zero API cost)
python smoke_test.py
```

Expected: all 20 runs complete, no `"pending"` final states, no errors.

---

## CHAPTER 8: Experiment Evaluation Guide

### Interpretation Table

| Observed Pattern | Interpretation | Paper Conclusion |
|---|---|---|
| `C ≈ B > A > D` | Failure exposure is the mechanism | Hypothesis falsified — co-evolution adds no value over static augmentation |
| `C > D ≈ B > A` | Adversarial pressure is the mechanism | Strong support for hypothesis |
| `C > B > D > A` | Both matter, synergistic | Most interesting outcome — mechanisms are complementary |
| `C > D > B > A` | Arms race alone is sufficient | Exposure alone insufficient; pressure drives improvement |

### Pre-Scale Checklist

```
[ ] smoke_test.py passes (no "pending" finals, no errors)
[ ] dp-sandbox Docker image built and tested
[ ] GROQ_API_KEY set in .env
[ ] data/probe_tasks.json populated (20 probe tasks for Exp 3)
[ ] data/failure_corpus.json populated (Condition B corpus)
[ ] results/ directory writable
```

---

## CHAPTER 9: Experiment Runners — As-Built Reference

All three runners are fully implemented as of v1.3. Each supports resume (skips completed rows on restart) and exponential backoff retry on rate-limit / timeout errors (base 2s, max 120s, 6 attempts).

### Exp 1 Runner (`experiments/exp1_runner.py`) — STATUS: COMPLETE (656/656 runs)

**Purpose:** 164 HumanEval+ tasks × 4 conditions = 656 runs. Primary evidence for mechanism hypothesis.

**CLI flags:**
```bash
python experiments/exp1_runner.py --max-rounds 10     # full run
python experiments/exp1_runner.py --max-rounds 2      # quick smoke check (2 rounds)
python experiments/exp1_runner.py --retry-errors      # strip ERROR rows from CSV, re-run them
python experiments/exp1_runner.py --dry-run           # print work list only, no API calls
```

**Output CSV schema** (`results/exp1_results.csv`, 10 columns):
```
task_id, condition, af_class, af_score, combined_pass_at_k, adversarial_ratio,
rounds_taken, termination_reason, wall_time_s, timestamp
```

**Final results (656/656 runs complete):**

| Condition | Correct | Degraded | Degraded% | Mean AF |
|-----------|---------|----------|-----------|---------|
| A — Baseline | 148 | 16 | 9.8% | 0.048 |
| B — Corpus | 146 | 18 | 11.0% | 0.025 |
| C — Co-Evolution | **153** | **11** | **6.7%** | 0.024 |
| D — Frozen | 152 | 12 | 7.3% | 0.019 |

Fisher exact C vs B: OR=0.58, p=0.121 (pilot; 49% power). K-W across conditions: H=7.537, p=0.057. `antifragile` structurally unreachable — G6 Docker branch coverage gate not deployed.

### Exp 2 Runner (`experiments/exp2_chaos.py`) — STATUS: COMPLETE (300 runs)

**Purpose:** Conditions A & C only. Toggle `injection_active=True` with `injected_failure_type` ∈ `["hallucination", "ctx_overflow", "timeout"]`. Measures `recovery_successful` and `recovery_steps` — tests pipeline resilience under mid-flight faults.

**Output:** `results/exp2_chaos_results.csv`
```
task_id, condition, injected_failure_type, af_class, recovery_successful, recovery_steps
```

### Exp 3 Runner (`experiments/exp3_fingerprint.py`) — STATUS: COMPLETE (50 tasks, Cond C)

**Purpose:** Condition C only. Track `probe_fingerprint` across rounds via 20 fixed probe tasks. Compute `fingerprint_distance` between consecutive rounds to verify behavioral drift (genuine reasoning evolution vs. memorization). Required for G7 gate validation.

**Required:** `data/probe_tasks.json` with exactly 20 probe tasks.

**Output:**
- `results/exp3_fingerprint.csv` — per-task, per-round fingerprint distance
- `results/exp3_fingerprint.json` — raw `probe_fingerprint` for post-hoc analysis

---

## APPENDIX A: Key File Map

```
DARWIN-PHOENIX/
├── state.py                    # DPState, TestResult, AgentStrategy TypedDicts
├── graph.py                    # LangGraph StateGraph, route_verdict() [v1.1 fix]
├── prompts.py                  # GENERATOR_ROUND_0, GENERATOR_ROUND_N, BREAKER
├── nodes/
│   ├── llm_client.py           # Shared LLM factory — Groq + OpenRouter routing [v1.3]
│   ├── initialize.py           # N1: loads HumanEval+, probe_tasks, failure_corpus
│   ├── generator.py            # N2: DARWIN — code generation (qwen3-32b)
│   ├── breaker.py              # N3: PHOENIX — adversarial tests [v1.1 fix, v1.3 guards]
│   ├── executor.py             # N4: Docker sandbox (5s timeout, --network none, 256MB)
│   ├── scorer.py               # N5: af_score formula, Bandit, coverage.py
│   ├── evolver.py              # N6: strategy evolution, increments current_round
│   └── terminator.py           # N7: 7-gate deterministic classification
├── experiments/
│   ├── exp1_runner.py          # ✅ 164 tasks × 4 conditions, resume-safe CSV [v1.3]
│   ├── exp2_chaos.py           # ✅ Fault injection stress test [v1.3]
│   └── exp3_fingerprint.py     # ✅ Behavioral fingerprinting [v1.3]
├── smoke_test.py               # Pre-scale validation (Ollama, zero API cost)
├── verbose_run.py              # Single-task debug trace with color-coded output
├── data/
│   ├── failure_corpus.json     # Curated failure examples (Condition B)
│   └── probe_tasks.json        # 20 fixed probe tasks (Exp 3)
├── results/                    # Output CSVs and logs (gitignored)
├── Dockerfile.sandbox          # dp-sandbox Docker image
└── docs/
    └── MASTERBOOK.md           # ← this file
```

---

## APPENDIX B: Known Design Decisions & Rationale

| Decision | Rationale |
|---|---|
| `current_round` incremented by `evolver_node`, not `terminator_node` | Round count reflects completed evolutionary cycles, not gate evaluations |
| Condition A `adversarial_pass_at_k = 0.0` in scorer | Empty list → 0.0 is the honest score; G4 gate returns `1.0` for empty adversarial set so Cond A is not penalized |
| `canonical_tests` expected = `""` | EvalPlus oracle is complex; pass-if-no-exception matches EvalPlus's own test-as-oracle pattern |
| Docker `--network none` | Prevents generator from calling external APIs to "cheat" the test suite |
| Partial JSON fallback in `breaker.py` | qwen3-32b sometimes truncates at token limit; regex fallback salvages partial test arrays |
| OpenRouter `enable_thinking: False` | Disables qwen3-32b chain-of-thought on OpenRouter; reduces avg latency from 10+ min → ~80s per run |
| 90s timeout on OpenRouter client | Prevents indefinite hangs from stalled HTTP streams; retried with backoff up to 6 attempts |
| `--retry-errors` in exp1_runner | Allows re-running ERROR rows (empty API response, transient network) without touching valid results |

---

## APPENDIX C: Final Results Summary

All experiments complete as of 2026-04-29. Full statistical reports in `results/exp*_statistical_report.txt`.

### Exp 1 — Code Quality Across Conditions (656/656 runs)

| Condition | N | Correct | Degraded | Degraded% | Mean AF |
|-----------|---|---------|----------|-----------|---------|
| A — Baseline | 164 | 148 | 16 | 9.8% | 0.048 |
| B — Corpus | 164 | 146 | 18 | 11.0% | 0.025 |
| C — Co-Evolution | 164 | 153 | 11 | **6.7%** | 0.024 |
| D — Frozen | 164 | 152 | 12 | 7.3% | 0.019 |

Fisher exact C vs B: OR=0.58, p=0.121. K-W: H=7.537, p=0.057. Study underpowered (49%); requires n≥342/condition for 80% power.

**Why no `antifragile`:** G6 branch coverage gate requires `dp-sandbox` Docker image. Docker not deployed → `edge_coverage=0.0` all runs → G6 always fails → `antifragile` structurally unreachable. Measured degradation resistance and behavioral drift as proxies.

### Exp 2 — Fault Recovery (300 runs)

| Fault Type | Cond A | Cond C | Δ |
|-----------|--------|--------|---|
| Hallucination | 76.0% | 80.0% | +4.0 pp |
| Context overflow | 78.0% | 86.0% | +8.0 pp |
| Timeout | 84.0% | 82.0% | −2.0 pp |
| Overall | 79.3% | 82.7% | +3.3 pp |

Mann-Whitney hallucination step distributions: U=903, p=0.010. K-W fault type effect: H=10.498, p=0.005.

### Exp 3 — Behavioral Fingerprint Drift (50 tasks, Cond C)

| Round | N | Mean Distance | SD |
|-------|---|---------------|----|
| 1 | 49 | 0.000 | 0.000 |
| 2 | 42 | 0.162 | 0.115 |
| 3 | 31 | 0.174 | 0.115 |
| 4 | 22 | 0.201 | 0.151 |

Spearman ρ=0.720, p<0.0001. Degraded tasks: mean max drift 0.240 vs. 0.092 correct (2.6×, p=0.0003). K-W across rounds: H=95.112, p<0.0001.
