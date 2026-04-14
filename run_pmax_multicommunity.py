#!/usr/bin/env python3
"""
Extended Pmax experiment across multiple communities.

For each community, Pmax range is scaled by building count so that
agent/building ratios span [2, 5, 8, 10, 15, 20, 25, 30, 35, 40, 50].
This makes breakpoints directly comparable across communities.

Shelter count = 62% of buildings (consistent with PSU-UP analysis).
"""

import argparse
import json
import math
import multiprocessing as mp
import os
import time
import numpy as np

from config import SIM_DURATION, HUMAN_GROUPS, HAZARD_TYPES, COMMUNITIES
from network_model import build_network
from agents import create_human_agents, create_hazard_agents
from simulation import EvacuationSimulation

HAZARD_SEED = 1135
BASE_SEED = 42
N_SEEDS = 10
H_MAX_LEVELS = [5, 10, 15]
SHELTER_FRACTION = 0.62

# Agent/building ratios to test — covers independence zone through breakpoint
AGENT_BUILDING_RATIOS = [2, 5, 8, 10, 15, 20, 25, 30, 35, 40, 50]
# Extended ratios for communities needing higher Pmax to confirm breakpoint
AGENT_BUILDING_RATIOS_EXTENDED = [60, 70, 80, 90, 100]

RESULTS_BASE = os.path.join(os.path.dirname(__file__), "results", "pmax_extension")

_shared_G = None
_shared_bn = None
_shared_sn = None
_shared_community = None


def _run_one(G, bn, sn, community, P_max, H_max, agent_seed):
    rng_h = np.random.default_rng(agent_seed)
    rng_hz = np.random.default_rng(HAZARD_SEED)
    rng_s = np.random.default_rng(agent_seed + 2000)

    humans = create_human_agents(G, bn, P_max, HUMAN_GROUPS, rng_h)
    hazards = create_hazard_agents(G, bn, H_max,
                                   HAZARD_TYPES, SIM_DURATION, rng_hz)

    t0 = time.time()
    sim = EvacuationSimulation(G, humans, hazards, sn, 0.10, rng_s)
    m = sim.run(verbose=False)
    elapsed = time.time() - t0

    m.update({
        "community": community, "P_max": P_max,
        "H_max": H_max, "panic_rate": 0.10,
        "seed": agent_seed, "hazard_seed": HAZARD_SEED,
        "elapsed_sec": round(elapsed, 1),
    })
    return m


def _worker(args):
    P_max, H_max, agent_seed = args
    return _run_one(_shared_G, _shared_bn, _shared_sn,
                    _shared_community, P_max, H_max, agent_seed)


def _aggregate(metrics_list, community, P_max, H_max):
    agg = {
        "community": community,
        "P_max": P_max, "H_max": H_max,
        "panic_rate": 0.10,
        "n_seeds": len(metrics_list),
        "hazard_seed": HAZARD_SEED,
    }
    for key in ["RI", "RS", "RC", "RL"]:
        vals = [m[key] for m in metrics_list]
        agg[key] = float(np.mean(vals))
        agg[f"{key}_std"] = float(np.std(vals))
    agg["elapsed_sec"] = sum(m["elapsed_sec"] for m in metrics_list)
    return agg


