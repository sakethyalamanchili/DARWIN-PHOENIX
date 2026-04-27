import json
import os
import subprocess
import sys
import tempfile

from state import DPState, TestResult

# scorer computes metrics locally — no LLM prompt needed

DOCKER_IMAGE = "dp-sandbox"
SANDBOX_TIMEOUT = 10


def _build_coverage_script(code: str, test_dicts: list[dict], entry_point: str) -> str:
    """Return a self-contained Python script for the Docker sandbox.
    Avoids nested .format() by building the string with concatenation."""
    return "\n".join([
        "import json, sys, ast, subprocess, tempfile",
        f"CODE = {repr(code)}",
        f"TESTS = {json.dumps(test_dicts)}",
        f"ENTRY_POINT = {repr(entry_point)}",
        # write code to /tmp file
        "tmp = tempfile.NamedTemporaryFile(suffix='.py', mode='w', delete=False, dir='/tmp')",
        "tmp.write(CODE); tmp.flush(); tmp_path = tmp.name; tmp.close()",
        # write test list
        "with open('/tmp/tests.json', 'w') as _f: json.dump(TESTS, _f)",
        # build driver as concatenated string — no nested braces
        "driver  = 'import json, sys, ast, importlib.util\\n'",
        "driver += 'spec = importlib.util.spec_from_file_location(\"t\", \"' + tmp_path + '\")\\n'",
        "driver += 'mod = importlib.util.module_from_spec(spec)\\n'",
        "driver += 'spec.loader.exec_module(mod)\\n'",
        "driver += 'fn = getattr(mod, \"' + ENTRY_POINT + '\")\\n'",
        "driver += 'tests = json.load(open(\"/tmp/tests.json\"))\\n'",
        "driver += 'for t in tests:\\n'",
        "driver += '    try:\\n'",
        "driver += '        p = ast.literal_eval(t[\"input\"]) if t[\"input\"].strip() else []\\n'",
        "driver += '        fn(**p) if isinstance(p, dict) else fn(*p) if isinstance(p, list) else fn(p)\\n'",
        "driver += '    except Exception: pass\\n'",
        "with open('/tmp/driver.py', 'w') as _f: _f.write(driver)",
        # run coverage
        "subprocess.run(['python', '-m', 'coverage', 'run', '--branch',",
        "    '--include=' + tmp_path, '/tmp/driver.py'], capture_output=True)",
        "subprocess.run(['python', '-m', 'coverage', 'json', '-o', '/tmp/cov.json', '--quiet'],",
        "    capture_output=True)",
        # parse result
        "try:",
        "    d = json.load(open('/tmp/cov.json'))",
        "    files = d.get('files', {})",
        "    pct = list(files.values())[0]['summary']['percent_covered'] / 100.0 if files else 0.0",
        "except Exception: pct = 0.0",
        "sys.stdout.write(str(pct))",
    ])


def _run_bandit(code: str) -> int:
    """Run Bandit static analysis locally; return HIGH/MEDIUM issue count."""
    with tempfile.NamedTemporaryFile(
        suffix=".py", mode="w", delete=False, encoding="utf-8"
    ) as f:
        f.write(code)
        tmp_path = f.name
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "bandit", "-r", "-f", "json", tmp_path],
            capture_output=True, text=True, timeout=15,
        )
        data = json.loads(proc.stdout) if proc.stdout.strip() else {}
        return sum(
            1 for r in data.get("results", [])
            if r.get("issue_severity") in ("HIGH", "MEDIUM")
        )
    except (json.JSONDecodeError, subprocess.TimeoutExpired):
        return 0
    finally:
        os.unlink(tmp_path)


def _run_coverage(code: str, adv_tests: list[TestResult], entry_point: str) -> float:
    """Run coverage.py inside dp-sandbox; return branch coverage 0.0–1.0."""
    if not adv_tests:
        return 0.0
    test_dicts = [
        {"test_id": t["test_id"], "input": t["input"], "source": t["source"]}
        for t in adv_tests
    ]
    script = _build_coverage_script(code, test_dicts, entry_point)
    cmd = [
        "docker", "run", "--rm", "--interactive",
        "--network", "none", "--memory", "256m",
        DOCKER_IMAGE, "python", "-",
    ]
    try:
        proc = subprocess.run(
            cmd, input=script, capture_output=True,
            text=True, timeout=SANDBOX_TIMEOUT,
        )
        raw = proc.stdout.strip()
        return float(raw) if raw else 0.0
    except (subprocess.TimeoutExpired, ValueError):
        return 0.0


def _entry_point(code: str) -> str:
    import re
    m = re.search(r"def\s+(\w+)\s*\(", code)
    return m.group(1) if m else "unknown"


def scorer_node(state: DPState) -> dict:
    code: str = state.get("current_code", "")
    test_results: list[TestResult] = state.get("test_results", [])
    af_trajectory: list[float] = state.get("af_trajectory", [])

    canonical   = [t for t in test_results if t["source"] == "standard"]
    adversarial = [t for t in test_results if t["source"] == "adversarial"]

    # canonical_pass@k
    canonical_pass_at_k = (
        sum(1 for t in canonical if t["passed"]) / len(canonical)
        if canonical else 0.0
    )

    # bug_rate = canonical failure rate
    bug_rate = 1.0 - canonical_pass_at_k

    # adversarial_pass@k
    adversarial_pass_at_k = (
        sum(1 for t in adversarial if t["passed"]) / len(adversarial)
        if adversarial else 0.0
    )

    # adversarial_ratio: adversarial count / total test count
    total = len(canonical) + len(adversarial)
    adversarial_ratio = len(adversarial) / total if total else 0.0

    # combined_pass@k across all tests
    combined_pass_at_k = (
        sum(1 for t in test_results if t["passed"]) / len(test_results)
        if test_results else 0.0
    )

    # vuln_count via Bandit (static, local — no code execution)
    vuln_count = _run_bandit(code) if code.strip() else 0

    # edge_coverage via coverage.py inside Docker sandbox
    ep = _entry_point(code)
    adv_state_tests = state.get("adversarial_tests", [])
    edge_coverage = _run_coverage(code, adv_state_tests, ep) if code.strip() else 0.0

    # af_delta: base score minus previous round score
    prev_af_score = af_trajectory[-1] if af_trajectory else 0.0
    base_score = (
        0.35 * canonical_pass_at_k
        + 0.35 * adversarial_pass_at_k
        + 0.20 * adversarial_ratio
    )
    af_delta = base_score - prev_af_score

    # af_score: exact Masterbook Ch. 5 formula
    af_score = base_score + 0.10 * af_delta

    return {
        "bug_rate":           bug_rate,
        "vuln_count":         vuln_count,
        "edge_coverage":      edge_coverage,
        "combined_pass_at_k": combined_pass_at_k,
        "adversarial_ratio":  adversarial_ratio,
        "af_score":           af_score,
        "af_delta":           af_delta,
        "af_trajectory":      [af_score],  # Annotated operator.add — appends each round
    }
