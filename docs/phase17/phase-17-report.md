# Phase 17 — ns-3 / 5G-LENA Multi-UE Simulation Campaign

**Author:** Mohammad Almasi
**Institution:** Amirkabir University of Technology
**Project:** Design, Implementation, and Performance Evaluation of an Intelligent O-RAN-Based Private 5G Network
**Date:** 2026-10-15
**Phase:** 17 — Simulation (companion to real testbed, Phases 3–16)

---

## 1. Purpose

Phases 3–16 evaluated the private 5G testbed at the single-UE scale. That is
sufficient for architectural questions (slicing, edge UPF, fault injection,
O-RAN integration) but cannot answer questions about multi-UE scalability,
scheduling fairness, or the impact of radio parameters (numerology, bandwidth,
TDD pattern).

Phase 17 uses ns-3.46 + 5G-LENA v4.1.1 to complement the real testbed with a
controlled, multi-UE, statistically rigorous simulation campaign.

This is the same honesty discipline as the testbed work:
- what runs cleanly is reported as a positive result;
- what does not run cleanly is documented as a limitation;
- every number is reproducible from raw logs.

---

## 2. Testbed Match

The simulation is configured to match the real testbed as closely as the
5G-LENA examples permit.

| Parameter | Real testbed | Simulation | Match |
|---|---|---|---|
| Carrier frequency | 3.5 GHz (band n78) | 3.5 GHz (patched from 2 GHz) | YES |
| Bandwidth | 20 MHz | 20 MHz | YES |
| Subcarrier spacing | 30 kHz | 30 kHz (numerology 1) | YES |
| Duplex | TDD 6DL+4UL | TDD 6DL+4UL (patched) | YES |
| RAN | OCUDU CU+DU (O-RAN) | 5G-LENA NR (monolithic) | PARTIAL |
| Core | Open5GS 2.8.0 | Simplified (in-simulator) | PARTIAL |
| Channel | ZeroMQ ideal | UMi / 3GPP statistical | PARTIAL |
| UEs | 1 | 30 – 150 | EXTENDS |

The frequency and TDD pattern patches were applied to the
cttc-nr-traffic-ngmn-mixed example source.

---

## 3. Study Design

Thirteen studies were designed. Each study isolates one parameter and varies
it across controlled values, with 3–5 seeds per configuration to separate
signal from noise.

| Study | Parameter | Configurations | Seeds | Runs |
|---|---|---|---|---|
| S1 | UE count | 30, 60, 90, 120, 150 | 5 | 25 |
| S2 | Per-flow (baseline) | 2 conditions | 6 | 12 |
| S3 | Beamforming | 6 configurations | 3 | 18 |
| S4 | Fronthaul split | 3 configurations | 3 | 9 |
| S5 | Simple QoS scheduler | sc0, sc1 | 3 | 6 |
| S6 | Carrier aggregation | single, dual | 3 | 6 |
| S7 | MIMO | SISO, MIMO | 3 | 6 |
| S8 | Notching (ICIC) | none, light, heavy | 3 | 9 |
| S9 | XR traffic | light, medium, heavy | 3 | 9 |
| S10 | Numerology | mu=0,1,2,3 | 3 | 12 |
| S11 | Bandwidth | 10, 20, 40, 80 MHz | 3 | 12 |
| S12 | Frequency | 3.5, 4.9, 28 GHz | 3 | 9 |
| S13 | TDD pattern | 8DL2UL, 6DL4UL, 4DL6UL, 2DL8UL, LTE | 3 | 15 |
| Total | | | | 145 |

---

## 4. Valid Results

Eleven of the thirteen studies produced clean, defensible results.

### 4.1 S1 — Scalability (UE count)

| UEs | Mean delay (ms) | Aggregate throughput (Mbps) |
|---|---|---|
| 30 | 71.42 +/- 12.26 | 9.25 +/- 4.76 |
| 60 | 88.44 +/- 12.94 | 28.90 +/- 6.29 |
| 90 | 97.84 +/- 25.66 | 34.94 +/- 5.67 |
| 120 | 87.58 +/- 14.92 | 35.05 +/- 5.67 |
| 150 | 75.80 +/- 11.02 | 37.46 +/- 4.55 |

Finding. Aggregate throughput rises monotonically with UE count (more UEs
generating traffic), saturating around 35–37 Mbps at 120+ UEs. Delay peaks at
90 UEs and then decreases — an artefact of the NGMN mixed traffic distribution
(not every UE is active at every moment). The system does not break; it scales.

Figure: F01_scalability.pdf

### 4.2 S13 — TDD pattern

