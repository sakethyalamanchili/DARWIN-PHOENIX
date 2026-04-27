import json
import re
import subprocess
import textwrap
import tempfile
import os

from state import DPState, TestResult

# executor runs code in sandbox — no LLM prompt needed

DOCKER_IMAGE = "dp-sandbox"
SANDBOX_TIMEOUT = 5  # hard kill after 5 seconds per Masterbook Ch. 4 N4

# Template executed inside the Docker container — never in-process
_RUNNER_TEMPLATE = textwrap.dedent("""
import json, sys, ast, traceback

CODE = {code_repr}
TESTS = {tests_json}
ENTRY_POINT = {entry_point_repr}

exec(CODE, globals())
fn = globals()[ENTRY_POINT]

results = []
for test in TESTS:
    test_id  = test["test_id"]
    raw_inp  = test["input"]
    expected = test["expected"]
    source   = test["source"]
    actual_str  = ""
    passed      = False
    error_type  = None

    try:
        parsed = ast.literal_eval(raw_inp) if raw_inp.strip() else []
        if isinstance(parsed, list):
            actual = fn(*parsed)
        elif isinstance(parsed, dict):
            actual = fn(**parsed)
        else:
            actual = fn(parsed)
        actual_str = repr(actual)
        if expected == "":
            passed = True          # canonical test: pass if no exception
        else:
            passed = (actual_str == expected or str(actual) == expected)
    except Exception as exc:
        actual_str = repr(exc)
        error_type = type(exc).__name__
        # adversarial test passes if expected error type appears in expected
        passed = bool(expected and error_type and error_type in expected)

    results.append({{
        "test_id":    test_id,
        "input":      raw_inp,
        "expected":   expected,
        "actual":     actual_str,
        "passed":     passed,
        "source":     source,
        "error_type": error_type,
    }})

sys.stdout.write(json.dumps(results))
""")


def _entry_point_from_code(code: str) -> str:
    """Extract the first def name from the generated code."""
    m = re.search(r"def\s+(\w+)\s*\(", code)
    if not m:
        raise ValueError(f"No function definition found in code:\n{code[:200]}")
    return m.group(1)


def _build_test_dicts(tests: list[TestResult]) -> list[dict]:
    return [
        {
            "test_id":  t["test_id"],
            "input":    t["input"],
            "expected": t["expected"],
            "source":   t["source"],
        }
        for t in tests
    ]


def _run_in_sandbox(script: str) -> str:
    """
    Pipe script to docker run dp-sandbox python - via stdin.
    Hard 5-second timeout enforced via subprocess.run(timeout=SANDBOX_TIMEOUT).
    Network disabled; container runs as unprivileged sandboxuser.
    """
    cmd = [
        "docker", "run",
        "--rm",
        "--interactive",
        "--network", "none",
        "--memory", "256m",
        "--cpus", "0.5",
        DOCKER_IMAGE,
        "python", "-",
    ]
    try:
        proc = subprocess.run(
            cmd,
            input=script,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=SANDBOX_TIMEOUT,
        )
        return proc.stdout
    except subprocess.TimeoutExpired:
        return json.dumps([])   # timed out — return empty; caller marks all failed


def _parse_results(raw_stdout: str, all_tests: list[TestResult]) -> list[TestResult]:
    """Parse JSON output from sandbox; fall back to all-failed if malformed."""
    if not raw_stdout.strip():
        return [
            {**t, "actual": "TIMEOUT_OR_CRASH", "passed": False, "error_type": "ExecutionError"}
            for t in all_tests
        ]
    try:
        rows = json.loads(raw_stdout)
        return [
            TestResult(
                test_id=r["test_id"],
                input=r["input"],
                expected=r["expected"],
                actual=r["actual"],
                passed=r["passed"],
                source=r["source"],
                error_type=r.get("error_type"),
            )
            for r in rows
        ]
    except (json.JSONDecodeError, KeyError):
        return [
            {**t, "actual": "PARSE_ERROR", "passed": False, "error_type": "ParseError"}
            for t in all_tests
        ]


def executor_node(state: DPState) -> dict:
    code = state["current_code"]
    if not code.strip():
        return {"test_results": []}

    entry_point = _entry_point_from_code(code)
    all_tests = list(state.get("canonical_tests", [])) + list(state.get("adversarial_tests", []))

    if not all_tests:
        return {"test_results": []}

    test_dicts = _build_test_dicts(all_tests)
    script = _RUNNER_TEMPLATE.format(
        code_repr=repr(code),
        tests_json=json.dumps(test_dicts),
        entry_point_repr=repr(entry_point),
    )

    stdout = _run_in_sandbox(script)
    test_results = _parse_results(stdout, all_tests)

    return {"test_results": test_results}
