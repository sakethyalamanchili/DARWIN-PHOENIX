import json
import os
import re

from dotenv import load_dotenv

from nodes.llm_client import get_client, resolve_model, extra_kwargs, timed_completion
from prompts import BREAKER
from state import DPState, TestResult

load_dotenv()

GROQ_MODEL = os.environ.get("BREAKER_MODEL", "qwen/qwen3-32b")
_client = None


def _get_client():
    global _client
    if _client is None:
        _client = get_client()
    return _client


def _strip_think(raw: str) -> str:
    """Remove Qwen3 <think>...</think> block; handle unclosed (truncated) block."""
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    if "<think>" in raw:
        after = re.sub(r"<think>.*", "", raw, flags=re.DOTALL).strip()
        raw = after if after else raw  # keep raw if stripping leaves nothing
    return raw


_PYTHON_EXPR_MAP = {
    r"\bsys\.maxsize\b": "9223372036854775807",
    r"\b-sys\.maxsize\s*-\s*1\b": "-9223372036854775808",
    r"\bfloat\('inf'\)": "1e308",
    r"\bfloat\('nan'\)": "null",
    r"\bNone\b": "null",
    r"\bTrue\b": "true",
    r"\bFalse\b": "false",
}


def _sanitize_json(s: str) -> str:
    """Replace Python literals/expressions with valid JSON equivalents."""
    for pattern, replacement in _PYTHON_EXPR_MAP.items():
        s = re.sub(pattern, replacement, s)
    return s


def _extract_json(raw: str) -> list[dict]:
    """Extract JSON array from LLM response; handles Qwen3 unclosed <think> blocks."""
    # Strategy 1: scan FULL raw (before any stripping) for fenced JSON arrays
    # Guard: empty/whitespace response (content filter or empty API reply)
    if not raw.strip():
        return []

    fenced = list(re.finditer(r"```(?:json)?\s*\n?(.*?)```", raw, re.DOTALL))
    if fenced:
        candidate = fenced[-1].group(1).strip()
    else:
        # Strategy 2: strip think, then look for [...]
        stripped = _strip_think(raw)
        arr_match = re.search(r"(\[.*?\])", stripped, re.DOTALL)
        candidate = arr_match.group(1) if arr_match else stripped.strip()

    # If still no "[", search full raw text for a JSON array
    if not candidate.startswith("["):
        arr_match = re.search(r"(\[.*?\])", raw, re.DOTALL)
        candidate = arr_match.group(1) if arr_match else candidate

    # If candidate still empty after all strategies, return empty gracefully
    if not candidate.strip():
        return []

    candidate = _sanitize_json(candidate)
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        # Partial parse: collect individually valid {...} objects from full raw
        objects = []
        for m in re.finditer(r"\{[^{}]+\}", raw, re.DOTALL):
            try:
                objects.append(json.loads(_sanitize_json(m.group())))
            except json.JSONDecodeError:
                continue
        if objects:
            return objects
        return []  # return empty instead of raising — run continues without adv tests


def _to_test_results(raw_tests: list[dict]) -> list[TestResult]:
    """Convert breaker JSON dicts to TestResult typed dicts."""
    results: list[TestResult] = []
    for i, t in enumerate(raw_tests):
        if not isinstance(t, dict):
            continue  # skip ints/strings the LLM occasionally returns
        results.append(TestResult(
            test_id=t.get("test_id", f"adv_{i:03d}"),
            input=str(t.get("input", "")),
            expected=str(t.get("expected", "")),
            actual="",       # filled by executor_node
            passed=False,    # filled by executor_node
            source="adversarial",
            error_type=None,
        ))
    return results


def breaker_node(state: DPState) -> dict:
    condition: str = state["condition"]
    current_round: int = state["current_round"]

    # Condition A: no adversarial testing
    if condition == "A":
        return {"adversarial_tests": []}

    # Condition D, Round 2+: replay frozen Round 1 tests unchanged
    if condition == "D" and current_round > 0:
        return {"adversarial_tests": state.get("adversarial_tests", [])}

    # All other conditions (B, C, D Round 1): call LLM
    # Truncate code to 60 lines to fit within model TPM limits for qwen3-32b (6K TPM)
    _code_lines = (state["current_code"] or "").splitlines()
    _code_for_prompt = "\n".join(_code_lines[:60])
    if len(_code_lines) > 60:
        _code_for_prompt += f"\n# ... ({len(_code_lines)-60} more lines truncated for brevity)"

    prompt = BREAKER.format(
        breaker_strategy_prompt_prefix=state["breaker_strategy"]["prompt_prefix"],
        current_code=_code_for_prompt,
        breaker_strategy_active_vectors=state["breaker_strategy"]["active_vectors"],
    )

    client = _get_client()
    raw = timed_completion(
        client,
        model=resolve_model(GROQ_MODEL),
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=1500,
        **extra_kwargs(),
    )
    raw_tests = _extract_json(raw)
    adversarial_tests = _to_test_results(raw_tests)

    return {"adversarial_tests": adversarial_tests}
