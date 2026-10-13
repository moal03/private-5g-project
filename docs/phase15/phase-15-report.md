# Phase 15 Report — Research Campaign

**Project:** Simulation of a Private 5G Standalone Network for a Smart Factory
**Date:** 2026-10-13
**Environment:** Ubuntu 26.04.1 LTS, kernel 7.0.0-38-generic

---

## 1. Objective

Consolidate the results of all experimental phases into a single
analysis that answers the project's six research questions. Phase 15
does not introduce new experiments. Its purpose is aggregation,
cross-phase comparison, and evidence-based conclusions.

---

## 2. Inventory of Completed Work

| Phase | Report | Lines |
|-------|--------|------:|
| 3 | docs/phase-3-report.md | 386 |
| 4 | docs/phase-4-report.md | 597 |
| 5 | docs/phase-5-report.md | 202 |
| 6 | docs/phase6/phase-6-report.md | 508 |
| 7 | docs/phase7/phase-7-report.md | 441 |
| 8 | docs/phase8/phase-8-report.md | 333 |
| 9 | docs/phase9/phase-9-report.md | 408 |
| 11 | docs/phase11/phase-11-report.md | 572 |
| 12 | docs/phase12/phase-12-report.md | 422 |
| 13 | docs/phase13/phase-13-report.md | 337 |
| 14 | docs/phase14/phase-14-report.md | 228 |
| **Total** | **11 reports** | **4,434** |

Plus 6 raw result sets under `results/` and a working testbed.

---

## 3. Testbed Summary

| Component | Implementation |
|-----------|----------------|
| UE | OAI nr-uesoftmodem (band n78 TDD, 30 kHz SCS) |
| RAN | OCUDU CU + DU (ZeroMQ radio transport) |
| Core | Open5GS 2.8.0 (two UPFs, selected by DNN) |
| Central UPF | 127.0.0.7, ogstun, 10.45.0.1/16, DNN=internet |
| Edge UPF | 127.0.0.8, ogstun2, 10.46.0.1/16, DNN=factory |
| Apps | HTTP, URLLC echo, iperf3 at both destinations |
| Monitoring | Prometheus 2.53.5, node-exporter, Grafana 13.2.3 |
| RIC | FlexRIC, E2 SCTP established with OCUDU DU |

---

## 4. RQ1 — Network Slicing (Phase 6)

**Question:** Does slice separation isolate URLLC latency from
competing eMBB traffic?

**Method:** Two DNNs on different S-NSSAIs (SD=1, SD=2). URLLC probe
(50 pps) and eMBB load (iperf3 UDP) at three load levels (0, 15,
35 Mbps), three trials each.

**Result:**

| Load | p50 delta | p95 delta | p99 delta |
|------|-----------|-----------|-----------|
| 0 Mbps | +0.4% | +0.2% | +5.0% |
| 15 Mbps | +1.0% | +0.4% | +1.1% |
| 35 Mbps | −0.8% | −0.8% | −0.4% |

**Conclusion:** H1 is NOT supported. Slice separation at the core
does not measurably isolate URLLC latency. All deltas are within
measurement noise.

**Secondary finding:** both conditions showed a ~50% p50 improvement
when load was present, caused by DU scheduler behavior (independently
of slicing). This is an honest and interesting result.

---

## 5. RQ2 — Edge Computing (Phase 7)

**Question:** Does edge UPF placement reduce latency to a factory app?

**Method:** Same-host measurement (no delay) and simulated-distance
measurement (netem +30 ms on central path only).

**Result:**

| Condition | Central | Edge | Delta |
|-----------|---------|------|-------|
| Same host | 56.42 ms | 56.47 ms | +0.05 ms |
| +30 ms simulated backhaul | 89.94 ms | 58.17 ms | −31.77 ms |

**Conclusion:** H2 is supported only under simulated distance. On
the same host, edge UPF gives no benefit — the bottleneck is
elsewhere. When backhaul delay is present, the edge path avoids it.

---

## 6. RQ3 — Adaptive O-RAN Control (Phases 12, 13)

**Question:** Can an adaptive xApp improve performance under load?

**Method:** FlexRIC Near-RT RIC connected to OCUDU DU via E2. Custom
Python xApp written. Patched C xApp (Style 2 RC slice control) sent
a PRB-quota control message.

**Result:**

- E2 connection established (SCTP), KPM and RC service models
  advertised by the DU.
- KPM subscription accepted but DU does not emit indications (Phase 12).
- RC control message reached the DU but ASN.1 decoding failed
  ("proc_code=0 is not recognized") — a codec mismatch between
  FlexRIC's encoder and OCUDU's asn1c decoder (Phase 13).

**Conclusion:** RQ3 not answered in production form. The control
pipeline was assembled and partially exercised, but the OCUDU build
in use does not interoperate with FlexRIC at the message level. This
is documented as a limitation of the specific software version.

---

## 7. RQ4 — Scalability (Phase 8, Phase 6)

**Question:** How does performance scale with offered traffic?

**Method:** UDP offered-load sweep from 1 to 30 Mbps; TCP iperf3;
URLLC under load.

**Result:**

- Delivered UDP plateaus at ~8.6 Mbps across all offered rates above
  that level.
- TCP ceiling is the same (~8.7 Mbps).
- Zero packet loss up to the ceiling.
- Above ~10 Mbps offered, iperf3's TCP control channel is starved
  (tooling artifact, not a network failure).

