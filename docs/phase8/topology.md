# Phase 8 — Experimental Topology

## Date
2026-10-13

## End-to-End Path

UE (namespace: ue1)
  ├─ oaitun_ue1     10.45.0.2/24  →  internet DNN
  └─ oaitun_ue1p2   10.46.0.2/24  →  factory DNN
        │
        │  ZMQ sample transport over veth 10.200.1.0/24
        ▼
OCUDU DU (odu) — band n78, 30 kHz SCS, 20 MHz
        │ F1-C (SCTP 38472) + F1-U (GTP-U)
        ▼
OCUDU CU (ocu) — CU-CP + CU-UP combined
        │ N2 (NGAP/SCTP 38412) + N3 (GTP-U 2152)
        ▼
Open5GS SMF (127.0.0.4:8805 PFCP)
   ├── UPF-A (127.0.0.7) → ogstun  10.45.0.1/16  (internet DNN)
   └── UPF-B (127.0.0.8) → ogstun2 10.46.0.1/16  (factory  DNN)
        │
        │ N6 host routing
        ▼
   ┌────┴──────────────────────────────┐
   │                                   │
factory-app namespace              edge-app namespace
  10.60.0.10 (central)               10.70.0.10 (edge)
  HTTP 8080 / URLLC 9200             HTTP 8080 / URLLC 9200
  iperf3 5201                        iperf3 5201

## Components

| Component | Implementation | Address |
|-----------|----------------|---------|
| UE | OAI nr-uesoftmodem (develop commit 6f89078b40) | 10.45.0.2 and 10.46.0.2 |
| RAN CU | OCUDU ocu (26.10.0 build) | 127.0.0.1:38472 (F1-C) |
| RAN DU | OCUDU odu (26.10.0 build) | 127.0.0.1 (F1-C peer) |
| SMF | Open5GS 2.8.0~resolute6 | 127.0.0.4 |
| UPF-A (central) | Open5GS upfd | 127.0.0.7 → ogstun 10.45.0.1 |
| UPF-B (edge) | Open5GS upfd-edge | 127.0.0.8 → ogstun2 10.46.0.1 |
| Central app | Python HTTP + URLLC echo + iperf3 | 10.60.0.10 |
| Edge app | Python HTTP + URLLC echo + iperf3 | 10.70.0.10 |

## UE Routes (namespace ue1)

    10.45.0.0/24 dev oaitun_ue1      src 10.45.0.2
    10.46.0.0/24 dev oaitun_ue1p2    src 10.46.0.2
    10.60.0.0/24 dev oaitun_ue1      # central app via internet DNN
    10.70.0.0/24 dev oaitun_ue1p2    # edge app   via factory  DNN
    10.200.1.0/24 dev v-ue1          src 10.200.1.2

## Application Namespace Return Routes

factory-app (central):
    10.45.0.0/16 via 10.60.0.1
    10.46.0.0/16 via 10.60.0.1
    10.60.0.0/24 dev factory-ns  src 10.60.0.10

edge-app (edge):
    10.46.0.0/16 via 10.70.0.1
    10.70.0.0/24 dev edge-ns  src 10.70.0.10

## Host Queue State

ogstun  (UPF-A egress): fq_codel (default)
ogstun2 (UPF-B egress): fq_codel (default)

No netem delay active.

## CPU Resources

Host: 8 cores. The DU process consumes ~130% CPU during idle running
(one core plus one thread). The UE process consumes ~20%. The CU
process consumes ~10%. Approximately 4–5 cores remain free for
application workloads.

## Test Endpoints

| Endpoint | IP | Ports |
|----------|----|-------|
| Central app | 10.60.0.10 | HTTP 8080, URLLC echo 9200, iperf3 5201 |
| Edge app | 10.70.0.10 | HTTP 8080, URLLC echo 9200, iperf3 5201 |

## Measurement Tools

| Tool | Version |
|------|---------|
| iperf3 | 3.20 |
| ping | iputils 20250605 |
| tc | iproute2 6.19.0 |
| tcpdump | (system) |
| python3 | 3.14.4 |

## Important Boundary

This is a software-emulated 5G SA testbed. The radio path uses ZeroMQ
sample transport over a veth pair, not physical RF. Measurements reflect
the software RAN, software UE, and Linux networking — not real radio
propagation.
