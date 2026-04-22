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
    """Draw spatial network — white background, clear node/edge colors."""
    fig, ax = plt.subplots(figsize=(10, 10))
    ax.set_facecolor("white")

    # Edges
    for u, v, d in G.edges(data=True):
        if u in G.nodes and v in G.nodes:
            x0, y0 = G.nodes[u]["x"], G.nodes[u]["y"]
            x1, y1 = G.nodes[v]["x"], G.nodes[v]["y"]
            ax.plot([x0, x1], [y0, y1], color="#cccccc", linewidth=0.3, alpha=0.6)

    # Non-building nodes (gray)
    non_b = [n for n in G.nodes() if not G.nodes[n].get("is_building")]
    xs = [G.nodes[n]["x"] for n in non_b]
    ys = [G.nodes[n]["y"] for n in non_b]
    ax.scatter(xs, ys, s=0.5, c="gray", alpha=0.3, label="Intersection")

    # Building nodes (dark goldenrod)
    bxs = [G.nodes[n]["x"] for n in building_nodes if n in G.nodes]
    bys = [G.nodes[n]["y"] for n in building_nodes if n in G.nodes]
    ax.scatter(bxs, bys, s=3, c="#B8860B", alpha=0.7, label="Building")

    # Shelters (green triangles)
    sxs = [G.nodes[n]["x"] for n in shelter_nodes if n in G.nodes]
    sys_ = [G.nodes[n]["y"] for n in shelter_nodes if n in G.nodes]
    ax.scatter(sxs, sys_, s=18, c="tab:green", marker="^", alpha=0.9,
               label="Shelter")

    # Crop to dense core (ignore outlier bridge edges)
    xlo, xhi, ylo, yhi = _get_view_bounds(G)
    ax.set_xlim(xlo, xhi)
    ax.set_ylim(ylo, yhi)

    ax.set_title(f"Spatial Network — {community_key}", fontsize=14)
    ax.legend(loc="upper right", fontsize=8)
    ax.set_aspect("equal")
    ax.axis("off")
    path = os.path.join(OUTPUT_DIR, f"fig3_network_{community_key}.png")
    fig.savefig(path, dpi=FIG_DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"[Viz] Saved {path}")


# ═══════════════════════════════════════════════════════════════════════════
#  2. Pedestrian flow snapshots over time  (Fig. 4)
# ═══════════════════════════════════════════════════════════════════════════

# Density-mapped states: shown as scatter with per-point alpha from KDE.
# (state_key, base_color_light, base_color_dark, zorder, label)
_DENSITY_LAYERS = [
    ("ARRIVAL",  "#C8F0C8", "#3D8B37", 5, "Arrival"),
    ("SURVIVAL", "#B0E8C0", "#1B7A3D", 5, "Survival"),
    ("NORMAL",   "#BDD7F0", "#1A56DB", 6, "Normal"),
    ("QUEUING",  "#FDE8C8", "#D4760A", 7, "Queuing"),
    ("IMPACTED", "#F8C0C0", "#CC1111", 8, "Impacted"),
]
# Individual-marker states: always shown as distinct markers.
_MARKER_LAYERS = [
    ("CASUALTY", "#222222", "X", 20, 1.0, 9, "Casualty"),
]


