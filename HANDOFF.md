# Project Handoff Document

> **Project:** Multi-agent Evacuation Simulation — Reproduction of Shi et al. (IEEE CASE 2024)
> **Course:** IE 522 Simulation, Penn State University, Spring 2026
> **Team:** Dalal Alboloushi & Jeongwon Bae
> **Last updated:** 2026-04-07

---

## 1. Project Summary

OpenStreetMap 기반 spatial network에서 pedestrian evacuation을 시뮬레이션하는 multi-agent 모델을 구현하고, 원 논문의 실험 결과를 재현한 프로젝트.

**원 논문:** Shi, Lee, Yang — "Multi-agent Modeling of Human Traffic Dynamics for Rapid Response to Public Emergency in Spatial Networks" (IEEE CASE 2024)

---

## 2. Repository Structure

```
IE522_PJT/
├── config.py                  # Table III/IV 파라미터, 실험 설계
├── network_model.py           # OSMnx 기반 spatial network 구축
├── agents.py                  # HumanAgent (6 states) + HazardAgent
├── simulation.py              # Algorithm 1/2, scipy batch SSSP 최적화
├── main.py                    # CLI 진입점 (single run / full factorial / parallel)
├── visualization.py           # Fig. 3–6, timeseries (density KDE, 상태별 마커)
├── run_final_experiment.py    # 최종 실험 스크립트 (390 runs, 8-worker parallel)
├── sweep_hazard_seed.py       # Hazard seed 최적화 (200 seeds × 3 Hmax)
├── network_diagnostics.py     # 네트워크 통계 분석 도구
├── reproduction_report.md     # 상세 재현 보고서
├── results/                   # 실험 결과 (JSON + PNG)
│   ├── final_experiment_PSU-UP.json   # 최종 실험 데이터
│   ├── fig3_network_*.png     # 5개 커뮤니티 네트워크 맵
│   ├── fig4_flow_*.png        # Pedestrian flow 스냅샷
│   ├── fig5_RI_PSU-UP.png     # RI vs Pmax × Hmax
│   ├── fig6_panic_PSU-UP.png  # RS/RC/RL vs εp
│   └── timeseries_*.png       # Agent 상태 시계열
├── presentation/              # 중간 발표 자료 (Beamer + toy simulation)
├── reference/                 # 참고 자료
└── HANDOFF.md                 # 이 문서
```

---

## 3. Commit History

| Commit | 내용 |
|---|---|
| `ddc67f8` | Initial commit: 전체 시뮬레이션 프레임워크 |
| `acf5848` | 네트워크 엣지 분석: uniform config + ADD mode |
| `692a1e9` | 시뮬레이션 엔진 수정: paper-accurate Algorithm 1/2 |
| `6a66fc3` | Pre-emptive edge congestion check 제거 (논문 일치) |
| `82515b9` | Per-step 경로 재계산 구현 |
| `1dc5f75` | Paper-faithful panic model + shelter sensitivity |
| `d3495b0` | 중간 발표 자료 (Beamer 9 slides + toy simulation GIF) |
| `e8cb8ed` | **scipy 최적화 + 병렬화 + 최종 실험 + 시각화 개편** |
| `c7ea929` | Reproduction report 최종 결과 반영 |

---

## 4. Key Design Decisions

### 4.1 Simulation Engine

| 결정 | 선택 | 근거 |
|---|---|---|
| Time step | 1 step = 1 minute | Table III speed 96m/step = 1.6m/s (보행속도) |
| Update model | Simultaneous (buffered) | 논문 Algorithm 1/2 — 순서 의존성 제거 |
| Pathfinding | Per-step 재계산 | 논문: "up-to-date observations" |
| Panic behavior | Random edge at ALL nodes | 논문 Discussion: "persist in following random paths" |
| RNG separation | 3 streams (human/hazard/sim) | Pmax 변경이 hazard config에 영향 안 주도록 |

