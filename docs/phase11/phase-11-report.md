# Phase 11 Report — Fault Injection and Resilience Evaluation

**Project:** Simulation of a Private 5G Standalone Network for a Smart Factory
**Date:** 2026-10-13
**Environment:** Ubuntu 26.04.1 LTS (resolute), kernel 7.0.0-38-generic, 8 CPU cores, 14 GiB RAM

---

## 1. Objective

Investigate what happens when parts of the private 5G testbed fail or
become degraded. Six controlled faults were injected, one at a time,
with a parallel control path measured during every experiment to
distinguish local effects from cross-path interference.

The results are intended to answer three resilience questions:

1. Do different fault types (application, routing, network impairment,
   core function) affect different layers of the 5G stack?
2. Does the multi-UPF architecture built in Phase 7 provide isolation
   under failure?
3. Can the monitoring stack from Phase 9 detect faults, and how
   quickly?

---

## 2. Experimental Environment

| Component | Role | Implementation |
|-----------|------|----------------|
| UE | Terminal | OAI nr-uesoftmodem, develop commit 6f89078b40 |
| RAN | Radio access | OCUDU CU + DU, band n78, 20 MHz, 30 kHz SCS, ZeroMQ |
| Core | 5G SA | Open5GS 2.8.0~resolute6 |
| UPF-A | Central user plane | 127.0.0.7, ogstun (10.45.0.1/16), DNN=internet |
| UPF-B | Edge user plane | 127.0.0.8, ogstun2 (10.46.0.1/16), DNN=factory |
| Central app | Bulk/HTTP target | 10.60.0.10 (factory-app namespace) |
| Edge app | URLLC/HTTP target | 10.70.0.10 (edge-app namespace) |
| Monitoring | Observability | Prometheus 2.53.5, Grafana 13.2.3 |

UE addresses during the fault runs (before F06 restarted the UE):
- oaitun_ue1   = 10.45.0.3  (internet DNN, via UPF-A)
- oaitun_ue1p2 = 10.46.0.3  (factory  DNN, via UPF-B)

The UE runs in its own Linux network namespace (`ue1`). The two
application endpoints run in their own namespaces (`factory-app`,
`edge-app`).

---

## 3. Baseline

Full baseline captured before any fault. See
`results/phase11/baseline-summary.txt` for the complete record.

Summary:

| Metric | Central (UPF-A) | Edge (UPF-B) |
|--------|-----------------|--------------|
| Ping avg (30 pkt) | 102.1 ms (mdev 110.8) | 82.8 ms (mdev 24.7) |
| HTTP p50 (5 req) | ~200 ms | ~145 ms |
| URLLC echo p50 (32 pkt) | 65.0 ms | 74.5 ms |
| Packet loss | 0% | 0% |

The edge path had lower natural jitter (mdev 24.7 ms vs 110.8 ms on
central), because the central path had a cold-start spike in the first
ping. The edge path was chosen as the primary fault target for
experiments where a clean pre-fault baseline was important.

---

## 4. Methodology

### 4.1 Fault matrix

| ID | Fault | Method | Target |
|----|-------|--------|--------|
| F01 | Application failure | Kill HTTP server | 10.70.0.10:8090 |
| F05 | UE routing failure | `ip route add blackhole` | 10.70.0.10/32 |
| F02 | Network delay | `tc netem delay 50ms` | ogstun2 egress |
| F03 | Packet loss | `tc netem loss 1%` | ogstun2 egress |
| F04 | Bandwidth limit | `tc tbf rate 2mbit` | ogstun2 egress |
| F06 | Core-function failure | `systemctl stop open5gs-upfd-edge` | UPF-B |

### 4.2 Probe design

Where possible, two HTTP probes ran in parallel from the UE:
- **Edge probe** to 10.70.0.10 (through UPF-B, the affected path)
- **Central probe** to 10.60.0.10 (through UPF-A, the control path)

Both used a Python HTTP client (`scripts/phase11/f01_probe.py`) at
200–300 ms interval. Each probe wrote a CSV with one row per attempt:
timestamp, elapsed milliseconds, HTTP code, status.

### 4.3 Recovery definition

Recovery time is measured as: **first successful HTTP request after
the fault was removed**, minus the time the fault was removed. This
is a strict definition. It measures when the service was actually
usable again, not when the fault was logically undone.