def plot_flow_snapshots(G, sim_history, community_key,
                        building_nodes=None, shelter_nodes=None):
    """Pedestrian flow snapshots with buildings, shelters, hazard zones,
    and state-coded agents (shape + color + size hierarchy)."""
    time_map = {round(s["t"]): i for i, s in enumerate(sim_history)}
    indices = [time_map[t] for t in SNAPSHOT_TIMES if t in time_map]
    n = len(indices)
    if n == 0:
        return
    fig, axes = plt.subplots(1, n, figsize=(4.5 * n, 4.5))
    if n == 1:
        axes = [axes]

    xlo, xhi, ylo, yhi = _get_view_bounds(G)

    bset = set(building_nodes) if building_nodes else set(
        nd for nd in G.nodes() if G.nodes[nd].get("is_building"))
    sset = set(shelter_nodes) if shelter_nodes else set()

    for ax, idx in zip(axes, indices):
        ax.set_facecolor("#FAFAFA")
        snap = sim_history[idx]

        # ── Layer 1: edges (subtle background) ────────────────────
        for u, v, d in G.edges(data=True):
            if u in G.nodes and v in G.nodes:
                x0, y0 = G.nodes[u]["x"], G.nodes[u]["y"]
                x1, y1 = G.nodes[v]["x"], G.nodes[v]["y"]
                ax.plot([x0, x1], [y0, y1], color="#E0E0E0",
                        linewidth=0.25, alpha=0.5, zorder=1)

        # ── Layer 2: buildings (gray squares — distinct from blue agents)
        if bset:
            bxs = [G.nodes[nd]["x"] for nd in bset if nd in G.nodes]
            bys = [G.nodes[nd]["y"] for nd in bset if nd in G.nodes]
            ax.scatter(bxs, bys, s=4, c="#B8860B", marker="s",
                       alpha=0.35, zorder=2, label="Building")

        # ── Layer 3: shelters (green triangles) ───────────────────
        if sset:
            sxs = [G.nodes[nd]["x"] for nd in sset if nd in G.nodes]
            sys_ = [G.nodes[nd]["y"] for nd in sset if nd in G.nodes]
            ax.scatter(sxs, sys_, s=10, c="#2D8A4E", marker="^",
                       alpha=0.35, zorder=3, label="Shelter")

        # ── Layer 4: hazard zones ─────────────────────────────────
        for hz in snap.get("hazards", []):
            cx, cy, r = hz["center"][0], hz["center"][1], hz["radius"]
            ax.add_patch(plt.Circle((cx, cy), r,
                         color="#FF4444", alpha=0.08, zorder=4))
            ax.add_patch(plt.Circle((cx, cy), r, fill=False,
                         color="#CC0000", linewidth=0.8,
                         linestyle="--", alpha=0.5, zorder=4))

        # ── Layer 5-8: density-mapped agent states ───────────────
        from scipy.stats import gaussian_kde
        from matplotlib.colors import LinearSegmentedColormap

        for state_key, c_light, c_dark, zord, label in _DENSITY_LAYERS:
            pxs, pys = [], []
            for _, info in snap["positions"].items():
                if info.get("state") != state_key:
                    continue
                if "x" in info and "y" in info:
                    pxs.append(info["x"])
                    pys.append(info["y"])
                elif info.get("node") is not None and info["node"] in G.nodes:
                    pxs.append(G.nodes[info["node"]]["x"])
                    pys.append(G.nodes[info["node"]]["y"])
            if len(pxs) < 2:
                if pxs:
                    ax.scatter(pxs, pys, s=6, c=c_dark, marker="o",
                               alpha=0.8, zorder=zord, label=label)
                continue

            xs_a, ys_a = np.array(pxs), np.array(pys)
            try:
                kde = gaussian_kde(np.vstack([xs_a, ys_a]),
                                   bw_method=0.08)
                density = kde(np.vstack([xs_a, ys_a]))
                d_norm = (density - density.min()) / (
                    density.max() - density.min() + 1e-10)
            except Exception:
                d_norm = np.ones(len(xs_a)) * 0.5

            cmap = LinearSegmentedColormap.from_list(
                state_key, [c_light, c_dark])
            sz = 4 if state_key in ("ARRIVAL", "SURVIVAL") else 6
            ax.scatter(xs_a, ys_a, s=sz, c=d_norm, cmap=cmap,
                       vmin=0, vmax=1, alpha=0.7, zorder=zord,
                       label=label)

        # ── Layer 9: individual-marker states (Casualty) ──────────
        for state_key, color, marker, sz, alpha, zord, label in _MARKER_LAYERS:
            pxs, pys = [], []
            for _, info in snap["positions"].items():
                if info.get("state") != state_key:
                    continue
                if "x" in info and "y" in info:
                    pxs.append(info["x"])
                    pys.append(info["y"])
                elif info.get("node") is not None and info["node"] in G.nodes:
                    pxs.append(G.nodes[info["node"]]["x"])
                    pys.append(G.nodes[info["node"]]["y"])
            if pxs:
                ax.scatter(pxs, pys, s=sz, c=color, marker=marker,
                           alpha=alpha, zorder=zord,
                           linewidths=0.5, edgecolors="black",
                           label=label)

        # ── Counts subtitle ───────────────────────────────────────
        counts = snap.get("counts", {})
        sub = (f"Active:{counts.get('active',0)}  "
               f"Imp:{counts.get('impacted',0)}  "
               f"Surv:{counts.get('survival',0)}  "
               f"Cas:{counts.get('casualty',0)}")
        ax.set_title(f"t = {int(snap['t'])} min\n{sub}", fontsize=8)

        ax.set_xlim(xlo, xhi)
        ax.set_ylim(ylo, yhi)
        ax.set_aspect("equal")
        ax.axis("off")

    # ── Shared legend (last panel) ────────────────────────────────
    from matplotlib.lines import Line2D
    legend_items = [
        Line2D([0], [0], marker="s", color="w", markerfacecolor="#B8860B",
               markersize=5, label="Building"),
        Line2D([0], [0], marker="^", color="w", markerfacecolor="#2D8A4E",
               markersize=6, label="Shelter"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#4A90D9",
               markersize=5, label="Normal"),
        Line2D([0], [0], marker="D", color="w", markerfacecolor="#F5A623",
               markersize=4, label="Queuing"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#FF3333",
               markersize=6, label="Impacted"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#50C878",
               markersize=5, alpha=0.5, label="Survival"),
        Line2D([0], [0], marker="X", color="w", markerfacecolor="#222222",
               markeredgecolor="black", markersize=7, label="Casualty"),
        Line2D([0], [0], linestyle="--", color="#CC0000",
               linewidth=1, label="Hazard zone"),
    ]
    axes[-1].legend(handles=legend_items, loc="lower right",
                    fontsize=5, framealpha=0.8, ncol=2)

    fig.suptitle(f"Pedestrian Flow — {community_key}", fontsize=13)
    path = os.path.join(OUTPUT_DIR, f"fig4_flow_{community_key}.png")
    fig.savefig(path, dpi=FIG_DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"[Viz] Saved {path}")


