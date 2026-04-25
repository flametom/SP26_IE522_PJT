# Engineering-Section Redesign + Animation Resize — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Current status (2026-04-25):** Implemented, merged into `main`, and pushed to `origin/main`. The current deliverables are `presentation/final.tex`, `presentation/final.pdf` (29 pages, tracked), `presentation/script.tex`, and `presentation/script.pdf` (5 pages, tracked).

**Goal:** Replace the 6-slide engineering section (current deck slides 6–11) of `presentation/final.tex` with a 4-slide redesign ("paper silence → our choice → measured outcome → enabled analysis"), resize the 4 animations on slides 12 and 22–24 so `\animategraphics` controls render without clipping, and resync `presentation/script.tex` speaker notes.

**Architecture:** The work was developed on branch `feature/final-presentation` and is now merged into `main`. Each slide replacement is an `Edit` against `final.tex` anchored by the existing `% SLIDE N:` comment block header. After each slide-level edit we rebuild the PDF with `pdflatex` twice and visually inspect the affected pages with the `Read` tool. Speaker-note update is a full rewrite of `script.tex`.

**Tech Stack:** LaTeX (Beamer class, `animate` package, TikZ), `pdflatex` from TeX Live, bash. No new dependencies.

**Spec reference:** `docs/superpowers/specs/2026-04-23-engineering-section-redesign.md`

---

## File Structure

| File | Responsibility | Change type |
|---|---|---|
| `presentation/final.tex` | Beamer source of the current 29-page final deck. | Modified — slides 6, 7, 8, 9 fully rewritten; `width=` inside `\animategraphics` on slides 12, 22, 23, 24 changed. |
| `presentation/final.pdf` | Compiled final deck, tracked in Git. | Regenerated via `pdflatex`; current artifact is 29 pages. |
| `presentation/script.tex` | Speaker notes for 25 main slides + 4 backup slides. | Modified — engineering notes rewritten and backup numbering resynced. |
| `presentation/script.pdf` | Compiled speaker notes, tracked in Git. | Regenerated; current artifact is 5 pages. |
| `HANDOFF_2026-04-23.md` | Repo-root handoff doc describing deck structure. | Modify — change "32 pages" to "30 pages" and update the slide table. |
| `/home/flametom/.claude/projects/-home-flametom-coursework-IE522-PJT/memory/session_20260423_handoff.md` | Auto-memory session note. | Modify — change page count. |

---

## Phase 0 — Baseline hygiene

### Task 1: Commit prior-session A\* scrub and script rewrite as baseline

The A\*/midterm scrub on `final.tex` (9 edits) and the full rewrite of `script.tex` from earlier in the same session are currently uncommitted. The spec was committed in `bb0c094`, but the artifacts it redesigns have uncommitted prior work. Commit these first so every subsequent task has a clean diff.

**Files:**
- Stage: `presentation/final.tex`
- Stage: `presentation/script.tex`
- Stage: `presentation/script.pdf`

- [ ] **Step 1: Confirm current uncommitted state matches what this plan assumes**

Run:
```bash
cd /home/flametom/coursework/IE522_PJT
git status --short
```

Expected (order may vary, other untracked files may be present — they are NOT in scope):
```
 M presentation/final.tex
 M presentation/script.pdf
 M presentation/script.tex
```

If `final.tex` or `script.tex` is missing from the modified list, STOP. The previous session's edits are either committed already or lost — re-investigate before proceeding.

- [ ] **Step 2: Verify final.tex is grep-clean on banned terms**

Run:
```bash
cd /home/flametom/coursework/IE522_PJT
grep -n -i -E 'A\*|A-star|SSSP|dijkstra|heuristic|euclidean|midterm|post-midterm' presentation/final.tex
```

Expected: no matches (exit 1, zero lines). If any matches appear, STOP and fix before committing.

- [ ] **Step 3: Verify script.tex is grep-clean on banned terms**

Run:
```bash
cd /home/flametom/coursework/IE522_PJT
grep -n -i -E 'A\*|A-star|SSSP|dijkstra|heuristic|euclidean|midterm|post-midterm' presentation/script.tex
```

Expected: no matches. If any appear, STOP and fix.

- [ ] **Step 4: Commit the deck scrub as its own commit**

```bash
cd /home/flametom/coursework/IE522_PJT
git add presentation/final.tex
git commit -m "$(cat <<'EOF'
docs(slides): drop internal-iteration framing from final deck

Removes "presented at midterm" footers (3 Recap slides), scipy-SSSP /
A*-heuristic / batch-Dijkstra jargon from the Summary, Limitations and
References slides, and comment-only A*/SSSP residue. Preserves the
"naïve vs ours" engineering comparison pending the engineering-section
redesign (tracked separately).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 5: Commit the script rewrite as its own commit**

```bash
cd /home/flametom/coursework/IE522_PJT
git add presentation/script.tex presentation/script.pdf
git commit -m "$(cat <<'EOF'
docs(script): full rewrite of speaker notes for 32-slide deck

Resyncs \slide{1}..\slide{32} to current deck frame titles (prior notes
covered only 26 slides and drifted from slide 3 onward). Removes all
A*/SSSP/Dijkstra/midterm vocabulary from presenter-facing text. Frames
narrative as paper vs our implementation throughout.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 6: Verify tree is clean on tracked files in `presentation/`**

```bash
cd /home/flametom/coursework/IE522_PJT
git status --short presentation/
```

Expected: no output (empty). Other untracked/modified files elsewhere in the repo are not this plan's concern.

---

## Phase 1 — Engineering section rewrite (4 slides)

### Task 2: Replace the old "Why speed matters" slide with "What the paper tells us — and what it leaves to us"

**Files:**
- Modify: `presentation/final.tex` (slide block at the `% SLIDE 5: Why speed matters` marker — in the current source this comment is mislabeled but it corresponds to deck slide 6; we replace the full frame)

- [ ] **Step 1: Locate current slide block**

```bash
cd /home/flametom/coursework/IE522_PJT
grep -n "% SLIDE 5: Why speed matters" presentation/final.tex
grep -n "% SLIDE 6: Engineering" presentation/final.tex
```

Expected: one match each. The replacement range is from the first match's line through the line immediately before the second match's line.

- [ ] **Step 2: Replace the full frame with the new Slide 6 content**

Use the `Edit` tool. The `old_string` is the entire current block from `% SLIDE 5: Why speed matters` through the closing `\end{frame}` and blank line before `% SLIDE 6: Engineering ①`. Because the block is long, use a unique anchor — the comment header line and the final `\end{frame}` immediately preceding the next comment.

`old_string` (the current Slide 6 block, exactly as it exists):

```latex
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
\begin{alertblock}{\small A na\"ive approach}
\scriptsize
Per-agent shortest-path query, one call at a time, pure Python.\\[3pt]
1 run $\approx$ 5--15 minutes (measured).\\[3pt]
$\Rightarrow$ 390 runs $\approx$ \textbf{1.5--4 days} of wall time.
\end{alertblock}

\vspace{0.4em}
\begin{block}{\small Our implementation}
\scriptsize
Same Algorithms 1, 2 from the paper.\\
Different \emph{functions} for path computation (slides 7--11).\\[3pt]
1 run $\approx$ 32 seconds.\\[3pt]
390 runs $\approx$ \textbf{3.4 hours} (8 workers).
\end{block}
\end{columns}
\end{frame}

```

`new_string` (the new Slide 6):

