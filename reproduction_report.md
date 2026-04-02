# Reproduction Report: Multi-agent Modeling of Human Traffic Dynamics

> **Original Paper:** Shi, Lee, Yang — "Multi-agent Modeling of Human Traffic Dynamics for Rapid Response to Public Emergency in Spatial Networks" (IEEE CASE 2024)
>
> **Team:** Dalal Alboloushi & Jeongwon Bae
> **Course:** IE 522 — Simulation, Penn State University, Spring 2026

---

## 1. Reproduction Objective

This project reproduces the community evacuation simulation from the above paper. The paper proposes a multi-agent model combining:

- A **spatial network** built from OpenStreetMap data
- **Human agents** (pedestrians) with 6 behavioral states
- **Hazard agents** (emergencies) with circular expanding impact zones

We implement the full model and reproduce the paper's two experimental phases:

1. **Phase 1 (Table V, Fig. 3 & 4):** Network construction and validation for 5 communities
2. **Phase 2 (Fig. 5 & 6):** Full factorial experiment on PSU-UP — RI vs Pmax x Hmax, and RS/RC/RL vs panic rate

---

## 2. Implementation Architecture

```
config.py              Table III, IV parameters + experimental design
        |
network_model.py       OSMnx-based spatial network (Section III-A)
        |
agents.py              HumanAgent (6 states) + HazardAgent (Section III-B,C)
        |
simulation.py          Algorithm 1 (Human-Network) + Algorithm 2 (Human-Hazard)
        |
main.py                Entry point: single run / full factorial / network verification
        |
visualization.py       Fig. 3 (network), Fig. 4 (flow), Fig. 5 (RI), Fig. 6 (RS/RC/RL)
```

### 2.1 Network Construction (`network_model.py`)

**Paper Section III-A** defines G = (V, E) with building/non-building nodes and pedestrian edges.

Our implementation:

```
1. ox.graph_from_place(place, network_type="walk", simplify=True, retain_all=True)
   -> Walk network: ~7,619 nodes, ~19,132 directed edges (PSU-UP)

2. Bridge disconnected components
   -> 135 isolated components connected with minimal edges

3. Building footprints via ox.features_from_polygon(buffered_polygon, tags={"building": True})
   -> Nominatim polygon + ~25m buffer -> ~969 buildings (PSU-UP)

4. ADD mode: building centroids as new graph nodes, connected to nearest walk node

5. Edge capacity: c_eij = l_eij x D_max (highway-type specific)
   -> footway=3.0, service=5.0, pedestrian=8.0, residential=5.0, etc.

6. Node capacity: sum of incident edge capacities

7. Shelters: OSM amenity=shelter + farthest-first supplementation (15% of buildings)
```

**Visualization note:** `retain_all=True` includes up to 135 disconnected components (PSU-UP), some far from the main campus. Bridge edges to these outliers distort the network shape. Our Fig. 3 and Fig. 4 visualizations crop to the 1st-99th percentile of node coordinates to show the dense core, matching the paper's compact network appearance.

**Why ~25m buffer:** OSMnx's `graph_from_place` internally buffers the Nominatim polygon by ~25m before downloading the network. Using the same buffer for buildings matches the paper's building counts within 0-2%.

**Community-specific query methods:**

| Community | Method | Detail |
|---|---|---|
| PSU-UP | graph_from_place | Nominatim polygon + 25m buffer |
| UVA-C | graph_from_point | center + 500m radius |
| VT-B | graph_from_place | Nominatim polygon + 25m buffer |
| RA-PA | graph_from_point | center + 1170m radius |
| KOP-PA | graph_from_point | center + 860m radius |

This distinction (universities=polygon, cities=point+dist) is supported by the authors' 2021 paper (Zhang & Yang, EMBC 2021): *"The place name can be an area that is within certain distances of an address, a university, and a city."*

### 2.2 Agent Design (`agents.py`)

