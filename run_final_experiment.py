#!/usr/bin/env python3
"""
Final experiment: paper reproduction + extensions.

Hazard seed 1135 (best match to paper RI across all Hmax levels).
10 seeds per config, hazard fixed, agent behavior varies.

Phase 2a — RI vs Pmax × Hmax (εp=10%)
  Paper:     Pmax={2K, 5K, 8K},         Hmax={5, 10, 15}
  Extension: Pmax={2K, 5K, 8K, 20K, 50K}, Hmax={5, 10, 15, 20, 25, 30}

Phase 2b — RS/RC/RL vs εp (Pmax=2000, Hmax=5)
  Paper:     εp={10, 30, 50, 70, 90%}
  Extension: εp={10, 20, 30, 40, 50, 60, 70, 80, 90%}
"""
import json
import multiprocessing as mp
import os
import time
import numpy as np

from config import SIM_DURATION, HUMAN_GROUPS, HAZARD_TYPES
from network_model import build_network
from agents import create_human_agents, create_hazard_agents
from simulation import EvacuationSimulation
from visualization import (
    plot_network, plot_flow_snapshots, plot_time_series,
    plot_impacted_rate, plot_panic_performance,
)

# ── Experiment parameters ─────────────────────────────────────────────────
HAZARD_SEED = 1135
BASE_SEED = 42
N_SEEDS = 10
N_WORKERS = 8
N_SHELTERS = 600
COMMUNITY = "PSU-UP"

# Phase 2a: extended Pmax and Hmax
P_MAX_LEVELS = [2000, 5000, 8000, 20000, 50000]
H_MAX_LEVELS = [5, 10, 15, 20, 25, 30]

# Phase 2b: finer εp
PANIC_RATES = [0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90]

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

# ── Shared state (fork COW) ──────────────────────────────────────────────
_shared_G = None
_shared_bn = None
_shared_sn = None


def _worker(args):
    """One simulation run.  hazard_seed is fixed; agent seed varies."""
    community, P_max, H_max, panic_rate, agent_seed, hazard_seed = args
    G, bn, sn = _shared_G, _shared_bn, _shared_sn

    rng_h = np.random.default_rng(agent_seed)
    rng_hz = np.random.default_rng(hazard_seed)
    rng_s = np.random.default_rng(agent_seed + 2000)

    humans = create_human_agents(G, bn, P_max, HUMAN_GROUPS, rng_h)
    hazards = create_hazard_agents(G, bn, H_max,
                                    HAZARD_TYPES, SIM_DURATION, rng_hz)

    t0 = time.time()
    sim = EvacuationSimulation(G, humans, hazards, sn, panic_rate, rng_s)
    m = sim.run(verbose=False)
    elapsed = time.time() - t0

    m.update({
        "community": community, "P_max": P_max,
        "H_max": H_max, "panic_rate": panic_rate,
        "seed": agent_seed, "hazard_seed": hazard_seed,
        "elapsed_sec": round(elapsed, 1),
    })
    return m


def _aggregate(metrics_list, community, P_max, H_max, panic_rate):
    """mean ± std from per-seed results."""
    agg = {
        "community": community,
        "P_max": P_max, "H_max": H_max,
        "panic_rate": panic_rate,
        "n_seeds": len(metrics_list),
        "hazard_seed": HAZARD_SEED,
    }
    for key in ["RI", "RS", "RC", "RL"]:
        vals = [m[key] for m in metrics_list]
        agg[key] = float(np.mean(vals))
        agg[f"{key}_std"] = float(np.std(vals))
    return agg