```latex
% SLIDE 6: What the paper tells us --- and what it leaves to us
% ============================================================
\begin{frame}[t]{What the paper tells us --- and what it leaves to us}
\footnotesize

\begin{columns}[T,onlytextwidth]
\column{0.48\textwidth}
\begin{block}{\small What the paper specifies}
\scriptsize
\begin{itemize}\itemsep0.25em
  \item Python 3.7 environment
  \item Apple M1 Pro, 16 GB RAM\\
        (8-core CPU, 14-core GPU)
  \item Algorithms 1 \& 2 --- \emph{decision logic only};\\
        path-computation mechanism unspecified
  \item Measured wall-time per run:\\
        $P_{\max} = 2{,}000 \to$ \textbf{2.5 h}\\
        $P_{\max} = 8{,}000 \to$ \textbf{22 h}
\end{itemize}
\end{block}

\column{0.48\textwidth}
\begin{alertblock}{\small What the paper leaves silent}
\scriptsize
\begin{itemize}\itemsep0.25em
  \item Shortest-path library / algorithm
  \item Per-step path policy (recompute? cache?)
  \item Parallel execution strategy\\
        (paper describes ``a single simulation run'')
  \item RNG scheme for controlled experiments
  \item Reproducibility seeding
\end{itemize}
\end{alertblock}
\end{columns}

\vspace{0.6em}
\begin{center}
\fcolorbox{highlightblue}{lightbluefill}{\parbox{0.92\linewidth}{\centering\scriptsize
At the paper's 2.5\,h/run, reproducing our \textbf{390-run experiment} would take $\sim$\,\textbf{41 days} of sequential compute.\\
Our engineered pipeline does it in \textbf{3.4 hours}.\\[2pt]
$\Rightarrow$ The engineering isn't a side achievement --- it's the prerequisite for every chart in the rest of this deck.
}}
\end{center}

\vspace{0.3em}
{\scriptsize\textcolor{gray}{Hardware comparison is indicative --- Apple M1 Pro is a reasonably fast chip; most of the gap is algorithmic, not hardware.}}

\source{Shi et al.\ (2024), p.\ 379}
\end{frame}

```

- [ ] **Step 3: Rebuild PDF**

```bash
cd /home/flametom/coursework/IE522_PJT/presentation
pdflatex -halt-on-error -interaction=nonstopmode final.tex > /tmp/p1.log 2>&1
echo "Exit: $?"
tail -5 /tmp/p1.log
pdflatex -halt-on-error -interaction=nonstopmode final.tex > /tmp/p2.log 2>&1
echo "Exit: $?"
pdfinfo final.pdf | grep Pages
```

