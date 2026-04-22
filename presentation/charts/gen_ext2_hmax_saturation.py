#!/usr/bin/env python3
"""Extension chart 2: RI vs Hmax at Pmax=2000, showing saturation."""
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
                   "fig_ext2_hmax_saturation.pdf")


if __name__ == "__main__":
    with open(DATA) as f:
        d = json.load(f)

    # phase2a has Pmax × Hmax grid at eps_p=0.1
    rows = [r for r in d["phase2a"] if int(r.get("P_max")) == 2000]
    rows.sort(key=lambda r: int(r.get("H_max")))
    print(f"[ext2] Loaded {len(rows)} rows at Pmax=2000")

    xs = [int(r["H_max"]) for r in rows]
    ys = [r["RI"] * 100 for r in rows]
    sds = [r.get("RI_std", 0) * 100 for r in rows]

    fig, ax = plt.subplots(figsize=(8, 5))
    if any(s > 0 for s in sds):
        ax.errorbar(xs, ys, yerr=sds, marker="o", capsize=4,
                    color="#CC1111", label="PSU-UP, Pmax=2000")
    else:
        ax.plot(xs, ys, marker="o", color="#CC1111",
                label="PSU-UP, Pmax=2000")

    # Saturation reference line at 86%
    ax.axhline(86, color="green", linestyle=":", alpha=0.6,
               label="~86% saturation")
    # Paper-tested range shade (Hmax 5-15)
    ax.axvspan(4.5, 15.5, alpha=0.08, color="gray",
               label="Paper-tested range")

    ax.set_xlabel("Hmax (number of hazard events)")
    ax.set_ylabel("RI (%)")
    ax.set_title("Extension 2: RI saturates at ~86% as Hmax grows\n"
                 "(PSU-UP, Pmax=2000, eps_p=10%, 10-seed mean ± SD)")
    ax.grid(alpha=0.3)
    ax.legend(loc="lower right")

    fig.tight_layout()
    fig.savefig(OUT, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {OUT}")
