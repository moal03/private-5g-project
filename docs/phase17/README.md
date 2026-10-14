# Phase 17 — ns-3 / 5G-LENA Multi-UE Simulation Campaign

Companion simulation phase to the real testbed Phases 3–16.

## Contents

- `phase-17-report.md` — full phase report (318 lines)
- `../../scripts/phase17/` — all runner, parser, analysis, and plotting scripts
- `../../results/phase17/raw/` — per-study result CSVs (one row per run)
- `../../results/phase17/master_summary.{txt,csv}` — aggregated results
- `../../figures/phase17/` — 10 figures (PDF + PNG)
- `../../patches/phase17/` — source patches to 5G-LENA for testbed matching

## Summary

- **13 studies, 145 runs, 3–5 seeds each**
- **11 studies valid, 2 documented limitations (S6 CA, S12 frequency)**
- Testbed-matched parameters: 3.5 GHz, 20 MHz, 30 kHz SCS, TDD 6DL+4UL
- Scale: 30 – 150 UEs (extends the real testbed's single-UE scope)

## Strongest findings

1. **S13 — TDD pattern:** 8DL+2UL gives 46 ms; 2DL+8UL gives 596 ms.
   12× latency penalty for a mismatched pattern. The single most
   private-5G-specific result of the campaign.

2. **S10 — Numerology:** 15 kHz SCS gives 428 ms; 30/60/120 kHz give
   3.8/1.9/1.1 ms. Confirms the testbed's 30 kHz choice.

3. **S9 — XR overload:** the "heavy" XR config produces zero received
   throughput. Simulation counterpart to the testbed's ~8.6 Mbps ceiling
   (Phase 8).

## Reproducibility

    ./scripts/phase17/run_wave1.sh    # S1–S4
    ./scripts/phase17/run_wave2.sh    # S5–S12
    ./scripts/phase17/run_wave3.sh    # S13
    python3 scripts/phase17/parse_all_studies.py
    python3 scripts/phase17/master_analysis.py
    python3 scripts/phase17/plot_all.py

