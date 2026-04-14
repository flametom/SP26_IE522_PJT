#!/usr/bin/env python3
"""
Extended Pmax experiment for HPC (SLURM array jobs).

Goal: Find the RI~Pmax independence breakpoint by filling the 20K–50K gap.

Pmax levels: [2K, 5K, 8K, 10K, 15K, 20K, 25K, 30K, 35K, 40K, 45K, 50K]
Hmax levels: [5, 10, 15]  (paper's original 3 levels — sufficient for breakpoint)
Seeds: 10 per config
Total: 12 Pmax × 3 Hmax = 36 configs → 360 runs

Usage:
  # ---------- HPC (SLURM array) ----------
  # Each array task runs one (Pmax, Hmax) config (10 seeds).
  # Submit:  sbatch run_pmax_extension.sbatch
  # Or run a single config manually:
  python run_pmax_extension.py --task-id 0          # Pmax=2K, Hmax=5
  python run_pmax_extension.py --task-id 11         # Pmax=50K, Hmax=5
  python run_pmax_extension.py --task-id 35         # Pmax=50K, Hmax=15

  # ---------- Local (all configs, parallel) ----------
  python run_pmax_extension.py --local --workers 8

  # ---------- Merge results after all tasks finish ----------
  python run_pmax_extension.py --merge
"""

import argparse
import json
import multiprocessing as mp
import os
import sys
import time
import numpy as np

from config import SIM_DURATION, HUMAN_GROUPS, HAZARD_TYPES
from network_model import build_network
from agents import create_human_agents, create_hazard_agents
from simulation import EvacuationSimulation

# ── Experiment parameters ─────────────────────────────────────────────────
HAZARD_SEED = 1135
BASE_SEED = 42
N_SEEDS = 10
N_SHELTERS = 600
COMMUNITY = "PSU-UP"

P_MAX_LEVELS = [2000, 5000, 8000, 10000, 15000, 20000,
                25000, 30000, 35000, 40000, 45000, 50000]
H_MAX_LEVELS = [5, 10, 15]

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results", "pmax_extension")


def _build_task_grid():
    """Return list of (Pmax, Hmax) tuples — one per SLURM array task."""
    grid = []
    for pm in P_MAX_LEVELS:
        for hm in H_MAX_LEVELS:
            grid.append((pm, hm))
    return grid


# ── Single run ────────────────────────────────────────────────────────────

def _run_one(G, bn, sn, P_max, H_max, agent_seed):
    """Execute one simulation run; return metrics dict."""
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
        "community": COMMUNITY, "P_max": P_max,
        "H_max": H_max, "panic_rate": 0.10,
        "seed": agent_seed, "hazard_seed": HAZARD_SEED,
        "elapsed_sec": round(elapsed, 1),
    })
    return m