### 4.2 Network Construction

- **Uniform config:** simplify=True, retain_all=True, network_type="walk" (5개 커뮤니티 동일)
- **Building mode:** ADD (centroid를 별도 노드로 추가, TAG 대비 building count 정확)
- **Shelter:** OSM amenity=shelter 기반 + farthest-first 보충, **62% of buildings** (PSU-UP 기준 sensitivity analysis로 결정)

### 4.3 Experimental Setup

- **Hazard seed:** 1135 (200개 sweep → 논문 RI에 가장 근접, error=0.00193)
- **Agent seeds:** 42, 142, 242, ..., 942 (10개) — hazard 고정, agent behavior만 변동
- **Shelter fraction:** 62% of buildings, 커뮤니티별 비례 적용

---

## 5. Current Results

### Phase 2a: RI vs Pmax × Hmax (εp=10%, 10 seeds)

| | Hmax=5 (paper 34.3%) | Hmax=10 (paper 56.5%) | Hmax=15 (paper 68.4%) |
|---|---|---|---|
| Pmax=2K | **36.3%±1.0%** | **59.2%±0.9%** | **72.1%±1.0%** |
| Pmax=5K | 36.4%±0.5% | 59.3%±0.5% | 72.2%±0.7% |
| Pmax=8K | 36.2%±0.4% | 59.0%±0.5% | 72.0%±0.4% |
| Pmax=20K | 36.3%±0.6% | 59.2%±0.4% | 72.0%±0.3% |
| Pmax=50K | **44.8%±1.1%** | **66.1%±0.3%** | **75.8%±0.3%** |

- **Pmax 2K~20K: RI 완벽 독립** (±0.2%p)
- **Pmax=50K에서 독립성 붕괴** (+8.5%p) — 건물 수용력 초과 효과
- **Hmax 포화:** ~86% at Hmax=30

### Phase 2b: RS/RC/RL vs εp (Pmax=2K, Hmax=5, 10 seeds)

| εp | RS (ours / paper) | RC (ours / paper) | RL (ours / paper) |
|---|---|---|---|
| 10% | 91.8% / 96.6% | **2.2% / 2.5%** | 6.0% / 0.9% |
| 30% | 81.2% / 93.0% | **3.8% / 4.0%** | 15.0% / 3.0% |
| 50% | 73.2% / 88.3% | 4.6% / 7.2% | 22.2% / 4.5% |
| 70% | 67.6% / 78.0% | 5.7% / 10.0% | 26.7% / 12.0% |
| 90% | **62.0% / 64.6%** | 6.1% / 13.3% | 31.9% / 22.1% |

- **모든 정성적 트렌드 일치:** RS↓ RC↑ RL↑
- **RC at εp=10%,30%:** 0.2~0.3%p 이내

### 5개 커뮤니티 네트워크 (Table V)

| Community | B (ours/paper) | Walk Edges (ratio) | Shelters |
|---|---|---|---|
| PSU-UP | **969 / 953** | 21,426 / 19,799 (108%) | 600 |
| UVA-C | **412 / 412** | 11,480 / 7,095 (162%) | 255 |
| VT-B | **448 / 445** | 8,214 / 6,929 (119%) | 277 |
| RA-PA | **473 / 473** | 7,334 / 16,432 (45%) | 292 |
| KOP-PA | **277 / 277** | 4,046 / 17,216 (24%) | 171 |

- Building count: **5개 모두 100-102%**
- RA-PA, KOP-PA 엣지 수 anomaly는 논문의 E/N 비율 이상 (해소 불가)

---

## 6. Unresolvable Gaps

| 차이 | 원인 | 영향 |
|---|---|---|
| RS offset (εp 낮을 때) | Shelter 위치 미공개 | RS 4~15%p 차이 |
| RC ceiling (~6% vs 13%) | Casualty 공식 미명시 | RC 절대값 차이 |
| RL higher than paper | 위 두 가지의 결합 | RL 5~10%p 차이 |
| RA-PA/KOP-PA 엣지 수 | 논문 E/N > 6 (표준 불가) | 해당 커뮤니티 topology 차이 |

