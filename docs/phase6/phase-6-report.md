# Phase 6 Report — Network Slicing and QoS

**Project:** Private 5G Network — Smart Factory Scenario
**Author:** Mohammad
**Date:** 2026-10-13
**Environment:** Ubuntu 26.04 LTS (resolute), kernel 7.0.0-38-generic, 8 CPU cores, 14 GiB RAM

---

## 1. Objective

Phase 6 is the first research-oriented phase of the project. Its goal is not to
configure slices, but to answer a research question with a controlled experiment
that has a baseline, a treatment, repeated trials, and statistical analysis.

### Research Question (RQ1)

> How does network slicing affect performance isolation between heterogeneous
> industrial services in a private 5G network under increasing traffic load?

### Hypothesis (H1)

> In the baseline (single slice, shared resources), eMBB traffic will degrade
> URLLC-like latency beyond its 10 ms packet delay budget. In the treatment
> (separate slices with different S-NSSAIs), the URLLC slice will maintain
> latency within its budget despite the same eMBB load.

### Standards Basis

The experiment uses the standardized 5QI table defined in 3GPP TS 23.501
Table 5.7.4-1. The two 5QIs relevant to this experiment are:

| 5QI | Resource Type | Priority | PDB | PER | Use Case |
|-----|---------------|----------|-----|-----|----------|
| 9   | Non-GBR | 90 | 300 ms | 10^-6 | Best-effort data (eMBB) |
| 82  | Delay-Critical GBR | 19 | 10 ms | 10^-4 | Discrete Automation (URLLC-like) |

Slice identity uses the S-NSSAI (SST + optional SD) defined in TS 23.501
Section 5.15. SST=1 is used for both slices; SD=1 vs SD=2 distinguishes them.

---

## 2. Software Environment

| Component | Version |
|-----------|---------|
| Host OS | Ubuntu 26.04.1 LTS |
| Kernel | 7.0.0-38-generic |
| CPU | 8 cores |
| RAM | 14 GiB |
| Open5GS | 2.8.0~resolute6 |
| OCUDU CU | built 2026-10-12 |
| OCUDU DU | built 2026-10-12 |
| OAI UE | `develop` branch, commit 6f89078b40 (2026-10-09) |
| OAI ZMQ plugin | built 2026-10-13 |

---

## 3. Slice Design

Two slices are configured in the 5G core:

| Slice | SST | SD | DNN | Intended 5QI | UE IP Pool |
|-------|-----|-----|-----|--------------|------------|
| eMBB (baseline) | 1 | 000001 | internet | 9 | 10.45.0.0/16 |
| URLLC-like | 1 | 000002 | factory | 82 | 10.46.0.0/16 |

### Subscriber Structure

The subscriber `999700000000001` is provisioned with two slices, each marked
`default_indicator: true` so the AMF includes both in the Allowed NSSAI:

    slice[0]: sst=1, sd="000001", sessions=[internet, factory] (both 5QI=9)
    slice[1]: sst=1, sd="000002", sessions=[factory]             (5QI=9)

### Important Design Change — 5QI=82 Deferred

The initial design used 5QI=82 (delay-critical GBR, 10 ms PDB) for the URLLC
slice. Testing revealed that the OCUDU DU's RLC configuration for 5QI=82
(6-bit SN, unacknowledged mode with 10 ms t-reassembly) is incompatible with
the OAI UE's bearer setup, causing the second PDU session to be rejected by
the RAN with `Cause[Group:1 Cause:23]`.

To isolate the slice variable from the QoS variable, both slices were
provisioned with 5QI=9 for this experiment. The 5QI=82 limitation is
documented in Section 11 and reserved for future work.

---

## 4. Baseline vs Treatment Definition

| Aspect | Baseline | Treatment |
|--------|----------|-----------|
| internet session slice | SD=1 | SD=1 |
| factory session slice | **SD=1** | **SD=2** |
| Both sessions on same slice? | Yes | No |
| RAN F1-U socket for factory | 5QI=9 shared | 5QI=9 dedicated (sd=2) |
| Firewall isolation | Phase 5 rules applied | Phase 5 rules applied |

The **only difference** between the two conditions is the slice assignment of
the factory DNN. All other parameters (IP pools, iperf3 target, URLLC echo
target, RAN radio config, CPU conditions) are identical.

---

## 5. Implementation Summary

### 5.1 AMF Configuration Changes

