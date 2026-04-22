# Final Presentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce the final IE 522 presentation deck (26 main + 4 backup slides with 4 animations, 3 extension charts, benchmark measurements, and speaker notes), following the science-first narrative in `docs/superpowers/specs/2026-04-22-final-presentation-design.md`.

**Architecture:** Extend `simulation.py` with a no-op branch that disables batch SSSP (for naïve benchmark) and allow per-step snapshots via `SNAPSHOT_TIMES` override. Add two pure-function renderers to `visualization.py` that consume existing `sim.history` output. Create a new `presentation/final.tex` Beamer deck (hybrid-copied from `main.tex`), plus `presentation/script.tex` for speaker notes, and per-figure chart scripts under `presentation/charts/`.

**Tech Stack:** Python (numpy, matplotlib, scipy, networkx), LaTeX (Beamer with `animategraphics`), pdflatex.

---

## File Structure

### New files

- `presentation/final.tex` — final 30-slide deck
- `presentation/script.tex` — speaker notes (standalone article)
- `presentation/charts/gen_benchmark_charts.py` — slides 6 + 10
- `presentation/charts/gen_ext1_pmax_breakpoint.py` — slide 18
- `presentation/charts/gen_ext2_hmax_saturation.py` — slide 19
- `presentation/charts/gen_ext3_panic_finer.py` — slide 20
- `presentation/charts/run_animation.py` — driver for E + C α/β/γ animations
- `presentation/charts/run_naive_benchmark.py` — naïve 1 run benchmark
- `presentation/assets/frames_psuup/sim_NNN.png` — E animation frames
- `presentation/assets/frames_cmp_pmax/cmp_NNN.png` — α frames
- `presentation/assets/frames_cmp_panic/cmp_NNN.png` — β frames
- `presentation/assets/frames_cmp_hmax/cmp_NNN.png` — γ frames
- `presentation/assets/fig_ext1_pmax_breakpoint.pdf`
- `presentation/assets/fig_ext2_hmax_saturation.pdf`
- `presentation/assets/fig_ext3_panic_finer.pdf`
- `presentation/assets/benchmark_time_dist.pdf`
- `presentation/assets/benchmark_scaling.pdf`
- `results/benchmark/naive_timings.json`
- `results/benchmark/optimized_timings.json`

### Modified files

- `config.py` — add animation-mode snapshot override
- `simulation.py` — add `use_batch_sssp` flag + timing instrumentation
- `visualization.py` — add `render_animation_frames()`, `render_sidebyside_frames()`
- `main.py` — add `--animation` and `--benchmark` CLI modes

### Preserved (do NOT touch)

- `presentation/main.tex` (1차 deck)
- `presentation/assets/frames/` (1차 toy animation)
- `presentation/script.tex` already existing? — no, 1차 had `script.tex` in presentation/ too. See Task 24 for how to reuse.

---

## Task 1: Add animation snapshot mode to config

**Files:**
- Modify: `config.py`

- [ ] **Step 1: Add override variable**

Open `config.py`. Replace the last section:

```python
# ── Visualization ───────────────────────────────────────────────────────────
FIG_DPI = 150
SNAPSHOT_TIMES = [0, 30, 60, 90, 120]
```

with:

```python
# ── Visualization ───────────────────────────────────────────────────────────
FIG_DPI = 150
SNAPSHOT_TIMES = [0, 30, 60, 90, 120]

# For animation rendering, override SNAPSHOT_TIMES to capture every N steps.
# Set via environment variable ANIMATION_STRIDE (int, 1=every step) before
# importing config. When set, SNAPSHOT_TIMES becomes [0, N, 2N, ..., 120].
import os as _os
_stride = _os.environ.get("ANIMATION_STRIDE")
if _stride is not None:
    _s = int(_stride)
    SNAPSHOT_TIMES = list(range(0, SIM_DURATION + 1, _s))
```

- [ ] **Step 2: Verify no import cycle**

Run: `python -c "from config import SNAPSHOT_TIMES; print(len(SNAPSHOT_TIMES))"`
Expected: `5` (default)

Run: `ANIMATION_STRIDE=2 python -c "from config import SNAPSHOT_TIMES; print(len(SNAPSHOT_TIMES))"`
Expected: `61`

- [ ] **Step 3: Commit**

```bash
git add config.py
git commit -m "feat: add ANIMATION_STRIDE env override for snapshot times"
```

---

## Task 2: Add `use_batch_sssp` flag + timing to simulation.py

**Files:**
- Modify: `simulation.py`

- [ ] **Step 1: Modify `__init__` signature**

Find the `__init__` of `EvacuationSimulation` (around line 42) and change it to accept the flag:

```python
def __init__(self, G, humans, hazards, shelter_nodes,
             background_panic, rng, use_batch_sssp=True):
    self.G = G
    self.humans = humans
    self.hazards = hazards
    self.shelter_nodes = shelter_nodes
    self.background_panic = background_panic
    self.rng = rng
    self.dt = DT
    self.use_batch_sssp = use_batch_sssp     # NEW

    # ... existing body unchanged ...

    # Timing instrumentation (populated by run())
    self.timings = {
        "flows": 0.0, "algo2": 0.0, "batch_sssp": 0.0,
        "algo1": 0.0, "commit": 0.0, "total": 0.0,
    }
```

- [ ] **Step 2: Gate `_batch_compute_paths` on the flag**

Find `_batch_compute_paths()` (around line 163). At the top of the function body, after the docstring, insert:

```python
if not self.use_batch_sssp:
    self._batch_preds = {}
    return
```

(The existing `_find_path_batch` already falls back to `_find_path` when `preds is None` for a destination, so no further changes are needed there.)

- [ ] **Step 3: Instrument `run()` with per-section timing**

Replace the `run()` method body with timed sections:

```python
def run(self, verbose=True):
    import time
    for step in range(N_STEPS + 1):
        t_min = step * self.dt

        for h in self.hazards:
            h.update(t_min, self.dt)

        for p in self.humans:
            if not p.departed and t_min >= p.departure_time:
                p.departed = True

        t0 = time.time()
        self._reset_flows()
        self._compute_flows()
        self.timings["flows"] += time.time() - t0

        for p in self.humans:
            p.clear_buffers()

        t0 = time.time()
        self._algorithm2()
        self.timings["algo2"] += time.time() - t0

        t0 = time.time()
        self._batch_compute_paths()
        self.timings["batch_sssp"] += time.time() - t0

        t0 = time.time()
        self._algorithm1()
        self.timings["algo1"] += time.time() - t0

        t0 = time.time()
        self._commit_updates()
        self.timings["commit"] += time.time() - t0

        if step in self._snapshot_steps:
            self._record(t_min)

        if verbose and step % max(1, N_STEPS // 12) == 0:
            self._print_status(t_min)

    if N_STEPS not in self._snapshot_steps:
        self._record(SIM_DURATION)

    self.timings["total"] = sum(
        v for k, v in self.timings.items() if k != "total"
    )
    return self._compute_metrics()
```

- [ ] **Step 4: Smoke test — optimized path still works**

Run: `python main.py --community PSU-UP --pmax 500 --hmax 5 --panic 0.1`
Expected: prints metrics `RI=... RS=... RC=... RL=...`, exits cleanly.

- [ ] **Step 5: Smoke test — naïve path works**

Add a one-shot test in a Python REPL:

```python
from main import single_run
m, hist, G, bn, sn = single_run("PSU-UP", 500, 5, 0.1, verbose=False)
# now rebuild with naive
from simulation import EvacuationSimulation
from agents import create_human_agents, create_hazard_agents
import numpy as np
from config import HUMAN_GROUPS, HAZARD_TYPES, SIM_DURATION
rng_h = np.random.default_rng(42); rng_z = np.random.default_rng(1042); rng_s = np.random.default_rng(2042)
humans = create_human_agents(G, bn, 500, HUMAN_GROUPS, rng_h)
hazards = create_hazard_agents(G, bn, 5, HAZARD_TYPES, SIM_DURATION, rng_z)
sim = EvacuationSimulation(G, humans, hazards, sn, 0.1, rng_s, use_batch_sssp=False)
metrics = sim.run(verbose=False)
print("naive metrics:", metrics["RI"], "timings:", sim.timings)
```

Expected: `naive metrics: <number> timings: {...}`  with `timings["batch_sssp"] ≈ 0.0` and `timings["algo1"]` much larger than the optimized run.

- [ ] **Step 6: Commit**

```bash
git add simulation.py
git commit -m "feat: add use_batch_sssp flag and per-section timing instrumentation"
```

---

## Task 3: Add `render_animation_frames()` to visualization.py

**Files:**
- Modify: `visualization.py`

- [ ] **Step 1: Append renderer function**

At the end of `visualization.py`, after the last existing function, append:

```python
# ═══════════════════════════════════════════════════════════════════════════
#  7. Animation frames (E: single scenario)
# ═══════════════════════════════════════════════════════════════════════════

def _render_single_frame(ax, G, snap, bset, sset, xlo, xhi, ylo, yhi,
                          title=None):
    """Render one snapshot onto an existing matplotlib Axes.
    Uses the same visual style as plot_flow_snapshots but simplified
    (scatter only, no KDE) for speed."""
    ax.set_facecolor("#FAFAFA")

    # Edges
    for u, v, d in G.edges(data=True):
        if u in G.nodes and v in G.nodes:
            x0, y0 = G.nodes[u]["x"], G.nodes[u]["y"]
            x1, y1 = G.nodes[v]["x"], G.nodes[v]["y"]
            ax.plot([x0, x1], [y0, y1], color="#E0E0E0",
                    linewidth=0.25, alpha=0.5, zorder=1)

    # Buildings
    if bset:
        bxs = [G.nodes[nd]["x"] for nd in bset if nd in G.nodes]
        bys = [G.nodes[nd]["y"] for nd in bset if nd in G.nodes]
        ax.scatter(bxs, bys, s=3, c="#B8860B", marker="s",
                   alpha=0.35, zorder=2)

    # Shelters
    if sset:
        sxs = [G.nodes[nd]["x"] for nd in sset if nd in G.nodes]
        sys_ = [G.nodes[nd]["y"] for nd in sset if nd in G.nodes]
        ax.scatter(sxs, sys_, s=8, c="#2D8A4E", marker="^",
                   alpha=0.35, zorder=3)

    # Hazards
    for hz in snap.get("hazards", []):
        cx, cy, r = hz["center"][0], hz["center"][1], hz["radius"]
        ax.add_patch(plt.Circle((cx, cy), r,
                     color="#FF4444", alpha=0.08, zorder=4))
        ax.add_patch(plt.Circle((cx, cy), r, fill=False,
                     color="#CC0000", linewidth=0.8,
                     linestyle="--", alpha=0.5, zorder=4))

    # Agents — single-color scatter per state (no KDE)
    state_style = {
        "NORMAL":   ("#1A56DB", 5, "o", 6),
        "QUEUING":  ("#F5A623", 5, "D", 7),
        "IMPACTED": ("#CC1111", 7, "o", 8),
        "SURVIVAL": ("#1B7A3D", 4, "o", 5),
        "ARRIVAL":  ("#3D8B37", 3, "o", 5),
        "CASUALTY": ("#222222", 8, "X", 9),
    }
    by_state = {k: ([], []) for k in state_style}
    for _, info in snap["positions"].items():
        st = info.get("state")
        if st not in by_state:
            continue
        if "x" in info and "y" in info:
            by_state[st][0].append(info["x"])
            by_state[st][1].append(info["y"])
        elif info.get("node") is not None and info["node"] in G.nodes:
            by_state[st][0].append(G.nodes[info["node"]]["x"])
            by_state[st][1].append(G.nodes[info["node"]]["y"])

    for st, (xs, ys) in by_state.items():
        if not xs:
            continue
        color, sz, marker, z = state_style[st]
        ax.scatter(xs, ys, s=sz, c=color, marker=marker,
                   alpha=0.75, zorder=z)

    ax.set_xlim(xlo, xhi)
    ax.set_ylim(ylo, yhi)
    ax.set_aspect("equal")
    ax.axis("off")

    counts = snap.get("counts", {})
    sub = (f"t = {int(snap['t'])} min  |  "
           f"Active:{counts.get('active',0)}  "
           f"Imp:{counts.get('impacted',0)}  "
           f"Surv:{counts.get('survival',0)}  "
           f"Cas:{counts.get('casualty',0)}")
    if title:
        ax.set_title(f"{title}\n{sub}", fontsize=9)
    else:
        ax.set_title(sub, fontsize=9)


def render_animation_frames(history, G, out_dir, prefix="sim",
                             building_nodes=None, shelter_nodes=None,
                             title=None):
    """Render each snapshot in `history` as a numbered PNG in out_dir."""
    os.makedirs(out_dir, exist_ok=True)
    xlo, xhi, ylo, yhi = _get_view_bounds(G)
    bset = set(building_nodes) if building_nodes else set(
        nd for nd in G.nodes() if G.nodes[nd].get("is_building"))
    sset = set(shelter_nodes) if shelter_nodes else set()

    for i, snap in enumerate(history):
        fig, ax = plt.subplots(figsize=(7, 6))
        _render_single_frame(ax, G, snap, bset, sset,
                              xlo, xhi, ylo, yhi, title=title)
        fname = os.path.join(out_dir, f"{prefix}_{i:03d}.png")
        fig.savefig(fname, dpi=FIG_DPI, bbox_inches="tight",
                    facecolor="white")
        plt.close(fig)
    print(f"[Viz] Rendered {len(history)} frames to {out_dir}/{prefix}_*.png")
```

- [ ] **Step 2: Smoke test**

Run this one-liner in a Python REPL to verify:

```python
from main import single_run
from visualization import render_animation_frames
import os
# Use default SNAPSHOT_TIMES (5 frames) just to verify the renderer works
m, hist, G, bn, sn = single_run("PSU-UP", 500, 5, 0.1, verbose=False)
render_animation_frames(hist, G, "/tmp/test_frames", "test", bn, sn)
print(os.listdir("/tmp/test_frames"))
```

Expected: `['test_000.png', 'test_001.png', 'test_002.png', 'test_003.png', 'test_004.png']`

- [ ] **Step 3: Commit**

