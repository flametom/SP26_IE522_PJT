# Engineering-Section Redesign + Animation Resize

**Date:** 2026-04-23
**Scope:** `presentation/final.tex` — slides 6–11 (engineering) and slides 12, 22–24 (animations).
**Supersedes:** engineering-related portions of `2026-04-22-final-presentation-design.md`. Animation sizing is new.
**Status:** Brainstorming complete, awaiting user review before plan-writing.

## 1. Motivation

User feedback on the current final deck (commit `fa13709`, 4th feedback round):

1. The engineering section (slides 6–11, 6 slides total) does not convey *why* the speedup work was necessary. Raw numbers (7.5×, 60×, 230×) land without context.
2. The paper (Shi et al., IEEE CASE 2024) specifies almost no implementation details — only "Python 3.7", "Apple M1 Pro, 16 GB RAM", and the per-run wall-time data (Pmax=2K → 2.5 h; Pmax=8K → 22 h). Everything else (shortest-path method, caching policy, parallelism, RNG scheme) was a choice the audience never sees us making.
3. The section should frame **paper vs our implementation**, not our-v1 vs our-v2. Current framing (e.g. "naïve approach vs our implementation", complexity tables with generic N/K variables) reads as us-vs-us without enough motivation.
4. Animations on slides 12, 22–24 are too large. On slides 22–24 (95 % width), the `\animategraphics` control bar renders cramped against the page bottom and risks clipping in Adobe Reader. On slide 12 (52 % width) the control bar is not visible at all.

## 2. Goals

- Replace slides 6–11 (6 slides) with **4 slides** that tell a "paper silence → our choice → measured outcome → enabled analysis" story.
- Every quantitative claim (speedup, runtime) is a *consequence* of the narrative, not the star.
- Cite the paper's implementation-related text verbatim so the "paper silence" frame is verifiable.
- Drop all remaining engineering-specific code blocks and abstract O(N)/O(K) complexity tables; replace with one mechanism diagram.
- Resize animations on slides 12, 22–24 so the `\animategraphics` control bar is clearly visible in Adobe Reader.

## 3. Non-goals

- No *content* changes to slides 1–5 (title + recaps + scope), slides 13–21 (Phase 1, Phase 2, Gaps, Extensions), or slides 25–32 (Summary, Limitations, References, Backup). Automatic renumbering of these slides' positions as the deck shrinks by 2 is expected and not considered a content change.
- No changes to the underlying simulation code.
- No attempt to measure `K` (unique destinations per step) empirically for this deck. The mechanism diagram uses a qualitative "hundreds" framing; exact measurement is a Possible Future Work item.

**In-scope clarification:** `presentation/script.tex` *is* in scope for this spec. The speaker-note entries for `\slide{6}` through `\slide{9}` must be rewritten to match the new engineering titles, and `\slide{10}`-onward entries must be decremented by 2 to re-sync with the renumbered deck. This is a small mechanical update but must happen in the same patch to keep presenter artifacts consistent.

## 4. Slide-level design

### 4.1 NEW Slide 6 — *What the paper tells us — and what it leaves to us*

**Frame title:** `What the paper tells us — and what it leaves to us`

**Layout:** two `\begin{columns}` blocks at top (paper specifies / paper silent), followed by a centered `\fcolorbox` highlight box at the bottom.

**Left column (block, blue, `\begin{block}{...}` with paper-specifies content):**
- Python 3.7 environment
- Apple M1 Pro (8-core CPU, 14-core GPU), 16 GB RAM
- Algorithms 1 & 2 — *decision logic only; path computation unspecified*
- Measured wall-time:
  - Pmax = 2,000 → 2.5 h per run
  - Pmax = 8,000 → 22 h per run

**Right column (alertblock, red-tinted, paper-silent content):**
- Shortest-path library / algorithm
- Per-step path policy (recompute? cache?)
- Parallel execution strategy (paper describes "a single simulation run")
- RNG scheme for controlled experiments
- Reproducibility seeding

**Bottom highlight (`\fcolorbox{highlightblue}{lightbluefill}{...}`):**
Three-line paragraph, centered:

```
At the paper's 2.5 h/run, reproducing our 390-run experiment
would take 41 days of sequential compute.

Our engineered pipeline does it in 3.4 hours.

→ The engineering isn't a side achievement —
  it's the prerequisite for every chart in the rest of this deck.
```

**Footnote (`\scriptsize\color{gray}`):** "Hardware comparison is indicative — Apple M1 Pro is a reasonably fast chip; most of the gap is algorithmic, not hardware."

**Source citation:** `\source{Shi et al.\ (2024), p. 379}` (paper page where the runtime sentence appears).

### 4.2 NEW Slide 7 — *Gap A: Computing paths, 200K+ times per run*

**Frame title:** `Gap A: Computing paths, 200K+ times per run`