# ═══════════════════════════════════════════════════════════════════════════
#  3. Impacted rate vs. Pmax / Hmax  (Fig. 5)
# ═══════════════════════════════════════════════════════════════════════════

def plot_impacted_rate(results, community_key):
    """
    results : list of dicts with keys P_max, H_max, RI (and optionally RI_std)
    Error bars show ±SD (standard deviation across seeds).
    """
    fig, ax = plt.subplots(figsize=(7, 5))
    h_vals = sorted(set(r["H_max"] for r in results))
    p_vals = sorted(set(r["P_max"] for r in results))

    for hm in h_vals:
        ris, sds = [], []
        for pm in p_vals:
            r = next(r for r in results if r["H_max"] == hm and r["P_max"] == pm)
            ris.append(r["RI"] * 100)
            sds.append(r.get("RI_std", 0) * 100)
        if any(s > 0 for s in sds):
            ax.errorbar(p_vals, ris, yerr=sds, marker="o",
                        capsize=4, label=f"Hmax = {hm}")
        else:
            ax.plot(p_vals, ris, marker="o", label=f"Hmax = {hm}")

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
              (and optionally RS_std, RC_std, RL_std)
    Error bars show ±SD (standard deviation across seeds).
    """
    fig, ax = plt.subplots(figsize=(7, 5))
    panic_vals = sorted(set(r["panic_rate"] for r in results))

    for metric, color, label in [("RS", "tab:blue", "RS"),
                                  ("RC", "tab:red", "RC"),
                                  ("RL", "tab:orange", "RL")]:
        vals, sds = [], []
        for ep in panic_vals:
            r = next(r for r in results if r["panic_rate"] == ep)
            vals.append(r[metric] * 100)
            sds.append(r.get(f"{metric}_std", 0) * 100)
        x = [p * 100 for p in panic_vals]
        if any(s > 0 for s in sds):
            ax.errorbar(x, vals, yerr=sds, marker="s", color=color,
                        capsize=4, label=label)
        else:
            ax.plot(x, vals, marker="s", color=color, label=label)

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
    """Plot active / impacted / arrival / survival / casualty counts over time."""
    ts = [s["t"] for s in sim_history]
    active = [s["counts"]["active"] for s in sim_history]
    impacted = [s["counts"].get("impacted", 0) for s in sim_history]
    arrival = [s["counts"]["arrival"] for s in sim_history]
    survival = [s["counts"]["survival"] for s in sim_history]
    casualty = [s["counts"]["casualty"] for s in sim_history]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(ts, active, label="Active", color="tab:blue")
    ax.plot(ts, impacted, label="Impacted", color="tab:purple",
            linestyle="--", linewidth=2)
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


# ═══════════════════════════════════════════════════════════════════════════
#  7. Animation frames (E: single scenario)
# ═══════════════════════════════════════════════════════════════════════════

_EDGE_SEG_CACHE = {}   # id(G) -> list of segment tuples, computed once per G


def _get_edge_segments(G):
    """Cache segment coordinates for a graph; reuse across frames."""
    k = id(G)
    segs = _EDGE_SEG_CACHE.get(k)
    if segs is None:
        segs = [
            ((G.nodes[u]["x"], G.nodes[u]["y"]),
             (G.nodes[v]["x"], G.nodes[v]["y"]))
            for u, v in G.edges()
            if u in G.nodes and v in G.nodes
        ]
        _EDGE_SEG_CACHE[k] = segs
    return segs


def _render_single_frame(ax, G, snap, bset, sset, xlo, xhi, ylo, yhi,
                          title=None):
    """Render one snapshot onto an existing matplotlib Axes.
    Uses the same visual style as plot_flow_snapshots but simplified
    (scatter only, no KDE) for speed.

    Edges drawn via LineCollection for ~10x speedup vs per-edge ax.plot."""
    from matplotlib.collections import LineCollection

    ax.set_facecolor("#FAFAFA")

    # Edges — single LineCollection instead of per-edge plot calls
    segs = _get_edge_segments(G)
    lc = LineCollection(segs, colors="#E0E0E0", linewidths=0.25,
                        alpha=0.5, zorder=1)
    ax.add_collection(lc)

    # Buildings
    if bset:
        bxs = [G.nodes[nd]["x"] for nd in bset if nd in G.nodes]
        bys = [G.nodes[nd]["y"] for nd in bset if nd in G.nodes]
        ax.scatter(bxs, bys, s=3, c="#B8860B", marker="s",
                   alpha=0.35, zorder=2)

    # Shelters
    if sset:
        sxs = [G.nodes[nd]["x"] for nd in sset if nd in G.nodes]
        sys_ = [G.nodes[nd]["y"] for nd in sset if nd in G.nodes]
        ax.scatter(sxs, sys_, s=8, c="#2D8A4E", marker="^",
                   alpha=0.35, zorder=3)

    # Hazards
    for hz in snap.get("hazards", []):
        cx, cy, r = hz["center"][0], hz["center"][1], hz["radius"]
        ax.add_patch(plt.Circle((cx, cy), r,
                     color="#FF4444", alpha=0.08, zorder=4))
        ax.add_patch(plt.Circle((cx, cy), r, fill=False,
                     color="#CC0000", linewidth=0.8,
                     linestyle="--", alpha=0.5, zorder=4))

    # Agents — single-color scatter per state (no KDE)
    state_style = {
        "NORMAL":   ("#1A56DB", 5, "o", 6),
        "QUEUING":  ("#F5A623", 5, "D", 7),
        "IMPACTED": ("#CC1111", 7, "o", 8),
        "SURVIVAL": ("#1B7A3D", 4, "o", 5),
        "ARRIVAL":  ("#3D8B37", 3, "o", 5),
        "CASUALTY": ("#222222", 8, "X", 9),
    }
    by_state = {k: ([], []) for k in state_style}
    for _, info in snap["positions"].items():
        st = info.get("state")
        if st not in by_state:
            continue
        if "x" in info and "y" in info:
            by_state[st][0].append(info["x"])
            by_state[st][1].append(info["y"])
        elif info.get("node") is not None and info["node"] in G.nodes:
            by_state[st][0].append(G.nodes[info["node"]]["x"])
            by_state[st][1].append(G.nodes[info["node"]]["y"])

    for st, (xs, ys) in by_state.items():
        if not xs:
            continue
        color, sz, marker, z = state_style[st]
        ax.scatter(xs, ys, s=sz, c=color, marker=marker,
                   alpha=0.75, zorder=z)

    ax.set_xlim(xlo, xhi)
    ax.set_ylim(ylo, yhi)
    ax.set_aspect("equal")
    ax.axis("off")

    counts = snap.get("counts", {})
    sub = (f"t = {int(snap['t'])} min  |  "
           f"Active:{counts.get('active',0)}  "
           f"Imp:{counts.get('impacted',0)}  "
           f"Surv:{counts.get('survival',0)}  "
           f"Cas:{counts.get('casualty',0)}")
    if title:
        ax.set_title(f"{title}\n{sub}", fontsize=9)
    else:
        ax.set_title(sub, fontsize=9)


def render_animation_frames(history, G, out_dir, prefix="sim",
                             building_nodes=None, shelter_nodes=None,
                             title=None):
    """Render each snapshot in `history` as a numbered PNG in out_dir."""
    os.makedirs(out_dir, exist_ok=True)
    xlo, xhi, ylo, yhi = _get_view_bounds(G)
    bset = set(building_nodes) if building_nodes else set(
        nd for nd in G.nodes() if G.nodes[nd].get("is_building"))
    sset = set(shelter_nodes) if shelter_nodes else set()

    for i, snap in enumerate(history):
        fig, ax = plt.subplots(figsize=(7, 6))
        _render_single_frame(ax, G, snap, bset, sset,
                              xlo, xhi, ylo, yhi, title=title)
        fname = os.path.join(out_dir, f"{prefix}_{i:03d}.png")
        fig.savefig(fname, dpi=FIG_DPI, bbox_inches="tight",
                    facecolor="white")
        plt.close(fig)
    print(f"[Viz] Rendered {len(history)} frames to {out_dir}/{prefix}_*.png")


# ═══════════════════════════════════════════════════════════════════════════
#  8. Animation frames (C: side-by-side comparison)
# ═══════════════════════════════════════════════════════════════════════════

def render_sidebyside_frames(hist_L, hist_R, G, out_dir, prefix,
                              label_L, label_R,
                              building_nodes=None, shelter_nodes=None,
                              caption=None):
    """Render paired snapshots (L, R) as 2-panel numbered PNGs.
    Assumes hist_L and hist_R have the same length (same SNAPSHOT_TIMES).
    If lengths differ, pairs up to the shorter length."""
    os.makedirs(out_dir, exist_ok=True)
    xlo, xhi, ylo, yhi = _get_view_bounds(G)
    bset = set(building_nodes) if building_nodes else set(
        nd for nd in G.nodes() if G.nodes[nd].get("is_building"))
    sset = set(shelter_nodes) if shelter_nodes else set()

    n = min(len(hist_L), len(hist_R))
    for i in range(n):
        fig, (axL, axR) = plt.subplots(1, 2, figsize=(14, 6))
        _render_single_frame(axL, G, hist_L[i], bset, sset,
                              xlo, xhi, ylo, yhi, title=label_L)
        _render_single_frame(axR, G, hist_R[i], bset, sset,
                              xlo, xhi, ylo, yhi, title=label_R)
        if caption:
            fig.suptitle(caption, fontsize=9, y=0.02)
        fname = os.path.join(out_dir, f"{prefix}_{i:03d}.png")
        fig.savefig(fname, dpi=FIG_DPI, bbox_inches="tight",
                    facecolor="white")
        plt.close(fig)
    print(f"[Viz] Rendered {n} side-by-side frames to "
          f"{out_dir}/{prefix}_*.png")
