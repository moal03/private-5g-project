# Private 5G Network — Software Testbed and Experimental Evaluation

A software-only Private 5G Standalone (SA) testbed for a smart-factory
scenario, with a two-UPF core, network slicing, edge computing, RAN
monitoring, and a Near-RT RIC integration.

This repository contains the full testbed configuration, the
experimental campaign, the raw results, the analysis and validation
scripts, and a step-by-step reproduction guide.

---

## 1. What This Is

A simulated private 5G network built entirely from open-source
software components. It models a smart factory serving three classes
of endpoint:

| Service class | Representative devices | Primary metric |
|---------------|------------------------|----------------|
| eMBB-like | Industrial cameras, video | Throughput |
| URLLC-like | Industrial robots, control | Latency, jitter, loss |
| IoT/mMTC-like | Sensors, telemetry | Scalability, resource efficiency |

The project is a research study, not a product. Its purpose is to
measure the actual behaviour of this software stack under controlled
conditions and to report those measurements honestly, including
results that did not support the original hypotheses.

---

## 2. Architecture

    SMART FACTORY
         |
         +--------------+---------------+
         |              |               |
      Robots         Cameras         Sensors
         |              |               |
         +--------------+---------------+
                        |
                  UE (software)
                        |
                        v
                 +--------------+
                 |  OCUDU RAN   |
                 |  CU + DU     |
                 +------+-------+
                        |
              +---------+---------+
              |                   |
              v                   v
            E2 (SCTP)         N2 / N3
              |                   |
              v                   v
         +----------+       +-------------+
         | Near-RT  |       |  Open5GS    |
         |   RIC    |       |  5G Core    |
         | (FlexRIC)|       +------+------+
         +----------+              |
              |              +-----+-----+
              v              |           |
            xApp         UPF-A         UPF-B
                       (central)      (edge)
                         |             |
                         v             v
                    Central app    Edge app
                  (DNN=internet)  (DNN=factory)

The system is delivered as software running on a single Linux host.
There is no radio hardware; the radio link uses a ZeroMQ sample
transport over a virtual Ethernet pair.

---

## 3. Software Components

| Layer | Component | Version | Purpose |
|-------|-----------|---------|---------|
| 5G Core | Open5GS | 2.8.0 | AMF, SMF, two UPFs, subscriber data |
| RAN | OCUDU | dev build 2026-10-12 | O-RAN-oriented CU + DU, E2 agent |
| UE | OpenAirInterface (Duranta) | commit 6f89078b40 | Software 5G NR UE, band n78 TDD, 30 kHz SCS |
| RIC | FlexRIC | br-flexric, commit 7365081 | Near-RT RIC |
| Monitoring | Prometheus + node-exporter | 2.53.5 / 1.10.2 | Metrics collection |
| Monitoring | Grafana | 13.2.3 | Dashboards |
| Transport | ZeroMQ | system | Radio sample transport |

---

## 4. Repository Layout

| Directory | Contents |
|-----------|----------|
| architecture/ | Design diagrams and notes |
| backups/ | Configuration snapshots taken before experiments |
| captures/ | Packet captures (pcap) from key experiments |
| configs/ | All configuration files (Open5GS, OCUDU, per phase) |
| docs/ | Phase reports, design documents, setup procedure |
| edge-app/ | Application served from the edge namespace |
| experiments/ | Experiment manifest and orchestrator results |
| figures/ | Generated plots |
| logs/ | Environment snapshots and runtime logs |
| results/ | Raw results per phase |
| scripts/ | All scripts, per phase |

---

## 5. The Experimental Campaign

The project is organized as a sequence of phases. Each phase has one
report in the docs/ directory.

| Phase | Topic | Report |
|-------|-------|--------|
| 3 | First working 5G SA (UERANSIM + Open5GS) | docs/phase-3-report.md |
| 4 | OCUDU RAN integration (srsUE and OAI UE) | docs/phase-4-report.md |
| 5 | Private 5G / Non-Public Network | docs/phase-5-report.md |
| 6 | Network slicing — controlled experiment | docs/phase6/phase-6-report.md |
| 7 | Multiple UPFs and edge computing | docs/phase7/phase-7-report.md |
| 8 | Traffic engineering and performance | docs/phase8/phase-8-report.md |
| 9 | Monitoring and observability | docs/phase9/phase-9-report.md |
| 10 | Fault injection and resilience | docs/phase10/phase-10-report.md |
| 11 | Near-RT RIC integration | docs/phase11/phase-11-report.md |
| 12 | Custom xApp and RC control | docs/phase12/phase-12-report.md |
| 13 | Automated experiment framework | docs/phase13/phase-13-report.md |
| 14 | Research campaign consolidation | docs/phase14/phase-14-report.md |
| 15 | Validation of every material claim | docs/phase15/phase-15-report.md |
| 16 | Reproducibility artifacts | docs/phase16/phase-16-report.md |

