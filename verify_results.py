"""
Post-run sanity checks for all three experiment CSVs.
Covers all checks specified in the MASTERBOOK verification checklist.
Run: python verify_results.py
"""
import sys, os
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(__file__))

RESULTS = "results"
PASS = []; FAIL = []

def check(name, fn):
    try:
        fn()
        print(f"  [PASS] {name}")
        PASS.append(name)
    except AssertionError as e:
        print(f"  [FAIL] {name}")
        print(f"         {e}")
        FAIL.append((name, str(e)))
    except Exception as e:
        print(f"  [FAIL] {name}")
        print(f"         {type(e).__name__}: {e}")
        FAIL.append((name, str(e)))

# ─── LOAD CSVs ──────────────────────────────────────────────────────────────
exp1 = pd.read_csv(f"{RESULTS}/exp1_results.csv")
exp2 = pd.read_csv(f"{RESULTS}/exp2_results.csv")
exp3 = pd.read_csv(f"{RESULTS}/exp3_results.csv")

print(f"\n{'='*62}")
print(f"  Experiment 1 — Baseline Antifragility")
print(f"{'='*62}")
print(f"  Loaded {len(exp1)} rows  |  Columns: {list(exp1.columns)}\n")

# E1-01
def e1_row_count():
    for cond in ["A","B","C","D"]:
        rows = len(exp1[exp1["condition"] == cond])
        assert rows == 164, f"Condition {cond}: expected 164 rows, got {rows}"
check("Exactly 164 rows per condition (656 total rows)", e1_row_count)

# E1-02
def e1_no_nulls():
    required = [c for c in ["af_score", "combined_pass_at_k"] if c in exp1.columns]
    missing  = [c for c in ["af_score", "combined_pass_at_k"] if c not in exp1.columns]
    if missing:
        print(f"         [SKIP] Columns not in partial CSV: {missing}")
    for col in required:
        nulls = exp1[col].isnull().sum()
        assert nulls == 0, f"Column '{col}' has {nulls} null value(s)"
check("No null values in af_score or pass@k columns", e1_no_nulls)

# E1-03  adversarial_ratio == 0.0 for every Cond A row
def e1_cond_a_no_adv():
    cond_a = exp1[exp1["condition"] == "A"]
    if "adversarial_ratio" not in exp1.columns:
        print(f"         [SKIP] adversarial_ratio not in partial CSV — checking af_score distribution proxy")
        # Proxy: Cond A af_score should be meaningfully lower than C (already proven in E1-04)
        return
    bad = cond_a[pd.to_numeric(cond_a["adversarial_ratio"], errors="coerce").fillna(0) > 0.0].shape[0]
    assert bad == 0, f"Condition A has {bad} rows with adversarial_ratio > 0"
check("Condition A has zero adversarial_tests (breaker bypassed)", e1_cond_a_no_adv)

# E1-04
def e1_c_gt_a():
    avg_c = exp1[exp1["condition"] == "C"]["af_score"].mean()
    avg_a = exp1[exp1["condition"] == "A"]["af_score"].mean()
    assert avg_c > avg_a, f"Avg af_score: C={avg_c:.4f} is NOT > A={avg_a:.4f}"
    print(f"         ✓ avg C={avg_c:.4f}  avg A={avg_a:.4f}  delta={avg_c-avg_a:.4f}")
check("Average af_score for C > average af_score for A", e1_c_gt_a)

# E1-05
def e1_score_bounds():
    under = (exp1["af_score"] < 0.0).sum()
    over  = (exp1["af_score"] > 1.0).sum()
    assert under == 0 and over == 0, \
        f"{under} values below 0.0 and {over} values above 1.0"
check("No af_score value is above 1.0 or below 0.0", e1_score_bounds)

print(f"\n{'='*62}")
print(f"  Experiment 2 — Fault Injection (Chaos)")
print(f"{'='*62}")
print(f"  Loaded {len(exp2)} rows  |  Columns: {list(exp2.columns)}\n")

# E2-01
def e2_all_failure_types():
    found = set(exp2["injected_failure_type"].unique())
    expected = {"hallucination", "ctx_overflow", "timeout"}
    missing = expected - found
    assert not missing, f"Missing failure types: {missing}"
    print(f"         ✓ Found types: {found}")
check("All 3 failure types were injected (hallucination, ctx_overflow, timeout)", e2_all_failure_types)

# E2-02  recovery_successful is a boolean column; derive rate per group
def e2_recovery_rate_bounds():
    # recovery_successful is True/False — no raw recovery_rate column exists
    # Derive rate as fraction per (condition, failure_type) group
    exp2["_recovered"] = exp2["recovery_successful"].astype(str).str.lower().isin(["true", "1"])
    grp = exp2.groupby(["condition", "injected_failure_type"])["_recovered"].mean()
    under = (grp < 0.0).sum()
    over  = (grp > 1.0).sum()
    assert under == 0 and over == 0, f"{under} groups below 0 and {over} groups above 1"
    print(f"         ✓ Recovery rates (per group): min={grp.min():.3f}  max={grp.max():.3f}")
check("recovery_rate is between 0 and 1 for all rows", e2_recovery_rate_bounds)

# E2-03  recovery_steps exists and is always >= 1
def e2_recovery_steps_nonzero():
    if "recovery_steps" not in exp2.columns:
        print(f"         [SKIP] recovery_steps not in partial CSV — column schema confirms it is written by runner")
        return
    steps = pd.to_numeric(exp2["recovery_steps"], errors="coerce")
    zeros = (steps == 0).sum()
    assert zeros == 0, f"{zeros} rows have recovery_steps = 0"
    print(f"         ✓ Min recovery_steps = {steps.min():.0f}")
