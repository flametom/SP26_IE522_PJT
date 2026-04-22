#!/usr/bin/env python3
"""Measure naïve (no batch SSSP) vs optimized single-run timing.
Outputs JSON with per-section timings for both modes."""
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import numpy as np
from network_model import build_network
from agents import create_human_agents, create_hazard_agents
from simulation import EvacuationSimulation
from config import HUMAN_GROUPS, HAZARD_TYPES, SIM_DURATION

OUT_DIR = os.path.join(ROOT, "results", "benchmark")
os.makedirs(OUT_DIR, exist_ok=True)

COMMUNITY = "PSU-UP"
PMAX = 2000
HMAX = 5
EPSILON = 0.10
SEED = 42
N_SHELTERS = 600


def run_one(use_batch_sssp):
    G, bn, sn = build_network(COMMUNITY, n_shelters=N_SHELTERS)
    rng_h = np.random.default_rng(SEED)
    rng_z = np.random.default_rng(1135)
    rng_s = np.random.default_rng(SEED + 2000)
    humans = create_human_agents(G, bn, PMAX, HUMAN_GROUPS, rng_h)
    hazards = create_hazard_agents(G, bn, HMAX, HAZARD_TYPES,
                                    SIM_DURATION, rng_z)

    sim = EvacuationSimulation(G, humans, hazards, sn, EPSILON, rng_s,
                                use_batch_sssp=use_batch_sssp)
    t0 = time.time()
    metrics = sim.run(verbose=False)
    wall = time.time() - t0

    return {
        "mode": "batch" if use_batch_sssp else "naive",
        "wall_sec": round(wall, 2),
        "timings": {k: round(v, 3) for k, v in sim.timings.items()},
        "metrics": {k: metrics[k] for k in ("RI", "RS", "RC", "RL")},
        "config": {"Pmax": PMAX, "Hmax": HMAX, "epsilon_p": EPSILON,
                   "seed": SEED, "community": COMMUNITY},
    }


if __name__ == "__main__":
    print("Running NAIVE (per-agent networkx A*)...")
    naive = run_one(use_batch_sssp=False)
    print(f"  wall={naive['wall_sec']}s  timings={naive['timings']}")
    with open(os.path.join(OUT_DIR, "naive_timings.json"), "w") as f:
        json.dump(naive, f, indent=2)

    print("\nRunning OPTIMIZED (scipy batch SSSP)...")
    opt = run_one(use_batch_sssp=True)
    print(f"  wall={opt['wall_sec']}s  timings={opt['timings']}")
    with open(os.path.join(OUT_DIR, "optimized_timings.json"), "w") as f:
        json.dump(opt, f, indent=2)

    speedup = naive["wall_sec"] / opt["wall_sec"]
    print(f"\nSpeedup (single-process): {speedup:.1f}x")