def _aggregate(metrics_list, P_max, H_max):
    """mean ± std from per-seed results."""
    agg = {
        "community": COMMUNITY,
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


# ── HPC mode: one task = one (Pmax, Hmax) config ─────────────────────────

def run_single_task(task_id):
    """Run 10 seeds for one (Pmax, Hmax) config. Called by SLURM array."""
    grid = _build_task_grid()
    if task_id >= len(grid):
        print(f"[Error] task_id={task_id} out of range (max {len(grid)-1})")
        sys.exit(1)

    P_max, H_max = grid[task_id]
    print(f"[Task {task_id}] Pmax={P_max}, Hmax={H_max}, {N_SEEDS} seeds")

    os.makedirs(RESULTS_DIR, exist_ok=True)

    G, bn, sn = build_network(COMMUNITY, n_shelters=N_SHELTERS)
    print(f"  Network: nodes={G.number_of_nodes()}, "
          f"buildings={len(bn)}, shelters={len(sn)}")

    seeds = [BASE_SEED + i * 100 for i in range(N_SEEDS)]
    raw_metrics = []
    for i, s in enumerate(seeds):
        m = _run_one(G, bn, sn, P_max, H_max, s)
        raw_metrics.append(m)
        print(f"  seed {s}: RI={m['RI']:.3f}  RS={m['RS']:.3f}  "
              f"RC={m['RC']:.3f}  RL={m['RL']:.3f}  ({m['elapsed_sec']}s)")

    agg = _aggregate(raw_metrics, P_max, H_max)
    print(f"  [Agg] RI={agg['RI']:.1%}±{agg['RI_std']:.1%}  "
          f"RS={agg['RS']:.1%}±{agg['RS_std']:.1%}")

    result = {"aggregated": agg, "raw": raw_metrics}
    out = os.path.join(RESULTS_DIR,
                       f"pmax{P_max}_hmax{H_max}.json")
    with open(out, "w") as f:
        json.dump(result, f, indent=2)
    print(f"  Saved → {out}")


# ── Local mode: all configs with multiprocessing ─────────────────────────

_shared_G = None
_shared_bn = None
_shared_sn = None


def _worker(args):
    """Worker for local parallel mode."""
    P_max, H_max, agent_seed = args
    return _run_one(_shared_G, _shared_bn, _shared_sn,
                    P_max, H_max, agent_seed)


def run_local(n_workers):
    """Run all configs locally with multiprocessing."""
    global _shared_G, _shared_bn, _shared_sn
    t0 = time.time()

    os.makedirs(RESULTS_DIR, exist_ok=True)

    print(f"Building network: {COMMUNITY} ...")
    _shared_G, _shared_bn, _shared_sn = build_network(
        COMMUNITY, n_shelters=N_SHELTERS)

    seeds = [BASE_SEED + i * 100 for i in range(N_SEEDS)]
    all_args = []
    for pm in P_MAX_LEVELS:
        for hm in H_MAX_LEVELS:
            for s in seeds:
                all_args.append((pm, hm, s))

    total = len(all_args)
    print(f"\n{'='*65}")
    print(f"  Pmax Extension: {total} runs  "
          f"({len(P_MAX_LEVELS)} Pmax × {len(H_MAX_LEVELS)} Hmax × "
          f"{N_SEEDS} seeds)")
    print(f"  Workers: {n_workers}")
    print(f"{'='*65}\n")

    ctx = mp.get_context("fork")
    with ctx.Pool(n_workers) as pool:
        all_raw = pool.map(_worker, all_args)

    # Aggregate and save per-config
    idx = 0
    all_agg = []
    print(f"\n{'':>12}", end="")
    for hm in H_MAX_LEVELS:
        print(f"  Hmax={hm:>2}      ", end="")
    print()

    for pm in P_MAX_LEVELS:
        print(f"  Pmax={pm:>5}", end="")
        for hm in H_MAX_LEVELS:
            batch = all_raw[idx:idx + N_SEEDS]
            idx += N_SEEDS
            agg = _aggregate(batch, pm, hm)
            all_agg.append(agg)

            out = os.path.join(RESULTS_DIR, f"pmax{pm}_hmax{hm}.json")
            with open(out, "w") as f:
                json.dump({"aggregated": agg, "raw": batch}, f, indent=2)

            print(f"  {agg['RI']:>5.1%}±{agg['RI_std']:.1%}", end="")
        print()

    # Save combined result
    combined = {
        "results": all_agg,
        "params": {
            "hazard_seed": HAZARD_SEED,
            "n_seeds": N_SEEDS,
            "P_max_levels": P_MAX_LEVELS,
            "H_max_levels": H_MAX_LEVELS,
            "panic_rate": 0.10,
        },
    }
    out = os.path.join(RESULTS_DIR, "pmax_extension_combined.json")
    with open(out, "w") as f:
        json.dump(combined, f, indent=2)

    elapsed = time.time() - t0
    print(f"\n{'='*65}")
    print(f"  DONE — {total} runs in {elapsed:.0f}s ({elapsed/60:.1f} min)")
    print(f"  Combined → {out}")
    print(f"{'='*65}")


# ── Merge mode: combine per-task JSONs after SLURM finishes ──────────────

def merge_results():
    """Merge individual pmax*_hmax*.json files into combined result."""
    grid = _build_task_grid()
    all_agg = []
    missing = []

    for pm, hm in grid:
        path = os.path.join(RESULTS_DIR, f"pmax{pm}_hmax{hm}.json")
        if not os.path.exists(path):
            missing.append(f"pmax{pm}_hmax{hm}")
            continue
        with open(path) as f:
            data = json.load(f)
        all_agg.append(data["aggregated"])

    if missing:
        print(f"[Warning] Missing {len(missing)} configs: {missing}")

    combined = {
        "results": all_agg,
        "params": {
            "hazard_seed": HAZARD_SEED,
            "n_seeds": N_SEEDS,
            "P_max_levels": P_MAX_LEVELS,
            "H_max_levels": H_MAX_LEVELS,
            "panic_rate": 0.10,
        },
    }
    out = os.path.join(RESULTS_DIR, "pmax_extension_combined.json")
    with open(out, "w") as f:
        json.dump(combined, f, indent=2)

    # Print summary table
    print(f"\n{'':>12}", end="")
    for hm in H_MAX_LEVELS:
        print(f"  Hmax={hm:>2}      ", end="")
    print()

    agg_map = {(a["P_max"], a["H_max"]): a for a in all_agg}
    for pm in P_MAX_LEVELS:
        print(f"  Pmax={pm:>5}", end="")
        for hm in H_MAX_LEVELS:
            a = agg_map.get((pm, hm))
            if a:
                print(f"  {a['RI']:>5.1%}±{a['RI_std']:.1%}", end="")
            else:
                print(f"  {'---':>12}", end="")
        print()

    print(f"\n  Merged {len(all_agg)}/{len(grid)} configs → {out}")


# ── CLI ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Extended Pmax experiment (HPC / local)")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--task-id", type=int,
                      help="SLURM array task ID (0-35)")
    mode.add_argument("--local", action="store_true",
                      help="Run all configs locally with multiprocessing")
    mode.add_argument("--merge", action="store_true",
                      help="Merge per-task results into combined JSON")
    parser.add_argument("--workers", type=int, default=8,
                        help="Workers for --local mode (default: 8)")
    args = parser.parse_args()

    if args.task_id is not None:
        run_single_task(args.task_id)
    elif args.local:
        run_local(args.workers)
    elif args.merge:
        merge_results()


if __name__ == "__main__":
    main()
