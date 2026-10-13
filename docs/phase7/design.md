# Phase 7 — Multi-UPF and Edge Design

## Objective

Deploy two User Plane Functions (UPFs) in the Open5GS 5G core, selected
by DNN. Measure whether traffic routed through the edge UPF to a local
application exhibits lower RTT than traffic routed through the central
UPF to a cloud-side application.

**RQ2:** How does edge UPF placement affect the latency and performance
of industrial applications compared with centralized UPF placement?

**H2:** The edge UPF path will exhibit measurably lower RTT to the factory
application than the central UPF path.

## Software Stack

| Component | Version |
|-----------|---------|
| Open5GS | 2.8.0~resolute6 |
| OCUDU CU/DU | built 2026-10-12 |
| OAI UE | develop commit 6f89078b40 |

## Open5GS Feature Support

Checked in `/etc/open5gs/smf.yaml` comments:

- UPF selection by DNN: SUPPORTED
- UPF selection by TAC: SUPPORTED (not used)
- UPF selection by CellID: SUPPORTED (not used)
- UL CL / Branching Point: NOT SUPPORTED in 2.8.0

**Design choice:** Design A (multiple UPFs for different sessions),
selected by DNN. This is the simplest supported topology.

## UPF Design

| Property | UPF-A (central) | UPF-B (edge) |
|----------|-----------------|--------------|
| Purpose | internet DNN | factory DNN |
| PFCP endpoint | 127.0.0.7:8805 | 127.0.0.8:8805 |
| GTP-U endpoint | 127.0.0.7:2152 | 127.0.0.8:2152 |
| Metrics | 127.0.0.7:9090 | 127.0.0.8:9091 |
| TUN interface | ogstun | ogstun2 |
| Session pool | 10.45.0.0/16 | 10.46.0.0/16 |
| Config file | /etc/open5gs/upf.yaml | /etc/open5gs/upf-edge.yaml |
| systemd unit | open5gs-upfd | open5gs-upfd-edge |

## SMF Selection Rule

    pfcp:
      client:
        upf:
          - address: 127.0.0.7
            dnn: internet
          - address: 127.0.0.8
            dnn: factory

## UE Sessions

| Session | DNN | UE IP | UPF | Destination |
|---------|-----|-------|-----|-------------|
| 1 | internet | 10.45.0.x | UPF-A | 10.60.0.10 (central app) |
| 2 | factory | 10.46.0.x | UPF-B | 10.70.0.10 (edge app) |

## Test Plan

| Test | Path | Measurement |
|------|------|-------------|
| Central RTT | UE -> UPF-A -> 10.60.0.10 | ping -c 100 |
| Edge RTT | UE -> UPF-B -> 10.70.0.10 | ping -c 100 |
| Central throughput | UE -> UPF-A -> 10.60.0.10 | iperf3 -t 60 |
| Edge throughput | UE -> UPF-B -> 10.70.0.10 | iperf3 -t 60 |

## Risks

1. Open5GS SMF may ignore DNN-based UPF selection - fall back to
   single UPF, two destinations.
2. Second UPF may conflict on ports - use distinct 127.0.0.8 addresses.
3. Firewall rules from Phase 5 block 10.45.0.0/16 -> 10.60.0.0/24 -
   must be removed for Phase 7 central path testing.
4. UE routing table needs updates for both new destinations.
5. Both UPFs are on the same host - the edge is logical, not
   geographic. Document this as a limitation.

## Success Criteria

Multi-UPF is considered verified when:

1. Both UPF processes are running with distinct PFCP/GTP-U sockets.
2. The SMF maintains PFCP sessions with both UPFs.
3. UE session 1 anchors at UPF-A (evidenced by SMF log).
4. UE session 2 anchors at UPF-B (evidenced by SMF log).
5. Traffic from UE session 1 reaches 10.60.0.10 via UPF-A.
6. Traffic from UE session 2 reaches 10.70.0.10 via UPF-B.
7. Each path is distinguishable in packet captures.
