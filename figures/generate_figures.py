"""
Generate all paper figures for DARWIN-PHOENIX.
Outputs to figures/ directory.
Run: python figures/generate_figures.py
"""
import csv, math, collections
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec
from scipy import stats

ROOT = Path(__file__).parent.parent
FIG_DIR = ROOT / "figures"
FIG_DIR.mkdir(exist_ok=True)

# ── Palette ────────────────────────────────────────────────────────────────────
C_CORRECT  = "#2196F3"   # blue
C_DEGRADED = "#FF9800"   # orange
C_ERROR    = "#F44336"   # red
COND_COLORS = {"A": "#78909C", "B": "#AB47BC", "C": "#26A69A", "D": "#EF5350"}
FAULT_COLORS = {"hallucination": "#5C6BC0", "ctx_overflow": "#26A69A", "timeout": "#FFA726"}

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.titlesize": 11,
    "axes.labelsize": 10,
    "legend.fontsize": 9,
    "figure.dpi": 150,
    "axes.spines.top": False,
    "axes.spines.right": False,
})

# ══════════════════════════════════════════════════════════════════════════════
# Load data
# ══════════════════════════════════════════════════════════════════════════════
def load_exp1():
    rows = []
    with open(ROOT / "results/exp1_results.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            r["af_score"] = float(r["af_score"])
            rows.append(r)
    return rows

def load_exp2():
    rows = []
    with open(ROOT / "results/exp2_results.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            r["recovered"] = r["recovery_successful"] == "True"
            r["steps"] = int(r["recovery_steps"]) if r["recovery_steps"].strip() else None
            rows.append(r)
    return rows

def load_exp3():
    rows = []
    with open(ROOT / "results/exp3_results.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["round_num"] == "FINAL":
                continue
            if r["fingerprint_distance"] in ("", "ERROR"):
                continue
            r["round_num"] = int(r["round_num"])
            r["fingerprint_distance"] = float(r["fingerprint_distance"])
            rows.append(r)
    return rows

def wilson_ci(k, n, z=1.96):
    if n == 0: return 0, 0
    p = k/n; d = 1 + z**2/n
    c = (p + z**2/(2*n)) / d
    m = z * math.sqrt(p*(1-p)/n + z**2/(4*n**2)) / d
    return max(0, c-m), min(1, c+m)

e1 = load_exp1()
e2 = load_exp2()
e3 = load_exp3()

CONDITIONS = ["A", "B", "C", "D"]
FAULTS     = ["hallucination", "ctx_overflow", "timeout"]
COND_LABELS = {"A": "A\n(baseline)", "B": "B\n(corpus)", "C": "C\n(co-evol)", "D": "D\n(frozen)"}

# ══════════════════════════════════════════════════════════════════════════════
# FIGURE 1 — Experiment 1: Code Quality Across Conditions  (3 panels)
# ══════════════════════════════════════════════════════════════════════════════
fig1, axes = plt.subplots(1, 3, figsize=(13, 4.5))
fig1.suptitle("Figure 3 — Experiment 2: Code Quality Across Conditions\n"
              "(164 HumanEval+ tasks × 4 conditions, n=656 runs)", fontsize=12, y=1.01)

# Panel A: af_class stacked bar
ax = axes[0]
class_counts = {}
for cond in CONDITIONS:
    sub = [r for r in e1 if r["condition"] == cond]
    n = len(sub)
    class_counts[cond] = {
        "correct":  sum(1 for r in sub if r["af_class"] == "correct") / n,
        "degraded": sum(1 for r in sub if r["af_class"] == "degraded") / n,
        "ERROR":    sum(1 for r in sub if r["af_class"] == "ERROR") / n,
    }

x = np.arange(len(CONDITIONS))
bot = np.zeros(len(CONDITIONS))
for cls, color, label in [("correct", C_CORRECT, "Correct"), ("degraded", C_DEGRADED, "Degraded"), ("ERROR", C_ERROR, "Error")]:
    vals = [class_counts[c][cls] for c in CONDITIONS]
    ax.bar(x, vals, bottom=bot, color=color, label=label, width=0.55, edgecolor="white", linewidth=0.5)
    bot += np.array(vals)

ax.set_xticks(x)
ax.set_xticklabels([COND_LABELS[c] for c in CONDITIONS])
ax.set_ylabel("Proportion of runs")
ax.set_ylim(0, 1.05)
ax.set_title("A. Outcome distribution\nby condition")
ax.legend(loc="lower right", framealpha=0.8)
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))

# Panel B: degraded% with Wilson CI
ax = axes[1]
deg_rates, lo_errs, hi_errs = [], [], []
for cond in CONDITIONS:
    sub = [r for r in e1 if r["condition"] == cond]
    k = sum(1 for r in sub if r["af_class"] == "degraded")
    n = len(sub)
    rate = k/n
    lo, hi = wilson_ci(k, n)
    deg_rates.append(rate)
    lo_errs.append(rate - lo)
    hi_errs.append(hi - rate)

colors = [COND_COLORS[c] for c in CONDITIONS]
bars = ax.bar(x, deg_rates, color=colors, width=0.55, edgecolor="white", linewidth=0.5, zorder=3)
ax.errorbar(x, deg_rates, yerr=[lo_errs, hi_errs], fmt="none", color="black",
            capsize=4, linewidth=1.5, zorder=4)
ax.set_xticks(x)
ax.set_xticklabels([COND_LABELS[c] for c in CONDITIONS])
ax.set_ylabel("Degraded rate")
ax.set_title("B. Degraded output rate\nwith 95% Wilson CI")
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
ax.grid(axis="y", alpha=0.3, zorder=0)

# Panel C: af_score violin
ax = axes[2]
score_data = [[r["af_score"] for r in e1 if r["condition"] == c] for c in CONDITIONS]
vp = ax.violinplot(score_data, positions=x, widths=0.5, showmedians=True, showextrema=False)
for i, (body, cond) in enumerate(zip(vp["bodies"], CONDITIONS)):
    body.set_facecolor(COND_COLORS[cond])
    body.set_alpha(0.75)
vp["cmedians"].set_color("black"); vp["cmedians"].set_linewidth(2)
ax.set_xticks(x)
ax.set_xticklabels([COND_LABELS[c] for c in CONDITIONS])
ax.set_ylabel("AF score (0=correct, 1=total failure)")
ax.set_title("C. AF score distribution\nby condition")
ax.grid(axis="y", alpha=0.3)

# Significance annotation C vs B
y_max = max(max(d) for d in score_data if d) * 1.05
idx_b, idx_c = 1, 2
ax.annotate("", xy=(idx_c, y_max), xytext=(idx_b, y_max),
            arrowprops=dict(arrowstyle="-", color="black", lw=1.2))
sB = [r["af_score"] for r in e1 if r["condition"]=="B"]
sC = [r["af_score"] for r in e1 if r["condition"]=="C"]
_, p_kw = stats.kruskal(*score_data)
ax.text((idx_b+idx_c)/2, y_max*1.02,
        f"K-W p={p_kw:.3f}", ha="center", fontsize=8, color="black")

fig1.tight_layout()
out1 = FIG_DIR / "fig2_quality.png"
fig1.savefig(out1, dpi=180, bbox_inches="tight")
print(f"Saved {out1}")
plt.close(fig1)

# ══════════════════════════════════════════════════════════════════════════════
# FIGURE 2 — Experiment 2: Fault Recovery  (3 panels)
# ══════════════════════════════════════════════════════════════════════════════
fig2, axes = plt.subplots(1, 3, figsize=(13, 4.5))
fig2.suptitle("Figure 4 — Experiment 3: Fault Recovery Under Adversarial Stress\n"
              "(50 tasks × 2 conditions × 3 fault types, n=300 runs)", fontsize=12, y=1.01)

# Panel A: Recovery rate by condition × fault type (grouped bar)
ax = axes[0]
x_fault = np.arange(len(FAULTS))
width = 0.32
for i, cond in enumerate(["A","C"]):
    rates, lo_e, hi_e = [], [], []
    for fault in FAULTS:
        sub = [r for r in e2 if r["condition"]==cond and r["injected_failure_type"]==fault]
        k = sum(r["recovered"] for r in sub); n = len(sub)
        rate = k/n; lo, hi = wilson_ci(k, n)
        rates.append(rate); lo_e.append(rate-lo); hi_e.append(hi-rate)
    offset = (i - 0.5) * width
    bars = ax.bar(x_fault + offset, rates, width=width,
                  color=COND_COLORS[cond], label=f"Cond {cond}", edgecolor="white", linewidth=0.5)
    ax.errorbar(x_fault + offset, rates, yerr=[lo_e, hi_e],
                fmt="none", color="black", capsize=3, linewidth=1.2)

ax.set_xticks(x_fault)
ax.set_xticklabels(["Hallucination", "Ctx overflow", "Timeout"], fontsize=9)
ax.set_ylabel("Recovery rate")
ax.set_ylim(0.5, 1.02)
ax.set_title("A. Recovery rate\nby condition & fault type")
ax.legend(framealpha=0.8)
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
ax.grid(axis="y", alpha=0.3)

# Panel B: Recovery steps distribution by fault type (box plot)
ax = axes[1]
step_groups = []
for fault in FAULTS:
    g = [r["steps"] for r in e2 if r["injected_failure_type"]==fault
         and r["steps"] is not None and r["recovered"]]
    step_groups.append(g)

bp = ax.boxplot(step_groups, positions=np.arange(len(FAULTS)), patch_artist=True,
                widths=0.45, showfliers=True,
                medianprops=dict(color="black", linewidth=2))
for patch, fault in zip(bp["boxes"], FAULTS):
    patch.set_facecolor(FAULT_COLORS[fault]); patch.set_alpha(0.8)

ax.set_xticks(np.arange(len(FAULTS)))
ax.set_xticklabels(["Hallucination", "Ctx overflow", "Timeout"], fontsize=9)
ax.set_ylabel("Recovery steps")
ax.set_title("B. Recovery steps by fault type\n(Kruskal-Wallis p=0.005**)")
ax.grid(axis="y", alpha=0.3)

# Panel C: Overall recovery rate A vs C with CI
ax = axes[2]
conds_2 = ["A", "C"]
rates_all, lo_all, hi_all = [], [], []
for cond in conds_2:
    sub = [r for r in e2 if r["condition"]==cond]
    k = sum(r["recovered"] for r in sub); n = len(sub)
    rate = k/n; lo, hi = wilson_ci(k, n)
    rates_all.append(rate); lo_all.append(rate-lo); hi_all.append(hi-rate)

x2 = np.arange(2)
colors2 = [COND_COLORS[c] for c in conds_2]
ax.bar(x2, rates_all, color=colors2, width=0.45, edgecolor="white", linewidth=0.5, zorder=3)
ax.errorbar(x2, rates_all, yerr=[lo_all, hi_all],
            fmt="none", color="black", capsize=5, linewidth=1.5, zorder=4)
ax.set_xticks(x2)
ax.set_xticklabels(["Cond A\n(baseline)", "Cond C\n(co-evol)"])
ax.set_ylabel("Overall recovery rate")
ax.set_ylim(0.6, 1.02)
ax.set_title("C. Overall recovery rate\n(Fisher p=0.278, n.s.)")
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
ax.grid(axis="y", alpha=0.3, zorder=0)

# Annotate values
for xi, rate in zip(x2, rates_all):
    ax.text(xi, rate + 0.015, f"{rate:.1%}", ha="center", fontsize=10, fontweight="bold")

fig2.tight_layout()
out2 = FIG_DIR / "fig3_recovery.png"
fig2.savefig(out2, dpi=180, bbox_inches="tight")
print(f"Saved {out2}")
plt.close(fig2)

# ══════════════════════════════════════════════════════════════════════════════
# FIGURE 3 — Experiment 3: Behavioral Fingerprint Drift  (2 panels)
# ══════════════════════════════════════════════════════════════════════════════
# Avg fingerprint distance per round + distribution
fig3, axes = plt.subplots(1, 2, figsize=(10, 4.5))
fig3.suptitle("Figure 2 — Experiment 1: Behavioral Fingerprint Drift Across Rounds\n"
              "(Condition C only, co-evolutionary pressure)", fontsize=12, y=1.01)

rounds = sorted(set(r["round_num"] for r in e3))
round_data = {rn: [r["fingerprint_distance"] for r in e3 if r["round_num"]==rn] for rn in rounds}

# Panel A: mean ± SE per round
ax = axes[0]
means = [np.mean(round_data[rn]) for rn in rounds]
sems  = [np.std(round_data[rn])/math.sqrt(len(round_data[rn])) for rn in rounds]
ax.plot(rounds, means, "o-", color="#26A69A", linewidth=2, markersize=7, zorder=3)
ax.fill_between(rounds,
                [m-s for m,s in zip(means,sems)],
                [m+s for m,s in zip(means,sems)],
                alpha=0.2, color="#26A69A")
ax.set_xlabel("Round number")
ax.set_ylabel("Fingerprint distance (mean ± SE)")
ax.set_title("A. Fingerprint drift across rounds\n(higher = more diverse solutions)")
ax.set_xticks(rounds)
ax.grid(axis="y", alpha=0.3)

# Panel B: violin per round
ax = axes[1]
vdata = [round_data[rn] for rn in rounds]
vp = ax.violinplot(vdata, positions=rounds, widths=0.6, showmedians=True, showextrema=False)
for body in vp["bodies"]:
    body.set_facecolor("#26A69A"); body.set_alpha(0.6)
vp["cmedians"].set_color("black"); vp["cmedians"].set_linewidth(2)
ax.set_xlabel("Round number")
ax.set_ylabel("Fingerprint distance")
ax.set_title("B. Distribution of fingerprint distance\nper round")
ax.set_xticks(rounds)
ax.grid(axis="y", alpha=0.3)

# KW test across rounds
H, p_kw3 = stats.kruskal(*vdata)
ax.text(0.97, 0.97, f"K-W p={p_kw3:.3f}", transform=ax.transAxes,
        ha="right", va="top", fontsize=9,
        bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor="gray", alpha=0.8))

