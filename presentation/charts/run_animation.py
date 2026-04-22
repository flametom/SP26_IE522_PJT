#!/usr/bin/env python3
"""Generate all 4 presentation animations (E + C α/β/γ).

Usage:
  ANIMATION_STRIDE=2 python3 presentation/charts/run_animation.py [--scenario E|alpha|beta|gamma|all]
"""
import argparse
import os
import sys

# Ensure project root is on path
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from main import single_run
from visualization import render_animation_frames, render_sidebyside_frames

ASSETS = os.path.join(ROOT, "presentation", "assets")


def run_E():
    """PSU-UP baseline: Pmax=2K, Hmax=5, εp=10%, seed=42."""
    print("\n=== E: PSU-UP baseline (Pmax=2K, Hmax=5, εp=10%) ===")
    m, hist, G, bn, sn = single_run(
        "PSU-UP", 2000, 5, 0.10, seed=42, hazard_seed=1135, verbose=False)
    out = os.path.join(ASSETS, "frames_psuup")
    render_animation_frames(hist, G, out, "sim", bn, sn,
                             title="PSU-UP baseline")
    print(f"  RI={m['RI']:.1%}  frames → {out}")


def run_alpha():
    """Pmax = 2K vs 50K, εp=10%, Hmax=5 (same hazard seed)."""
    print("\n=== α: Pmax 2K vs 50K ===")
    _, hL, G, bn, sn = single_run(
        "PSU-UP", 2000, 5, 0.10, seed=42, hazard_seed=1135, verbose=False)
    _, hR, _, _, _ = single_run(
        "PSU-UP", 50000, 5, 0.10, seed=42, hazard_seed=1135, verbose=False)
    out = os.path.join(ASSETS, "frames_cmp_pmax")
    render_sidebyside_frames(hL, hR, G, out, "cmp",
                              "Pmax = 2,000", "Pmax = 50,000",
                              bn, sn,
                              caption="Same hazard scenario (seed=1135)")


def run_beta():
    """εp = 10% vs 90%, Pmax=2K, Hmax=5 (same hazard seed)."""
    print("\n=== β: εp 10% vs 90% ===")
    _, hL, G, bn, sn = single_run(
        "PSU-UP", 2000, 5, 0.10, seed=42, hazard_seed=1135, verbose=False)
    _, hR, _, _, _ = single_run(
        "PSU-UP", 2000, 5, 0.90, seed=42, hazard_seed=1135, verbose=False)
    out = os.path.join(ASSETS, "frames_cmp_panic")
    render_sidebyside_frames(hL, hR, G, out, "cmp",
                              "εp = 10%", "εp = 90%",
                              bn, sn,
                              caption="Same hazard scenario (seed=1135)")


def run_gamma():
    """Hmax = 5 vs 30, Pmax=2K, εp=10% (hazard configs differ by design)."""
    print("\n=== γ: Hmax 5 vs 30 ===")
    _, hL, G, bn, sn = single_run(
        "PSU-UP", 2000, 5, 0.10, seed=42, hazard_seed=1135, verbose=False)
    _, hR, _, _, _ = single_run(
        "PSU-UP", 2000, 30, 0.10, seed=42, hazard_seed=1135, verbose=False)
    out = os.path.join(ASSETS, "frames_cmp_hmax")
    render_sidebyside_frames(hL, hR, G, out, "cmp",
                              "Hmax = 5", "Hmax = 30",
                              bn, sn,
                              caption="Hazard count differs by design; "
                              "agent seed = 42 held constant")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario",
                    choices=["E", "alpha", "beta", "gamma", "all"],
                    default="all")
    args = ap.parse_args()

    if os.environ.get("ANIMATION_STRIDE") is None:
        print("WARNING: ANIMATION_STRIDE not set. Using default "
              "SNAPSHOT_TIMES (5 frames). For a proper animation, "
              "rerun with: ANIMATION_STRIDE=2 python3 ...")

    if args.scenario in ("E", "all"): run_E()
    if args.scenario in ("alpha", "all"): run_alpha()
    if args.scenario in ("beta", "all"): run_beta()
    if args.scenario in ("gamma", "all"): run_gamma()
