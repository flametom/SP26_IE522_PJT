#!/usr/bin/env python3
"""Phase 2 reproduction charts limited to paper-tested ranges (no extensions).

Phase 2a: RI vs Pmax x Hmax, paper range only (Pmax in {2K, 5K, 8K}, Hmax in {5, 10, 15}).
Phase 2b: RS/RC/RL vs epsilon_p, paper's 5 points only (10/30/50/70/90).
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

DATA = os.path.join(ROOT, "results", "final_experiment_PSU-UP.json")
OUT_DIR = os.path.join(ROOT, "presentation", "assets")
os.makedirs(OUT_DIR, exist_ok=True)

PAPER_PMAX = [2000, 5000, 8000]
PAPER_HMAX = [5, 10, 15]
PAPER_EP = [0.10, 0.30, 0.50, 0.70, 0.90]


def chart_ri_paper_only():
    """Fig. 5 reproduction limited to paper range."""
    with open(DATA) as f:
        d = json.load(f)

    rows = [r for r in d["phase2a"]
            if r["P_max"] in PAPER_PMAX and r["H_max"] in PAPER_HMAX]
    print(f"[fig5] Loaded {len(rows)} paper-range rows (expected {len(PAPER_PMAX)*len(PAPER_HMAX)})")

    fig, ax = plt.subplots(figsize=(7, 4.6))
    colors = {5: "#2E86AB", 10: "#D4760A", 15: "#CC1111"}

    for hm in PAPER_HMAX:
        xs, ys, sds = [], [], []
        for pm in PAPER_PMAX:
            r = next((r for r in rows if r["P_max"] == pm and r["H_max"] == hm), None)
            if r is None:
                continue
            xs.append(pm)
            ys.append(r["RI"] * 100)
            sds.append(r.get("RI_std", 0) * 100)
        if not xs:
            continue
        if any(s > 0 for s in sds):
            ax.errorbar(xs, ys, yerr=sds, marker="o", capsize=5,
                        color=colors[hm], label=f"Hmax = {hm}")
        else:
            ax.plot(xs, ys, marker="o", color=colors[hm],
                    label=f"Hmax = {hm}")

    ax.set_xticks(PAPER_PMAX)
    ax.set_xticklabels([f"{p//1000}K" for p in PAPER_PMAX])
    ax.set_xlabel("Pmax")
    ax.set_ylabel("RI (%)")
    ax.set_title("Fig. 5 reproduction (paper range) --- "
                 "PSU-UP, eps_p=10%, 10 seeds")
    ax.grid(alpha=0.3)
    ax.legend(loc="lower right")
    ax.set_ylim(25, 80)

    fig.tight_layout()
    out = os.path.join(OUT_DIR, "fig5_RI_paper_only.pdf")
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {out}")


def chart_panic_paper_only():
    """Fig. 6 reproduction limited to paper's 5 points."""
    with open(DATA) as f:
        d = json.load(f)

    rows = []
    for ep in PAPER_EP:
        for r in d["phase2b"]:
            if (r["P_max"] == 2000 and r["H_max"] == 5
                    and abs(r["panic_rate"] - ep) < 1e-6):
                rows.append(r)
                break
    rows.sort(key=lambda r: r["panic_rate"])
    print(f"[fig6] Loaded {len(rows)} paper-range rows (expected {len(PAPER_EP)})")

    eps = [r["panic_rate"] * 100 for r in rows]
    rs = [r["RS"] * 100 for r in rows]
    rc = [r["RC"] * 100 for r in rows]
    rl = [r["RL"] * 100 for r in rows]
    rs_sd = [r.get("RS_std", 0) * 100 for r in rows]
    rc_sd = [r.get("RC_std", 0) * 100 for r in rows]
    rl_sd = [r.get("RL_std", 0) * 100 for r in rows]

    fig, ax = plt.subplots(figsize=(7, 4.6))
    ax.errorbar(eps, rs, yerr=rs_sd, marker="s", capsize=5,
                color="#1B7A3D", label="RS (survival)")
    ax.errorbar(eps, rc, yerr=rc_sd, marker="^", capsize=5,
                color="#D4760A", label="RC (casualty)")
    ax.errorbar(eps, rl, yerr=rl_sd, marker="o", capsize=5,
                color="#CC1111", label="RL (leftover)")

    ax.set_xticks([10, 30, 50, 70, 90])
    ax.set_xlabel("eps_p (%)")
    ax.set_ylabel("Rate (%)")
    ax.set_title("Fig. 6 reproduction (paper's 5 points) --- "
                 "PSU-UP, Pmax=2000, Hmax=5")
    ax.grid(alpha=0.3)
    ax.legend(loc="center right")

    fig.tight_layout()
    out = os.path.join(OUT_DIR, "fig6_panic_paper_only.pdf")
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {out}")


if __name__ == "__main__":
    chart_ri_paper_only()
    chart_panic_paper_only()
