#!/usr/bin/env python3
"""
Network Reverse-Engineering Diagnostics
=========================================
Scans (network_type × simplify × retain_all × truncate_by_edge × building_mode
× open_ground × dist_override) and scores each against Table V.

Score = |B-Bt|/Bt + |NB-NBt|/NBt + min(|Ed-Et|, |Eu-Et|)/Et

Usage:
  python network_diagnostics.py                          # PSU-UP quick scan
  python network_diagnostics.py --community all          # all 5 communities
  python network_diagnostics.py --community RA-PA        # single community
  python network_diagnostics.py --quick                  # reduced grid
  python network_diagnostics.py --with-history           # + historical snapshots
"""

import argparse
import csv
import json
import os
import time
from itertools import product

import networkx as nx
import numpy as np
import osmnx as ox

# ── Paper Table V targets ──────────────────────────────────────────────────
TABLE_V = {
    "PSU-UP": {"B": 953, "NB": 6670, "E": 19799},
    "UVA-C":  {"B": 412, "NB": 5677, "E": 7095},
    "VT-B":   {"B": 445, "NB": 6511, "E": 6929},
    "RA-PA":  {"B": 473, "NB": 2068, "E": 16432},
    "KOP-PA": {"B": 277, "NB": 2240, "E": 17216},
}

# Per-community query configurations.
# "place" → graph_from_polygon via geocode.
# "point" + "dists" → graph_from_point with multiple dist candidates.
# "alt_places" → alternative place queries to try.
COMMUNITIES = {
    "PSU-UP": {
        "place": "Pennsylvania State University, University Park, PA, USA",
    },
    "UVA-C": {
        "place": "University of Virginia, Charlottesville, VA, USA",
        "point": (38.0336, -78.5080),
        "dists": [500, 1000, 1500, 2000, 2500],
    },
    "VT-B": {
        "place": "Virginia Tech, Blacksburg, VA, USA",
        "alt_places": ["Blacksburg, VA, USA"],
        "point": (37.2296, -80.4139),
        "dists": [1500, 2000, 2500, 3000],
    },
    "RA-PA": {
        "place": "Reading, PA, USA",
        "point": (40.3357, -75.9269),
        "dists": [1170, 1500, 2000, 2500, 3000],
    },
    "KOP-PA": {
        "place": "King of Prussia, PA, USA",
        "point": (40.0876, -75.3890),
        "dists": [860, 1170, 1500, 2000],
    },
}

# Open-ground OSM tags (paper: "parks, lawns, parking lots")
OPEN_GROUND_TAGS = {
    "leisure": ["park", "garden", "pitch", "playground", "sports_centre"],
    "amenity": "parking",
    "landuse": ["grass", "recreation_ground", "meadow"],
}

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")


# ── Raw data fetching ─────────────────────────────────────────────────────

def _apply_overpass_settings(snapshot_date=None):
    if snapshot_date:
        ox.settings.overpass_settings = (
            f'[out:json][timeout:300][date:"{snapshot_date}T00:00:00Z"]'
        )
    else:
        ox.settings.overpass_settings = '[out:json][timeout:300]'
    ox.settings.requests_timeout = 300
    ox.settings.use_cache = True
    ox.settings.cache_folder = CACHE_DIR


def fetch_from_polygon(place_name, network_type, snapshot_date=None):
    """Fetch raw graph + buildings + open-ground via place polygon."""
    _apply_overpass_settings(snapshot_date)

    print(f"    Geocoding '{place_name}'...", flush=True)
    gdf = ox.geocode_to_gdf(place_name)
    polygon = gdf.geometry.iloc[0]
    # ~25m buffer for buildings/open-ground (matches network_model.py and
    # OSMnx graph_from_place internal buffer behaviour)
    buffered = polygon.buffer(25 / 111000)

    print(f"    Fetching raw {network_type} network (polygon)...", flush=True)
    G_raw = ox.graph_from_polygon(buffered, network_type=network_type,
                                   simplify=False, retain_all=True,
                                   truncate_by_edge=True)

    print(f"    Fetching buildings...", flush=True)
    try:
        buildings = ox.features_from_polygon(buffered, tags={"building": True})
    except Exception:
        buildings = None

    print(f"    Fetching open-ground...", flush=True)
    try:
        open_ground = ox.features_from_polygon(buffered, tags=OPEN_GROUND_TAGS)
    except Exception:
        open_ground = None

    return G_raw, buildings, open_ground, f"place:{place_name}"