fig3.tight_layout()
out3 = FIG_DIR / "fig1_fingerprint.png"
fig3.savefig(out3, dpi=180, bbox_inches="tight")
print(f"Saved {out3}")
plt.close(fig3)

# ══════════════════════════════════════════════════════════════════════════════
# FIGURE 4 — Combined summary (1-page overview)
# ══════════════════════════════════════════════════════════════════════════════
fig4 = plt.figure(figsize=(14, 9))
gs = GridSpec(2, 3, figure=fig4, hspace=0.45, wspace=0.35)
fig4.suptitle("DARWIN-PHOENIX: Co-Evolutionary Code Generation — Summary Results",
              fontsize=13, fontweight="bold", y=1.01)

# Top-left: Exp1 af_class stacked bar
ax = fig4.add_subplot(gs[0, 0])
bot = np.zeros(len(CONDITIONS))
for cls, color, label in [("correct",C_CORRECT,"Correct"),("degraded",C_DEGRADED,"Degraded"),("ERROR",C_ERROR,"Error")]:
    vals = [class_counts[c][cls] for c in CONDITIONS]
    ax.bar(x, vals, bottom=bot, color=color, label=label, width=0.55, edgecolor="white")
    bot += np.array(vals)
ax.set_xticks(x); ax.set_xticklabels([COND_LABELS[c] for c in CONDITIONS], fontsize=8)
ax.set_title("Exp 2: Outcome distribution"); ax.set_ylabel("Proportion")
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v,_: f"{v:.0%}"))
ax.legend(fontsize=7, loc="lower right")

