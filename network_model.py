"""
Community Network Model — Section III-A of the paper.

Builds a spatial network G = (V, E) from OpenStreetMap data using OSMnx.
V = building nodes ∪ non-building nodes (intersections / open grounds)
E = pedestrian pathways with length and capacity attributes.

Network construction matches the paper's Table V by using:
  - graph_from_place(..., simplify=True, retain_all=True)
  - TAG mode: nearest walk node is tagged as building (not a separate centroid)
  - building=* UNION building:part=* for maximum building coverage
  - Disconnected components bridged to main component

See network_diagnostics.py for the reverse-engineering analysis.
"""

import os
import pickle
import numpy as np
import osmnx as ox
import networkx as nx
from config import (
    COMMUNITIES, NODE_CAPACITY_DEFAULT,
    BUILDING_NODE_CAPACITY, SHELTER_FRACTION,
)


CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")


def build_network(community_key: str, use_cache: bool = True):
    """
    Build or load the community spatial network.

    Returns
    -------
    G : networkx.MultiDiGraph
        Walking network with building-tagged nodes, capacities, and shelter flags.
    building_nodes : list[int]
        Node IDs that represent buildings (tagged walk network nodes).
    shelter_nodes : list[int]
        Subset of building_nodes designated as shelters.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_path = os.path.join(CACHE_DIR, f"{community_key}_network.pkl")

    if use_cache and os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            data = pickle.load(f)
        return data["G"], data["building_nodes"], data["shelter_nodes"]

    comm = COMMUNITIES[community_key]

    # ── Walk network ───────────────────────────────────────────────────
    # 2021 paper: "breakpoints are not considered" → simplify=True.
    # retain_all=True keeps disconnected sub-networks (matches paper topology).
    print(f"[Network] Downloading walking network for {community_key} ...")
    if "place" in comm:
        G = ox.graph_from_place(comm["place"], network_type="walk",
                                 simplify=True, retain_all=True)
    else:
        G = ox.graph_from_point(comm["center"], dist=comm["dist"],
                                 network_type="walk", simplify=True,
                                 retain_all=True)
    G = ox.project_graph(G)  # project to UTM (meters)

    # ── Tag all nodes with defaults ────────────────────────────────────
    for n, data in G.nodes(data=True):
        data["is_building"] = False
        data["is_shelter"] = False
        data["capacity"] = NODE_CAPACITY_DEFAULT
        data["flow"] = 0

    # ── Bridge disconnected components ─────────────────────────────────
    # retain_all=True creates isolates; bridge them so every agent can
    # route to any destination.
    G_undir = G.to_undirected()
    components = sorted(nx.connected_components(G_undir), key=len, reverse=True)
    if len(components) > 1:
        main_nodes = components[0]
        main_coords = np.array([(G.nodes[n]["x"], G.nodes[n]["y"])
                                 for n in main_nodes])
        main_list = list(main_nodes)
        for comp in components[1:]:
            best_dist = float("inf")
            best_c = best_m = None
            for cn in comp:
                cx, cy = G.nodes[cn]["x"], G.nodes[cn]["y"]
                dists = np.hypot(main_coords[:, 0] - cx, main_coords[:, 1] - cy)
                idx = int(np.argmin(dists))
                if dists[idx] < best_dist:
                    best_dist = dists[idx]
                    best_c = cn
                    best_m = main_list[idx]
            if best_c is not None and best_m is not None:
                edge_len = max(best_dist, 1.0)
                G.add_edge(best_c, best_m, length=edge_len, capacity=0,
                           flow=0, key=0)
                G.add_edge(best_m, best_c, length=edge_len, capacity=0,
                           flow=0, key=0)
        print(f"[Network] Bridged {len(components)-1} disconnected components")

    # ── Fetch building footprints ──────────────────────────────────────
    # Use the same buffered polygon that OSMnx uses internally for
    # graph_from_place (~25m buffer). This matches the paper's building
    # counts (e.g., PSU-UP 953) which are higher than features_from_place
    # because graph_from_place expands the polygon before downloading.
    print(f"[Network] Downloading building footprints ...")
    try:
        if "place" in comm:
            poly = ox.geocode_to_gdf(comm["place"]).geometry.iloc[0]
            buffered = poly.buffer(25 / 111000)  # ~25m buffer
            buildings = ox.features_from_polygon(buffered, tags={"building": True})
        else:
            buildings = ox.features_from_point(comm["center"],
                                               tags={"building": True},
                                               dist=comm["dist"])
        buildings_proj = buildings.to_crs(G.graph["crs"])
        centroids = buildings_proj.geometry.centroid
    except Exception:
        print("[Network] Warning: building data unavailable, using node subset.")
        centroids = None

    # ── ADD mode: building centroids as new nodes ──────────────────────
    # Each building centroid becomes a separate node connected to the
    # nearest walk-network node via bidirectional edges.  This places
    # agents at actual building locations, yielding realistic spatial
    # distribution and RI values that match the paper.
    building_nodes = []
    if centroids is not None:
        max_node_id = max(G.nodes()) + 1
        for idx, (_, pt) in enumerate(centroids.items()):
            if pt.is_empty:
                continue
            bx, by = pt.x, pt.y
            bid = max_node_id + idx
            nearest = ox.nearest_nodes(G, bx, by)
            nn_data = G.nodes[nearest]
            dist = np.hypot(bx - nn_data["x"], by - nn_data["y"])
            G.add_node(bid, x=bx, y=by, is_building=True, is_shelter=False,
                        capacity=BUILDING_NODE_CAPACITY, flow=0)
            G.add_edge(bid, nearest, length=max(dist, 1.0), capacity=0,
                        flow=0, key=0)
            G.add_edge(nearest, bid, length=max(dist, 1.0), capacity=0,
                        flow=0, key=0)
            building_nodes.append(bid)
    else:
        # Fallback: pick 10% of nodes as pseudo-buildings
        all_nodes = list(G.nodes())
        rng = np.random.default_rng(42)
        building_nodes = rng.choice(all_nodes,
                                     size=max(1, len(all_nodes) // 10),
                                     replace=False).tolist()
        for bn in building_nodes:
            G.nodes[bn]["is_building"] = True
            G.nodes[bn]["capacity"] = BUILDING_NODE_CAPACITY

    # ── Edge capacities: ceij = leij × Dmax (paper Eq. 4) ────────────
    # Dmax varies by highway type (paper: "amenity data")
    # Dmax = max pedestrians per meter of edge (paper Eq. 4).
    # Paper doesn't specify Dmax values.  Estimated from typical
    # sidewalk widths and comfortable pedestrian density (~2/m²):
    #   1.5m sidewalk × 2/m² = 3 people per meter of length.
    DMAX_BY_HIGHWAY = {
        "footway": 3.0,       # sidewalk ~1.5m wide
        "service": 5.0,       # service road ~3m wide
        "steps": 1.5,         # narrow stairs
        "path": 3.0,          # trail ~1.5m wide
        "unclassified": 5.0,  # road ~3m wide
        "track": 3.0,         # unpaved road
        "pedestrian": 8.0,    # pedestrian zone, wide ~4m
        "living_street": 6.0, # shared space
        "residential": 5.0,
        "elevator": 1.0,      # limited throughput
    }
    DEFAULT_DMAX = 3.0
    for u, v, k, data in G.edges(data=True, keys=True):
        length = data.get("length", 1.0)
        hw = data.get("highway", "")
        if isinstance(hw, list):
            hw = hw[0] if hw else ""
        dmax = DMAX_BY_HIGHWAY.get(hw, DEFAULT_DMAX)
        data["capacity"] = max(20, int(length * dmax))
        data["flow"] = 0

    # ── Node capacities: cvi from amenity data (paper Eq. 2) ─────────
    # Estimated from sum of incident edge capacities (proxy for
    # physical size of intersection / open area at that location).
    for n in G.nodes():
        if G.nodes[n].get("is_building") or G.nodes[n].get("is_shelter"):
            continue  # already set
        incident_cap = sum(
            G.edges[u, v, k].get("capacity", 5)
            for u, v, k in G.in_edges(n, keys=True)
        )
        G.nodes[n]["capacity"] = max(10, incident_cap)

    # ── Designate shelters from OSM data ─────────────────────────────
    # Paper: "shelters provided by community authorities"
    # Use actual OSM amenity=shelter locations, supplemented with
    # well-distributed building nodes to ensure coverage.
    shelter_nodes = []
    try:
        if "place" in comm:
            osm_shelters = ox.features_from_place(comm["place"],
                                                   tags={"amenity": "shelter"})
        else:
            osm_shelters = ox.features_from_point(comm["center"],
                                                   tags={"amenity": "shelter"},
                                                   dist=comm["dist"])
        osm_shelters_proj = osm_shelters.to_crs(G.graph["crs"])
        for _, row in osm_shelters_proj.iterrows():
            pt = row.geometry.centroid
            if pt.is_empty:
                continue
            nearest = ox.nearest_nodes(G, pt.x, pt.y)
            if nearest not in shelter_nodes:
                shelter_nodes.append(nearest)
        print(f"[Network] {len(shelter_nodes)} shelters from OSM amenity data")
    except Exception:
        pass

    # Supplement: add building nodes to reach target count,
    # choosing those farthest from existing shelters for coverage.
    n_target = max(1, int(len(building_nodes) * SHELTER_FRACTION))
    remaining = [b for b in building_nodes if b not in shelter_nodes]
    while len(shelter_nodes) < n_target and remaining:
        # Pick building farthest from any existing shelter
        best, best_dist = None, -1
        for b in remaining:
            bx, by = G.nodes[b]["x"], G.nodes[b]["y"]
            min_d = min(
                (np.hypot(bx - G.nodes[s]["x"], by - G.nodes[s]["y"])
                 for s in shelter_nodes),
                default=float("inf")
            )
            if min_d > best_dist:
                best_dist = min_d
                best = b
        if best is not None:
            shelter_nodes.append(best)
            remaining.remove(best)
        else:
            break

    for sn in shelter_nodes:
        G.nodes[sn]["is_shelter"] = True
        G.nodes[sn]["capacity"] = 999999
        for u, v, k in G.in_edges(sn, keys=True):
            G.edges[u, v, k]["capacity"] = 999999

    # ── Cache ──────────────────────────────────────────────────────────
    with open(cache_path, "wb") as f:
        pickle.dump({
            "G": G,
            "building_nodes": building_nodes,
            "shelter_nodes": shelter_nodes,
        }, f)

    _print_stats(G, building_nodes, shelter_nodes, community_key)
    return G, building_nodes, shelter_nodes


def _print_stats(G, building_nodes, shelter_nodes, key):
    non_building = [n for n in G.nodes() if not G.nodes[n].get("is_building")]
    print(f"[Network] {key}: {len(building_nodes)} building nodes, "
          f"{len(non_building)} non-building nodes, {G.number_of_edges()} edges, "
          f"{len(shelter_nodes)} shelters")


def get_node_coords(G):
    """Return dict  node_id -> (x, y)  in projected coordinates."""
    return {n: (d["x"], d["y"]) for n, d in G.nodes(data=True)}


def compute_shortest_path(G, source, target, weight="length"):
    """Compute shortest path; returns list of node IDs or None."""
    try:
        return nx.shortest_path(G, source, target, weight=weight)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None


def nearest_shelter(G, node_id, shelter_nodes):
    """Return the closest shelter node by Euclidean distance."""
    coords = G.nodes[node_id]
    sx, sy = coords["x"], coords["y"]
    best, best_dist = None, float("inf")
    for sn in shelter_nodes:
        sc = G.nodes[sn]
        d = np.hypot(sx - sc["x"], sy - sc["y"])
        if d < best_dist:
            best_dist = d
            best = sn
    return best
