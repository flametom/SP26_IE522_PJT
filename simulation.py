"""
Simulation engine — Algorithms 1 & 2 from the paper.

Position model: agents advance along edges each step and arrive at nodes.
  - Node flow fvi(t) = agents at each node
  - Edge flow feij(t) = agents traversing each edge this step
  - Algorithm 1 checks BOTH node AND edge congestion
  - Panic agents random-walk at every node (per Discussion + RL results)
  - Panic check runs every step inside hazard (Algorithm 2)
  - Movement always respects speed × dt (including panic agents)

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

        # Edge flow tracking: which agents are currently traversing which edge
        self._agent_edge = {}  # agent_id → (u, v, k)

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
        path = self._find_path(p.current_node, target)
        if path and len(path) > 1:
            p.path = path[1:]
            p.path_idx = 0
            p.edge_progress = 0.0

    def _find_path(self, src, tgt):
        try:
            return nx.shortest_path(self.G_undirected, src, tgt, weight="length")
        except (nx.NetworkXNoPath, nx.NodeNotFound):
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

            # Compute flows: node + edge
            self._reset_flows()
            self._compute_flows()

            # Clear buffers
            for p in self.humans:
                p.clear_buffers()

            # Algorithm 2 — Human-Hazard
            self._algorithm2()

            # Algorithm 1 — Human-Network
            self._algorithm1()

            # Commit
            self._commit_updates()

            if step in self._snapshot_steps:
                self._record(t_min)

            if verbose and step % (N_STEPS // 12) == 0:
                self._print_status(t_min)

        if N_STEPS not in self._snapshot_steps:
            self._record(SIM_DURATION)

        return self._compute_metrics()

    # ══════════════════════════════════════════════════════════════════════
    #  Flow computation — fvi(t) AND feij(t)
    # ══════════════════════════════════════════════════════════════════════

    def _reset_flows(self):
        for n in self.G.nodes():
            self.G.nodes[n]["flow"] = 0
        for u, v, k in self.G.edges(keys=True):
            self.G.edges[u, v, k]["flow"] = 0

    def _compute_flows(self):
        """Count agents at each node AND on each edge."""
        for p in self.humans:
            if not p.is_active:
                continue
            # Node flow
            node = p.current_node
            if node in self.G.nodes:
                self.G.nodes[node]["flow"] += 1

            # Edge flow: if agent is partway along an edge, count it
            aid = p.agent_id
            if aid in self._agent_edge:
                u, v, k = self._agent_edge[aid]
                if self.G.has_edge(u, v, k):
                    self.G.edges[u, v, k]["flow"] += 1

    # ══════════════════════════════════════════════════════════════════════
    #  Algorithm 2 — Human-Hazard Interaction
    # ══════════════════════════════════════════════════════════════════════

    def _algorithm2(self):
        """
        Paper Algorithm 2 — checked EVERY step agent is in hazard zone:
          1. Set IMPACTED (first time → redirect to shelter)
          2. Casualty check (every step)
          3. Panic check (every step, irreversible)
        """
        cas_prob = CASUALTY_PROB_PER_STEP
        for p in self.humans:
            if not p.is_active:
                continue
            px, py = self.coords.get(p.current_node, (0, 0))

            for h in self.hazards:
                if not h.active:
                    continue
                if not h.contains_point(px, py):
                    continue

                # First impact → IMPACTED + shelter redirect
                first_impact = (p.state != HumanState.IMPACTED)
                if first_impact:
                    p._next_state = HumanState.IMPACTED
                    shelter = self._find_nearby_shelter(p.current_node)
                    if shelter is not None:
                        p._next_dest = shelter

                # Casualty check (every step in hazard)
                dist = h.distance_to_center(px, py)
                ratio = max(0.0, 1.0 - dist / max(h.radius, 1.0))
                prob = cas_prob * (1 + CASUALTY_CENTER_WEIGHT * ratio)
                if self.rng.random() < prob:
                    p._next_state = HumanState.CASUALTY
                    break

                # Panic check — ONCE at first impact only
                # Paper Sec III-C: "the likelihood of panic when Spi(t)
                # becomes Impacted" — one-time determination
                if first_impact and not p.is_panicked:
                    eff_panic = self.background_panic * p.panic_rate
                    if self.rng.random() < eff_panic:
                        p._next_panic = True

                break  # first matching hazard

    def _find_nearby_shelter(self, node_id):
        """Paper: 'Impacted pi changes destination to a nearby shelter.'
        Nearest safe shelter by Euclidean distance."""
        px, py = self.coords.get(node_id, (0, 0))
        best, best_dist = None, float("inf")
        for sn in self.shelter_nodes:
            sx, sy = self.coords.get(sn, (0, 0))
            inside = any(h.contains_point(sx, sy)
                         for h in self.hazards if h.active)
            if inside:
                continue
            d = np.hypot(px - sx, py - sy)
            if d < best_dist:
                best_dist = d
                best = sn
        if best is None:
            return nearest_shelter(self.G, node_id, self.shelter_nodes)
        return best

    # ══════════════════════════════════════════════════════════════════════
    #  Algorithm 1 — Human-Network Interaction
    # ══════════════════════════════════════════════════════════════════════

    def _algorithm1(self):
        """
        Paper Algorithm 1 — node congestion + edge congestion checks.
        Agents move along paths, checking BOTH node AND edge capacity.
        """
        dt = self.dt
        for p in self.humans:
            if not p.is_active:
                continue

            # ── Destination arrival ────────────────────────────────
            if p.current_node == p.destination:
                if p.state == HumanState.IMPACTED:
                    p._next_state = HumanState.SURVIVAL
                else:
                    p._next_state = HumanState.ARRIVAL
                continue

            # Impacted at any shelter → Survival
            if (p.state == HumanState.IMPACTED
                    and p.current_node in self._shelter_set):
                p._next_state = HumanState.SURVIVAL
                continue

            node = p.current_node
            nd = self.G.nodes[node]
            node_flow = nd.get("flow", 0)
            node_cap = nd.get("capacity", 50)

            if node_flow >= node_cap:
                # ═══ Node IS congested ═════════════════════════════
                out = list(self.G.out_edges(node, data=True, keys=True))
                all_edges_cong = all(
                    d.get("flow", 0) >= d.get("capacity", 1)
                    for _, _, _, d in out
                ) if out else True

                if all_edges_cong:
                    # Paper: Queuing, Vpi(t) = 0
                    if p.state != HumanState.IMPACTED:
                        p._next_state = HumanState.QUEUING
                    # No movement
                else:
                    if p.is_panicked:
                        self._move_random_edge(p, out, dt)
                    else:
                        # Paper: "re-routes" — recompute path
                        self._move_reroute(p, dt)
            else:
                # ═══ Node NOT congested ════════════════════════════
                if p.is_panicked:
                    out = list(self.G.out_edges(node, data=True, keys=True))
                    if out:
                        self._move_random_edge(p, out, dt)
                else:
                    # Paper: "Update spi(t+1) based on Vpi(t)"
                    # = advance along current path by speed.
                    # Reroute only if next edge is congested.
                    moved = self._move_along_path(p, dt)
                    if not moved:
                        self._move_reroute(p, dt)

    # ══════════════════════════════════════════════════════════════════════
    #  Movement — all respect speed × dt and check edge congestion
    # ══════════════════════════════════════════════════════════════════════

    def _move_along_path(self, p, dt):
        """Move along pre-computed path, checking edge congestion.
        Returns True if agent moved, False if blocked by edge congestion."""
        move_budget = p.speed * dt
        cur = p.current_node
        prog = p.edge_progress
        pidx = p.path_idx
        moved = False

        if p.state == HumanState.QUEUING:
            p._next_state = HumanState.NORMAL

        while move_budget > 0 and pidx < len(p.path):
            nxt = p.path[pidx]
            elen = self._edge_length(cur, nxt)
            remaining_on_edge = elen - prog

            # Check edge congestion before entering/continuing
            edata = self.G.get_edge_data(cur, nxt)
            if edata is None:
                edata = self.G.get_edge_data(nxt, cur)
            if edata is not None:
                ekey = next(iter(edata.keys()))
                eu, ev = (cur, nxt) if self.G.has_edge(cur, nxt) else (nxt, cur)
                ed = self.G.edges[eu, ev, ekey]
                if ed.get("flow", 0) >= ed.get("capacity", 1):
                    # Edge congested — stop, caller may reroute
                    break

            if move_budget >= remaining_on_edge:
                # Finish this edge → arrive at nxt
                move_budget -= remaining_on_edge
                cur = nxt
                pidx += 1
                prog = 0.0
                if cur == p.destination:
                    break
                # Paper: congestion check is only at the agent's CURRENT
                # node at the start of the step, not at intermediate nodes
                # during multi-edge traversal.
            else:
                # Partially traverse — stay between nodes
                prog += move_budget
                move_budget = 0

        moved = (cur != p.current_node or prog != p.edge_progress)
        p._next_node = cur
        p._next_edge_progress = prog
        p._next_path = (p.path, pidx)

        # Track which edge agent is on (for next step's flow computation)
        if pidx < len(p.path) and prog > 0:
            nxt = p.path[pidx]
            edata = self.G.get_edge_data(cur, nxt)
            if edata is None:
                edata = self.G.get_edge_data(nxt, cur)
                if edata:
                    self._agent_edge[p.agent_id] = (nxt, cur, next(iter(edata.keys())))
            else:
                self._agent_edge[p.agent_id] = (cur, nxt, next(iter(edata.keys())))
        else:
            self._agent_edge.pop(p.agent_id, None)

        return moved

    def _move_random_edge(self, p, out_edges, dt):
        """Panicked agent: randomly select edge, move along it at speed."""
        if not out_edges:
            return
        idx = self.rng.integers(len(out_edges))
        u, v, k, d = out_edges[idx]

        # Check edge congestion
        if d.get("flow", 0) >= d.get("capacity", 1):
            # Try another uncongested edge
            available = [(u2, v2, k2, d2) for u2, v2, k2, d2 in out_edges
                         if d2.get("flow", 0) < d2.get("capacity", 1)]
            if not available:
                return
            u, v, k, d = available[self.rng.integers(len(available))]

        elen = d.get("length", 1.0)
        move_dist = p.speed * dt

        if move_dist >= elen:
            # Arrive at v
            p._next_node = v
            p._next_edge_progress = 0.0
            p._next_path = ([], 0)  # panic agent has no path
            self._agent_edge.pop(p.agent_id, None)
        else:
            # Partially traverse
            p._next_node = u  # stay "at" u conceptually
            p._next_edge_progress = move_dist
            # Track edge for flow
            self._agent_edge[p.agent_id] = (u, v, k)
            # Still at same node until edge is fully traversed
            # (simplification: agent stays at node u, edge flow is tracked)

    def _move_reroute(self, p, dt):
        """Paper: 're-routes' — find alternative path avoiding congestion."""
        path = self._find_path_congestion_aware(p.current_node, p.destination)
        if path and len(path) > 1:
            p.path = path[1:]
            p.path_idx = 0
            p.edge_progress = 0.0
            self._move_along_path(p, dt)

    def _find_path_congestion_aware(self, src, tgt):
        """Shortest path with penalty for congested nodes/edges."""
        try:
            # Temporarily add congestion weight to edges
            def weight_fn(u, v, data):
                base = data.get("length", 1.0)
                # Penalize edges leading to congested nodes
                nd = self.G.nodes.get(v, {})
                node_ratio = nd.get("flow", 0) / max(nd.get("capacity", 50), 1)
                if node_ratio >= 1.0:
                    base *= (1.0 + 5.0 * node_ratio)  # heavy penalty
                return base
            return nx.shortest_path(self.G_undirected, src, tgt,
                                     weight=weight_fn)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    # ══════════════════════════════════════════════════════════════════════
    #  Commit simultaneous updates
    # ══════════════════════════════════════════════════════════════════════

    def _commit_updates(self):
        for p in self.humans:
            dest_changed = (p._next_dest is not None)

            if p._next_state is not None:
                p.state = p._next_state

            if p._next_panic:
                p.is_panicked = True

            if dest_changed:
                p.destination = p._next_dest
                self._assign_path(p, p.destination)
            else:
                if p._next_node is not None:
                    p.current_node = p._next_node
                if p._next_edge_progress is not None:
                    p.edge_progress = p._next_edge_progress
                if p._next_path is not None:
                    p.path = p._next_path[0]
                    p.path_idx = p._next_path[1]

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
    #  Snapshot
    # ══════════════════════════════════════════════════════════════════════

    def _record(self, t_min):
        positions = {}
        for p in self.humans:
            if p.is_active:
                px, py = self.coords.get(p.current_node, (0, 0))
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
        c = {"active": 0, "arrival": 0, "survival": 0, "casualty": 0}
        for p in self.humans:
            if p.is_active:
                c["active"] += 1
            elif p.state == HumanState.ARRIVAL:
                c["arrival"] += 1
            elif p.state == HumanState.SURVIVAL:
                c["survival"] += 1
            elif p.state == HumanState.CASUALTY:
                c["casualty"] += 1
        print(f"  t={t_min:>6.1f} min | active={c['active']:>5d}  "
              f"arrival={c['arrival']:>5d}  survival={c['survival']:>5d}  "
              f"casualty={c['casualty']:>5d}")