# Top-center: Exp1 degraded rate
ax = fig4.add_subplot(gs[0, 1])
ax.bar(x, deg_rates, color=colors, width=0.55, edgecolor="white", zorder=3)
ax.errorbar(x, deg_rates, yerr=[lo_errs, hi_errs], fmt="none", color="black", capsize=4, linewidth=1.5)
ax.set_xticks(x); ax.set_xticklabels([COND_LABELS[c] for c in CONDITIONS], fontsize=8)
ax.set_title("Exp 2: Degraded rate (95% CI)"); ax.set_ylabel("Degraded rate")
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v,_: f"{v:.0%}"))
ax.grid(axis="y", alpha=0.3)

# Top-right: Exp1 af_score violin
ax = fig4.add_subplot(gs[0, 2])
vp = ax.violinplot(score_data, positions=x, widths=0.5, showmedians=True, showextrema=False)
for body, cond in zip(vp["bodies"], CONDITIONS):
    body.set_facecolor(COND_COLORS[cond]); body.set_alpha(0.75)
vp["cmedians"].set_color("black"); vp["cmedians"].set_linewidth(2)
ax.set_xticks(x); ax.set_xticklabels([COND_LABELS[c] for c in CONDITIONS], fontsize=8)
ax.set_title(f"Exp 2: AF score (K-W p={p_kw:.3f})"); ax.set_ylabel("AF score")
ax.grid(axis="y", alpha=0.3)