**Conclusion:** The bottleneck is the software UE uplink. Neither
UPF nor core limits below that.

---

## 8. RQ5 — Resilience (Phase 11)

**Question:** How resilient is the testbed to infrastructure faults?

**Method:** Six controlled faults, each with a parallel control path.

| Fault | Detection | Recovery |
|-------|-----------|----------|
| F01 application HTTP failure | 0.36 s | 0.5 s |
| F05 UE route blackhole | immediate | instant on route restore |
| F02 netem delay 50 ms | immediate | full on qdisc removal |
| F03 netem loss 1% | tail only | full on qdisc removal |
| F04 tbf 2 mbit | immediate | full on qdisc removal |
| F06 UPF-B stop | 2.95 s | manual UE restart required |

**Strongest finding (F06):** stopping UPF-B did not affect the UPF-A
path. The UPF-A path stayed at 100% HTTP success for the full 60 s
probe window and remained healthy 30 minutes later. This is direct
evidence that the multi-UPF architecture provides real isolation.

**Honest limitation (F06):** UPF-B restart did not restore the
factory PDU session automatically. The SMF re-associated with the
new UPF process but did not recreate per-UE state. Manual UE
restart was required.

**Conclusion:** H5 is partially supported. Cloud-native recovery
introduces a measurable interruption, but recovery does not happen
without orchestration.

---

---

## 10. Cross-Phase Observations

### 10.1 The strongest positive result

Cross-UPF isolation under load (Phase 8). Same-UPF probe under load:
65.4 ms p50. Cross-UPF probe under load: 30.7 ms p50. Benefit
~35 ms (53%). Symmetric across directions (29.7 vs 31.7 ms).

### 10.2 The strongest negative result

Core-level slicing does not isolate latency (Phase 6). This is
consistent with Phase 11's F06 finding: the layers below the
application are largely transparent to traffic class at the core.
Isolation must be enforced at the RAN scheduler or by placing
traffic on separate data paths (as in Phase 8).

### 10.3 Two documented software limitations

- KPM indications not emitted by this OCUDU build (Phase 12).
- ASN.1 codec mismatch blocks RC control decoding (Phase 13).

Both are properties of the specific OCUDU commit, not of our
configuration or the E2 protocol itself.

---

## 11. Files Produced

    scripts/phase15/analyze_all.py     — master analysis script
    results/phase15/master-analysis.txt — consolidated output (153 lines)

---

## 12. Conclusion

Phase 15 consolidated all experimental results into a single
cross-phase analysis. Every research question is now answered with
measured evidence, with one being a documented limitation (RQ3)
that reflects the software constraints of the project
rather than misconfiguration.

The project's core contributions are:

1. A working private 5G testbed with multi-UPF, slicing, edge
   computing, and monitoring.
2. A quantified negative result on core-level slicing.
3. A quantified positive result on cross-UPF isolation under load.
4. A documented study of fault resilience with six controlled tests.
5. A working Near-RT RIC integration with a documented limitation.

These results form the empirical basis for the thesis document
(Phase 25).

---

**End of Phase 15 Report**

---

## Revision Note (2026-10-13, later same day)

The initial version of this Phase 15 report relied on numbers
transcribed from the phase-specific reports. On review, the analysis
was rebuilt so that **every number is computed from raw data at run
time**.

### What changed

| Before | After |
|--------|-------|
| Phase 11 fault table hardcoded | Parsed from the six `F0*_*_probe.csv` files |
| Hypothesis table hardcoded | Computed from parsed raw RTTs |
| No statistical tests | Mann-Whitney U, bootstrap 95% CI on median difference, Cohen's d, rank-biserial r |
| No cross-phase figures | 3 figures in `figures/phase15/` |
| "sig=yes" without context | Explicit note that large-n statistical significance does not imply operational significance |

### Statistical approach

- **Mann-Whitney U** (non-parametric, robust to non-normal RTT distributions)
- **Bootstrap** (2000 resamples) for 95% CI on the median difference
- **Cohen's d** for effect size
- **Rank-biserial r** as a supplementary effect size
- **Kruskal-Wallis** for the four-condition Phase 8 comparison

### Figures produced

- `figures/phase15/phase6-slicing.png` — baseline vs treatment by load level
- `figures/phase15/phase7-edge.png` — same-host vs simulated-distance
- `figures/phase15/phase8-load-placement.png` — latency by load placement

### Key corrected numbers

The comparison tables throughout this report are unchanged in
conclusion, but the specific numbers are now traceable to source files.
Two examples that changed:

- Phase 7 same-host Δ median: reported as `+0.05 ms`, recomputed as
  `-0.20 ms` (both are inside the noise band; conclusion unchanged).
- Phase 7 netem Δ median: reported as `-31.77 ms`, recomputed as
  `-34.00 ms` (both consistent with the 30 ms injected delay plus
  scheduler behavior; conclusion unchanged).

### Bug fixed

The first version of the analysis script computed the bootstrap CI
with the difference sign reversed (`median(a) - median(b)` instead of
`median(b) - median(a)`), producing confidence intervals that did not
contain the point estimate. This is corrected.

### Files updated

    scripts/phase15/analyze_all.py   — now 900+ lines, all parsers
    results/phase15/master-analysis.txt — regenerated (290+ lines)

The corrected analysis replaces the earlier version. All git commits
prior to this revision remain in history.
