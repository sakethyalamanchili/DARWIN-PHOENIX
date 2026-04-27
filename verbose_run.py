"""
verbose_run.py — Full lifecycle trace for one HumanEval problem, Condition C.

Hooks into every LangGraph node via stream(), printing a rich state diff at
each step so you can follow every round from generator → terminator.

Usage:
    python verbose_run.py [task_id]   e.g.  python verbose_run.py HumanEval/0
"""

import sys, os, textwrap, time, re
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from graph import darwin_phoenix
from state import DPState, AgentStrategy
from nodes.initialize import initialize_node

# ─── Colours (Windows-safe via ANSI – works in Windows Terminal / VS Code) ───
C_RESET  = "\033[0m"
C_BOLD   = "\033[1m"
C_CYAN   = "\033[96m"
C_GREEN  = "\033[92m"
C_YELLOW = "\033[93m"
C_RED    = "\033[91m"
C_GREY   = "\033[90m"
C_BLUE   = "\033[94m"
C_PURPLE = "\033[95m"

COND_COLOR = {"A": C_GREY, "B": C_BLUE, "C": C_GREEN, "D": C_YELLOW}

def _w(text, width=88):
    """Wrap long text for terminal."""
    return textwrap.fill(str(text), width=width, subsequent_indent="      ")

def _code_snippet(code: str, n=8) -> str:
    lines = [l for l in (code or "").splitlines() if l.strip()]
    snippet = "\n".join(f"      {l}" for l in lines[:n])
    if len(lines) > n:
        snippet += f"\n      {C_GREY}... (+{len(lines)-n} more lines){C_RESET}"
    return snippet or "      (empty)"

def _fmt_tests(tests: list) -> str:
    if not tests:
        return "      (none)"
    lines = []
    for t in tests[:6]:
        icon = "✓" if t.get("passed") else "✗"
        src  = t.get("source","?")[0].upper()
        err  = f"  {C_RED}{t.get('error_type','')}{C_RESET}" if not t.get("passed") else ""
        lines.append(f"      [{src}] {icon}  {t.get('test_id','?'):<18} "
                     f"in={str(t.get('input',''))[:25]:<25}{err}")
    if len(tests) > 6:
        lines.append(f"      ... +{len(tests)-6} more tests")
    return "\n".join(lines)

def _gate_bar(label: str, value: float, threshold: float, higher_ok=True) -> str:
    ok = value >= threshold if higher_ok else value <= threshold
    icon = f"{C_GREEN}✓{C_RESET}" if ok else f"{C_RED}✗{C_RESET}"
    bar_len = 20
    filled = int(value * bar_len)
    bar = "█" * filled + "░" * (bar_len - filled)
    thr_pos = int(threshold * bar_len)
    bar = bar[:thr_pos] + C_YELLOW + "|" + C_RESET + bar[thr_pos+1:]
    return f"      {icon}  {label:<28} {value:5.3f}  [{bar}]  thr={threshold}"

# ─── Node display handlers ─────────────────────────────────────────────────

def show_generator(state: dict, prev: dict):
    code    = state.get("current_code", "")
    n       = len(state.get("code_versions", []))
    rnd     = state.get("current_round", "?")
    print(f"\n  {C_CYAN}generator{C_RESET}  → code v{n} generated  "
          f"({len(code)} chars,  round={rnd})")
    print(_code_snippet(code))

def show_breaker(state: dict, prev: dict):
    tests = state.get("adversarial_tests", [])
    vectors = state.get("breaker_strategy", {}).get("active_vectors", [])
    frozen  = state.get("breaker_strategy_frozen", False)
    tag = f"{C_YELLOW}[FROZEN]{C_RESET}" if frozen else ""
    print(f"\n  {C_CYAN}breaker{C_RESET}    → {len(tests)} adversarial tests generated {tag}")
    if vectors:
        print(f"      vectors: {', '.join(str(v) for v in vectors[:5])}")
    # Show first 3 test IDs + rationale if present
    for t in (tests or [])[:3]:
        rat = t.get("rationale","")[:60]
        print(f"      · {t.get('test_id','?'):<20}  {C_GREY}{rat}{C_RESET}")

def show_executor(state: dict, prev: dict):
    results  = state.get("test_results", [])
    canon    = [t for t in results if t.get("source") == "standard"]
    adv      = [t for t in results if t.get("source") == "adversarial"]
    c_pass   = sum(1 for t in canon if t.get("passed"))
    a_pass   = sum(1 for t in adv  if t.get("passed"))
    a_fail   = len(adv) - a_pass
    icon_c = C_GREEN if c_pass == len(canon) else C_RED
    icon_a = C_GREEN if a_fail == 0 else C_YELLOW
    print(f"\n  {C_CYAN}executor{C_RESET}   → canonical: "
          f"{icon_c}{c_pass}/{len(canon)} pass{C_RESET}   "
          f"adversarial: {icon_a}{a_pass}/{len(adv)} pass  "
          f"({C_RED}{a_fail} failed{C_RESET})")
    print(_fmt_tests(results))

