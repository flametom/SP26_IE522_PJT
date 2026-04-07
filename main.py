#!/usr/bin/env python3
"""
Community Evacuation Simulation — Main Entry Point
===================================================
Reproduces the experiments from:
  Shi, Lee, Yang — "Multi-agent Modeling of Human Traffic Dynamics for
  Rapid Response to Public Emergency in Spatial Networks" (IEEE CASE 2024)

Usage:
  python main.py                                 # single run (defaults)
  python main.py --experiment full               # full factorial (PSU-UP)
  python main.py --experiment networks           # all 5 communities network verification
  python main.py --community PSU-UP --pmax 2000 --hmax 5 --panic 0.10
"""

import argparse
import json
import multiprocessing as mp
import os
import time
import numpy as np

from config import (
    SIM_DURATION, HUMAN_GROUPS, HAZARD_TYPES,
    PANIC_RATES, P_MAX_LEVELS, H_MAX_LEVELS,
    DEFAULT_COMMUNITY, COMMUNITIES,
)
from network_model import build_network
from agents import create_human_agents, create_hazard_agents
from simulation import EvacuationSimulation
from visualization import (
    plot_network, plot_flow_snapshots, plot_time_series,
    plot_impacted_rate, plot_panic_performance,
)

# Shelter count determined via sensitivity analysis (see reproduction_report Section 4.5).
# Paper's shelter list is unpublished; 600 best matches RS at εp=90%.
N_SHELTERS = 600

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

# ── Shared state for parallel workers (set once in parent, read via fork COW) ──
_shared_G = None
_shared_bn = None
_shared_sn = None


def single_run(community_key, P_max, H_max, panic_rate, seed=42,
               hazard_seed=None, verbose=True):
    """Execute one simulation run and return metrics + history."""
    # Hazard seed defaults to seed+1000 for backward compat (single runs).
    # For multi-seed experiments, caller passes a fixed hazard_seed so
    # the scenario stays constant and only agent behavior varies.
    rng_human = np.random.default_rng(seed)
    rng_hazard = np.random.default_rng(hazard_seed if hazard_seed is not None
                                        else seed + 1000)
    rng_sim = np.random.default_rng(seed + 2000)

    G, building_nodes, shelter_nodes = build_network(community_key,
                                                      n_shelters=N_SHELTERS)

    if verbose:
        print(f"\n{'='*60}")
        print(f" Run: {community_key}  Pmax={P_max}  Hmax={H_max}  εp={panic_rate:.0%}"
              f"  seed={seed}")
        print(f"{'='*60}")

    humans = create_human_agents(G, building_nodes, P_max, HUMAN_GROUPS, rng_human)
    hazards = create_hazard_agents(G, building_nodes, H_max,
                                    HAZARD_TYPES, SIM_DURATION, rng_hazard)

    t0 = time.time()
    sim = EvacuationSimulation(G, humans, hazards, shelter_nodes,
                                panic_rate, rng_sim)
    metrics = sim.run(verbose=verbose)
    elapsed = time.time() - t0

    metrics.update({
        "community": community_key,
        "H_max": H_max,
        "panic_rate": panic_rate,
        "seed": seed,
        "elapsed_sec": round(elapsed, 1),
    })

    if verbose:
        print(f"\n[Result] RI={metrics['RI']:.1%}  RS={metrics['RS']:.1%}  "
              f"RC={metrics['RC']:.1%}  RL={metrics['RL']:.1%}  ({elapsed:.1f}s)")

    return metrics, sim.history, G, building_nodes, shelter_nodes


def _worker_single_run(args):
    """Worker function for parallel execution.
    Uses shared network from parent process (fork copy-on-write).
    hazard_seed is fixed across seeds within a config (scenario is constant;
    only agent placement and behavior rolls vary)."""
    community_key, P_max, H_max, panic_rate, seed, hazard_seed = args
    G, bn, sn = _shared_G, _shared_bn, _shared_sn

    rng_human = np.random.default_rng(seed)
    rng_hazard = np.random.default_rng(hazard_seed)   # FIXED per config
    rng_sim = np.random.default_rng(seed + 2000)

    humans = create_human_agents(G, bn, P_max, HUMAN_GROUPS, rng_human)
    hazards = create_hazard_agents(G, bn, H_max,
                                    HAZARD_TYPES, SIM_DURATION, rng_hazard)

    t0 = time.time()
    sim = EvacuationSimulation(G, humans, hazards, sn, panic_rate, rng_sim)
    metrics = sim.run(verbose=False)
    elapsed = time.time() - t0

    metrics.update({
        "community": community_key,
        "H_max": H_max,
        "panic_rate": panic_rate,
        "seed": seed,
        "elapsed_sec": round(elapsed, 1),
    })
    return metrics