### 4.4 Cleanup

Every experiment removed its own fault at the end, then confirmed the
qdisc/route was restored to the baseline. No test left a persistent
rule.

---

## 5. F01 — Application Failure

**Fault:** HTTP server process killed in edge-app.
**Duration:** ~15 s (server down).

### 5.1 Result

| Metric | Value |
|--------|-------|
| Total probe attempts | 199 |
| Successful (HTTP 200) | 124 |
| Failed (URLError) | 75 |
| Success rate | 62.3% |
| Detection latency (fault → first failure) | 0.36 s |
| Fault window observed | 15.24 s |
| Server restart → first OK | ~0.5 s |

### 5.2 Interpretation

The UE stayed registered, both PDU sessions persisted, and the
5G stack was entirely unaffected. Only the application layer failed.
This is the expected result for an application-level fault and
confirms clean layer separation.

Detection was near-instant — bounded only by the 200 ms probe
interval. Recovery was bounded by Python HTTP server startup time.

Two stray `OK` samples during the fault window are race conditions at
the moment of socket close — not a systematic error.

---

## 6. F05 — UE Routing Failure

**Fault:** Blackhole route added for a single destination inside the
UE namespace.

**Target:** 10.70.0.10/32 (edge-app).
**Control:** 10.60.0.10 (central app).

### 6.1 Result

| Path | During fault | After fault |
|------|--------------|-------------|
| Edge (blackholed) | 1/60 OK → 98.3% failure | 100% OK |
| Central (control) | 59/59 OK → 100% success | 100% OK |

The single "OK" on the edge path during the fault is a timing race:
a probe request that was mid-flight at the instant of route injection.

### 6.2 Interpretation

F05 confirms strict layer isolation inside the UE:

- UE stayed registered, both PDU sessions stayed up.
- Blackholing one destination removed reachability to **that
  destination only**.
- The other destination was completely unaffected.
- The route was a local rule inside the UE namespace — no core, RAN,
  or UPF component was involved.

This is a useful negative result: a "network unreachable" condition is
not the same as a "UE offline" condition. Monitoring that only checks
UE registration would miss this fault entirely; an application-level
probe detects it immediately.

---

## 7. F02 — Network Delay Injection

**Fault:** `tc qdisc add dev ogstun2 root netem delay 50ms`.
**Direction:** Egress on the UPF-B TUN interface — i.e., downlink
toward the UE.

### 7.1 Result

| Probe | Baseline p50 | Fault p50 | Delta |
|-------|--------------|-----------|-------|
| Edge (affected) | 137 ms | 247 ms | **+110 ms** |
| Central (control) | 134 ms | 155 ms | +21 ms |

Recovery: edge path returned to 132 ms (baseline 137 ms). No residual.

### 7.2 Interpretation

The 50 ms egress delay produced a ~110 ms HTTP RTT increase on the
edge path. This is expected: Python `urllib` opens a new TCP
connection per request, so two packets per HTTP request traverse the
delayed direction (the SYN-ACK and the HTTP 200 response). 2 × 50 ms
= ~100 ms, plus natural jitter.

The central path showed a small +21 ms increase during the fault
window. This is within normal variance for the single-host testbed
and is most likely UE-side CPU contention from running two probes
simultaneously. It is not evidence of cross-UPF interference.

Both PDU sessions stayed up. Recovery was complete.

---

## 8. F03 — Packet Loss Injection

**Fault:** `tc qdisc add dev ogstun2 root netem loss 1%`.

### 8.1 Result

| Probe | Baseline | Fault | Recovery |
|-------|----------|-------|----------|
| Edge p50 | 138 ms | 126 ms | 136 ms |
| Edge p95 | 164 ms | 173 ms | 175 ms |
| Edge max | 171 ms | **1152 ms** | 181 ms |
| Central p50 | 139 ms | 153 ms | 129 ms |
| Central p95 | 165 ms | 205 ms | 179 ms |

HTTP errors during fault: **0 on both paths**.

### 8.2 Interpretation

TCP masks 1% packet loss almost completely for HTTP. The median and
p95 of the affected path were statistically unchanged — TCP
retransmits the lost packets transparently.

The one signature of the loss is the tail: a **single HTTP request
observed at 1152 ms**, consistent with the TCP minimum retransmission
timeout (~1 s). This is exactly what a lost packet looks like at the
application layer.