def show_scorer(state: dict, prev: dict):
    af_score  = state.get("af_score",  0.0)
    af_delta  = state.get("af_delta",  0.0)
    cov       = state.get("edge_coverage", 0.0)
    vuln      = state.get("vuln_count", 0)
    adv_ratio = state.get("adversarial_ratio", 0.0)
    delta_str = f"+{af_delta:.4f}" if af_delta >= 0 else f"{af_delta:.4f}"
    delta_col = C_GREEN if af_delta > 0 else C_RED
    vuln_col  = C_RED if vuln > 0 else C_GREEN
    print(f"\n  {C_CYAN}scorer{C_RESET}     → "
          f"af_score: {C_BOLD}{af_score:.4f}{C_RESET}   "
          f"af_delta: {delta_col}{delta_str}{C_RESET}   "
          f"vuln: {vuln_col}{vuln}{C_RESET}   "
          f"cov: {cov:.3f}   adv_ratio: {adv_ratio:.3f}")

def show_evolver(state: dict, prev: dict):
    gen_new = state.get("generator_strategy", {}).get("active_vectors", [])
    brk_new = state.get("breaker_strategy",  {}).get("active_vectors", [])
    gen_old = (prev or {}).get("generator_strategy", {}).get("active_vectors", [])
    brk_old = (prev or {}).get("breaker_strategy",  {}).get("active_vectors", [])

    gen_added = [v for v in gen_new if v not in gen_old]
    brk_added = [v for v in brk_new if v not in brk_old]

    print(f"\n  {C_CYAN}evolver{C_RESET}    → generator strategies:  "
          f"{C_GREEN}{', '.join(str(v) for v in gen_new[:4])}{C_RESET}")
    if gen_added:
        print(f"               {C_GREEN}+ NEW:{C_RESET} {', '.join(str(v) for v in gen_added)}")
    if brk_added:
        print(f"               breaker  {C_YELLOW}+ NEW:{C_RESET} {', '.join(str(v) for v in brk_added)}")
    rnd = state.get("current_round", "?")
    print(f"               {C_GREY}current_round → {rnd}{C_RESET}")

def show_terminator(state: dict, prev: dict):
    af_class  = state.get("af_class", "?")
    reason    = state.get("termination_reason", "")
    rnd       = state.get("current_round", "?")
    max_r     = state.get("max_rounds", "?")
    af_delta  = state.get("af_delta",  0.0)
    cov       = state.get("edge_coverage", 0.0)
    vuln      = state.get("vuln_count", 0)
    results   = state.get("test_results", [])
    canon_k   = sum(1 for t in results if t.get("source")=="standard" and t.get("passed")) / max(1, sum(1 for t in results if t.get("source")=="standard"))
    adv_k     = sum(1 for t in results if t.get("source")=="adversarial" and t.get("passed")) / max(1, sum(1 for t in results if t.get("source")=="adversarial"))

    CLASS_COLOR = {
        "antifragile": C_GREEN + C_BOLD,
        "correct":     C_YELLOW,
        "pending":     C_BLUE,
        "degraded":    C_RED + C_BOLD,
    }
    col = CLASS_COLOR.get(af_class, C_RESET)

    print(f"\n  {C_CYAN}terminator{C_RESET} → 7-gate evaluation  (round {rnd}/{max_r})")
    print(_gate_bar("G1 Syntax OK",            1.0,   1.0))
    print(_gate_bar("G2 Canonical pass@k",     canon_k, 1.0))
    print(_gate_bar("G3 Security (0 vulns)",   1.0 if vuln==0 else 0.0, 1.0))
    print(_gate_bar("G4 Adversarial pass@k",   adv_k,   0.80))
    print(_gate_bar("G5 Delta improvement",    abs(af_delta), 0.05))
    print(_gate_bar("G6 Edge coverage",        cov,     0.75))
    print(f"\n      af_class : {col}{af_class.upper()}{C_RESET}")
    if reason:
        print(f"      reason   : {C_GREY}{reason}{C_RESET}")
    if af_class == "antifragile":
        print(f"\n  {C_GREEN}{C_BOLD}  ✅  ALL 7 GATES PASS → ANTIFRAGILE{C_RESET}\n")
    elif af_class == "pending":
        print(f"      ↻  looping → round {int(rnd)+1 if str(rnd).isdigit() else '?'}")