def fetch_from_point(center, dist, network_type, snapshot_date=None):
    """Fetch raw graph + buildings + open-ground via center+dist."""
    _apply_overpass_settings(snapshot_date)

    print(f"    Fetching raw {network_type} network (point, dist={dist})...",
          flush=True)
    G_raw = ox.graph_from_point(center, dist=dist, network_type=network_type,
                                 simplify=False, retain_all=True,
                                 truncate_by_edge=True)

    print(f"    Fetching buildings...", flush=True)
    try:
        buildings = ox.features_from_point(center, tags={"building": True},
                                            dist=dist)
    except Exception:
        buildings = None

    print(f"    Fetching open-ground...", flush=True)
    try:
        open_ground = ox.features_from_point(center, tags=OPEN_GROUND_TAGS,
                                              dist=dist)
    except Exception:
        open_ground = None

    return G_raw, buildings, open_ground, f"point:dist={dist}"


def apply_graph_options(G_raw, simplify, retain_all):
    """Apply simplify / retain_all to a raw graph copy."""
    G = G_raw.copy()
    if simplify:
        G = ox.simplify_graph(G)
    if not retain_all:
        G = ox.truncate.largest_component(G)
    return G


# ── Building / open-ground node modes ─────────────────────────────────────

def count_buildings_tag(G_proj, buildings_proj):
    if buildings_proj is None:
        return set(), 0
    tagged = set()
    for _, pt in buildings_proj.geometry.centroid.items():
        if pt.is_empty:
            continue
        tagged.add(ox.nearest_nodes(G_proj, pt.x, pt.y))
    return tagged, 0


def count_buildings_add(G_proj, buildings_proj):
    if buildings_proj is None:
        return set(), 0
    max_id = max(G_proj.nodes()) + 1
    added = set()
    n_edges = 0
    for idx, (_, pt) in enumerate(buildings_proj.geometry.centroid.items()):
        if pt.is_empty:
            continue
        bid = max_id + idx
        nearest = ox.nearest_nodes(G_proj, pt.x, pt.y)
        nn = G_proj.nodes[nearest]
        dist = max(np.hypot(pt.x - nn["x"], pt.y - nn["y"]), 1.0)
        G_proj.add_node(bid, x=pt.x, y=pt.y)
        G_proj.add_edge(bid, nearest, length=dist, key=0)
        G_proj.add_edge(nearest, bid, length=dist, key=0)
        added.add(bid)
        n_edges += 2
    return added, n_edges


def count_open_ground_add(G_proj, og_proj, building_ids):
    if og_proj is None:
        return 0, 0
    max_id = max(G_proj.nodes()) + 1
    added = set()
    n_edges = 0
    for idx, (_, pt) in enumerate(og_proj.geometry.centroid.items()):
        if pt.is_empty:
            continue
        nearest = ox.nearest_nodes(G_proj, pt.x, pt.y)
        if nearest in building_ids or nearest in added:
            continue
        oid = max_id + idx
        nn = G_proj.nodes[nearest]
        dist = max(np.hypot(pt.x - nn["x"], pt.y - nn["y"]), 1.0)
        G_proj.add_node(oid, x=pt.x, y=pt.y)
        G_proj.add_edge(oid, nearest, length=dist, key=0)
        G_proj.add_edge(nearest, oid, length=dist, key=0)
        added.add(oid)
        n_edges += 2
    return len(added), n_edges


def count_open_ground_tag(G_proj, og_proj, building_ids):
    if og_proj is None:
        return 0, 0
    tagged = set()
    for _, pt in og_proj.geometry.centroid.items():
        if pt.is_empty:
            continue
        nearest = ox.nearest_nodes(G_proj, pt.x, pt.y)
        if nearest not in building_ids:
            tagged.add(nearest)
    return len(tagged), 0


# ── Evaluate one candidate ────────────────────────────────────────────────