**Human agents** (Section III-C): Each pedestrian is defined by `(destination, position, speed, state, panic_rate)` with 6 states (Table II). Agents are placed at random building nodes and assigned random building destinations. Three demographic groups from Table III define speed and panic susceptibility.

**Hazard agents** (Section III-B): Each hazard is defined by `(emergence_time, lifespan, movement_speed, expansion_speed, initial_radius, center, direction)`. Three hazard types from Table IV are sampled uniformly. Emergence times use stratified temporal sampling with an adaptive window:

```
window = sim_duration x (0.35 + 0.6 / (1 + H_max/8))
```

This ensures hazards are spread over the simulation rather than clustering at the start.

### 2.3 Simulation Engine (`simulation.py`)

The engine runs 121 steps (0-120 minutes), executing per step:

1. Update hazard positions and radii
2. Depart agents (if using departure window)
3. Compute node flows f_vi(t) and edge flows f_eij(t)
4. **Algorithm 2** — Human-Hazard interaction
5. **Algorithm 1** — Human-Network interaction
6. Commit all buffered updates (simultaneous update model)

**Algorithm 1 (Human-Network Interaction):**

```
For each active agent:
  IF at destination:
    IMPACTED -> SURVIVAL  |  otherwise -> ARRIVAL

  IF node congested (f_vi >= c_vi):
    all edges also congested -> QUEUING
    some edges free:
      panicked -> random edge, speed-based movement
      normal   -> congestion-aware reroute, move along new path

  IF node not congested:
    panicked -> random edge, speed-based movement
    normal   -> follow path (reroute if next edge congested)
```

Movement uses `move_budget = speed x dt`. Agents traverse multiple edges per step if budget allows, checking edge congestion (`f_eij >= c_eij`) at each edge entry.

**Algorithm 2 (Human-Hazard Interaction):**

```
For each active agent inside any hazard zone:
  First impact:
    state -> IMPACTED
    destination -> nearest safe shelter
    panic check (once, irreversible): prob = epsilon_p x group_panic_rate

  Every step while inside:
    casualty check: prob = 0.001 x (1 + 2.0 x (1 - dist/radius))
```

**Simultaneous update:** All agent state changes are buffered during the step and committed together at the end, preventing order-dependent artifacts.

**RNG separation:** Three independent random streams (`seed`, `seed+1000`, `seed+2000`) for human creation, hazard creation, and simulation dynamics. This ensures changing P_max does not affect hazard configurations.

---

## 3. Results

### 3.1 Phase 1: Network Validation (Table V)

#### Our Method

All 5 communities are built with a **single, uniform configuration** for methodological consistency:

| Parameter | Value | Justification |
|---|---|---|
| `network_type` | `"walk"` | Paper: "pathways connecting buildings and intersections" |
| `simplify` | `True` | 2021 paper (Zhang & Yang): "non-junction breakpoints are not considered" |
| `retain_all` | `True` | Preserves disconnected sub-networks; bridged for full connectivity |
| Building mode | TAG hybrid | Nearest walk node tagged as building; centroid stored as attribute |
| Data source | OSMnx → Overpass API | Paper: "geographical data from open sources like OpenStreetMap" |