# ─── Node dispatch map ─────────────────────────────────────────────────────

NODE_HANDLERS = {
    "generator":  show_generator,
    "breaker":    show_breaker,
    "executor":   show_executor,
    "scorer":     show_scorer,
    "evolver":    show_evolver,
    "terminator": show_terminator,
}

# ─── Main run ──────────────────────────────────────────────────────────────

def run_verbose(task_id: str = "HumanEval/0", condition: str = "C", max_rounds: int = 10):
    # Build initial state via initialize_node (loads real HumanEval problem)
    seed: DPState = {
        "task_id": task_id, "condition": condition, "max_rounds": max_rounds,
        "current_round": 0, "problem_spec": "", "function_signature": "",
        "canonical_tests": [], "current_code": "", "code_versions": [],
        "generator_strategy": AgentStrategy(round_num=0, prompt_prefix="", active_vectors=[], fingerprint=""),
        "breaker_strategy":   AgentStrategy(round_num=0, prompt_prefix="", active_vectors=[
            "integer_overflow","empty_input","type_confusion",
            "boundary_values","unicode_injection","deep_nesting",
        ], fingerprint=""),
        "breaker_strategy_frozen": False,
        "adversarial_tests": [], "test_results": [],
        "combined_pass_at_k": 0.0, "adversarial_ratio": 0.0,
        "bug_rate": 0.0, "edge_coverage": 0.0, "vuln_count": 0,
        "af_score": 0.0, "af_delta": 0.0, "af_trajectory": [],
        "consecutive_improvement": 0, "af_class": "pending",
        "termination_reason": "", "probe_tasks": [], "probe_fingerprint": [],
        "failure_corpus": [], "injection_active": False,
        "injected_failure_type": "none", "recovery_successful": False, "recovery_steps": 0,
    }

    banner = f" DARWIN-PHOENIX  |  Task: {task_id}  |  Condition: {condition}  |  max_rounds: {max_rounds} "
    print("\n" + "═" * 70)
    print(f"{C_BOLD}{banner}{C_RESET}")
    print("═" * 70)

    prev_state:  dict = {}
    cumulative:  dict = dict(seed)   # running merged state
    current_round    = -1
    t0               = time.time()

    for step in darwin_phoenix.stream(seed):
        node_name = list(step.keys())[0]
        delta     = list(step.values())[0]

        # Merge delta into cumulative (LangGraph only yields changed fields)
        # For list fields with Annotated[list, operator.add] reducers, append.
        for k, v in delta.items():
            if isinstance(v, list) and k in ("code_versions", "test_results",
                                              "af_trajectory", "probe_fingerprint"):
                cumulative[k] = cumulative.get(k, []) + v
            else:
                cumulative[k] = v
        state = cumulative

        # Round header
        rnd = state.get("current_round", 0)
        if node_name == "generator" and rnd != current_round:
            current_round = rnd
            elapsed = time.time() - t0
            print(f"\n{'─'*70}")
            print(f"{C_BOLD}  Round {rnd}   "
                  f"{C_GREY}(elapsed: {elapsed:.1f}s){C_RESET}")
            print(f"{'─'*70}")

        handler = NODE_HANDLERS.get(node_name)
        if handler:
            handler(state, prev_state)
        else:
            print(f"\n  {C_CYAN}{node_name}{C_RESET}")

        prev_state = dict(state)

    total = time.time() - t0
    final_class  = prev_state.get("af_class", "?")
    final_reason = prev_state.get("termination_reason", "")
    final_score  = prev_state.get("af_score", 0.0)
    final_round  = prev_state.get("current_round", "?")

    CLASS_COLOR = {"antifragile": C_GREEN+C_BOLD, "correct": C_YELLOW,
                   "pending": C_BLUE, "degraded": C_RED+C_BOLD}
    col = CLASS_COLOR.get(final_class, C_RESET)

    print(f"\n{'═'*70}")
    print(f"{C_BOLD}  FINAL RESULT{C_RESET}")
    print(f"  af_class  : {col}{final_class.upper()}{C_RESET}")
    print(f"  af_score  : {final_score:.4f}")
    print(f"  rounds    : {final_round}/{max_rounds}")
    print(f"  reason    : {C_GREY}{final_reason}{C_RESET}")
    print(f"  wall time : {total:.1f}s")
    print(f"{'═'*70}\n")


if __name__ == "__main__":
    task = sys.argv[1] if len(sys.argv) > 1 else "HumanEval/0"
    run_verbose(task_id=task, condition="C", max_rounds=10)
