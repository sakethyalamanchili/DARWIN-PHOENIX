"""
analysis.py

Reads experimental results from the `results/` directory and generates:
1. Average af_score across all 4 conditions (table & bar chart)
2. Recovery rate by failure type for Conditions A vs C (bar chart)
3. Fingerprint distance across rounds for Condition C (line graph)
4. Empirical Hypothesis Truth Table based on Masterbook Ch. 8

Usage:
  python analysis.py
  python analysis.py --mock  (Generate mock data if real data is missing)
"""

import argparse
import sys
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

# Setup plotting style
sns.set_theme(style="whitegrid", palette="muted")
plt.rcParams.update({'font.size': 12, 'figure.autolayout': True})

RESULTS_DIR = Path("results")
EXP1_FILE = RESULTS_DIR / "exp1_results.csv"
EXP2_FILE = RESULTS_DIR / "exp2_results.csv"
EXP3_FILE = RESULTS_DIR / "exp3_results.csv"
FIGURES_DIR = Path("figures")

def _generate_mock_data():
    """Generates mock CSVs to demonstrate what the plots look like."""
    print("Generating mock data...")
    RESULTS_DIR.mkdir(exist_ok=True)
    
    # Mock Exp 1
    exp1_data = []
    # Pattern to simulate: C > D > B > A (Adversarial pressure is the mechanism)
    means = {"A": 0.40, "B": 0.55, "C": 0.85, "D": 0.65}
    for cond in ["A", "B", "C", "D"]:
        for i in range(164):
            score = max(0.0, min(1.0, np.random.normal(loc=means[cond], scale=0.1)))
            exp1_data.append({"task_id": f"HumanEval/{i}", "condition": cond, "af_score": score})
    pd.DataFrame(exp1_data).to_csv(EXP1_FILE, index=False)

    # Mock Exp 2
    exp2_data = []
    # Condition C (antifragile) should heal better than A (baseline)
    rec_rates = {
        "A": {"hallucination": 0.2, "ctx_overflow": 0.3, "timeout": 0.1},
        "C": {"hallucination": 0.8, "ctx_overflow": 0.7, "timeout": 0.6}
    }
    for cond in ["A", "C"]:
        for ftype in ["hallucination", "ctx_overflow", "timeout"]:
             for i in range(164):
                 success = np.random.rand() < rec_rates[cond][ftype]
                 exp2_data.append({
                     "task_id": f"HumanEval/{i}", "condition": cond, 
                     "injected_failure_type": ftype, "recovery_successful": success
                 })
    pd.DataFrame(exp2_data).to_csv(EXP2_FILE, index=False)

    # Mock Exp 3
    exp3_data = []
    for i in range(164):
        rounds = np.random.randint(4, 11)
        for r in range(1, rounds+1):
            # Distance grows logarithmically as behavior diverges from Round 1
            dist = 0.0 if r == 1 else np.log(r) * 0.1 + np.random.normal(0, 0.05)
            dist = max(0.0, dist)
            exp3_data.append({
                "task_id": f"HumanEval/{i}", "condition": "C", 
                "round_num": r, "fingerprint_distance": dist
            })
    pd.DataFrame(exp3_data).to_csv(EXP3_FILE, index=False)


def analyze_exp1():
    print(f"\n{'='*60}\nExperiment 1: Baseline Antifragility\n{'='*60}")
    if not EXP1_FILE.exists():
        print(f"Missing {EXP1_FILE}")
        return None
    
    df = pd.read_csv(EXP1_FILE)
    if "af_score" not in df.columns:
        print("Invalid CSV schema.")
        return None

    # Calculate means
    scores = df.groupby("condition")["af_score"].mean().to_dict()
    
    print("\nAverage af_score locally across conditions:")
    for c in ["A", "B", "C", "D"]:
        v = scores.get(c, 0.0)
        print(f"  Condition {c}: {v:.4f}")

    # Plot
    plt.figure(figsize=(8, 5))
    ax = sns.barplot(x=list(scores.keys()), y=list(scores.values()), hue=list(scores.keys()), palette=["#d3d3d3", "#a8dadc", "#1d3557", "#457b9d"], order=["A", "B", "C", "D"], legend=False)
    plt.title("Average Antifragility (af_score) by Condition")
    plt.ylabel("af_score")
    plt.xlabel("Experimental Condition")
    plt.ylim(0, 1.0)
    for p in ax.patches:
        ax.annotate(format(p.get_height(), '.3f'), 
                    (p.get_x() + p.get_width() / 2., p.get_height()), 
                    ha = 'center', va = 'center', xytext = (0, 9), textcoords = 'offset points')
    
    out_file = FIGURES_DIR / "exp1_af_scores.png"
    plt.savefig(out_file)
    plt.close()
    print(f"Saved figure: {out_file}")
    
    return scores