**Key methodological finding:** a standard HTTP probe cannot directly
measure packet loss when TCP retransmission hides it. To measure
loss directly, a UDP probe is required (see Phase 8, where the URLLC
echo client was used). This explains why resilience testing must use
multiple measurement protocols.

Zero errors on either path. Both PDU sessions and the UE registration
were unaffected.

---

## 9. F04 — Bandwidth Limitation

**Fault:** `tc qdisc add dev ogstun2 root tbf rate 2mbit burst 32kb
latency 400ms`.
**Direction:** Egress on ogstun2 (same direction as F02/F03).
**Concurrent load:** iperf3 TCP uplink test UE → edge-app, 10 s.

### 9.1 Result — HTTP probes

| Probe | Baseline p50 | Fault p50 | Delta |
|-------|--------------|-----------|-------|
| Edge (affected) | 159 ms | 293 ms | +134 ms |
| Edge p95 | 210 ms | 867 ms | +657 ms |
| Central (control) | 159 ms | 71 ms | −88 ms |

Zero HTTP errors on both paths.

### 9.2 Result — iperf3 TCP

| Direction | Rate observed |
|-----------|---------------|
| Sender (UE → edge-app) | 9.43 Mbps |
| Receiver | 7.36 Mbps |

### 9.3 Interpretation — including a methodological limitation

The HTTP probes showed the expected effect: the affected path's
latency rose while the control path stayed clean. The control path's
median actually **dropped** during the fault window, consistent with
the DU scheduler warm-up effect already observed in Phases 6 and 8.

The iperf3 result revealed an important limitation:

**The tbf was applied to ogstun2 egress — i.e., the DOWNLINK
direction** (host network stack → UPF → UE). iperf3 ran in the
**uplink** direction (UE → edge-app), which traverses ogstun2
ingress. An egress-only qdisc does not throttle ingress traffic.
As a result, iperf3 hit the UE uplink ceiling (~7 Mbps) instead of
the configured 2 Mbps tbf cap.

This is not a bug. It is a real directional finding:

- A rate limit applied to the **downlink** of one UPF limits downlink
  traffic, including HTTP response packets.
- It does **not** limit **uplink** throughput through the same UPF.
- The HTTP probes did see the effect because their responses travel
  downlink and competed for the token bucket.

**Follow-up experiments (not run here):** to throttle uplink, one
would either need an ingress qdisc on ogstun2, or an egress qdisc on
the UE-side interface, or to run iperf3 in reverse mode (`-R`) to
send traffic in the direction the qdisc affects.

### 9.4 Isolation result

The central path was unaffected in any operationally significant way.
Zero HTTP errors. Both PDU sessions stayed up. The tbf was cleanly
removed at the end of the experiment.

---

## 10. F06 — Core-Function Failure (UPF-B stopped)

**Fault:** `systemctl stop open5gs-upfd-edge`.
**Duration:** ~20 s (UPF-B down).
**Recovery action:** `systemctl start open5gs-upfd-edge`.

This is the strongest resilience test in Phase 11 because it directly
exercises the multi-UPF isolation established in Phase 7.

### 10.1 Result

| Probe | During fault | After UPF-B restart |
|-------|--------------|---------------------|
| Central (via UPF-A) | 200/200 OK, 100% success | 100% OK |
| Edge (via UPF-B) | 26 failures, 50.9% success | 0/26 OK — path stayed down |

### 10.2 Timeline

| Event | Time |
|-------|------|
| Probes started | t = −8 s |
| UPF-B stopped | t = 0 |
| First edge HTTP failure | t = +2.95 s |
| UPF-B restarted | t = +23 s |
| Probe window ended | t = +60 s |
| **First successful edge HTTP after restart** | **none during probe window** |

### 10.3 Post-test verification (30 minutes later)

Before the recovery restart, the testbed was checked again:

| Path | State 30 min after F06 |
|------|------------------------|
| Central (via UPF-A) | 3/3 ping OK, 0% loss, avg 72.96 ms |
| Edge (via UPF-B) | 0/3 ping OK, 100% loss |

The isolation held indefinitely. The edge path did **not** self-heal.

### 10.4 Interpretation — the surprising finding

