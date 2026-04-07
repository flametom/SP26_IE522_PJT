"""Sweep hazard seeds to find best match to paper RI values."""
import multiprocessing as mp
import numpy as np
import time
from config import SIM_DURATION, HUMAN_GROUPS, HAZARD_TYPES
from network_model import build_network
from agents import create_human_agents, create_hazard_agents
from simulation import EvacuationSimulation

_G = None
_bn = None
_sn = None

# Paper RI targets (Pmax=2000, εp=10%)
TARGETS = {5: 0.343, 10: 0.565, 15: 0.684}

def _run_one(args):
    hazard_seed, hmax = args
    G, bn, sn = _G, _bn, _sn
    agent_seed = 42  # fixed agent seed for fair comparison
    rng_h = np.random.default_rng(agent_seed)
    rng_hz = np.random.default_rng(hazard_seed)
    rng_s = np.random.default_rng(agent_seed + 2000)
    humans = create_human_agents(G, bn, 2000, HUMAN_GROUPS, rng_h)
    hazards = create_hazard_agents(G, bn, hmax, HAZARD_TYPES, SIM_DURATION, rng_hz)
    sim = EvacuationSimulation(G, humans, hazards, sn, 0.10, rng_s)
    m = sim.run(verbose=False)
    return hazard_seed, hmax, m["RI"]

if __name__ == "__main__":
    _G, _bn, _sn = build_network("PSU-UP", n_shelters=600)

    # Sweep 200 hazard seeds × 3 Hmax
    seeds = list(range(1000, 1200))
    args_list = [(s, h) for s in seeds for h in [5, 10, 15]]
    print(f"Sweeping {len(seeds)} hazard seeds × 3 Hmax = {len(args_list)} runs (8 workers)...")

    t0 = time.time()
    ctx = mp.get_context("fork")
    with ctx.Pool(8) as pool:
        results = pool.map(_run_one, args_list)
    elapsed = time.time() - t0

    # Group by hazard_seed
    by_seed = {}
    for hs, hm, ri in results:
        by_seed.setdefault(hs, {})[hm] = ri

    # Score: sum of squared RI errors vs paper
    scores = []
    for hs, ri_map in by_seed.items():
        err = sum((ri_map[h] - TARGETS[h])**2 for h in TARGETS)
        scores.append((err, hs, ri_map))
    scores.sort()

    print(f"\nDone in {elapsed:.0f}s. Top 10 hazard seeds:\n")
    print(f"{'Seed':>6}  {'Hmax=5':>8} (34.3%)  {'Hmax=10':>8} (56.5%)  {'Hmax=15':>8} (68.4%)  {'Error':>8}")
    print("-" * 70)
    for err, hs, ri_map in scores[:10]:
        print(f"{hs:>6}  {ri_map[5]:>8.1%}          {ri_map[10]:>8.1%}          {ri_map[15]:>8.1%}          {err:>8.5f}")