**Layout:** top band (profile + why-this-matters, 2 columns), middle band (mechanism diagram, TikZ, full-width), bottom band (Amdahl bridge, one `\fcolorbox` line).

**Top band, left column (≈0.50\textwidth):**
- `\includegraphics` of `assets/benchmark_time_dist.pdf` at ≈0.95\linewidth (already used on current slide 7; keep but shrink slightly).

**Top band, right column (≈0.46\textwidth):**
- `\textbf{Why this slice matters}` heading
- Bullets:
  - Algorithm 1 path recomputation ≈ 87 % of a single run
  - 2,000 agents × 121 steps ≈ 242 K queries / run
  - In pure Python + per-agent calls → the paper's reported 2.5–22 h
  - Everything else (flow bookkeeping, state transitions, hazard checks) is the other 13 %

**Middle band (TikZ mechanism diagram, 2 panels side-by-side):**

Panel A (left, labeled **"Per-agent queries"**):
- Stack of agent nodes `p1 … pN` (use 3–4 visible nodes + ellipsis)
- Each agent has an arrow pointing to a shared graph node, labeled `shortest_path(G, src, dest)`
- Caption under panel: `2,000 per-agent queries × 121 steps, pure Python`

Panel B (right, labeled **"Shared destination trees"**):
- Row of destination nodes `d1, d2, d3, …` (use 3–4 visible + ellipsis)
- Each destination has a small tree icon `T(d)` computed once
- Agent cloud below points to trees with `O(1) lookup` labels
- Caption under panel: `~hundreds of trees × 121 steps, compiled scipy.csgraph`

Both panels share a background box labeled `Graph G = (V, E)` to make explicit that only the query *pattern* changed, not the network.

**Intentionally no "Naïve" label on the diagram** — per session directive, the deck avoids any framing that reads as our-v1 vs our-v2. "Per-agent queries" names the query pattern neutrally.

TikZ style: reuse existing `panelbox`, `transarrow` styles from `final.tex` preamble.

**Bottom band (`\fcolorbox`, blue highlight):**

```
Algorithm 1 recomputation ≈ 87 % of runtime.
Our change speeds up that 87 % by ≈ 230×.
End-to-end: 7.5× single-process. The other 13 % was left untouched.
```

**No code blocks.** Current slide 8's `semiverbatim` naïve/ours code blocks are fully replaced by the mechanism diagram. Current slide 8's complexity table (`O(N)` / `O(K)`) is also removed.

### 4.3 NEW Slide 8 — *Gap B: Running 390 experiments, honestly*

**Frame title:** `Gap B: Running 390 experiments, honestly`

**Layout:** three stacked `\begin{block}` rows, each ≈ 2 cm tall, uniform 3-line format. Bottom `\fcolorbox` single-line callout.

**Block ①: Per-step path recomputation**
```
Paper (Sec. III-C): "pedestrians rely on up-to-date observations"
We chose: recompute every step against current flow state
Because: caching would decouple agents from live congestion — violates the paper's own spec
```

**Block ②: Parallel experiment execution**
```
Paper: reports one-run wall-time (2.5–22 h) — no parallelism described
We chose: 8-worker multiprocessing over seed × config grid; graph built once, shared via fork copy-on-write
Because: 390 runs × 2.5 h sequential = 41 days. Won't happen.
```

**Block ③: Controlled RNG streams**
```
Paper: silent on RNG design
We chose: 3 independent streams (human / hazard / sim); hazard stream fixed within a config across seeds
Because: without separation, varying Pmax also varies hazard placements — can't tell whether ΔRI is from people or hazards
```

**Bottom callout (`\fcolorbox{highlightblue}`, centered, 1 line):**
> Each row is a question the paper does not ask out loud. Answering them is the difference between reproduction at scale and a single run.

### 4.4 NEW Slide 9 — *What this engineering unlocked*

**Frame title:** `What this engineering unlocked`

**Layout:** two columns. Left: existing `assets/benchmark_scaling.pdf` chart. Right: enumerated enable-list.

**Left column (≈0.48\textwidth):**
- `\includegraphics[width=0.95\linewidth]{assets/benchmark_scaling.pdf}`

**Right column (≈0.48\textwidth), heading "What the 3.4 hours bought us":**
- 10 seeds / config (paper: single run per cfg)
- Phase 1: 5 communities validated in parallel
- Ext 1: 17 × 3 Pmax / Hmax grid (paper: 3 × 3)
- Ext 2: 6-point Hmax sweep (paper: 3 values)
- Ext 3: 9-point panic grid (paper: 5 values)
- 3 side-by-side comparison animations (paper: static figures)

**Bottom caption (`\scriptsize\color{gray}`, centered, below both columns):**
> Measured speedup: 7.5× single-process, 60× overall with 8 workers. The number is a means; the end is making 390 runs affordable.