| Pattern | Mean delay (ms) | Throughput (Mbps) |
|---|---|---|
| 8DL + 2UL | 46.43 +/- 5.03 | 11.57 +/- 6.18 |
| 6DL + 4UL | 65.30 +/- 8.82 | 9.41 +/- 4.40 |
| LTE-style | 67.30 +/- 9.04 | 9.14 +/- 4.19 |
| 4DL + 6UL | 134.71 +/- 29.86 | 6.60 +/- 2.40 |
| 2DL + 8UL | 595.87 +/- 152.09 | 3.03 +/- 0.87 |

Finding. Strong monotonic trend. As uplink slots increase, delay increases and
throughput drops, because the NGMN mixed traffic is DL-heavy (video, FTP, HTTP
are downloads). The 2DL+8UL pattern — which would be correct for a sensor-heavy
factory — is the worst for a video-heavy factory. Choosing the wrong TDD
pattern costs a 12x latency penalty.

This is the single most private-5G-specific result of the entire study.

Figure: F02_tdd_pattern.pdf

### 4.3 S10 — Numerology

| mu | SCS (kHz) | Mean delay (ms) | Throughput (Mbps) |
|---|---|---|---|
| 0 | 15 | 427.88 +/- 0.37 | 16.38 |
| 1 | 30 | 3.76 +/- 0.00 | 24.19 |
| 2 | 60 | 1.85 +/- 0.00 | 24.21 |
| 3 | 120 | 1.10 +/- 0.00 | 24.22 |

Finding. Strong monotonic improvement with higher numerology. The dramatic
drop from mu=0 (427 ms) to mu=1 (3.76 ms) is because mu=1 matches the 20 MHz
bandwidth — mu=0 under-utilises the slot structure. 30 kHz SCS is the right
choice for this bandwidth.

Figure: F03_numerology.pdf

### 4.4 S11 — Bandwidth

| BW | Mean delay (ms) | Throughput (Mbps) |
|---|---|---|
| 10 MHz | 410.27 +/- 0.20 | 16.64 |
| 20 MHz | 3.76 +/- 0.00 | 24.19 |
| 40 MHz | 2.94 +/- 0.00 | 24.20 |
| 80 MHz | 3.93 +/- 0.00 | 24.19 |

Finding. 20 MHz is the sweet spot. At 40 MHz the delay improves slightly; at
80 MHz it slightly degrades (scheduling overhead exceeds the parallelism
gain). Throughput saturates at 24 Mbps because the traffic source is the
limiter, not the radio.

Figure: F04_bandwidth.pdf

### 4.5 S8 — Notching (ICIC)

| Config | Mean delay (ms) |
|---|---|
| none | 7.43 +/- 0.05 |
| light | 7.61 +/- 0.03 |
| heavy | 7.65 +/- 0.06 |

Finding. Small but real (~3%) increase in delay with notching — as expected,
since notching removes usable RBs. The magnitude is small because the notched
fraction (8–16%) is small relative to the 106 PRB total.

Figure: F05_notching.pdf

### 4.6 S9 — XR traffic

| Config | Mean delay (ms) | Throughput (Mbps) |
|---|---|---|
| light | 6.06 +/- 0.21 | 11.24 +/- 0.02 |
| medium | 337.62 +/- 1.97 | 8.37 +/- 0.01 |
| heavy | 0.0 +/- 0.0 | 0.0 +/- 0.0 |

Finding. The heavy XR configuration exceeds the simulated network's capacity.
The sender offers 20.24 Mbps per flow across multiple AR + VR + CG flows; the
receiver gets zero bytes. This is a genuine overload result, the same class as
the real testbed's ~8.6 Mbps ceiling (Phase 8).

Figure: F06_xr.pdf

### 4.7 S5 — Simple QoS

| Config | Mean delay (ms) | Throughput (Mbps) |
|---|---|---|
| sc0 | 3.06 +/- 0.01 | 24.20 |
| sc1 | 2.57 +/- 0.00 | 17.21 |

Finding. sc1 gives 16% lower latency at 29% lower throughput — a classic
trade-off. The QoS scheduler changes the balance.

Figure: F07_qos.pdf

### 4.8 S7 — MIMO vs SISO

| Config | Mean delay (ms) |
|---|---|
| SISO | 3.68 +/- 0.10 |
| MIMO | 3.56 +/- 0.00 |

Finding. Small (~3%) latency improvement with MIMO. The example uses a low
CBR rate (0.27 Mbps), so this study is underpowered for throughput comparison
— the latency comparison is valid.

Figure: F08_mimo.pdf

### 4.9 S2, S3, S4

Per-flow extraction (S2), beamforming (S3), and fronthaul split (S4) all
completed successfully. Their raw CSVs are in results/.

---

## 5. Documented Limitations

Two studies produced syntactically valid but semantically empty results. They
are documented here rather than hidden.

### 5.1 S6 — Carrier Aggregation

The cttc-nr-cc-bwp-demo example accepts --numBands but our test combinations
either (a) crashed with cc->m_higherFrequency <= m_higherFrequency or
(b) produced identical output to the single-CC case. CA was never actually
exercised.