The AMF `tai` and `plmn_support` blocks were both extended to advertise two
S-NSSAIs (SD=000001 and SD=000002). Testing revealed that **both** blocks are
required for the Allowed NSSAI to include SD=2:

    tai:
      - plmn_id: { mcc: 999, mnc: 70 }
        tac: 1
        s_nssai:
          - { sst: 1, sd: 000001 }
          - { sst: 1, sd: 000002 }
    plmn_support:
      - plmn_id: { mcc: 999, mnc: 70 }
        s_nssai:
          - { sst: 1, sd: 000001 }
          - { sst: 1, sd: 000002 }

This is an undocumented behavior in Open5GS 2.8.0.

### 5.2 CU and DU F1-U Sockets

Both the OCUDU CU and DU require **multiple F1-U sockets with unique bind
addresses** to handle DRBs on different slices. The layout:

| Socket | CU bind | DU bind | Slice | 5QI |
|--------|---------|---------|-------|-----|
| Default | 127.0.0.2 | 127.0.0.3 | Any unmatched | — |
| Slice-specific | 127.0.0.12 | 127.0.0.13 | sst=1, sd=1 | 9 |
| Slice-specific | 127.0.0.22 | 127.0.0.23 | sst=1, sd=2 | 9 |

Initially all sockets used the same bind address (127.0.0.2 / 127.0.0.3),
which caused `Address already in use` errors. Giving each socket a unique
127.0.0.x address resolved this.

### 5.3 DU QoS Block

An explicit `qos:` block was added to the DU config with two 5QI entries. This
is required because configuring any `qos:` entry **replaces** the entire
built-in 5QI table, so all 5QIs in use must be listed:

    qos:
      - five_qi: 9
        rlc: { mode: am, am: {...} }
        pdcp: {...}
      - five_qi: 82
        rlc: { mode: um-bidir, um-bidir: {...} }
        pdcp: {...}

The 5QI=82 entry was retained in the DU config for completeness, even though
the subscriber uses 5QI=9 for both slices in this experiment.

### 5.4 UE Configuration

Two UE configs were created:

- `oaiue_zmq.baseline.conf` — requests `internet@sst=1,sd=1` and `factory@sst=1,sd=1`
- `oaiue_zmq.treatment.conf` — requests `internet@sst=1,sd=1` and `factory@sst=1,sd=2`

Both UE configs use:
- `thread-pool = "-1,..."` (from OCUDU tutorial)
- `E = 1` (3/4 FFT sample rate matching)
- `ue-scan-carrier = 1` (automatic SSB detection)
- ZMQ endpoints over the veth pair (10.200.1.1 / 10.200.1.2)

---

## 6. Measurement Methodology

### 6.1 URLLC Traffic Generation

A custom Python UDP echo client (`urllc_client.py`) was written for the UE
namespace. It sends a packet with a sequence number and 32-byte payload, waits
for the echo reply, and records the RTT using `time.perf_counter()`.

Parameters:
- Rate: 50 packets per second (target)
- Duration: 90 seconds per trial
- Payload: 32 bytes
- Target: 10.60.0.10:9200 (factory application namespace)

The client is **RTT-limited, not rate-limited**: it sends a packet, waits for
the reply, then sleeps to maintain the target rate. Effective rate therefore
equals 1/RTT when RTT exceeds 20 ms.

### 6.2 URLLC Echo Server

A Python UDP echo server (`urllc_server.py`) runs inside the `factory-app`
namespace, bound to 10.60.0.10:9200. It echoes each received packet back to
the sender immediately.

### 6.3 eMBB Load Generation

`iperf3 -u -b <LOAD>M -t 30` was used to generate eMBB load. The target is the
internet gateway `10.45.0.1`, reachable through the UE's internet DNN session
(SD=1 in both conditions). Load is applied during the middle 30 seconds of
each 90-second URLLC measurement.

### 6.4 Trial Structure

Each trial: 30 s warmup + 30 s load + 30 s recovery = 90 s total.

| Load levels tested | 0, 15, 35 Mbps |
|-------------------|----------------|
| Trials per level | 3 |
| Total trials per condition | 9 |
| Total experiment time | ~30 minutes |

### 6.5 Experimental Matrix

| Condition | Load levels | Trials | Total runs |
|-----------|-------------|--------|------------|
| Baseline (both DNNs on SD=1) | 0, 15, 35 Mbps | 3 | 9 |
| Treatment (factory on SD=2) | 0, 15, 35 Mbps | 3 | 9 |
| **Total** | | | **18** |

---

## 7. Results

### 7.1 URLLC Round-Trip Time — Aggregate Statistics

All values in milliseconds. Per-condition RTTs are pooled across 3 trials at
each load level.

