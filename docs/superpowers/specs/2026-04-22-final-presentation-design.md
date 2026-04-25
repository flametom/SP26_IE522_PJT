# Final Presentation Design — IE 522 Project

**Date:** 2026-04-22
**Author:** Jeongwon Bae
**Project:** Multi-agent Evacuation Simulation (Shi et al., IEEE CASE 2024)
**Course:** IE 522 Simulation, Penn State University, Spring 2026

**Current status (2026-04-25):** Implemented and superseded by later slide-polish passes. The current committed deck is `presentation/final.pdf` (29 pages: 25 main + 4 backup) with `presentation/script.pdf` as the companion speaker notes.

---

## 0. Context

- This design covers the **final presentation slides only** (Jeongwon's deliverable).
  The final report is owned by Dalal and is out of scope here.
- The **first presentation** (`presentation/main.tex`, 9 slides, pre-reproduction)
  already covered problem motivation, model overview, agents, hazards, Algorithm 1/2,
  and a toy animation. Audience and instructor are assumed to have seen it.
- Reproduction work is complete: Phase 1 (5-community network validation),
  Phase 2a (RI vs P_max x H_max), Phase 2b (RS/RC/RL vs ε_p).
- Extension work is complete: P_max 2K → 97K (PSU-UP), H_max 5 → 30, finer ε_p
  resolution (9 points), and multi-community P_max sweep.

---

## 1. Decisions Summary

| Decision | Value | Reason |
|---|---|---|
| Presentation depth | Level (c) — 25+ slides, deep dive | Recap minimal since 1차 covered model |
| Deck build mode | Hybrid (C) — copy `main.tex` → `final.tex`, edit front, replace slide 9, add new | Reuses validated Beamer style/macros |
| Narrative arc | B — Science-first (Reproduction → Engineering → Extensions) | Matches user requirement "reproduction must come first" and IE 522 simulation identity |
| Engineering depth | (III) — 5 slides, deep dive with pseudo-code + complexity + benchmark | User chose for depth; can trim later |
| Benchmark evidence | Measured naïve 1 run | Strongest quantitative support for speedup claim |
| Visualization plan | E + C (all three α/β/γ) | User wants flip-through multiple scenarios |
| Animation format | Beamer `animategraphics` (same as 1차) | Already validated in 1차 presentation |
| Speaker notes | Separate `script.tex` (1차 pattern) | Consistency with prior workflow |
| Compressible slides | Not pre-marked | User prefers full deck first, trim during rehearsal if needed |
| Total slide count | Current artifact: 25 main + 4 backup = 29 | Final deck after later consolidation and backup trimming |
| Bug fix history | Excluded | User requested exclusion |
| Multi-community extension | Backup slide only | Keeps main narrative clean |

---

## 2. Original Slide Skeleton (superseded)

This section records the initial 2026-04-22 design target. The implemented final deck was later consolidated to 25 main slides + 4 backup slides.

All slides use Beamer aspectratio=169 with the color/font system from `main.tex`.
"1차 reuse" = TikZ/content can be lifted. "New" = must be authored.

### Opening (slides 1–4)

| # | Title | Source | Key content |
|---|---|---|---|
| 1 | Title | Modify 1차 | "Final Report", updated date |
| 2 | Problem & Model recap (compressed) | Merge 1차 slide 2 + 3 | Problem framing TikZ + 3-component block diagram |
| 3 | Agents & Algorithms recap (compressed) | Merge 1차 slide 5 + 7 | 6-state transition + Algorithm 1/2 side-by-side summary |
| 4 | Reproduction scope | New | Paper-to-our-work mapping: Table V, Fig 3/4/5/6; Phase 2a (Pmax × Hmax, 9 configs) + Phase 2b (ε_p, 5 → 9 finer configs) + Extensions (Pmax 2K–97K, Hmax to 30) |

### Why speed matters (slide 5)

| # | Title | Source | Key content |
|---|---|---|---|
| 5 | Why speed matters | New | "390 runs × 121 steps × N agents"; naïve would take days; motivates engineering section |

### Engineering deep dive (slides 6–10)

| # | Title | Key content |
|---|---|---|
| 6 | Profiling & bottleneck | Naïve call count (~200K path calls per run); time-distribution bar chart from measured naïve run; **path recomputation dominates (>80%)** |
| 7 | scipy batch SSSP | Key insight: destinations shared across agents (K ≪ N); side-by-side code (networkx A* per-agent vs `sp_dijkstra` with dest indices); complexity table; measured **7–20× speedup** |
| 8 | A* heuristic + per-step recomputation | Euclidean heuristic for single-source fallback; per-step recomputation kept (paper-spec compliance); panic noisy-weight A* for irrational routing; **"algorithm unchanged, only functions replaced"** explicit callout |
| 9 | Multiprocessing + RNG separation | 8-worker parallelism across configs; 3-stream RNG architecture (seed / seed+1000 / seed+2000) so P_max change does not contaminate hazard configuration; multi-seed averaging (N=10) |
| 10 | Benchmark results | 2-panel chart: per-step scaling + cumulative throughput; **naïve 1 run vs optimized 1 run (measured)**; final speedup number = scipy batch × multiprocessing × A*; "what this enabled" summary box |

### Visualization bridge (slide 11)

| # | Title | Source | Key content |
|---|---|---|---|
| 11 | **E animation — PSU-UP in action** | New `\animategraphics` block | 61 frames @ 6 fps, Pmax=2K/Hmax=5/ε_p=10%/seed=42 (paper baseline); replaces 1차 toy animation |

### Reproduction results (slides 12–16)

| # | Title | Source | Key content |
|---|---|---|---|
| 12 | Phase 1 — Network validation (5 communities) | `fig3_network_*.png` | Building count table (100–102% match); Fig 3 grid; edge count anomaly (RA-PA, KOP-PA) mentioned as table footnote |
| 13 | Phase 1 — PSU-UP Fig 3/4 | `fig3_network_PSU-UP.png`, `fig4_flow_PSU-UP.png` | 2-panel: static network + one flow snapshot |
| 14 | Phase 2a — RI vs P_max × H_max | `fig5_RI_PSU-UP.png` | Table (ours vs paper) + reproduced Fig 5 chart |
| 15 | Phase 2b — RS/RC/RL vs ε_p | `fig6_panic_PSU-UP.png` | Table (ours vs paper, 9 ε_p points) + reproduced Fig 6 chart |
| 16 | Differences & unresolvable gaps | New | 3 structurally unresolvable: shelter list (unpublished), casualty formula (unspecified), hazard seed (unpublished); shelter sensitivity 62% figure; note that we still match within 2–4%p |

### Extensions (slides 17–20)

| # | Title | Source | Key content |
|---|---|---|---|
| 17 | Extension overview | New | 3-box diagram: paper-tested range (faded) vs our extended range (bold); sentence per extension; fast transition |
| 18 | Extension ① — P_max breakpoint | `fig_ext1_pmax_breakpoint.pdf` | RI vs log(P_max) curve (2K → 97K), Hmax 5/10/15 overlaid; flat up to 20K, break at 50K, saturates by 97K; arithmetic: 51 agents/building at 50K; connects to slide 21 |
| 19 | Extension ② — H_max saturation | `fig_ext2_hmax_saturation.pdf` | RI vs H_max (5 → 30), saturates at ~86%; interpretation: ~14% unreachable topology; connects to slide 23 |
| 20 | Extension ③ — Finer ε_p | `fig_ext3_panic_finer.pdf` | 9-point RS/RC/RL curves vs paper's 5 points; smooth monotonic curves; diminishing marginal panic effect; connects to slide 22 |

### Comparison animations (slides 21–23)

All use `\animategraphics`, 61 frames @ 6 fps, side-by-side 2-panel composite.

| # | Title | Left panel | Right panel | Notes |
|---|---|---|---|---|
| 21 | Comparison α — P_max 2K vs 50K | Pmax=2K, Hmax=5, ε_p=10% | Pmax=50K, Hmax=5, ε_p=10% | Same hazard scenario (hazard_seed=1135) |
| 22 | Comparison β — ε_p 10% vs 90% | Pmax=2K, Hmax=5, ε_p=10% | Pmax=2K, Hmax=5, ε_p=90% | Same hazard scenario |
| 23 | Comparison γ — H_max 5 vs 30 | Pmax=2K, Hmax=5, ε_p=10% | Pmax=2K, Hmax=30, ε_p=10% | Hazard scenarios differ by design (H_max varies hazard count); caption clarifies |

### Closing (slides 24–26)

| # | Title | Source | Key content |
|---|---|---|---|
| 24 | Conclusion | New | Reproduction confirmed + 3 novel findings + remaining gaps acknowledged |
| 25 | Future work | Compress 1차 slide 9 | Response agents, panic-dependent casualty multiplier, social force model, MDP — as mentioned in paper Discussion |
| 26 | References & Acknowledgment | New | Paper citation, Zhang & Yang 2021 EMBC, OSMnx, scipy |

### Backup slides (appendix, slides 27–30)

Reachable via `\appendix` or navigation; not part of main flow.

| # | Title | Purpose |
|---|---|---|
| 27 | Multi-community P_max extension | Q&A: "does breakpoint generalize?" |
| 28 | Edge count anomaly — diagnostic detail | Q&A: "why RA-PA, KOP-PA off?" |
| 29 | Extension catalog (6 candidates) | Q&A: "why not more extensions?" |
| 30 | Static snapshot strips (E + C α/β/γ) | PDF viewer animation fallback |

---

## 3. Engineering Deep Dive Detail (slides 6–10)

### Slide 6 — Profiling & bottleneck

**Layout:** Left = bar chart of time distribution from naïve 1 run. Right = text explanation.

**Bar chart segments (representative, actual values from A2 benchmark):**
- Path recomputation (A* per agent per step): dominant
- Algorithm 2 (hazard interaction): small
- Flow computation: small
- Commit / state update: small
- Misc (logging, snapshot): minimal

**Text:**
- Per run (P_max = 2000, 121 steps): ~200K+ path calls
- Observation: every non-panicked agent recomputes a full shortest path every step
  (paper-spec: agents rely on up-to-date local observations)
- Pure Python `nx.astar_path` becomes the bottleneck

### Slide 7 — scipy batch SSSP

**Layout:** Top = naïve code block. Bottom = optimized code block. Right = complexity table.

**Code comparison:**
```python
# Naive: per agent, per step
for p in humans:
    path = nx.astar_path(G, p.src, p.dest)

# Optimized: per unique destination, per step (shared across agents)
dest_indices = np.array([node_to_idx[d] for d in unique_destinations])
_, preds = sp_dijkstra(sparse_matrix, indices=dest_indices,
                       return_predecessors=True)
# Each agent looks up its path from preds[dest] in O(path_length)
```

**Complexity table:**

| Approach | Per-step call count | Per-step total |
|---|---|---|
| Naïve per-agent A* | O(N) | O(N · (V+E) log V) |
| Batch SSSP | O(K) | O(K · (V+E) + V) |

Here N = active agents, K = unique destinations, K ≪ N when agents share shelter targets.

**Measured speedup: 7–20×** (from reproduction_report.md).

**Implementation note in small font:** predecessor tree is rooted at target; chasing preds from src walks toward tgt (intuition-reversed but correct).

### Slide 8 — A* Euclidean heuristic + per-step recomputation

**Layout:** Top half = heuristic function with spatial-network rationale.
Bottom half = per-step recomputation justification + panic noisy-weight variant.

**Key callout (footer):**
> *"Our Algorithm 1/2 logic is unchanged from the paper.
> Only the functions used for path computation were replaced."*

### Slide 9 — Multiprocessing + RNG separation

**Layout:** Left = "config × seed grid" diagram showing parallelism. Right = 3-stream RNG diagram.

**Key points:**
- 8-worker `multiprocessing.Pool` across (P_max, H_max, ε_p, seed) combinations
- Each worker independent → ~8× additional throughput
- **3-stream RNG (seed, seed+1000, seed+2000) = (humans, hazards, sim dynamics)**
- Why this matters: changing P_max only changes the human stream; hazard configuration is identical across P_max sweeps → apples-to-apples comparison
- Multi-seed averaging (N = 10 seeds per config) → mean ± std

### Slide 10 — Benchmark results

**Layout:** Left chart + right chart + summary box below.

**Left chart (per-step timing vs N agents):**
- Blue line: naïve
- Orange line: optimized
- X-axis: P_max (log scale)
- Y-axis: ms / step

**Right chart (cumulative throughput):**
- Runs completed over wall-clock time
- Naïve (extrapolated) vs optimized (actual)

**Summary numbers:**
- Naïve 1 run: X minutes (measured by A2)
- Optimized 1 run: ~32 seconds (3.4h / 390 runs)
- Total speedup: batch SSSP (7–20×) × multiprocessing (8×) × A* heuristic (~2×) ≈ 100–300×

**"What this enabled" box:**
- 10 seeds × 45 paper configs = full reproduction with statistical significance
- 5 communities × network sweep = Phase 1 validation
- P_max 2K → 97K + H_max 5 → 30 + finer ε_p = three extensions

---

## 4. Visualization Implementation Plan

### 4.1 Snapshot generation

`config.py` exposes `SNAPSHOT_TIMES`. For animation runs, set to `list(range(0, 121, 2))` → 61 snapshots per run. `simulation.py`'s existing `_record()` method already dumps positions, states, and hazards to `history` — no new simulation code needed.

### 4.2 New renderer functions (in `visualization.py`)

```python
def render_animation_frames(history, G, out_dir, prefix="sim", fps_hint=6):
    """Render each snapshot in history as a numbered PNG.
    Uses existing fig4_flow style (network background + colored agent dots +
    hazard circles). Output: out_dir/{prefix}_000.png ... {prefix}_NNN.png."""
```

```python
def render_sidebyside_frames(hist_L, hist_R, G, labels, out_dir, prefix):
    """Two-panel composite. Same timestep index aligned between panels.
    Output: out_dir/{prefix}_000.png ... {prefix}_NNN.png."""
```

Estimated ~100 LOC combined.

### 4.3 Simulation runs required

| Run | Config | Use | Est. time |
|---|---|---|---|
| R1 | Pmax=2K, Hmax=5, ε_p=10% | E (slide 11) + α left + β left + γ left | ~1 min |
| R2 | Pmax=50K, Hmax=5, ε_p=10% | α right (slide 21) | ~5 min |
| R3 | Pmax=2K, Hmax=5, ε_p=90% | β right (slide 22) | ~1 min |
| R4 | Pmax=2K, Hmax=30, ε_p=10% | γ right (slide 23) | ~2 min |
| R5 | Naïve baseline (Pmax=2K, Hmax=5, ε_p=10%) | Slide 6 + 10 benchmark | ~5–15 min |

Total simulation time: ~20–30 min. R1 is reused across 4 animation slides.

### 4.4 File layout

```
presentation/
├── final.tex
├── script.tex                       (speaker notes, new)
├── main.tex                         (1차 deck, preserved)
└── assets/
    ├── frames/                      (1차 toy, preserved)
    ├── frames_psuup/                (E, new)
    ├── frames_cmp_pmax/             (α, new)
    ├── frames_cmp_panic/            (β, new)
    ├── frames_cmp_hmax/             (γ, new)
    ├── network_PSU-UP_white.png     (1차, reused)
    ├── fig_ext1_pmax_breakpoint.pdf (new)
    ├── fig_ext2_hmax_saturation.pdf (new)
    ├── fig_ext3_panic_finer.pdf     (new)
    ├── benchmark_time_dist.pdf      (new, slide 6 — time distribution bar chart)
    └── benchmark_scaling.pdf        (new, slide 10 — naïve vs optimized scaling + throughput)
```

### 4.5 γ caption requirement

Slide 23 must include a caption clarifying:
> *Left and right panels show different hazard scenarios by design
> (H_max is the hazard count itself). Agent seed = 42 held constant;
> only hazard configuration varies with H_max.*

### 4.6 PDF viewer compatibility

Primary: Adobe Reader (confirmed working with 1차 deck).
Fallback: backup slide 30 (static snapshot strips for all 4 animations) reachable via appendix.

---

## 5. Non-Slide Work Items

### A. Jeongwon (slides) solo work

| # | Task | Priority | Est. time |
|---|---|---|---|
| A1 | `final.tex` draft (26 slides) | ★★★ | 6–8 h |
| A2 | Naïve benchmark 1 run (slide 6/10 data) | ★★★ | 30 min – 1 h |
| A3 | Extension charts `fig_ext1/2/3.pdf` | ★★★ | 1–1.5 h |
| A4 | E animation render (PSU-UP single scenario) | ★★★ | 1–1.5 h |
| A5 | C animations α/β/γ (side-by-side × 3) | ★★★ | 2–3 h |
| A6 | `script.tex` speaker notes (1–2 sentences per slide) | ★★ | 3–4 h |
| A7 | Dress rehearsal + timing check (≥ 2 solo runs) | ★★ | 1.5–2 h |
| A8 | Q&A question list + answers linked to backup slides | ★ | 2 h |
| A9 | Backup slides (multi-community, edge anomaly, extension catalog, snapshot strips) | ★ | 1 h |

**Total: ~20–25 h.**

### B. Dalal (report) solo work — Jeongwon flags only

| # | Task | Jeongwon's role |
|---|---|---|
| B1 | Report draft | None |
| B2 | Report fact-check | Review when draft arrives |
| B3 | Report figure selection | Share new visuals (C1 below) |

### C. Joint / coordination

| # | Task | Detail |
|---|---|---|
| C1 | Share new visual assets | Extension charts (A3) + static strips of E/α/β/γ (5 timesteps each) → email Dalal |
| C2 | Share naïve benchmark result | Relevant to report's implementation/performance section |
| C3 | Cross-check numbers 2–3 days before submission | RI/RS/RC/RL values must match between slides and report |
| C4 | GitHub hygiene | Commit `final.tex`, `script.tex`, new figures, new frame directories; verify `.gitignore` |
| C5 | Presentation-day equipment check | Confirm Beamer `animategraphics` playback on venue viewer |

### D. Risk management

| # | Risk | Mitigation |
|---|---|---|
| D1 | Animation won't play on venue PDF viewer | Backup snapshot strips in slide 30; bring own laptop as fallback |
| D2 | Presentation runs over time | No pre-marking of compressible slides; decide in rehearsal. Do NOT pre-compress. |
| D3 | Q&A: edge count anomaly | Backup slide 28 |
| D4 | Q&A: why no further extensions | Backup slide 29 (extension catalog) |
| D5 | Data inconsistency with report | C3 cross-check resolves |

### E. Schedule (today = 2026-04-22)

| Day | Date | Work |
|---|---|---|
| D1–2 | 04-23 Fri, 04-24 Sat | A2 (benchmark), A3 (ext charts), A4 (E anim), A5 partial (α) |
| D3–4 | 04-25 Sun, 04-26 Mon | A5 complete (β, γ), A1 skeleton |
| D5–6 | 04-27 Tue, 04-28 Wed | A1 complete, A6 first draft |
| D7 | 04-29 Thu | A7 rehearsal #1 + revisions; C1/C2 to Dalal |
| D8 | 04-30 Fri | A6/A7 iterate; A8 Q&A prep; A9 backup slides |
| D9 | 05-01 Sat | C3 cross-check with Dalal; final rehearsal |
| D10 | 05-02 Sun | Buffer: micro-adjustments; C5 equipment check |
| Day of | TBD | Present |

---

## 6. Acceptance Criteria for This Spec

This design is considered done and ready to transition to implementation planning when:

1. `final.tex` produces a 26-slide PDF with all animations playing in Adobe Reader.
2. 4 animation frame directories (`frames_psuup`, `frames_cmp_pmax`, `frames_cmp_panic`, `frames_cmp_hmax`) each have frames 000–060.
3. 3 extension charts + 2 benchmark charts exist in `presentation/assets/`.
4. Naïve benchmark measurement recorded and used in slides 6 and 10.
5. `script.tex` exists with 1–2 sentences per slide.
6. Backup slides (multi-community, edge anomaly, extension catalog, static strips) are present.
7. At least one solo rehearsal completed with timing log.
8. Key visual assets shared with Dalal for potential report reuse.
9. Numbers cross-checked with Dalal's report within 2–3 days of submission.

---

## 7. Out of Scope

- Report writing (Dalal's deliverable).
- New simulation experiments beyond those listed in §4.3.
- Algorithm changes. (Engineering section explicitly states logic is unchanged.)
- Bug fix history slides. (User excluded.)
- Pre-compression of the deck. (User prefers full deck first.)
- New extension experiments (e.g., response agents, panic-dependent casualty).
  The extension catalog remains backup-only.