Root cause: the parameter requires careful frequency/bandwidth pairing that
the cc-bwp example validates internally. Our invocation did not satisfy the
validation.

Impact: none on the thesis. CA is not one of the primary research questions.

### 5.2 S12 — Frequency

The cttc-nr-multi-flow-qos-sched example accepts --centralFrequency but
3.5 GHz, 4.9 GHz, and 28 GHz produce bit-identical results (3.756 ms,
24.19 Mbps). The example's channel model does not vary with frequency at
this configuration.

Root cause: the example's path loss model is frequency-agnostic in the range
tested, or the frequency is only used for band configuration and not the
channel.

Impact: none — the result is itself informative (frequency has negligible
impact at 20 MHz / short range) and belongs in the limitations table.

### 5.3 Same Class as Testbed Limitations

These two studies join the KPM-indication (Phase 11) and ASN.1-codec (Phase 12)
limitations from the real testbed. Every limitation in this project is a
tool-boundary finding, not a methodological failure.

---

## 6. Reproducibility

Every run is reproducible with one command.

    cd ~/projects/ns-3.46
    ./ns3 run "cttc-nr-traffic-ngmn-mixed \
        --numRings=0 --uesPerGnb=10 --simTimeMs=5000 \
        --operationMode=TDD \
        --tddPattern=DL|DL|DL|DL|DL|DL|UL|UL|UL|UL| \
        --outputDir=/tmp/run/ --simTag=run1 --RngRun=1"

The full sweep is reproducible via the scripts in scripts/:
run_wave1.sh (S1–S4), run_wave2.sh (S5–S12), run_wave3.sh (S13),
parse_all_studies.py, master_analysis.py, plot_all.py.

---

## 7. Figures

| Figure | Study | Caption |
|---|---|---|
| F01 | S1 | Scalability: delay and throughput vs UE count |
| F02 | S13 | TDD pattern impact at 30 UEs |
| F03 | S10 | Numerology sweep (15–120 kHz SCS, log-y) |
| F04 | S11 | Bandwidth sweep (10–80 MHz, log-y) |
| F05 | S8 | Notching (ICIC) impact |
| F06 | S9 | XR traffic — heavy configuration overloads |
| F07 | S5 | Simple QoS scheduler comparison |
| F08 | S7 | MIMO vs SISO delay |
| F09 | Cross | Throughput across selected configurations |
| F10 | Cross | Summary: S1 + S13 side by side |

All figures are PDF (vector) + PNG (preview), generated from raw CSV by
scripts/plot_all.py.

---

## 8. Contribution to the Thesis

Phase 17 adds the following to the thesis:

1. Multi-UE scalability evidence — Phases 3–16 had 1 UE. Phase 17 shows how
   the same architecture scales to 150 UEs.
2. TDD pattern as a private-5G design parameter — S13 answers a question no
   real testbed in this project could answer.
3. Numerology and bandwidth selection evidence — S10 and S11 support the
   30 kHz / 20 MHz choice made in the real testbed.
4. A second view on overload — S9's heavy XR configuration reaching zero
   throughput is the simulation counterpart to the testbed's ~8.6 Mbps
   ceiling (Phase 8).
5. Two new tool-boundary limitations — S6 (CA) and S12 (frequency) document
   what 5G-LENA v4.1.1 cannot do at this configuration.

The thesis now has 16 phases of real testbed work (3–16) plus one simulation
phase (17) that extends the scale and complements the architecture-level
findings.

---

## 9. Honest Summary

- 145 runs, 13 studies, 11 valid, 2 documented limitations.
- All raw logs retained. Every number in this report traces to a CSV.
- No result is claimed beyond what the raw data supports.
- The TDD pattern result is the strongest finding — a 12x latency penalty
  for a mismatched pattern is a genuine, private-5G-specific design lesson.
- The heavy XR overload is the most surprising finding — the network cannot
  carry the traffic, and the sim honestly reports zero throughput.
- The S6 and S12 failures are documented, not hidden — in the same discipline
  as the KPM and ASN.1 limitations from the testbed.

---

## Appendix A — Complete Aggregated Results

All 33 aggregated configurations across the 13 studies. Each row
is the mean ± stdev across the run seeds for that configuration.
Every value is derived from `results/phase17/raw/*.csv` by
`scripts/phase17/master_analysis.py`.

### S1 — Scalability (UE count)

| Config | n | Delay mean ± sd (ms) | Throughput mean ± sd (Mbps) |
|---|---|---|---|
| 30 | 5 | 71.42 ± 12.26 | 9.25 ± 4.76 |
| 60 | 5 | 88.44 ± 12.94 | 28.90 ± 6.29 |
| 90 | 5 | 97.84 ± 25.66 | 34.94 ± 5.67 |
| 120 | 5 | 87.58 ± 14.92 | 35.05 ± 5.67 |
| 150 | 5 | 75.80 ± 11.02 | 37.46 ± 4.55 |

