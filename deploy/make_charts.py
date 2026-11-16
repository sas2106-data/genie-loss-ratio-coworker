"""Charts from the committed run evidence (docs/run_evidence/csv) → docs/charts/*.png. No workspace access needed.

Usage: python deploy/make_charts.py   (needs matplotlib)
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
EV, OUT = ROOT / "docs" / "run_evidence", ROOT / "docs" / "charts"
BLUE, RED, INK, MUTED, GRID, SURF = "#2272B4", "#FF3621", "#1B3139", "#5b6b73", "#e6eaec", "#ffffff"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 12, "axes.edgecolor": GRID, "axes.labelcolor": MUTED,
                     "xtick.color": MUTED, "ytick.color": INK, "axes.titlesize": 15, "axes.titleweight": "bold",
                     "axes.titlecolor": INK, "axes.titlelocation": "left", "figure.facecolor": SURF, "axes.facecolor": SURF})


def rows(name):
    with open(EV / "csv" / f"{name}.csv") as f:
        r = list(csv.reader(f))
    return r[0], r[1:]


def finish(ax, fig, name, note=None):
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="x", color=GRID, linewidth=1)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    if note:
        fig.text(0.01, 0.01, note, color=MUTED, fontsize=10)
    fig.tight_layout(rect=(0, 0.05 if note else 0, 1, 1))
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{name}.png", dpi=200)
    plt.close(fig)


def genai_quality():
    _, r = rows("genai_precision_recall")
    names = {"peril_mismatch": "Peril mismatch\n(ai_classify)", "pii_in_free_text": "Personal data\n(ai_mask)"}
    fig, ax = plt.subplots(figsize=(8, 3.6))
    for i, row in enumerate(r):
        p, rc = float(row[8]), float(row[9])
        ax.barh(i + 0.18, rc, height=0.32, color=BLUE)
        ax.barh(i - 0.18, p, height=0.32, color=RED)
        ax.text(rc + 0.01, i + 0.18, f"Recall {rc:.0%}", va="center", color=INK, fontsize=11)
        ax.text(p + 0.01, i - 0.18, f"Precision {p:.0%}", va="center", color=INK, fontsize=11)
    ax.set_yticks(range(len(r)), [names.get(x[0], x[0]) for x in r])
    ax.set_xlim(0, 1.25)
    ax.set_xticks([0, .25, .5, .75, 1])
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.set_title("Gen AI checks vs seeded defects")
    finish(ax, fig, "genai_precision_recall", "Source: dq_genai_eval (src/genai/04_evaluate_genai_dq.py), latest run")


def rate_adequacy():
    h, r = rows("rate_adequacy")
    ix = {k: h.index(k) for k in ("line_of_business", "region", "indicated_rate_change_pct", "achieved_rate_change_pct", "adequacy_status")}
    r = [x for x in r if float(x[ix["indicated_rate_change_pct"]]) > 0][:8][::-1]
    fig, ax = plt.subplots(figsize=(8.5, 4.4))
    for i, x in enumerate(r):
        ind, ach = float(x[ix["indicated_rate_change_pct"]]), float(x[ix["achieved_rate_change_pct"]])
        ax.plot([ach, ind], [i, i], color=GRID, linewidth=3, zorder=1)
        ax.scatter([ach], [i], s=90, color=BLUE, zorder=2, edgecolor=SURF, linewidth=2)
        ax.scatter([ind], [i], s=90, color=RED, zorder=2, edgecolor=SURF, linewidth=2)
        ax.text(ind + 1.2, i, f"+{ind:.0f}%", va="center", color=INK, fontsize=10)
    ax.set_yticks(range(len(r)), [f"{x[ix['line_of_business']]} · {x[ix['region']]}" for x in r])
    ax.set_xlabel("")
    ax.scatter([], [], color=BLUE, s=60, label="Achieved on quotes (Lakebase)")
    ax.scatter([], [], color=RED, s=60, label="Indicated (loss ratio ÷ target − 1)")
    ax.legend(loc="upper center", bbox_to_anchor=(0.4, -0.16), ncol=2, frameon=False, fontsize=10)
    ax.set_title("Rate adequacy: indicated vs achieved rate change")
    finish(ax, fig, "rate_adequacy", "Source: gold_rate_adequacy (Lakeflow) joined with Lakebase pricing.quotes")


def loss_ratio_vs_target():
    h, r = rows("rate_adequacy")
    lr, tg = h.index("loss_ratio_30d"), h.index("target_loss_ratio")
    r = sorted(r, key=lambda x: float(x[lr]) - float(x[tg]), reverse=True)[:10][::-1]
    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    for i, x in enumerate(r):
        v, t = float(x[lr]), float(x[tg])
        ax.barh(i, v, height=0.6, color=RED if v > t else BLUE)
        ax.plot([t, t], [i - 0.38, i + 0.38], color=INK, linewidth=2)
        ax.text(v + 0.01, i, f"{v:.0%}", va="center", color=INK, fontsize=10)
    ax.set_yticks(range(len(r)), [f"{x[0]} · {x[1]}" for x in r])
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.plot([], [], color=INK, linewidth=2, label="Target loss ratio")
    ax.legend(loc="upper center", bbox_to_anchor=(0.4, -0.16), ncol=2, frameon=False, fontsize=10)
    ax.set_title("30-day loss ratio vs target, top 10 gaps")
    finish(ax, fig, "loss_ratio_vs_target", "Red = above target. Source: gold_rate_adequacy · lr_targets")


def medallion():
    _, r = rows("bronze_to_gold_counts")
    d = dict((a, int(b)) for a, b in r)
    steps = [("Bronze claims (Auto Loader)", d.get("bronze_fnol")), ("Silver claims (expectations, de-dup)", d.get("silver_claims")),
             ("Recent claims checked by Gen AI", d.get("silver_claims_ai_checked")), ("Data-quality issues explained", d.get("dq_claims_issues"))]
    steps = [s for s in steps if s[1] is not None][::-1]
    fig, ax = plt.subplots(figsize=(8.5, 3.4))
    for i, (k, v) in enumerate(steps):
        ax.barh(i, v, height=0.6, color=BLUE if i else RED)
        ax.text(v + 30, i, f"{v:,}", va="center", color=INK, fontsize=11)
    ax.set_yticks(range(len(steps)), [s[0] for s in steps])
    ax.set_xlim(0, max(s[1] for s in steps) * 1.15)
    ax.set_title("Claims through the Lakeflow medallion")
    finish(ax, fig, "medallion_counts", "Source: pipeline tables after the committed run")


def expectations():
    t = (EV / "03_lakeflow_pipeline.md").read_text()
    m = re.findall(r"\| (silver_\w+) \| (\w+) \| (\d+) \| (\d+) \|", t)
    m = sorted(m, key=lambda x: int(x[3]))
    fig, ax = plt.subplots(figsize=(8, 3.6))
    for i, (ds, name, ok, bad) in enumerate(m):
        ax.barh(i, int(bad), height=0.6, color=RED if int(bad) else GRID)
        ax.text(int(bad) + 0.3, i, f"{int(bad)} failed of {int(ok) + int(bad):,}", va="center", color=INK, fontsize=10)
    ax.set_yticks(range(len(m)), [f"{n} ({ds.replace('silver_', '')})" for ds, n, _, _ in m])
    ax.set_xlim(0, max(int(x[3]) for x in m) * 1.9 + 1)
    ax.set_title("Lakeflow expectations: failed records per rule")
    finish(ax, fig, "expectations", "Source: Lakeflow pipeline event log (event_log)")


def forecast():
    _, r = rows("ml_frequency_forecast")
    r = r[:8][::-1]
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    for i, x in enumerate(r):
        last, fc = float(x[2]), float(x[3])
        ax.plot([last, fc], [i, i], color=GRID, linewidth=3, zorder=1)
        ax.scatter([last], [i], s=90, color=BLUE, zorder=2, edgecolor=SURF, linewidth=2)
        ax.scatter([fc], [i], s=90, color=RED, zorder=2, edgecolor=SURF, linewidth=2)
        ax.text(max(last, fc) + 1.5, i, f"{float(x[5]):+.0f}% vs 4-wk avg · {x[6]}", va="center", color=INK, fontsize=10)
    ax.set_yticks(range(len(r)), [f"{x[0]} · {x[1]}" for x in r])
    ax.set_xlim(0, max(max(float(x[2]), float(x[3])) for x in r) * 1.6)
    ax.set_xlabel("")
    ax.scatter([], [], color=BLUE, s=60, label="Last 7 days")
    ax.scatter([], [], color=RED, s=60, label="Forecast next 7 days (UC model @champion)")
    ax.legend(loc="upper center", bbox_to_anchor=(0.4, -0.16), ncol=2, frameon=False, fontsize=10)
    ax.set_title("Claim-frequency forecast, top segments")
    finish(ax, fig, "frequency_forecast", "Source: lr_frequency_forecast (src/ml/06_train_frequency_forecast.py)")


def judge():
    h, r = rows("genai_llm_judge")
    tot = next((x for x in r if x[0] and not x[1]), r[-1])
    crit = [("Explains the right check", float(tot[3])), ("Actionable fix", float(tot[4])),
            ("No personal data", float(tot[5])), ("Faithful (no invented facts)", float(tot[6]))][::-1]
    fig, ax = plt.subplots(figsize=(8, 3.2))
    for i, (k, v) in enumerate(crit):
        ax.barh(i, v, height=0.6, color=BLUE)
        ax.text(v + 0.01, i, f"{v:.0%}", va="center", color=INK, fontsize=11)
    ax.set_yticks(range(len(crit)), [c[0] for c in crit])
    ax.set_xlim(0, 1.15)
    ax.set_xticks([0, .25, .5, .75, 1])
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.set_title(f"LLM judge: {tot[2]} explanations, avg {tot[7]}/5")
    finish(ax, fig, "llm_judge", f"Judge: {tot[0]} (different model family from the generator)")


if __name__ == "__main__":
    for f in (genai_quality, rate_adequacy, loss_ratio_vs_target, medallion, expectations, forecast, judge):
        f()
    print("charts →", OUT)
