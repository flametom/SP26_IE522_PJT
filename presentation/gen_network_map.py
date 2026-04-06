"""
Generate a white-background network map for the presentation slide.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from network_model import build_network

ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

def _get_view_bounds(G, margin=0.05):
    xs = [G.nodes[n]["x"] for n in G.nodes]
    ys = [G.nodes[n]["y"] for n in G.nodes]
    x_lo, x_hi = np.percentile(xs, 1), np.percentile(xs, 99)
    y_lo, y_hi = np.percentile(ys, 1), np.percentile(ys, 99)
    dx = (x_hi - x_lo) * margin
    dy = (y_hi - y_lo) * margin
    return x_lo - dx, x_hi + dx, y_lo - dy, y_hi + dy

def plot_network_white(G, building_nodes, shelter_nodes, community_key):
    fig, ax = plt.subplots(figsize=(10, 10))
    ax.set_facecolor("white")

    # Edges
    for u, v, d in G.edges(data=True):
        if u in G.nodes and v in G.nodes:
            x0, y0 = G.nodes[u]["x"], G.nodes[u]["y"]
            x1, y1 = G.nodes[v]["x"], G.nodes[v]["y"]
            ax.plot([x0, x1], [y0, y1], color="#CCCCCC", linewidth=0.3, alpha=0.6)

    # Non-building nodes (gray)
    non_b = [n for n in G.nodes() if not G.nodes[n].get("is_building")]
    xs = [G.nodes[n]["x"] for n in non_b]
    ys = [G.nodes[n]["y"] for n in non_b]
    ax.scatter(xs, ys, s=0.5, c="#999999", alpha=0.4, label="Intersection", zorder=2)

    # Building nodes (blue)
    bxs = [G.nodes[n]["x"] for n in building_nodes if n in G.nodes]
    bys = [G.nodes[n]["y"] for n in building_nodes if n in G.nodes]
    ax.scatter(bxs, bys, s=3, c="#0055A8", alpha=0.7, label="Building", zorder=3)

    # Shelters (green triangles)
    sxs = [G.nodes[n]["x"] for n in shelter_nodes if n in G.nodes]
    sys_ = [G.nodes[n]["y"] for n in shelter_nodes if n in G.nodes]
    ax.scatter(sxs, sys_, s=20, c="#50C878", marker="^", alpha=0.9,
               edgecolors="black", linewidths=0.3, label="Shelter", zorder=4)

    xlo, xhi, ylo, yhi = _get_view_bounds(G)
    ax.set_xlim(xlo, xhi)
    ax.set_ylim(ylo, yhi)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.legend(loc="upper right", fontsize=9, framealpha=0.9)

    path = os.path.join(ASSET_DIR, "network_PSU-UP_white.png")
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  -> saved {path}")

if __name__ == "__main__":
    print("Building PSU-UP network...")
    G, building_nodes, shelter_nodes = build_network("PSU-UP")
    print(f"  Nodes: {G.number_of_nodes()}, Edges: {G.number_of_edges()}")
    plot_network_white(G, building_nodes, shelter_nodes, "PSU-UP")
    print("Done!")
