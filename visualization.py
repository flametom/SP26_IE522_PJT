"""
Visualization module — Figures 3–6 of the paper.

- Community network map
- Pedestrian flow snapshots over time
- Performance metric charts (RI, RS, RC, RL)
"""

import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
from config import FIG_DPI, SNAPSHOT_TIMES


OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "results")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def _get_view_bounds(G, margin=0.05):
    """Compute axis limits that crop to the dense core, ignoring bridge outliers.
    Uses 1st-99th percentile of node coordinates + margin."""
    xs = np.array([G.nodes[n]["x"] for n in G.nodes()])
    ys = np.array([G.nodes[n]["y"] for n in G.nodes()])
    x_lo, x_hi = np.percentile(xs, 1), np.percentile(xs, 99)
    y_lo, y_hi = np.percentile(ys, 1), np.percentile(ys, 99)
    dx = (x_hi - x_lo) * margin
    dy = (y_hi - y_lo) * margin
    return x_lo - dx, x_hi + dx, y_lo - dy, y_hi + dy


# ═══════════════════════════════════════════════════════════════════════════
#  1. Network map  (Fig. 3)
# ═══════════════════════════════════════════════════════════════════════════

def plot_network(G, building_nodes, shelter_nodes, community_key):
    """Draw spatial network matching paper Fig. 3 style: white dots + gray edges."""
    fig, ax = plt.subplots(figsize=(10, 10))
    ax.set_facecolor("black")

    # Edges
    for u, v, d in G.edges(data=True):
        if u in G.nodes and v in G.nodes:
            x0, y0 = G.nodes[u]["x"], G.nodes[u]["y"]
            x1, y1 = G.nodes[v]["x"], G.nodes[v]["y"]
            ax.plot([x0, x1], [y0, y1], color="gray", linewidth=0.3, alpha=0.5)

    # Non-building nodes (white)
    non_b = [n for n in G.nodes() if not G.nodes[n].get("is_building")]
    xs = [G.nodes[n]["x"] for n in non_b]
    ys = [G.nodes[n]["y"] for n in non_b]
    ax.scatter(xs, ys, s=0.5, c="white", alpha=0.4, label="Intersection")

    # Building nodes (blue)
    bxs = [G.nodes[n]["x"] for n in building_nodes if n in G.nodes]
    bys = [G.nodes[n]["y"] for n in building_nodes if n in G.nodes]
    ax.scatter(bxs, bys, s=2, c="dodgerblue", alpha=0.6, label="Building")

    # Shelters (green triangles)
    sxs = [G.nodes[n]["x"] for n in shelter_nodes if n in G.nodes]
    sys_ = [G.nodes[n]["y"] for n in shelter_nodes if n in G.nodes]
    ax.scatter(sxs, sys_, s=15, c="lime", marker="^", alpha=0.9, label="Shelter")

    # Crop to dense core (ignore outlier bridge edges)
    xlo, xhi, ylo, yhi = _get_view_bounds(G)
    ax.set_xlim(xlo, xhi)
    ax.set_ylim(ylo, yhi)

    ax.set_title(f"Spatial Network — {community_key}", color="white", fontsize=14)
    ax.legend(loc="upper right", fontsize=8)
    ax.set_aspect("equal")
    ax.axis("off")
    path = os.path.join(OUTPUT_DIR, f"fig3_network_{community_key}.png")
    fig.savefig(path, dpi=FIG_DPI, bbox_inches="tight", facecolor="black")
    plt.close(fig)
    print(f"[Viz] Saved {path}")


# ═══════════════════════════════════════════════════════════════════════════
#  2. Pedestrian flow snapshots over time  (Fig. 4)
# ═══════════════════════════════════════════════════════════════════════════

def plot_flow_snapshots(G, sim_history, community_key):
    """Create a row of panels showing pedestrian positions at key time steps."""
    # Match snapshot times to history entries by closest 't' value
    time_map = {round(s["t"]): i for i, s in enumerate(sim_history)}
    indices = [time_map[t] for t in SNAPSHOT_TIMES if t in time_map]
    n = len(indices)
    if n == 0:
        return
    fig, axes = plt.subplots(1, n, figsize=(4 * n, 4))
    if n == 1:
        axes = [axes]

    for ax, idx in zip(axes, indices):
        ax.set_facecolor("black")
        snap = sim_history[idx]

        # Draw edges lightly
        for u, v, d in G.edges(data=True):
            if u in G.nodes and v in G.nodes:
                x0, y0 = G.nodes[u]["x"], G.nodes[u]["y"]
                x1, y1 = G.nodes[v]["x"], G.nodes[v]["y"]
                ax.plot([x0, x1], [y0, y1], color="gray",
                        linewidth=0.2, alpha=0.3)

        # Pedestrians only — paper Fig. 4 shows red dots, no hazard circles
        pxs, pys = [], []
        for _, info in snap["positions"].items():
            if "x" in info and "y" in info:
                pxs.append(info["x"])
                pys.append(info["y"])
            elif info.get("node") is not None and info["node"] in G.nodes:
                pxs.append(G.nodes[info["node"]]["x"])
                pys.append(G.nodes[info["node"]]["y"])
        ax.scatter(pxs, pys, s=1, c="red", alpha=0.6)

        # Crop to dense core
        xlo, xhi, ylo, yhi = _get_view_bounds(G)
        ax.set_xlim(xlo, xhi)
        ax.set_ylim(ylo, yhi)

        ax.set_title(f"t = {int(snap['t'])} min", color="white", fontsize=10)
        ax.set_aspect("equal")
        ax.axis("off")

    fig.suptitle(f"Pedestrian Flow — {community_key}",
                 color="white", fontsize=13)
    path = os.path.join(OUTPUT_DIR, f"fig4_flow_{community_key}.png")
    fig.savefig(path, dpi=FIG_DPI, bbox_inches="tight", facecolor="black")
    plt.close(fig)
    print(f"[Viz] Saved {path}")