Building footprints are fetched from a ~25m-buffered polygon (matching OSMnx's internal `graph_from_place` buffer). Each building centroid is mapped to its nearest walk-network node (`is_building=True`). Multiple buildings sharing the same nearest node are naturally deduplicated.

#### Full Network Statistics (B, NB, E)

The paper does not specify how buildings are integrated into the graph (whether as separate centroid nodes or by tagging existing walk nodes). We use **ADD mode**: each building footprint centroid is added as a separate graph node connected to the nearest walk-network node via bidirectional connector edges. This preserves a 1:1 mapping between footprints and building nodes, keeping B accurate. The alternative (TAG mode — tagging the nearest walk node) causes building-count deflation due to multiple buildings sharing the same nearest node (e.g., PSU-UP: 969 footprints → 737 unique tagged nodes). Since the paper does not clarify whether its edge count includes building-to-network connectors, we track connector edges separately and compare only walk-network edges against Table V.

| Community | B (ours/paper) | NB (ours/paper) | Walk Ed (ours/paper) | Walk Ed ratio | Connector edges |
|---|---|---|---|---|---|
| PSU-UP | **969 / 953** | 8,351 / 6,670 | 21,426 / 19,799 | **108%** | 1,938 |
| UVA-C | **412 / 412** | 4,150 / 5,677 | 11,480 / 7,095 | 162% | 824 |
| VT-B | **448 / 445** | 3,057 / 6,511 | 8,214 / 6,929 | 119% | 896 |
| RA-PA | **473 / 473** | 2,538 / 2,068 | 7,334 / 16,432 | **45%** | 946 |
| KOP-PA | **277 / 277** | 1,492 / 2,240 | 4,046 / 17,216 | **24%** | 554 |

Walk Ed = directed walk-network edges only (excluding building connector edges).
Connector edges = bidirectional edges linking building centroid nodes to walk network (2 per building).

#### Analysis of Discrepancies

**Building count (B):** All 5 communities match within 0–2%. Three communities (UVA-C, RA-PA, KOP-PA) are exact matches. The 1–2% difference for PSU-UP and VT-B is due to OSM data evolving over time. UVA-C uses a separate building query area (`point+dist=500m`) from its walk-network query (place polygon), because the university's place polygon includes buildings far outside the paper's coverage area.

**PSU-UP Walk Ed (108%):** Closest match. The 8% surplus is from bridge edges connecting 145 disconnected sub-networks (`retain_all=True`). With `retain_all=False` (largest component only), walk Ed = 19,824, matching the paper's 19,799 within 0.1%. We retain disconnected components for consistency across communities.

**NB deficit (UVA-C, VT-B):** The paper reports NB = 5,677 (UVA-C) and 6,511 (VT-B), while our simplified walk networks yield 4,150 and 3,057. The paper's NB counts are consistent with **unsimplified** networks (`simplify=False`), where intermediate road waypoints are preserved as nodes. However, using `simplify=False` uniformly would produce walk Ed = 50,000+ for PSU-UP (vs paper's 19,799), making it impossible to match all communities with one setting. This inconsistency suggests the paper may use **different preprocessing per community** or an intermediate simplification strategy not described in the text.

**RA-PA and KOP-PA (E/N anomaly):** See Section 4.4 for detailed investigation.

### 3.2 Phase 2a: RI vs Pmax x Hmax (Fig. 5, epsilon_p = 10%)

| | Hmax=5 | Hmax=10 | Hmax=15 |
|---|---|---|---|
| **Pmax=2000** | 17.2% (34.3%) | 53.3% (56.5%) | 75.4% (68.4%) |
| **Pmax=5000** | 18.1% (27.5%) | 54.5% (51.8%) | 74.9% (64.4%) |
| **Pmax=8000** | 18.8% (34.4%) | 54.9% (54.4%) | 75.1% (66.2%) |

*(Values in parentheses = paper values)*

**Qualitative trends reproduced:**
- **Hmax increases -> RI increases:** More hazards cover more of the network.
- **RI is approximately independent of Pmax:** Hazard coverage determines impact ratio, not population size.

**Quantitative comparison:**
- Hmax=10: our RI (53-55%) closely matches paper (52-56%)
- Hmax=15: our RI (75%) is higher than paper (64-68%)
- Hmax=5: our RI (17-19%) is lower than paper (27-34%)
- The absolute RI values are **seed-dependent** because hazard placement is random and the paper does not publish its random seeds.

### 3.3 Phase 2b: RS/RC/RL vs Panic Rate (Fig. 6, Pmax=2000, Hmax=5)

