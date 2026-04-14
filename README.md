# Multi-Agent Modeling of Human Traffic Dynamics for Rapid Response to Public Emergency in Spatial Networks

**IE 522 — Simulation: Final Project**
**Team Members:** Dalal Alboloushi & Jeongwon Bae
**Penn State University, Spring 2026**

## Overview

Reproduction and extension of the community evacuation simulation from:

> Shi, Lee, Yang — "Multi-agent Modeling of Human Traffic Dynamics for Rapid Response to Public Emergency in Spatial Networks" (IEEE CASE 2024)

The simulation models pedestrian evacuation during public emergencies using:
- **Community Network Model** — OpenStreetMap spatial network via OSMnx
- **Human Agents** — Pedestrians with six states (Normal, Queuing, Impacted, Arrival, Survival, Casualty)
- **Hazard Agents** — Emergencies with expanding circular impact zones

## Repository Structure

```
IE522_PJT/
├── config.py                  # Table III/IV parameters, experimental design
├── network_model.py           # OSMnx spatial network (Section III-A)
├── agents.py                  # HumanAgent (6 states) + HazardAgent
├── simulation.py              # Algorithm 1/2, scipy batch SSSP optimization
├── main.py                    # CLI entry point (single / factorial / networks)
├── visualization.py           # Fig. 3–6, timeseries
├── run_final_experiment.py    # Phase 2 reproduction (390 runs, 8-worker)
├── run_pmax_extension.py      # Pmax extension — PSU-UP breakpoint analysis
├── run_pmax_multicommunity.py # Pmax extension — 5 community comparison
├── requirements.txt           # Python dependencies
├── reproduction_report.md     # Detailed reproduction report
├── README.md                  # This file
├── results/
│   ├── final_experiment_PSU-UP.json   # Phase 2 reproduction data
│   ├── pmax_extension/                # Pmax extension results
│   │   ├── PSU-UP/                    #   969 buildings, Pmax 2K–97K
│   │   ├── UVA-C/                     #   412 buildings, Pmax 1K–42K
│   │   ├── VT-B/                      #   448 buildings, Pmax 1K–45K
│   │   ├── RA-PA/                     #   473 buildings, Pmax 1K–48K
│   │   └── KOP-PA/                    #   277 buildings, Pmax 1K–28K
│   ├── fig3_network_*.png             # Network maps (5 communities)
│   ├── fig4_flow_*.png                # Pedestrian flow snapshots
│   ├── fig5_RI_PSU-UP.png             # RI vs Pmax × Hmax
│   ├── fig6_panic_PSU-UP.png          # RS/RC/RL vs εp
│   └── timeseries_*.png              # Agent state timeseries
├── presentation/              # Midterm presentation (Beamer + toy sim)
└── reference/                 # Paper, course guides
```

## Quick Start

```bash
pip install -r requirements.txt

# Single run (PSU-UP, Pmax=2000, Hmax=5, εp=10%)
python main.py

# Custom parameters
python main.py --community PSU-UP --pmax 2000 --hmax 5 --panic 0.10

# Full factorial experiment (Fig. 5 & 6)
python main.py --experiment full --community PSU-UP

# 5 community network verification (Table V, Fig. 3 & 4)
python main.py --experiment networks

# Pmax extension — single community
python run_pmax_extension.py --local --workers 8

# Pmax extension — all communities
python run_pmax_multicommunity.py --workers 8
```

## Key Results

### Reproduction (Phase 2, PSU-UP)

| Metric | Our Result | Paper | Difference |
|---|---|---|---|
| RI at Hmax=5 | 36.3%±1.0% | 34.3% | 2.0%p |
| RI at Hmax=10 | 59.2%±0.9% | 56.5% | 2.7%p |
| RI at Hmax=15 | 72.1%±1.0% | 68.4% | 3.7%p |
| RS at εp=90% | 62.0%±1.1% | 64.6% | 2.6%p |
| RC at εp=10% | 2.2%±0.4% | 2.5% | 0.3%p |
| Building counts (5 communities) | 100–102% | — | Excellent |

### Extension: RI~Pmax Independence Breakpoint (5 communities)

| Community | Buildings | Breakpoint (agent/B) | Pattern |
|---|---|---|---|
| PSU-UP | 969 | ~26 | Monotonic rise → 53% saturation |
| UVA-C | 412 | ~10 | Fastest transition, monotonic rise |
| VT-B | 448 | ~20 | U-shape at Hmax=5 (building absorption) |
| RA-PA | 473 | ~30 | Gradual rise |
| KOP-PA | 277 | ~25 | U-shape at Hmax=5, sharp rise at Hmax=10,15 |

## Communities

| Key | Community | Buildings | Shelters (62%) |
|---|---|---|---|
| PSU-UP | Penn State University, University Park | 969 | 600 |
| UVA-C | University of Virginia, Charlottesville | 412 | 255 |
| VT-B | Virginia Tech, Blacksburg | 448 | 277 |
| RA-PA | Reading, PA | 473 | 293 |
| KOP-PA | King of Prussia, PA | 277 | 171 |

## Experimental Design

**Reproduction (Paper Fig. 2):**
- Panic Rate (εp): {10%, 30%, 50%, 70%, 90%}
- Max Pedestrians (Pmax): {2000, 5000, 8000}
- Max Hazards (Hmax): {5, 10, 15}

**Extension:**
- Pmax scaled by agent/building ratio [2, 5, 8, 10, 15, 20, 25, 30, 35, 40, 50, 60, 70, 80, 90, 100]
- Hmax: {5, 10, 15}
- 10 seeds per config, hazard seed 1135 (fixed)
