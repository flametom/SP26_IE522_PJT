#!/usr/bin/env python3
"""Generate benchmark charts for slides 6 and 10."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

BENCH_DIR = os.path.join(ROOT, "results", "benchmark")
OUT_DIR = os.path.join(ROOT, "presentation", "assets")
os.makedirs(OUT_DIR, exist_ok=True)


def load(name):
    with open(os.path.join(BENCH_DIR, name)) as f:
        return json.load(f)


def chart_time_distribution():
    """Slide 6: horizontal bar chart of time spent per section, both modes."""
    naive = load("naive_timings.json")
    opt = load("optimized_timings.json")

    sections = ["flows", "algo2", "batch_sssp", "algo1", "commit"]
    labels = ["Flow compute", "Algorithm 2", "Batch SSSP",
              "Algorithm 1 (+ path calls)", "Commit"]
    naive_vals = [naive["timings"][k] for k in sections]
    opt_vals = [opt["timings"][k] for k in sections]

    fig, ax = plt.subplots(figsize=(8.5, 4.5))
    y = np.arange(len(sections))
    h = 0.38
    ax.barh(y + h/2, naive_vals, h, label=f"Naive ({naive['wall_sec']:.0f}s)",
            color="#CC4444")
    ax.barh(y - h/2, opt_vals, h, label=f"Optimized ({opt['wall_sec']:.1f}s)",
            color="#2E86AB")

    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_xlabel("Wall-clock seconds")
    ax.set_title("Time distribution per run "
                 f"(PSU-UP, Pmax={naive['config']['Pmax']}, "
                 f"Hmax={naive['config']['Hmax']})")
    ax.legend(loc="lower right")
    ax.grid(axis="x", alpha=0.3)

    for i, (nv, ov) in enumerate(zip(naive_vals, opt_vals)):
        ax.text(nv, i + h/2, f" {nv:.1f}s", va="center", fontsize=8)
        ax.text(ov, i - h/2, f" {ov:.1f}s", va="center", fontsize=8)

    fig.tight_layout()
    out = os.path.join(OUT_DIR, "benchmark_time_dist.pdf")
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {out}")


def chart_scaling():
    """Slide 10: summary panel — per-run time + extrapolated throughput."""
    naive = load("naive_timings.json")
    opt = load("optimized_timings.json")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.2))

    # Panel 1: single-run wall time
    modes = ["Naive\n(per-agent A*)", "Optimized\n(scipy batch SSSP)"]
    vals = [naive["wall_sec"], opt["wall_sec"]]
    colors = ["#CC4444", "#2E86AB"]
    bars = ax1.bar(modes, vals, color=colors)
    ax1.set_ylabel("Seconds per single run")
    ax1.set_title("Single-run wall time "
                  f"(Pmax={opt['config']['Pmax']}, Hmax={opt['config']['Hmax']})")
    ax1.set_yscale("log")
    for b, v in zip(bars, vals):
        ax1.text(b.get_x() + b.get_width()/2, v,
                 f"{v:.1f}s", ha="center", va="bottom")
    ax1.grid(axis="y", alpha=0.3)

    # Panel 2: extrapolated total for 390-run extension sweep
    N_RUNS = 390
    N_WORKERS = 8
    naive_total = naive["wall_sec"] * N_RUNS / N_WORKERS
    opt_total = opt["wall_sec"] * N_RUNS / N_WORKERS
    extrap_vals = [naive_total / 3600, opt_total / 3600]
    bars = ax2.bar(modes, extrap_vals, color=colors)
    ax2.set_ylabel(f"Hours for {N_RUNS} runs (8-worker parallel)")
    ax2.set_title(f"Extrapolated: {N_RUNS}-run extension experiment")
    ax2.set_yscale("log")
    for b, v in zip(bars, extrap_vals):
        ax2.text(b.get_x() + b.get_width()/2, v,
                 f"{v:.1f}h" if v >= 1 else f"{v*60:.0f}min",
                 ha="center", va="bottom")
    ax2.grid(axis="y", alpha=0.3)

    speedup = naive["wall_sec"] / opt["wall_sec"]
    fig.suptitle(f"Single-process speedup: {speedup:.1f}x "
                 f"(x{N_WORKERS} workers = ~{speedup*N_WORKERS:.0f}x overall)",
                 fontsize=11)
    fig.tight_layout()
    out = os.path.join(OUT_DIR, "benchmark_scaling.pdf")
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {out}")


if __name__ == "__main__":
    chart_time_distribution()
    chart_scaling()
