# Figures Guide

Every figure in this repository, what it shows, and where it fits in
the thesis. All figures are generated from the raw data by
`scripts/thesis/generate_all_figures.py`.

Regenerate all figures:

    python3 scripts/thesis/generate_all_figures.py

---

## Phase 6 — Network Slicing

`figures/phase6/`

| File | Shows | Suggested thesis chapter |
|------|-------|--------------------------|
| `cdf-rtt-load0.png` | Empirical CDF of URLLC RTT at 0 Mbps offered load, baseline vs treatment | Results — RQ1 |
| `cdf-rtt-load15.png` | Same at 15 Mbps load | Results — RQ1 |
| `cdf-rtt-load35.png` | Same at 35 Mbps load | Results — RQ1 |
| `percentile-bars.png` | p50 / p95 / p99 bars for both conditions at three load levels | Results — RQ1 |
| `trial-medians-boxplot.png` | Per-trial median RTT distribution (3 trials per condition) | Results — RQ1 |
| `timeseries-load15-trial1.png` | RTT over time for baseline vs treatment at 15 Mbps | Results — RQ1 |

**Key message:** Slice separation at the core does not measurably
isolate URLLC latency. All differences within measurement noise.

---

## Phase 7 — Multi-UPF and Edge Computing

`figures/phase7/`

| File | Shows | Suggested thesis chapter |
|------|-------|--------------------------|
| `central-vs-edge-bars.png` | Ping average for central and edge UPFs, same-host and +30 ms netem | Results — RQ2 |
| `per-trial-deltas.png` | Edge advantage per trial, both conditions | Results — RQ2 |
| `cdf-all-conditions.png` | CDF overlay of four conditions (central/edge × same-host/netem) | Results — RQ2 |

**Key message:** Edge UPF does not reduce latency on the same host;
under simulated backhaul delay it reduces it by ~32 ms.

---

## Phase 8 — Traffic Engineering

`figures/phase8/`

| File | Shows | Suggested thesis chapter |
|------|-------|--------------------------|
| `offered-vs-delivered.png` | Offered UDP rate vs delivered rate, showing the ~8.6 Mbps plateau | Results — RQ4 |
| `offered-vs-loss.png` | Packet loss vs offered UDP rate | Results — RQ4 |
| `load-placement-bars.png` | Latency under four load-placement conditions | Results — RQ1/RQ2 |
| `cdf-four-conditions.png` | RTT CDF for all four conditions | Results |
| `latency-under-load.png` | p50/p95/p99 by condition | Results |
| `load-sweep-throughput.png` | Load sweep throughput (from earlier phase 8 analysis) | Results — RQ4 |
| `load-sweep-loss.png` | Load sweep loss | Results — RQ4 |
| `rtt-percentiles-idle-vs-crossupf.png` | RTT percentile comparison idle vs cross-UPF | Results |

**Key message:** Placing a probe and load on different UPFs reduces
probe latency by ~35 ms under load. UE uplink ceiling is ~8.6 Mbps.

---

## Phase 10 — Fault Injection

`figures/phase10/`

| File | Shows | Suggested thesis chapter |
|------|-------|--------------------------|
| `detection-latency.png` | Detection latency for each of the six faults | Results — RQ5 |
| `f01-application-timeline.png` | Success/fail timeline for F01 HTTP failure | Results — RQ5 |
| `f06-isolation-proof.png` | F06 UPF-B stop — edge fails, central stays 100% OK | Results — RQ5 |

**Key message:** Faults isolate cleanly to their layer. The multi-UPF
architecture provides real isolation under core-function failure.

---

## Cross-Phase Summary

`figures/cross-phase/`

| File | Shows | Suggested thesis chapter |
|------|-------|--------------------------|
| `hypothesis-status.png` | H1–H5 status at a glance | Discussion |
| `data-volume.png` | Packet/sample counts per phase | Methodology |
| `rq-summary-table.png` | RQ1–RQ5 answers rendered as a table figure | Conclusion |

**Key message:** Quick summary of the project's answer to each
research question.

---

## Phase 14 — Cross-Phase Analysis

`figures/phase14/` — produced by the Phase 14 analysis script.

| File | Shows |
|------|-------|
| `phase6-slicing.png` | Slicing comparison bar chart |
| `phase7-edge.png` | Edge UPF comparison |
| `phase8-load-placement.png` | Load placement comparison |

**Note:** These are the same concepts as the phase-specific
directories above but rendered at a summary level. Either version can
be used in the thesis; the phase-specific ones have more detail.

---

## Reproducing

All figures derive from raw data in `results/`. No figure is hand-drawn
or synthetic. Regenerate at any time with:

    python3 scripts/thesis/generate_all_figures.py

Requires: numpy, matplotlib (available in the base system Python).