# ═══════════════════════════════════════════════════════════════════════════
#  3. Impacted rate vs. Pmax / Hmax  (Fig. 5)
# ═══════════════════════════════════════════════════════════════════════════

def plot_impacted_rate(results, community_key):
    """
    results : list of dicts with keys P_max, H_max, RI
    """
    fig, ax = plt.subplots(figsize=(7, 5))
    h_vals = sorted(set(r["H_max"] for r in results))
    p_vals = sorted(set(r["P_max"] for r in results))

    for hm in h_vals:
        ris = [next(r["RI"] for r in results
                    if r["H_max"] == hm and r["P_max"] == pm)
               for pm in p_vals]
        ax.plot(p_vals, [ri * 100 for ri in ris],
                marker="o", label=f"Hmax = {hm}")

    ax.set_xlabel("Pmax")
    ax.set_ylabel("Impacted Rate RI (%)")
    ax.set_title(f"Impacted Rate — {community_key}")
    ax.legend()
    ax.grid(True, alpha=0.3)
    path = os.path.join(OUTPUT_DIR, f"fig5_RI_{community_key}.png")
    fig.savefig(path, dpi=FIG_DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"[Viz] Saved {path}")


# ═══════════════════════════════════════════════════════════════════════════
#  4. RS, RC, RL vs. panic rate  (Fig. 6)
# ═══════════════════════════════════════════════════════════════════════════

def plot_panic_performance(results, community_key):
    """
    results : list of dicts with keys panic_rate, RS, RC, RL
    """
    fig, ax = plt.subplots(figsize=(7, 5))
    panic_vals = sorted(set(r["panic_rate"] for r in results))

    for metric, color, label in [("RS", "tab:blue", "RS"),
                                  ("RC", "tab:red", "RC"),
                                  ("RL", "tab:orange", "RL")]:
        vals = [next(r[metric] for r in results
                     if r["panic_rate"] == ep)
                for ep in panic_vals]
        ax.plot([p * 100 for p in panic_vals],
                [v * 100 for v in vals],
                marker="s", color=color, label=label)

    ax.set_xlabel("Background Panic Rate εp (%)")
    ax.set_ylabel("Performance Metrics (%)")
    ax.set_title(f"Evacuation Performance vs. Panic — {community_key}")
    ax.legend()
    ax.grid(True, alpha=0.3)
    path = os.path.join(OUTPUT_DIR, f"fig6_panic_{community_key}.png")
    fig.savefig(path, dpi=FIG_DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"[Viz] Saved {path}")


# ═══════════════════════════════════════════════════════════════════════════
#  5. Time-series count plot
# ═══════════════════════════════════════════════════════════════════════════

def plot_time_series(sim_history, community_key, tag=""):
    """Plot active / arrival / survival / casualty counts over time."""
    ts = [s["t"] for s in sim_history]
    active = [s["counts"]["active"] for s in sim_history]
    arrival = [s["counts"]["arrival"] for s in sim_history]
    survival = [s["counts"]["survival"] for s in sim_history]
    casualty = [s["counts"]["casualty"] for s in sim_history]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(ts, active, label="Active", color="tab:blue")
    ax.plot(ts, arrival, label="Arrival", color="tab:green")
    ax.plot(ts, survival, label="Survival", color="tab:cyan")
    ax.plot(ts, casualty, label="Casualty", color="tab:red")
    ax.set_xlabel("Time (min)")
    ax.set_ylabel("Number of Agents")
    ax.set_title(f"Agent Status Over Time — {community_key} {tag}")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fname = f"timeseries_{community_key}{'_' + tag if tag else ''}.png"
    path = os.path.join(OUTPUT_DIR, fname)
    fig.savefig(path, dpi=FIG_DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"[Viz] Saved {path}")