Expected: both `Exit: 0`. Page count is still **32** at this point (we've only replaced one slide; the merge happens in the next tasks).

- [ ] **Step 4: Visual inspection of new slide 6**

Use the `Read` tool on `/home/flametom/coursework/IE522_PJT/presentation/final.pdf` with `pages: "6"`. Confirm:
  - Left block titled "What the paper specifies" with 4 bullets
  - Right alertblock titled "What the paper leaves silent" with 5 bullets
  - Blue highlight box at bottom containing "41 days" and "3.4 hours"
  - Gray footer text "Hardware comparison is indicative..."
  - Source line "Shi et al. (2024), p. 379" in bottom right

If layout overflows or elements are missing, shrink spacing (`\vspace{...}` values) or switch the frame to `[t,shrink=5]` and recompile.

- [ ] **Step 5: Commit**

```bash
cd /home/flametom/coursework/IE522_PJT
git add presentation/final.tex
git commit -m "$(cat <<'EOF'
feat(slides): rewrite slide 6 as "What the paper tells us"

Replaces the old "Why speed matters" slide with a paper-silence frame
that cites Shi et al. p. 379 verbatim on Python 3.7, Apple M1 Pro
16 GB RAM, and the Pmax-vs-runtime envelope (2.5 h @ 2K, 22 h @ 8K).
The closing highlight box compares the paper's 41-days-sequential cost
against our 3.4-hour pipeline, grounding the rest of the engineering
section as "prerequisite for every chart" rather than a showcase.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Merge old slides 7 + 8 into new Slide 7 "Gap A: Computing paths, 200K+ times per run"

This task deletes two existing slide frames (current "Engineering ①: Profiling" and "Engineering ②: Shared shortest-path trees") and replaces them with a single new frame containing: profile chart (reused), mechanism TikZ diagram (new, replaces the old `semiverbatim` code blocks and complexity table), and an Amdahl bridge highlight box.

**Files:**
- Modify: `presentation/final.tex` (delete two frame blocks at the `% SLIDE 6:` and `% SLIDE 7:` markers; insert one new frame in their place)

- [ ] **Step 1: Locate the two adjacent slide blocks**

```bash
cd /home/flametom/coursework/IE522_PJT
grep -n "% SLIDE 6: Engineering ① --- Profiling" presentation/final.tex
grep -n "% SLIDE 7: Engineering ② --- Shared shortest-path" presentation/final.tex
grep -n "% SLIDE 8: Engineering ③ --- Per-step recomputation" presentation/final.tex
```

Expected: three unique matches. The replacement range is from the first line of the first match through the line immediately before the third match's line.

- [ ] **Step 2: Read the current content of both slides to confirm exact old_string**

Use the `Read` tool on `presentation/final.tex` with `offset` = line of "% SLIDE 6: Engineering ① --- Profiling" and `limit` appropriate to reach the line just before "% SLIDE 8: Engineering ③".

- [ ] **Step 3: Replace the two-slide block with the new single slide**

Use `Edit`. `old_string` is the exact content between the `% SLIDE 6:` header and the line immediately before `% SLIDE 8:` (which includes both the profile slide AND the shared-trees slide, with their separator comments).

`old_string` — exactly as currently in the file:

```latex
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
Every non-panicked agent triggers its own shortest-path query from its current position, every step, in pure Python.

\vspace{0.5em}
{\scriptsize\textcolor{gray}{Measured on PSU-UP, Pmax=2000, Hmax=5, $\varepsilon_p$=10\%, seed=42.}}
\end{columns}
\end{frame}

% ============================================================
% SLIDE 7: Engineering ② --- Shared shortest-path trees
% ============================================================
\begin{frame}[t,fragile,shrink=8]{Engineering \textcircled{\scriptsize 2}: Shared shortest-path trees}
\footnotesize

\textbf{Na\"ive approach:} each agent independently queries the graph for its own shortest path to destination. With 2{,}000 agents $\times$ 121 steps, that is $\sim$200K shortest-path calls per run.

\vspace{0.3em}
\textbf{Our insight:} many agents share destinations --- the same building, the same shelter. Compute \emph{one} shortest-path \emph{tree} per unique destination; all agents heading there reuse that tree with a constant-time lookup.

\vspace{0.4em}
\begin{columns}[T,onlytextwidth]
\column{0.49\textwidth}
\begin{block}{\scriptsize Na\"ive: one call per agent}
\vspace{-0.3em}
\begin{semiverbatim}\tiny
for p in active_humans:
  path = shortest_path(
      G, p.src, p.dest)
\end{semiverbatim}
\vspace{-0.3em}
$O(N)$ calls per step.
\end{block}

\column{0.49\textwidth}
\begin{block}{\scriptsize Ours: one tree per destination}
\vspace{-0.3em}
\begin{semiverbatim}\tiny
for dest in unique_destinations:
  tree[dest] = shortest_path_tree(G, dest)
# each agent: O(1) lookup in tree[p.dest]
\end{semiverbatim}
\vspace{-0.3em}
$O(K)$ calls per step, $K \ll N$.
\end{block}
\end{columns}

\vspace{0.4em}
\begin{columns}[T,onlytextwidth]
\column{0.55\textwidth}
\begin{center}
{\scriptsize
\begin{tabular}{lcc}
\toprule
& \textbf{Calls / step} & \textbf{Total cost / step} \\
\midrule
Na\"ive per-agent query & $O(N)$ & $O(N \cdot (V{+}E) \log V)$ \\
Our batch trees         & $O(K)$ & $O(K \cdot (V{+}E) + V)$ \\
\bottomrule
\end{tabular}}
\end{center}
{\scriptsize $N$ = active agents; $K$ = unique destinations; $K \ll N$ because many agents share the same building or shelter.}

\column{0.42\textwidth}
\begin{alertblock}{\scriptsize Speedup}
\scriptsize
\textbf{230$\times$} on the path-computation section alone\\
\textbf{7.5$\times$} single-process end-to-end\\
(plus: the batch library is compiled C; the per-agent loop was pure Python)
\end{alertblock}
\end{columns}
\end{frame}

```

`new_string` (new Slide 7 — single merged frame, uses TikZ mechanism diagram, no code blocks):

```latex
% SLIDE 7: Gap A --- Computing paths, 200K+ times per run
% ============================================================
\begin{frame}[t]{Gap A: Computing paths, 200K+ times per run}
\footnotesize

% --- Top band: profile chart + why-this-matters ---
\begin{columns}[T,onlytextwidth]
\column{0.50\textwidth}
\begin{center}
\includegraphics[width=0.92\linewidth]{assets/benchmark_time_dist.pdf}
\end{center}

\column{0.46\textwidth}
\vspace{0.2em}
\textbf{Why this slice matters}
\vspace{0.2em}
\begin{itemize}\itemsep0.15em
  \item Algorithm 1 path recomputation is\\
        $\approx$\,\keyterm{87\% of a single run}
  \item 2{,}000 agents $\times$ 121 steps\\
        $\approx$ \textbf{242K queries / run}
  \item Pure Python + per-agent calls\\
        $\Rightarrow$ paper's reported 2.5--22\,h
  \item Flow bookkeeping, state transitions, hazard checks = other 13\%
\end{itemize}
\end{columns}

\vspace{0.4em}

% --- Middle band: mechanism diagram ---
\begin{center}
\begin{tikzpicture}[>=Stealth, font=\scriptsize, scale=0.88, transform shape]

  % Background graph-G strip
  \node[draw=gray!40, dashed, rounded corners, fill=lightgrayfill,
        minimum width=13cm, minimum height=2.4cm] (bg) at (0, 0) {};
  \node[anchor=north west, font=\tiny, text=gray, inner sep=3pt] at (bg.north west) {Graph $G = (V, E)$};

  % --- Panel A: Per-agent queries (left) ---
  \node[font=\scriptsize\bfseries, text=highlightblue] at (-4.4, 0.95) {Per-agent queries};

  \node[panelbox, fill=lightbluefill, minimum width=0.55cm, minimum height=0.35cm, text width=0.45cm, align=center, inner sep=1pt] (p1) at (-6.2, 0.5) {$p_1$};
  \node[panelbox, fill=lightbluefill, minimum width=0.55cm, minimum height=0.35cm, text width=0.45cm, align=center, inner sep=1pt] (p2) at (-6.2, 0.05) {$p_2$};
  \node[font=\tiny, text=gray] at (-6.2, -0.38) {$\vdots$};
  \node[panelbox, fill=lightbluefill, minimum width=0.55cm, minimum height=0.35cm, text width=0.45cm, align=center, inner sep=1pt] (pn) at (-6.2, -0.8) {$p_N$};

  \node[panelbox, fill=highlightblue!30, minimum width=1.7cm, minimum height=0.4cm, text width=1.6cm, align=center, inner sep=2pt] (G1) at (-3.0, -0.15) {\scriptsize query $G$};

  \draw[->, thick, darkgray] (p1) -- (G1);
  \draw[->, thick, darkgray] (p2) -- (G1);
  \draw[->, thick, darkgray] (pn) -- (G1);

  % --- Panel B: Shared destination trees (right) ---
  \node[font=\scriptsize\bfseries, text=highlightred] at (4.1, 0.95) {Shared destination trees};

  \node[panelbox, fill=lightredfill, minimum width=0.45cm, minimum height=0.35cm, text width=0.35cm, align=center, inner sep=1pt] (d1) at (2.3, 0.55) {$d_1$};
  \node[panelbox, fill=lightredfill, minimum width=0.45cm, minimum height=0.35cm, text width=0.35cm, align=center, inner sep=1pt] (d2) at (3.0, 0.55) {$d_2$};
  \node[panelbox, fill=lightredfill, minimum width=0.45cm, minimum height=0.35cm, text width=0.35cm, align=center, inner sep=1pt] (d3) at (3.7, 0.55) {$d_3$};
  \node[font=\tiny, text=gray] at (4.4, 0.55) {$\cdots$};
  \node[panelbox, fill=lightredfill, minimum width=0.45cm, minimum height=0.35cm, text width=0.35cm, align=center, inner sep=1pt] (dK) at (5.3, 0.55) {$d_K$};

  \node[panelbox, fill=highlightred!15, minimum width=0.45cm, minimum height=0.35cm, text width=0.35cm, align=center, inner sep=1pt] (T1) at (2.3, -0.1) {$T$};
  \node[panelbox, fill=highlightred!15, minimum width=0.45cm, minimum height=0.35cm, text width=0.35cm, align=center, inner sep=1pt] (T2) at (3.0, -0.1) {$T$};
  \node[panelbox, fill=highlightred!15, minimum width=0.45cm, minimum height=0.35cm, text width=0.35cm, align=center, inner sep=1pt] (T3) at (3.7, -0.1) {$T$};
  \node[font=\tiny, text=gray] at (4.4, -0.1) {$\cdots$};
  \node[panelbox, fill=highlightred!15, minimum width=0.45cm, minimum height=0.35cm, text width=0.35cm, align=center, inner sep=1pt] (TK) at (5.3, -0.1) {$T$};

  \draw[->, thin, darkgray] (d1) -- (T1);
  \draw[->, thin, darkgray] (d2) -- (T2);
  \draw[->, thin, darkgray] (d3) -- (T3);
  \draw[->, thin, darkgray] (dK) -- (TK);

  \node[panelbox, fill=lightbluefill, minimum width=3.4cm, minimum height=0.35cm, text width=3.3cm, align=center, font=\tiny, inner sep=1pt] (agents) at (3.8, -0.85) {agents: $O(1)$ lookup in $T(d_{p_i})$};
  \draw[->, thin, darkgray, dotted] (T3) -- (agents);

\end{tikzpicture}
\end{center}

{\scriptsize\textcolor{gray}{Left: 2{,}000 per-agent \texttt{shortest\_path} calls $\times$ 121 steps, pure Python. \hfill Right: $\sim$hundreds of trees $\times$ 121 steps, compiled \texttt{scipy.csgraph}.}}

\vspace{0.4em}

% --- Bottom band: Amdahl bridge ---
\begin{center}
\fcolorbox{highlightblue}{lightbluefill}{\parbox{0.92\linewidth}{\centering\scriptsize
Algorithm 1 recomputation $\approx$ \textbf{87\%} of runtime.
Our change speeds up that 87\% by $\approx$ \textbf{230$\times$}.\\
End-to-end: \textbf{7.5$\times$} single-process. The other 13\% was left untouched.
}}
\end{center}

\end{frame}

```

- [ ] **Step 4: Rebuild PDF**

```bash
cd /home/flametom/coursework/IE522_PJT/presentation
pdflatex -halt-on-error -interaction=nonstopmode final.tex > /tmp/p1.log 2>&1
echo "Exit: $?"
tail -10 /tmp/p1.log
pdflatex -halt-on-error -interaction=nonstopmode final.tex > /tmp/p2.log 2>&1
echo "Exit: $?"
pdfinfo final.pdf | grep Pages
```

Expected: `Exit: 0` on both runs. **Page count is now 31** (was 32; one slide removed as 2 old slides collapsed into 1 new slide).

If pdflatex crashes with a TikZ error, the most likely causes are:
- A `panelbox` node missing `text width=...` → add it.
- A typo in a `\draw` command → re-check the diagram block.

- [ ] **Step 5: Visual inspection of new slide 7**

Use `Read` on `final.pdf` with `pages: "7"`. Confirm:
  - Top-left: profile chart (benchmark_time_dist.pdf)
  - Top-right: "Why this slice matters" block with 4 bullets
  - Middle: mechanism diagram with two labeled panels ("Per-agent queries" in blue on left, "Shared destination trees" in red on right), enclosed by dashed "Graph G = (V, E)" strip
  - Caption line below diagram
  - Bottom: Amdahl highlight box with "87%", "230×", "7.5×", "13%"
  - No `for p in active_humans...` code block visible anywhere
  - No O(N)/O(K) complexity table visible

If any code block or complexity table is still visible, the Edit didn't match correctly — STOP and re-diff.

If the mechanism diagram overflows the dashed strip or panel labels overlap, tune `scale=0.88` down to `0.82` or increase `minimum width` on the background `bg` node.

- [ ] **Step 6: Commit**

```bash
cd /home/flametom/coursework/IE522_PJT
git add presentation/final.tex
git commit -m "$(cat <<'EOF'
feat(slides): merge old slides 7+8 into new "Gap A" slide

Collapses the profile + shared-shortest-path-tree slides into a single
frame that opens with the 87% bottleneck, shows the mechanism visually
(per-agent queries vs shared destination trees, TikZ diagram replacing
the old semiverbatim code blocks), and closes with an Amdahl bridge
(87% × 230x -> 7.5x end-to-end). No "naïve" label remains anywhere in
the deck.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Merge old slides 9 + 10 into new Slide 8 "Gap B: Running 390 experiments, honestly"

This task collapses "Engineering ③: Per-step recomputation & panic noise" and "Engineering ④: Parallelism + RNG streams" into a single slide with 3 uniformly-formatted "Paper … / We chose … / Because …" blocks.

**Files:**
- Modify: `presentation/final.tex`

- [ ] **Step 1: Locate the two adjacent slide blocks**

```bash
cd /home/flametom/coursework/IE522_PJT
grep -n "% SLIDE 8: Engineering ③ --- Per-step recomputation" presentation/final.tex
grep -n "% SLIDE 9: Engineering ④ --- Multiprocessing" presentation/final.tex
grep -n "% SLIDE 10: Engineering ⑤ --- Benchmark results" presentation/final.tex
```

Expected: three unique matches.

- [ ] **Step 2: Replace the two-slide block with the new single slide**

Use `Edit`. `old_string` is the block from `% SLIDE 8: Engineering ③` through the line immediately before `% SLIDE 10: Engineering ⑤`.

`old_string` — exactly as currently in the file:

```latex
% SLIDE 8: Engineering ③ --- Per-step recomputation & panic noise
% ============================================================
\begin{frame}[t,fragile,shrink=5]{Engineering \textcircled{\scriptsize 3}: Per-step recomputation \& panic noise}
\footnotesize

\begin{columns}[T,onlytextwidth]
\column{0.50\textwidth}
\begin{alertblock}{\small Per-step recomputation is kept}
\scriptsize
Paper Section III-C: \emph{``pedestrians rely on up-to-date observations of their immediate surroundings.''}\\[4pt]
We do NOT cache paths across steps.\\
Every non-panicked agent's path is recomputed every step against the \emph{current} flow state.\\[4pt]
This is why the per-step shortest-path cost dominates the profile (slide 7).
\end{alertblock}

\vspace{0.4em}
\begin{block}{\scriptsize Panicked agents: \emph{noisy} edge weights}
\vspace{-0.3em}
\begin{semiverbatim}\tiny
def noisy_weight(u, v, data):
    base = data["length"]
    return base * (1.0 + rng.exponential(1.0))
\end{semiverbatim}
\vspace{-0.3em}
{\scriptsize Models paper's ``limited observations'' --- panicked agents perceive edge lengths with multiplicative random noise, so their path drifts away from the optimum. Their path is computed per-agent (noise is per-agent), so the batch tree doesn't apply here.}
\end{block}

\column{0.46\textwidth}
\begin{block}{\small Edge cases \emph{outside} the batch tree}
\scriptsize
Three situations keep the per-agent query alive, because agents don't share destinations there:
\begin{itemize}\itemsep0.15em
  \item \textbf{Shelter redirect} --- agent just got impacted this step, destination flips from building to nearest shelter
  \item \textbf{Congestion-aware reroute} --- edge cost temporarily inflated for this agent's detour
  \item \textbf{Panicked agents} --- noisy weights above
\end{itemize}
\scriptsize These are a few percent of calls. The remaining $\sim$95\% hit the shared batch tree and get the 7.5$\times$ speedup.
\end{block}
\end{columns}

\vspace{0.4em}
\begin{center}
\fcolorbox{highlightblue}{lightbluefill}{\parbox{0.92\linewidth}{\centering\scriptsize
\textbf{Algorithms 1 and 2 are unchanged from the paper.}
Only the \emph{path-computation function} was swapped.}}
\end{center}
\end{frame}

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

`new_string` (new Slide 8 — single frame, 3 uniform blocks):

```latex
% SLIDE 8: Gap B --- Running 390 experiments, honestly
% ============================================================
\begin{frame}[t]{Gap B: Running 390 experiments, honestly}
\footnotesize

\begin{block}{\scriptsize \textcircled{\scriptsize 1}\ Per-step path recomputation}
\scriptsize
\textbf{Paper (Sec.\ III-C):} ``pedestrians rely on up-to-date observations of their immediate surroundings.''\\
\textbf{We chose:} recompute every step against the current flow state; never cache paths across steps.\\
\textbf{Because:} caching would decouple agents from live congestion --- violates the paper's own spec and breaks the emergent-queueing behavior.
\end{block}

\vspace{0.3em}

\begin{block}{\scriptsize \textcircled{\scriptsize 2}\ Parallel experiment execution}
\scriptsize
\textbf{Paper:} reports single-run wall-time (2.5--22\,h); no parallelism described.\\
\textbf{We chose:} 8-worker \texttt{multiprocessing} over the seed $\times$ config grid; graph built once in the parent, shared via fork copy-on-write.\\
\textbf{Because:} 390 runs $\times$ 2.5\,h sequential $=$ \textbf{41 days}. Won't happen in a semester.
\end{block}

\vspace{0.3em}

\begin{block}{\scriptsize \textcircled{\scriptsize 3}\ Controlled RNG streams}
\scriptsize
\textbf{Paper:} silent on RNG design.\\
\textbf{We chose:} 3 independent streams --- human (\texttt{seed}), hazard (\texttt{seed+1000}), sim (\texttt{seed+2000}); hazard stream fixed within a config across all seeds.\\
\textbf{Because:} without separation, varying $P_{\max}$ also varies hazard placements --- can't tell whether $\Delta RI$ comes from people or from hazards.
\end{block}

\vspace{0.4em}
\begin{center}
\fcolorbox{highlightblue}{lightbluefill}{\parbox{0.92\linewidth}{\centering\scriptsize
Each row is a question the paper does not ask out loud.\\
Answering them is the difference between reproduction at scale and a single run.
}}
\end{center}

\end{frame}

```

- [ ] **Step 3: Rebuild PDF**

```bash
cd /home/flametom/coursework/IE522_PJT/presentation
pdflatex -halt-on-error -interaction=nonstopmode final.tex > /tmp/p1.log 2>&1
echo "Exit: $?"
tail -10 /tmp/p1.log
pdflatex -halt-on-error -interaction=nonstopmode final.tex > /tmp/p2.log 2>&1
echo "Exit: $?"
pdfinfo final.pdf | grep Pages
```

Expected: `Exit: 0` on both. **Page count is now 30** (was 31).

- [ ] **Step 4: Visual inspection of new slide 8**

Use `Read` on `final.pdf` with `pages: "8"`. Confirm:
  - Three stacked blocks, each labeled ①/②/③
  - Each block has 3 bold labels ("Paper ...", "We chose ...", "Because ...") in the same order
  - Blue highlight box at bottom with "Each row is a question..."
  - No TikZ diagram of RNG streams visible (the old 3-stream diagram was removed)
  - No `noisy_weight(u, v, data)` code block visible
  - No `multiprocessing.Pool(8)` reference in a block body (mention in block ② is fine, but no separate alertblock about it)

If any of the old content leaks through, the Edit didn't match — STOP and re-diff.

- [ ] **Step 5: Commit**

```bash
cd /home/flametom/coursework/IE522_PJT
git add presentation/final.tex
git commit -m "$(cat <<'EOF'
feat(slides): merge old slides 9+10 into new "Gap B" slide

Collapses "per-step recomputation + panic noise" and "parallelism + RNG
streams" into a single slide with three uniformly-formatted blocks
("Paper ... / We chose ... / Because ..."). Drops the noisy-weight
semiverbatim block and the 3-stream TikZ diagram in favor of one-line
reasoning per choice. Each block ties back to the paper's silence,
making the engineering look motivated rather than ornamental.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Replace old Slide 11 with new Slide 9 "What this engineering unlocked"

**Files:**
- Modify: `presentation/final.tex`

- [ ] **Step 1: Locate the current slide**

```bash
cd /home/flametom/coursework/IE522_PJT
grep -n "% SLIDE 10: Engineering ⑤ --- Benchmark results" presentation/final.tex
grep -n "% SLIDE 11: E --- Real PSU-UP animation" presentation/final.tex
```

Expected: one match each.

- [ ] **Step 2: Replace the frame**

`old_string`:

```latex
% SLIDE 10: Engineering ⑤ --- Benchmark results
% ============================================================
\begin{frame}[t,shrink=10]{Engineering \textcircled{\scriptsize 5}: Measured speedup}
\footnotesize

\begin{center}
\includegraphics[width=0.80\linewidth]{assets/benchmark_scaling.pdf}
\end{center}

\vspace{0.2em}
\begin{columns}[T,onlytextwidth]
\column{0.48\textwidth}
\begin{alertblock}{\small Our implementation vs a na\"ive baseline}
\scriptsize
\textbf{7.5$\times$} single-process end-to-end\\
\textbf{$\times$ 8 workers $=$ $\sim$60$\times$} overall\\[2pt]
$\Rightarrow$ 390 runs (8-worker parallel): \\ na\"ive $\sim$ 2.3 h $\to$ ours $\sim$ 18 min
\end{alertblock}

\column{0.48\textwidth}
\begin{block}{\small What this speedup enabled}
\scriptsize
\begin{itemize}\itemsep0.05em
  \item 10 seeds / config $\to$ mean $\pm$ SD
  \item Phase 1: 5 community networks
  \item Ext.\ Pmax 2K--97K (17 $\times$ 3 Hmax)
  \item Ext.\ Hmax 5--30 (6 values)
  \item Ext.\ $\varepsilon_p$ 9-point finer grid
\end{itemize}
\end{block}
\end{columns}
\end{frame}

```

`new_string`:

```latex
% SLIDE 9: What this engineering unlocked
% ============================================================
\begin{frame}[t]{What this engineering unlocked}
\footnotesize

\begin{columns}[T,onlytextwidth]
\column{0.50\textwidth}
\begin{center}
\includegraphics[width=0.95\linewidth]{assets/benchmark_scaling.pdf}
\end{center}

\column{0.46\textwidth}
\vspace{0.2em}
\textbf{What the 3.4 hours bought us}
\vspace{0.3em}
\begin{itemize}\itemsep0.3em
  \item \textbf{10 seeds / config}\\
        {\scriptsize (paper: single run per cfg $\to$ mean $\pm$ SD possible)}
  \item \textbf{Phase 1:} 5 communities validated in parallel
  \item \textbf{Ext 1:} 17 $\times$ 3 $P_{\max}$/$H_{\max}$ grid\\
        {\scriptsize (paper: 3 $\times$ 3 configs)}
  \item \textbf{Ext 2:} 6-point $H_{\max}$ sweep\\
        {\scriptsize (paper: 3 values)}
  \item \textbf{Ext 3:} 9-point panic grid\\
        {\scriptsize (paper: 5 values)}
  \item \textbf{3 side-by-side animations}\\
        {\scriptsize (paper: static figures only)}
\end{itemize}
\end{columns}

\vspace{0.5em}
\begin{center}
{\scriptsize\textcolor{gray}{Measured speedup: 7.5$\times$ single-process, 60$\times$ overall with 8 workers. The number is a means; the end is making 390 runs affordable.}}
\end{center}

\end{frame}

```

- [ ] **Step 3: Rebuild PDF**

```bash
cd /home/flametom/coursework/IE522_PJT/presentation
pdflatex -halt-on-error -interaction=nonstopmode final.tex > /tmp/p1.log 2>&1
echo "Exit: $?"
pdflatex -halt-on-error -interaction=nonstopmode final.tex > /tmp/p2.log 2>&1
echo "Exit: $?"
pdfinfo final.pdf | grep Pages
```

Expected: `Exit: 0` on both. **Page count is now 30.**

- [ ] **Step 4: Visual inspection of new slide 9**

Use `Read` on `final.pdf` with `pages: "9"`. Confirm:
  - Left column: benchmark_scaling.pdf chart
  - Right column: "What the 3.4 hours bought us" heading, 6 bullets, each contrasting our extent vs paper's
  - Bottom: small gray caption mentioning 7.5× and 60× — NOT in an alertblock or any colored container
  - No "Our implementation vs a naïve baseline" alertblock visible

- [ ] **Step 5: Commit**

```bash
cd /home/flametom/coursework/IE522_PJT
git add presentation/final.tex
git commit -m "$(cat <<'EOF'
feat(slides): replace "Measured speedup" with "What the engineering unlocked"

Demotes the 7.5x / 60x numbers from a red alertblock to a small gray
caption. Headlines the slide with the six things the 3.4-hour budget
bought us (10 seeds per config, 5-community Phase 1 in parallel, the
17x3 Pmax/Hmax grid, Hmax and panic sweeps finer than the paper's,
three side-by-side animations). The chart is the supporting evidence,
not the feature.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase 2 — Animation resize (4 animations, 2 tasks)

### Task 6: Shrink the PSU-UP single-animation on (new) slide 10 from `\linewidth` to `0.9\linewidth`

After Task 5, the old "Slide 11 PSU-UP animation" is now deck slide 10 (because the engineering section lost 2 slides).

**Files:**
- Modify: `presentation/final.tex` (one `\animategraphics` call)

- [ ] **Step 1: Locate the animation line**

```bash
cd /home/flametom/coursework/IE522_PJT
grep -n "frames_psuup/sim_" presentation/final.tex | grep animategraphics
```

Expected: one match, on a line that reads `\animategraphics[poster=30,controls,loop,width=\linewidth]{6}{assets/frames_psuup/sim_}{000}{060}`.

- [ ] **Step 2: Edit the width value**

`old_string`:
```latex
\animategraphics[poster=30,controls,loop,width=\linewidth]{6}{assets/frames_psuup/sim_}{000}{060}
```

`new_string`:
```latex
\animategraphics[poster=30,controls,loop,width=0.9\linewidth]{6}{assets/frames_psuup/sim_}{000}{060}
```

- [ ] **Step 3: Rebuild PDF**

```bash
cd /home/flametom/coursework/IE522_PJT/presentation
pdflatex -halt-on-error -interaction=nonstopmode final.tex > /tmp/p1.log 2>&1
echo "Exit: $?"
pdflatex -halt-on-error -interaction=nonstopmode final.tex > /tmp/p2.log 2>&1
echo "Exit: $?"
pdfinfo final.pdf | grep Pages
```

Expected: `Exit: 0`. Page count still **30**.

- [ ] **Step 4: Visual inspection**

Use `Read` on `final.pdf` with `pages: "10"`. Confirm:
  - PSU-UP animation poster frame is visibly smaller than the prior 52 %-of-slide size (now ≈ 47 %)
  - The configuration block and legend on the right still fit without clipping
  - There is vertical breathing room below the animation frame where the `\animategraphics` control bar can render in Adobe Reader

- [ ] **Step 5: Commit**

```bash
cd /home/flametom/coursework/IE522_PJT
git add presentation/final.tex
git commit -m "$(cat <<'EOF'
chore(slides): shrink PSU-UP animation to 0.9\\linewidth (47% of slide)

Leaves vertical margin below the animate frame for the \animategraphics
control bar, which was not visible in the previous 52% layout. No
change to the frame content (poster=30, controls, loop preserved).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: Shrink the 3 side-by-side comparison animations (new slides 20, 21, 22) from `0.95\linewidth` to `0.75\linewidth`

**Files:**
- Modify: `presentation/final.tex` (three `\animategraphics` calls)

- [ ] **Step 1: Locate the three animation lines**

```bash
cd /home/flametom/coursework/IE522_PJT
grep -n "frames_cmp_" presentation/final.tex | grep animategraphics
```

Expected: three matches, for `frames_cmp_pmax`, `frames_cmp_panic`, `frames_cmp_hmax`.

- [ ] **Step 2: Edit each width value (three edits)**

Edit 1:

`old_string`:
```latex
\animategraphics[poster=30,controls,loop,width=0.95\linewidth]{6}{assets/frames_cmp_pmax/cmp_}{000}{060}
```

`new_string`:
```latex
\animategraphics[poster=30,controls,loop,width=0.75\linewidth]{6}{assets/frames_cmp_pmax/cmp_}{000}{060}
```

Edit 2:

`old_string`:
```latex
\animategraphics[poster=30,controls,loop,width=0.95\linewidth]{6}{assets/frames_cmp_panic/cmp_}{000}{060}
```

`new_string`:
```latex
\animategraphics[poster=30,controls,loop,width=0.75\linewidth]{6}{assets/frames_cmp_panic/cmp_}{000}{060}
```

Edit 3:

`old_string`:
```latex
\animategraphics[poster=30,controls,loop,width=0.95\linewidth]{6}{assets/frames_cmp_hmax/cmp_}{000}{060}
```

`new_string`:
```latex
\animategraphics[poster=30,controls,loop,width=0.75\linewidth]{6}{assets/frames_cmp_hmax/cmp_}{000}{060}
```

- [ ] **Step 3: Rebuild PDF**

```bash
cd /home/flametom/coursework/IE522_PJT/presentation
pdflatex -halt-on-error -interaction=nonstopmode final.tex > /tmp/p1.log 2>&1
echo "Exit: $?"
pdflatex -halt-on-error -interaction=nonstopmode final.tex > /tmp/p2.log 2>&1
echo "Exit: $?"
pdfinfo final.pdf | grep Pages
```

Expected: `Exit: 0`. Page count still **30**.

- [ ] **Step 4: Visual inspection of the 3 comparison slides**

Use `Read` on `final.pdf` with `pages: "20-22"`. Confirm for each:
  - The side-by-side animation frame is visibly smaller than before (≈ 75 % of slide width)
  - The caption line below the frame has breathing room
  - The `\animategraphics` control bar at the very bottom has clear space above the page margin (not compressed against the 2-of-30 page footer)

- [ ] **Step 5: Commit**

```bash
cd /home/flametom/coursework/IE522_PJT
git add presentation/final.tex
git commit -m "$(cat <<'EOF'
chore(slides): shrink comparison animations (α/β/γ) to 0.75\\linewidth

Before: 0.95\linewidth pressed the \animategraphics control bar against
the page bottom. 0.75\linewidth leaves clear vertical margin for
controls + caption without making the 2:1 side-by-side frames too
small to read.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase 3 — Speaker notes sync

### Task 8: Rewrite `script.tex` for the new 30-slide deck

The engineering section collapsed from 6 slides to 4, so every `\slide{N}` entry from the old slide 10 onward shifts down by 2. Speaker-note bullets for the new engineering slides 6–9 must also be rewritten to match the new content (paper opacity, Gap A, Gap B, unlocked analysis).

**Files:**
- Modify: `presentation/script.tex`

- [ ] **Step 1: Read the current script.tex to confirm starting content**

Use `Read` on `/home/flametom/coursework/IE522_PJT/presentation/script.tex`.

Note the full current structure (approximately 180 lines) — this is the script written in the same session for the 32-slide deck. The rewrite reuses slides 1–5 and 10+ content verbatim where their deck position shifted by 0 or −2.

- [ ] **Step 2: Replace slides 6–11 content (entries `\slide{6}` through `\slide{11}`) with 4 new entries (`\slide{6}` through `\slide{9}`)**

Use `Edit`. Anchor on the header line of slide 6 and the trailing line of slide 11's itemize.

`old_string` (current script.tex, slides 6–11 block — copy exactly from the file as it is right now):

```latex
\slide{6}{Why speed matters}
\begin{itemize}
\item Our full experiment is about 390 runs. A straightforward per-agent shortest-path implementation in Python takes 5--15 minutes per run, which is days of wall time for the whole sweep.
\item Our pipeline runs the same model in about 32 seconds per run, a few hours total with parallel workers. Critically: we did NOT change the algorithms --- only the functions used for path computation.
\end{itemize}

\slide{7}{Engineering 1: Profiling}
\begin{itemize}
\item The bar chart shows where the time goes. Algorithm 1 path recomputation dominates --- over 80\% of runtime.
\item Root cause: every non-panicked agent triggers its own shortest-path query from its current position, every step, in pure Python.
\end{itemize}

\slide{8}{Engineering 2: Shared shortest-path trees}
\begin{itemize}
\item Key insight: many agents share destinations --- the same building, the same shelter. So compute one shortest-path tree per unique destination; each agent then looks up its route in constant time.
\item This converts $O(N)$ calls per step into $O(K)$ with $K \ll N$. Measured: about 230x speedup on the path-computation section alone, 7.5x end-to-end single-process.
\end{itemize}

\slide{9}{Engineering 3: Per-step recomputation \& panic noise}
\begin{itemize}
\item Per-step recomputation is kept, following the paper --- pedestrians act on up-to-date observations, so paths are not cached across steps.
\item A few edge cases stay per-agent: shelter redirects, congestion-aware detours, panicked agents with noisy edge weights. These are only a few percent of calls.
\item The bottom callout is the key message: Algorithms 1 and 2 are unchanged; only the path function was swapped.
\end{itemize}

\slide{10}{Engineering 4: Parallelism + RNG streams}
\begin{itemize}
\item Eight parallel workers across the seed--config grid give an extra 8x throughput. The network is built once and shared to workers via copy-on-write.
\item Separate RNG streams for humans, hazards, and sim dynamics. Without this, changing $P_{\max}$ would also change hazard placements --- we couldn't tell whether a higher $RI$ came from more people or from different hazards.
\end{itemize}

\slide{11}{Engineering 5: Measured speedup}
\begin{itemize}
\item Head-to-head benchmark at the paper's baseline config: 168 seconds per run with per-agent queries, 22 seconds with shared trees. That is 7.5x single-process, about 60x overall with 8 workers.
\item What this speedup enabled: 10 seeds per config, all 5 communities for Phase 1, three full extensions --- without cutting corners.
\end{itemize}
```

`new_string`:

```latex
\slide{6}{What the paper tells us --- and what it leaves to us}
\begin{itemize}
\item What the paper specifies about implementation: Python 3.7, Apple M1 Pro with 16 GB RAM, and measured runtime of 2.5 hours at Pmax=2K and 22 hours at Pmax=8K per single run. Algorithms 1 and 2 are decision logic only --- the paper does not say how paths are actually computed.
\item What the paper leaves silent: shortest-path library, per-step vs cached path policy, parallel execution, RNG design, reproducibility seeding. We had to pick a position on every one.
\item Key takeaway (bottom box): at the paper's 2.5 h/run, our 390-run experiment would take 41 days of sequential compute. Our pipeline does it in 3.4 hours. The engineering is the prerequisite for every chart in the rest of this deck.
\end{itemize}

\slide{7}{Gap A: Computing paths, 200K+ times per run}
\begin{itemize}
\item Algorithm 1 path recomputation is about 87\% of runtime: 2{,}000 agents across 121 steps is roughly 242K shortest-path queries per run. In pure Python per-agent, this is the paper's reported 2.5--22 hours.
\item Our fix: many agents share destinations (same buildings, same shelters), so compute one shortest-path tree per unique destination and let agents do an O(1) lookup. Shown in the mechanism diagram: per-agent queries on the left, shared destination trees on the right.
\item The bottom box is the Amdahl arithmetic: 87\% of runtime sped up by 230x gives 7.5x end-to-end. The other 13\% we left alone.
\end{itemize}

\slide{8}{Gap B: Running 390 experiments, honestly}
\begin{itemize}
\item Three more places the paper is silent, answered with one choice each. Per-step recomputation: the paper says pedestrians act on up-to-date observations, so we never cache paths. Parallel execution: the paper reports a single run, so the 8-worker multiprocessing layer is our addition --- without it, 390 runs at paper pace is 41 days. RNG streams: we split human / hazard / sim into three streams so that varying Pmax does not also vary the hazard scenario.
\item Bottom box: each row is a question the paper does not ask out loud. Answering them is what makes reproduction-at-scale possible rather than a single run.
\end{itemize}

\slide{9}{What this engineering unlocked}
\begin{itemize}
\item 10 seeds per config, all 5 communities validated in parallel, the 17x3 Pmax/Hmax grid for Ext 1, a 6-point Hmax sweep for Ext 2, a 9-point panic grid for Ext 3, three side-by-side comparison animations. Every one of these is finer than what the paper reported.
\item The gray caption at the bottom mentions the raw speedup --- 7.5x single-process, 60x overall --- but only as evidence. The headline is what the 3.4 hours bought us, not the multiplier on a benchmark.
\end{itemize}
```

- [ ] **Step 3: Decrement slide numbers on entries 10 through 32 to become 10 through 30**

Because old slide 12 (PSU-UP animation) is now new slide 10, old slide 13 is now 11, etc. The mapping is `N_new = N_old - 2` for every entry after the engineering section.

Use multiple `Edit` calls. Because each `\slide{N}{title}` line is unique, targeted edits work. Do one pass:

Edit 4:
```
old: \slide{12}{PSU-UP baseline in action}
new: \slide{10}{PSU-UP baseline in action}
```

Edit 5:
```
old: \slide{13}{Phase 1: Network validation}
new: \slide{11}{Phase 1: Network validation}
```

Edit 6:
```
old: \slide{14}{Phase 1: PSU-UP figures}
new: \slide{12}{Phase 1: PSU-UP figures}
```

Edit 7:
```
old: \slide{15}{Phase 2a: $RI$ vs $P_{\max} \times H_{\max}$}
new: \slide{13}{Phase 2a: $RI$ vs $P_{\max} \times H_{\max}$}
```

Edit 8:
```
old: \slide{16}{Phase 2b: $RS / RC / RL$ vs panic}
new: \slide{14}{Phase 2b: $RS / RC / RL$ vs panic}
```

Edit 9:
```
old: \slide{17}{Gaps with the paper}
new: \slide{15}{Gaps with the paper}
```

Edit 10:
```
old: \slide{18}{Three questions we could ask}
new: \slide{16}{Three questions we could ask}
```

Edit 11:
```
old: \slide{19}{Extension 1: $P_{\max}$ breakpoint}
new: \slide{17}{Extension 1: $P_{\max}$ breakpoint}
```

Edit 12:
```
old: \slide{20}{Extension 2: $H_{\max}$ saturation}
new: \slide{18}{Extension 2: $H_{\max}$ saturation}
```

Edit 13:
```
old: \slide{21}{Extension 3: Finer panic grid}
new: \slide{19}{Extension 3: Finer panic grid}
```

Edit 14:
```
old: \slide{22}{Comparison alpha: $P_{\max}$ 2K vs 50K}
new: \slide{20}{Comparison alpha: $P_{\max}$ 2K vs 50K}
```

Edit 15:
```
old: \slide{23}{Comparison beta: panic 10\% vs 90\%}
new: \slide{21}{Comparison beta: panic 10\% vs 90\%}
```

Edit 16:
```
old: \slide{24}{Comparison gamma: $H_{\max}$ 5 vs 30}
new: \slide{22}{Comparison gamma: $H_{\max}$ 5 vs 30}
```

Edit 17:
```
old: \slide{25}{Summary}
new: \slide{23}{Summary}
```

Edit 18:
```
old: \slide{26}{Limitations}
new: \slide{24}{Limitations}
```

Edit 19:
```
old: \slide{27}{References \& acknowledgements}
new: \slide{25}{References \& acknowledgements}
```

Edit 20:
```
old: \slide{28}{Backup: Future work}
new: \slide{26}{Backup: Future work}
```

Edit 21:
```
old: \slide{29}{Backup: $P_{\max}$ breakpoint generalization}
new: \slide{27}{Backup: $P_{\max}$ breakpoint generalization}
```

Edit 22:
```
old: \slide{30}{Backup: Edge count anomaly}
new: \slide{28}{Backup: Edge count anomaly}
```

Edit 23:
```
old: \slide{31}{Backup: Extension candidates considered}
new: removed in the final cleanup pass
```

Edit 24:
```
old: \slide{32}{Backup: Static snapshots}
new: \slide{29}{Backup: Static snapshots}
```

Also update the opening structure line near the top of `script.tex`; final cleanup now uses "Structure: 25 main slides + 4 backup":

Edit 25:
```
old: earlier structure line with 27 main slides and 5 backup slides
new: \noindent\textbf{Structure:} 25 main slides + 4 backup. Framing throughout is paper vs our implementation. No internal-iteration history in what the audience hears.
```

Also remove the two references to earlier-indexed slides that point forward; check for strings like "matching the Phase 2a chart on slide 15" (now slide 13) and "details in backup slide 30" (now slide 28):

Edit 26:
```
old: matching the Phase 2a chart on slide 15.
new: matching the Phase 2a chart on slide 13.
```

Edit 27:
```
old: Treated as a paper data anomaly; details in backup slide 30.
new: Treated as a paper data anomaly; details in backup slide 28.
```

- [ ] **Step 4: Rebuild the script PDF**

```bash
cd /home/flametom/coursework/IE522_PJT
pdflatex -halt-on-error -interaction=nonstopmode \
  -output-directory /home/flametom/coursework/IE522_PJT/presentation \
  /home/flametom/coursework/IE522_PJT/presentation/script.tex > /tmp/s1.log 2>&1
echo "Exit: $?"
pdfinfo presentation/script.pdf | grep Pages
```

Expected: `Exit: 0`, page count approximately **5**.

- [ ] **Step 5: Verify no banned terms slipped in**

```bash
cd /home/flametom/coursework/IE522_PJT
grep -n -i -E 'A\*|A-star|SSSP|dijkstra|heuristic|euclidean|midterm|post-midterm|naïve|naive' presentation/script.tex
```

Expected: no matches.

- [ ] **Step 6: Verify every slide entry references a real deck slide number 1..30**

```bash
cd /home/flametom/coursework/IE522_PJT
grep -oE '\\slide\{[0-9]+\}' presentation/script.tex | sort -t'{' -k2 -n | uniq
```

Expected: one `\slide{N}` each for N = 1, 2, 3, ..., 30. Any gap or duplicate is a bug from the renumbering pass.

- [ ] **Step 7: Commit**

```bash
cd /home/flametom/coursework/IE522_PJT
git add presentation/script.tex presentation/script.pdf
git commit -m "$(cat <<'EOF'
docs(script): resync speaker notes for 30-slide deck

Rewrites \slide{6} through \slide{9} for the new engineering section
(paper opacity, Gap A, Gap B, unlocked analysis) and decrements
\slide{10} through \slide{30} by 2 (was \slide{12} through \slide{32})
to match the now-30-page deck. Forward-pointing references to
slide-15 / slide-30 are likewise updated to slide-13 / slide-28.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase 4 — Final verification and memory sync

### Task 9: Run acceptance criteria + update handoff docs

**Files:**
- Modify: `HANDOFF_2026-04-23.md` (repo root)
- Modify: `/home/flametom/.claude/projects/-home-flametom-coursework-IE522-PJT/memory/session_20260423_handoff.md`

- [ ] **Step 1: Run all grep-based acceptance checks**

```bash
cd /home/flametom/coursework/IE522_PJT
echo "=== grep banned terms in deck (expect empty) ==="
grep -n -i -E 'A\*|A-star|SSSP|dijkstra|heuristic|euclidean|midterm|post-midterm|naïve|naive' presentation/final.tex || echo "(clean)"
echo "=== grep banned terms in script (expect empty) ==="
grep -n -i -E 'A\*|A-star|SSSP|dijkstra|heuristic|euclidean|midterm|post-midterm|naïve|naive' presentation/script.tex || echo "(clean)"
echo "=== 41 days hit count (expect exactly 1) ==="
grep -c "41 days" presentation/final.tex
echo "=== 3.4 hours hit count (expect >=1) ==="
grep -c "3.4 hours" presentation/final.tex
echo "=== pages in deck (expect 30) ==="
pdfinfo presentation/final.pdf | grep Pages
echo "=== pages in script (expect ~5) ==="
pdfinfo presentation/script.pdf | grep Pages
```

All six lines should be as labeled. If any fails, STOP and fix before moving on.

- [ ] **Step 2: Visual sweep of the 4 new engineering slides + 4 animations**

Use `Read` on `final.pdf` with:
- `pages: "6-9"` — the four rewritten engineering slides
- `pages: "10"` — the resized PSU-UP animation
- `pages: "20-22"` — the 3 resized comparison animations

For each page, confirm the acceptance-criterion description from §9 of the spec.

- [ ] **Step 3: Update `HANDOFF_2026-04-23.md`**

The handoff doc currently says "32 pages" and has a slide table with 32 rows. Update both.

Specifically:
- Line 1-ish: change `**Current artifact:** presentation/final.pdf (32 pages, ~93 MB with embedded animation frames)` to `**Current artifact:** presentation/final.pdf (30 pages, ~93 MB with embedded animation frames)`.
- Section 2.4 slide table: rewrite rows for slides 6–11 as the new 6–9, and renumber rows 12→10 through 32→30.

Use `Read` to get the current line numbers, then `Edit` each affected line.

- [ ] **Step 4: Update auto-memory handoff entry**

Edit `/home/flametom/.claude/projects/-home-flametom-coursework-IE522-PJT/memory/session_20260423_handoff.md`:

- Change "Final presentation deck is structurally complete (32 pages = 27 main + 5 backup)" → "Final presentation deck is structurally complete (30 pages = 25 main + 5 backup)".

(Other content in that file remains valid.)

- [ ] **Step 5: Commit the handoff updates**

```bash
cd /home/flametom/coursework/IE522_PJT
git add HANDOFF_2026-04-23.md
git commit -m "$(cat <<'EOF'
docs(handoff): reflect 30-page deck after engineering-section redesign

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

(The memory file lives outside the repo — it is not a git-tracked commit; just save the file.)

- [ ] **Step 6: Final status report**

Print a summary to the user:

```
Engineering-section redesign complete.
  - final.tex:    9 commits, deck now 30 pages (was 32).
  - script.tex:   1 commit, speaker notes resynced.
  - animations:   4 frames resized for control-bar visibility.
  - grep-clean on banned terms in both deck and script.
Ready for visual review.
```

---

## Self-Review Checklist

**Spec coverage:** Each spec section maps to at least one task:
- §4.1 (new slide 6) → Task 2
- §4.2 (new slide 7) → Task 3
- §4.3 (new slide 8) → Task 4
- §4.4 (new slide 9) → Task 5
- §5 (animation resize) → Tasks 6, 7
- §6 (content deleted) → covered by old_string blocks in Tasks 2–5 (deletion is explicit)
- §7 (content preserved) → chart includes are re-used verbatim in Tasks 3, 5; TikZ style keys are reused in Task 3
- §8 (compile risk mitigations) → addressed in Task 3 Step 5 troubleshooting note (TikZ scale reduction) and Task 2 Step 4 (shrink=5 escape hatch)
- §9 (acceptance criteria) → all 6 items covered in Task 9 Step 1 (greps + page counts) and Task 9 Step 2 (visual sweeps)
- §3 in-scope clarification (script.tex) → Task 8 fully covers `script.tex` rewrite + renumbering
- §11 (post-implementation follow-ups) → handoff and memory updates in Task 9; K-measurement is explicitly deferred

**Placeholder scan:** No "TBD", "TODO", "implement later", or vague instructions. Every Step with code shows the exact code. Every `old_string` is the full current content; every `new_string` is the full replacement.

**Type consistency:** The slide content, highlight-box formatting (`\fcolorbox{highlightblue}{lightbluefill}`), and `panelbox` TikZ style key are used consistently across Tasks 2, 3, 4, 5. Commit messages use consistent verb style.

Plan complete.
