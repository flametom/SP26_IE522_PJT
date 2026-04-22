#!/usr/bin/env python3
"""Extension chart 1: RI vs log(Pmax), Hmax = 5/10/15 overlaid.
Highlights the breakpoint where RI ~ Pmax independence fails."""
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

DATA_DIR = os.path.join(ROOT, "results", "pmax_extension", "PSU-UP")
OUT = os.path.join(ROOT, "presentation", "assets",
                   "fig_ext1_pmax_breakpoint.pdf")


def load_all():
    """Load every pmax*_hmax*.json and return list of aggregated dicts."""
    rows = []
    for f in sorted(glob.glob(os.path.join(DATA_DIR, "pmax*_hmax*.json"))):
        with open(f) as fp:
            d = json.load(fp)
        if "aggregated" in d:
            rows.append(d["aggregated"])
    return rows


def group(data, hmax):
    rows = [r for r in data if int(r.get("H_max", 0)) == hmax]
    rows.sort(key=lambda r: r.get("P_max", 0))
    xs = [r["P_max"] for r in rows]
    ys = [r["RI"] * 100 for r in rows]
    sds = [r.get("RI_std", 0) * 100 for r in rows]
    return xs, ys, sds


if __name__ == "__main__":
    data = load_all()
    print(f"[ext1] Loaded {len(data)} aggregated rows")

    fig, ax = plt.subplots(figsize=(8, 5))

    colors = {5: "#2E86AB", 10: "#D4760A", 15: "#CC1111"}
    for hm in [5, 10, 15]:
        xs, ys, sds = group(data, hm)
        if not xs:
            continue
        if any(s > 0 for s in sds):
            ax.errorbar(xs, ys, yerr=sds, marker="o", capsize=4,
                        color=colors[hm], label=f"Hmax = {hm}")
        else:
            ax.plot(xs, ys, marker="o", color=colors[hm],
                    label=f"Hmax = {hm}")

    # Paper-tested band (Pmax 2000-8000)
    ax.axvspan(1500, 8500, alpha=0.08, color="gray",
               label="Paper-tested range")
    # Building capacity reference: 969 buildings x 20 = 19380
    ax.axvline(969 * 20, color="green", linestyle=":",
               alpha=0.6, label="~20 agents / building")

    ax.set_xscale("log")
    ax.set_xlabel("Pmax (log scale)")
    ax.set_ylabel("RI (%)")
    ax.set_title("Extension 1: RI vs. Pmax -- independence breaks at extreme populations\n"
                 "(PSU-UP, eps_p = 10%, 10-seed mean +/- SD)")
    ax.grid(alpha=0.3)
    ax.legend(loc="lower right")

    fig.tight_layout()
    fig.savefig(OUT, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {OUT}")