def run_community(community_key, n_workers):
    global _shared_G, _shared_bn, _shared_sn, _shared_community
    t0 = time.time()

    # Build network with 62% shelter fraction
    print(f"\n{'='*65}")
    print(f"  Building network: {community_key}")
    print(f"{'='*65}")
    _shared_G, _shared_bn, _shared_sn = build_network(community_key)
    n_buildings = len(_shared_bn)

    # Compute shelter count = 62% of buildings
    n_shelters = max(5, int(n_buildings * SHELTER_FRACTION))
    _shared_G, _shared_bn, _shared_sn = build_network(
        community_key, n_shelters=n_shelters)
    _shared_community = community_key

    print(f"  Buildings={n_buildings}, Shelters={len(_shared_sn)}, "
          f"Nodes={_shared_G.number_of_nodes()}")

    # Compute Pmax levels from agent/building ratios
    pmax_levels = sorted(set(
        int(math.ceil(r * n_buildings / 1000) * 1000)
        for r in AGENT_BUILDING_RATIOS
    ))
    print(f"  Pmax levels: {pmax_levels}")
    print(f"  (agent/building ratios: {AGENT_BUILDING_RATIOS})")

    # Build run args
    seeds = [BASE_SEED + i * 100 for i in range(N_SEEDS)]
    all_args = []
    for pm in pmax_levels:
        for hm in H_MAX_LEVELS:
            for s in seeds:
                all_args.append((pm, hm, s))

    total = len(all_args)
    print(f"  Total: {total} runs ({len(pmax_levels)} Pmax × "
          f"{len(H_MAX_LEVELS)} Hmax × {N_SEEDS} seeds)")

    # Run
    ctx = mp.get_context("fork")
    with ctx.Pool(n_workers) as pool:
        all_raw = pool.map(_worker, all_args)

    # Aggregate and save
    out_dir = os.path.join(RESULTS_BASE, community_key)
    os.makedirs(out_dir, exist_ok=True)

    idx = 0
    all_agg = []
    print(f"\n{'':>12}", end="")
    for hm in H_MAX_LEVELS:
        print(f"  Hmax={hm:>2}      ", end="")
    print()

    for pm in pmax_levels:
        print(f"  Pmax={pm:>5}", end="")
        for hm in H_MAX_LEVELS:
            batch = all_raw[idx:idx + N_SEEDS]
            idx += N_SEEDS
            agg = _aggregate(batch, community_key, pm, hm)
            all_agg.append(agg)

            out = os.path.join(out_dir, f"pmax{pm}_hmax{hm}.json")
            with open(out, "w") as f:
                json.dump({"aggregated": agg, "raw": batch}, f, indent=2)

            print(f"  {agg['RI']:>5.1%}±{agg['RI_std']:.1%}", end="")
        print()

    # Save combined
    combined = {
        "results": all_agg,
        "params": {
            "community": community_key,
            "n_buildings": n_buildings,
            "n_shelters": len(_shared_sn),
            "hazard_seed": HAZARD_SEED,
            "n_seeds": N_SEEDS,
            "P_max_levels": pmax_levels,
            "H_max_levels": H_MAX_LEVELS,
            "agent_building_ratios": AGENT_BUILDING_RATIOS,
            "panic_rate": 0.10,
        },
    }
    out = os.path.join(out_dir, "combined.json")
    with open(out, "w") as f:
        json.dump(combined, f, indent=2)

    elapsed = time.time() - t0
    print(f"\n  {community_key} DONE — {total} runs in "
          f"{elapsed:.0f}s ({elapsed/60:.1f} min)")
    print(f"  → {out}")
    return elapsed


def main():
    parser = argparse.ArgumentParser(
        description="Multi-community Pmax extension experiment")
    parser.add_argument("--community", type=str, default=None,
                        help="Single community (default: all except PSU-UP)")
    parser.add_argument("--extend", action="store_true",
                        help="Run extended high-Pmax ratios only (60-100)")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    if args.community:
        communities = [args.community]
    else:
        # All except PSU-UP (already done)
        communities = ["UVA-C", "VT-B", "RA-PA", "KOP-PA"]

    # Override ratios if --extend
    if args.extend:
        global AGENT_BUILDING_RATIOS
        AGENT_BUILDING_RATIOS = AGENT_BUILDING_RATIOS_EXTENDED

    t0_total = time.time()
    for comm in communities:
        run_community(comm, args.workers)

    total_elapsed = time.time() - t0_total
    print(f"\n{'='*65}")
    print(f"  ALL DONE — {len(communities)} communities in "
          f"{total_elapsed:.0f}s ({total_elapsed/60:.1f} min)")
    print(f"{'='*65}")


if __name__ == "__main__":
    main()
