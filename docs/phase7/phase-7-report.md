# Phase 7 Report — Multiple UPFs and Edge Computing

**Project:** Private 5G Network Simulation — Smart Factory Scenario
**Author:** Mohammad
**Date:** 2026-10-13
**Environment:** Ubuntu 26.04 LTS (resolute), kernel 7.0.0-38-generic, 8 CPU cores, 14 GiB RAM

---

## 1. Objective

Deploy two User Plane Functions (UPFs) in the Open5GS 5G Core and
investigate whether anchoring factory traffic at a local edge UPF reduces
the round-trip latency to a factory application compared with anchoring
the same traffic at a central UPF.

This addresses research question RQ2 from the project definition:

> How does edge UPF placement affect the latency and performance of
> industrial applications compared with centralized UPF placement?

**Hypothesis H2:** Local edge UPF placement will reduce end-to-end latency
compared with centralized traffic breakout.

The phase also serves an engineering goal: demonstrate that the private 5G
core can select different UPFs for different PDU sessions, which is a
prerequisite for any real multi-UPF deployment.

---

## 2. Software and Experimental Environment

| Component | Version |
|-----------|---------|
| Operating system | Ubuntu 26.04.1 LTS (resolute) |
| Kernel | 7.0.0-38-generic |
| Open5GS | 2.8.0~resolute6 |
| OCUDU CU/DU | built 2026-10-12 |
| OAI UE | develop branch, commit 6f89078b40 |
| ZeroMQ | installed (baseline) |
| tc / netem | available via iproute2 |

Host interfaces relevant to the experiment:

| Interface | Role |
|-----------|------|
| lo | Loopback |
| wlp0s20f3 | Wi-Fi (management only) |
| ogstun | UPF-A TUN, 10.45.0.1/16 (internet DNN) |
| ogstun2 | UPF-B TUN, 10.46.0.1/16 (factory DNN) |
| v-eth1 | veth to UE namespace |
| factory-host | veth to central application namespace |

---

## 3. Architecture

### 3.1 Intended Topology

Two UPFs, each anchored to a different DNN, selected by the SMF:

- **UPF-A** (central): DNN = internet, PFCP and GTP-U on 127.0.0.7
- **UPF-B** (edge): DNN = factory, PFCP and GTP-U on 127.0.0.8

A UE with two PDU sessions receives two UE IP addresses:

- internet session: 10.45.0.2 via oaitun_ue1 (through UPF-A)
- factory session:  10.46.0.2 via oaitun_ue1p2 (through UPF-B)

Two application endpoints:

- **Central application**: 10.60.0.10 (namespace factory-app)
- **Edge application**: 10.70.0.10 (namespace edge-app)

### 3.2 Feature Support in Open5GS 2.8.0

The Open5GS SMF configuration documented three selection mechanisms for
multiple UPFs: DNN, TAC, and CellID. UL CL and branching point are not
implemented in this release.

**Design choice:** Use DNN-based UPF selection. This is the simplest
supported approach and matches the factory use case (different DNNs for
different application domains).

### 3.3 Implemented Topology

Matched the intended design:

| Property | UPF-A | UPF-B |
|----------|-------|-------|
| DNN | internet | factory |
| PFCP endpoint | 127.0.0.7:8805 | 127.0.0.8:8805 |
| GTP-U endpoint | 127.0.0.7:2152 | 127.0.0.8:2152 |
| TUN interface | ogstun | ogstun2 |
| Session pool | 10.45.0.0/16 | 10.46.0.0/16 |
| Config file | /etc/open5gs/upf.yaml | /etc/open5gs/upf-edge.yaml |
| Service | open5gs-upfd | open5gs-upfd-edge |

---

## 4. Implementation

### 4.1 SMF Configuration Change

The SMF's `pfcp.client.upf` list was extended from one entry to two, with
each entry scoped by DNN:

    pfcp:
      server:
        - address: 127.0.0.4
      client:
        upf:
          - address: 127.0.0.7
            dnn: internet
          - address: 127.0.0.8
            dnn: factory

### 4.2 New UPF-B Configuration

A new file `/etc/open5gs/upf-edge.yaml` was created with:

- PFCP server on 127.0.0.8
- GTP-U server on 127.0.0.8
- Session subnet 10.46.0.0/16 with DNN=factory
- `dev: ogstun2` directive forcing a distinct TUN interface
- Metrics on 127.0.0.8:9091 (non-conflicting port)

### 4.3 UPF-A Configuration Change

The factory session was removed from UPF-A so it handles only the
internet DNN. This prevents two UPFs from both attempting to serve the
same session subnet.

### 4.4 systemd Unit for UPF-B

A new unit `open5gs-upfd-edge.service` was created with two important
details:

- `ExecStart=/usr/bin/open5gs-upfd -c /etc/open5gs/upf-edge.yaml`
- `AmbientCapabilities=CAP_NET_ADMIN` and `CapabilityBoundingSet=CAP_NET_ADMIN`

The capability is required because creating a new TUN interface
(ogstun2) needs CAP_NET_ADMIN, which the open5gs user does not have by
default.

### 4.5 UE Route Configuration

The UE namespace `ue1` was configured with:

    10.45.0.0/24 dev oaitun_ue1     # internet session
    10.46.0.0/24 dev oaitun_ue1p2   # factory session
    10.60.0.0/24 dev oaitun_ue1     # central app via internet DNN
    10.70.0.0/24 dev oaitun_ue1p2   # edge app via factory DNN

Both application namespaces were configured with return routes back to
the UE pools:

- factory-app: route to 10.45.0.0/16 and 10.46.0.0/16 via 10.60.0.1
- edge-app: route to 10.46.0.0/16 via 10.70.0.1

### 4.6 Removed Phase 5 Rule

The Phase 5 isolation rule (10.45.0.0/16 → 10.60.0.0/24 drop) was
removed and the corresponding systemd service disabled. The rule was
designed for Phase 5's isolation experiment and would have blocked the
central application path in Phase 7.

---

## 5. Control-Plane Verification

### 5.1 Both UPFs Registered with the SMF

After restart:

    open5gs-upfd-edge[225421]: [pfcp] INFO: pfcp_server() [127.0.0.8]:8805
    open5gs-upfd-edge[225421]: [gtp] INFO: gtp_server() [127.0.0.8]:2152
    open5gs-upfd-edge[225421]: [upf] INFO: PFCP associated [127.0.0.4]:8805
    open5gs-upfd-edge[225421]: [app] INFO: UPF initialize...done

The SMF log confirmed the reverse direction:

    open5gs-smfd[224932]: [smf] INFO: PFCP associated [127.0.0.8]:8805

### 5.2 Two Distinct Listener Sockets

    UNCONN  127.0.0.7:8805  open5gs-upfd
    UNCONN  127.0.0.8:8805  open5gs-upfd (edge)
    UNCONN  127.0.0.7:2152  open5gs-upfd
    UNCONN  127.0.0.8:2152  open5gs-upfd (edge)

### 5.3 Session-Level Selection

Both PDU sessions were established by the UE. The AMF logged:

    [gmm] UE SUPI[imsi-999700000000001] DNN[internet] S_NSSAI[SST:1 SD:0x1]
    [gmm] UE SUPI[imsi-999700000000001] DNN[factory]  S_NSSAI[SST:1 SD:0x1]

The UPF-B log recorded the newly assigned session:

    [upf] INFO: [Added] Number of UPF-Sessions is now 1

This proves UPF-B was selected for the factory DNN.

---

## 6. User-Plane Verification

### 6.1 TUN Interface Split

    ogstun:  inet 10.45.0.1/16  (UPF-A, internet)
    ogstun2: inet 10.46.0.1/16  (UPF-B, factory)

Each gateway belongs to exactly one UPF.

### 6.2 Cross-UPF Packet Capture Test

Two verification captures were made with tcpdump on both TUN
interfaces simultaneously.

**Test A — ping to central (10.60.0.10)**

    Captured on ogstun  (UPF-A): 6 packets
    Captured on ogstun2 (UPF-B): 0 packets

**Test B — ping to edge (10.70.0.10)**

    Captured on ogstun  (UPF-A): 0 packets
    Captured on ogstun2 (UPF-B): 6 packets