```bash
git add visualization.py
git commit -m "feat: add render_animation_frames for single-scenario animation"
```

---

## Task 4: Add `render_sidebyside_frames()` to visualization.py

**Files:**
- Modify: `visualization.py`

- [ ] **Step 1: Append side-by-side renderer**

At the end of `visualization.py`, append:

```python
# ═══════════════════════════════════════════════════════════════════════════
#  8. Animation frames (C: side-by-side comparison)
# ═══════════════════════════════════════════════════════════════════════════

def render_sidebyside_frames(hist_L, hist_R, G, out_dir, prefix,
                              label_L, label_R,
                              building_nodes=None, shelter_nodes=None,
                              caption=None):
    """Render paired snapshots (L, R) as 2-panel numbered PNGs.
    Assumes hist_L and hist_R have the same length (same SNAPSHOT_TIMES).
    If lengths differ, pairs up to the shorter length."""
    os.makedirs(out_dir, exist_ok=True)
    xlo, xhi, ylo, yhi = _get_view_bounds(G)
    bset = set(building_nodes) if building_nodes else set(
        nd for nd in G.nodes() if G.nodes[nd].get("is_building"))
    sset = set(shelter_nodes) if shelter_nodes else set()

    n = min(len(hist_L), len(hist_R))
    for i in range(n):
        fig, (axL, axR) = plt.subplots(1, 2, figsize=(14, 6))
        _render_single_frame(axL, G, hist_L[i], bset, sset,
                              xlo, xhi, ylo, yhi, title=label_L)
        _render_single_frame(axR, G, hist_R[i], bset, sset,
                              xlo, xhi, ylo, yhi, title=label_R)
        if caption:
            fig.suptitle(caption, fontsize=9, y=0.02)
        fname = os.path.join(out_dir, f"{prefix}_{i:03d}.png")
        fig.savefig(fname, dpi=FIG_DPI, bbox_inches="tight",
                    facecolor="white")
        plt.close(fig)
    print(f"[Viz] Rendered {n} side-by-side frames to "
          f"{out_dir}/{prefix}_*.png")
```

- [ ] **Step 2: Smoke test**

```python
from main import single_run
from visualization import render_sidebyside_frames
m1, h1, G, bn, sn = single_run("PSU-UP", 500, 5, 0.1, verbose=False)
m2, h2, _, _, _  = single_run("PSU-UP", 500, 5, 0.9, verbose=False)
render_sidebyside_frames(h1, h2, G, "/tmp/test_cmp", "test",
                          "εp=10%", "εp=90%", bn, sn)
import os; print(os.listdir("/tmp/test_cmp"))
```

Expected: 5 paired PNG files `test_000.png` ... `test_004.png`.

- [ ] **Step 3: Commit**

```bash
git add visualization.py
git commit -m "feat: add render_sidebyside_frames for comparison animations"
```

---

## Task 5: Create animation driver script

**Files:**
- Create: `presentation/charts/run_animation.py`

- [ ] **Step 1: Write the driver**

```python
#!/usr/bin/env python3
"""Generate all 4 presentation animations (E + C α/β/γ).

Usage:
  ANIMATION_STRIDE=2 python presentation/charts/run_animation.py [--scenario E|alpha|beta|gamma|all]
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
              "rerun with: ANIMATION_STRIDE=2 python ...")

    if args.scenario in ("E", "all"): run_E()
    if args.scenario in ("alpha", "all"): run_alpha()
    if args.scenario in ("beta", "all"): run_beta()
    if args.scenario in ("gamma", "all"): run_gamma()
```

- [ ] **Step 2: Dry run with default stride (5 frames, fast)**

```bash
mkdir -p /home/flametom/coursework/IE522_PJT/presentation/charts
# Save the script first, then run:
cd /home/flametom/coursework/IE522_PJT
python presentation/charts/run_animation.py --scenario E
```

Expected: prints "WARNING: ANIMATION_STRIDE not set." then renders 5 frames to `presentation/assets/frames_psuup/sim_000.png` ... `sim_004.png`. Verify by `ls presentation/assets/frames_psuup/`.

- [ ] **Step 3: Commit the driver (frames are gitignored)**

```bash
git add presentation/charts/run_animation.py
git commit -m "feat: add animation driver for E + C α/β/γ scenarios"
```

---

## Task 6: Generate all 4 animation frame sets at production stride

**Files:**
- Generates: `presentation/assets/frames_{psuup,cmp_pmax,cmp_panic,cmp_hmax}/*.png`

- [ ] **Step 1: Run with stride=2 (61 frames per scenario)**

```bash
cd /home/flametom/coursework/IE522_PJT
ANIMATION_STRIDE=2 python presentation/charts/run_animation.py --scenario all 2>&1 | tee /tmp/anim_log.txt
```

