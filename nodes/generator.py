import os
import re
from dotenv import load_dotenv

from nodes.llm_client import get_client, resolve_model, extra_kwargs, timed_completion
from prompts import GENERATOR_ROUND_0, GENERATOR_ROUND_N
from state import DPState, TestResult

load_dotenv()

GROQ_MODEL = os.environ.get("GENERATOR_MODEL", "qwen/qwen3-32b")
_client = None


def _get_client():
    global _client
    if _client is None:
        _client = get_client()
    return _client


def _clip_to_function(code: str) -> str:
    """Clip text starting with 'def' to just the function body.

    Stops at the first non-indented, non-blank line that appears after the
    function body has started. This strips thinking prose Qwen3 appends after
    the function definition inside <think> blocks.
    """
    lines = code.splitlines()
    result = []
    body_started = False
    for line in lines:
        stripped = line.lstrip()
        is_indented = bool(line) and line[0] in (" ", "\t")
        is_blank = not stripped

        if not result:          # always keep the first def line
            result.append(line)
            continue

        if is_indented:
            body_started = True
            result.append(line)
        elif is_blank:
            result.append(line)
        elif body_started:
            break               # non-indented content after body = end of fn
        else:
            result.append(line) # decorators / from-imports before body

    return "\n".join(result).rstrip()


def _extract_code(raw: str) -> str:
    """Strip <think> blocks and markdown fences; return bare Python function.

    Handles three Qwen3 response shapes:
      1. <think>...</think>\n```python\ndef fn(): ...\n```
      2. <think>...</think>\ndef fn(): ...  (no fence)
      3. <think>unclosed — full response is thinking, code embedded inside
    """
    # ── Strategy 1: find the last ```python...``` fence in the FULL raw text
    # (works even if <think> is unclosed because Qwen3 sometimes writes the
    #  code fence inside the thinking block before it ends)
    fenced_all = list(re.finditer(r"```(?:python)?\s*\n(.*?)```", raw, re.DOTALL))
    if fenced_all:
        return fenced_all[-1].group(1).strip()

    # -- Strategy 2: strip closed <think>...</think> then look for def
    stripped = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    if stripped:
        m = re.search(r"(def \w+.*)", stripped, re.DOTALL)
        if m:
            return _clip_to_function(m.group(1).strip())

    # -- Strategy 3: unclosed <think> -- search ENTIRE raw text for a def
    m = re.search(r"(def \w+.*)", raw, re.DOTALL)
    if m:
        return _clip_to_function(m.group(1).strip())

    return raw.strip()

def _build_failed_tests_summary(failed: list[TestResult]) -> str:
    lines = []
    for t in failed:
        lines.append(
            f"  test_id={t['test_id']}  input={t['input']}  "
            f"expected={t['expected']}  actual={t['actual']}  "
            f"error={t.get('error_type', 'None')}"
        )
    return "\n".join(lines) if lines else "None"


def _build_corpus_summary(corpus: list[dict], n: int = 2) -> str:
    """Inject up to n failure_corpus examples into Round N+ prompt (Condition B)."""
    lines = []
    for entry in corpus[:n]:
        lines.append(
            f"  [{entry['corpus_id']}] {entry['description']}\n"
            f"    Code:    {entry['code_snippet']}\n"
            f"    Failure: {entry['failure_mode']}\n"
            f"    Lesson:  {entry['lesson']}"
        )
    return "\n".join(lines) if lines else "None"


def generator_node(state: DPState) -> dict:
    client = _get_client()
    current_round: int = state["current_round"]
    condition: str = state["condition"]

    if current_round == 0:
        prompt = GENERATOR_ROUND_0.format(
            problem_spec=state["problem_spec"],
            function_signature=state["function_signature"],
        )
    else:
        # Condition B: use failure_corpus instead of adversarial test failures
        if condition == "B":
            failed_summary = _build_corpus_summary(state.get("failure_corpus", []))
        else:
            failed = [t for t in state.get("test_results", []) if not t["passed"]]
            failed_summary = _build_failed_tests_summary(failed)

        prompt = GENERATOR_ROUND_N.format(
            current_round=current_round,
            problem_spec=state["problem_spec"],
            function_signature=state["function_signature"],
            generator_strategy_prompt_prefix=state["generator_strategy"]["prompt_prefix"],
            failed_tests_summary=failed_summary,
            generator_strategy_active_vectors=state["generator_strategy"]["active_vectors"],
        )

    import ast as _ast

    _GEN_RETRIES = 3
    code = ""
    for _attempt in range(_GEN_RETRIES):
        raw = timed_completion(
            client,
            model=resolve_model(GROQ_MODEL),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=1500,
            **extra_kwargs(),
        )
        code = _extract_code(raw)
        # Validate syntax — if extraction grabbed thinking prose, retry with tighter search
        try:
            _ast.parse(code)
        except SyntaxError:
            fence_m = re.findall(r"```python\s*\n(.*?)```", raw, re.DOTALL)
            if fence_m:
                code = fence_m[-1].strip()
            else:
                lines_raw = raw.splitlines()
                for ln in reversed(lines_raw):
                    if ln.startswith("def ") or ln.startswith("from typing"):
                        idx = raw.rfind(ln)
                        code = _clip_to_function(raw[idx:].strip())
                        break
        # Sanitize: strip non-ASCII chars that break Windows cp1252 subprocess stdin pipes
        code = code.encode("ascii", errors="ignore").decode("ascii")
        if code.strip():
            break  # got valid non-empty code

    return {
        "current_code": code,
        "code_versions": [code],  # Annotated[List[str], operator.add] — appends
    }