# Bottom-left: Exp2 recovery by fault
ax = fig4.add_subplot(gs[1, 0])
for i, cond in enumerate(["A","C"]):
    rates_f, lo_f, hi_f = [], [], []
    for fault in FAULTS:
        sub=[r for r in e2 if r["condition"]==cond and r["injected_failure_type"]==fault]
        k=sum(r["recovered"] for r in sub); n=len(sub); rate=k/n; lo,hi=wilson_ci(k,n)
        rates_f.append(rate); lo_f.append(rate-lo); hi_f.append(hi-rate)
    offset=(i-0.5)*0.32
    ax.bar(x_fault+offset, rates_f, width=0.32, color=COND_COLORS[cond], label=f"Cond {cond}", edgecolor="white")
    ax.errorbar(x_fault+offset, rates_f, yerr=[lo_f,hi_f], fmt="none", color="black", capsize=3, linewidth=1)
ax.set_xticks(x_fault); ax.set_xticklabels(["Halluc.","Ctx ovf.","Timeout"], fontsize=8)
ax.set_title("Exp 3: Recovery rate"); ax.set_ylabel("Recovery rate"); ax.set_ylim(0.5,1.02)
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v,_: f"{v:.0%}"))
ax.legend(fontsize=7); ax.grid(axis="y", alpha=0.3)