This is conclusive: each application destination is reachable only via
the UPF matching its DNN. No cross-traffic leaked between UPFs.

### 6.3 Saved Captures

- `multiupf-central-on-ogstun.pcap`
- `multiupf-central-on-ogstun2-EMPTY.pcap`
- `multiupf-edge-on-ogstun-EMPTY.pcap`
- `multiupf-edge-on-ogstun2.pcap`

---

## 7. Performance Measurements

### 7.1 Same-Host Baseline (no added delay)

Three trials of 200-packet ping and 60-second iperf3, alternating between
central and edge destinations.

| Metric | Central (UPF-A) | Edge (UPF-B) | Delta |
|--------|-----------------|--------------|-------|
| Ping avg (ms) | 56.42 (σ=2.69) | 56.47 (σ=1.96) | +0.05 |
| Ping delta % | — | — | +0.1% |
| TCP sender (Mbps) | 8.38 (σ=0.07) | 8.63 (σ=0.18) | +0.25 |
| TCP receiver (Mbps) | 7.76 (σ=0.17) | 7.97 (σ=0.16) | +0.21 |

**Result:** Same-host edge UPF placement shows no measurable latency
benefit. The difference between paths is within trial-to-trial noise.

### 7.2 Simulated Distance (netem 30 ms on central egress)

To evaluate the concept of edge computing without a geographically
distributed deployment, Linux `netem` was used to inject 30 ms one-way
delay on the `ogstun` egress path (affecting only the central
application). The edge path was left untouched.

| Metric | Central (UPF-A) | Edge (UPF-B) | Delta |
|--------|-----------------|--------------|-------|
| Ping avg (ms) | 89.94 (σ=2.42) | 58.17 (σ=1.91) | **−31.77** |
| Ping delta % | — | — | **−35.3%** |
| TCP sender (Mbps) | 8.13 | 8.32 | +0.19 |
| TCP receiver (Mbps) | 7.58 | 7.68 | +0.10 |

**Result:** With 30 ms of emulated backhaul, the edge path is 31.77 ms
faster than the central path — a change of −31.82 ms relative to the
same-host condition.

### 7.3 Comparison Table

| Metric | Same-host | +30 ms central | Change |
|--------|-----------|----------------|--------|
| Central ping avg (ms) | 56.42 | 89.94 | +33.51 |
| Edge ping avg (ms) | 56.47 | 58.17 | +1.69 |
| Delta (edge − central) (ms) | +0.05 | −31.77 | −31.82 |

The change in the delta matches the injected delay, confirming that the
delay was applied to the central path only.

---

## 8. Results and Discussion

### 8.1 Multi-UPF Steering Verified

The core capability claimed for this phase — that the SMF selects
different UPFs based on the requested DNN — is proven. The evidence is
threefold:

1. **Control plane:** Two PFCP associations at distinct addresses.
2. **Session plane:** The UPF-B process logged the new session when the
   factory DNN was requested.
3. **User plane:** Packet captures on both TUN interfaces showed
   unambiguous separation between the paths.

### 8.2 H2 Outcome

**H2 is supported under the simulated-distance condition and not
supported under the same-host condition.** The phase delivers both
results, which is why the experiment is more useful than a simple
positive claim:

- On a single host, edge UPF placement cannot reduce latency because
  there is no backhaul to remove.
- When backhaul delay is introduced, the edge path avoids it, and the
  RTT reduction equals the injected delay.

### 8.3 Throughput Observation

TCP throughput is bounded at approximately 8.4 Mbps in both conditions
and at both destinations. This is the same ceiling as Phase 4 and
Phase 6, and it is a property of the software UE's uplink, not of the
UPF placement. The two UPFs do not impose different throughput limits.

### 8.4 What the Measurements Do and Do Not Show

**Do show:** Under these conditions, with these endpoints, and with this
specific artificial delay, the edge path exhibits lower RTT than the
central path.

**Do not show:** That the physical UPF placement itself causes the
difference; that the system meets an industrial control latency
requirement; that the behavior holds under heavier load; that the
result generalizes to real geographic deployments.

---

## 9. Limitations