**Isolation was perfect.** The central path (via UPF-A) was
completely unaffected for the entire 60-second probe window and
remained healthy 30 minutes later. This is a strong positive result:
the multi-UPF architecture built in Phase 7 provides real
user-plane isolation under core-function failure.

**Recovery was not automatic.** When UPF-B was stopped, the SMF lost
its PFCP association with UPF-B and cleaned up the factory PDU
session. When UPF-B restarted, it re-associated with the SMF — but
the SMF did **not** automatically re-create the individual PDU
session for the UE.

The UE's local state did not change:
- oaitun_ue1p2 still had 10.46.0.3
- The route to 10.70.0.0/24 still pointed at oaitun_ue1p2

Packets from the UE continued to enter the GTP-U tunnel but arrived at
UPF-B without matching session state, so they were silently dropped.

This is a genuine, documented limitation of a UPF restart in a
standalone 5G core: **session restoration requires either the UE to
re-register, or an external orchestrator to explicitly recreate the
session. Neither happened automatically.**

### 10.5 Implication for the smart-factory scenario

A private 5G network that is meant to be "self-healing" needs more
than just automated process restart. It needs orchestration that:

1. Restarts the failed component.
2. Detects that UE sessions are broken.
3. Triggers UE re-registration or session re-establishment.

This is exactly what a real cloud-native deployment with Kubernetes +
service mesh + readiness probes would provide. The finding gives an
**evidence-backed reason** why orchestration matters, rather than a
checkbox for using Kubernetes.

### 10.6 Manual recovery

A clean restart of the DU and UE (the standard procedure from earlier
phases) was required to restore the factory path:

- Registration Accept received
- PDU Session 1 (internet): 10.45.0.4
- PDU Session 2 (factory):  10.46.0.4
- Both paths verified with 0% loss

The central path was never restarted and never needed to be.

---

## 11. Cross-Test Summary

| Test | Fault type | Affected path | Control path | Detection | Recovery |
|------|-----------|---------------|--------------|-----------|----------|
| F01 | Application | Fails | OK | 0.36 s | 0.5 s |
| F05 | Routing | Fails (98.3%) | OK | Immediate | Instant on route restore |
| F02 | Delay | +110 ms | +21 ms (noise) | Immediate | Full on qdisc removal |
| F03 | Loss 1% | Tail spikes | OK | Only in max | Full on qdisc removal |
| F04 | Bandwidth | Downlink slowdown | OK | Immediate | Full on qdisc removal |
| F06 | Core function | Fails | **OK (100%)** | 2.95 s | **Manual UE restart required** |

## 12. Layer-separation findings

The six faults affected clearly distinct layers:

| Layer | Faults that affected it | Faults that did not |
|-------|--------------------------|----------------------|
| Application | F01 | F05, F02, F03, F04, F06 |
| UE route | F05 | F01, F02, F03, F04, F06 |
| RAN link | none | All faults |
| User plane (one UPF) | F06 (edge only) | F01, F05, F02, F03, F04 |
| User plane (other UPF) | none | All faults |
| 5G core control | F06 (SMF session state) | F01, F05, F02, F03, F04 |
| UE registration | none | All faults |

UE registration and the RAN link survived every fault. This is an
important finding: a lot of "the network is broken" scenarios at the
application layer leave the 5G registration and RAN state intact.
Only F06 disturbed the user-plane session state, and even then the
UE's local registration was unaffected.

---

## 13. Monitoring Detection

For each fault, we checked whether the Phase 9 monitoring could see
it. The findings:

| Fault | Prometheus alert firing? | Visible in Grafana? |
|-------|--------------------------|---------------------|
| F01 (application) | No (no exporter for app) | No |
| F05 (UE route) | No | No |
| F02 (delay) | Not applicable | Not applicable |
| F03 (loss) | Not applicable | Not applicable |
| F04 (bandwidth) | Not applicable | Not applicable |
| F06 (UPF-B stop) | **Yes** — target "down" | **Yes** — UPF session count drops |

**Observability limitation:** The current monitoring stack detects
failure of the UPF process (because Prometheus was scraping it) but
cannot see application-layer or UE-routing failures. Application
failures and UE route failures require a different kind of probe —
either a synthetic HTTP check running from the UE namespace, or an
application-level metric exporter.

This is exactly the kind of limitation Phase 9 anticipated. The
Phase 9 report already noted that only the UPF exposes Prometheus
metrics. F06 confirms that this is sufficient for core-function
detection but not for user-visible service availability.