def evaluate_candidate(G_proj, buildings_proj, og_proj,
                       building_mode, open_ground_mode):
    G = G_proj.copy()

    if building_mode == "tag":
        building_ids, b_edges = count_buildings_tag(G, buildings_proj)
    else:
        building_ids, b_edges = count_buildings_add(G, buildings_proj)

    og_nodes = 0
    og_edges = 0
    if open_ground_mode == "add":
        og_nodes, og_edges = count_open_ground_add(G, og_proj, building_ids)
    elif open_ground_mode == "tag":
        og_nodes, og_edges = count_open_ground_tag(G, og_proj, building_ids)

    total = G.number_of_nodes()
    B = len(building_ids)
    NB = total - B
    Ed = G.number_of_edges()
    Eu = G.to_undirected().number_of_edges()

    comps = list(nx.weakly_connected_components(G))
    lc_ratio = len(max(comps, key=len)) / total if total > 0 else 0

    return {
        "B": B, "NB": NB, "total": total,
        "Ed": Ed, "Eu": Eu,
        "og_nodes": og_nodes, "og_edges": og_edges,
        "b_edges": b_edges,
        "n_comp": len(comps),
        "lc_ratio": round(lc_ratio, 4),
    }


def score(stats, target):
    Bt, NBt, Et = target["B"], target["NB"], target["E"]
    s_b = abs(stats["B"] - Bt) / Bt
    s_nb = abs(stats["NB"] - NBt) / NBt
    s_e = min(abs(stats["Ed"] - Et), abs(stats["Eu"] - Et)) / Et
    return round(s_b + s_nb + s_e, 4)


# ── Main scan ─────────────────────────────────────────────────────────────