1. **Same-host deployment.** Both UPFs run on the same physical machine.
   The "edge" is a logical separation created by network topology, not a
   physical one. Real deployments place the edge UPF at a factory site
   and the central UPF at a data center.

2. **Simulated delay.** The 30 ms netem delay is an emulation, not a
   measurement of a real backhaul path. It represents a plausible
   regional distance (200–300 km of fiber) but does not include
   jitter, packet loss, or path asymmetry typical of real backhauls.

3. **Single UE.** All measurements use one UE with two PDU sessions.
   Multi-UE scenarios are not tested.

4. **Single-application endpoints.** Each destination runs only HTTP,
   URLLC echo, and iperf3. Industrial protocols (Modbus, OPC UA) are
   not tested.

5. **No UL CL / branching.** Open5GS 2.8.0 does not implement these
   features, so the more advanced traffic-classification topologies
   could not be evaluated. This is a hard version limitation.

6. **TCP throughput ceiling.** The 8.4 Mbps TCP ceiling is imposed by
   the software UE and does not vary with UPF placement. It limits the
   interpretability of any throughput-difference claim.

7. **Same PFCP port.** All UPFs and the SMF use port 8805 by default.
   The distinct addresses (127.0.0.7 vs 127.0.0.8) avoid conflict, but
   the shared port number is a design choice worth revisiting if more
   UPFs are added.

8. **Numerical coincidence risk.** The −31.77 ms RTT delta closely
   matches the injected 30 ms delay, which is expected, but the
   measurement precision (~2 ms standard deviation) does not allow us
   to distinguish a 30 ms injected delay from a 32 ms one.

---

## 10. Conclusion

Phase 7 established a working multi-UPF architecture using Open5GS
2.8.0's DNN-based UPF selection. Both control-plane associations and
user-plane paths were verified with logs, socket state, and packet
captures.

The performance comparison yielded a clean, expected result:

- **Same-host:** no measurable latency difference between edge and
  central paths (Δ = +0.05 ms).
- **Simulated distance:** the edge path avoids the emulated 30 ms
  backhaul and delivers a 31.77 ms RTT improvement.

The experiment demonstrates the **mechanism** of edge computing
(local user-plane anchoring removes backhaul latency) and correctly
does **not** claim a benefit that the single-host testbed cannot
support. The honest two-part result is more valuable than a false
positive.

The infrastructure built in this phase — multi-UPF configuration,
DNN-based selection, TUN-interface isolation, and the measurement
harness — is reusable for Phase 8 (traffic engineering) and for later
phases that add RAN-level control via the Near-RT RIC and xApps.

---

## Appendix A — Artifacts

| Category | Files |
|----------|-------|
| Configs | `/etc/open5gs/upf.yaml`, `upf-edge.yaml`, `smf.yaml` + backups |
| systemd | `open5gs-upfd-edge.service` |
| Scripts | `scripts/phase7/measure-central-vs-edge.sh` |
| Raw results | `results/phase7/ping-*.txt`, `iperf3-*.txt` (24 files) |
| Analysis | `results/phase7/analysis-final.txt`, `multi-upf-verification.txt` |
| Captures | `captures/phase7/*.pcap` (4 files) |
| Logs | `logs/phase7/*` (14 files) |
| Design | `docs/phase7/design.md` |

## Appendix B — Key Commands Used

    # UPF-B service
    sudo systemctl start open5gs-upfd-edge

    # Add TUN gateway to ogstun2
    sudo ip link set ogstun2 up
    sudo ip addr add 10.46.0.1/16 dev ogstun2

    # UE routes
    sudo ip netns exec ue1 ip route add 10.60.0.0/24 dev oaitun_ue1
    sudo ip netns exec ue1 ip route add 10.70.0.0/24 dev oaitun_ue1p2

    # Application namespace return routes
    sudo ip netns exec factory-app ip route add 10.45.0.0/16 via 10.60.0.1
    sudo ip netns exec edge-app ip route add 10.46.0.0/16 via 10.70.0.1

    # Simulated distance
    sudo tc qdisc add dev ogstun root netem delay 30ms

    # Measurement
    ./scripts/phase7/measure-central-vs-edge.sh

---

**End of Phase 7 Report**