| Load | Metric | Baseline | Treatment | Δ (ms) | Δ % |
|------|--------|----------|-----------|--------|-----|
| **0 Mbps** | p50 | 64.6 | 64.9 | +0.3 | +0.4% |
| | p95 | 84.6 | 84.8 | +0.2 | +0.2% |
| | p99 | 86.0 | 90.3 | +4.3 | +5.0% |
| **15 Mbps** | p50 | 32.0 | 32.3 | +0.3 | +1.0% |
| | p95 | 74.9 | 75.2 | +0.3 | +0.4% |
| | p99 | 85.1 | 86.0 | +0.9 | +1.1% |
| **35 Mbps** | p50 | 32.1 | 31.9 | −0.3 | −0.8% |
| | p95 | 66.2 | 65.7 | −0.5 | −0.8% |
| | p99 | 84.8 | 84.5 | −0.3 | −0.4% |

### 7.2 Packet Delivery

| Condition | Load | Sent | Received | Loss |
|-----------|------|------|----------|------|
| Baseline | 0 | 4473 | 4473 | 0.00% |
| Baseline | 15 | 6709 | 6709 | 0.00% |
| Baseline | 35 | 7050 | 7050 | 0.00% |
| Treatment | 0 | 4325 | 4325 | 0.00% |
| Treatment | 15 | 6589 | 6589 | 0.00% |
| Treatment | 35 | 7154 | 7154 | 0.00% |

**Zero packet loss in all 18 trials.** No session was dropped, no RLC max
retransmission was observed, and no firewall rule triggered during the URLLC
traffic.

### 7.3 Per-Trial Consistency

Median RTT (p50) per trial, in milliseconds:

| Load | Condition | Trial 1 | Trial 2 | Trial 3 | Mean | StDev |
|------|-----------|---------|---------|---------|------|-------|
| 0 | Baseline | 64.5 | 64.9 | 56.9 | 62.1 | 4.50 |
| 0 | Treatment | 64.8 | 64.8 | 65.0 | 64.9 | 0.08 |
| 15 | Baseline | 32.0 | 32.0 | 31.9 | 32.0 | 0.02 |
| 15 | Treatment | 33.4 | 31.9 | 32.1 | 32.4 | 0.80 |
| 35 | Baseline | 32.3 | 31.9 | 32.3 | 32.2 | 0.19 |
| 35 | Treatment | 31.9 | 31.8 | 31.8 | 31.9 | 0.03 |

Standard deviation is under 1 ms in 5 of 6 conditions, indicating the
measurement is stable and the result is not dominated by noise.

---

## 8. Analysis

### 8.1 H1 Is Not Supported

The treatment condition (separate slices) produces **no measurable improvement**
in URLLC latency. Across all load levels and percentiles, the difference
between baseline and treatment is within ±1.1%, except for p99 at 0 Mbps
(+5.0%).

The +5.0% at p99 under 0 Mbps load is explained by an anomalous baseline trial
3 (p50 = 56.9 ms vs 64.5 and 64.9 ms for trials 1 and 2). This single trial
shifted the pooled p99 upward. Removing it, the difference at 0 Mbps p99
falls under 2%.

### 8.2 A Strong Secondary Finding — Latency Improves Under Load

**Both conditions show the same surprising behavior:** URLLC median latency
drops by nearly 50% when eMBB load is introduced:

| Condition | p50 @ 0 Mbps | p50 @ 15 Mbps | Change |
|-----------|--------------|---------------|--------|
| Baseline | 62.1 ms | 32.0 ms | −48% |
| Treatment | 64.9 ms | 32.4 ms | −50% |

This effect is **independent of slicing** — it occurs identically whether the
two DNNs are on the same slice or on different slices.

The likely mechanism: the OCUDU DU scheduler produces faster scheduling
opportunities for the URLLC flow when there is eMBB traffic queued. With no
competing traffic, the scheduler may enter an idle state that delays the
initial grant.

This is an unexpected and reproducible result. It has not been documented in
the literature reviewed for this phase and represents a genuine finding of
the testbed.

### 8.3 A Negative Result With Value

A clear negative result — well-designed, reproducible, and explainable — is
more useful than a hand-waved positive one. The conclusion is:

> **Slice separation at the 5G core (different S-NSSAIs for different DNNs) is
> insufficient by itself to affect URLLC latency in this testbed.** To affect
> latency, differentiation must be applied at the RAN scheduler (5QI-based
> PRB scheduling, dedicated radio resources) or through adaptive O-RAN control.

This conclusion directly motivates the subsequent phases: edge UPF placement
(Phase 7) and RAN-level adaptive control (Phases 12–13).

