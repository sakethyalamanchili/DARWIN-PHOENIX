"""
Experiment 3: Behavioral Fingerprinting — Statistical Analysis
Outputs results/exp3_statistical_report.txt
"""

import csv
import math
from collections import Counter, defaultdict
from pathlib import Path
from scipy import stats
import numpy as np

ROOT        = Path(__file__).parent.parent
RESULTS_CSV = ROOT / "results" / "exp3_results.csv"
REPORT_FILE = ROOT / "results" / "exp3_statistical_report.txt"


def wilson_ci(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z**2 / n
    c = (p + z**2 / (2 * n)) / d
    m = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / d
    return max(0.0, c - m), min(1.0, c + m)


def load():
    distance_rows = []
    final_rows    = []
    with RESULTS_CSV.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["round_num"] == "FINAL":
                final_rows.append(r)
            elif r["fingerprint_distance"] not in ("", "ERROR"):
                r["round_num"] = int(r["round_num"])
                r["fingerprint_distance"] = float(r["fingerprint_distance"])
                distance_rows.append(r)
    return distance_rows, final_rows


def main():
    dist_rows, final_rows = load()

    valid_finals = [r for r in final_rows if r["fingerprint_distance"] != "ERROR"]
    error_finals = [r for r in final_rows if r["fingerprint_distance"] == "ERROR"]

    n_tasks = len(valid_finals)
    af_counts = Counter(r["af_class"] for r in valid_finals)

    # Per-round distance stats
    rounds = sorted(set(r["round_num"] for r in dist_rows))
    round_dists = {rn: [r["fingerprint_distance"] for r in dist_rows if r["round_num"] == rn]
                   for rn in rounds}

    # Max drift per task (across all rounds)
    task_max = defaultdict(float)
    for r in dist_rows:
        task_max[r["task_id"]] = max(task_max[r["task_id"]], r["fingerprint_distance"])
    max_dists = list(task_max.values())

    # Kruskal-Wallis across rounds
    kw_H, kw_p = stats.kruskal(*[round_dists[rn] for rn in rounds if len(round_dists[rn]) > 1])

    # Drift > 0 rate
    all_dists = [r["fingerprint_distance"] for r in dist_rows if r["round_num"] > 1]
    nonzero   = sum(1 for d in all_dists if d > 0)

    lines = []
    lines.append("=" * 65)
    lines.append("DARWIN-PHOENIX  Experiment 3: Behavioral Fingerprinting")
    lines.append("Statistical Analysis Report")
    lines.append("=" * 65)
    lines.append("")
    lines.append(f"Tasks completed (valid): {n_tasks}")
    lines.append(f"Tasks errored:           {len(error_finals)}")
    lines.append(f"Error task IDs:          {[r['task_id'] for r in error_finals]}")
    lines.append("")
    lines.append("--- Outcome Distribution ---")
    for cls, cnt in sorted(af_counts.items()):
        pct = cnt / n_tasks * 100
        lo, hi = wilson_ci(cnt, n_tasks)
        lines.append(f"  {cls:12s}: {cnt:3d}/{n_tasks} ({pct:.1f}%)  95% CI [{lo:.3f}, {hi:.3f}]")
    lines.append("")
    lines.append("--- Fingerprint Distance by Round ---")
    lines.append(f"  {'Round':>6}  {'N':>4}  {'Mean':>7}  {'SD':>7}  {'Median':>7}  {'Min':>6}  {'Max':>6}")
    for rn in rounds:
        d = round_dists[rn]
        if not d:
            continue
        lines.append(f"  {rn:6d}  {len(d):4d}  {np.mean(d):7.4f}  {np.std(d):7.4f}  "
                     f"{np.median(d):7.4f}  {min(d):6.4f}  {max(d):6.4f}")
    lines.append("")
    lines.append(f"  Kruskal-Wallis across rounds: H={kw_H:.3f}, p={kw_p:.4f}"
                 + (" **" if kw_p < 0.01 else " *" if kw_p < 0.05 else " n.s."))
    lines.append("")
    lines.append("--- Drift Signal (rounds 2+) ---")
    lines.append(f"  Total distance measurements (R2+): {len(all_dists)}")
    lines.append(f"  Non-zero drift:  {nonzero}/{len(all_dists)} ({100*nonzero/max(len(all_dists),1):.1f}%)")
    lines.append(f"  Mean max drift per task: {np.mean(max_dists):.4f}")
    lines.append(f"  Median max drift:        {np.median(max_dists):.4f}")
    lines.append(f"  SD max drift:            {np.std(max_dists):.4f}")
    lines.append(f"  Range:                   {min(max_dists):.4f} - {max(max_dists):.4f}")
    lines.append("")

    # Spearman correlation: round number vs distance
    rn_vals = [r["round_num"] for r in dist_rows]
    fd_vals = [r["fingerprint_distance"] for r in dist_rows]
    rho, p_sp = stats.spearmanr(rn_vals, fd_vals)
    lines.append("--- Trend: Does drift increase with rounds? ---")
    lines.append(f"  Spearman rho(round, distance) = {rho:.4f}, p={p_sp:.4f}"
                 + (" **" if p_sp < 0.01 else " *" if p_sp < 0.05 else " n.s."))
    lines.append("")

    # Drift by af_class
    lines.append("--- Max Drift by af_class ---")
    class_max = defaultdict(list)
    for task_id, mx in task_max.items():
        af = next((r["af_class"] for r in valid_finals if r["task_id"] == task_id), "unknown")
        class_max[af].append(mx)
    for cls, vals in sorted(class_max.items()):
        lines.append(f"  {cls:12s}: n={len(vals):2d}  mean={np.mean(vals):.4f}  "
                     f"median={np.median(vals):.4f}  SD={np.std(vals):.4f}")

    if len(class_max) >= 2:
        cls_list = sorted(class_max.keys())
        groups   = [class_max[c] for c in cls_list if len(class_max[c]) > 1]
        if len(groups) >= 2:
            H2, p2 = stats.kruskal(*groups)
            lines.append(f"  Kruskal-Wallis (drift by class): H={H2:.3f}, p={p2:.4f}"
                         + (" **" if p2 < 0.01 else " *" if p2 < 0.05 else " n.s."))

    lines.append("")
    lines.append("=" * 65)
    lines.append("INTERPRETATION")
    lines.append("=" * 65)

    if kw_p < 0.05:
        lines.append("- Round has significant effect on fingerprint distance (K-W p<0.05).")
        lines.append("  Co-evolutionary pressure measurably shifts code generation strategy.")
    else:
        lines.append("- No significant round effect on fingerprint distance (K-W p>=0.05).")
        lines.append("  Generator strategy drift is not statistically detectable across rounds.")

    if rho > 0 and p_sp < 0.05:
        lines.append(f"- Positive trend: distance increases with round (rho={rho:.3f}, p={p_sp:.4f}).")
        lines.append("  Generator accumulates drift under sustained adversarial pressure.")
    elif p_sp >= 0.05:
        lines.append(f"- No monotonic round trend (rho={rho:.3f}, p={p_sp:.4f} n.s.).")

    degraded_n = af_counts.get("degraded", 0)
    correct_n  = af_counts.get("correct", 0)
    lines.append(f"- {degraded_n}/{n_tasks} tasks degraded under co-evolutionary pressure "
                 f"({100*degraded_n/n_tasks:.1f}%).")
    lines.append(f"- Mean max fingerprint drift: {np.mean(max_dists):.4f} "
                 f"(range {min(max_dists):.4f}-{max(max_dists):.4f}).")

    report = "\n".join(lines)
    print(report)
    REPORT_FILE.write_text(report, encoding="utf-8")
    print(f"\nReport saved to {REPORT_FILE}")


if __name__ == "__main__":
    main()