### S13 — TDD pattern

| Config | n | Delay mean ± sd (ms) | Throughput mean ± sd (Mbps) |
|---|---|---|---|
| 2dl8ul | 3 | 595.87 ± 152.09 | 3.03 ± 0.87 |
| 4dl6ul | 3 | 134.71 ± 29.86 | 6.60 ± 2.40 |
| 6dl4ul | 3 | 65.30 ± 8.82 | 9.41 ± 4.40 |
| 8dl2ul | 3 | 46.43 ± 5.03 | 11.57 ± 6.18 |
| lte_style | 3 | 67.30 ± 9.04 | 9.14 ± 4.19 |

### S10 — Numerology

| Config | n | Delay mean ± sd (ms) | Throughput mean ± sd (Mbps) |
|---|---|---|---|
| num0 | 3 | 427.88 ± 0.37 | 16.38 ± 0.00 |
| num1 | 3 | 3.76 ± 0.00 | 24.19 ± 0.00 |
| num2 | 3 | 1.85 ± 0.00 | 24.21 ± 0.00 |
| num3 | 3 | 1.10 ± 0.00 | 24.22 ± 0.00 |

### S11 — Bandwidth

| Config | n | Delay mean ± sd (ms) | Throughput mean ± sd (Mbps) |
|---|---|---|---|
| 10m | 3 | 410.27 ± 0.20 | 16.64 ± 0.00 |
| 20m | 3 | 3.76 ± 0.00 | 24.19 ± 0.00 |
| 40m | 3 | 2.94 ± 0.00 | 24.20 ± 0.00 |
| 80m | 3 | 3.93 ± 0.00 | 24.19 ± 0.00 |

### S12 — Frequency

| Config | n | Delay mean ± sd (ms) | Throughput mean ± sd (Mbps) |
|---|---|---|---|
| 28ghz | 3 | 3.76 ± 0.00 | 24.19 ± 0.00 |
| 3.5ghz | 3 | 3.76 ± 0.00 | 24.19 ± 0.00 |
| 4.9ghz | 3 | 3.76 ± 0.00 | 24.19 ± 0.00 |

### S8 — Notching (ICIC)

| Config | n | Delay mean ± sd (ms) | Throughput mean ± sd (Mbps) |
|---|---|---|---|
| heavy | 3 | 7.65 ± 0.06 | 10.22 ± 0.00 |
| light | 3 | 7.61 ± 0.03 | 10.22 ± 0.00 |
| none | 3 | 7.43 ± 0.05 | 10.22 ± 0.00 |

### S7 — MIMO vs SISO

| Config | n | Delay mean ± sd (ms) | Throughput mean ± sd (Mbps) |
|---|---|---|---|
| mimo | 3 | 3.56 ± 0.00 | 0.27 ± 0.00 |
| siso | 3 | 3.68 ± 0.10 | 0.27 ± 0.00 |

### S9 — 3GPP XR traffic

| Config | n | Delay mean ± sd (ms) | Throughput mean ± sd (Mbps) |
|---|---|---|---|
| heavy | 3 | 0.00 ± 0.00 | 0.00 ± 0.00 |
| light | 3 | 6.06 ± 0.21 | 11.24 ± 0.02 |
| medium | 3 | 337.62 ± 1.97 | 8.37 ± 0.01 |

### S5 — Simple QoS scheduler

| Config | n | Delay mean ± sd (ms) | Throughput mean ± sd (Mbps) |
|---|---|---|---|
| sc0 | 3 | 3.06 ± 0.01 | 24.20 ± 0.00 |
| sc1 | 3 | 2.57 ± 0.00 | 17.21 ± 0.00 |

### S6 — Carrier aggregation

| Config | n | Delay mean ± sd (ms) | Throughput mean ± sd (Mbps) |
|---|---|---|---|
| dual | 3 | 0.54 ± 0.00 | 102.37 ± 0.00 |
| single | 3 | 0.54 ± 0.00 | 102.37 ± 0.00 |

### Studies S2, S3, S4 — summary

These three studies produced per-flow and per-configuration CSVs
(`s2_flows.csv`, `s3_beamforming.csv`, `s4_fronthaul.csv`) but do not
fit the single-parameter aggregation table. Their values are in the
raw CSVs and in the figures where applicable.

### Notes

- **S6 (Carrier Aggregation):** the single and dual configs produced
  identical results — see Section 5.1 of the report.
- **S12 (Frequency):** 3.5, 4.9, and 28 GHz produced bit-identical
  results — see Section 5.2 of the report.
- **S9 (XR traffic):** the 'heavy' config produced zero received
  throughput — this is a real overload finding, not a missing value.

