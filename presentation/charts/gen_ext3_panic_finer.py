#!/usr/bin/env python3
"""Extension chart 3: RS/RC/RL vs εp at 9 points vs paper's 5."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

DATA = os.path.join(ROOT, "results", "final_experiment_PSU-UP.json")
OUT = os.path.join(ROOT, "presentation", "assets",
                   "fig_ext3_panic_finer.pdf")

# Paper's Fig 6 values (from reproduction_report.md §3.3)
PAPER_EP = [0.10, 0.30, 0.50, 0.70, 0.90]
PAPER_RS = [96.6, 93.0, 88.3, 78.0, 64.6]
PAPER_RC = [2.5, 4.0, 7.2, 10.0, 13.3]
PAPER_RL = [0.9, 3.0, 4.5, 12.0, 22.1]


if __name__ == "__main__":
    with open(DATA) as f:
        d = json.load(f)

    # phase2b rows: Pmax=2000, Hmax=5, vary εp
    rows = [r for r in d["phase2b"]
            if int(r.get("P_max")) == 2000 and int(r.get("H_max")) == 5]
    rows.sort(key=lambda r: r["panic_rate"])
    print(f"[ext3] Loaded {len(rows)} phase2b rows at Pmax=2000, Hmax=5")

    eps = [r["panic_rate"] * 100 for r in rows]
    rs = [r["RS"] * 100 for r in rows]
    rc = [r["RC"] * 100 for r in rows]
    rl = [r["RL"] * 100 for r in rows]

    fig, ax = plt.subplots(figsize=(8, 5))

    ax.plot(eps, rs, marker="o", color="#1B7A3D", label="RS (ours, 9 pts)")
    ax.plot(eps, rc, marker="o", color="#D4760A", label="RC (ours, 9 pts)")
    ax.plot(eps, rl, marker="o", color="#CC1111", label="RL (ours, 9 pts)")

    # Paper points
    paper_eps_pct = [e * 100 for e in PAPER_EP]
    ax.scatter(paper_eps_pct, PAPER_RS, marker="x", s=80, color="#1B7A3D",
               linewidths=2, label="RS (paper, 5 pts)")
    ax.scatter(paper_eps_pct, PAPER_RC, marker="x", s=80, color="#D4760A",
               linewidths=2, label="RC (paper, 5 pts)")
    ax.scatter(paper_eps_pct, PAPER_RL, marker="x", s=80, color="#CC1111",
               linewidths=2, label="RL (paper, 5 pts)")

    ax.set_xlabel("eps_p (%)")
    ax.set_ylabel("Rate (%)")
    ax.set_title("Extension 3: Finer eps_p resolution reveals smooth monotonic curves\n"
                 "(PSU-UP, Pmax=2000, Hmax=5)")
    ax.grid(alpha=0.3)
    ax.legend(loc="upper right", fontsize=8, ncol=2)

    fig.tight_layout()
    fig.savefig(OUT, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {OUT}")