---

## 6. Key Findings

Six quantitative studies were conducted. Summary:

| Study | Result |
|-------|--------|
| Slicing (Phase 6) | No measurable isolation of URLLC latency from eMBB load. 18 trials, differences within ±1.1%. |
| Edge UPF (Phase 7) | No benefit on the same host; ~32 ms reduction when a 30 ms backhaul delay is simulated. |
| Traffic engineering (Phase 8) | Placing a probe and competing load on different UPFs reduces latency by ~35 ms (53%) versus sharing one UPF. |
| Fault injection (Phase 10) | Six controlled faults. Clean layer separation. Multi-UPF isolation held at 100% success under core-function failure. |
| Near-RT RIC (Phase 11) | E2 interface works; KPM subscription accepted. This OCUDU build does not emit periodic KPM indications. |
| Custom xApp (Phase 12) | RC control message reached the DU, but ASN.1 decoding failed due to a codec mismatch between FlexRIC and OCUDU. |

Two honest negative results (slicing, and UPF-restart recovery) are
documented. Two software limitations of the specific OCUDU revision
are documented with evidence.

Full analysis:
- docs/phase14/phase-14-report.md
- results/phase14/master-analysis.txt

---

## 7. Validation and Reproducibility

### Validation (Phase 15)

Every material quantitative claim is recomputed from raw result
files. 26 claims validated: 24 verified, 1 close (rounding), 1
informational, 0 mismatches.

Run it:

    python3 scripts/phase15/validate.py

### Reproducibility (Phase 16)

- docs/phase16/setup-procedure.md — 15-stage rebuild guide
- scripts/phase16/verify.sh — 40 read-only checks of the running stack
- results/phase16/environment-snapshot.txt — reference machine state
- results/phase16/dependency-inventory.txt — every package and revision

Run verification:

    ./scripts/phase16/verify.sh

Expected: 38 PASS, 0 FAIL, 2 SKIP (the two skips are data-path
pings that only run when the application namespaces are running).

---

## 8. Running an Experiment

Experiments are declared in experiments/manifests/experiments.yaml
and executed through a Python orchestrator.

List experiments:

    python3 scripts/phase13/run_experiment.py \
      --manifest experiments/manifests/experiments.yaml --list

Run one experiment:

    python3 scripts/phase13/run_experiment.py \
      --manifest experiments/manifests/experiments.yaml \
      --only stack-health

Results are stored under experiments/results/<name>/<timestamp>/
with metadata, stdout, stderr, and declared artifacts.

---

## 9. Requirements

Hardware: 8-thread CPU, 14 GiB RAM, ~20 GiB free disk.
Tested on an Intel i7-1165G7 laptop.

OS: Ubuntu 26.04 LTS (tested). Ubuntu 24.04+ should work.

Network: apt mirrors, GitHub, and gitlab.eurecom.fr reachable.
Some upstream services are geo-restricted in certain regions; the
setup procedure documents workarounds.

Privileges: sudo for network namespace creation and systemd service
management. No special hardware required.

---

## 10. Documented Software Limitations

Two limitations are properties of the software versions used, not of
the project's configuration:

1. No periodic KPM indications from this OCUDU build.
   The KPM subscription is accepted, but no indication messages are
   emitted. Documented in Phase 11.

2. ASN.1 codec mismatch between FlexRIC and OCUDU.
   RC control messages reach the DU but cannot be decoded.
   Documented in Phase 12.

These are documented with evidence at the log level and the source
level. They are not setup errors.

---

## 11. Getting Started

1. Read the top-level report for the project overview:
   docs/phase16/phase-16-report.md

2. To rebuild the testbed, follow:
   docs/phase16/setup-procedure.md

3. To verify a running testbed:
   ./scripts/phase16/verify.sh

4. To see the results:
   docs/phase14/phase-14-report.md

5. To review validation:
   docs/phase15/phase-15-report.md

---

## 12. Author

Mohammad Almas
Undergraduate final project
GitHub: https://github.com/moal03

---

## 13. License and Use

This repository is shared for academic review. The software
components it depends on (Open5GS, OCUDU, OpenAirInterface, FlexRIC,
Prometheus, Grafana) are each governed by their own licenses. The
project-specific configurations, scripts, reports, and results are
the author's own work.

If you reuse any part of this work in academic context, please cite
the repository.