def _aggregate_metrics(all_metrics, community_key, P_max, H_max,
                       panic_rate, n_seeds):
    """Compute mean ± std from a list of per-seed metric dicts."""
    agg = {
        "community": community_key,
        "P_max": P_max, "H_max": H_max,
        "panic_rate": panic_rate,
        "n_seeds": n_seeds,
    }
    for key in ["RI", "RS", "RC", "RL"]:
        vals = [m[key] for m in all_metrics]
        agg[key] = float(np.mean(vals))
        agg[f"{key}_std"] = float(np.std(vals))
    agg["elapsed_sec"] = sum(m["elapsed_sec"] for m in all_metrics)
    return agg


def multi_seed_run(community_key, P_max, H_max, panic_rate,
                   n_seeds=10, base_seed=42):
    """Run simulation across multiple seeds (serial) and return aggregated metrics."""
    all_metrics = []
    for i in range(n_seeds):
        seed = base_seed + i * 100
        m, _, _, _, _ = single_run(community_key, P_max, H_max, panic_rate,
                                    seed=seed, verbose=False)
        all_metrics.append(m)

    agg = _aggregate_metrics(all_metrics, community_key, P_max, H_max,
                             panic_rate, n_seeds)

    print(f"  [{community_key}] Pmax={P_max} Hmax={H_max} εp={panic_rate:.0%} "
          f"({n_seeds} seeds): "
          f"RI={agg['RI']:.1%}±{agg['RI_std']:.1%}  "
          f"RS={agg['RS']:.1%}±{agg['RS_std']:.1%}  "
          f"RC={agg['RC']:.1%}±{agg['RC_std']:.1%}  "
          f"RL={agg['RL']:.1%}±{agg['RL_std']:.1%}")

    return agg, all_metrics


# ═══════════════════════════════════════════════════════════════════════════
#  Experiment modes
# ═══════════════════════════════════════════════════════════════════════════

def run_network_verification():
    """Phase 1 — Build all 5 community networks (Table V, Fig. 3, Fig. 4)."""
    for key in COMMUNITIES:
        m, hist, G, bn, sn = single_run(key, P_max=2000, H_max=5,
                                         panic_rate=0.10)
        plot_network(G, bn, sn, key)
        plot_flow_snapshots(G, hist, key, bn, sn)
        plot_time_series(hist, key)