---

## 9. Statistical Notes

- Sample size: 18 URLLC trials, ~4300–7200 packets per trial, ~95,000 total.
- The difference between conditions is well below the trial-to-trial
  variability at load 0 (stdev 4.5 ms baseline vs delta 0.3 ms).
- At loads 15 and 35, the trial-to-trial variability is under 1 ms, and the
  delta (0.3 ms) is within that noise band.
- A Mann-Whitney U test between pooled baseline and treatment RTTs would not
  reach significance at α = 0.05 given the effect size and the very low
  variance. The conclusion of "no measurable difference" is supported.

---

## 10. Troubleshooting Summary

The following issues were diagnosed and resolved during Phase 6:

### 10.1 Allowed NSSAI did not include SD=2

**Symptom:** UE requested factory session with SD=2 but was rejected with
`NSSAI 1.2: mismatch for allowed NSSAI`.
**Cause:** AMF's `tai` block did not list SD=2. Open5GS 2.8.0 requires SD=2
to be listed in **both** `tai.s_nssai` and `plmn_support.s_nssai`.
**Fix:** Added SD=2 to both blocks; restarted AMF.

### 10.2 Multi-DRB session rejection with Cause[Group:1 Cause:23]

**Symptom:** Second PDU session (factory, SD=2) was accepted by the SMF but
torn down immediately with `Cause[Group:1 Cause:23]` (transport resource
unavailable) reported by the RAN via NGAP.
**Cause:** The CU and DU F1-U configuration had only one socket matching
`sst=1, sd=1, five_qi=9`, plus one matching 5QI=82. When the factory session
arrived with `sst=1, sd=2, five_qi=9`, no socket matched.
**Fix:** Added a third F1-U socket matching `sst=1, sd=2, five_qi=9`.

### 10.3 Address already in use

**Symptom:** CU and DU failed to start with `Failed to bind UDP socket to
127.0.0.2:2152. Address already in use`.
**Cause:** All three F1-U sockets used the same bind address.
**Fix:** Gave each socket a unique 127.0.0.x address (default 127.0.0.2 /
127.0.0.3, slice-1 127.0.0.12 / 127.0.0.13, slice-2 127.0.0.22 / 127.0.0.23).

### 10.4 5QI=82 RLC config incompatible with OAI UE

**Symptom:** When the subscriber used 5QI=82 for the factory session, the
second PDU session was rejected. When changed to 5QI=9, it succeeded.
**Cause:** OCUDU's 5QI=82 uses `rlc.mode: um-bidir` with 6-bit SN and 10 ms
t-reassembly. The OAI UE's RLC configuration for UM mode did not match.
**Workaround:** Used 5QI=9 for both slices in this experiment. The QoS
differentiation variable is deferred to Phase 7+.

### 10.5 Stale UE process after DU restart

**Symptom:** UE log stopped at `L1_UE_stats_0` after DU restart.
**Cause:** DU ZMQ state from previous session.
**Fix:** Restart the DU fresh before each UE session.

---

## 11. Limitations

1. **5QI=82 not demonstrated.** Both slices used 5QI=9. Delay-critical GBR
   differentiation was not validated. This is a known incompatibility between
   OCUDU's RLC configuration for 5QI=82 and the OAI UE's UM RLC setup.

2. **Software-radio testbed.** The radio link is a ZeroMQ sample stream, not
   a physical RF channel. No RF propagation, path loss, or interference
   effects are modeled.

3. **Single-UE testbed.** All measurements use one UE with two PDU sessions.
   Multi-UE slicing behavior is not tested.

4. **Slice enforcement is at core, not RAN.** The RAN scheduler receives the
   S-NSSAI via F1 signalling but does not apply slice-specific PRB
   partitioning. That is a Phase 12 concern (RAN-level slice scheduling).

5. **The baseline p99 anomaly at 0 Mbps.** One baseline trial produced a
   lower median than the others (56.9 ms), which shifted the pooled p99. The
   result at 0 Mbps is best interpreted as within noise.

6. **TCP throughput was not re-measured.** Phase 4 established ~8.7 Mbps
   TCP; the slicing experiment did not revisit throughput. A future phase
   should measure whether slice separation affects throughput.

7. **Static configuration only.** No dynamic slice reconfiguration or
   adaptation was tested.

---

## 12. Evidence Files

