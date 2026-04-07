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
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra as sp_dijkstra
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

        # Scipy sparse matrix for fast batch SSSP (replaces per-agent A*)
        self._build_sparse_matrix()
        self._batch_preds = {}

        self.history = []
        self._snapshot_steps = {int(t / self.dt) for t in SNAPSHOT_TIMES
                                if t <= SIM_DURATION}
        self._initial_routing()

    # ══════════════════════════════════════════════════════════════════════
    #  Routing
    # ══════════════════════════════════════════════════════════════════════

    def _initial_routing(self):
        # Batch SSSP for all initial destinations at once
        dest_set = set(p.destination for p in self.humans)
        dest_list = list(dest_set)
        dest_indices = np.array([self._node_to_idx[d] for d in dest_list])
        _, predecessors = sp_dijkstra(
            self._sp_matrix, indices=dest_indices,
            return_predecessors=True,
        )
        self._batch_preds = {
            d: predecessors[i] for i, d in enumerate(dest_list)
        }
        for p in self.humans:
            path = self._find_path_batch(p.origin, p.destination)
            if path and len(path) > 1:
                p.path = path[1:]
                p.path_idx = 0

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

    def _find_path_noisy(self, src, tgt):
        """Shortest path with noisy edge weights for panicked agents.

        Paper III-C: "When panicked, human agents deviate from optimal
        evacuation routes" due to "limited observations of the community
        network."  Modeled as multiplicative noise on edge lengths —
        panicked agents misperceive distances, producing suboptimal but
        directionally correct paths."""
        try:
            coords = self.coords
            rng = self.rng

            def heuristic(u, v):
                ux, uy = coords.get(u, (0, 0))
                vx, vy = coords.get(v, (0, 0))
                return ((ux - vx) ** 2 + (uy - vy) ** 2) ** 0.5

            def noisy_weight(u, v, data):
                base = data.get("length", 1.0)
                # Multiplicative noise: perceived length = actual × (1 + noise)
                # noise ~ Exp(1) gives heavy-tailed distortion
                return base * (1.0 + rng.exponential(1.0))

            return nx.astar_path(self.G_undirected, src, tgt,
                                 heuristic=heuristic, weight=noisy_weight)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    # ══════════════════════════════════════════════════════════════════════
    #  Scipy batch SSSP — replaces per-agent networkx A*
    # ══════════════════════════════════════════════════════════════════════

    def _build_sparse_matrix(self):
        """Convert undirected graph to scipy CSR matrix (one-time cost)."""
        nodes_list = list(self.G_undirected.nodes())
        self._node_to_idx = {n: i for i, n in enumerate(nodes_list)}
        self._idx_to_node = nodes_list
        n = len(nodes_list)

        rows, cols, weights = [], [], []
        for u, v, d in self.G_undirected.edges(data=True):
            i, j = self._node_to_idx[u], self._node_to_idx[v]
            w = d.get("length", 1.0)
            rows.append(i); cols.append(j); weights.append(w)
            rows.append(j); cols.append(i); weights.append(w)

        self._sp_matrix = csr_matrix(
            (weights, (rows, cols)), shape=(n, n)
        )

    def _batch_compute_paths(self):
        """Pre-compute shortest-path trees for active agents' destinations.
        Called once per step; results are looked up in _find_path_batch."""
        dest_set = set()
        for p in self.humans:
            if not p.is_active:
                continue
            if p._next_state in (HumanState.CASUALTY, HumanState.IMPACTED):
                continue
            if p.is_panicked:
                continue
            dest_set.add(p.destination)

        if not dest_set:
            self._batch_preds = {}
            return

        dest_list = list(dest_set)
        dest_indices = np.array([self._node_to_idx[d] for d in dest_list])

        _, predecessors = sp_dijkstra(
            self._sp_matrix, indices=dest_indices,
            return_predecessors=True,
        )

        self._batch_preds = {
            d: predecessors[i] for i, d in enumerate(dest_list)
        }

    def _find_path_batch(self, src, tgt):
        """Look up shortest path from pre-computed batch SSSP.
        Falls back to networkx A* if target not in batch."""
        if src == tgt:
            return [src]

        preds = self._batch_preds.get(tgt)
        if preds is None:
            return self._find_path(src, tgt)

        src_idx = self._node_to_idx.get(src)
        tgt_idx = self._node_to_idx.get(tgt)
        if src_idx is None or tgt_idx is None:
            return None

        # Reconstruct path: follow predecessors from src toward tgt.
        # preds[j] = predecessor of j on shortest-path tree rooted at tgt,
        # so chasing preds from src walks toward tgt.
        path_idx = []
        node = src_idx
        limit = len(self._idx_to_node)
        for _ in range(limit):
            path_idx.append(node)
            if node == tgt_idx:
                break
            nxt = preds[node]
            if nxt < 0:          # -9999 = unreachable
                return None
            node = nxt
        else:
            return None

        return [self._idx_to_node[i] for i in path_idx]

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
            self._batch_compute_paths()
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
                        self._move_with_fresh_path(p, dt, congestion_aware=True)
            else:
                # Node not congested
                if p.is_panicked:
                    # Paper Discussion: "panicking pedestrians choose
                    # paths randomly at nodes" + "persist in following
                    # random paths once panic occurs"
                    out = list(self.G.out_edges(node, data=True, keys=True))
                    if out:
                        self._move_random_edge(p, out, dt)
                else:
                    # Paper: "Update spi(t+1) based on Vpi(t)"
                    self._move_with_fresh_path(p, dt, congestion_aware=False)

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

        # Panicked agents stop at v — next step they choose random edge
        # from the at-node branch (paper: "persist in following random paths")
        if p.is_panicked or budget <= 0:
            p._next_node = v
            p._next_edge = None
            p._next_edge_progress = 0.0
            return

        # Normal agents recompute path from v and continue
        path = self._find_path_batch(v, p.destination)
        if not path or len(path) < 2:
            p._next_node = v
            p._next_edge = None
            p._next_edge_progress = 0.0
            return

        p.path = path[1:]
        p.path_idx = 0
        self._traverse_path(p, v, 0, budget)

    def _move_with_fresh_path(self, p, dt, congestion_aware=False):
        """Paper: 'Update spi(t+1) based on Vpi(t)' — recompute shortest
        path from current position every step, then advance.

        Panicked agents use noisy edge weights (paper: "limited observations
        of the community network" → imperfect knowledge of distances,
        causing deviation from optimal routes).

        congestion_aware: if True, also penalize congested nodes/edges
        (used at congested nodes where paper says 'pi re-routes')."""
        if congestion_aware:
            path = self._find_path_congestion_aware(p.current_node, p.destination)
        elif p.is_panicked:
            path = self._find_path_noisy(p.current_node, p.destination)
        else:
            path = self._find_path_batch(p.current_node, p.destination)

        if not path or len(path) < 2:
            return

        p.path = path[1:]
        p.path_idx = 0

        # Clear queuing if we can move (guard: don't overwrite Algo 2)
        if p.state == HumanState.QUEUING and p._next_state is None:
            p._next_state = HumanState.NORMAL

        self._traverse_path(p, p.current_node, 0, p.speed * dt)

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
            if not p.departed:
                continue
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
                "impacted": sum(1 for p in self.humans
                                if p.state == HumanState.IMPACTED),
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
