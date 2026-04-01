"""
Agent definitions — Sections III-B and III-C of the paper.

HazardAgent  h_i = (t_h0, ζ_h, V_h, V_s_h, s_h(t), a_h(t))
HumanAgent   p_i = (d_pi, s_pi(t), V_pi(t), S_pi(t), ε_pi)

Position model (Algorithm 1):
  - Agent is either AT a node  (current_node is set, current_edge is None)
  - Or ON an edge             (current_edge is set, current_node is None)
"""

from enum import Enum, auto
import numpy as np


# ── Human agent states (Table II) ──────────────────────────────────────────

class HumanState(Enum):
    NORMAL   = auto()
    QUEUING  = auto()
    IMPACTED = auto()
    ARRIVAL  = auto()
    SURVIVAL = auto()
    CASUALTY = auto()


# ── Human Agent ────────────────────────────────────────────────────────────

class HumanAgent:
    """
    Represents a single pedestrian in the simulation.

    Position model:
      - At a node:  current_node is int, current_edge is None
      - On an edge: current_edge is (u, v, key), current_node is None
                    edge_progress = meters traveled from u toward v
    """

    __slots__ = (
        "agent_id", "group_id", "destination", "origin",
        "current_node", "current_edge", "edge_progress",
        "state", "speed", "base_speed",
        "panic_rate", "is_panicked",
        "path", "path_idx",
        "departure_time", "departed",
        # Buffers for simultaneous update
        "_next_state", "_next_dest", "_next_panic",
        "_next_node", "_next_edge", "_next_edge_progress",
        "_next_path",
    )

    def __init__(self, agent_id, group_id, origin, destination,
                 speed, panic_rate, departure_time=0.0):
        self.agent_id = agent_id
        self.group_id = group_id
        self.origin = origin
        self.destination = destination
        # Position: start at origin node
        self.current_node = origin
        self.current_edge = None
        self.edge_progress = 0.0
        # State
        self.state = HumanState.NORMAL
        self.speed = speed
        self.base_speed = speed
        self.panic_rate = panic_rate
        self.is_panicked = False
        # Path
        self.path = []
        self.path_idx = 0
        # Departure
        self.departure_time = departure_time
        self.departed = (departure_time == 0.0)
        # Buffers
        self._next_state = None
        self._next_dest = None
        self._next_panic = None
        self._next_node = None
        self._next_edge = None
        self._next_edge_progress = None
        self._next_path = None

    # ── position queries ───────────────────────────────────────────────

    @property
    def at_node(self):
        return self.current_node is not None

    @property
    def on_edge(self):
        return self.current_edge is not None

    def get_position(self, G):
        """Return interpolated (x, y) in projected coordinates."""
        if self.at_node:
            nd = G.nodes[self.current_node]
            return nd["x"], nd["y"]
        else:
            u, v, _ = self.current_edge
            ux, uy = G.nodes[u]["x"], G.nodes[u]["y"]
            vx, vy = G.nodes[v]["x"], G.nodes[v]["y"]
            edge_data = G.get_edge_data(u, v)
            edge_len = next(iter(edge_data.values())).get("length", 1.0)
            frac = min(self.edge_progress / max(edge_len, 1.0), 1.0)
            return ux + frac * (vx - ux), uy + frac * (vy - uy)

    @property
    def is_active(self):
        return (self.departed
                and self.state in (HumanState.NORMAL, HumanState.QUEUING,
                                   HumanState.IMPACTED))

    @property
    def has_ended(self):
        return self.state in (HumanState.ARRIVAL, HumanState.SURVIVAL,
                              HumanState.CASUALTY)

    def clear_buffers(self):
        self._next_state = None
        self._next_dest = None
        self._next_panic = None
        self._next_node = None
        self._next_edge = None
        self._next_edge_progress = None
        self._next_path = None


# ── Hazard Agent ───────────────────────────────────────────────────────────

