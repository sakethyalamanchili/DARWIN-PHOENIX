"""
Generate DARWIN-PHOENIX system architecture figure.
Output: figures/fig_architecture.png
Run: python figures/generate_architecture.py
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from pathlib import Path

OUT = Path(__file__).parent / "fig_architecture.png"

FW, FH = 7.0, 13.5
fig, ax = plt.subplots(figsize=(FW, FH))
ax.set_xlim(0, FW); ax.set_ylim(0, FH)
ax.axis("off")
fig.patch.set_facecolor("white")
ax.set_facecolor("white")

CX   = FW / 2      # center x of main column
NW   = 5.2         # node width
LX   = CX - NW/2  # left edge of nodes

# ── Colours ──────────────────────────────────────────────────────────────────
C = {
    "io":   ("#ECEFF1", "#607D8B", "#263238"),
    "init": ("#FAFAFA", "#90A4AE", "#37474F"),
    "gen":  ("#E8F5E9", "#388E3C", "#1B5E20"),
    "brk":  ("#FCE4EC", "#D32F2F", "#880E4F"),
    "eval": ("#E3F2FD", "#1976D2", "#0D47A1"),
    "term": ("#FFF8E1", "#F57C00", "#E65100"),
    "rt":   ("#EDE7F6", "#7B1FA2", "#4527A0"),
}

# ── Helper: draw rounded box ──────────────────────────────────────────────────
def box(yc, h, role, title, lines, pad=0.18):
    fill, edge, tc = C[role]
    lw = 2.0 if role in ("gen", "brk") else 1.5
    b = FancyBboxPatch((LX, yc - h/2), NW, h,
                        boxstyle=f"round,pad={pad}",
                        facecolor=fill, edgecolor=edge,
                        linewidth=lw, zorder=3)
    ax.add_patch(b)
    # Title
    n_body = len(lines)
    spacing = 0.30
    total   = (n_body) * spacing
    ty_title = yc + total / 2 + 0.05
    ax.text(CX, ty_title, title, ha="center", va="center",
            fontsize=9.5, fontweight="bold", color=tc, zorder=4)
    for i, ln in enumerate(lines):
        ty = ty_title - spacing * (i + 1)
        ax.text(CX, ty, ln, ha="center", va="center",
                fontsize=8.2, color=tc, zorder=4)
    return yc - h/2, yc + h/2   # bottom, top

def io_box(yc, h, text):
    fill, edge, tc = C["io"]
    b = FancyBboxPatch((LX + 0.3, yc - h/2), NW - 0.6, h,
                        boxstyle="round,pad=0.18",
                        facecolor=fill, edgecolor=edge,
                        linewidth=2, zorder=3)
    ax.add_patch(b)
    ax.text(CX, yc, text, ha="center", va="center",
            fontsize=9, color=C["io"][2], fontweight="bold", zorder=4)
    return yc - h/2, yc + h/2

def arrow(x1, y1, x2, y2, label=None, dashed=False, color="#546E7A", lw=1.4):
    ls = (0, (5, 4)) if dashed else "solid"
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(
                    arrowstyle="-|>",
                    color=color, lw=lw,
                    linestyle=ls,
                    mutation_scale=14,
                    connectionstyle="arc3,rad=0.0"),
                zorder=5)
    if label:
        mx, my = (x1+x2)/2, (y1+y2)/2
        ax.text(mx + 0.15, my, label, fontsize=7.5, color="#546E7A",
                ha="left", va="center", zorder=6,
                bbox=dict(facecolor="white", edgecolor="#B0BEC5",
                          boxstyle="round,pad=0.2", alpha=0.95))

def side_arrow(x, y_from, y_to, label=None, dashed=False, side="right",
               color="#546E7A"):
    """Vertical arrow on the side for loop-backs."""
    ox = x + (0.45 if side == "right" else -0.45)
    ls = (0, (5, 4)) if dashed else "solid"
    ax.annotate("", xy=(x, y_to), xytext=(x, y_from),
                arrowprops=dict(
                    arrowstyle="-|>", color=color, lw=1.4,
                    linestyle=ls, mutation_scale=13,
                    connectionstyle=f"arc3,rad=0"),
                zorder=5)

def curved_arrow(x1, y1, x2, y2, rad, label=None, dashed=False,
                 color="#546E7A", lw=1.3):
    ls = (0, (5, 4)) if dashed else "solid"
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(
                    arrowstyle="-|>", color=color, lw=lw,
                    linestyle=ls, mutation_scale=13,
                    connectionstyle=f"arc3,rad={rad}"),
                zorder=5)
    if label:
        mx = (x1+x2)/2 + (0.5 if rad > 0 else -0.5)
        my = (y1+y2)/2
        ax.text(mx, my, label, fontsize=7.5, color="#546E7A",
                ha="center", va="center", zorder=6,
                bbox=dict(facecolor="white", edgecolor="#B0BEC5",
                          boxstyle="round,pad=0.2", alpha=0.95))

# ── Layout: y-centres from top ─────────────────────────────────────────────
Y_INPUT = 12.80
Y_INIT  = 11.90
Y_GEN   = 10.65
Y_BRK   =  9.20
Y_EXEC  =  7.90
Y_SCR   =  6.80
Y_EVOL  =  5.55
Y_TERM  =  3.90
Y_RT    =  2.55
Y_OUT   =  1.40

H_IO   = 0.48
H_INIT = 0.60
H_GEN  = 1.00
H_BRK  = 1.10
H_EXEC = 0.78
H_SCR  = 0.72
H_EVOL = 0.90
H_TERM = 1.30
H_RT   = 0.55
H_OUT  = 0.48

# ── Draw nodes ────────────────────────────────────────────────────────────────
_, top_input   = io_box(Y_INPUT, H_IO, "HumanEval+  Task Specification")
bot_init, top_init = box(Y_INIT, H_INIT, "init",
    "Initialize",
    ["Load problem spec  ·  canonical tests  ·  condition config"])

bot_gen, top_gen = box(Y_GEN, H_GEN, "gen",
    "Generator  ·  DARWIN",
    ["Qwen3-32B  ·  240 s wall-clock timeout",
     "Round 0 :  full problem specification",
     "Round N :  spec  +  failed tests  +  strategy prefix"])

bot_brk, top_brk = box(Y_BRK, H_BRK, "brk",
    "Breaker  ·  PHOENIX",
    ["Qwen3-32B  ·  240 s wall-clock timeout",
     "6 attack vectors: overflow · empty input · type confusion",
     "boundary values · unicode injection · deep nesting",
     "Cond D:  breaker strategy frozen after Round 1"])

bot_exec, top_exec = box(Y_EXEC, H_EXEC, "eval",
    "Executor  ·  Subprocess Sandbox",
    ["Canonical tests  +  adversarial tests",
     "pass@k  ·  adv_pass@k  ·  adv_ratio  ·  bug_rate"])

bot_scr, top_scr = box(Y_SCR, H_SCR, "eval",
    "Scorer",
    ["AF  =  0.35·pass\u1d9c\u1d43\u207f  +  0.35·pass\u1d43\u1d48\u1d5b  +  0.20·adv_ratio  +  0.10·\u0394AF"])

bot_evol, top_evol = box(Y_EVOL, H_EVOL, "eval",
    "Evolver  ·  Llama-3.1-8B-Instant",
    ["Update generator defense heuristics",
     "Update breaker attack vectors",
     "Cond A: no-op    Cond B: inject static failure corpus"])

bot_term, top_term = box(Y_TERM, H_TERM, "term",
    "Terminator  ·  7-Gate Deterministic Classifier",
    ["G1  Syntax validity           G2  Canonical test regression",
     "G3  Security scan (Bandit)   G4  Adv pass rate \u2265 0.80",
     "G5  \u0394AF \u2265 0.05                    G6  Branch coverage \u2265 0.75",
     "G7  Fingerprint change",
     "Observed outcomes :   correct   \u00b7   degraded"])

# Route diamond
fill, edge, tc = C["rt"]
diamond_w, diamond_h = 1.2, 0.52
dx = [CX, CX + diamond_w/2, CX, CX - diamond_w/2, CX]
dy = [Y_RT + diamond_h/2, Y_RT, Y_RT - diamond_h/2, Y_RT, Y_RT + diamond_h/2]
ax.fill(dx, dy, facecolor=fill, edgecolor=edge, linewidth=1.5, zorder=3)
ax.text(CX, Y_RT, "Route", ha="center", va="center",
        fontsize=9, fontweight="bold", color=tc, zorder=4)
rt_top    = Y_RT + diamond_h/2
rt_bot    = Y_RT - diamond_h/2
rt_right  = CX + diamond_w/2
rt_left   = CX - diamond_w/2

bot_out, _ = io_box(Y_OUT, H_OUT, "af_class  ·  code_versions  ·  fingerprint_distances")

# ── Draw straight arrows (main flow) ─────────────────────────────────────────
arrow(CX, Y_INPUT - H_IO/2,   CX, top_init,   color="#546E7A")
arrow(CX, bot_init,            CX, top_gen,    color="#546E7A")
arrow(CX, bot_gen,             CX, top_brk,    label="code  vN", color="#546E7A")
arrow(CX, bot_brk,             CX, top_exec,   label="adversarial tests", color="#546E7A")
arrow(CX, bot_exec,            CX, top_scr,    color="#546E7A")
arrow(CX, bot_scr,             CX, top_evol,   color="#546E7A")
arrow(CX, bot_evol,            CX, top_term,   color="#546E7A")
arrow(CX, bot_term,            CX, rt_top,     color="#546E7A")

# terminate arrow
arrow(CX, rt_bot, CX, Y_OUT + H_OUT/2, label="terminate", color="#546E7A")

# ── Loop arrow: Route right → up → Generator right ───────────────────────────
RX = LX + NW + 0.55   # x of right loop rail
ax.annotate("", xy=(CX + diamond_w/2 + 0.01, Y_RT),
            xytext=(CX + NW/2 + 0.01, Y_GEN),
            arrowprops=dict(arrowstyle="-|>", color="#546E7A", lw=1.4,
                            mutation_scale=13,
                            connectionstyle=f"arc3,rad=-0.35"),
            zorder=5)
ax.text(CX + NW/2 + 0.75, (Y_RT + Y_GEN)/2,
        "loop", fontsize=7.5, color="#546E7A", ha="center", va="center",
        rotation=90, zorder=6,
        bbox=dict(facecolor="white", edgecolor="#B0BEC5",
                  boxstyle="round,pad=0.2", alpha=0.95))

# ── Dashed: Evolver → Generator (strategy prefix) ────────────────────────────
curved_arrow(CX + NW/2, Y_EVOL, CX + NW/2, Y_GEN,
             rad=-0.4, label="strategy prefix",
             dashed=True, color="#1976D2")

# ── Dashed: Evolver → Breaker (updated vectors) ──────────────────────────────
curved_arrow(CX + NW/2 - 0.15, Y_EVOL, CX + NW/2 - 0.15, Y_BRK,
             rad=0.35, label="updated vectors",
             dashed=True, color="#1976D2")

# ── Legend ────────────────────────────────────────────────────────────────────
legend_items = [
    (C["gen"][0],  C["gen"][1],  "Generator agent (DARWIN)"),
    (C["brk"][0],  C["brk"][1],  "Breaker agent (PHOENIX)"),
    (C["eval"][0], C["eval"][1], "Shared evaluation pipeline"),
    (C["term"][0], C["term"][1], "Terminator classifier"),
]
lx, ly = LX + 0.1, 0.55
ax.text(lx, ly + 0.28, "Legend", fontsize=8, fontweight="bold",
        color="#37474F", va="center")
for i, (fc, ec, label) in enumerate(legend_items):
    bx = lx + 0.02
    by = ly + 0.05 - i * 0.25
    b = FancyBboxPatch((bx, by - 0.08), 0.28, 0.18,
                        boxstyle="round,pad=0.04",
                        facecolor=fc, edgecolor=ec, linewidth=1.2, zorder=3)
    ax.add_patch(b)
    ax.text(bx + 0.36, by + 0.01, label, fontsize=7.8,
            color="#37474F", va="center", zorder=4)

# Solid vs dashed legend
by_s = ly - 1.05
ax.annotate("", xy=(lx + 0.30, by_s), xytext=(lx + 0.02, by_s),
            arrowprops=dict(arrowstyle="-|>", color="#546E7A",
                            lw=1.4, mutation_scale=11), zorder=5)
ax.text(lx + 0.36, by_s, "LangGraph graph edge", fontsize=7.8,
        color="#37474F", va="center")

by_d = by_s - 0.25
ax.annotate("", xy=(lx + 0.30, by_d), xytext=(lx + 0.02, by_d),
            arrowprops=dict(arrowstyle="-|>", color="#1976D2",
                            lw=1.4, linestyle=(0, (5, 4)),
                            mutation_scale=11), zorder=5)
ax.text(lx + 0.36, by_d, "State data flow (next round)", fontsize=7.8,
        color="#37474F", va="center")

# ── Save ──────────────────────────────────────────────────────────────────────
fig.savefig(OUT, dpi=200, bbox_inches="tight",
            facecolor="white", edgecolor="none")
print(f"Saved -> {OUT}")
plt.close(fig)