def run_scan(community_key, quick=False, snapshot_dates=None):
    target = TABLE_V[community_key]
    comm = COMMUNITIES[community_key]
    print(f"\n{'='*72}")
    print(f"  Network Diagnostics: {community_key}")
    print(f"  Target: B={target['B']}  NB={target['NB']}  E={target['E']}")
    print(f"{'='*72}\n")

    if snapshot_dates is None:
        snapshot_dates = [None]

    # Parameter grid
    simplify_opts = [True, False]
    retain_opts = [True, False]
    building_modes = ["tag", "add"]
    network_types = ["walk", "all"] if not quick else ["walk"]
    if quick:
        og_modes = ["off", "add"]
    else:
        og_modes = ["off", "tag", "add"]

    # Build list of (fetcher_func, fetcher_args, source_label) candidates
    fetch_jobs = []
    for snap_date in snapshot_dates:
        date_label = snap_date or "current"
        # Place polygon queries
        if "place" in comm:
            for nt in network_types:
                fetch_jobs.append((
                    "polygon", comm["place"], None, None, nt, snap_date,
                    f"snap={date_label} query=place net={nt}"
                ))
        # Alternative place queries
        for alt in comm.get("alt_places", []):
            for nt in network_types:
                fetch_jobs.append((
                    "polygon", alt, None, None, nt, snap_date,
                    f"snap={date_label} query=place:{alt} net={nt}"
                ))
        # Point + dist queries
        if "point" in comm:
            dists = comm.get("dists", [])
            for d in dists:
                for nt in network_types:
                    fetch_jobs.append((
                        "point", None, comm["point"], d, nt, snap_date,
                        f"snap={date_label} query=point:d={d} net={nt}"
                    ))

    results = []
    hdr = (f"{'simp':>5} {'ret':>5} {'bmode':>5} {'og':>4} | "
           f"{'B':>5} {'NB':>6} {'Ed':>6} {'Eu':>6} {'comp':>4} | "
           f"{'score':>7}")

    for mode, place, center, dist, net_type, snap_date, label in fetch_jobs:
        print(f"\n--- {label} ---", flush=True)

        try:
            if mode == "polygon":
                G_raw, buildings, open_ground, src = fetch_from_polygon(
                    place, net_type, snap_date)
            else:
                G_raw, buildings, open_ground, src = fetch_from_point(
                    center, dist, net_type, snap_date)
        except Exception as e:
            print(f"  FETCH FAILED: {e}", flush=True)
            continue

        print(f"  {hdr}", flush=True)

        for simplify, retain_all in product(simplify_opts, retain_opts):
            try:
                G_proc = apply_graph_options(G_raw, simplify, retain_all)
                G_proj = ox.project_graph(G_proc)
            except Exception as e:
                print(f"  simp={simplify} ret={retain_all} — graph error: {e}",
                      flush=True)
                continue

            crs = G_proj.graph["crs"]
            b_proj = buildings.to_crs(crs) if buildings is not None else None
            og_proj = (open_ground.to_crs(crs)
                       if open_ground is not None else None)

            for bmode, ogmode in product(building_modes, og_modes):
                try:
                    st = evaluate_candidate(G_proj, b_proj, og_proj,
                                            bmode, ogmode)
                    sc = score(st, target)
                    row = {
                        "source": label,
                        "network_type": net_type,
                        "simplify": simplify,
                        "retain_all": retain_all,
                        "building_mode": bmode,
                        "open_ground": ogmode,
                        **st, "score": sc,
                    }
                    results.append(row)
                    flag = " ***" if sc < 0.10 else (
                           " **" if sc < 0.20 else (
                           " *" if sc < 0.35 else ""))
                    print(f"  {str(simplify):>5} {str(retain_all):>5} "
                          f"{bmode:>5} {ogmode:>4} | "
                          f"{st['B']:>5} {st['NB']:>6} "
                          f"{st['Ed']:>6} {st['Eu']:>6} {st['n_comp']:>4} | "
                          f"{sc:.4f}{flag}", flush=True)
                except Exception as e:
                    print(f"  {str(simplify):>5} {str(retain_all):>5} "
                          f"{bmode:>5} {ogmode:>4} | ERROR: {e}", flush=True)

    results.sort(key=lambda r: r["score"])

    # Save
    os.makedirs(RESULTS_DIR, exist_ok=True)
    out_csv = os.path.join(RESULTS_DIR, f"netdiag_{community_key}.csv")
    if results:
        with open(out_csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=results[0].keys())
            w.writeheader()
            w.writerows(results)
    out_json = os.path.join(RESULTS_DIR, f"netdiag_{community_key}.json")
    with open(out_json, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n[Saved] {out_csv}")
    print(f"[Saved] {out_json}")

    # Top 10
    print(f"\n{'='*72}")
    print(f"  TOP 10 CANDIDATES  "
          f"(target: B={target['B']} NB={target['NB']} E={target['E']})")
    print(f"{'='*72}")
    for i, r in enumerate(results[:10]):
        print(f"  #{i+1:>2}  score={r['score']:.4f}  "
              f"B={r['B']:>5}  NB={r['NB']:>6}  "
              f"Ed={r['Ed']:>6}  Eu={r['Eu']:>6}  "
              f"simp={r['simplify']}  ret={r['retain_all']}  "
              f"bm={r['building_mode']}  og={r['open_ground']}  "
              f"net={r['network_type']}  src={r['source']}")

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Scan OSMnx parameters to match paper Table V")
    parser.add_argument("--community", default="PSU-UP",
                        choices=list(COMMUNITIES.keys()) + ["all"])
    parser.add_argument("--quick", action="store_true",
                        help="Reduced grid (no 'all' network_type, "
                             "fewer open-ground modes)")
    parser.add_argument("--with-history", action="store_true",
                        help="Also scan 2024-01-01 and 2023-06-01 snapshots")
    args = parser.parse_args()

    dates = [None]
    if args.with_history:
        dates = [None, "2024-01-01", "2023-06-01"]

    keys = list(COMMUNITIES.keys()) if args.community == "all" else [args.community]

    t0 = time.time()
    all_results = {}
    for key in keys:
        all_results[key] = run_scan(key, quick=args.quick, snapshot_dates=dates)

    # Summary across communities
    if len(keys) > 1:
        print(f"\n{'='*72}")
        print(f"  SUMMARY — Best score per community")
        print(f"{'='*72}")
        for key in keys:
            target = TABLE_V[key]
            res = all_results[key]
            if res:
                best = res[0]
                print(f"  {key:>6}  score={best['score']:.4f}  "
                      f"B={best['B']:>5}/{target['B']}  "
                      f"NB={best['NB']:>6}/{target['NB']}  "
                      f"Ed={best['Ed']:>6}  Eu={best['Eu']:>6}  "
                      f"(target E={target['E']})  "
                      f"net={best['network_type']}  "
                      f"simp={best['simplify']}  "
                      f"src={best['source']}")
            else:
                print(f"  {key:>6}  NO RESULTS")

    print(f"\n[Done] {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