def main():
    global _shared_G, _shared_bn, _shared_sn
    t0_total = time.time()

    print(f"Building network: {COMMUNITY} ...")
    _shared_G, _shared_bn, _shared_sn = build_network(
        COMMUNITY, n_shelters=N_SHELTERS)
    print(f"  Nodes={_shared_G.number_of_nodes()}  "
          f"Buildings={len(_shared_bn)}  Shelters={len(_shared_sn)}")

    # ── Prepare all run args ──────────────────────────────────────────
    seeds = [BASE_SEED + i * 100 for i in range(N_SEEDS)]

    ri_args = []
    for pm in P_MAX_LEVELS:
        for hm in H_MAX_LEVELS:
            for s in seeds:
                ri_args.append((COMMUNITY, pm, hm, 0.10, s, HAZARD_SEED))

    panic_args = []
    for ep in PANIC_RATES:
        for s in seeds:
            panic_args.append((COMMUNITY, 2000, 5, ep, s, HAZARD_SEED))

    all_args = ri_args + panic_args
    total = len(all_args)
    print(f"\n{'='*65}")
    print(f"  Final Experiment: {total} runs  "
          f"({N_SEEDS} seeds × {N_WORKERS} workers)")
    print(f"  Hazard seed: {HAZARD_SEED}  (fixed)")
    print(f"  Phase 2a: {len(P_MAX_LEVELS)} Pmax × {len(H_MAX_LEVELS)} Hmax "
          f"= {len(P_MAX_LEVELS)*len(H_MAX_LEVELS)} configs")
    print(f"  Phase 2b: {len(PANIC_RATES)} εp levels")
    print(f"{'='*65}\n")

    # ── Execute ───────────────────────────────────────────────────────
    ctx = mp.get_context("fork")
    with ctx.Pool(N_WORKERS) as pool:
        all_raw = pool.map(_worker, all_args)

    ri_raw = all_raw[:len(ri_args)]
    panic_raw = all_raw[len(ri_args):]

    # ── Phase 2a aggregation ─────────────────────────────────────────
    print("[Phase 2a] RI vs Pmax × Hmax (εp=10%)")
    print(f"{'':>12}", end="")
    for hm in H_MAX_LEVELS:
        print(f"  Hmax={hm:>2}", end="")
    print()

    ri_results = []
    idx = 0
    for pm in P_MAX_LEVELS:
        print(f"  Pmax={pm:>5}", end="")
        for hm in H_MAX_LEVELS:
            batch = ri_raw[idx:idx + N_SEEDS]
            idx += N_SEEDS
            agg = _aggregate(batch, COMMUNITY, pm, hm, 0.10)
            ri_results.append(agg)
            print(f"  {agg['RI']:>5.1%}±{agg['RI_std']:.1%}", end="")
        print()

    # ── Phase 2b aggregation ─────────────────────────────────────────
    print(f"\n[Phase 2b] RS/RC/RL vs εp (Pmax=2000, Hmax=5)")
    print(f"  {'εp':>4}  {'RS':>14}  {'RC':>14}  {'RL':>14}")
    panic_results = []
    idx = 0
    for ep in PANIC_RATES:
        batch = panic_raw[idx:idx + N_SEEDS]
        idx += N_SEEDS
        agg = _aggregate(batch, COMMUNITY, 2000, 5, ep)
        panic_results.append(agg)
        print(f"  {ep:>4.0%}  "
              f"{agg['RS']:>5.1%}±{agg['RS_std']:>4.1%}  "
              f"{agg['RC']:>5.1%}±{agg['RC_std']:>4.1%}  "
              f"{agg['RL']:>5.1%}±{agg['RL_std']:>4.1%}")

    # ── Visualization ────────────────────────────────────────────────
    plot_impacted_rate(ri_results, COMMUNITY)
    plot_panic_performance(panic_results, COMMUNITY)

    # One detailed run for flow snapshots
    from main import single_run
    m, hist, G, bn, sn = single_run(
        COMMUNITY, 2000, 5, 0.10, seed=BASE_SEED,
        hazard_seed=HAZARD_SEED, verbose=False)
    plot_flow_snapshots(G, hist, COMMUNITY, bn, sn)
    plot_network(G, bn, sn, COMMUNITY)
    plot_time_series(hist, COMMUNITY)

    # ── Save ─────────────────────────────────────────────────────────
    all_results = {"phase2a": ri_results, "phase2b": panic_results,
                   "params": {"hazard_seed": HAZARD_SEED,
                              "n_seeds": N_SEEDS,
                              "P_max_levels": P_MAX_LEVELS,
                              "H_max_levels": H_MAX_LEVELS,
                              "panic_rates": PANIC_RATES}}
    out = os.path.join(RESULTS_DIR, f"final_experiment_{COMMUNITY}.json")
    with open(out, "w") as f:
        json.dump(all_results, f, indent=2, default=str)

    elapsed = time.time() - t0_total
    print(f"\n{'='*65}")
    print(f"  DONE — {total} runs in {elapsed:.0f}s ({elapsed/60:.1f} min)")
    print(f"  Results → {out}")
    print(f"{'='*65}")


if __name__ == "__main__":
    main()