class HazardAgent:
    """
    Represents a single hazard event.
    h_i = (t_h0, ζ_h, V_h, V_s_h, s_h(t), a_h(t))
    """

    __slots__ = (
        "hazard_id", "hazard_type", "emergence_time", "lifespan",
        "movement_speed", "expansion_speed", "initial_radius",
        "center", "radius",
        "direction", "active",
    )

    def __init__(self, hazard_id, hazard_type, emergence_time,
                 lifespan, movement_speed, expansion_speed,
                 center, initial_radius, direction):
        self.hazard_id = hazard_id
        self.hazard_type = hazard_type
        self.emergence_time = emergence_time
        self.lifespan = lifespan
        self.movement_speed = movement_speed
        self.expansion_speed = expansion_speed
        self.initial_radius = initial_radius
        self.center = np.array(center, dtype=float)
        self.radius = 0.0
        self.direction = np.array(direction, dtype=float)
        self.active = False

    def update(self, t_min, dt):
        if t_min < self.emergence_time:
            self.active = False
            return
        elapsed = t_min - self.emergence_time
        if elapsed > self.lifespan:
            self.active = False
            return
        self.active = True
        self.radius = self.initial_radius + self.expansion_speed * elapsed
        self.center = self.center + self.direction * self.movement_speed * dt

    def contains_point(self, x, y):
        if not self.active:
            return False
        dx = x - self.center[0]
        dy = y - self.center[1]
        return (dx * dx + dy * dy) <= self.radius ** 2

    def distance_to_center(self, x, y):
        return np.hypot(x - self.center[0], y - self.center[1])


# ── Factory helpers ────────────────────────────────────────────────────────

def create_human_agents(G, building_nodes, P_max, human_groups, rng,
                        departure_window=0.0):
    agents = []
    aid = 0
    for grp in human_groups:
        n_grp = int(P_max * grp["portion"])
        for _ in range(n_grp):
            origin = rng.choice(building_nodes)
            dest = rng.choice(building_nodes)
            while dest == origin:
                dest = rng.choice(building_nodes)
            dep_time = rng.uniform(0, departure_window)
            agents.append(HumanAgent(
                agent_id=aid,
                group_id=grp["id"],
                origin=origin,
                destination=dest,
                speed=grp["speed"],
                panic_rate=grp["panic_rate"],
                departure_time=dep_time,
            ))
            aid += 1
    return agents


def create_hazard_agents(G, building_nodes, H_max, hazard_types,
                         sim_duration_min, rng):
    coords = {n: (G.nodes[n]["x"], G.nodes[n]["y"]) for n in building_nodes}
    xs = [c[0] for c in coords.values()]
    ys = [c[1] for c in coords.values()]
    x_range = (min(xs), max(xs))
    y_range = (min(ys), max(ys))

    hazards = []
    window = sim_duration_min * (0.35 + 0.6 / (1 + H_max / 8))
    for hid in range(H_max):
        ht = hazard_types[hid % len(hazard_types)]
        slot_start = (hid / H_max) * window
        slot_end = ((hid + 1) / H_max) * window
        emergence = rng.uniform(slot_start, slot_end)
        lifespan = rng.uniform(*ht["lifespan_range"])
        cx = rng.uniform(*x_range)
        cy = rng.uniform(*y_range)
        angle = rng.uniform(0, 2 * np.pi)
        direction = np.array([np.cos(angle), np.sin(angle)])
        hazards.append(HazardAgent(
            hazard_id=hid,
            hazard_type=ht["type"],
            emergence_time=emergence,
            lifespan=lifespan,
            movement_speed=rng.uniform(*ht["movement_speed_range"]),
            expansion_speed=rng.uniform(*ht["expansion_speed_range"]),
            center=(cx, cy),
            initial_radius=rng.uniform(*ht["initial_radius_range"]),
            direction=direction,
        ))
    return hazards