# Bottom-center: Exp2 recovery steps boxplot
ax = fig4.add_subplot(gs[1, 1])
bp = ax.boxplot(step_groups, positions=np.arange(len(FAULTS)), patch_artist=True,
                widths=0.4, showfliers=False,
                medianprops=dict(color="black", linewidth=2))
for patch, fault in zip(bp["boxes"], FAULTS):
    patch.set_facecolor(FAULT_COLORS[fault]); patch.set_alpha(0.8)
ax.set_xticks(np.arange(len(FAULTS))); ax.set_xticklabels(["Halluc.","Ctx ovf.","Timeout"], fontsize=8)
ax.set_title("Exp 3: Recovery steps\n(K-W p=0.005**)"); ax.set_ylabel("Steps")
ax.grid(axis="y", alpha=0.3)

# Bottom-right: Exp3 fingerprint drift
ax = fig4.add_subplot(gs[1, 2])
ax.plot(rounds, means, "o-", color="#26A69A", linewidth=2, markersize=6)
ax.fill_between(rounds,[m-s for m,s in zip(means,sems)],[m+s for m,s in zip(means,sems)],
                alpha=0.2, color="#26A69A")
ax.set_xlabel("Round"); ax.set_ylabel("Fingerprint distance")
ax.set_title(f"Exp 1: Fingerprint drift\n(K-W p={p_kw3:.3f})")
ax.set_xticks(rounds); ax.grid(axis="y", alpha=0.3)

out4 = FIG_DIR / "fig4_summary.png"
fig4.savefig(out4, dpi=180, bbox_inches="tight")
print(f"Saved {out4}")
plt.close(fig4)

print("\nAll figures saved to figures/")