---

## 7. Performance

| 항목 | Before | After |
|---|---|---|
| 단일 실행 (Pmax=2K) | 212s | **27s** (7.8x) |
| 단일 실행 (Pmax=8K) | 733s | **37s** (20x) |
| 병렬화 | 직렬 | **8-worker** fork pool |
| 최종 실험 (390 runs) | ~50시간 (추정) | **3.4시간** |

최적화 핵심: networkx A* → **scipy batch SSSP** (per-step, destination 그루핑)

---

## 8. How to Run

```bash
# 단일 실행
python main.py --community PSU-UP --pmax 2000 --hmax 5 --panic 0.10

# Full factorial (병렬)
python main.py --experiment full --nseeds 10 --workers 8

# 최종 실험 (extended Pmax/Hmax/εp)
python run_final_experiment.py

# Hazard seed sweep
python sweep_hazard_seed.py

# 5개 커뮤니티 네트워크 검증
python main.py --experiment networks
```

---

## 9. Extension Candidates (미착수)

### Tier 1: 바로 실행 가능 (1-2일)

| # | 아이디어 | 핵심 질문 |
|---|---|---|
| E1 | **Staged Evacuation** | 동시 대피 vs 구역별 시차 대피 → RS 차이? |
| E2 | **Shelter 배치 전략 비교** | farthest-first vs random vs 인구가중 → RS 차이? |
| E3 | **커뮤니티별 full factorial** | 네트워크 구조 → 대피 성능 영향? |

### Tier 2: 새 모델 추가 (3-5일)

| # | 아이디어 | 핵심 질문 |
|---|---|---|
| E4 | **Panic Intervention** | 패닉 agent X% 진정 시 RS 향상 marginal value? |
| E5 | **Network Vulnerability** | 핵심 도로 차단 시 RS 하락? critical infrastructure? |
| E6 | **Price of Anarchy** | 이기적 경로 vs 중앙 배분 → RS 차이? |
| E7 | **Counter-flow** | 역주행 agent(가족 찾기) 비율 → RS 영향? |

### Tier 3: 학술적 임팩트 (1주+)

| # | 아이디어 | 핵심 질문 |
|---|---|---|
| E8 | **Tipping Point** | εp × Hmax × shelter의 phase transition boundary? |
| E9 | **MDP 패닉** (논문 Future Work) | 상태 전이 확률 기반 패닉 모델? |
| E10 | **Social Force** (논문 Future Work) | 밀도 기반 속도 감소 → 혼잡 현실성? |

### 추천 조합

| 목표 | 조합 | 작업량 |
|---|---|---|
| 최소 노력, 최대 효과 | E1 + E2 | 1-2일 |
| 논문 연장선 | E1 + E4 | 3일 |
| 학술적 차별화 | E1 + E6 | 4-5일 |
| 실용적 완성도 | E1 + E2 + E5 | 4-5일 |

---

## 10. Known Issues / Notes

1. **Pmax=50K 실행 시간:** ~100s/run으로 다른 config 대비 3-4배 느림 (agent 수에 비례하는 iteration 비용)
2. **UVA-C RI=2.9%:** 정상 — 네트워크가 넓어 hazard 커버리지가 작음
3. **Simultaneous update → capacity 초과 가능:** 논문의 의도된 동작. Agent들이 동일 시점 정보로 동시 결정 → 다음 step에서 congestion 해소
4. **OSM 데이터 시점:** 2026-04 기준. 논문(2024)과 OSM 편집 차이로 건물/노드 수 미세 차이 발생
5. **sweep_hazard_seed.py:** 일회성 도구. 결과(seed 1135)는 run_final_experiment.py에 하드코딩됨
