import json
import os
import re

from dotenv import load_dotenv

from nodes.llm_client import get_client, resolve_model, extra_kwargs, timed_completion
from prompts import GENERATOR_ROUND_N  # evolver uses generator strategy context
from state import DPState, AgentStrategy, TestResult

load_dotenv()

GROQ_MODEL = os.environ.get("EVOLVER_MODEL", "llama-3.1-8b-instant")
_client = None

_GENERATOR_EVOLVE_PROMPT = """\
You are a co-evolution engine. A Python code generator just failed these tests:

{failed_tests}

Based on ONLY these failures, return a JSON array of 3-5 short defense heuristics the generator \
should apply next round to fix these specific failures.

Rules:
- Each heuristic is a short string (max 10 words), e.g. "guard against None inputs before processing"
- Focus on the ROOT CAUSE of each failure
- Output ONLY a valid JSON array of strings. No explanation. No markdown.

Example: ["validate input types before use", "handle division by zero explicitly"]
"""

_BREAKER_EVOLVE_PROMPT = """\
You are a co-evolution engine. A code breaker just found these successful attacks \
(tests that CRASHED or FAILED the generator's code):

{successful_attacks}

Based on ONLY these successful attacks, return a JSON array of 3-5 new attack vector \
categories the breaker should escalate to next round.

Rules:
- Each vector is a short category label (max 6 words), e.g. "recursive_depth_explosion"
- Escalate the attacks that worked — probe deeper or find related edge cases
- Output ONLY a valid JSON array of strings. No explanation. No markdown.

Example: ["nested_structure_overflow", "unicode_boundary_injection"]
"""


def _get_client():
    global _client
    if _client is None:
        _client = get_client()
    return _client


def _extract_json_list(raw: str) -> list[str]:
    """Extract JSON array of strings; strip think blocks, fences, prose."""
    # strip Qwen3-style think block — safe even if unclosed
    stripped = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    if "<think>" in stripped:
        after = re.sub(r"<think>.*", "", stripped, flags=re.DOTALL).strip()
        stripped = after if after else raw  # fall back to full raw if empty
    # Strategy 1: scan FULL raw for fenced JSON (catches code inside unclosed <think>)
    fenced = list(re.finditer(r"```(?:json)?\s*\n?(.*?)```", raw, re.DOTALL))
    if fenced:
        candidate = fenced[-1].group(1).strip()
    else:
        candidate = stripped.strip()
    # Strategy 2: if no '[', search both stripped and full raw
    if not candidate.startswith("["):
        m = re.search(r"(\[.*?\])", candidate + raw, re.DOTALL)
        candidate = m.group(1) if m else "[]"
    try:
        result = json.loads(candidate)
        return [str(v) for v in result if v]
    except json.JSONDecodeError:
        return []


def _format_failed_tests(test_results: list[TestResult]) -> str:
    failed = [t for t in test_results if not t["passed"]]
    if not failed:
        return "None — all tests passed this round."
    lines = []
    for t in failed[:10]:  # cap at 10 to stay within token budget
        lines.append(
            f"  test_id={t['test_id']}  source={t['source']}"
            f"  input={t['input'][:80]}  expected={t['expected'][:40]}"
            f"  actual={t['actual'][:40]}  error={t.get('error_type','')}"
        )
    return "\n".join(lines)


def _format_successful_attacks(test_results: list[TestResult]) -> str:
    hits = [t for t in test_results if t["source"] == "adversarial" and not t["passed"]]
    if not hits:
        return "None — generator resisted all attacks this round."
    lines = []
    for t in hits[:10]:
        lines.append(
            f"  test_id={t['test_id']}  input={t['input'][:80]}"
            f"  error={t.get('error_type','')}"
        )
    return "\n".join(lines)


def _call_llm(prompt: str) -> list[str]:
    client = _get_client()
    raw = timed_completion(
        client,
        model=resolve_model(GROQ_MODEL),
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=512,
        **extra_kwargs(),
    )
    return _extract_json_list(raw)


def evolver_node(state: DPState) -> dict:
    condition: str = state["condition"]
    current_round: int = state["current_round"]
    test_results: list[TestResult] = state.get("test_results", [])
    gen_strategy: AgentStrategy = state["generator_strategy"]
    brk_strategy: AgentStrategy = state["breaker_strategy"]

    # --- Update Generator strategy ---
    failed_summary = _format_failed_tests(test_results)
    new_gen_vectors = _call_llm(
        _GENERATOR_EVOLVE_PROMPT.format(failed_tests=failed_summary)
    )
    updated_gen = AgentStrategy(
        round_num=current_round + 1,
        prompt_prefix=gen_strategy["prompt_prefix"],
        active_vectors=new_gen_vectors if new_gen_vectors else gen_strategy["active_vectors"],
        fingerprint=gen_strategy["fingerprint"],
    )

    # --- Update Breaker strategy (Condition C only) ---
    if condition == "C":
        attack_summary = _format_successful_attacks(test_results)
        new_brk_vectors = _call_llm(
            _BREAKER_EVOLVE_PROMPT.format(successful_attacks=attack_summary)
        )
        updated_brk = AgentStrategy(
            round_num=current_round + 1,
            prompt_prefix=brk_strategy["prompt_prefix"],
            active_vectors=new_brk_vectors if new_brk_vectors else brk_strategy["active_vectors"],
            fingerprint=brk_strategy["fingerprint"],
        )
    else:
        # Conditions A, B, D: breaker strategy unchanged
        updated_brk = AgentStrategy(
            round_num=current_round + 1,
            prompt_prefix=brk_strategy["prompt_prefix"],
            active_vectors=brk_strategy["active_vectors"],
            fingerprint=brk_strategy["fingerprint"],
        )

    return {
        "generator_strategy": updated_gen,
        "breaker_strategy":   updated_brk,
        "current_round":      current_round + 1,
    }
