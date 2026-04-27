# DARWIN-PHOENIX

![Pipeline Status](https://img.shields.io/badge/Pipeline-Validated-success)
![Exp1 Status](https://img.shields.io/badge/Exp1-Running_91%25-blue)
![LangGraph](https://img.shields.io/badge/Powered_by-LangGraph-orange)
![Venue](https://img.shields.io/badge/Target-NeurIPS_2026_Workshop-purple)

**DARWIN-PHOENIX** is an agentic AI research pipeline designed to investigate the mechanisms behind code generation antifragility in large language models. Built for COT6930 (Spring 2026) and targeted at the NeurIPS 2026 Workshop on Agentic AI.

> *Is adversarial pressure or failure exposure the primary mechanism behind antifragility improvement in co-evolving LLM pipelines?*

A multi-agent system where **Generator (DARWIN)** writes defensive code and **Breaker (PHOENIX)** aggressively searches for vulnerabilities creates a controlled environment to isolate and answer this question.

---

## Research Hypothesis

**Claim:** Dynamic adversarial co-evolution (Condition C) produces code that is more robust than static failure augmentation (Condition B), demonstrating that *adversarial pressure* — not just failure exposure — is the necessary mechanism.

**Falsification criterion:** If C ≈ B, the hypothesis fails. If C > B > A, the hypothesis holds.

---

## System Architecture

The pipeline is a deterministic state machine built with **LangGraph**, comprising 7 nodes wired in a round-trip loop:

```
initialize → generator → breaker → executor → scorer → evolver → terminator
                 ↑                                                     |
                 └────────────────── "loop" ──────────────────────────┘
                                                                "done" → END
```

| Node | Agent | Role |
|------|-------|------|
| `initialize_node` | — | Load HumanEval+ task, build canonical tests, inject failure corpus (Cond B) |
| `generator_node` | **DARWIN** | Write defensive Python using qwen3-32b; adapt via strategy vectors each round |
| `breaker_node` | **PHOENIX** | Generate adversarial edge-case tests (overflow, unicode, type confusion, etc.) |
| `executor_node` | — | Run code + tests inside Docker sandbox; capture pass/fail per test |
| `scorer_node` | — | Compute `af_score`, `pass@k`, `adversarial_ratio`, `vuln_count`, `edge_coverage` |
| `evolver_node` | — | LLM-driven strategy update for DARWIN (all conds) and PHOENIX (Cond C only) |
| `terminator_node` | — | 7-gate deterministic halt logic; assign final `af_class` |

---

## Experimental Design

Four conditions strictly isolate the mechanism variable:

| Condition | Name | Behavior | Isolates |
|-----------|------|----------|----------|
| **A** | Cooperative Baseline | No breaker, no corpus | Baseline generation ceiling |
| **B** | Failure-Augmented | Static `failure_corpus` injected; no live adversary | **Exposure** without pressure |
| **C** | Full Co-Evolution | DARWIN + PHOENIX both evolve each round | **True adversarial arms race** |
| **D** | Frozen Adversarial | Breaker active Round 1 only; frozen tests replayed thereafter | Co-evolution vs. static pressure |

---

## The 7-Gate Antifragility Logic

Terminal classification is deterministic — no LLM, no randomness:

| Gate | Name | Threshold | Fail → Class |
|------|------|-----------|--------------|
| G1 | Syntax | `ast.parse(code)` succeeds | `degraded` (immediate exit) |
| G2 | Canonical | `canonical_pass@k == 1.0` | `degraded` |
| G3 | Security | `vuln_count == 0` (Bandit HIGH+MED) | `degraded` |
| G4 | Adversarial | `adversarial_pass@k >= 0.80` | `pending` → loop |
| G5 | Improvement | `af_delta >= 0.05` | `correct` (plateau) |
| G6 | Coverage | `edge_coverage >= 0.75` | `correct` |
| G7 | Behavioral | `fingerprint_distance > 0.15` | `correct` |
| PASS | — | All gates cleared | `antifragile` |

**af_score formula:**
```
base  = 0.35 * canonical_pass@k + 0.35 * adversarial_pass@k + 0.20 * adversarial_ratio
delta = base - prev_af_score
af_score = base + 0.10 * delta
```

---

## Preliminary Results (Exp 1 — 91% complete, 602/656 runs)

| Condition | correct | degraded | antifragile |
|-----------|---------|---------|-------------|
| A — Cooperative Baseline | 136 | 14 | 0 |
| B — Failure-Augmented | 136 | 15 | 0 |
| C — Full Co-Evolution | **142** | **8** | 0 |
| D — Frozen Adversarial | 140 | 10 | 0 |

**Early signal:** Condition C has fewest degraded outcomes — consistent with hypothesis. `antifragile` class requires multi-round problems; most HumanEval tasks solve in Round 1. Full analysis pending completion.

---

## Experiment Suites

| Runner | File | Purpose | Status |
|--------|------|---------|--------|
| **Exp 1** | `experiments/exp1_runner.py` | 164 tasks × 4 conditions; collect `af_class`, `af_score` | **~91% complete** |
| **Exp 2** | `experiments/exp2_chaos.py` | Fault injection (hallucination, timeout, ctx_overflow); measure recovery | Pending |
| **Exp 3** | `experiments/exp3_fingerprint.py` | Behavioral fingerprinting across rounds; track code drift | Pending |

All runners support **resume** (`--retry-errors` flag re-runs failed rows without touching successful ones).

---

## Environment Setup

### 1. Prerequisites

```bash
pip install uv
uv venv .venv
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

uv pip install -r requirements.txt
```

### 2. Docker Sandbox

```bash
docker build -t dp-sandbox -f Dockerfile.sandbox .
```

### 3. Environment Variables (`.env`)

**Option A — Groq (free tier, 500K TPD limit):**
```env
LLM_PROVIDER=groq
GROQ_API_KEY=your_groq_key_here
GENERATOR_MODEL=qwen/qwen3-32b
BREAKER_MODEL=qwen/qwen3-32b
EVOLVER_MODEL=llama-3.1-8b-instant
```

**Option B — OpenRouter (pay-per-token, no daily cap — recommended for full runs):**
```env
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=your_openrouter_key_here
GENERATOR_MODEL=qwen/qwen3-32b
BREAKER_MODEL=qwen/qwen3-32b
EVOLVER_MODEL=llama-3.1-8b-instant
```

The `nodes/llm_client.py` factory routes all LLM calls to the correct provider automatically. On OpenRouter, `enable_thinking: False` is passed to disable qwen3-32b chain-of-thought (reduces latency ~10×).

### 4. Validate Before Scale Run

```bash
# End-to-end trace on one task (color-coded LangGraph output)
python verbose_run.py HumanEval/0

# Smoke test — 5 tasks × 4 conditions (uses local Ollama for cost-free dev testing)
python smoke_test.py
```

---

## Running Experiments

```bash
# Exp 1 — full run (164 tasks × 4 conditions)
python experiments/exp1_runner.py --max-rounds 10

# Exp 1 — quick smoke check (2 rounds)
python experiments/exp1_runner.py --max-rounds 2

# Exp 1 — re-run only rows that errored previously
python experiments/exp1_runner.py --retry-errors

# Exp 1 — dry run (print work list, no API calls)
python experiments/exp1_runner.py --dry-run
```

All output is written incrementally to `results/exp1_results.csv` — safe to Ctrl-C and resume at any time.

---

## Compute Stack

| Role | Model | Default Provider | Est. Cost (full Exp 1) |
|------|-------|-----------------|------------------------|
| Generator | `qwen/qwen3-32b` | OpenRouter | ~$1.50 |
| Breaker | `qwen/qwen3-32b` | OpenRouter | ~$1.00 |
| Evolver | `meta-llama/llama-3.1-8b-instruct` | OpenRouter | ~$0.10 |

Total Exp 1 cost on OpenRouter: **~$2.60** for 656 runs.

---

## File Map

```
DARWIN-PHOENIX/
├── state.py                    # DPState, TestResult, AgentStrategy TypedDicts
├── graph.py                    # LangGraph StateGraph, route_verdict()
├── prompts.py                  # GENERATOR_ROUND_0, GENERATOR_ROUND_N, BREAKER
├── nodes/
│   ├── llm_client.py           # Shared LLM factory (Groq / OpenRouter)
│   ├── initialize.py           # N1: task loading, corpus injection
│   ├── generator.py            # N2: DARWIN — code generation
│   ├── breaker.py              # N3: PHOENIX — adversarial tests
│   ├── executor.py             # N4: Docker sandbox (5s timeout, --network none)
│   ├── scorer.py               # N5: af_score, Bandit, coverage.py
│   ├── evolver.py              # N6: strategy evolution, round increment
│   └── terminator.py           # N7: 7-gate classification
├── experiments/
│   ├── exp1_runner.py          # 164 tasks × 4 conditions, resume-safe CSV
│   ├── exp2_chaos.py           # Fault injection stress test
│   └── exp3_fingerprint.py     # Behavioral fingerprinting
├── data/
│   ├── failure_corpus.json     # Curated failure examples (Condition B)
│   └── probe_tasks.json        # 20 fixed probe tasks (Exp 3)
├── results/                    # Output CSVs and logs (gitignored)
├── smoke_test.py               # Pre-scale validation (Ollama, no API cost)
├── verbose_run.py              # Single-task debug trace
├── Dockerfile.sandbox          # dp-sandbox Docker image
├── docs/
│   └── MASTERBOOK.md           # Full academic design reference
└── requirements.txt
```

---

> For full academic mechanics, node implementation details, prompt engineering, and experiment interpretation guides, see [`/docs/MASTERBOOK.md`](docs/MASTERBOOK.md).
