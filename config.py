"""
Configuration parameters for the community evacuation simulation.
Based on: Shi, Lee, Yang — "Multi-agent Modeling of Human Traffic Dynamics
for Rapid Response to Public Emergency in Spatial Networks" (IEEE CASE 2024)

Interpretation:
  - 1 time step = 1 minute (120 steps total)
  - Table III "Speed (m)" = m/step = m/min
  - Table IV "(m/s)" = m/step = m/min (paper notation inconsistency)
  - Table IV "Area as Radius" = INITIAL radius (grows via Expansion Speed)
"""

# ── Simulation ──────────────────────────────────────────────────────────────
SIM_DURATION = 120      # minutes = 120 steps
DT = 1.0                # 1 minute per step
N_STEPS = int(SIM_DURATION / DT)

# ── Community targets ───────────────────────────────────────────────────────
# Paper: "Leveraging geographical data from open sources like OpenStreetMap"
# 2021 paper: "place name can be an area within certain distances of
#   an address, a university, and a city."
# Per-community overrides: simplify, network_type, retain_all.
# Defaults (if omitted): simplify=True, network_type="walk", retain_all=True.
COMMUNITIES = {
    # Uniform config: simplify=True, retain_all=True, network_type="walk"
    # for methodological consistency across all communities.
    # 2021 paper (Zhang & Yang): "breakpoints are not considered" → simplify=True
    # retain_all=True preserves disconnected sub-networks (bridged in network_model).
    # Per-community edge count discrepancies are documented in reproduction_report.
    "PSU-UP": {"place": "Pennsylvania State University, University Park, PA, USA"},
    "UVA-C":  {"place": "University of Virginia, Charlottesville, VA, USA",
               "building_center": (38.0336, -78.5080), "building_dist": 500},
    "VT-B":   {"place": "Virginia Tech, Blacksburg, VA, USA"},
    "RA-PA":  {"center": (40.3357, -75.9269), "dist": 1170},
    "KOP-PA": {"center": (40.0876, -75.3890), "dist": 860},
}
DEFAULT_COMMUNITY = "PSU-UP"

# ── Network ─────────────────────────────────────────────────────────────────
# Paper: ceij = leij × Dmax (Eq. 4), cvi from community amenity data (Eq. 2).
# Dmax varies by highway type; node capacity from incident edge sum.
# See network_model.py for the per-type Dmax table.
NODE_CAPACITY_DEFAULT = 50    # fallback for nodes without edge data
BUILDING_NODE_CAPACITY = 100  # building nodes

# ── Human agent groups (Table III — EXACT) ──────────────────────────────────
# Speed (m) = m/step = m/min
HUMAN_GROUPS = [
    {"id": 1, "age_range": (18, 25), "speed": 96,  "panic_rate": 0.60, "portion": 0.60},
    {"id": 2, "age_range": (25, 50), "speed": 84,  "panic_rate": 0.50, "portion": 0.20},
    {"id": 3, "age_range": (40, 60), "speed": 72,  "panic_rate": 0.20, "portion": 0.20},
]

# ── Hazard agent types (Table IV — EXACT) ──────────────────────────────────
# "(m/s)" interpreted as m/step = m/min
# "Area as Radius" = INITIAL radius; grows via Expansion Speed each step
HAZARD_TYPES = [
    {
        "type": 1,
        "lifespan_range": (130, 170),
        "initial_radius_range": (150, 200),     # meters
        "expansion_speed_range": (25, 35),       # m/step
        "movement_speed_range": (30, 42),        # m/step
    },
    {
        "type": 2,
        "lifespan_range": (30, 50),
        "initial_radius_range": (20, 80),
        "expansion_speed_range": (0, 10),
        "movement_speed_range": (90, 102),
    },
    {
        "type": 3,
        "lifespan_range": (120, 170),
        "initial_radius_range": (200, 400),
        "expansion_speed_range": (100, 120),
        "movement_speed_range": (102, 204),
    },
]

# ── Experimental design (Fig. 2 — EXACT) ──────────────────────────────────
PANIC_RATES = [0.10, 0.30, 0.50, 0.70, 0.90]
P_MAX_LEVELS = [2000, 5000, 8000]
H_MAX_LEVELS = [5, 10, 15]

# ── Casualty model (not specified in paper — minimal assumption) ───────────
CASUALTY_PROB_PER_STEP = 0.001    # per step while inside hazard
CASUALTY_CENTER_WEIGHT = 2.0      # higher near center

# ── Shelter ─────────────────────────────────────────────────────────────────
# Paper: "shelters provided by community authorities"
# We use OSM amenity=shelter data (no artificial supplementation).

# ── Visualization ───────────────────────────────────────────────────────────
FIG_DPI = 150
SNAPSHOT_TIMES = [0, 30, 60, 90, 120]
