"""
toy_simulation.py
=================
Generates an animated GIF of a small toy evacuation simulation.
Also exports key frames as PNG for the slide deck.

Run: python presentation/toy_simulation.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, Polygon
from matplotlib.lines import Line2D
import matplotlib.animation as animation
import networkx as nx
import numpy as np

ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
os.makedirs(ASSET_DIR, exist_ok=True)

plt.rcParams["font.family"] = "DejaVu Sans"

# Colors
C_BLUE = "#0055A8"
C_ORANGE = "#E37222"
C_GREEN = "#50C878"
C_RED = "#D0021B"
C_DARK = "#333333"

# Agent states
NORMAL = "Normal"
QUEUING = "Queuing"
IMPACTED = "Impacted"
ARRIVAL = "Arrival"
SURVIVAL = "Survival"
CASUALTY = "Casualty"

STATE_COLORS = {
    NORMAL: "#4A90D9",
    QUEUING: "#F5A623",
    IMPACTED: "#FF3333",
    ARRIVAL: "#7ED321",
    SURVIVAL: "#50C878",
    CASUALTY: "#333333",
}


# =========================================================================
# Network
# =========================================================================
def build_toy_network():
    """Build a hand-crafted 17-node network for visualization."""
    G = nx.MultiDiGraph()

    # Node layout: grid-like, readable
    # Buildings (B): origins for agents
    # Shelters (S): safe destinations after impact
    # Intersections (I): routing nodes
    nodes = {
        # Buildings (top area)
        "B1": (1, 9, "building"),
        "B2": (5, 9, "building"),
        "B3": (9, 9, "building"),
        "B4": (1, 6, "building"),
        # Intersections (middle)
        "I1": (3, 8, "intersection"),
        "I2": (7, 8, "intersection"),
        "I3": (1, 7.5, "intersection"),
        "I4": (5, 7, "intersection"),
        "I5": (9, 7, "intersection"),
        "I6": (3, 5.5, "intersection"),
        "I7": (7, 5.5, "intersection"),
        "I8": (5, 4.5, "intersection"),
        "I9": (3, 3, "intersection"),
        "I10": (7, 3, "intersection"),
        # Shelters (bottom)
        "S1": (1, 2, "shelter"),
        "S2": (5, 1.5, "shelter"),
        "S3": (9, 2, "shelter"),
    }

    for nid, (x, y, ntype) in nodes.items():
        G.add_node(nid, x=x, y=y, node_type=ntype)

    # Edges (bidirectional)
    edge_list = [
        ("B1", "I3"), ("B1", "I1"),
        ("B2", "I1"), ("B2", "I4"),
        ("B3", "I2"), ("B3", "I5"),
        ("B4", "I3"), ("B4", "I6"),
        ("I1", "I4"), ("I2", "I4"), ("I2", "I5"),
        ("I3", "I6"), ("I4", "I6"), ("I4", "I7"), ("I5", "I7"),
        ("I6", "I8"), ("I7", "I8"),
        ("I6", "I9"), ("I8", "I9"), ("I8", "I10"), ("I7", "I10"),
        ("I9", "S1"), ("I9", "S2"), ("I10", "S2"), ("I10", "S3"),
    ]

    for u, v in edge_list:
        x1, y1 = nodes[u][0], nodes[u][1]
        x2, y2 = nodes[v][0], nodes[v][1]
        length = np.hypot(x2 - x1, y2 - y1)
        G.add_edge(u, v, length=length, capacity=max(int(length * 3), 5))
        G.add_edge(v, u, length=length, capacity=max(int(length * 3), 5))

    buildings = [n for n, d in G.nodes(data=True) if d["node_type"] == "building"]
    shelters = [n for n, d in G.nodes(data=True) if d["node_type"] == "shelter"]
    return G, buildings, shelters


# =========================================================================
# Agents
# =========================================================================
class ToyAgent:
    def __init__(self, agent_id, origin, destination, speed, group_id):
        self.agent_id = agent_id
        self.origin = origin
        self.destination = destination
        self.speed = speed  # units per step
        self.group_id = group_id
        self.state = NORMAL
        self.is_panicked = False

        self.current_node = origin
        self.current_edge = None
        self.edge_progress = 0.0
        self.path = []

    def get_position(self, G):
        if self.current_node is not None:
            d = G.nodes[self.current_node]
            return d["x"], d["y"]
        if self.current_edge is not None:
            u, v = self.current_edge
            x1, y1 = G.nodes[u]["x"], G.nodes[u]["y"]
            x2, y2 = G.nodes[v]["x"], G.nodes[v]["y"]
            edge_len = np.hypot(x2 - x1, y2 - y1)
            if edge_len == 0:
                return x1, y1
            frac = min(self.edge_progress / edge_len, 1.0)
            return x1 + frac * (x2 - x1), y1 + frac * (y2 - y1)
        d = G.nodes[self.origin]
        return d["x"], d["y"]


class ToyHazard:
    def __init__(self, center_x, center_y, emergence_time, initial_radius,
                 expansion_speed, movement_speed, direction, lifespan=999):
        self.cx = center_x
        self.cy = center_y
        self.emergence_time = emergence_time
        self.initial_radius = initial_radius
        self.expansion_speed = expansion_speed
        self.movement_speed = movement_speed
        self.direction = np.array(direction, dtype=float)
        self.lifespan = lifespan
        self.radius = 0
        self.active = False

    def update(self, t):
        if t < self.emergence_time:
            self.active = False
            self.radius = 0
            return
        elapsed = t - self.emergence_time
        if elapsed > self.lifespan:
            self.active = False
            self.radius = 0
            return
        self.active = True
        self.radius = self.initial_radius + self.expansion_speed * elapsed
        self.cx += self.movement_speed * self.direction[0]
        self.cy += self.movement_speed * self.direction[1]

    def contains(self, x, y):
        if not self.active:
            return False
        return np.hypot(x - self.cx, y - self.cy) <= self.radius


# =========================================================================
# Simulation
# =========================================================================
def find_path(G, source, target):
    try:
        return nx.shortest_path(G, source, target, weight="length")
    except nx.NetworkXNoPath:
        return []


def find_nearest_shelter(G, node, shelters):
    best, best_len = None, float("inf")
    for s in shelters:
        try:
            length = nx.shortest_path_length(G, node, s, weight="length")
            if length < best_len:
                best, best_len = s, length
        except nx.NetworkXNoPath:
            continue
    return best


EDGE_CAPACITY = 99   # no queuing in this 8-agent toy demo
NODE_CAPACITY = 99   # congestion concept explained on slides instead


def run_toy_simulation(G, buildings, shelters, n_steps=28, seed=42):
    rng = np.random.RandomState(seed)

    # ── Create agents: 4 per building (16 total), spread across groups ──
    agents = []
    group_speeds = [1.8, 1.5, 1.2]
    group_panics = [0.6, 0.5, 0.2]
    agent_configs = [
        # (building_idx, group_id)  — 60% young, 20% mid, 20% old
        (0, 0), (0, 0), (0, 1), (0, 2),   # B1: 2 young + 1 mid + 1 old
        (1, 0), (1, 0), (1, 1), (1, 2),   # B2: same
        (2, 0), (2, 0), (2, 1), (2, 2),   # B3: same
        (3, 0), (3, 0), (3, 1), (3, 2),   # B4: same
    ]
    for agent_id, (bidx, gid) in enumerate(agent_configs):
        origin = buildings[bidx]
        dest_choices = [b for b in buildings if b != origin]
        dest = rng.choice(dest_choices)
        a = ToyAgent(agent_id, origin, dest, group_speeds[gid], gid)
        a.path = find_path(G, origin, dest)
        agents.append(a)

    # ── Hazard: moderate growth, drifts slightly right-down ──
    hazard = ToyHazard(
        center_x=5.5, center_y=7.5,
        emergence_time=5,
        initial_radius=0.6,
        expansion_speed=0.07,
        movement_speed=0.008,
        direction=(0.2, -0.4),
        lifespan=28
    )

    frames = []

    for t in range(n_steps):
        # ── 1. Update hazard ──
        hazard.update(t)

        # ── 2. Snapshot: save each agent's state before any changes ──
        import copy
        snap = {}
        for a in agents:
            snap[a.agent_id] = {
                "state": a.state, "node": a.current_node,
                "edge": a.current_edge, "progress": a.edge_progress,
                "dest": a.destination, "panicked": a.is_panicked,
                "pos": a.get_position(G),
            }

        # ── 3. Compute edge/node flow from snapshot ──
        edge_flow = {}
        node_flow = {}
        for a in agents:
            s = snap[a.agent_id]
            if s["state"] in (ARRIVAL, SURVIVAL, CASUALTY):
                continue
            if s["node"] is not None:
                node_flow[s["node"]] = node_flow.get(s["node"], 0) + 1
            elif s["edge"] is not None:
                ek = tuple(sorted(s["edge"]))
                edge_flow[ek] = edge_flow.get(ek, 0) + 1

        # ── 4. Decide: collect updates per agent ──
        updates = {}  # agent_id -> dict of changes to apply
        for a in agents:
            updates[a.agent_id] = {}

        # ── 4a. Algorithm 2: Human-Hazard ──
        for a in agents:
            s = snap[a.agent_id]
            if s["state"] in (ARRIVAL, SURVIVAL, CASUALTY):
                continue
            px, py = s["pos"]
            if not hazard.contains(px, py):
                continue
            u = updates[a.agent_id]

            # First impact: change state + destination only, DON'T move
            # (Algorithm 1 will handle movement next)
            if s["state"] not in (IMPACTED,):
                u["state"] = IMPACTED
                ref = s["node"] if s["node"] else s["edge"][1]
                nearest = find_nearest_shelter(G, ref, shelters)
                if nearest:
                    u["dest"] = nearest

            # Casualty
            dist = np.hypot(px - hazard.cx, py - hazard.cy)
            closeness = max(0, 1.0 - dist / max(hazard.radius, 0.1))
            if rng.random() < 0.05 * (1 + 3.0 * closeness):
                u["state"] = CASUALTY
                continue

            # Panic
            if not s["panicked"] and rng.random() < 0.15 * group_panics[a.group_id]:
                u["panic"] = True

        # ── 4b. Algorithm 1: Human-Network ──
        for a in agents:
            s = snap[a.agent_id]
            u = updates[a.agent_id]
            eff_state = u.get("state", s["state"])
            if eff_state in (ARRIVAL, SURVIVAL, CASUALTY):
                continue

            # Use updated destination if Algo 2 changed it
            dest = u.get("dest", s["dest"])
            cur_node = u.get("node", s["node"])
            cur_edge = u.get("edge", s["edge"])
            cur_progress = u.get("progress", s["progress"])
            is_panicked = u.get("panic", s["panicked"])

            # At destination?
            if cur_node is not None and cur_node == dest:
                if eff_state == IMPACTED:
                    if G.nodes[cur_node].get("node_type") == "shelter":
                        u["state"] = SURVIVAL
                    else:
                        nearest = find_nearest_shelter(G, cur_node, shelters)
                        if nearest:
                            u["dest"] = nearest
                            u["path"] = find_path(G, cur_node, nearest)
                else:
                    u["state"] = ARRIVAL
                continue

            # Branch 1: On an edge
            if cur_edge is not None:
                eu, ev = cur_edge
                ek = tuple(sorted([eu, ev]))
                if edge_flow.get(ek, 0) > EDGE_CAPACITY:
                    if "state" not in u:
                        u["state"] = QUEUING
                else:
                    new_prog = cur_progress + a.speed
                    elen = G[eu][ev][0]["length"]
                    if new_prog >= elen:
                        u["node"] = ev
                        u["edge"] = None
                        u["progress"] = 0
                        # Recover from QUEUING
                        if eff_state == QUEUING and "state" not in u:
                            u["state"] = IMPACTED if s["state"] == IMPACTED else NORMAL
                    else:
                        u["progress"] = new_prog
                        if eff_state == QUEUING and "state" not in u:
                            u["state"] = IMPACTED if s["state"] == IMPACTED else NORMAL
                continue

            # Branch 2: At a node
            if cur_node is not None:
                out_edges = list(G.out_edges(cur_node, keys=True))
                free = [(eu, ev) for eu, ev, ek in out_edges
                        if edge_flow.get(tuple(sorted([eu, ev])), 0) < EDGE_CAPACITY]

                if node_flow.get(cur_node, 0) > NODE_CAPACITY and not free:
                    if "state" not in u:
                        u["state"] = QUEUING
                elif is_panicked:
                    choices = free if free else [(eu, ev) for eu, ev, ek in out_edges]
                    if choices:
                        eu, ev = choices[rng.randint(len(choices))]
                        u["edge"] = (eu, ev)
                        u["progress"] = 0
                        u["node"] = None
                        if eff_state == QUEUING and "state" not in u:
                            u["state"] = IMPACTED if s["state"] == IMPACTED else NORMAL
                else:
                    path = find_path(G, cur_node, dest)
                    if len(path) >= 2:
                        nxt = path[1]
                        ek = tuple(sorted([cur_node, nxt]))
                        if edge_flow.get(ek, 0) < EDGE_CAPACITY:
                            u["edge"] = (cur_node, nxt)
                            u["progress"] = 0
                            u["node"] = None
                            if eff_state == QUEUING and "state" not in u:
                                u["state"] = IMPACTED if s["state"] == IMPACTED else NORMAL
                        elif free:
                            eu, ev = free[0]
                            u["edge"] = (eu, ev)
                            u["progress"] = 0
                            u["node"] = None
                        else:
                            if "state" not in u:
                                u["state"] = QUEUING
                    else:
                        if "state" not in u:
                            u["state"] = QUEUING

        # ── 5. Apply all updates simultaneously ──
        for a in agents:
            u = updates[a.agent_id]
            if "state" in u:
                a.state = u["state"]
            if u.get("panic"):
                a.is_panicked = True
            if "dest" in u:
                a.destination = u["dest"]
            if "path" in u:
                a.path = u["path"]
            if "progress" in u:
                a.edge_progress = u["progress"]
            if "node" in u:
                a.current_node = u["node"]
            if "edge" in u:
                a.current_edge = u["edge"]
                if u["edge"] is not None:
                    a.current_node = None

        # ── 6. Record frame ──
        frame = {
            "t": t,
            "agents": [],
            "hazard": {
                "cx": hazard.cx, "cy": hazard.cy,
                "radius": hazard.radius, "active": hazard.active,
            },
            "counts": {s: 0 for s in [NORMAL, QUEUING, IMPACTED, ARRIVAL, SURVIVAL, CASUALTY]},
        }
        for a in agents:
            px, py = a.get_position(G)
            frame["agents"].append({
                "x": px, "y": py, "state": a.state,
                "panicked": a.is_panicked, "group": a.group_id,
            })
            frame["counts"][a.state] += 1
        frames.append(frame)

    return frames


# =========================================================================
# Animation
# =========================================================================
def create_animation(G, buildings, shelters, frames, save_gif=True, save_key_frames=True):
    fig, ax = plt.subplots(figsize=(10, 7))

    pos = {n: (G.nodes[n]["x"], G.nodes[n]["y"]) for n in G.nodes}

    def draw_frame(frame_idx):
        ax.clear()
        frame = frames[frame_idx]

        ax.set_xlim(-0.5, 14.0)
        ax.set_ylim(0.0, 11.0)
        ax.set_aspect("equal")
        ax.set_facecolor("#FAFAFA")
        ax.grid(True, alpha=0.15)

        # Remove tick labels for cleanliness
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)

        # Draw edges
        drawn_edges = set()
        for u, v, _ in G.edges(data=True):
            key = tuple(sorted([u, v]))
            if key in drawn_edges:
                continue
            drawn_edges.add(key)
            x1, y1 = pos[u]
            x2, y2 = pos[v]
            ax.plot([x1, x2], [y1, y2], color="#CCCCCC", linewidth=2, zorder=1)

        # Draw hazard zone (semi-transparent)
        h = frame["hazard"]
        if h["active"]:
            haz_fill = plt.Circle((h["cx"], h["cy"]), h["radius"],
                                  color="#FF4444", alpha=0.12, zorder=2)
            haz_border = plt.Circle((h["cx"], h["cy"]), h["radius"],
                                   fill=False, color="#FF4444", linewidth=1.5,
                                   linestyle="--", alpha=0.6, zorder=3)
            ax.add_patch(haz_fill)
            ax.add_patch(haz_border)
            ax.text(h["cx"], h["cy"] + h["radius"] + 0.3, "HAZARD",
                    ha="center", fontsize=8, color="#CC0000", fontweight="bold",
                    alpha=0.7, zorder=3)

        # Draw nodes
        for nid, (x, y) in pos.items():
            ntype = G.nodes[nid]["node_type"]
            if ntype == "building":
                sq = FancyBboxPatch((x - 0.25, y - 0.25), 0.5, 0.5,
                                   boxstyle="round,pad=0.03",
                                   facecolor="#4A90D9", edgecolor="#333",
                                   linewidth=1.2, zorder=4)
                ax.add_patch(sq)
            elif ntype == "shelter":
                tri = Polygon([(x, y + 0.35), (x - 0.3, y - 0.2), (x + 0.3, y - 0.2)],
                             closed=True, facecolor=C_GREEN, edgecolor="#333",
                             linewidth=1.5, zorder=4)
                ax.add_patch(tri)
                ax.text(x, y - 0.5, "Shelter", ha="center", fontsize=7,
                       color="#2D7A2D", fontweight="bold", zorder=5)
            else:
                circ = plt.Circle((x, y), 0.15, facecolor="white",
                                 edgecolor="#666", linewidth=1.2, zorder=4)
                ax.add_patch(circ)

        # Draw agents — jitter overlapping positions so they don't stack
        from collections import Counter
        pos_counts = Counter()
        pos_indices = {}
        for i, ad in enumerate(frame["agents"]):
            key = (round(ad["x"], 2), round(ad["y"], 2))
            pos_indices[i] = pos_counts[key]
            pos_counts[key] += 1

        JITTER_R = 0.25  # spread radius for overlapping agents
        for i, agent_data in enumerate(frame["agents"]):
            px, py = agent_data["x"], agent_data["y"]
            state = agent_data["state"]
            color = STATE_COLORS.get(state, "#999")

            # Apply circular jitter if multiple agents at same spot
            key = (round(px, 2), round(py, 2))
            n_at = pos_counts[key]
            if n_at > 1:
                idx = pos_indices[i]
                angle = 2 * np.pi * idx / n_at
                px += JITTER_R * np.cos(angle)
                py += JITTER_R * np.sin(angle)

            if state == CASUALTY:
                ax.plot(px, py, "x", color=color, markersize=11,
                       markeredgewidth=2.5, zorder=10)
            elif state in (ARRIVAL, SURVIVAL):
                ax.plot(px, py, "o", color=color, markersize=8,
                       markeredgecolor="black", markeredgewidth=0.8,
                       alpha=0.5, zorder=10)
            else:
                ax.plot(px, py, "o", color=color, markersize=9,
                       markeredgecolor="black", markeredgewidth=1.0, zorder=10)
                if agent_data["panicked"]:
                    ax.text(px + 0.15, py + 0.15, "!", fontsize=7,
                           fontweight="bold", color="#FF0000", zorder=11)

        # Time label (top-left)
        ax.text(0.0, 10.4, f"t = {frame['t']} min", fontsize=14,
               fontweight="bold", color=C_DARK, zorder=12)

        # Status counts (below time label)
        counts = frame["counts"]
        status_text = (f"Active: {counts[NORMAL] + counts[QUEUING] + counts[IMPACTED]}  |  "
                      f"Arrival: {counts[ARRIVAL]}  |  "
                      f"Survival: {counts[SURVIVAL]}  |  "
                      f"Casualty: {counts[CASUALTY]}")
        ax.text(0.0, 9.9, status_text, fontsize=9, ha="left",
               color="#666", zorder=12)

        # Legend
        legend_items = [
            Line2D([0], [0], marker="s", color="w", markerfacecolor="#4A90D9",
                   markeredgecolor="#333", markersize=10, label="Building"),
            Line2D([0], [0], marker="^", color="w", markerfacecolor=C_GREEN,
                   markeredgecolor="#333", markersize=10, label="Shelter"),
            Line2D([0], [0], marker="o", color="w", markerfacecolor=STATE_COLORS[NORMAL],
                   markeredgecolor="black", markersize=9, label="Normal"),
            Line2D([0], [0], marker="o", color="w", markerfacecolor=STATE_COLORS[QUEUING],
                   markeredgecolor="black", markersize=9, label="Queuing"),
            Line2D([0], [0], marker="o", color="w", markerfacecolor=STATE_COLORS[IMPACTED],
                   markeredgecolor="black", markersize=9, label="Impacted"),
            Line2D([0], [0], marker="o", color="w", markerfacecolor=STATE_COLORS[SURVIVAL],
                   markeredgecolor="black", markersize=9, label="Survival"),
            Line2D([0], [0], marker="x", color=STATE_COLORS[CASUALTY],
                   markersize=9, markeredgewidth=2, label="Casualty"),
            mpatches.Patch(fc="#FF4444", ec="#FF4444", alpha=0.2, label="Hazard zone"),
        ]
        ax.legend(handles=legend_items, loc="center left", fontsize=7.5,
                 framealpha=0.95, edgecolor="#ccc",
                 bbox_to_anchor=(0.72, 0.45))

    # Save key frames
    if save_key_frames:
        key_times = [0, 10, 25]
        key_figs = []
        for kt in key_times:
            fig_k, ax_k = plt.subplots(figsize=(10, 7))
            ax_orig = ax
            ax = ax_k
            draw_frame(min(kt, len(frames) - 1))
            ax = ax_orig
            key_path = os.path.join(ASSET_DIR, f"toy_frame_t{kt}.png")
            fig_k.savefig(key_path, dpi=100, bbox_inches="tight", facecolor="white")
            plt.close(fig_k)
            print(f"  -> saved key frame {key_path}")
            key_figs.append(key_path)

        # Composite key frames
        fig_comp, axes = plt.subplots(1, 3, figsize=(24, 8))
        for i, kp in enumerate(key_figs):
            import matplotlib.image as mpimg
            img = mpimg.imread(kp)
            axes[i].imshow(img)
            axes[i].axis("off")
            axes[i].set_title(f"t = {key_times[i]} min", fontsize=16,
                            fontweight="bold", color=C_DARK, pad=8)
        fig_comp.tight_layout(pad=1.0)
        comp_path = os.path.join(ASSET_DIR, "slide8_toy_frames.png")
        fig_comp.savefig(comp_path, dpi=120, bbox_inches="tight", facecolor="white")
        plt.close(fig_comp)
        print(f"  -> saved composite {comp_path}")

    # Create GIF
    if save_gif:
        print("  Creating GIF animation...")
        anim = animation.FuncAnimation(fig, draw_frame, frames=len(frames),
                                       interval=350, repeat=True)
        gif_path = os.path.join(ASSET_DIR, "toy_example.gif")
        writer = animation.PillowWriter(fps=3)
        anim.save(gif_path, writer=writer, dpi=80)
        plt.close(fig)
        print(f"  -> saved GIF {gif_path}")


# =========================================================================
# Main
# =========================================================================
if __name__ == "__main__":
    print("Building toy network...")
    G, buildings, shelters = build_toy_network()
    print(f"  Nodes: {G.number_of_nodes()}, Edges: {G.number_of_edges()}")
    print(f"  Buildings: {buildings}, Shelters: {shelters}")

    print("\nRunning toy simulation (40 steps)...")
    frames = run_toy_simulation(G, buildings, shelters, n_steps=28)

    print("\nCreating animation and key frames...")
    create_animation(G, buildings, shelters, frames)

    print("\nDone!")