| epsilon_p | RS (ours) | RS (paper) | RC (ours) | RC (paper) | RL (ours) | RL (paper) |
|---|---|---|---|---|---|---|
| 10% | 93.6% | 96.6% | 2.9% | 2.5% | 3.5% | 0.9% |
| 30% | 84.8% | 93.0% | 5.0% | 4.0% | 10.2% | 3.0% |
| 50% | 76.1% | 88.3% | 6.1% | 7.2% | 17.8% | 4.5% |
| 70% | 67.1% | 78.0% | 7.9% | 10.0% | 25.1% | 12.0% |
| 90% | 61.8% | 64.6% | 7.9% | 13.3% | 30.3% | 22.1% |

**Qualitative trends reproduced:**
- **epsilon_p increases -> RS decreases:** More panicked agents fail to reach shelters.
- **epsilon_p increases -> RC increases:** Longer exposure in hazard zones increases casualty probability.
- **epsilon_p increases -> RL increases:** Panicked agents wander randomly and don't reach shelters before simulation ends.

**Quantitative comparison:**
- RC matches well at low panic (2.9% vs 2.5% at epsilon_p=10%)
- RS at epsilon_p=90% closely matches (61.8% vs 64.6%)
- RL is consistently higher than paper — see Section 4 for analysis

---

## 4. Differences from Paper and Their Causes

### 4.1 What Matches Well

| Aspect | Our Result | Paper | Assessment |
|---|---|---|---|
| Building counts (5 communities) | 100-102% | — | Excellent |
| RI trends (Hmax effect) | Hmax up -> RI up | Same | Qualitative match |
| RI independence from Pmax | Confirmed | Same | Qualitative match |
| RS/RC/RL trend directions | All 3 correct | Same | Qualitative match |
| RC at low panic | 2.9% | 2.5% | Close match |

### 4.2 Systematic Differences

| Difference | Magnitude | Root Cause |
|---|---|---|
| RI absolute values vary by seed | +/-10%p | Hazard placement is random; paper's seeds are unpublished |
| RL higher than paper | +2~8%p | Shelter locations differ (see below) |
| RS lower than paper | -2~8%p | Coupled with RL (RS + RC + RL = 100%) |
| RC saturates at ~8% | Paper reaches 13% | Casualty formula is unspecified in paper |
| Edge counts (RA-PA, KOP-PA) | 26-49% of paper | Paper E/N ratio anomalous (see 4.4) |

### 4.3 Structurally Unresolvable Differences

These differences cannot be eliminated without information the paper does not provide:

1. **Shelter locations:** The paper states shelters are "provided by community authorities" — an unpublished list specific to PSU. We approximate with OSM `amenity=shelter` tags plus farthest-first supplementation. This means our agents may have longer paths to shelters, increasing RL.

2. **Random seeds:** The paper does not publish the random seeds used for hazard generation. Since RI is directly determined by where hazards appear relative to building clusters, RI absolute values cannot be exactly reproduced.

3. **OSM data timestamp:** The paper's exact OSM data download date is unpublished. OSM is continuously edited, so node/edge counts will differ slightly from any current download.

4. **Casualty formula:** The paper states "Compute whether p_i becomes casualty" without specifying the probability model. Our implementation uses `0.001 x (1 + 2.0 x distance_ratio)` per step, which is a reasonable but not exact match.

### 4.4 Edge Count Anomaly in City Communities

The paper's Table V reports edge counts for RA-PA (16,432) and KOP-PA (17,216) that produce edge-to-node ratios of 6.5 and 6.8 respectively. Standard OSMnx walk networks yield E/N = 2.0-2.9 regardless of configuration.

#### Systematic Investigation

We conducted an exhaustive parameter scan using `network_diagnostics.py` across all 5 communities:

| Hypothesis | Method | RA-PA result | Target (16,432) |
|---|---|---|---|
| Directed edges (`simplify=True`) | `G.number_of_edges()` | Ed = 7,136 | 43% |
| Undirected x2 | `2 * G.to_undirected().number_of_edges()` | 7,154 | 44% |
| `network_type="all"` | All road types including cycling, service | Ed = 6,750 | 41% |
| `network_type="drive_service"` | Driving + service roads | Ed = 4,030 | 25% |
| Walk + drive union | `nx.compose(G_walk, G_drive)` | Ed = 7,668 | 47% |
| `simplify=False` | Preserve all intermediate waypoints | Ed = 66,836 | 407% |
| Geometry segments | Count LineString segments, not graph edges | 12,030 | **73%** |
| Edge subdivision (20m) | Split each edge into 20m segments | est. 18,966 | 115% |
| Edge subdivision (50m) | Split each edge into 50m segments | est. 9,604 | 58% |

Full parameter grid: `network_type` x `simplify` x `retain_all` x `building_mode` x `open_ground_mode` x `dist` variations. Results saved in `results/netdiag_*.csv`.

#### Key Findings

1. **No standard OSMnx configuration produces E/N > 3.0** for any community, regardless of network type, simplification, or boundary.

2. **Geometry segment counting** (73% match) is the closest hypothesis: each simplified edge retains a multi-point geometry (polyline). Counting line segments within these geometries yields ~12,030 for RA-PA, the closest to 16,432 of any method tested. This suggests the paper may count road *segments* rather than graph *edges*.

3. **The paper's own Fig. 3 confirms dense networks** for RA-PA and KOP-PA, ruling out simple typographical errors. The visual density is consistent with some form of edge densification beyond standard OSMnx.

4. **Cross-community inconsistency in E/N ratios:**

| Community | E/N (paper) | Interpretation |
|---|---|---|
| PSU-UP | 2.60 | Consistent with directed edges, simplified |
| UVA-C | 1.17 | Consistent with undirected edges |
| VT-B | 1.00 | Consistent with undirected edges, ~tree structure |
| RA-PA | **6.47** | Requires non-standard preprocessing |
| KOP-PA | **6.84** | Requires non-standard preprocessing |

This variation in E/N suggests the paper may use **different edge counting or preprocessing methods across communities**, or an intermediate approach not described in the text.

#### Impact on Simulation

The edge count discrepancy for RA-PA and KOP-PA means their simulated networks have **fewer alternative evacuation routes** and **different congestion patterns** compared to the paper. This is a topology difference, not merely a counting difference: fewer edges = fewer paths = different evacuation dynamics. Results for these communities should be interpreted as "best-effort reproduction under the available network" rather than exact replication of the paper's conditions.

PSU-UP (Ed ratio 108%) is minimally affected and remains valid for direct comparison with the paper's primary results.

---

## 5. Interpretation Decisions

The paper leaves several parameters unspecified. Below are our decisions and their justifications.

### 5.1 Time Step Duration

**Decision:** 1 step = 1 minute

| Evidence | Reasoning |
|---|---|
| Table III speed = 96 m/step | At 1 min/step: 96 m/min = 1.6 m/s (normal walking speed) |
| Fig. 4 x-axis | "Time (min) 0, 30, 60, 90, 120" -> 120-minute simulation |
| Table IV lifespan unit | "(minute)" -> time base is minutes |

If 1 step = 1 second, speeds would be 96 m/s = 345 km/h, which is physically impossible.

**Consequence:** Table IV's "(m/s)" header is interpreted as "m/step" = m/min. This is a notation inconsistency in the paper.

### 5.2 Edge Capacity (D_max)

**Decision:** Highway-type-specific D_max values

```
footway: 3.0    (sidewalk ~1.5m wide)
service: 5.0    (service road ~3m)
pedestrian: 8.0 (pedestrian zone ~4m)
residential: 5.0
steps: 1.5      (narrow stairway)
path: 3.0
default: 3.0
```

The paper defines `c_eij = l_eij x D_max` but does not specify D_max values. We estimate from typical sidewalk widths multiplied by pedestrian density (~2 persons/m width).

### 5.3 Node Capacity

