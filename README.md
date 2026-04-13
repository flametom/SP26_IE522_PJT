# Multi-Agent Modeling of Human Traffic Dynamics for Rapid Response to Public Emergency in Spatial Networks

**IE 522 — Simulation: Final Project**
**Team Members:** Dalal Alboloushi & Jeongwon Bae
**Penn State University, Spring 2026**

## Overview

This project reproduces and implements the community evacuation simulation model from:

> Shi, Lee, Yang — "Multi-agent Modeling of Human Traffic Dynamics for Rapid Response to Public Emergency in Spatial Networks" (IEEE CASE 2024)

The simulation models pedestrian evacuation behavior during public emergencies using:
- **Community Network Model** — Built from OpenStreetMap data via OSMnx
- **Human Agents** — Pedestrians with six states (Normal, Queuing, Impacted, Arrival, Survival, Casualty)
- **Hazard Agents** — Emergency events with circular impact areas that expand and move over time

## Run Environment

### Requirements

- Python 3.10+
- OS: Linux / macOS / Windows (tested on Ubuntu 22.04 WSL2)

### Installation

```bash
pip install -r requirements.txt
```

Required packages: `osmnx`, `networkx`, `matplotlib`, `numpy`, `scipy`, `tqdm`

### Running the Simulation

**Single run (default: PSU-UP, Pmax=2000, Hmax=5, εp=10%):**
```bash
python main.py
```

**Custom parameters:**
```bash
python main.py --community PSU-UP --pmax 2000 --hmax 5 --panic 0.10
```

**Full factorial experiment (Fig. 5 & 6):**
```bash
python main.py --experiment full --community PSU-UP
```

**All 5 community network verification (Table V, Fig. 3 & 4):**
```bash
python main.py --experiment networks
```

**Complete experiment (networks + full factorial):**
```bash
python main.py --experiment all
```

### Output

Results are saved to the `results/` directory:
- `fig3_network_<community>.png` — Spatial network visualization (Fig. 3)
- `fig4_flow_<community>.png` — Pedestrian flow snapshots (Fig. 4)
- `fig5_RI_<community>.png` — Impacted rate chart (Fig. 5)
- `fig6_panic_<community>.png` — Performance metrics vs. panic rate (Fig. 6)
- `timeseries_<community>.png` — Agent status over time
- `experiment_<community>.json` / `final_experiment_<community>.json` — Numerical results

## Project Structure

| File | Description |
|---|---|
| `config.py` | All simulation parameters (Tables III, IV, Fig. 2) |
| `network_model.py` | Community network from OSMnx (Section III-A) |
| `agents.py` | Human and Hazard agent classes (Sections III-B, III-C) |
| `simulation.py` | Core simulation engine — Algorithms 1 & 2 |
| `visualization.py` | Figure generation (Figs. 3–6) |
| `main.py` | Entry point and experiment runner |
| `requirements.txt` | Python dependencies |

## Key Algorithms

- **Algorithm 1 (Human-Network Interaction):** Models pedestrian movement, congestion, queuing, and route decisions at each time step.
- **Algorithm 2 (Human-Hazard Interaction):** Detects hazard impact on pedestrians, triggers evacuation to shelters, determines casualty and panic states.

## Experimental Design

Three control factors (Fig. 2):
- **Panic Rate (εp):** {10%, 30%, 50%, 70%, 90%}
- **Maximum Pedestrian Flow (Pmax):** {2000, 5000, 8000}
- **Maximum Hazard Occurrences (Hmax):** {5, 10, 15}

Four performance metrics:
- **RI** — Impacted Rate
- **RS** — Survival Rate
- **RC** — Casualty Rate
- **RL** — Leftover Rate

## Communities

| Key | Community |
|---|---|
| PSU-UP | Penn State University, University Park |
| UVA-C | University of Virginia, Charlottesville |
| VT-B | Virginia Tech, Blacksburg |
| RA-PA | Reading, PA |
| KOP-PA | King of Prussia, PA |