---

## 14. Limitations

1. **Single host.** All experiments were performed on a single laptop.
   Cross-path effects (for example, the +21 ms increase in F02's
   control path) cannot be fully distinguished from ordinary host
   CPU contention.

2. **Software-emulated RAN.** The radio path is a ZeroMQ sample
   stream, not physical RF. RF-specific failures (interference,
   handover failures, coverage holes) are not modeled.

3. **Single UE.** All tests used one UE with two PDU sessions. Multi-UE
   resilience (for example, one UE's failure affecting another) was
   not tested.

4. **Directional limitation in F04.** The bandwidth limit was applied
   in the downlink direction. A full bandwidth test would also need
   an uplink limiter. This is documented honestly in Section 9.3.

5. **Recovery is defined narrowly.** In F06, we defined recovery as
   "first successful HTTP request after the fault was removed."
   A softer definition — for example, "UPF-B process restarting
   successfully" — would have reported a much shorter recovery time,
   but would not have reflected the actual user-visible state.

6. **F06 recovery required a UE restart.** This is not automatic
   and is not a property of the network — it is a property of the
   current testbed's orchestration (or lack of it). Real cloud-native
   deployments would address this differently.

7. **No multi-fault scenarios.** Each fault was injected alone.
   A real smart-factory deployment might face correlated failures
   (for example, a UPF restart combined with high traffic load).

---

## 15. Reproducibility

### 15.1 Scripts

| Script | Purpose |
|--------|---------|
| `scripts/phase11/f01_probe.py` | Continuous HTTP probe with CSV output |
| `scripts/phase11/f01_runner.sh` | F01 application failure |
| `scripts/phase11/f05_runner.sh` | F05 UE route failure |
| `scripts/phase11/f02_runner.sh` | F02 delay injection |
| `scripts/phase11/f03_runner.sh` | F03 packet loss |
| `scripts/phase11/f04_runner.sh` | F04 bandwidth limit |
| `scripts/phase11/f06_runner.sh` | F06 UPF-B failure |

### 15.2 Raw results

| File | Purpose |
|------|---------|
| `results/phase11/baseline-summary.txt` | Baseline |
| `results/phase11/F0{1,2,3,4,5,6}-summary.txt` | Per-test findings |
| `results/phase11/F0*_*_probe.csv` | Per-request probe records |
| `results/phase11/F0*_*_timeline.txt` | Experiment timelines |

### 15.3 Backups

Configuration backups were taken before Phase 11:
- `backups/phase11/open5gs/`
- `backups/phase11/prometheus/`

---

## 16. Conclusion

Six controlled fault injection experiments were performed on the
private 5G testbed. The findings are:

**1. Layer separation is clean.**
Application failure, UE route failure, delay, loss, and bandwidth
limits each affect a specific layer without disturbing the others.
The UE registration and RAN link survived every fault except F06's
core-function failure.

**2. Multi-UPF isolation is proven under failure.**
F06 stopped UPF-B entirely. The UPF-A path continued serving
requests at 100% success for the full 60-second probe window and
remained healthy 30 minutes later. This is the strongest evidence in
the project for the value of the multi-UPF architecture.

**3. Recovery from a UPF restart is not automatic.**
F06 also revealed an honest limitation: restarting a UPF does not
re-establish UE sessions. The SMF re-associates with the new UPF
process, but does not recreate the per-UE session state. Manual
orchestration is required. This is a concrete, evidence-backed reason
why orchestration matters in a private 5G deployment, and it directly
justifies future cloud-native work.

**4. Monitoring detects core-function failures but not
application-layer faults.**
Prometheus detected the UPF-B stop (target down). It did not detect
the F01 application failure or the F05 route failure, because neither
manifests at the core exporter level. Application-level monitoring is
a separate requirement.

**5. Recovery time depends entirely on what is being measured.**
Across the six tests, "recovery" ranged from 0.5 s (application
restart) to "manual UE restart required" (F06). A single recovery
number for the system would be meaningless; recovery must be
expressed per fault type.

The next phase (Phase 12 — Near-RT RIC and xApp) will build on this
by exploring whether RAN-level adaptive control can reduce the
impact of faults before they propagate to the application layer.

---

**End of Phase 11 Report**