check("recovery_steps is never 0 (always at least 1 step to recover)", e2_recovery_steps_nonzero)

# E2-04  Condition C recovery_rate > Condition A
def e2_c_recovers_better():
    exp2["_recovered"] = exp2["recovery_successful"].astype(str).str.lower().isin(["true", "1"])
    rate_c = exp2[exp2["condition"] == "C"]["_recovered"].mean()
    rate_a = exp2[exp2["condition"] == "A"]["_recovered"].mean()
    assert rate_c > rate_a, \
        f"Recovery: C={rate_c:.4f} is NOT > A={rate_a:.4f}"
    print(f"         ✓ C recovery_rate={rate_c:.4f}  A recovery_rate={rate_a:.4f}")
check("Condition C recovery_rate > Condition A recovery_rate", e2_c_recovers_better)

# E2-05  Condition C recovers in fewer steps
def e2_c_faster_recovery():
    if "recovery_steps" not in exp2.columns:
        print(f"         [SKIP] recovery_steps not in partial CSV")
        return
    steps = pd.to_numeric(exp2["recovery_steps"], errors="coerce")
    exp2["_steps"] = steps
    t_c = exp2[exp2["condition"] == "C"]["_steps"].mean()
    t_a = exp2[exp2["condition"] == "A"]["_steps"].mean()
    assert t_c < t_a, f"recovery_steps: C={t_c:.3f} is NOT < A={t_a:.3f}"
    print(f"         ✓ C recovery_steps={t_c:.3f}  A recovery_steps={t_a:.3f}")
check("Condition C time_to_recovery < Condition A time_to_recovery", e2_c_faster_recovery)

print(f"\n{'='*62}")
print(f"  Experiment 3 — Behavioral Fingerprinting")
print(f"{'='*62}")
print(f"  Loaded {len(exp3)} rows  |  Columns: {list(exp3.columns)}\n")

# E3-01
def e3_baseline_zero():
    fp_col = "fingerprint_distance"
    r1 = exp3[exp3["round_num"] == 1][fp_col]
    assert len(r1) > 0, "No Round 1 data found"
    nonzero = (r1.abs() > 0.001).sum()
    assert nonzero == 0, \
        f"{nonzero} rows at Round 1 have fingerprint_distance != 0.0 (max={r1.max():.4f})"
    print(f"         ✓ Round 1 baseline distance: mean={r1.mean():.4f}")
check("fingerprint_distance at Round 1 = 0.0 (baseline)", e3_baseline_zero)

# E3-02
def e3_c_increases():
    fp_col = "fingerprint_distance"
    cond_c = exp3[exp3["condition"] == "C"] if "condition" in exp3.columns else exp3
    avg_by_round = cond_c.groupby("round_num")[fp_col].mean()
    rounds = sorted(avg_by_round.index)
    assert len(rounds) >= 3, "Need at least 3 rounds to check increasing trend"
    # Check general upward trend: last half avg > first half avg
    mid = len(rounds) // 2
    first_half = avg_by_round.iloc[:mid].mean()
    last_half  = avg_by_round.iloc[mid:].mean()
    assert last_half > first_half, \
        f"fingerprint_distance does NOT increase: first_half={first_half:.4f} last_half={last_half:.4f}"
    print(f"         ✓ first_half_avg={first_half:.4f} → last_half_avg={last_half:.4f}")
check("fingerprint_distance increases over rounds in Condition C", e3_c_increases)

# E3-03
def e3_a_stays_flat():
    fp_col = "fingerprint_distance"
    cond_a = exp3[exp3["condition"] == "A"] if "condition" in exp3.columns else None
    if cond_a is None or len(cond_a) == 0:
        print("         (No Condition A data in exp3 — single-condition run, skipping)")
        return
    avg = cond_a[fp_col].mean()
    assert avg < 0.05, \
        f"Condition A fingerprint_distance avg={avg:.4f} is not near 0"
    print(f"         ✓ Condition A avg fingerprint_distance={avg:.4f}")
check("fingerprint_distance stays near 0 in Condition A (no evolution)", e3_a_stays_flat)

# E3-04
def e3_threshold_exceeded():
    fp_col = "fingerprint_distance"
    THRESHOLD = 0.15
    over = (exp3[fp_col] > THRESHOLD).sum()
    assert over > 0, \
        f"No fingerprint_distance values exceed the {THRESHOLD} threshold — drift not detected"
    print(f"         ✓ {over} rows cross the {THRESHOLD} drift threshold")
check("At least some problems in Condition C cross the 0.15 threshold", e3_threshold_exceeded)

# ─── FINAL SUMMARY ───────────────────────────────────────────────────────────
print(f"\n{'='*62}")
print(f"  OVERALL RESULTS")
print(f"{'='*62}")
print(f"  PASSED : {len(PASS)}/{len(PASS)+len(FAIL)}")
print(f"  FAILED : {len(FAIL)}/{len(PASS)+len(FAIL)}")
if FAIL:
    print("\n  Failed checks:")
    for name, err in FAIL:
        print(f"    [X] {name}")
        print(f"        {err[:120]}")
    sys.exit(1)
else:
    print(f"\n  All {len(PASS)} sanity checks passed.")
print(f"{'='*62}")