def run_full_experiment(community_key, n_seeds=10, n_workers=8):
    """Phase 2 — Full factorial on one community (Fig. 5 & 6).
    All seed×config combinations run in parallel via fork pool."""
    global _shared_G, _shared_bn, _shared_sn
    t0 = time.time()

    # Build network once; shared with workers via fork COW
    _shared_G, _shared_bn, _shared_sn = build_network(
        community_key, n_shelters=N_SHELTERS)

    print(f"\n{'='*60}")
    print(f" Full Experiment: {community_key}  "
          f"({n_seeds} seeds × {n_workers} workers)")
    print(f"{'='*60}")

    # ── Prepare ALL run args ──────────────────────────────────────────
    # Hazard seed is FIXED within each config (scenario constant).
    # Only agent placement (seed) and behavior rolls (seed+2000) vary.
    base_seed = 42
    hazard_seed = base_seed + 1000   # = 1042, same for all seeds
    ri_args = []     # Phase 2a: RI vs Pmax × Hmax (εp = 10%)
    panic_args = []  # Phase 2b: RS/RC/RL vs εp (Pmax=2000, Hmax=5)

    for pm in P_MAX_LEVELS:
        for hm in H_MAX_LEVELS:
            for i in range(n_seeds):
                ri_args.append((community_key, pm, hm, 0.10,
                                base_seed + i * 100, hazard_seed))

    for ep in PANIC_RATES:
        for i in range(n_seeds):
            panic_args.append((community_key, 2000, 5, ep,
                               base_seed + i * 100, hazard_seed))

    all_args = ri_args + panic_args
    total_runs = len(all_args)
    print(f"\n[Parallel] Submitting {total_runs} runs to {n_workers} workers...")

    # ── Execute in parallel ──────────────────────────────────────────
    ctx = mp.get_context("fork")
    with ctx.Pool(n_workers) as pool:
        all_raw = pool.map(_worker_single_run, all_args)

    ri_raw = all_raw[:len(ri_args)]
    panic_raw = all_raw[len(ri_args):]

    # ── Aggregate Phase 2a ───────────────────────────────────────────
    print("\n[Phase 2a] RI vs Pmax × Hmax (εp = 10%)")
    ri_results = []
    idx = 0
    for pm in P_MAX_LEVELS:
        for hm in H_MAX_LEVELS:
            batch = ri_raw[idx:idx + n_seeds]
            idx += n_seeds
            agg = _aggregate_metrics(batch, community_key, pm, hm,
                                     0.10, n_seeds)
            ri_results.append(agg)
            print(f"  Pmax={pm} Hmax={hm}: "
                  f"RI={agg['RI']:.1%}±{agg['RI_std']:.1%}")
    plot_impacted_rate(ri_results, community_key)

    # ── Aggregate Phase 2b ───────────────────────────────────────────
    print("\n[Phase 2b] RS/RC/RL vs εp (Pmax=2000, Hmax=5)")
    panic_results = []
    idx = 0
    for ep in PANIC_RATES:
        batch = panic_raw[idx:idx + n_seeds]
        idx += n_seeds
        agg = _aggregate_metrics(batch, community_key, 2000, 5,
                                 ep, n_seeds)
        panic_results.append(agg)
        print(f"  εp={ep:.0%}: RS={agg['RS']:.1%}±{agg['RS_std']:.1%}  "
              f"RC={agg['RC']:.1%}±{agg['RC_std']:.1%}  "
              f"RL={agg['RL']:.1%}±{agg['RL_std']:.1%}")
    plot_panic_performance(panic_results, community_key)

    # ── Flow snapshot from one representative run ────────────────────
    m, hist, G, bn, sn = single_run(community_key, 2000, 5, 0.10,
                                     verbose=False)
    plot_flow_snapshots(G, hist, community_key, bn, sn)

    elapsed = time.time() - t0
    all_results = ri_results + panic_results
    out = os.path.join(RESULTS_DIR, f"experiment_{community_key}.json")
    with open(out, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\n[Experiment] {len(all_results)} configs × {n_seeds} seeds "
          f"= {total_runs} runs  ({elapsed:.0f}s total)")
    print(f"[Experiment] Results → {out}")


def main():
    parser = argparse.ArgumentParser(description="Community Evacuation Simulation")
    parser.add_argument("--community", default=DEFAULT_COMMUNITY,
                        choices=list(COMMUNITIES.keys()))
    parser.add_argument("--pmax", type=int, default=2000)
    parser.add_argument("--hmax", type=int, default=5)
    parser.add_argument("--panic", type=float, default=0.10)
    parser.add_argument("--experiment", choices=["full", "networks", "all"])
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--nseeds", type=int, default=10,
                        help="Number of seeds for multi-seed experiments")
    parser.add_argument("--workers", type=int, default=8,
                        help="Number of parallel workers (default: 8)")
    args = parser.parse_args()

    if args.experiment == "networks":
        run_network_verification()
    elif args.experiment == "full":
        run_full_experiment(args.community, n_seeds=args.nseeds,
                            n_workers=args.workers)
    elif args.experiment == "all":
        run_network_verification()
        run_full_experiment(args.community, n_seeds=args.nseeds,
                            n_workers=args.workers)
    else:
        m, hist, G, bn, sn = single_run(
            args.community, args.pmax, args.hmax, args.panic, args.seed)
        plot_network(G, bn, sn, args.community)
        plot_flow_snapshots(G, hist, args.community, bn, sn)
        plot_time_series(hist, args.community)
        out = os.path.join(RESULTS_DIR, f"run_{args.community}.json")
        with open(out, "w") as f:
            json.dump(m, f, indent=2, default=str)
        print(f"[Done] {out}")


if __name__ == "__main__":
    main()