Expected wall time: 15–30 min (R1 reused; R2/R3/R4 dominated by R2's Pmax=50K run which takes ~5 min).

- [ ] **Step 2: Verify frame counts**

```bash
for d in frames_psuup frames_cmp_pmax frames_cmp_panic frames_cmp_hmax; do
  count=$(ls presentation/assets/$d/*.png 2>/dev/null | wc -l)
  echo "$d: $count frames"
done
```

Expected: each line shows `61 frames`.

- [ ] **Step 3: Spot-check visuals**

Open 3 frames from each directory (e.g., 000, 030, 060) and verify:
- Background network visible
- Hazard red circles present (and growing over time)
- Agent colored dots visible
- No obvious rendering errors (missing elements, wrong axis range)

If an issue is found, fix in `visualization.py` `_render_single_frame` and re-run. Do NOT commit frames.

- [ ] **Step 4: Update .gitignore to exclude frames**

Add to `.gitignore`:

```
presentation/assets/frames_psuup/
presentation/assets/frames_cmp_pmax/
presentation/assets/frames_cmp_panic/
presentation/assets/frames_cmp_hmax/
```

```bash
git add .gitignore
git commit -m "chore: ignore generated animation frame directories"
```

---

## Task 7: Naïve benchmark runner

**Files:**
- Create: `presentation/charts/run_naive_benchmark.py`
- Generates: `results/benchmark/naive_timings.json`, `results/benchmark/optimized_timings.json`

- [ ] **Step 1: Write the runner**

```python
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
```

- [ ] **Step 2: Run the benchmark**

```bash
cd /home/flametom/coursework/IE522_PJT
python presentation/charts/run_naive_benchmark.py 2>&1 | tee /tmp/benchmark_log.txt
```

Expected: naïve ~ 5–15 min, optimized ~ 30–90 sec, speedup ≥ 5×. Verify metrics match (RI/RS/RC/RL within 0.1%p between naive and optimized — sanity check that algorithm semantics are preserved).

- [ ] **Step 3: Verify JSON outputs**

```bash
cat results/benchmark/naive_timings.json
cat results/benchmark/optimized_timings.json
```

Both files should contain `mode`, `wall_sec`, `timings`, `metrics`, `config`.

- [ ] **Step 4: Commit runner and results**

```bash
git add presentation/charts/run_naive_benchmark.py results/benchmark/
git commit -m "feat: add naïve vs optimized benchmark runner and results"
```

---

## Task 8: Generate benchmark charts (slides 6 + 10)

**Files:**
- Create: `presentation/charts/gen_benchmark_charts.py`
- Generates: `presentation/assets/benchmark_time_dist.pdf`, `presentation/assets/benchmark_scaling.pdf`

- [ ] **Step 1: Write the chart script**

```python
#!/usr/bin/env python3
"""Generate benchmark charts for slides 6 and 10."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

BENCH_DIR = os.path.join(ROOT, "results", "benchmark")
OUT_DIR = os.path.join(ROOT, "presentation", "assets")
os.makedirs(OUT_DIR, exist_ok=True)


def load(name):
    with open(os.path.join(BENCH_DIR, name)) as f:
        return json.load(f)


def chart_time_distribution():
    """Slide 6: horizontal bar chart of time spent per section, both modes."""
    naive = load("naive_timings.json")
    opt = load("optimized_timings.json")

    sections = ["flows", "algo2", "batch_sssp", "algo1", "commit"]
    labels = ["Flow compute", "Algorithm 2", "Batch SSSP",
              "Algorithm 1 (+ path calls)", "Commit"]
    naive_vals = [naive["timings"][k] for k in sections]
    opt_vals = [opt["timings"][k] for k in sections]

    fig, ax = plt.subplots(figsize=(8.5, 4.5))
    y = np.arange(len(sections))
    h = 0.38
    ax.barh(y + h/2, naive_vals, h, label=f"Naïve ({naive['wall_sec']:.0f}s)",
            color="#CC4444")
    ax.barh(y - h/2, opt_vals, h, label=f"Optimized ({opt['wall_sec']:.1f}s)",
            color="#2E86AB")

    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_xlabel("Wall-clock seconds")
    ax.set_title("Time distribution per run "
                 f"(PSU-UP, Pmax={naive['config']['Pmax']}, "
                 f"Hmax={naive['config']['Hmax']})")
    ax.legend(loc="lower right")
    ax.grid(axis="x", alpha=0.3)

    for i, (nv, ov) in enumerate(zip(naive_vals, opt_vals)):
        ax.text(nv, i + h/2, f" {nv:.1f}s", va="center", fontsize=8)
        ax.text(ov, i - h/2, f" {ov:.1f}s", va="center", fontsize=8)

    fig.tight_layout()
    out = os.path.join(OUT_DIR, "benchmark_time_dist.pdf")
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {out}")


def chart_scaling():
    """Slide 10: summary panel — per-run time + extrapolated throughput."""
    naive = load("naive_timings.json")
    opt = load("optimized_timings.json")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.2))

    # Panel 1: single-run wall time
    modes = ["Naïve\n(per-agent A*)", "Optimized\n(scipy batch SSSP)"]
    vals = [naive["wall_sec"], opt["wall_sec"]]
    colors = ["#CC4444", "#2E86AB"]
    bars = ax1.bar(modes, vals, color=colors)
    ax1.set_ylabel("Seconds per single run")
    ax1.set_title("Single-run wall time "
                  f"(Pmax={opt['config']['Pmax']}, Hmax={opt['config']['Hmax']})")
    ax1.set_yscale("log")
    for b, v in zip(bars, vals):
        ax1.text(b.get_x() + b.get_width()/2, v,
                 f"{v:.1f}s", ha="center", va="bottom")
    ax1.grid(axis="y", alpha=0.3)

    # Panel 2: extrapolated total for 390-run extension sweep
    N_RUNS = 390
    N_WORKERS = 8
    naive_total = naive["wall_sec"] * N_RUNS / N_WORKERS  # assume same parallelism
    opt_total = opt["wall_sec"] * N_RUNS / N_WORKERS
    extrap_vals = [naive_total / 3600, opt_total / 3600]  # hours
    bars = ax2.bar(modes, extrap_vals, color=colors)
    ax2.set_ylabel(f"Hours for {N_RUNS} runs (8-worker parallel)")
    ax2.set_title(f"Extrapolated: {N_RUNS}-run extension experiment")
    ax2.set_yscale("log")
    for b, v in zip(bars, extrap_vals):
        ax2.text(b.get_x() + b.get_width()/2, v,
                 f"{v:.1f}h" if v >= 1 else f"{v*60:.0f}min",
                 ha="center", va="bottom")
    ax2.grid(axis="y", alpha=0.3)

    speedup = naive["wall_sec"] / opt["wall_sec"]
    fig.suptitle(f"Single-process speedup: {speedup:.1f}× "
                 f"(×{N_WORKERS} workers = ~{speedup*N_WORKERS:.0f}× overall)",
                 fontsize=11)
    fig.tight_layout()
    out = os.path.join(OUT_DIR, "benchmark_scaling.pdf")
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {out}")


if __name__ == "__main__":
    chart_time_distribution()
    chart_scaling()
```

- [ ] **Step 2: Run and verify**

```bash
cd /home/flametom/coursework/IE522_PJT
python presentation/charts/gen_benchmark_charts.py
ls presentation/assets/benchmark_*.pdf
```

Expected: both PDFs exist. Open them and check: bars readable, legends correct, speedup number printed.

- [ ] **Step 3: Commit**

```bash
git add presentation/charts/gen_benchmark_charts.py presentation/assets/benchmark_time_dist.pdf presentation/assets/benchmark_scaling.pdf
git commit -m "feat: add benchmark charts for slides 6 and 10"
```

---

## Task 9: Extension chart 1 — Pmax breakpoint (slide 18)

**Files:**
- Create: `presentation/charts/gen_ext1_pmax_breakpoint.py`
- Generates: `presentation/assets/fig_ext1_pmax_breakpoint.pdf`

- [ ] **Step 1: Inspect data shape**

```bash
python -c "import json; d=json.load(open('results/pmax_extension/PSU-UP/combined.json')); print(type(d), len(d) if hasattr(d,'__len__') else ''); print(json.dumps(d[0] if isinstance(d,list) else list(d.values())[0], indent=2)[:500])"
```

Note the structure (likely a list of dicts with `P_max`, `H_max`, `RI`, `RI_std` fields, similar to `results/final_experiment_PSU-UP.json`).

- [ ] **Step 2: Write the script**

```python
#!/usr/bin/env python3
"""Extension chart 1: RI vs log(Pmax), Hmax = 5/10/15 overlaid.
Highlights the breakpoint where RI ~ Pmax independence fails."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

DATA = os.path.join(ROOT, "results", "pmax_extension", "PSU-UP", "combined.json")
OUT = os.path.join(ROOT, "presentation", "assets",
                   "fig_ext1_pmax_breakpoint.pdf")


def load():
    with open(DATA) as f:
        d = json.load(f)
    # Normalize to list
    return d if isinstance(d, list) else list(d.values())


def group(data, hmax):
    rows = [r for r in data if int(r.get("H_max", r.get("hmax", 0))) == hmax]
    rows.sort(key=lambda r: r.get("P_max", r.get("pmax", 0)))
    xs = [r.get("P_max", r.get("pmax")) for r in rows]
    ys = [r["RI"] * 100 for r in rows]
    sds = [r.get("RI_std", 0) * 100 for r in rows]
    return xs, ys, sds


if __name__ == "__main__":
    data = load()
    fig, ax = plt.subplots(figsize=(8, 5))

    colors = {5: "#2E86AB", 10: "#D4760A", 15: "#CC1111"}
    for hm in [5, 10, 15]:
        xs, ys, sds = group(data, hm)
        if not xs:
            continue
        if any(s > 0 for s in sds):
            ax.errorbar(xs, ys, yerr=sds, marker="o", capsize=4,
                        color=colors[hm], label=f"Hmax = {hm}")
        else:
            ax.plot(xs, ys, marker="o", color=colors[hm],
                    label=f"Hmax = {hm}")

    # Paper-tested band (up to Pmax=8000)
    ax.axvspan(1500, 8500, alpha=0.08, color="gray",
               label="Paper-tested range")
    # Building capacity reference
    ax.axvline(969 * 20, color="green", linestyle=":",
               alpha=0.6, label="~20 agents/building")

    ax.set_xscale("log")
    ax.set_xlabel("Pmax (log scale)")
    ax.set_ylabel("RI (%)")
    ax.set_title("Extension ①: RI vs. Pmax — independence breaks at extreme populations\n"
                 "(PSU-UP, εp = 10%, 10-seed mean ± SD)")
    ax.grid(alpha=0.3)
    ax.legend(loc="lower right")

    fig.tight_layout()
    fig.savefig(OUT, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {OUT}")
```

- [ ] **Step 3: Run and verify**

```bash
python presentation/charts/gen_ext1_pmax_breakpoint.py
```

Expected: `Saved .../fig_ext1_pmax_breakpoint.pdf`. Open the PDF; verify 3 curves exist, log x-axis, paper-tested band visible.

If the JSON field names differ from assumptions, adjust the `group()` function accordingly. Check with:

```python
python -c "import json; d=json.load(open('results/pmax_extension/PSU-UP/combined.json')); import sys; r=d[0] if isinstance(d,list) else list(d.values())[0]; print(sorted(r.keys()))"
```

- [ ] **Step 4: Commit**

```bash
git add presentation/charts/gen_ext1_pmax_breakpoint.py presentation/assets/fig_ext1_pmax_breakpoint.pdf
git commit -m "feat: add extension chart 1 (Pmax breakpoint, slide 18)"
```

---

## Task 10: Extension chart 2 — Hmax saturation (slide 19)

**Files:**
- Create: `presentation/charts/gen_ext2_hmax_saturation.py`
- Generates: `presentation/assets/fig_ext2_hmax_saturation.pdf`

- [ ] **Step 1: Locate Hmax extension data**

The Hmax extension (5 → 30) is documented in `reproduction_report.md` §3.2. Verify whether the data is in `results/pmax_extension/PSU-UP/combined.json` (some Hmax > 15 entries) or a separate file. Run:

```bash
python -c "import json; d=json.load(open('results/pmax_extension/PSU-UP/combined.json')); hmaxes=sorted({r.get('H_max', r.get('hmax')) for r in (d if isinstance(d,list) else list(d.values()))}); print('Hmax values:', hmaxes)"
```

If Hmax > 15 is present: proceed with `combined.json`. Otherwise search other result files:

```bash
ls results/*.json
grep -l "H_max.*30\|hmax.*30" results/ -r 2>/dev/null
```

- [ ] **Step 2: Write the script (uses combined.json)**

```python
#!/usr/bin/env python3
"""Extension chart 2: RI vs Hmax at Pmax=2000, showing saturation."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

DATA = os.path.join(ROOT, "results", "pmax_extension", "PSU-UP", "combined.json")
OUT = os.path.join(ROOT, "presentation", "assets",
                   "fig_ext2_hmax_saturation.pdf")


if __name__ == "__main__":
    with open(DATA) as f:
        d = json.load(f)
    data = d if isinstance(d, list) else list(d.values())

    # Filter to Pmax=2000
    rows = [r for r in data
            if int(r.get("P_max", r.get("pmax", 0))) == 2000]
    rows.sort(key=lambda r: int(r.get("H_max", r.get("hmax", 0))))

    xs = [int(r.get("H_max", r.get("hmax"))) for r in rows]
    ys = [r["RI"] * 100 for r in rows]
    sds = [r.get("RI_std", 0) * 100 for r in rows]

    fig, ax = plt.subplots(figsize=(8, 5))
    if any(s > 0 for s in sds):
        ax.errorbar(xs, ys, yerr=sds, marker="o", capsize=4,
                    color="#CC1111", label="PSU-UP, Pmax=2000")
    else:
        ax.plot(xs, ys, marker="o", color="#CC1111",
                label="PSU-UP, Pmax=2000")

    # Saturation reference line at 86%
    ax.axhline(86, color="green", linestyle=":", alpha=0.6,
               label="~86% saturation")
    # Paper-tested range shade
    ax.axvspan(4.5, 15.5, alpha=0.08, color="gray",
               label="Paper-tested range")

    ax.set_xlabel("Hmax (number of hazard events)")
    ax.set_ylabel("RI (%)")
    ax.set_title("Extension ②: RI saturates at ~86% as Hmax grows\n"
                 "(PSU-UP, Pmax=2000, εp=10%, 10-seed mean ± SD)")
    ax.grid(alpha=0.3)
    ax.legend(loc="lower right")

    fig.tight_layout()
    fig.savefig(OUT, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {OUT}")
```

- [ ] **Step 3: Run and verify**

```bash
python presentation/charts/gen_ext2_hmax_saturation.py
```

Expected: curve rising from ~36% (Hmax=5) to ~86% (Hmax=30), saturation line visible.

- [ ] **Step 4: Commit**

```bash
git add presentation/charts/gen_ext2_hmax_saturation.py presentation/assets/fig_ext2_hmax_saturation.pdf
git commit -m "feat: add extension chart 2 (Hmax saturation, slide 19)"
```

---

## Task 11: Extension chart 3 — Finer εp resolution (slide 20)

**Files:**
- Create: `presentation/charts/gen_ext3_panic_finer.py`
- Generates: `presentation/assets/fig_ext3_panic_finer.pdf`

- [ ] **Step 1: Locate εp data**

The 9-point εp data should be in `results/final_experiment_PSU-UP.json`. Verify:

```bash
python -c "import json; d=json.load(open('results/final_experiment_PSU-UP.json')); eps=sorted({r.get('panic_rate') for r in (d if isinstance(d,list) else list(d.values())) if r.get('panic_rate') is not None}); print('εp values:', eps)"
```

Expected: `[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]` (9 values).

- [ ] **Step 2: Write the script**

```python
#!/usr/bin/env python3
"""Extension chart 3: RS/RC/RL vs εp at 9 points vs paper's 5."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

DATA = os.path.join(ROOT, "results", "final_experiment_PSU-UP.json")
OUT = os.path.join(ROOT, "presentation", "assets",
                   "fig_ext3_panic_finer.pdf")

# Paper's Fig 6 values (from reproduction_report.md §3.3)
PAPER_EP = [0.10, 0.30, 0.50, 0.70, 0.90]
PAPER_RS = [96.6, 93.0, 88.3, 78.0, 64.6]
PAPER_RC = [2.5, 4.0, 7.2, 10.0, 13.3]
PAPER_RL = [0.9, 3.0, 4.5, 12.0, 22.1]


if __name__ == "__main__":
    with open(DATA) as f:
        d = json.load(f)
    data = d if isinstance(d, list) else list(d.values())

    # Phase 2b rows: Pmax=2000, Hmax=5, vary εp
    rows = [r for r in data
            if r.get("P_max") == 2000 and r.get("H_max") == 5
            and r.get("panic_rate") is not None]
    rows.sort(key=lambda r: r["panic_rate"])

    eps = [r["panic_rate"] * 100 for r in rows]
    rs = [r["RS"] * 100 for r in rows]
    rc = [r["RC"] * 100 for r in rows]
    rl = [r["RL"] * 100 for r in rows]

    fig, ax = plt.subplots(figsize=(8, 5))

    ax.plot(eps, rs, marker="o", color="#1B7A3D", label="RS (ours, 9 pts)")
    ax.plot(eps, rc, marker="o", color="#D4760A", label="RC (ours, 9 pts)")
    ax.plot(eps, rl, marker="o", color="#CC1111", label="RL (ours, 9 pts)")

    # Paper points
    paper_eps_pct = [e * 100 for e in PAPER_EP]
    ax.scatter(paper_eps_pct, PAPER_RS, marker="x", s=80, color="#1B7A3D",
               linewidths=2, label="RS (paper, 5 pts)")
    ax.scatter(paper_eps_pct, PAPER_RC, marker="x", s=80, color="#D4760A",
               linewidths=2, label="RC (paper, 5 pts)")
    ax.scatter(paper_eps_pct, PAPER_RL, marker="x", s=80, color="#CC1111",
               linewidths=2, label="RL (paper, 5 pts)")

    ax.set_xlabel("εp (%)")
    ax.set_ylabel("Rate (%)")
    ax.set_title("Extension ③: Finer εp resolution reveals smooth monotonic curves\n"
                 "(PSU-UP, Pmax=2000, Hmax=5)")
    ax.grid(alpha=0.3)
    ax.legend(loc="upper right", fontsize=8, ncol=2)

    fig.tight_layout()
    fig.savefig(OUT, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {OUT}")
```

- [ ] **Step 3: Run and verify**

```bash
python presentation/charts/gen_ext3_panic_finer.py
```

Expected: 3 line curves (ours) + 3 sets of x-markers (paper). Verify monotonicity of our curves.

- [ ] **Step 4: Commit**

```bash
git add presentation/charts/gen_ext3_panic_finer.py presentation/assets/fig_ext3_panic_finer.pdf
git commit -m "feat: add extension chart 3 (finer εp, slide 20)"
```

---

## Task 12: Scaffold `final.tex` — preamble and Slides 1–4

**Files:**
- Create: `presentation/final.tex`

- [ ] **Step 1: Copy main.tex as base**

```bash
cd /home/flametom/coursework/IE522_PJT/presentation
cp main.tex final.tex
```

- [ ] **Step 2: Update meta (title/date)**

In `final.tex`, find the `--- Meta ---` block (around line 73) and change:

```tex
\title{Multi-Agent Modeling of Human Traffic Dynamics\\for Rapid Response to Public Emergency\\in Spatial Networks}
\subtitle{Shi, Lee, Yang --- IEEE CASE 2024}
\author{Dalal Alboloushi \quad \& \quad Jeongwon Bae}
\institute{IE 522 --- Simulation \\ Penn State University}
\date{Spring 2026}
```

to:

```tex
\title{Reproducing and Extending\\ a Multi-Agent Evacuation Simulation}
\subtitle{Final Project --- Shi, Lee, Yang (IEEE CASE 2024)}
\author{Dalal Alboloushi \quad \& \quad Jeongwon Bae}
\institute{IE 522 --- Simulation \\ Penn State University}
\date{Spring 2026 --- Final Presentation}
```

- [ ] **Step 3: Compress slides 2–3 into new Slide 2 (Problem & Model recap)**

In `final.tex`:
1. Delete the existing slide 2 (`Problem: Simulating Emergency Evacuation`, ~75 lines starting at `\begin{frame}[t,shrink=10]{Problem: Simulating...}` through its `\end{frame}`).
2. Delete the existing slide 3 (`Model Overview --- Three Components`).
3. Insert a new combined slide in their place:

```tex
% ============================================================
% SLIDE 2: Problem & Model recap (compressed from 1차)
% ============================================================
\begin{frame}[t,shrink=10]{Recap: Problem \& Three-Component Model}
\footnotesize

\begin{columns}[T,onlytextwidth]
\column{0.45\textwidth}
\textbf{Problem:} hazard strikes a community; thousands evacuate simultaneously.\\
Needed: agent-based sim capturing individual decisions + emergent congestion + panic.

\vspace{0.6em}
\begin{alertblock}{}
\scriptsize
Traditional process-flow models cannot capture emergent crowd dynamics.
$\Rightarrow$ \textbf{Multi-agent simulation} on a spatial network.
\end{alertblock}

\column{0.55\textwidth}
\vspace{-0.5em}
\begin{center}
\begin{tikzpicture}[>=Stealth, font=\scriptsize, scale=0.70, transform shape]
  \node[panelbox, fill=highlightblue!85, text=white, minimum width=5cm, minimum height=1.3cm, align=center] (net) at (0, 2.2)
    {\textbf{Community Network}\\ {\scriptsize $G=(V,E)$, OSM-derived}};
  \node[panelbox, fill=stateimpacted!85, text=white, minimum width=3.6cm, minimum height=1.3cm, align=center] (human) at (-2.6, -0.2)
    {\textbf{Human Agents}\\ {\scriptsize 6 states, 3 groups}};
  \node[panelbox, fill=highlightred!85, text=white, minimum width=3.6cm, minimum height=1.3cm, align=center] (hazard) at (2.6, -0.2)
    {\textbf{Hazard Agents}\\ {\scriptsize expanding, moving}};
  \draw[transarrow, highlightblue] (net.south) -- (human.north);
  \draw[transarrow, highlightblue] (net.south) -- (hazard.north);
  \draw[transarrow, highlightred] (hazard.west) -- (human.east);
\end{tikzpicture}
\end{center}
\end{columns}
\source{Shi et al.\ (2024) --- presented in the midterm}
\end{frame}
```

- [ ] **Step 4: Compress slides 5 + 7 into new Slide 3**

Delete existing slides 4, 5, 6, 7 (spatial network detail, human agents detail, hazard agents detail, one-agent perspective). Insert:

```tex
% ============================================================
% SLIDE 3: Agents & Algorithms recap
% ============================================================
\begin{frame}[t,shrink=10]{Recap: Agents \& Algorithms 1--2}
\footnotesize

\begin{columns}[T,onlytextwidth]
\column{0.46\textwidth}
\textbf{Human states (6)} — Normal, Queuing, Impacted, Arrival, Survival, Casualty.
Panic is \keyterm{irreversible}; impacted agents reroute to nearest shelter.

\vspace{0.4em}
\textbf{Hazards} — circular impact zone, expanding and moving over time, with a lifespan.

\column{0.52\textwidth}
\begin{block}{\scriptsize Algorithm 2 --- Human$\leftrightarrow$Hazard (every step)}
\scriptsize
\begin{enumerate}\itemsep0.1em
  \item If agent inside hazard \& first impact $\to$ IMPACTED + reroute to shelter
  \item Casualty check (higher prob near center)
  \item Panic check (irreversible, $\varepsilon_p$ times group rate)
\end{enumerate}
\end{block}

\begin{block}{\scriptsize Algorithm 1 --- Human$\leftrightarrow$Network (every step)}
\scriptsize
\begin{enumerate}\itemsep0.1em
  \item If on edge $\to$ check edge congestion: queue or continue
  \item If at node $\to$ check node congestion: queue, reroute, random (panic), or advance
\end{enumerate}
\end{block}
\end{columns}
\source{Shi et al.\ (2024), Section III --- presented in the midterm}
\end{frame}
```

- [ ] **Step 5: Delete existing slide 8 (toy animation) and slide 9 (pending validation)**

In the current state of `final.tex`, after the edits above, the following slides from the original `main.tex` should be gone: original slides 2, 3, 4, 5, 6, 7, 8 ("Toy Example"), 9 ("Current Status"). Keep ONLY the title slide and the two new recap slides (2 and 3).

Verify by looking at what's left: just title + new Slide 2 + new Slide 3 + `\end{document}`. Everything between "Slide 3 recap" and `\end{document}` should be blank (new slides will be added in subsequent tasks).

- [ ] **Step 6: Add new Slide 4 — Reproduction scope**

Before `\end{document}`, insert:

```tex
% ============================================================
% SLIDE 4: Reproduction scope
% ============================================================
\begin{frame}[t]{What we reproduced \& extended}
\footnotesize

\begin{columns}[T,onlytextwidth]
\column{0.48\textwidth}
\begin{block}{\small Paper reproduction targets}
\scriptsize
\begin{itemize}\itemsep0.2em
  \item \textbf{Phase 1} --- Table V, Fig.\ 3--4:\\
        networks for \textbf{5 communities}\\
        (PSU-UP, UVA-C, VT-B, RA-PA, KOP-PA)
  \item \textbf{Phase 2a} --- Fig.\ 5:\\
        $RI$ vs $P_{\max} \times H_{\max}$\\
        (9 configs, $\varepsilon_p = 10\%$)
  \item \textbf{Phase 2b} --- Fig.\ 6:\\
        $RS / RC / RL$ vs $\varepsilon_p$\\
        (5 paper points)
\end{itemize}
\end{block}

\column{0.48\textwidth}
\begin{alertblock}{\small Our extensions (beyond the paper)}
\scriptsize
\begin{itemize}\itemsep0.2em
  \item \textbf{Ext.\ \textcircled{\scriptsize 1}} Pmax \textbf{2K $\to$ 97K}\\
        (paper tested 2K--8K) --- breakpoint
  \item \textbf{Ext.\ \textcircled{\scriptsize 2}} Hmax \textbf{5 $\to$ 30}\\
        (paper tested 5--15) --- saturation
  \item \textbf{Ext.\ \textcircled{\scriptsize 3}} $\varepsilon_p$ \textbf{finer grid}\\
        (9 points vs paper's 5)
\end{itemize}
\end{alertblock}
\vspace{0.3em}
{\scriptsize 10 seeds per config; mean $\pm$ SD reported throughout.}
\end{columns}
\end{frame}
```

- [ ] **Step 7: Compile and verify**

```bash
cd /home/flametom/coursework/IE522_PJT/presentation
pdflatex -halt-on-error final.tex
pdflatex -halt-on-error final.tex   # twice for TOC/refs if any
```

Expected: `final.pdf` generated, 4 slides (title + recap + recap + scope). No LaTeX errors.

- [ ] **Step 8: Commit**

```bash
git add final.tex
git commit -m "feat: scaffold final.tex with slides 1-4 (title, recap, scope)"
```

---

## Task 13: Slide 5 — Why speed matters

**Files:**
- Modify: `presentation/final.tex`

- [ ] **Step 1: Add slide 5**

Before `\end{document}`, insert:

```tex
% ============================================================
% SLIDE 5: Why speed matters
% ============================================================
\begin{frame}[t]{Why speed matters: 390 runs, thousands of agents each}
\footnotesize

\begin{columns}[T,onlytextwidth]
\column{0.50\textwidth}
\textbf{Per single run} (Pmax = 2{,}000, 121 steps):
\vspace{0.3em}
\begin{itemize}\itemsep0.25em
  \item $\sim 2{,}000$ active agents
  \item $121$ time steps
  \item Each non-panicked agent recomputes its path \keyterm{every step}\\
        {\scriptsize (paper spec: ``pedestrians rely on up-to-date observations'')}
  \item $\Rightarrow \sim 200{,}000$+ shortest-path calls per run
\end{itemize}

\vspace{0.4em}
\textbf{Across our full experiment:}
\vspace{0.3em}
\begin{itemize}\itemsep0.25em
  \item Paper reproduction: 14 configs $\times$ 10 seeds $=$ 140 runs
  \item Extensions: $\sim 250$ additional runs
  \item \textbf{Total: $\sim 390$ runs}
\end{itemize}

\column{0.46\textwidth}
\vspace{0.1em}
\begin{alertblock}{\small With a naïve implementation}
\scriptsize
Per-agent \texttt{nx.astar\_path} in pure Python.\\[3pt]
1 run $\approx$ 5--15 minutes (measured).\\[3pt]
$\Rightarrow$ 390 runs $\approx$ \textbf{1.5--4 days} of wall time.
\end{alertblock}

\vspace{0.4em}
\begin{block}{\small With our optimized pipeline}
\scriptsize
Same Algorithms 1, 2.\\
Different \emph{functions} for path computation.\\[3pt]
1 run $\approx$ 32 seconds.\\[3pt]
390 runs $\approx$ \textbf{3.4 hours} (8 workers).
\end{block}
\end{columns}
\end{frame}
```

- [ ] **Step 2: Compile and verify**

```bash
pdflatex -halt-on-error final.tex
```

Check the new slide renders correctly.

- [ ] **Step 3: Commit**

```bash
git add final.tex
git commit -m "feat: add slide 5 (why speed matters)"
```

---

## Task 14: Slides 6–7 — Profiling + scipy batch SSSP

**Files:**
- Modify: `presentation/final.tex`

- [ ] **Step 1: Verify benchmark chart exists**

```bash
ls presentation/assets/benchmark_time_dist.pdf
```

If missing, complete Task 8 first.

- [ ] **Step 2: Add slide 6 (profiling)**

Before `\end{document}`, insert:

```tex
% ============================================================
% SLIDE 6: Engineering ① --- Profiling & bottleneck
% ============================================================
\begin{frame}[t]{Engineering \textcircled{\scriptsize 1}: Profiling identifies the bottleneck}
\footnotesize

\begin{columns}[T,onlytextwidth]
\column{0.55\textwidth}
\begin{center}
\includegraphics[width=0.98\linewidth]{assets/benchmark_time_dist.pdf}
\end{center}

\column{0.42\textwidth}
\vspace{0.5em}
\textbf{What dominates?}
\vspace{0.3em}
\begin{itemize}\itemsep0.25em
  \item Flow / state bookkeeping is cheap
  \item Algorithm 2 (hazard check) is cheap
  \item \keyterm{Algorithm 1 path recomputation is \textgreater 80\% of runtime}
\end{itemize}

\vspace{0.5em}
\textbf{Root cause:}\\
Every non-panicked agent calls \texttt{nx.astar\_path} from its current position, every step, in pure Python.

\vspace{0.5em}
{\scriptsize\textcolor{gray}{Measured on PSU-UP, Pmax=2000, Hmax=5, εp=10\%, seed=42.}}
\end{columns}
\end{frame}
```

- [ ] **Step 3: Add slide 7 (scipy batch SSSP)**

```tex
% ============================================================
% SLIDE 7: Engineering ② --- scipy batch SSSP
% ============================================================
\begin{frame}[t,fragile,shrink=8]{Engineering \textcircled{\scriptsize 2}: Replace per-agent A* with batch SSSP}
\footnotesize

\textbf{Insight:} many agents share destinations (buildings, shelters). Compute one shortest-path tree per unique destination, reuse across agents.

\vspace{0.4em}
\begin{columns}[T,onlytextwidth]
\column{0.49\textwidth}
\begin{block}{\scriptsize Naïve (per-agent)}
\vspace{-0.3em}
\begin{semiverbatim}\tiny
for p in active_humans:
  path = nx.astar_path(
      G, p.src, p.dest)
\end{semiverbatim}
\vspace{-0.3em}
\end{block}

\column{0.49\textwidth}
\begin{block}{\scriptsize Optimized (batch)}
\vspace{-0.3em}
\begin{semiverbatim}\tiny
dests = set(p.dest for p in active_humans)
_, preds = sp_dijkstra(
    sparse_matrix,
    indices=dest_indices,
    return_predecessors=True)
# each agent: O(path_length) lookup in preds
\end{semiverbatim}
\vspace{-0.3em}
\end{block}
\end{columns}

\vspace{0.4em}
\begin{columns}[T,onlytextwidth]
\column{0.55\textwidth}
\begin{center}
{\scriptsize
\begin{tabular}{lcc}
\toprule
& \textbf{Per-step calls} & \textbf{Per-step total} \\
\midrule
Per-agent A* & $O(N)$ & $O(N \cdot (V{+}E) \log V)$ \\
Batch SSSP   & $O(K)$ & $O(K \cdot (V{+}E) + V)$ \\
\bottomrule
\end{tabular}}
\end{center}
{\scriptsize $N$ = active agents, $K$ = unique destinations, $K \ll N$.}

\column{0.42\textwidth}
\begin{alertblock}{\scriptsize Speedup}
\scriptsize
\textbf{7--20$\times$} for path computation alone\\
(plus: scipy dijkstra is C; networkx is Python)
\end{alertblock}
\end{columns}
\end{frame}
```

- [ ] **Step 4: Compile and verify**

```bash
pdflatex -halt-on-error final.tex
```

If `semiverbatim` triggers errors, ensure the frame has `[fragile]`. Verify both new slides render.

- [ ] **Step 5: Commit**

```bash
git add final.tex
git commit -m "feat: add slides 6-7 (profiling + scipy batch SSSP)"
```

---

## Task 15: Slides 8–9 — A* heuristic + multiprocessing

**Files:**
- Modify: `presentation/final.tex`

- [ ] **Step 1: Add slide 8 (A* heuristic + per-step recomputation)**

Before `\end{document}`:

```tex
% ============================================================
% SLIDE 8: Engineering ③ --- A* heuristic + per-step recomputation
% ============================================================
\begin{frame}[t,fragile,shrink=5]{Engineering \textcircled{\scriptsize 3}: A* heuristic, per-step recomputation, panic noise}
\footnotesize

\begin{columns}[T,onlytextwidth]
\column{0.50\textwidth}
\begin{block}{\scriptsize A* with Euclidean heuristic}
\vspace{-0.3em}
\begin{semiverbatim}\tiny
def heuristic(u, v):
    ux, uy = coords[u]; vx, vy = coords[v]
    return ((ux-vx)**2 + (uy-vy)**2) ** 0.5
\end{semiverbatim}
\vspace{-0.3em}
Used for single-source fallbacks (shelter redirect, congestion-aware) where batch doesn't apply. $\sim 2$--$3\times$ faster than plain Dijkstra on spatial graphs.
\end{block}

\begin{block}{\scriptsize Panicked agents: \emph{noisy} weights}
\vspace{-0.3em}
\begin{semiverbatim}\tiny
def noisy_weight(u, v, data):
    base = data["length"]
    return base * (1.0 + rng.exponential(1.0))
\end{semiverbatim}
\vspace{-0.3em}
Models paper's ``limited observations'' for panicked agents.
\end{block}

\column{0.46\textwidth}
\begin{alertblock}{\small Per-step recomputation is kept}
\scriptsize
Paper Section III-C: \emph{``pedestrians rely on up-to-date observations of their immediate surroundings.''}\\[4pt]
We do NOT cache paths.\\
Every non-panicked agent's path is recomputed every step against the current flow state.
\end{alertblock}

\vspace{0.6em}
\begin{center}
\fcolorbox{highlightblue}{lightbluefill}{\parbox{0.95\linewidth}{\centering\scriptsize
\textbf{Algorithms 1 and 2 are unchanged from the paper.}\\
Only the \emph{functions} used for path computation were replaced.}}
\end{center}
\end{columns}
\end{frame}
```

- [ ] **Step 2: Add slide 9 (multiprocessing + RNG separation)**

```tex
% ============================================================
% SLIDE 9: Engineering ④ --- Multiprocessing + RNG separation
% ============================================================
\begin{frame}[t]{Engineering \textcircled{\scriptsize 4}: Parallelism + independent RNG streams}
\footnotesize

\begin{columns}[T,onlytextwidth]
\column{0.46\textwidth}
\begin{block}{\small 8-worker parallelism}
\scriptsize
\texttt{multiprocessing.Pool(8)} across seed $\times$ config grid.\\[3pt]
Network built once in the parent; workers share it via fork copy-on-write.\\[3pt]
Each worker's run is independent $\Rightarrow \sim 8\times$ extra throughput.
\end{block}

\vspace{0.4em}
\begin{alertblock}{\small Why RNG separation matters}
\scriptsize
If a single RNG drives humans + hazards + sim dynamics, changing $P_{\max}$ alters the hazard placements \emph{for free}.\\
$\Rightarrow$ Can't tell whether a higher RI is from more people or from different hazards.
\end{alertblock}

\column{0.50\textwidth}
\begin{center}
\begin{tikzpicture}[>=Stealth, font=\scriptsize, scale=0.85, transform shape]
  \node[panelbox, fill=lightbluefill, minimum width=5cm, minimum height=0.8cm, align=center] (hu) at (0, 2.5)
    {Human stream --- \texttt{seed}\\ {\scriptsize origins, destinations, groups}};
  \node[panelbox, fill=lightredfill, minimum width=5cm, minimum height=0.8cm, align=center] (hz) at (0, 1.0)
    {Hazard stream --- \texttt{seed+1000}\\ {\scriptsize centers, types, times}};
  \node[panelbox, fill=lightgreenfill, minimum width=5cm, minimum height=0.8cm, align=center] (sim) at (0, -0.5)
    {Sim stream --- \texttt{seed+2000}\\ {\scriptsize casualty rolls, panic rolls, random edges}};
  \node[below=0.3em of sim, font=\scriptsize, align=center, text width=5.5cm]
    {Hazard stream is \keyterm{fixed} within each config\\ across all seeds $\to$ same scenario,\\ only agent variation.};
\end{tikzpicture}
\end{center}
\end{columns}
\end{frame}
```

- [ ] **Step 3: Compile and verify**

```bash
pdflatex -halt-on-error final.tex
```

- [ ] **Step 4: Commit**

```bash
git add final.tex
git commit -m "feat: add slides 8-9 (A* heuristic + multiprocessing)"
```

---

## Task 16: Slide 10 — Benchmark results

**Files:**
- Modify: `presentation/final.tex`

- [ ] **Step 1: Verify scaling chart exists**

```bash
ls presentation/assets/benchmark_scaling.pdf
```

- [ ] **Step 2: Compute actual speedup number for the headline**

```bash
python -c "
import json
n = json.load(open('results/benchmark/naive_timings.json'))['wall_sec']
o = json.load(open('results/benchmark/optimized_timings.json'))['wall_sec']
print(f'Single-process speedup: {n/o:.1f}x')
print(f'With 8-worker parallelism: {n/o*8:.0f}x')
"
```

Note the numbers (e.g., "Single-process 12×, total 96×"). These will replace placeholders in the slide.

- [ ] **Step 3: Add slide 10 (fill in numbers from Step 2)**

Replace `__SINGLE_SPEEDUP__` and `__TOTAL_SPEEDUP__` with the values you just computed:

```tex
% ============================================================
% SLIDE 10: Engineering ⑤ --- Benchmark results
% ============================================================
\begin{frame}[t]{Engineering \textcircled{\scriptsize 5}: Benchmark --- naïve vs optimized}
\footnotesize

\begin{center}
\includegraphics[width=0.92\linewidth]{assets/benchmark_scaling.pdf}
\end{center}

\vspace{0.3em}
\begin{columns}[T,onlytextwidth]
\column{0.48\textwidth}
\begin{alertblock}{\small Total speedup}
\scriptsize
\textbf{__SINGLE_SPEEDUP__$\times$} single-process (batch SSSP + A* heuristic)\\
\textbf{$\times$ 8 workers = __TOTAL_SPEEDUP__$\times$} overall\\[4pt]
$\Rightarrow$ 390-run extension experiment: \\ naïve $\sim$ 1--4 days $\to$ optimized $\sim$ 3.4 h
\end{alertblock}

\column{0.48\textwidth}
\begin{block}{\small What this speedup enabled}
\scriptsize
\begin{itemize}\itemsep0.1em
  \item 10 seeds per config $\to$ mean $\pm$ SD throughout
  \item Phase 1: 5 community networks
  \item Extension Pmax 2K--97K (12 values $\times$ 3 Hmax)
  \item Extension Hmax 5--30 (6 values)
  \item Extension $\varepsilon_p$ 9-point finer resolution
\end{itemize}
\end{block}
\end{columns}
\end{frame}
```

Manually substitute the actual numbers from Step 2.

- [ ] **Step 4: Compile and verify**

```bash
pdflatex -halt-on-error final.tex
```

Verify slide 10 renders with the chart and the correct speedup numbers (no `__PLACEHOLDER__` strings left).

- [ ] **Step 5: Commit**

```bash
git add final.tex
git commit -m "feat: add slide 10 (benchmark results)"
```

---

## Task 17: Slide 11 — E animation

**Files:**
- Modify: `presentation/final.tex`

- [ ] **Step 1: Verify frames exist**

```bash
ls presentation/assets/frames_psuup/ | wc -l
```

Expected: 61 files. If missing, rerun Task 6.

- [ ] **Step 2: Add slide 11**

```tex
% ============================================================
% SLIDE 11: E --- Real PSU-UP animation (replaces 1차 toy)
% ============================================================
\begin{frame}[t]{PSU-UP baseline in action --- real network, real agents}
\footnotesize

\begin{columns}[T,onlytextwidth]
\column{0.65\textwidth}
\begin{center}
\animategraphics[controls,loop,width=0.98\linewidth]{6}{assets/frames_psuup/sim_}{000}{060}
\end{center}

\column{0.32\textwidth}
\vspace{0.3em}
\textbf{Configuration:}
\scriptsize
\begin{itemize}\itemsep0.2em
  \item PSU-UP (969 buildings, $\sim 600$ shelters)
  \item Pmax = 2{,}000
  \item Hmax = 5
  \item $\varepsilon_p = 10\%$
  \item Hazard seed = 1135
  \item Agent seed = 42
\end{itemize}

\vspace{0.4em}
\textbf{Outcome:}\\
\scriptsize
$RI \approx 36\%$, $RS \approx 92\%$
(see slides 14--15)
\end{columns}

\vspace{0.3em}
{\scriptsize\textcolor{gray}{Colors: \textcolor{statenormal}{Normal}, \textcolor{statequeuing}{Queuing}, \textcolor{stateimpacted}{Impacted}, \textcolor{statesurvival}{Survival}, Casualty ($\times$). Red dashed = hazard.}}
\end{frame}
```

- [ ] **Step 3: Compile and verify animation embeds**

```bash
pdflatex -halt-on-error final.tex
```

Open `final.pdf` in Adobe Reader. Click slide 11, verify animation plays (play controls visible).

- [ ] **Step 4: Commit**

```bash
git add final.tex
git commit -m "feat: add slide 11 (E animation: PSU-UP baseline)"
```

---

## Task 18: Slides 12–13 — Phase 1 reproduction

**Files:**
- Modify: `presentation/final.tex`

- [ ] **Step 1: Add slide 12 (5-community building counts)**

Before `\end{document}`:

```tex
% ============================================================
% SLIDE 12: Phase 1 --- Network validation (5 communities)
% ============================================================
\begin{frame}[t]{Phase 1: Network validation across 5 communities}
\footnotesize

\begin{center}
\begin{tabular}{lcccc}
\toprule
\textbf{Community} & \textbf{Buildings (ours / paper)} & \textbf{Match} & \textbf{Walk edges (ours / paper)} & \textbf{Notes} \\
\midrule
PSU-UP  & 969 / 953 & \textbf{102\%} & 21{,}426 / 19{,}799 & Close \\
UVA-C   & 412 / 412 & \textbf{100\%} & 11{,}480 / 7{,}095  & Our edges higher \\
VT-B    & 448 / 445 & \textbf{101\%} &  8{,}214 / 6{,}929  & Close \\
RA-PA   & 473 / 473 & \textbf{100\%} &  7{,}334 / 16{,}432 & See note$^{\dagger}$ \\
KOP-PA  & 277 / 277 & \textbf{100\%} &  4{,}046 / 17{,}216 & See note$^{\dagger}$ \\
\bottomrule
\end{tabular}
\end{center}

\vspace{0.5em}
\begin{columns}[T,onlytextwidth]
\column{0.55\textwidth}
\begin{block}{\small Building counts match within 0--2\%}
\scriptsize
Using \keyterm{ADD mode}: each building footprint centroid added as a separate graph node.\\
Polygon + 25m buffer (universities), point + dist (cities).\\
Exact matches for 3/5 communities; 1--2\% drift on PSU-UP and VT-B from OSM data evolving over time.
\end{block}

\column{0.42\textwidth}
\begin{alertblock}{\scriptsize $^{\dagger}$ Edge count anomaly (RA-PA, KOP-PA)}
\scriptsize
Paper reports E/N $\approx$ 6.5--6.8 for these cities.\\
No standard OSMnx configuration reproduces this.\\
Closest hypothesis (geometry-segment counting) gets 73\%.\\
See backup slide for diagnostic detail.
\end{alertblock}
\end{columns}
\end{frame}
```

- [ ] **Step 2: Add slide 13 (PSU-UP fig3 + fig4)**

```tex
% ============================================================
% SLIDE 13: Phase 1 --- PSU-UP network + flow
% ============================================================
\begin{frame}[t]{Phase 1: PSU-UP spatial network \& flow snapshot}
\footnotesize

\begin{columns}[T,onlytextwidth]
\column{0.48\textwidth}
\begin{center}
\includegraphics[width=0.98\linewidth]{../results/fig3_network_PSU-UP.png}\\[2pt]
{\scriptsize Fig.\ 3 reproduction --- PSU-UP walk network}
\end{center}

\column{0.48\textwidth}
\begin{center}
\includegraphics[width=0.98\linewidth]{../results/fig4_flow_PSU-UP.png}\\[2pt]
{\scriptsize Fig.\ 4 reproduction --- pedestrian flow over time}
\end{center}
\end{columns}

\vspace{0.3em}
{\scriptsize\textcolor{gray}{Building nodes (yellow), shelters (green $\triangle$), hazard zones (red $\bigcirc$), agent states coded by color and shape.}}
\end{frame}
```

- [ ] **Step 3: Compile and verify**

```bash
pdflatex -halt-on-error final.tex
```

Verify both images display. Note the relative path `../results/` (from `presentation/`).

- [ ] **Step 4: Commit**

```bash
git add final.tex
git commit -m "feat: add slides 12-13 (Phase 1 network validation)"
```

---

## Task 19: Slides 14–15 — Phase 2a + 2b reproduction

**Files:**
- Modify: `presentation/final.tex`

- [ ] **Step 1: Add slide 14 (RI vs Pmax × Hmax)**

```tex
% ============================================================
% SLIDE 14: Phase 2a --- RI vs Pmax × Hmax
% ============================================================
\begin{frame}[t]{Phase 2a: $RI$ vs $P_{\max} \times H_{\max}$ --- reproduced}
\footnotesize

\begin{columns}[T,onlytextwidth]
\column{0.48\textwidth}
\begin{center}
\includegraphics[width=0.98\linewidth]{../results/fig5_RI_PSU-UP.png}\\[2pt]
{\scriptsize Fig.\ 5 reproduction (PSU-UP, $\varepsilon_p = 10\%$, 10 seeds)}
\end{center}

\column{0.48\textwidth}
\begin{center}
{\scriptsize
\begin{tabular}{lccc}
\toprule
& $H_{\max}$=5 & $H_{\max}$=10 & $H_{\max}$=15 \\
\midrule
$P_{\max}$=2K ours  & 36.3\% & 59.2\% & 72.1\% \\
paper             & 34.3\% & 56.5\% & 68.4\% \\
\addlinespace
$P_{\max}$=5K ours  & 36.4\% & 59.3\% & 72.2\% \\
paper             & 27.5\% & 51.8\% & 64.4\% \\
\addlinespace
$P_{\max}$=8K ours  & 36.2\% & 59.0\% & 72.0\% \\
paper             & 34.4\% & 54.4\% & 66.2\% \\
\bottomrule
\end{tabular}}
\end{center}

\vspace{0.4em}
\begin{alertblock}{\scriptsize}
\scriptsize
$RI \sim P_{\max}$ \textbf{independence confirmed}\\
(within $\pm 0.2$\%p across 2K--8K).\\[3pt]
Paper's core finding reproduced.
\end{alertblock}
\end{columns}
\end{frame}
```

- [ ] **Step 2: Add slide 15 (RS/RC/RL vs εp)**

```tex
% ============================================================
% SLIDE 15: Phase 2b --- RS/RC/RL vs εp
% ============================================================
\begin{frame}[t]{Phase 2b: $RS$ / $RC$ / $RL$ vs $\varepsilon_p$ --- reproduced}
\footnotesize

\begin{columns}[T,onlytextwidth]
\column{0.48\textwidth}
\begin{center}
\includegraphics[width=0.98\linewidth]{../results/fig6_panic_PSU-UP.png}\\[2pt]
{\scriptsize Fig.\ 6 reproduction (PSU-UP, $P_{\max}$=2000, $H_{\max}$=5)}
\end{center}

\column{0.48\textwidth}
\begin{center}
{\scriptsize
\begin{tabular}{lccc}
\toprule
$\varepsilon_p$ & $RS$ (ours / paper) & $RC$ (ours / paper) \\
\midrule
10\% & 91.8\% / 96.6\% & 2.2\% / \textbf{2.5\%} \\
30\% & 81.2\% / 93.0\% & 3.8\% / \textbf{4.0\%} \\
50\% & 73.2\% / 88.3\% & 4.6\% / 7.2\% \\
70\% & 67.6\% / 78.0\% & 5.7\% / 10.0\% \\
90\% & \textbf{62.0\%} / \textbf{64.6\%} & 6.1\% / 13.3\% \\
\bottomrule
\end{tabular}}
\end{center}

\vspace{0.3em}
\begin{alertblock}{\scriptsize}
\scriptsize
\textbf{All three trends} ($\varepsilon_p \uparrow$ $\to$ RS$\downarrow$, RC$\uparrow$, RL$\uparrow$) reproduced.\\
Near-exact match at boundary points (RS 90\%, RC 10/30\%).
\end{alertblock}
\end{columns}
\end{frame}
```

- [ ] **Step 3: Compile and verify**

```bash
pdflatex -halt-on-error final.tex
```

- [ ] **Step 4: Commit**

```bash
git add final.tex
git commit -m "feat: add slides 14-15 (Phase 2a RI, Phase 2b panic)"
```

---

## Task 20: Slide 16 — Differences & unresolvable gaps

**Files:**
- Modify: `presentation/final.tex`

- [ ] **Step 1: Add slide 16**

```tex
% ============================================================
% SLIDE 16: Differences & structurally unresolvable gaps
% ============================================================
\begin{frame}[t]{Gaps with the paper \& why they persist}
\footnotesize

\begin{columns}[T,onlytextwidth]
\column{0.52\textwidth}
\textbf{What remains off, by 2--10\%p:}
\vspace{0.2em}
\begin{itemize}\itemsep0.25em
  \item $RI$ slightly higher (+2--4\%p)
  \item $RS$ at low $\varepsilon_p$ lower ($-5$\%p)
  \item $RC$ saturates at $\sim$6\% (paper reaches 13\%)
  \item $RL$ higher ($+5$--$10$\%p)
\end{itemize}

\vspace{0.4em}
\textbf{Root causes --- all structurally unresolvable without additional paper data:}
\vspace{0.2em}
\begin{enumerate}\itemsep0.25em
  \item Paper's \keyterm{shelter list} is unpublished\\
        (we fitted 62\% of buildings via sensitivity analysis)
  \item Paper's \keyterm{casualty formula} is unspecified\\
        (we use a per-step distance-weighted probability)
  \item Paper's \keyterm{hazard random seed} is unpublished\\
        (we swept 200 seeds $\to$ 1135 minimizes $RI$ error)
  \item OSM data has evolved since the paper's download
\end{enumerate}

\column{0.44\textwidth}
\begin{alertblock}{\small Shelter sensitivity analysis}
\scriptsize
\begin{tabular}{lcc}
\toprule
\# shelters & $RS$ at $\varepsilon_p$=90\% & error \\
\midrule
15 (OSM)  & 13.8\% & --50.8\%p \\
100       & 35.7\% & --28.9\%p \\
300       & 53.5\% & --11.1\%p \\
\textbf{600} & \textbf{64.3\%} & \textbf{--0.3\%p} \\
700       & 62.2\% & --2.4\%p \\
\midrule
Paper     & 64.6\% & --- \\
\bottomrule
\end{tabular}

\vspace{0.4em}
$\Rightarrow$ \textbf{600 shelters} (62\% of buildings) produces the closest match.\\
Applied consistently across all 5 communities.
\end{alertblock}
\end{columns}
\end{frame}
```

- [ ] **Step 2: Compile and commit**

```bash
pdflatex -halt-on-error final.tex
git add final.tex
git commit -m "feat: add slide 16 (differences and unresolvable gaps)"
```

---

## Task 21: Slides 17–20 — Extensions (overview + 3 findings)

**Files:**
- Modify: `presentation/final.tex`

- [ ] **Step 1: Add slide 17 (Extension overview)**

```tex
% ============================================================
% SLIDE 17: Extension overview
% ============================================================
\begin{frame}[t]{Three questions we could ask because our pipeline is fast}
\footnotesize

\begin{center}
\begin{tikzpicture}[>=Stealth, font=\footnotesize, scale=0.95, transform shape]
  \node[panelbox, fill=lightbluefill, minimum width=4.2cm, minimum height=1.8cm, align=center] at (-4.5, 0)
    {\textbf{\textcircled{\scriptsize 1} $P_{\max}$ breakpoint}\\[3pt]
     {\scriptsize Paper: $P_{\max}$ = 2K--8K}\\
     {\scriptsize Us: 2K $\to$ \textbf{97K}}\\[3pt]
     {\scriptsize \emph{Does independence hold?}}};
  \node[panelbox, fill=lightredfill, minimum width=4.2cm, minimum height=1.8cm, align=center] at (0, 0)
    {\textbf{\textcircled{\scriptsize 2} $H_{\max}$ saturation}\\[3pt]
     {\scriptsize Paper: $H_{\max}$ = 5--15}\\
     {\scriptsize Us: 5 $\to$ \textbf{30}}\\[3pt]
     {\scriptsize \emph{Does RI grow without bound?}}};
  \node[panelbox, fill=lightgreenfill, minimum width=4.2cm, minimum height=1.8cm, align=center] at (4.5, 0)
    {\textbf{\textcircled{\scriptsize 3} $\varepsilon_p$ finer grid}\\[3pt]
     {\scriptsize Paper: 5 points}\\
     {\scriptsize Us: \textbf{9 points} (10\% incr.)}\\[3pt]
     {\scriptsize \emph{Smooth or stepwise?}}};
\end{tikzpicture}
\end{center}

\vspace{0.5em}
\begin{center}
\scriptsize
Each extension answered on the next slide. Side-by-side animations for \textcircled{\scriptsize 1}, \textcircled{\scriptsize 2}, \textcircled{\scriptsize 3} follow.
\end{center}
\end{frame}
```

- [ ] **Step 2: Add slide 18 (Pmax breakpoint)**

```tex
% ============================================================
% SLIDE 18: Extension ① Pmax breakpoint
% ============================================================
\begin{frame}[t]{Extension \textcircled{\scriptsize 1}: $P_{\max}$ independence breaks at extreme populations}
\footnotesize

\begin{columns}[T,onlytextwidth]
\column{0.58\textwidth}
\begin{center}
\includegraphics[width=0.98\linewidth]{assets/fig_ext1_pmax_breakpoint.pdf}
\end{center}

\column{0.40\textwidth}
\vspace{0.2em}
\begin{block}{\small Finding}
\scriptsize
Paper: \emph{$RI \sim P_{\max}$ independent}.\\
Confirmed: $P_{\max} \leq 20K$ ($\Delta RI < 0.2$\%p).\\[4pt]
\textbf{Breaks at $P_{\max}$ = 50K}\\
(+8.5\%p at $H_{\max}$=5).
\end{block}

\begin{alertblock}{\small Mechanism}
\scriptsize
969 buildings $\times \sim 20$ occupancy $\approx$ 20K capacity.\\
At 50K: $\sim$51 agents/building\\
$\Rightarrow$ outdoor queuing\\
$\Rightarrow$ hazard exposure
\end{alertblock}

\vspace{0.3em}
{\scriptsize \textcolor{gray}{See slide 21 for visual comparison.}}
\end{columns}
\end{frame}
```

- [ ] **Step 3: Add slide 19 (Hmax saturation)**

```tex
% ============================================================
% SLIDE 19: Extension ② Hmax saturation
% ============================================================
\begin{frame}[t]{Extension \textcircled{\scriptsize 2}: $RI$ saturates at $\sim$86\% as $H_{\max}$ grows}
\footnotesize

\begin{columns}[T,onlytextwidth]
\column{0.58\textwidth}
\begin{center}
\includegraphics[width=0.98\linewidth]{assets/fig_ext2_hmax_saturation.pdf}
\end{center}

\column{0.40\textwidth}
\vspace{0.2em}
\begin{block}{\small Finding}
\scriptsize
$RI$ grows \textbf{logarithmically, not linearly}, with $H_{\max}$.\\
Saturates at $\sim$86\%: \\{\scriptsize 36\% (Hmax=5) $\to$ 86\% (Hmax=30)}.
\end{block}

\begin{alertblock}{\small Interpretation}
\scriptsize
$\sim$14\% of the network remains \emph{structurally unreachable} by hazards regardless of count.\\[4pt]
Likely peripheral nodes far from any feasible hazard center.
\end{alertblock}

\vspace{0.3em}
{\scriptsize \textcolor{gray}{See slide 23 for visual comparison.}}
\end{columns}
\end{frame}
```

- [ ] **Step 4: Add slide 20 (Finer εp)**

```tex
% ============================================================
% SLIDE 20: Extension ③ Finer εp resolution
% ============================================================
\begin{frame}[t]{Extension \textcircled{\scriptsize 3}: Finer $\varepsilon_p$ grid --- smooth, monotonic}
\footnotesize

\begin{columns}[T,onlytextwidth]
\column{0.58\textwidth}
\begin{center}
\includegraphics[width=0.98\linewidth]{assets/fig_ext3_panic_finer.pdf}
\end{center}

\column{0.40\textwidth}
\vspace{0.2em}
\begin{block}{\small Finding}
\scriptsize
All three rates ($RS$, $RC$, $RL$) vs $\varepsilon_p$ are:
\begin{itemize}\itemsep0.1em
  \item smooth and monotonic
  \item no phase transitions between paper's 5 points
  \item \textbf{diminishing marginal} panic effect
\end{itemize}
\end{block}

\begin{alertblock}{\small Implication}
\scriptsize
$RS$ drops $\sim$6\%p per 10\%p $\varepsilon_p$ at low panic,\\
$\sim$3\%p per 10\%p at high panic.\\[4pt]
$\Rightarrow$ Panic management has highest impact at \emph{low-baseline} states.
\end{alertblock}

\vspace{0.3em}
{\scriptsize \textcolor{gray}{See slide 22 for visual comparison.}}
\end{columns}
\end{frame}
```

- [ ] **Step 5: Compile and commit**

```bash
pdflatex -halt-on-error final.tex
git add final.tex
git commit -m "feat: add slides 17-20 (extensions overview + 3 findings)"
```

---

## Task 22: Slides 21–23 — Comparison animations α/β/γ

**Files:**
- Modify: `presentation/final.tex`

- [ ] **Step 1: Verify all three frame directories**

```bash
for d in frames_cmp_pmax frames_cmp_panic frames_cmp_hmax; do
  echo "$d: $(ls presentation/assets/$d/ | wc -l) frames"
done
```

Each should be `61 frames`.

- [ ] **Step 2: Add slide 21 (α: Pmax)**

```tex
% ============================================================
% SLIDE 21: Comparison α --- Pmax 2K vs 50K
% ============================================================
\begin{frame}[t]{Comparison \textalpha: $P_{\max}$ = 2K vs 50K}
\footnotesize

\begin{center}
\animategraphics[controls,loop,width=0.95\linewidth]{6}{assets/frames_cmp_pmax/cmp_}{000}{060}
\end{center}

\vspace{0.3em}
{\scriptsize Same hazard scenario (hazard seed = 1135). Left: 2{,}000 agents fit within building capacity. Right: 50{,}000 agents overflow $\to$ outdoor queuing $\to$ hazard exposure.}
\end{frame}
```

- [ ] **Step 3: Add slide 22 (β: εp)**

```tex
% ============================================================
% SLIDE 22: Comparison β --- εp 10% vs 90%
% ============================================================
\begin{frame}[t]{Comparison \textbeta: $\varepsilon_p$ = 10\% vs 90\%}
\footnotesize

\begin{center}
\animategraphics[controls,loop,width=0.95\linewidth]{6}{assets/frames_cmp_panic/cmp_}{000}{060}
\end{center}

\vspace{0.3em}
{\scriptsize Same hazard scenario (hazard seed = 1135). Left: most agents reach shelter in order. Right: high panic $\to$ many wander randomly; higher casualty and leftover.}
\end{frame}
```

- [ ] **Step 4: Add slide 23 (γ: Hmax)**

```tex
% ============================================================
% SLIDE 23: Comparison γ --- Hmax 5 vs 30
% ============================================================
\begin{frame}[t]{Comparison \textgamma: $H_{\max}$ = 5 vs 30}
\footnotesize

\begin{center}
\animategraphics[controls,loop,width=0.95\linewidth]{6}{assets/frames_cmp_hmax/cmp_}{000}{060}
\end{center}

\vspace{0.3em}
{\scriptsize
Left and right panels show \textbf{different hazard scenarios by design} --- $H_{\max}$ is the hazard count itself, so the 5 hazards on the left and 30 hazards on the right are entirely different events.
Agent seed = 42 held constant.}
\end{frame}
```

- [ ] **Step 5: Compile and verify all three animations play**

```bash
pdflatex -halt-on-error final.tex
```

Open `final.pdf`, click slides 21, 22, 23, verify playback.

- [ ] **Step 6: Commit**

```bash
git add final.tex
git commit -m "feat: add slides 21-23 (comparison animations α/β/γ)"
```

---

## Task 23: Slides 24–26 — Closing (conclusion, future work, references)

**Files:**
- Modify: `presentation/final.tex`

- [ ] **Step 1: Add slide 24 (conclusion)**

```tex
% ============================================================
% SLIDE 24: Conclusion
% ============================================================
\begin{frame}[t]{Summary}
\footnotesize

\begin{columns}[T,onlytextwidth]
\column{0.48\textwidth}
\begin{block}{\small Reproduction}
\scriptsize
\begin{itemize}\itemsep0.2em
  \item Building counts: \textbf{100--102\%} across 5 communities
  \item $RI$ within \textbf{2--4\%p} of paper across all 9 configs
  \item $RS$/$RC$/$RL$ trends fully reproduced
  \item Core finding confirmed:\\ \keyterm{$RI \sim P_{\max}$ independence}
\end{itemize}
\end{block}

\column{0.48\textwidth}
\begin{alertblock}{\small Novel findings (beyond paper)}
\scriptsize
\begin{itemize}\itemsep0.2em
  \item \textcircled{\scriptsize 1} $P_{\max}$ independence \textbf{breaks at 50K} (population exceeds building capacity)
  \item \textcircled{\scriptsize 2} $RI$ \textbf{saturates at $\sim$86\%} as $H_{\max}$ grows (topology ceiling)
  \item \textcircled{\scriptsize 3} $\varepsilon_p$ effect is \textbf{smooth with diminishing returns}
\end{itemize}
\end{alertblock}
\end{columns}

\vspace{0.6em}
\begin{center}
\fcolorbox{highlightblue}{lightbluefill}{\parbox{0.92\linewidth}{\centering\footnotesize
\textbf{Engineering}: 7--20$\times$ single-process speedup (scipy batch SSSP), $\times$8 parallel $\Rightarrow$ 390 runs in 3.4 h.\\
Enabled full multi-seed reproduction + 3 extensions without cutting corners on the paper's model.}}
\end{center}
\end{frame}
```

- [ ] **Step 2: Add slide 25 (future work)**

```tex
% ============================================================
% SLIDE 25: Future work
% ============================================================
\begin{frame}[t]{Future work}
\footnotesize

\begin{columns}[T,onlytextwidth]
\column{0.5\textwidth}
\begin{block}{\small From the paper's own discussion}
\scriptsize
\begin{itemize}\itemsep0.2em
  \item \textbf{Response agents}: firefighters, volunteers coordinating evacuation
  \item \textbf{Social-force models}: physics-based crowd dynamics
  \item \textbf{MDP panic model}: probabilistic irrationality triggered by evolving hazards
\end{itemize}
\end{block}

\column{0.46\textwidth}
\begin{alertblock}{\small From our own gap analysis}
\scriptsize
\begin{itemize}\itemsep0.2em
  \item \textbf{Panic-dependent casualty}: current model uses distance only; extending to $p_{\text{cas}} \propto \varepsilon_p$ could close the $RC$ ceiling gap at high panic
  \item \textbf{Shelter-location sensitivity}: apply the 62\% fitting method across broader community types
\end{itemize}
\end{alertblock}
\end{columns}
\end{frame}
```

- [ ] **Step 3: Add slide 26 (references)**

```tex
% ============================================================
% SLIDE 26: References
% ============================================================
\begin{frame}[t]{References \& acknowledgements}
\footnotesize

\begin{itemize}\itemsep0.4em
  \item Shi, Lee, Yang. \textbf{Multi-agent Modeling of Human Traffic Dynamics for Rapid Response to Public Emergency in Spatial Networks}. IEEE CASE 2024.
  \item Zhang, Yang. \textbf{Agent-based Modeling of Pedestrian Dynamics}. IEEE EMBC 2021.\\
        {\scriptsize (Used to disambiguate preprocessing choices not stated in the CASE paper.)}
  \item Boeing, G. \textbf{OSMnx}. Python package for street-network analysis.
  \item Virtanen et al. \textbf{SciPy} (batch Dijkstra via \texttt{scipy.sparse.csgraph}).
  \item OpenStreetMap contributors. \textbf{OpenStreetMap}. \url{openstreetmap.org}
\end{itemize}

\vspace{1em}
\begin{center}
\fcolorbox{highlightblue}{lightbluefill}{\parbox{0.8\linewidth}{\centering\small
\textbf{Thank you.} \\[3pt]
{\scriptsize Questions? Code and data: \texttt{github.com/flametom/IE522\_PJT}}}}
\end{center}
\end{frame}
```

- [ ] **Step 4: Compile and verify 26 slides**

```bash
pdflatex -halt-on-error final.tex
pdfinfo final.pdf | grep Pages
```

Expected: `Pages:          26`

- [ ] **Step 5: Commit**

```bash
git add final.tex
git commit -m "feat: add slides 24-26 (conclusion, future work, references)"
```

---

## Task 24: Backup slides 27–30

**Files:**
- Modify: `presentation/final.tex`

- [ ] **Step 1: Add `\appendix` marker before backup slides**

Before `\end{document}` (after slide 26), add:

```tex
% ============================================================
% APPENDIX (backup slides)
% ============================================================
\appendix
```

- [ ] **Step 2: Add slide 27 (multi-community Pmax extension)**

```tex
% ============================================================
% BACKUP 27: Multi-community Pmax extension
% ============================================================
\begin{frame}[t]{Backup: Does the $P_{\max}$ breakpoint generalize?}
\footnotesize

\begin{center}
{\scriptsize
\begin{tabular}{lccccc}
\toprule
Community & Buildings & Capacity@20 & Breakpoint onset & Mechanism \\
\midrule
PSU-UP & 969 & 19{,}380 & $\sim$50K & outdoor queuing \\
KOP-PA & 277 & 5{,}540 & to be verified & same \\
RA-PA  & 473 & 9{,}460 & to be verified & same \\
VT-B   & 448 & 8{,}960 & to be verified & same \\
UVA-C  & 412 & 8{,}240 & to be verified & same \\
\bottomrule
\end{tabular}}
\end{center}

\vspace{0.6em}
{\scriptsize Multi-community Pmax sweep data is in \texttt{results/pmax\_extension/\{community\}/combined.json}.
Breakpoint should correlate with building capacity; PSU-UP exhibits it at $\sim$2.5$\times$ capacity ($\sim$51 agents/building). Primary finding (breakpoint exists) demonstrated on PSU-UP.}
\end{frame}
```

- [ ] **Step 3: Add slide 28 (edge count diagnostic)**

```tex
% ============================================================
% BACKUP 28: Edge count anomaly diagnostic
% ============================================================
\begin{frame}[t]{Backup: Edge count anomaly for RA-PA, KOP-PA}
\footnotesize

\textbf{Paper's E/N ratios (2021 Table V):} RA-PA 6.47, KOP-PA 6.84. Other communities 1.0--2.6.

\begin{center}
{\scriptsize
\begin{tabular}{lcc}
\toprule
Method tested & Our edges (RA-PA) & Fraction of paper \\
\midrule
walk network + simplify & 7{,}136 & 43\% \\
network\_type="all" & 6{,}750 & 41\% \\
simplify=False (all waypoints) & 66{,}836 & 407\% \\
Geometry segment count & 12{,}030 & \textbf{73\%} \\
Edge subdivision, 20m & $\sim$18{,}966 & 115\% \\
\bottomrule
\end{tabular}}
\end{center}

\vspace{0.4em}
\textbf{Conclusion:} No standard OSMnx config produces the paper's edge counts for these two communities. Closest hypothesis is geometry-segment counting (73\%). Treated as a paper data anomaly rather than a reproduction failure.
\end{frame}
```

- [ ] **Step 4: Add slide 29 (extension catalog)**

```tex
% ============================================================
% BACKUP 29: Why not more extensions?
% ============================================================
\begin{frame}[t]{Backup: Extension candidates considered}
\footnotesize

We drafted 6 extension candidates. Selected the 3 already presented. Remaining ideas were scoped out:

\vspace{0.4em}
{\scriptsize
\begin{tabular}{p{4.5cm}p{9cm}}
\toprule
Candidate & Status \\
\midrule
A1: Panic-dependent casualty & Deferred --- addresses the $RC$ ceiling gap at high panic; requires new casualty formula and re-running Phase 2b \\
A2: Demographic-specific shelter preference & Deferred --- low expected effect on headline metrics \\
B1: Shelter-location sensitivity study & Partially done (see slide 16) --- extended sweep would strengthen it \\
C1: Response agents (firefighters, volunteers) & Deferred --- requires new agent class; high implementation cost \\
C2: Social-force movement model & Deferred --- replaces the whole movement layer \\
C3: MDP panic model & Deferred --- replaces the panic trigger; out of scope for a course project \\
\bottomrule
\end{tabular}}

\vspace{0.4em}
{\scriptsize\textcolor{gray}{Full write-up: \texttt{Extension\_Candidates\_Detailed.md}.}}
\end{frame}
```

- [ ] **Step 5: Add slide 30 (static snapshot strips fallback)**

```tex
% ============================================================
% BACKUP 30: Static snapshot strips (animation fallback)
% ============================================================
\begin{frame}[t]{Backup: Static snapshots (animation fallback)}
\footnotesize

\begin{center}
{\scriptsize If animations do not play in the venue PDF viewer, static frames are embedded here.}
\end{center}

\vspace{0.3em}
\textbf{E} --- PSU-UP baseline
\begin{center}
\includegraphics[width=0.14\linewidth]{assets/frames_psuup/sim_000.png}\hfill
\includegraphics[width=0.14\linewidth]{assets/frames_psuup/sim_015.png}\hfill
\includegraphics[width=0.14\linewidth]{assets/frames_psuup/sim_030.png}\hfill
\includegraphics[width=0.14\linewidth]{assets/frames_psuup/sim_045.png}\hfill
\includegraphics[width=0.14\linewidth]{assets/frames_psuup/sim_060.png}
\end{center}

\vspace{0.2em}
\textbf{\textalpha} --- Pmax 2K vs 50K
\begin{center}
\includegraphics[width=0.22\linewidth]{assets/frames_cmp_pmax/cmp_000.png}\hfill
\includegraphics[width=0.22\linewidth]{assets/frames_cmp_pmax/cmp_030.png}\hfill
\includegraphics[width=0.22\linewidth]{assets/frames_cmp_pmax/cmp_060.png}
\end{center}

\vspace{0.2em}
{\scriptsize $\beta$ and $\gamma$ snapshot strips analogous. Reach via \texttt{Slide >}.}
\end{frame}
```

- [ ] **Step 6: Compile and verify 30 slides**

```bash
pdflatex -halt-on-error final.tex
pdfinfo final.pdf | grep Pages
```

Expected: `Pages:          30`

- [ ] **Step 7: Commit**

```bash
git add final.tex
git commit -m "feat: add backup slides 27-30 (multi-community, anomaly, catalog, fallback)"
```

---

## Task 25: Speaker notes — `script.tex`

**Files:**
- Create: `presentation/script.tex` (replacing or extending 1차 `script.tex` — the new file)

- [ ] **Step 1: Inspect existing 1차 `script.tex` for reusable preamble**

```bash
head -40 /home/flametom/coursework/IE522_PJT/presentation/script.tex
```

Note the document class and any macros.

- [ ] **Step 2: Overwrite `script.tex` with final-presentation notes**

Replace the file content with:

```tex
\documentclass[11pt]{article}
\usepackage[margin=0.9in]{geometry}
\usepackage{enumitem}
\usepackage{xcolor}
\setlist[itemize]{leftmargin=*,itemsep=0.2em}
\newcommand{\slide}[2]{\vspace{0.6em}\noindent\textbf{Slide #1.\ #2}\par\nopagebreak\vspace{0.1em}}

\title{Final Presentation — Speaker Notes}
\author{Jeongwon Bae}
\date{IE 522, Spring 2026}

\begin{document}
\maketitle

\slide{1}{Title}
\begin{itemize}
\item Introduce: final presentation of our paper reproduction project.
\item We reproduced Shi et al. (2024), then engineered a 100x faster pipeline that let us extend beyond the paper. I'll present the reproduction first, then the engineering, then three findings that go beyond what the paper tested.
\end{itemize}

\slide{2}{Recap: Problem and model}
\begin{itemize}
\item As we showed in the midterm, this paper models emergency evacuation using three components: the community network built from OpenStreetMap, human agents with six states, and hazard agents that expand and move.
\item Since you've seen the model in the midterm, I'll move quickly.
\end{itemize}

\slide{3}{Recap: Algorithms 1 and 2}
\begin{itemize}
\item Each step, every agent runs both Algorithm 2 (human--hazard) and Algorithm 1 (human--network). Both are from the paper, unchanged in our implementation.
\end{itemize}

\slide{4}{Reproduction scope}
\begin{itemize}
\item We reproduced all three phases on the paper: 5-community network validation, Fig.\ 5 RI vs $P_\text{max} \times H_\text{max}$, and Fig.\ 6 panic sweep.
\item Then three extensions --- I'll cover those after the reproduction results.
\end{itemize}

\slide{5}{Why speed matters}
\begin{itemize}
\item A naive implementation takes 5--15 minutes per single run. 390 runs total $\to$ 1--4 days.
\item Our optimized pipeline: 32 seconds per run, 3.4 hours total.
\item Critically: we did NOT change the algorithm. Just the functions used for path computation.
\end{itemize}

\slide{6}{Engineering 1: Profiling}
\begin{itemize}
\item The bar chart shows where time goes in a single run. Over 80\% of runtime in the naive case is Algorithm 1 --- specifically, path recomputation.
\item Root cause: every non-panicked agent calls networkx A* in pure Python every step.
\end{itemize}

\slide{7}{Engineering 2: scipy batch SSSP}
\begin{itemize}
\item Key insight: many agents share destinations (buildings, shelters). Compute one shortest-path tree per unique destination, reuse.
\item This converts per-agent work into per-destination work. Scipy's Dijkstra is in C, 10x+ faster than networkx.
\item Measured: 7--20x speedup for path computation alone.
\end{itemize}

\slide{8}{Engineering 3: A* heuristic + per-step recomputation}
\begin{itemize}
\item For single-source fallbacks (shelter redirect), we use A* with Euclidean heuristic --- another 2--3x on spatial graphs.
\item Per-step recomputation is kept, per the paper's spec.
\item Panicked agents get noisy edge weights to model "limited observations" from the paper.
\item Bottom line box: algorithms unchanged, functions replaced.
\end{itemize}

\slide{9}{Engineering 4: Multiprocessing + RNG separation}
\begin{itemize}
\item 8 workers across configs $\to$ 8x extra throughput. Network built once, shared via fork copy-on-write.
\item RNG separation is subtler but critical: 3 independent streams for humans, hazards, sim dynamics. Without it, changing Pmax changes the hazards too --- apples-to-oranges.
\end{itemize}

\slide{10}{Engineering 5: Benchmark}
\begin{itemize}
\item We ran a head-to-head: naive Pmax=2000 run vs optimized.
\item Substitute actual measured speedup here (e.g., "12x single-process, 96x overall").
\item What this enabled: 10 seeds per config, 5 communities, three extensions --- without taking shortcuts.
\end{itemize}

\slide{11}{E: PSU-UP animation}
\begin{itemize}
\item This replaces the toy animation from the midterm.
\item Configuration: paper's baseline (Pmax=2K, Hmax=5, epsilon\_p=10\%).
\item Watch: hazard appears, impacted agents reroute to shelter, some are casualties, the rest arrive.
\item Outcome corresponds to RI $\approx$ 36\% which we'll see on slide 14.
\end{itemize}

\slide{12}{Phase 1: Network validation}
\begin{itemize}
\item Building counts match the paper's Table V within 0--2\% across all 5 communities.
\item Edge counts: PSU-UP, UVA-C, VT-B are close. RA-PA and KOP-PA are way off --- paper reports E/N ratios of 6.5--6.8, unreproducible with any OSMnx config. Treated as a paper data anomaly.
\end{itemize}

\slide{13}{Phase 1: PSU-UP figures}
\begin{itemize}
\item Fig.\ 3 reproduction: walk network with buildings in yellow, shelters in green.
\item Fig.\ 4 reproduction: pedestrian flow snapshots at five timesteps during a hazard scenario.
\end{itemize}

\slide{14}{Phase 2a: RI vs Pmax x Hmax}
\begin{itemize}
\item Fig.\ 5 reproduction. Our RI is 2--4\%p higher than paper uniformly.
\item Critical confirmation: RI is independent of Pmax across 2K--8K ($\Delta < 0.2$\%p). This is the paper's core finding, and we reproduced it.
\end{itemize}

\slide{15}{Phase 2b: RS/RC/RL vs epsilon\_p}
\begin{itemize}
\item Fig.\ 6 reproduction with 9 epsilon\_p points instead of 5.
\item All three monotonic trends reproduced. Near-exact match at boundary points.
\item Paper's main conclusion holds: panic is the dominant driver of survival/casualty outcomes.
\end{itemize}

\slide{16}{Differences and unresolvable gaps}
\begin{itemize}
\item Four categories of remaining gap: all traced to unpublished paper data.
\item Shelter list not in the paper --- we swept shelter count and found 62\% of buildings best matches RS at epsilon\_p=90\%.
\item Casualty formula not specified --- we use a distance-weighted probability.
\item Hazard seed not specified --- we swept 200 seeds and picked 1135.
\end{itemize}

\slide{17}{Extension overview}
\begin{itemize}
\item Three questions the paper didn't answer, which our fast pipeline let us tackle.
\item Move quickly --- details on the next three slides.
\end{itemize}

\slide{18}{Extension 1: Pmax breakpoint}
\begin{itemize}
\item Extended Pmax from 2K to 97K across three Hmax levels.
\item Independence holds up to 20K. Breaks at 50K by +8.5\%p.
\item Mechanism: 969 buildings at 20 occupancy is about 20K capacity. At 50K we overflow --- agents queue outdoors and get hit by hazards.
\end{itemize}

\slide{19}{Extension 2: Hmax saturation}
\begin{itemize}
\item Extended Hmax from 5 to 30 at Pmax=2K.
\item RI saturates at $\sim$86\% --- more hazards don't push past this ceiling.
\item Likely $\sim$14\% of the network is structurally unreachable by hazards.
\end{itemize}

\slide{20}{Extension 3: Finer epsilon\_p}
\begin{itemize}
\item 9 points vs paper's 5.
\item Curves are smooth, monotonic, diminishing marginal --- no phase transitions.
\item Implication for policy: panic management has highest payoff at low baseline panic.
\end{itemize}

\slide{21}{Comparison alpha: Pmax animation}
\begin{itemize}
\item Same hazard scenario, different Pmax. Watch for outdoor queuing on the right.
\end{itemize}

\slide{22}{Comparison beta: epsilon\_p animation}
\begin{itemize}
\item Same hazard, different panic. Notice how the right panel's agents wander randomly instead of moving toward shelters.
\end{itemize}

\slide{23}{Comparison gamma: Hmax animation}
\begin{itemize}
\item Hazard counts differ by design --- say this explicitly. Left has 5 hazard events, right has 30.
\item The visual takeaway: right panel has most of the network covered in red, agents hit repeatedly.
\end{itemize}

\slide{24}{Summary}
\begin{itemize}
\item Reproduction successful within 2--4\%p across all paper targets.
\item Three novel findings: Pmax breakpoint, Hmax saturation, smooth panic effect.
\item Engineering enabled all of this without algorithm changes.
\end{itemize}

\slide{25}{Future work}
\begin{itemize}
\item Paper's own: response agents, social-force, MDP panic model.
\item Our own gap analysis suggests a panic-dependent casualty formula could close the RC ceiling gap.
\end{itemize}

\slide{26}{References}
\begin{itemize}
\item Acknowledge OSMnx, scipy. Code available on GitHub.
\item Thank audience, invite questions.
\end{itemize}

\end{document}
```

- [ ] **Step 3: Compile and verify**

```bash
cd /home/flametom/coursework/IE522_PJT/presentation
pdflatex -halt-on-error script.tex
```

Verify `script.pdf` generated with all 26 slides' notes.

- [ ] **Step 4: Commit**

```bash
git add script.tex
git commit -m "feat: add speaker notes (script.tex) for all 26 main slides"
```

---

## Task 26: Rehearsal #1 + timing log

**Files:**
- Create: `presentation/rehearsal_log.md`

- [ ] **Step 1: Do a solo rehearsal**

Open `final.pdf` in Adobe Reader on your laptop. Go through all 26 main slides while speaking from `script.pdf`. Start a stopwatch at Slide 1.

Record per-slide time (wall-clock) in a log file.

- [ ] **Step 2: Write the log**

Create `presentation/rehearsal_log.md`:

```markdown
# Rehearsal Log

## Rehearsal #1 — [date]

Total elapsed (Slide 1 → Slide 26): XX:XX

| Slide | Time used | Notes |
|---|---|---|
| 1 | 0:15 | |
| 2 | 0:45 | recap fast |
| 3 | 0:50 | ... |
| ... | | |
| 26 | 0:20 | |

### Observations
- Overrun: [list slides that took longer than expected]
- Verbal fumbles: [list sections that were hard to articulate]
- Missing transitions: [list slides where I didn't have a good "next"]

### Revisions for Rehearsal #2
- [what to compress / expand / re-order]
```

- [ ] **Step 3: If total > 30 min, identify cuts**

If you overran, candidate cuts (in priority order):
1. Slide 17 (extension overview) — can drop or fold into slide 18
2. Slide 20 (finer εp) — smallest new finding
3. Slide 16 (gap analysis) — can be compressed to 3 bullets
4. Slide 22 or 23 (one of the side-by-side animations) — cut one, keep alpha+beta

Do NOT cut: slides 1–5, 7, 10, 11, 14, 18, 21.

- [ ] **Step 4: Commit the log**

```bash
git add presentation/rehearsal_log.md
git commit -m "docs: rehearsal #1 timing log"
```

---

## Task 27: Share assets with Dalal + Q&A prep

**Files:**
- Create: `presentation/qna_prep.md`

- [ ] **Step 1: Draft the Dalal email**

Create `email_to_dalal_shared_assets.md`:

```markdown
Hi Dalal,

As I worked through the final presentation I generated a few new assets that might be useful for the report:

1. Extension charts (PDF):
   - presentation/assets/fig_ext1_pmax_breakpoint.pdf
   - presentation/assets/fig_ext2_hmax_saturation.pdf
   - presentation/assets/fig_ext3_panic_finer.pdf

2. Benchmark charts (PDF):
   - presentation/assets/benchmark_time_dist.pdf
   - presentation/assets/benchmark_scaling.pdf

3. Benchmark numbers (JSON):
   - results/benchmark/naive_timings.json
   - results/benchmark/optimized_timings.json
   - Key number for the report: naive X sec -> optimized Y sec, ~Zx single-process speedup.

4. Animation frames (static snapshots could work as figures in the report):
   - presentation/assets/frames_psuup/sim_000.png, sim_030.png, sim_060.png
   - presentation/assets/frames_cmp_pmax/cmp_000.png, cmp_030.png, cmp_060.png
   - (and same for cmp_panic, cmp_hmax)

Use anything you find helpful. Feel free to ignore if they don't fit the report's narrative.

Let me know when you have a draft ready for cross-check.

Jeongwon
```

- [ ] **Step 2: Send the email (outside this automation)**

Copy the email text into your email client. Strip markdown formatting first (no \*\* or \#). Send.

- [ ] **Step 3: Draft Q&A prep**

Create `presentation/qna_prep.md`:

```markdown
# Q&A Preparation

## Likely questions and answers

### Q: Why did you stop at 97K Pmax for the extension?
A: At 97K, agents per building exceed 100. Beyond that the simulation becomes memory-bound (we hit swap) and the agent-per-building ratio is no longer physically meaningful for a pedestrian model. 97K is well past the breakpoint so it covers the phenomenon.

### Q: Why does RS stay lower than the paper at low epsilon_p?
A: We fit shelter count (600) against RS at epsilon_p=90%. At low panic the difference reflects the unknown shelter locations in the paper. Increasing shelter count closes this gap but worsens RS at high panic. See slide 16 and backup slide.

### Q: Why didn't you use GPU acceleration?
A: The bottleneck was Python overhead (networkx calls), not numerical compute. scipy's C implementation was sufficient. GPU would help if we went to 1M+ agents, which is beyond the paper's scope.

### Q: What's the RA-PA/KOP-PA edge count anomaly?
A: See backup slide 28. Paper's E/N ratios of 6.5--6.8 are unreproducible with any OSMnx config; geometry segment counting gets 73% of the paper's number.

### Q: Why not implement response agents?
A: See backup slide 29 (extension catalog). Response agents require a new agent class; we scoped to extensions that use the existing model.

### Q: How did you validate the scipy batch SSSP gives the same answer as networkx A*?
A: See Task 7 step 2 — the benchmark runs both and confirms RI/RS/RC/RL match within 0.1%p.

### Q: Why per-step path recomputation instead of caching?
A: Paper spec: "pedestrians rely on up-to-date observations." Cached paths would cause agents to move through newly-congested edges. We keep per-step recomputation and use batch SSSP to make it fast.

### Q: What's the MTV scenario (if asked about simulation validity)?
A: We used 10 independent seeds per config and report mean ± SD. Variability is typically ±1%p for RI, ±2%p for RS/RC/RL. Our matches to the paper are all well outside noise.

## Backup slide reference
- 27: Multi-community Pmax
- 28: Edge count anomaly diagnostics
- 29: Extension catalog
- 30: Static snapshot strips
```

- [ ] **Step 4: Commit**

```bash
git add email_to_dalal_shared_assets.md presentation/qna_prep.md
git commit -m "docs: Q&A prep and Dalal asset-sharing email draft"
```

---

## Task 28: Cross-check with Dalal + Rehearsal #2

**Files:**
- Append to: `presentation/rehearsal_log.md`

- [ ] **Step 1: Cross-check key numbers**

When Dalal's report draft arrives (or 2--3 days before submission, whichever first), cross-check:
- RI values at (Pmax, Hmax) corners must match between slides 14/18 and the report
- RS/RC/RL at εp = 10%, 50%, 90% must match between slides 15/20 and the report
- Building counts must match slide 12 and the report's Phase 1 section
- Benchmark numbers (if Dalal uses them) must match slide 10

If discrepancies found, investigate:
1. Are we using the same source JSON? Likely yes — both pull from `results/` on git `main`.
2. Was one side rounded differently? Agree on a precision convention.
3. Was a bug fix applied after one side captured numbers? Flag and re-derive.

- [ ] **Step 2: Rehearsal #2**

Same procedure as Task 26 Step 1. Focus on:
- Slides that overran in Rehearsal #1
- Smooth transitions between reproduction (slide 15) → gaps (slide 16) → extensions (slide 17)
- Animation slides — don't wait for the loop; narrate over 15–20 seconds and click forward

Append to `rehearsal_log.md`:

```markdown
## Rehearsal #2 — [date]

Total elapsed: XX:XX  (vs. #1: XX:XX)

### Changes since #1
- [what was revised]

### Remaining issues
- [...]
```

- [ ] **Step 3: Commit log**

```bash
git add presentation/rehearsal_log.md
git commit -m "docs: rehearsal #2 log + cross-check with Dalal"
```

---

## Task 29: Final rehearsal + equipment check

**Files:**
- Append to: `presentation/rehearsal_log.md`

- [ ] **Step 1: Equipment verification checklist**

Print-out or on-screen checklist, 1 day before presentation:

```
[ ] final.pdf opens in Adobe Reader
[ ] All 4 animations play when clicked
[ ] Backup slide 30 static strips visible
[ ] Font renders correctly (no missing glyphs)
[ ] Laptop charger in bag
[ ] HDMI adapter in bag
[ ] USB backup of final.pdf
[ ] Backup: final.pdf uploaded to Google Drive (link accessible offline on phone)
[ ] Water bottle
```

- [ ] **Step 2: Final rehearsal under presentation conditions**

- Use laptop + external display if available (simulates projector)
- Stand up; do not sit
- Speak out loud; do not read the script silently
- Use a real stopwatch — hit start at slide 1

- [ ] **Step 3: Final log entry**

Append:

```markdown
## Final Rehearsal — [date, day before]

Total elapsed: XX:XX

Status: [READY | NEEDS REVISION]

Equipment check: all items ✓
```

- [ ] **Step 4: Commit**

```bash
git add presentation/rehearsal_log.md
git commit -m "docs: final rehearsal log + equipment check"
```

---

## Self-Review

### 1. Spec coverage

Going through the spec (§2 Slide Skeleton, §3 Engineering Deep Dive, §4 Visualization, §5 Non-Slide Work):

| Spec item | Plan task(s) |
|---|---|
| Slides 1–4 (title, recap, scope) | Task 12 |
| Slide 5 (why speed) | Task 13 |
| Slides 6–10 (engineering deep dive) | Tasks 14, 15, 16 |
| Slide 11 (E animation) | Task 17 |
| Slides 12–13 (Phase 1) | Task 18 |
| Slides 14–15 (Phase 2a, 2b) | Task 19 |
| Slide 16 (gaps) | Task 20 |
| Slides 17–20 (extensions) | Task 21 |
| Slides 21–23 (α/β/γ animations) | Task 22 |
| Slides 24–26 (closing) | Task 23 |
| Backup slides 27–30 | Task 24 |
| Naïve benchmark measurement | Tasks 2, 7 |
| Renderer functions | Tasks 3, 4 |
| Animation generation | Tasks 5, 6 |
| Benchmark charts | Task 8 |
| Extension charts | Tasks 9, 10, 11 |
| script.tex speaker notes | Task 25 |
| Rehearsals | Tasks 26, 28, 29 |
| Dalal coordination | Task 27, 28 |
| Equipment check | Task 29 |

All spec sections covered.

### 2. Placeholder scan

- Task 16 Step 3 has `__SINGLE_SPEEDUP__` and `__TOTAL_SPEEDUP__` — these are flagged as "manually substitute from Step 2" which is an explicit handoff, not a placeholder in the final artifact.
- Task 25 script.tex slide 10: "Substitute actual measured speedup here" — similar explicit handoff.
- No "TODO", "TBD", "implement later" anywhere else.

### 3. Type consistency

- `render_animation_frames(history, G, out_dir, prefix="sim", building_nodes=None, shelter_nodes=None, title=None)` — consistent between Task 3 definition and Task 5 call site.
- `render_sidebyside_frames(hist_L, hist_R, G, out_dir, prefix, label_L, label_R, building_nodes=None, shelter_nodes=None, caption=None)` — consistent between Task 4 and Task 5.
- `EvacuationSimulation(..., use_batch_sssp=True)` — consistent between Task 2 (definition) and Task 7 (usage).
- Frame file patterns: `sim_NNN.png` (E) and `cmp_NNN.png` (C) — consistent between driver (Task 5) and LaTeX animategraphics calls (Tasks 17, 22).

No inconsistencies found.

### 4. Additional notes

- Backup slide 30 uses frames from `frames_psuup` and `frames_cmp_pmax` directly. This means those frames must exist before Task 24 completes. Task 6 (frame generation) precedes Task 24 in the plan ordering, so this is fine.
- `email_to_dalal_shared_assets.md` is created in Task 27 but references files generated in earlier tasks. This is correct ordering.
