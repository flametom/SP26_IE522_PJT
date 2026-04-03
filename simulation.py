"""
Simulation engine — Algorithms 1 & 2 from Shi et al. (IEEE CASE 2024).

Position model (paper Algorithm 1, Section III-C):
  Agent is either AT a node or ON an edge at any given time step.
  - At node:  p.current_node is int, p.current_edge is None
  - On edge:  p.current_edge is (u, v, key), p.current_node is None
              p.edge_progress = meters traveled from u toward v

Flow (paper Eq. 2, 4 — mutually exclusive):
  fvi(t)  = count of agents at node vi  (not on any edge)
  feij(t) = count of agents on edge eij (not at either endpoint)

Algorithm 2 (Human-Hazard, paper p.4):
  Runs every step for agents inside hazard zones.
  Panic check every step (irreversible once triggered).
  Uses interpolated position for on-edge agents.

Algorithm 1 (Human-Network, paper p.3):
  Branch 1 — agent on edge: check edge congestion → queue or continue
  Branch 2 — agent at node: check node congestion →
             queue / panic-random / reroute / advance

Pathfinding: A* with Euclidean heuristic for spatial networks.
Time: 1 step = 1 minute, 120 steps total.
"""

import numpy as np
import networkx as nx
from agents import HumanState
from network_model import nearest_shelter
from config import (
    DT, N_STEPS, SIM_DURATION, SNAPSHOT_TIMES,
    CASUALTY_PROB_PER_STEP, CASUALTY_CENTER_WEIGHT,
)