**No alertblock for speedup numbers.** The caption framing intentionally demotes them from headline to footnote.

## 5. Animation resize

Two one-token changes inside `\animategraphics[... width=X ...]`:

| Slide | LaTeX line (approx) | Current `width=` | New `width=` | Rationale |
|---|---|---|---|---|
| 12 (PSU-UP single) | `\animategraphics[…width=\linewidth]` inside `\column{0.52\textwidth}` | `\linewidth` (= 52 % of slide) | `0.9\linewidth` (≈ 47 % of slide) | Current PDF render shows no control bar in this narrow column; shrinking gives the `controls` strip room to render below the frame. |
| 22 (Comparison α) | `\animategraphics[…width=0.95\linewidth]` full-width | `0.95\linewidth` | `0.75\linewidth` | Side-by-side aspect is wide (2:1); 95 % pushes the control bar against page bottom. 75 % leaves clear vertical margin for controls + caption. |
| 23 (Comparison β) | same as 22 | `0.95\linewidth` | `0.75\linewidth` | same |
| 24 (Comparison γ) | same as 22 | `0.95\linewidth` | `0.75\linewidth` | same |

No other animation parameters change (`poster=30`, `controls`, `loop`, `{6}{assets/..}{000}{060}` all preserved). No change to frame PNGs in `assets/frames_*`.

## 6. Content that will be deleted

- Current slide 7 (profiling-only): merged into new slide 7 as top-left band.
- Current slide 8 (Shared shortest-path trees): two `semiverbatim` code blocks, `O(N)` / `O(K)` complexity table, and alertblock with `230×`/`7.5×` are all removed. The 230×/7.5× number moves to the Amdahl `\fcolorbox` on new slide 7.
- Current slide 9 (Per-step + panic noise): "Panicked agents: noisy edge weights" `semiverbatim` block is removed. Panic-noise mention survives as one bullet under new slide 8 block ① (part of "per-step recomputation").
- Current slide 10 (Parallelism + RNG streams): the TikZ 3-stream diagram is removed. Its content condenses into new slide 8 blocks ② and ③.
- Current slide 11 (Measured speedup): `alertblock` titled "Our implementation vs a naïve baseline" is removed. Chart is kept and moves to new slide 9. `60×` and `7.5×` move from alertblock into the small gray caption.

Slide-renumber consequences:
- Current slides 6–11 (6 slides) → new slides 6–9 (4 slides).
- Everything downstream (current 12 → 32) shifts left by 2 to become new 10 → 30 for main + backup stays at the end.
- **Backup counts change**: the "32-page deck" figure quoted in memory (`session_20260423_handoff.md`) becomes a 30-page deck after this edit. Memory will need an update after implementation.
- **Script (`script.tex`) impact**: speaker-note entries for the current slides 6–11 no longer map 1:1. Speaker notes must be rewritten for new slides 6–9 (roughly 4 slide blocks, same condensed style as the rest of the current script). Cross-reference lines elsewhere in the script (e.g. `slide 15`, `slide 14`) must be decremented by 2 where they point to post-engineering slides.

## 7. Content that will be preserved

- Slide 6 block contents (Python 3.7, M1 Pro, runtime) are verbatim from the paper page 379. No paraphrase.
- `assets/benchmark_time_dist.pdf` (profile chart) and `assets/benchmark_scaling.pdf` (scaling chart) are reused as-is.
- `keyterm`, `parambox`, `source`, `panelbox` LaTeX commands are already defined in `final.tex` preamble — reused, not redefined.
- All TikZ-style keys (`statebox`, `transarrow`, `panelbox`, `flowbox`, `flowdiamond`) are reused.
- All animation frame PNGs (`presentation/assets/frames_*`) are reused unchanged; only the `width=` argument of their `\animategraphics` call changes.

## 8. Compile risk + mitigations

Known Beamer / pdflatex failure modes from the existing codebase (per `HANDOFF_2026-04-23.md`):

1. **`semiverbatim` removal** — the old slide 8 uses `[fragile]` because it contains `semiverbatim`. New slide 7 uses TikZ only, so `[fragile]` can be dropped. Leaving `[fragile]` in place is harmless, so on balance we will keep `[fragile]` until the first successful compile passes, then remove in a follow-up edit if desired.
2. **Long `\fcolorbox{...}{...}{\parbox{0.95\linewidth}{...}}` inside narrow column** — a known crash cause. The Slide 6 bottom highlight is placed *outside* any `\begin{columns}` block (it sits after `\end{columns}`, before `\end{frame}`), mirroring the existing safe pattern on current slide 25.
3. **TikZ `align=left` without `text width=...`** — known to crash. The mechanism diagram on new slide 7 will use `text width=...` on every `panelbox` node where text wraps.
4. **Extra `\end{block}`** — must keep block open/close counts matched. Mitigation: compile after each new slide is inserted, before moving on.
5. **Animation `width=` values rounding** — beamer sometimes rounds `0.75\linewidth` oddly at fragile frames. The `comparison α/β/γ` frames are not `[fragile]` in the current source, so no interaction expected.