def analyze_exp2():
    print(f"\n{'='*60}\nExperiment 2: Fault Injection Recovery (Chaos)\n{'='*60}")
    if not EXP2_FILE.exists():
        print(f"Missing {EXP2_FILE}")
        return

    df = pd.read_csv(EXP2_FILE)
    # Map string bools if necessary
    if df["recovery_successful"].dtype == object:
        df["recovery_successful"] = df["recovery_successful"].astype(str).str.lower() == "true"
    
    rates = df.groupby(["condition", "injected_failure_type"])["recovery_successful"].mean().reset_index()
    rates.rename(columns={"recovery_successful": "recovery_rate"}, inplace=True)
    
    print("\nRecovery Rates:")
    print(rates.to_string(index=False))

    plt.figure(figsize=(9, 6))
    ax = sns.barplot(data=rates, x="injected_failure_type", y="recovery_rate", hue="condition", palette=["#d3d3d3", "#1d3557"], order=["hallucination", "ctx_overflow", "timeout"])
    plt.title("Recovery Rate by Failure Type (Condition A vs C)")
    plt.ylabel("Recovery Rate (0 to 1)")
    plt.xlabel("Injected Failure Type")
    plt.ylim(0, 1.0)
    
    out_file = FIGURES_DIR / "exp2_recovery.png"
    plt.savefig(out_file)
    plt.close()
    print(f"Saved figure: {out_file}")

def analyze_exp3():
    print(f"\n{'='*60}\nExperiment 3: Behavioral Fingerprinting\n{'='*60}")
    if not EXP3_FILE.exists():
        print(f"Missing {EXP3_FILE}")
        return

    df = pd.read_csv(EXP3_FILE)
    # exclude the str 'FINAL' sentinels using numeric coercion
    df["round_num"] = pd.to_numeric(df["round_num"], errors='coerce')
    df = df.dropna(subset=["round_num"])
    
    # Calculate macro mean per round (dropping standard deviation in console, but plotting it)
    means = df.groupby("round_num")["fingerprint_distance"].mean().reset_index()
    print("\nAverage Fingerprint Distance per Round:")
    print(means.to_string(index=False))

    plt.figure(figsize=(9, 5))
    sns.lineplot(data=df, x="round_num", y="fingerprint_distance", marker="o", color="#1d3557", errorbar=('ci', 95))
    plt.title("Behavioral Drift (Cosine Distance from Round 1) across Rounds")
    plt.ylabel("TF-IDF Cosine Distance")
    plt.xlabel("Round Number")
    
    out_file = FIGURES_DIR / "exp3_fingerprint.png"
    plt.savefig(out_file)
    plt.close()
    print(f"Saved figure: {out_file}")

def interpret_truth_table(scores: dict):
    print(f"\n{'='*60}\nResearch Mechanism Interpretation (Chapter 8)\n{'='*60}")
    if not scores:
        print("No scores available from Exp 1.")
        return
        
    sA = scores.get("A", 0)
    sB = scores.get("B", 0)
    sC = scores.get("C", 0)
    sD = scores.get("D", 0)
    
    epsilon = 0.05  # threshold for equality (≈)
    
    def approx(a, b): return abs(a - b) <= epsilon

    print(f"Scores -> A: {sA:.3f} | B: {sB:.3f} | C: {sC:.3f} | D: {sD:.3f}")
    
    if approx(sC, sB) and sB > sA and sA > sD:
        pattern = "C ≈ B > A > D"
        conclusion = "Failure exposure is the primary mechanism. Hypothesis falsified."
    elif sC > sD and approx(sD, sB) and sB > sA:
        pattern = "C > D ≈ B > A"
        conclusion = "Adversarial pressure is the primary mechanism. Strong support for hypothesis."
    elif sC > sB and sB > sD and sD > sA:
        pattern = "C > B > D > A"
        conclusion = "Both matter, synergistic. Mechanisms are complementary."
    elif sC > sD and sD > sB and sB > sA:
        pattern = "C > D > B > A"
        conclusion = "Arms race alone is sufficient. Exposure alone insufficient; pressure drives improvement."
    else:
        pattern = "Uncategorized Pattern"
        # Determine dominant trait
        if sC > sB:
            conclusion = "Pressure heavily drives improvement (C > B)."
        else:
            conclusion = "Exposure is sufficient to match pressure (C = B)."

    print(f"\nObserved Pattern : {pattern}")
    print(f"Conclusion       : {conclusion}")
    print("="*60 + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mock", action="store_true", help="Generate mock CSVs before analyzing")
    args = parser.parse_args()
    
    FIGURES_DIR.mkdir(exist_ok=True)
    
    if args.mock:
        _generate_mock_data()
        
    scores = analyze_exp1()
    analyze_exp2()
    analyze_exp3()
    
    if scores:
        interpret_truth_table(scores)