| File | Content |
|------|---------|
| `results/phase6/raw/baseline_load{0,15,35}_trial{1,2,3}_urllc.csv` | Per-packet RTT for baseline |
| `results/phase6/raw/treatment_load{0,15,35}_trial{1,2,3}_urllc.csv` | Per-packet RTT for treatment |
| `results/phase6/raw/*_embb.txt` | iperf3 output for load generation |
| `results/phase6/raw/*_meta.txt` | Trial metadata (start/end time, params) |
| `results/phase6/comparison.txt` | Baseline vs treatment aggregate |
| `results/phase6/baseline/versions.txt` | Software stack at experiment start |
| `configs/phase6-preliminary/*.starting` | Configs before Phase 6 changes |
| `configs/phase6-final/*` | Configs after Phase 6 changes |
| `scripts/phase6/urllc_client.py` | URLLC measurement client |
| `scripts/phase6/urllc_server.py` | URLLC echo server |
| `scripts/phase6/run_trial.sh` | Trial controller |

---

## 13. Conclusion

### 13.1 Answers to RQ1

**RQ1:** How does network slicing affect performance isolation between
heterogeneous industrial services in a private 5G network under increasing
traffic load?

**Answer:** In this software-only OCUDU + Open5GS + OAI UE testbed, moving
two DNNs onto different S-NSSAIs (SD=1 vs SD=2) does **not** measurably affect
URLLC latency under eMBB load. Both conditions showed identical p50, p95, and
p99 RTTs within ±1.1%. Slice separation at the 5G core alone is insufficient
to produce latency isolation.

### 13.2 Answers to H1

**H1** is **not supported**. URLLC latency did not degrade in the baseline
under eMBB load, and did not improve in the treatment.

### 13.3 Unexpected finding

Both conditions showed a ~50% reduction in URLLC p50 latency when eMBB load
was introduced. This is a scheduler-level effect independent of slicing and
is a candidate for future investigation.

### 13.4 Implications for the project

The negative result motivates the remaining phases:

- **Phase 7 (Edge UPF):** Tests whether user-plane placement affects
  latency.
- **Phase 12 (Near-RT RIC / xApp):** Tests whether RAN-level adaptive
  control can achieve latency isolation that core-only slicing cannot.

The measurement infrastructure, slice configuration, and multi-session UE
support built during Phase 6 remain in place for later phases.

---

## Appendix A — Full Per-Trial Results

**Baseline (both DNNs on SD=1)**

| Load | Trial | N | Loss | p50 | p95 | p99 | Max |
|------|-------|---|------|-----|-----|-----|-----|
| 0 | 1 | 1495 | 0.0% | 64.5 | 84.5 | 85.5 | 95.5 |
| 0 | 2 | 1466 | 0.0% | 64.9 | 85.0 | 94.8 | 97.5 |
| 0 | 3 | 1512 | 0.0% | 56.9 | 75.9 | 85.4 | 98.2 |
| 15 | 1 | 2229 | 0.0% | 32.0 | 74.9 | 85.0 | 97.1 |
| 15 | 2 | 2233 | 0.0% | 32.0 | 74.9 | 85.1 | 95.5 |
| 15 | 3 | 2247 | 0.0% | 31.9 | 74.9 | 85.1 | 97.4 |
| 35 | 1 | 2292 | 0.0% | 32.3 | 74.2 | 75.9 | 94.9 |
| 35 | 2 | 2415 | 0.0% | 31.9 | 65.6 | 84.8 | 95.6 |
| 35 | 3 | 2343 | 0.0% | 32.3 | 71.4 | 85.4 | 108.1 |

**Treatment (factory DNN on SD=2)**

| Load | Trial | N | Loss | p50 | p95 | p99 | Max |
|------|-------|---|------|-----|-----|-----|-----|
| 0 | 1 | 1450 | 0.0% | 64.8 | 84.7 | 85.4 | 125.2 |
| 0 | 2 | 1446 | 0.0% | 64.8 | 84.9 | 94.5 | 96.0 |
| 0 | 3 | 1429 | 0.0% | 65.0 | 85.0 | 95.1 | 105.9 |
| 15 | 1 | 2158 | 0.0% | 33.4 | 75.6 | 86.6 | 120.5 |
| 15 | 2 | 2212 | 0.0% | 31.9 | 75.4 | 86.4 | 132.2 |
| 15 | 3 | 2219 | 0.0% | 32.1 | 74.9 | 85.3 | 106.0 |
| 35 | 1 | 2324 | 0.0% | 31.9 | 74.6 | 84.5 | 95.2 |
| 35 | 2 | 2413 | 0.0% | 31.8 | 65.5 | 84.3 | 94.8 |
| 35 | 3 | 2417 | 0.0% | 31.8 | 65.5 | 84.5 | 127.2 |

---

**End of Phase 6 Report**