## 9. Acceptance criteria

Implementation is done when all of the following hold:

1. `cd presentation && pdflatex -halt-on-error final.tex` exits 0 on two consecutive runs.
2. `pdfinfo presentation/final.pdf | grep Pages` reports **30** (down from 32 main+backup; actually 27 main + 5 backup was the old state, so new state is 25 main + 5 backup = 30).
3. `grep -n -i -E 'A\*|A-star|SSSP|dijkstra|heuristic|euclidean|midterm|post-midterm|naïve|naive' presentation/final.tex` returns zero matches. No exceptions: the mechanism-diagram panels are labeled "Per-agent queries" / "Shared destination trees" so "naïve" does not appear anywhere in the deck.
4. Visual inspection (via `Read` tool on `final.pdf`) of the four new engineering slides + the four animation slides (positions given as "new N (was M)"):
   - **New slide 6** (was 6): two-column paper-specifies vs paper-silent layout with the 41-days-vs-3.4-hours highlight box centered at the bottom.
   - **New slide 7** (was 7+8 merged): profile chart top-right, mechanism diagram middle, Amdahl highlight bottom. Zero `semiverbatim` code blocks visible.
   - **New slide 8** (was 9+10 merged): three uniformly-formatted blocks in "Paper … / We chose … / Because …" shape.
   - **New slide 9** (was 11): benchmark chart left + enable-list right. 7.5× / 60× appears only in the small gray caption, never in an alertblock.
   - **New slide 10** (was 12) PSU-UP animation: visually ≈ 47 % of slide width (shrunk from 52 %).
   - **New slides 20, 21, 22** (were 22, 23, 24) comparison animations: visually ≈ 75 % of slide width, with clear vertical margin below the animation frame so `\animategraphics` controls + caption render without clipping.
5. `grep -n "41 days" presentation/final.tex` returns exactly one hit (new slide 6). `grep -n "3.4 hours" presentation/final.tex` returns at least one hit on new slide 6 (may also exist elsewhere in the deck; that's acceptable).
6. `script.tex` is updated so `\slide{6}` through `\slide{9}` entries match the new engineering-section titles and the downstream `\slide{10}` through `\slide{30}` entries are correctly decremented from the old `\slide{12}` through `\slide{32}`. `pdflatex script.tex` compiles exit 0. Speaker notes do not reintroduce any of the banned terms from criterion 3.

## 10. Open questions (resolved)

| # | Question | Resolution |
|---|---|---|
| Q1 | Paper's exact quote on implementation? | Verified page 379: "Within a Python 3.7 simulation environment running on a system with 16 GB of RAM and an Apple M1 Pro chip (8-core CPU, 14-core GPU), increasing 𝒫max from 2,000 to 8,000 extends the duration of a single simulation run from 2.5 hours to 22 hours, while keeping all other control factors constant." |
| Q2 | Include 2.5 h vs 2.8 min vs 22 s comparison? | Yes, per user direction. Expressed as 41 days vs 3.4 hours on the full 390-run scale for clarity. |
| Q3 | Note that Alg. 1 & 2 are decision logic only? | Yes, per user direction. Mentioned as a bullet in Slide 6 paper-specifies block. |
| Q4 | Keep explicit "naïve vs ours" labels in mechanism diagram? | Yes — the labels are diagram axes, not a narrative comparison. Clear from context that "Naïve" is the straightforward first-pass, not our v1. |
| Q5 | Speedup numbers 7.5× / 60× fully banished? | No. 230× and 7.5× appear in the Amdahl highlight on slide 7 (where they explain the mechanism). 7.5× / 60× appear only as gray caption on slide 9 (demoted from headline). Neither is in an alertblock. |
| Q6 | Animation widths? | Slide 10 (ex-12): `0.9\linewidth` inside 52 % column ≈ 47 % of slide. Slides 20–22 (ex-22/23/24): `0.75\linewidth`. |

## 11. Post-implementation follow-ups (out of this spec)

- Update `HANDOFF_2026-04-23.md` with new 30-page layout + renumbered slide map.
- Update `/home/flametom/.claude/projects/-home-flametom-coursework-IE522-PJT/memory/session_20260423_handoff.md` with the new 25-main + 5-backup = 30-page figure.
- Measure actual K (unique destinations per step) and retro-fit it into slide 7's mechanism-diagram caption, if empirical measurement is cheap. Deferred.
- Consider whether current slides 17 ("Gaps with the paper") and 18 ("Three questions") also benefit from the "paper silent → we chose X" framing. Deferred to a possible follow-up feedback round.