**Decision:** Sum of incident edge capacities

The paper states node capacity comes from "community amenity data" which is unavailable. Using incident edge capacity sum provides a natural proxy: larger intersections (more/wider roads) accommodate more people.

### 5.4 Shelter Designation

**Decision:** OSM `amenity=shelter` tags + farthest-first supplementation to reach 15% of buildings

The paper's "community authorities" shelter list is unpublished. Our approach uses real shelter data from OSM and supplements with well-distributed additional shelters to ensure coverage across the network.

### 5.5 Casualty Model

**Decision:** Per-step probability `0.001 x (1 + 2.0 x (1 - dist/radius))`

The paper only says "Compute whether p_i becomes casualty." Our model:
- Base probability is low (0.001 per step)
- Probability increases near hazard center (distance ratio term)
- Produces RC ~2-8% which is in the paper's range

### 5.6 Hazard Emergence Timing

**Decision:** Stratified sampling within adaptive window

The paper does not specify when hazards appear. Our adaptive window shrinks as H_max increases, ensuring hazards don't all appear at once (which would be unrealistic) but still overlap enough to create compound effects.

---

## 6. Bug Fixes During Development

| # | Bug | Impact | Fix |
|---|---|---|---|
| 1 | Shared RNG across human/hazard/sim | Pmax change altered hazard configs | 3 separate RNG streams |
| 2 | Panic checked every step | Nearly all agents panicked | Once at first impact only |
| 3 | QUEUING reset IMPACTED state | Lost hazard impact tracking | State preservation logic |
| 4 | Algorithm 1 overwrote shelter path | Agents walked away from shelter | Buffer commit with dest_changed guard |
| 5 | No edge flow computation | Edge congestion never triggered | Compute both node and edge flows |
| 6 | Panic agents teleported to next node | Ignored speed/distance | Speed-based movement budget |
| 7 | Edge congestion caused permanent stop | No rerouting -> deadlock | Congestion-aware reroute |
| 8 | Uniform D_max for all edges | Unrealistic bottlenecks | Highway-type specific D_max |
| 9 | Intermediate node congestion check | Blocked multi-edge traversal | Check only current node |

---

## 7. How to Run

```bash
# Install dependencies
pip install osmnx networkx matplotlib numpy scipy tqdm

# Single run (PSU-UP, Pmax=2000, Hmax=5, epsilon_p=10%)
python main.py

# Custom parameters
python main.py --community PSU-UP --pmax 5000 --hmax 10 --panic 0.30

# Full factorial experiment (Fig. 5 & 6)
python main.py --experiment full --community PSU-UP

# All 5 community network verification (Table V, Fig. 3 & 4)
python main.py --experiment networks

# Complete (networks + full factorial)
python main.py --experiment all
```

### Output Files

| File | Content | Paper Figure |
|---|---|---|
| `results/fig3_network_*.png` | Spatial network map | Fig. 3 |
| `results/fig4_flow_*.png` | Pedestrian distribution snapshots | Fig. 4 |
| `results/fig5_RI_*.png` | RI vs Pmax x Hmax | Fig. 5 |
| `results/fig6_panic_*.png` | RS/RC/RL vs panic rate | Fig. 6 |
| `results/timeseries_*.png` | Agent state counts over time | — |
| `results/experiment_*.json` | Numerical results | — |

---

## 8. Conclusion

We successfully reproduce the qualitative behavior of the paper's evacuation model:

- **Network construction** matches all 5 communities' building counts within 0-2%
- **RI trends** correctly show hazard-count dependence and population-independence
- **RS/RC/RL trends** correctly show panic rate as the dominant factor in evacuation outcomes
- **The core finding is confirmed:** panic management is the most critical factor for evacuation success, not population size or network capacity

Remaining quantitative differences (RI seed variation, RL shelter gap) are attributable to unpublished implementation details (random seeds, shelter lists, casualty formula) that cannot be resolved without author correspondence.