class EvacuationSimulation:

    def __init__(self, G, humans, hazards, shelter_nodes,
                 background_panic, rng):
        self.G = G
        self.humans = humans
        self.hazards = hazards
        self.shelter_nodes = shelter_nodes
        self.background_panic = background_panic
        self.rng = rng
        self.dt = DT

        self.G_undirected = G.to_undirected()
        self.coords = {n: (d["x"], d["y"]) for n, d in G.nodes(data=True)}
        self._shelter_set = set(shelter_nodes)

        self.history = []
        self._snapshot_steps = {int(t / self.dt) for t in SNAPSHOT_TIMES
                                if t <= SIM_DURATION}
        self._initial_routing()

    # ══════════════════════════════════════════════════════════════════════
    #  Routing
    # ══════════════════════════════════════════════════════════════════════

    def _initial_routing(self):
        for p in self.humans:
            self._assign_path(p, p.destination)

    def _assign_path(self, p, target):
        """Compute shortest path from agent's effective position to target."""
        if p.on_edge:
            src = p.current_edge[1]   # route from edge destination node
        else:
            src = p.current_node
        path = self._find_path(src, target)
        if path and len(path) > 1:
            p.path = path[1:]         # skip src
            p.path_idx = 0

    def _find_path(self, src, tgt):
        """A* shortest path with Euclidean heuristic for spatial networks."""
        try:
            coords = self.coords

            def heuristic(u, v):
                ux, uy = coords.get(u, (0, 0))
                vx, vy = coords.get(v, (0, 0))
                return ((ux - vx) ** 2 + (uy - vy) ** 2) ** 0.5

            return nx.astar_path(self.G_undirected, src, tgt,
                                 heuristic=heuristic, weight="length")
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    def _resolve_edge(self, u, v):
        """Return (actual_u, actual_v, key) for directed edge between u, v."""
        edata = self.G.get_edge_data(u, v)
        if edata is not None:
            return (u, v, next(iter(edata.keys())))
        edata = self.G.get_edge_data(v, u)
        if edata is not None:
            return (v, u, next(iter(edata.keys())))
        return None

    def _edge_length(self, u, v):
        data = self.G.get_edge_data(u, v)
        if data:
            return next(iter(data.values())).get("length", 1.0)
        data = self.G.get_edge_data(v, u)
        if data:
            return next(iter(data.values())).get("length", 1.0)
        return 1.0

    # ══════════════════════════════════════════════════════════════════════
    #  Main loop
    # ══════════════════════════════════════════════════════════════════════

    def run(self, verbose=True):
        for step in range(N_STEPS + 1):
            t_min = step * self.dt

            for h in self.hazards:
                h.update(t_min, self.dt)

            for p in self.humans:
                if not p.departed and t_min >= p.departure_time:
                    p.departed = True

            self._reset_flows()
            self._compute_flows()

            for p in self.humans:
                p.clear_buffers()

            self._algorithm2()
            self._algorithm1()
            self._commit_updates()

            if step in self._snapshot_steps:
                self._record(t_min)

            if verbose and step % max(1, N_STEPS // 12) == 0:
                self._print_status(t_min)

        if N_STEPS not in self._snapshot_steps:
            self._record(SIM_DURATION)

        return self._compute_metrics()

    # ══════════════════════════════════════════════════════════════════════
    #  Flow — mutually exclusive node / edge  (paper Eq. 2, 4)
    # ══════════════════════════════════════════════════════════════════════

    def _reset_flows(self):
        for n in self.G.nodes():
            self.G.nodes[n]["flow"] = 0
        for u, v, k in self.G.edges(keys=True):
            self.G.edges[u, v, k]["flow"] = 0

    def _compute_flows(self):
        """Paper: fvi(t) counts agents at node vi; feij(t) counts agents on
        edge eij.  Mutually exclusive — an agent is either at a node or on
        an edge, never both."""
        for p in self.humans:
            if not p.is_active:
                continue
            if p.on_edge:
                u, v, k = p.current_edge
                if self.G.has_edge(u, v, k):
                    self.G.edges[u, v, k]["flow"] += 1
            elif p.at_node and p.current_node in self.G.nodes:
                self.G.nodes[p.current_node]["flow"] += 1

    # ══════════════════════════════════════════════════════════════════════
    #  Algorithm 2 — Human-Hazard Interaction  (paper p.4)
    # ══════════════════════════════════════════════════════════════════════

    def _algorithm2(self):
        """Paper Algorithm 2 — checked EVERY step agent is in hazard zone:
          1. First impact → IMPACTED + redirect to shelter
          2. Casualty check (every step)
          3. Panic check (every step, irreversible)
        Position uses interpolation for on-edge agents."""
        cas_prob = CASUALTY_PROB_PER_STEP
        for p in self.humans:
            if not p.is_active:
                continue
            px, py = p.get_position(self.G)

            for h in self.hazards:
                if not h.active or not h.contains_point(px, py):
                    continue

                # First impact → IMPACTED + shelter redirect
                first_impact = (p.state != HumanState.IMPACTED)
                if first_impact:
                    p._next_state = HumanState.IMPACTED
                    shelter = self._find_nearby_shelter(p, px, py)
                    if shelter is not None:
                        p._next_dest = shelter

                # Casualty check (every step in hazard)
                dist = h.distance_to_center(px, py)
                ratio = max(0.0, 1.0 - dist / max(h.radius, 1.0))
                prob = cas_prob * (1 + CASUALTY_CENTER_WEIGHT * ratio)
                if self.rng.random() < prob:
                    p._next_state = HumanState.CASUALTY
                    break

                # Panic check — every step in hazard zone (irreversible)
                # Paper Algorithm 2: "Compute εpi; Determine if pi is in panic"
                # Paper Discussion: "panic states are irreversible"
                if not p.is_panicked:
                    eff_panic = self.background_panic * p.panic_rate
                    if self.rng.random() < eff_panic:
                        p._next_panic = True

                break  # first matching hazard

    def _find_nearby_shelter(self, p, px, py):
        """Paper: 'Impacted pi changes destination to a nearby shelter.'
        Nearest safe shelter by Euclidean distance from agent's position."""
        best, best_dist = None, float("inf")
        for sn in self.shelter_nodes:
            sx, sy = self.coords.get(sn, (0, 0))
            if any(h.contains_point(sx, sy)
                   for h in self.hazards if h.active):
                continue
            d = np.hypot(px - sx, py - sy)
            if d < best_dist:
                best_dist = d
                best = sn
        if best is None:
            src = p.current_node if p.at_node else p.current_edge[0]
            return nearest_shelter(self.G, src, self.shelter_nodes)
        return best

    # ══════════════════════════════════════════════════════════════════════
    #  Algorithm 1 — Human-Network Interaction  (paper p.3)
    # ══════════════════════════════════════════════════════════════════════

    def _algorithm1(self):
        """Paper Algorithm 1 — two branches:
          Branch 1: agent on edge → check edge congestion
          Branch 2: agent at node → check node congestion"""
        dt = self.dt
        for p in self.humans:
            if not p.is_active:
                continue
            # Algorithm 2 determinations have absolute priority
            if p._next_state in (HumanState.CASUALTY, HumanState.IMPACTED):
                continue

            # ── Destination arrival (at node only) ────────────────
            if p.at_node and p.current_node == p.destination:
                if p.state == HumanState.IMPACTED:
                    p._next_state = HumanState.SURVIVAL
                else:
                    p._next_state = HumanState.ARRIVAL
                continue

            # Impacted at any shelter → Survival
            if (p.at_node and p.state == HumanState.IMPACTED
                    and p.current_node in self._shelter_set):
                p._next_state = HumanState.SURVIVAL
                continue

            # ═══ Branch 1: Agent ON AN EDGE ═══════════════════════
            if p.on_edge:
                u, v, k = p.current_edge
                ed = self.G.edges[u, v, k]
                if ed.get("flow", 0) >= ed.get("capacity", 1):
                    # Paper: "Spi(t+1) ← Queuing and Vpi(t) ← 0"
                    if p.state != HumanState.IMPACTED:
                        p._next_state = HumanState.QUEUING
                    # No movement — stay on same edge
                else:
                    # Paper: "Update spi(t+1) based on Vpi(t)"
                    self._continue_on_edge(p, dt)
                continue

            # ═══ Branch 2: Agent AT A NODE ════════════════════════
            node = p.current_node
            nd = self.G.nodes[node]
            node_flow = nd.get("flow", 0)
            node_cap = nd.get("capacity", 50)

            if node_flow >= node_cap:
                # Node congested
                out = list(self.G.out_edges(node, data=True, keys=True))
                all_cong = all(
                    d.get("flow", 0) >= d.get("capacity", 1)
                    for _, _, _, d in out
                ) if out else True

                if all_cong:
                    # Paper: "Queuing, Vpi(t) = 0"
                    if p.state != HumanState.IMPACTED:
                        p._next_state = HumanState.QUEUING
                else:
                    if p.is_panicked:
                        # Paper: "pi randomly selects ej ∈ E(vk(t))"
                        self._move_random_edge(p, out, dt)
                    else:
                        # Paper: "pi re-routes"
                        self._move_reroute(p, dt)
            else:
                # Node not congested
                if p.is_panicked:
                    # Paper Discussion: "panicking pedestrians choose
                    # paths randomly at nodes"
                    out = list(self.G.out_edges(node, data=True, keys=True))
                    if out:
                        self._move_random_edge(p, out, dt)
                else:
                    # Paper: "Update spi(t+1) based on Vpi(t)"
                    # No reroute at non-congested nodes — just advance.
                    # If agent enters a congested edge, the on-edge branch
                    # handles it next step.
                    self._move_along_path(p, dt)

    # ══════════════════════════════════════════════════════════════════════
    #  Movement
    # ══════════════════════════════════════════════════════════════════════

    def _continue_on_edge(self, p, dt):
        """Continue agent along current edge.  If arriving at destination
        node, continue along path with remaining speed budget."""
        u, v, k = p.current_edge
        elen = self.G.edges[u, v, k].get("length", 1.0)
        remaining = elen - p.edge_progress
        budget = p.speed * dt

        if budget < remaining:
            # Still on same edge
            p._next_edge = p.current_edge
            p._next_edge_progress = p.edge_progress + budget
            return

        # Arrive at v
        budget -= remaining

        if v == p.destination:
            p._next_node = v
            p._next_edge = None
            p._next_edge_progress = 0.0
            return

        # Advance path index past v
        pidx = p.path_idx
        if p.path and pidx < len(p.path) and p.path[pidx] == v:
            pidx += 1

        # Panicked agents stop at v — they choose a new random edge
        # next step from the at-node branch (paper: random at nodes,
        # continue on edges, no path-following)
        if p.is_panicked or budget <= 0 or not p.path or pidx >= len(p.path):
            p._next_node = v
            p._next_edge = None
            p._next_edge_progress = 0.0
            p._next_path = (p.path, pidx)
            return

        # Normal agents continue multi-edge traversal from v
        self._traverse_path(p, v, pidx, budget)

    def _move_along_path(self, p, dt):
        """Move along pre-computed path from current node.
        Returns True if agent moved, False if blocked."""
        if not p.path or p.path_idx >= len(p.path):
            return False

        # Clear queuing if we can move (guard: don't overwrite Algo 2)
        if p.state == HumanState.QUEUING and p._next_state is None:
            p._next_state = HumanState.NORMAL

        return self._traverse_path(p, p.current_node, p.path_idx,
                                   p.speed * dt)

    def _traverse_path(self, p, start, pidx, budget):
        """Core multi-edge traversal from a node with given speed budget.
        Returns True if agent moved.  Sets position and path buffers.

        Paper Algorithm 1: 'Update spi(t+1) based on Vpi(t)' — agents
        advance along their path without pre-checking edge congestion.
        If they end up on a congested edge, the on-edge branch handles
        it next step (Queuing).  This matches the paper's model where
        agents only discover edge congestion AFTER entering the edge."""
        cur = start
        prog = 0.0

        while budget > 0 and pidx < len(p.path):
            nxt = p.path[pidx]
            elen = self._edge_length(cur, nxt)

            # Check edge exists (topology only, no congestion pre-check)
            edge_ref = self._resolve_edge(cur, nxt)
            if edge_ref is None:
                break

            if budget >= elen:
                # Complete this edge → arrive at nxt
                budget -= elen
                cur = nxt
                pidx += 1
                if cur == p.destination:
                    break
            else:
                # Partial traversal → agent ends up on this edge
                prog = budget
                budget = 0

        moved = (cur != start or prog > 0)

        if prog > 0 and pidx < len(p.path):
            # Agent is on an edge (partial traversal)
            nxt = p.path[pidx]
            edge_ref = self._resolve_edge(cur, nxt)
            if edge_ref:
                p._next_node = None
                p._next_edge = edge_ref
                p._next_edge_progress = prog
            else:
                # Fallback: stay at cur
                p._next_node = cur
                p._next_edge = None
                p._next_edge_progress = 0.0
        else:
            # Agent is at a node
            p._next_node = cur
            p._next_edge = None
            p._next_edge_progress = 0.0

        p._next_path = (p.path, pidx)
        return moved

    def _move_random_edge(self, p, out_edges, dt):
        """Panicked agent at a node: randomly select an edge and traverse.
        Paper: 'pi randomly selects ej ∈ E(vk(t))' — no congestion filter
        (panicked agents make irrational choices)."""
        if not out_edges:
            return
        idx = self.rng.integers(len(out_edges))
        u, v, k, d = out_edges[idx]
        elen = d.get("length", 1.0)
        budget = p.speed * dt

        if budget >= elen:
            p._next_node = v
            p._next_edge = None
            p._next_edge_progress = 0.0
        else:
            p._next_node = None
            p._next_edge = (u, v, k)
            p._next_edge_progress = budget

        p._next_path = ([], 0)

    def _move_reroute(self, p, dt):
        """Paper: 're-routes' — congestion-aware path from current node."""
        path = self._find_path_congestion_aware(p.current_node, p.destination)
        if path and len(path) > 1:
            p.path = path[1:]
            p.path_idx = 0
            self._traverse_path(p, p.current_node, 0, p.speed * dt)

    def _find_path_congestion_aware(self, src, tgt):
        """A* shortest path with congestion penalty on nodes and edges.
        Reads flow data from directed graph (undirected copy has stale flows)."""
        try:
            coords = self.coords
            G_dir = self.G

            def heuristic(u, v):
                ux, uy = coords.get(u, (0, 0))
                vx, vy = coords.get(v, (0, 0))
                return ((ux - vx) ** 2 + (uy - vy) ** 2) ** 0.5

            def weight_fn(u, v, data):
                base = data.get("length", 1.0)
                # Node congestion penalty
                nd = G_dir.nodes.get(v, {})
                nr = nd.get("flow", 0) / max(nd.get("capacity", 50), 1)
                if nr >= 1.0:
                    base *= (1.0 + 5.0 * nr)
                # Edge congestion penalty (from directed graph)
                for eu, ev in [(u, v), (v, u)]:
                    edata = G_dir.get_edge_data(eu, ev)
                    if edata:
                        for kd in edata.values():
                            er = kd.get("flow", 0) / max(
                                kd.get("capacity", 1), 1)
                            if er >= 1.0:
                                base *= (1.0 + 3.0 * er)
                            break
                        break
                return base

            return nx.astar_path(self.G_undirected, src, tgt,
                                 heuristic=heuristic, weight=weight_fn)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    # ══════════════════════════════════════════════════════════════════════
    #  Commit simultaneous updates
    # ══════════════════════════════════════════════════════════════════════

    def _commit_updates(self):
        for p in self.humans:
            dest_changed = (p._next_dest is not None)

            # State
            if p._next_state is not None:
                p.state = p._next_state
            if p._next_panic:
                p.is_panicked = True

            # Position: on-edge takes precedence over at-node
            if p._next_edge is not None:
                p.current_edge = p._next_edge
                p.current_node = None
            elif p._next_node is not None:
                p.current_node = p._next_node
                p.current_edge = None
            if p._next_edge_progress is not None:
                p.edge_progress = p._next_edge_progress

            # Path (only if destination didn't change)
            if not dest_changed and p._next_path is not None:
                p.path = p._next_path[0]
                p.path_idx = p._next_path[1]

            # Destination change → reroute from updated position
            if dest_changed and p.is_active:
                p.destination = p._next_dest
                self._assign_path(p, p.destination)

    # ══════════════════════════════════════════════════════════════════════
    #  Metrics
    # ══════════════════════════════════════════════════════════════════════

    def _compute_metrics(self):
        n_total = len(self.humans)
        counts = {}
        for st in HumanState:
            counts[st] = sum(1 for p in self.humans if p.state == st)
        n_imp = (counts[HumanState.IMPACTED] + counts[HumanState.SURVIVAL]
                 + counts[HumanState.CASUALTY])
        RI = n_imp / max(n_total, 1)
        RS = counts[HumanState.SURVIVAL] / max(n_imp, 1)
        RC = counts[HumanState.CASUALTY] / max(n_imp, 1)
        RL = counts[HumanState.IMPACTED] / max(n_imp, 1)
        return {
            "P_max": n_total, "n_impacted": n_imp,
            "n_survival": counts[HumanState.SURVIVAL],
            "n_casualty": counts[HumanState.CASUALTY],
            "n_arrival": counts[HumanState.ARRIVAL],
            "n_active": (counts[HumanState.IMPACTED] + counts[HumanState.NORMAL]
                         + counts[HumanState.QUEUING]),
            "RI": RI, "RS": RS, "RC": RC, "RL": RL,
        }

    # ══════════════════════════════════════════════════════════════════════
    #  Snapshot & status
    # ══════════════════════════════════════════════════════════════════════

    def _record(self, t_min):
        positions = {}
        for p in self.humans:
            if p.is_active:
                px, py = p.get_position(self.G)
                positions[p.agent_id] = {
                    "x": px, "y": py,
                    "node": p.current_node,
                    "state": p.state.name,
                }
        hz = [{"center": h.center.copy(), "radius": h.radius}
              for h in self.hazards if h.active]
        self.history.append({
            "t": round(t_min, 1),
            "positions": positions, "hazards": hz,
            "counts": {
                "active": sum(1 for p in self.humans if p.is_active),
                "arrival": sum(1 for p in self.humans
                               if p.state == HumanState.ARRIVAL),
                "survival": sum(1 for p in self.humans
                                if p.state == HumanState.SURVIVAL),
                "casualty": sum(1 for p in self.humans
                                if p.state == HumanState.CASUALTY),
            },
        })

    def _print_status(self, t_min):
        c = {"active": 0, "arrival": 0, "survival": 0, "casualty": 0,
             "on_edge": 0}
        for p in self.humans:
            if p.is_active:
                c["active"] += 1
                if p.on_edge:
                    c["on_edge"] += 1
            elif p.state == HumanState.ARRIVAL:
                c["arrival"] += 1
            elif p.state == HumanState.SURVIVAL:
                c["survival"] += 1
            elif p.state == HumanState.CASUALTY:
                c["casualty"] += 1
        print(f"  t={t_min:>6.1f} min | active={c['active']:>5d} "
              f"(edge={c['on_edge']:>4d})  "
              f"arrival={c['arrival']:>5d}  survival={c['survival']:>5d}  "
              f"casualty={c['casualty']:>5d}")
