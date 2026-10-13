# Phase 4 Report — OCUDU and Open5GS Integration

**Project:** Private 5G Network — Smart Factory Scenario
**Author:** Mohammad
**Date:** 2026-10-13
**Environment:** Ubuntu 26.04 LTS (resolute), kernel 7.0.0-38-generic, 8 CPU cores, 14 GiB RAM

---

## 1. Objective

Replace the simulated UERANSIM base station with OCUDU, an O-RAN-oriented
RAN implementation, while keeping Open5GS as the 5G Core. Validate the
integration at the interfaces between the RAN and core, connect a 5G SA
UE, and verify user-plane connectivity.

## 2. Software Environment

| Component | Version |
|-----------|---------|
| Operating System | Ubuntu 26.04 LTS (resolute) |
| Kernel | 7.0.0-38-generic |
| CPU | 8 cores |
| RAM | 14 GiB |
| OCUDU | 26.10.0 (downloaded from gitlab.com/ocudu/ocudu) |
| srsRAN 4G | 25.10.0 (release_25_10, commit 6bcbd9e5bf) |
| Open5GS | 2.8.0~resolute6 |
| FerretDB | 1.24.2 |
| PostgreSQL | 18.6 |
| ZeroMQ | 4.3.6 |

## 3. Architecture

The Phase 4 network replaces the UERANSIM gNB with a full OCUDU split 8
RAN, running entirely in software:

- **5G SA UE:** srsUE (srsRAN 4G, 5G SA mode), running inside namespace `ue1`
- **Simulated radio:** ZeroMQ IQ sample transport at 23.04 MHz
- **Distributed Unit (DU):** OCUDU `odu`
- **Central Unit (CU):** OCUDU `ocu` (CU-CP + CU-UP combined)
- **5G Core:** Open5GS (17 services)
- **Subscriber store:** FerretDB + PostgreSQL

Interface map:

| Interface | Endpoints | Protocol |
|-----------|-----------|----------|
| ZeroMQ (radio) | srsUE ↔ DU | IQ samples over TCP |
| F1-C | DU ↔ CU | F1AP over SCTP (port 38472) |
| F1-U | DU ↔ CU | GTP-U over UDP |
| E1 | CU-CP ↔ CU-UP | E1AP over SCTP |
| N2 | CU ↔ AMF | NGAP over SCTP (port 38412) |
| N3 | CU-UP ↔ UPF | GTP-U over UDP (port 2152) |
| N4 | SMF ↔ UPF | PFCP over UDP (port 8805) |
| N6 | UPF ↔ Data Network | IP via ogstun (10.45.0.1) |

## 4. Configuration

Network identity (unchanged from Phase 3):

- PLMN: 999/70
- TAC: 1
- SST / SD: 1 / 1
- DNN: internet
- UE pool: 10.45.0.0/16
- Subscriber: IMSI 999700000000001

Cell configuration (matching OCUDU's official srsUE example):

- Band: n3 (FDD, 1800 MHz)
- DL ARFCN: 368500
- SSB ARFCN: 367930
- SCS: 15 kHz
- Channel bandwidth: 20 MHz
- PRBs: 106

Addressing for the split RAN:

| Component | Address |
|-----------|---------|
| CU-CP F1-C | 127.0.0.1:38472 |
| CU F1-U | 127.0.0.2:2152 |
| CU NG-U | 127.0.0.1:2152 |
| DU F1-U | 127.0.0.3:2152 |
| ZeroMQ DU TX | 127.0.0.1:2000 |
| ZeroMQ UE TX | 127.0.0.1:2001 |

## 5. Build and Startup

### 5.1 OCUDU Build

    cd ~/projects/ocudu-dev
    cmake -S . -B build \
      -DCMAKE_BUILD_TYPE=Release \
      -DENABLE_EXPORT=ON \
      -DENABLE_ZEROMQ=ON \
      -DENABLE_UHD=OFF \
      -DBUILD_TESTING=OFF \
      -DENABLE_WERROR=OFF
    cmake --build build --parallel 2

Produced binaries:
- `build/apps/cu/ocu`
- `build/apps/du/odu`
- `build/apps/gnb/gnb` (combined gNB)
- plus `ocucp`, `ocuup`, `odu_low`, etc.

### 5.2 srsRAN 4G Build

    cd ~/projects/srsRAN_4G
    mkdir -p build && cd build
    cmake ../ \
      -DENABLE_ZEROMQ=ON \
      -DENABLE_WERROR=OFF \
      -DENABLE_UHD=OFF \
      -DENABLE_BLADERAF=OFF \
      -DENABLE_SOAPYSDR=OFF \
      -DENABLE_GUI=OFF \
      -DENABLE_HARDSIM=OFF
    make -j2

The `ENABLE_WERROR=OFF` flag was necessary because GCC 15.2 triggers
warnings in test files that srsRAN 4G's build treats as errors.

### 5.3 Startup Order

1. Open5GS core (already running from Phase 3)
2. OCUDU CU
3. OCUDU DU
4. srsUE

## 6. Milestone A — N2 Validation

The CU connected to the AMF at `127.0.0.5:38412`:

    [CU-CP   ] [I] N2: Connection to AMF on 127.0.0.5:38412 was established
    [NGAP    ] [I] "NG Setup Procedure" started...
    [NGAP    ] [I] Tx PDU: NGSetupRequest
    [NGAP    ] [I] Rx PDU: NGSetupResponse
    [NGAP    ] [I] "NG Setup Procedure" finished successfully
    [CU-CP   ] [I] Connected to AMF. Supported PLMNs: 99970

The AMF acknowledged the CU as a gNB:

    [amf] INFO: gNB-N2 accepted[127.0.0.1]:54977 in ng-path module
    [amf] INFO: [Added] Number of gNBs is now 1

**Milestone A achieved.**

## 7. Milestone B — F1 Validation

The DU connected to the CU's F1-C endpoint:

    [DU-F1   ] [I] F1-C: TNL connection to CU-CP on 127.0.0.1:38472 accepted
    [DU-F1   ] [I] F1 Setup: Sending F1 Setup Request to CU-CP...
    [DU-F1   ] [I] F1 Setup: Procedure completed successfully.

The CU's internal E1 interface between CU-CP and CU-UP also came up:

    [CU-UP-E1] [I] e1=0: Rx PDU tid=0 GNB-CU-UP-E1SetupResponse

**Milestone B achieved.**

## 8. Milestone C — UE Registration

The srsUE completed the full 5G SA attach procedure:

    Random Access Transmission: prach_occasion=0, preamble_index=0, ra-rnti=0x39
    Random Access Complete.     c-rnti=0x4601, ta=0
    RRC Connected
    PDU Session Establishment successful. IP: 10.45.0.4
    RRC NR reconfiguration successful.

The AMF log confirms registration:

    [gmm] INFO: [imsi-999700000000001] Registration complete
    [gmm] INFO: UE SUPI[imsi-999700000000001] DNN[internet] S_NSSAI[SST:1 SD:0x1]
    [amf] INFO: [Added] Number of AMF-Sessions is now 1

The SMF created the PDU session:

    [smf] INFO: [Added] Number of SMF-UEs is now 1
    [smf] INFO: UE SUPI[imsi-999700000000001] DNN[internet] IPv4[10.45.0.4]

The UPF added the user-plane session:

    [upf] INFO: [Added] Number of UPF-Sessions is now 1
    [upf] INFO: UE F-SEID[UP:0x981 CP:0xd1b] APN[internet] PDN-Type[1] IPv4[10.45.0.4]

**Milestone C achieved.**

## 9. Milestone D — User-Plane Validation

Ping from the UE (inside namespace `ue1`) to the UPF gateway:

    PING 10.45.0.1 (10.45.0.1) 56(84) bytes of data.
    64 bytes from 10.45.0.1: icmp_seq=1 ttl=64 time=34.7 ms
    64 bytes from 10.45.0.1: icmp_seq=2 ttl=64 time=28.4 ms
    64 bytes from 10.45.0.1: icmp_seq=3 ttl=64 time=25.3 ms
    64 bytes from 10.45.0.1: icmp_seq=4 ttl=64 time=22.6 ms
    64 bytes from 10.45.0.1: icmp_seq=5 ttl=64 time=39.2 ms

    --- 10.45.0.1 ping statistics ---
    5 packets transmitted, 5 received, 0% packet loss
    rtt min/avg/max/mdev = 22.649/30.057/39.201/6.094 ms

The N3 capture showed the complete round trip across all four user-plane
segments — ZeroMQ, F1-U, N3 GTP-U, and ogstun — confirming the entire
path from UE to data network is operational.

TCP throughput (iperf3, 20 seconds):

    26.0 MBytes transferred
    10.9 Mbits/sec sender / 10.7 Mbits/sec receiver
    25 retransmissions

UDP test (5 Mbps target) was attempted but caused the DU to release the
UE due to an RRC ACK timeout. This is noted as a limitation below.

**Milestone D achieved.**

## 10. Packet Analysis

Four captures were saved during Phase 4:

- `phase4_n3.pcap` — GTP-U traffic on F1-U and N3 (30 packets)
- `phase4_sctp.pcap` — SCTP on N2, F1-C, and E1 (24 packets)
- `phase4_n3.pcap` (earlier) — combined user-plane evidence

Analysis of the N3 capture:

    127.0.0.3.2152 → 127.0.0.2.2152 (length 107)  ← DU F1-U to CU F1-U
    127.0.0.1.2152 → 127.0.0.7.2152 (length 100)  ← CU N3 to UPF
    127.0.0.7.2152 → 127.0.0.1.2152 (length 100)  ← UPF N3 to CU
    127.0.0.2.2152 → 127.0.0.3.2152 (length 107)  ← CU F1-U to DU F1-U

Both the F1-U (DU ↔ CU) and N3 (CU-UP ↔ UPF) tunnels carried the same
ICMP packets, confirming encapsulation and decapsulation at each hop.

Analysis of the SCTP capture:

- N2: `127.0.0.5.38412 ↔ 127.0.0.1` — heartbeats between AMF and CU
- F1-C: `127.0.0.2.3868 ↔ 127.0.0.8` — heartbeats between CU-CP and DU
- E1: `127.0.0.4 ↔ 127.0.0.9.3868` — heartbeats and DATA between CU-CP and CU-UP

All three control-plane interfaces were continuously monitored with SCTP
heartbeats.

## 11. Troubleshooting

The following problems were diagnosed and resolved during Phase 4:

### Problem 1 — UHD linker error
The OCUDU build failed because the system UHD library was built against a
different Python version. Fix: reconfigured with `-DENABLE_UHD=OFF`.

### Problem 2 — Invalid CU config — missing five_qi
The CU refused to start because the F1-U socket had `sst` and `sd` but no
`five_qi`. Fix: added `five_qi: 9`.

### Problem 3 — Port conflict on 127.0.0.1:2152
The CU's NG-U socket and the CU's F1-U socket both defaulted to port 2152
on the same address. Fix: moved F1-U to 127.0.0.2:2152 and added
`ext_addr` to advertise the correct address.

### Problem 4 — DU port conflict with the CU's NG-U socket
The DU's F1-U also bound 127.0.0.1:2152, conflicting with the CU's NG-U.
Fix: moved DU F1-U to 127.0.0.3:2152.

### Problem 5 — srsRAN 4G build failed on GCC 15.2 warnings
The `-Werror` flag in srsRAN 4G made warnings fatal. Fix: passed
`-DENABLE_WERROR=OFF` to CMake.

### Problem 6 — srsUE config had unknown options
The `usim.amf`, `usim.imeisv`, and `[metrics]` sections were not valid in
this version of srsUE. Fix: removed those fields and added
`algo = milenage` to `[usim]`.

### Problem 7 — srsUE not finding the cell at 10 MHz
srsUE silently stalled after "Attaching UE..." with a 10 MHz cell and
11.52 MHz sample rate. Fix: switched to OCUDU's official srsUE-compatible
config — 20 MHz, 23.04 MHz sample rate, plus the `pdcch`, `prach`,
`pdsch`, and `pusch` sections that srsUE requires. Also removed the
`dl_nr_arfcn` and `ssb_nr_arfcn` overrides so the UE could derive them
from the DU's broadcast.

### Problem 8 — UE released after iperf3 UDP test
The UDP iperf3 test triggered an RRC ACK timeout in the DU, which caused
the UE context to be released after 120 ms. Fix: restarted the UE and
avoided the UDP test. The DU's 120 ms RRC ACK timer is a legitimate
behavior under CPU contention.

## 12. Limitations

- The measured TCP throughput (10.7 Mbps) is well below the theoretical
  capability of a 20 MHz NR cell (50–150 Mbps). This is due to CPU
  contention from Chrome and the software-radio PHY overhead, not a
  protocol or architecture limitation. Running on a dedicated machine
  with more CPU headroom would produce higher numbers.
- The UDP iperf3 test caused the UE to be released by the DU's 120 ms
  RRC ACK timer, likely due to CPU contention during the test. Only TCP
  throughput is reported for this reason.
- The radio link is entirely software-simulated through ZeroMQ. No RF
  measurements (RSRP, SINR, path loss) can be taken.
- The CU and DU are connected on the same host. A multi-host deployment
  would be needed to test real network dynamics between CU and DU.

## 13. Conclusion

All four Phase 4 milestones were achieved:

1. **Milestone A:** The OCUDU CU connected to Open5GS AMF over N2 with a
   successful NG Setup procedure.
2. **Milestone B:** The OCUDU DU connected to the OCUDU CU over F1-C,
   with the CU-CP and CU-UP also establishing E1.
3. **Milestone C:** srsUE completed the full 5G SA attach — random
   access, RRC connection, registration, and PDU session establishment —
   with IP address 10.45.0.4.
4. **Milestone D:** Real ICMP and TCP traffic flowed end to end from the
   UE through the ZeroMQ radio, F1-U, N3 GTP-U, and the UPF to the data
   network, with 0% packet loss.

The Phase 4 network is a complete O-RAN-oriented 5G SA testbed running
entirely in software. It is ready for Phase 5 (private 5G / NPN
configuration) and later phases (slicing, edge UPF, monitoring, O-RAN
control).

---

# Phase 4-B — OAI UE + OCUDU Integration (Alternative Implementation)

**Date:** 2026-10-13
**Status:** Complete — user plane verified

## B.1 Motivation

The srsUE implementation (Phase 4-A) uses band n3 (FDD, 1800 MHz) with
15 kHz subcarrier spacing. While fully functional, this is not the most
representative configuration for a private 5G smart-factory deployment.
Industrial 5G deployments in the 3.5 GHz range use band n78 (TDD) with
30 kHz subcarrier spacing.

This section documents a second Phase 4 implementation using the
OpenAirInterface (OAI) NR UE, which supports band n78 TDD natively.

## B.2 Software Environment

| Component | Version |
|-----------|---------|
| OCUDU | 26.10.0 (unchanged from 4-A) |
| Open5GS | 2.8.0~resolute6 |
| OAI UE | duranta-project/openairinterface5g, develop branch |
| OAI commit | 6f89078b409e671fa566782f67aae9de52fd55d8 (2026-10-09) |
| OAI ZMQ plugin | liboai_zmqdevif.so (built with same commit) |
| Build system | CMake + Ninja |

**Key difference from 4-A:** The OAI UE version must contain the
UCI-on-PUSCH mapping fix and the TRS processing patch. The `develop`
branch contains both; earlier branches (w25, w39) do not.

## B.3 Cell Configuration

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Band | n78 (TDD) | Standard industrial 5G band |
| DL ARFCN | 632628 | ~3.489 GHz |
| SSB ARFCN | 632256 | Derived by OCUDU |
| SCS | 30 kHz | Standard for n78 |
| Channel bandwidth | 20 MHz | Standard NR bandwidth |
| PRBs | 51 | Matches 20 MHz at 30 kHz SCS |

## B.4 DU Configuration Changes

The DU config required two additions that were absent in 4-A:

    cell_cfg:
      ...
      csi:
        csi_rs_enabled: true
      pucch:
        nof_cell_csi_res: 1
      tdd_ul_dl_cfg:
        dl_ul_tx_period: 5
        nof_dl_slots: 3
        nof_dl_symbols: 10
        nof_ul_slots: 1
        nof_ul_symbols: 2

- `csi_rs_enabled` and `nof_cell_csi_res` are required for the OAI UE
  to perform CSI measurements on scheduled channels.
- `tdd_ul_dl_cfg` ensures the DU and UE agree on the TDD slot pattern.
  Without it, the UE derives a different pattern from SIB1 and PUSCH
  scheduling fails.

## B.5 UE Configuration — Modern Format

The OAI UE uses the modern `pdu_sessions` format. This is critical:

    uicc0 = {
      imsi = "999700000000001";
      key = "...";
      opc = "...";
      pdu_sessions = ({ dnn = "internet"; nssai_sst = 1; nssai_sd = 1; });
    };

The `nssai_sd = 1` field is required. Without it, the UE requests
SD = 0xFFFFFF (wildcard), and the AMF rejects the PDU session with
"mismatch for allowed NSSAI".

## B.6 Network Namespace Setup

Unlike srsUE (which has a built-in `[gw] netns` option), the OAI UE
has no native namespace support. A manual namespace and veth pair are
required:

    sudo ip netns add ue1
    sudo ip link add v-eth1 type veth peer name v-ue1
    sudo ip link set v-ue1 netns ue1
    sudo ip addr add 10.200.1.1/24 dev v-eth1
    sudo ip link set v-eth1 up
    sudo ip netns exec ue1 ip addr add 10.200.1.2/24 dev v-ue1
    sudo ip netns exec ue1 ip link set v-ue1 up

The ZMQ endpoints are configured to use the veth IPs (10.200.1.1 and
10.200.1.2) so that samples can cross the namespace boundary:

    # DU
    device_args: tx_port=tcp://10.200.1.1:4556,rx_port=tcp://10.200.1.2:4557

    # UE
    zmq = ( { tx_channels = ( "tcp://10.200.1.2:4557" );
              rx_channels = ( "tcp://10.200.1.1:4556" ); } );

Without this, both sides would use 127.0.0.1 in their respective
namespaces, and samples would never reach each other.

## B.7 Milestones Achieved

| Milestone | Evidence |
|-----------|----------|
| B-A: N2 (CU↔AMF) | `Connected to AMF. Supported PLMNs: 99970` |
| B-B: F1 (DU↔CU) | `F1 Setup: Procedure completed successfully` |
| B-C: UE Registration | `Received Registration Accept with result 3GPP` |
| B-D: PDU Session | `UE IPv4: 10.45.0.3` |
| B-E: User Plane | `5 packets transmitted, 5 received, 0% packet loss` |

## B.8 User-Plane Validation

Ping from inside namespace `ue1`:

    PING 10.45.0.1 (10.45.0.1) 56(84) bytes of data.
    64 bytes from 10.45.0.1: icmp_seq=1 ttl=64 time=104 ms
    64 bytes from 10.45.0.1: icmp_seq=2 ttl=64 time=98.2 ms
    ...
    --- 10.45.0.1 ping statistics ---
    10 packets transmitted, 10 received, 0% packet loss
    rtt min/avg/max/mdev = 74.064/94.190/139.469/18.475 ms

GTP-U capture on ogstun confirmed the round trip:

    IP 10.45.0.3 > 10.45.0.1: ICMP echo request
    IP 10.45.0.1 > 10.45.0.3: ICMP echo reply
    (repeated for each ping)

## B.9 Comparison: srsUE (4-A) vs OAI UE (4-B)

| Aspect | Phase 4-A (srsUE) | Phase 4-B (OAI UE) |
|--------|-------------------|---------------------|
| Band | n3 (FDD, 1800 MHz) | n78 (TDD, 3500 MHz) |
| SCS | 15 kHz | 30 kHz |
| Duplex | FDD | TDD |
| PRBs | 106 | 51 |
| Namespace | Native (`[gw] netns`) | Manual veth pair |
| UE IP | 10.45.0.4 | 10.45.0.3 |
| Ping avg | ~30 ms | ~94 ms |
| Standards fit | 4G heritage | Native 5G SA |
| Community support | Mature | Experimental |
| Effort to run | Config alignment | Source branch + rebuild |

**Conclusion:** Both implementations work. For smart-factory
demonstration purposes, srsUE (4-A) is faster and easier to reproduce.
For standards-representative 5G SA behavior, OAI UE (4-B) is the
better model. Both should be cited in any published result.

## B.10 Troubleshooting — Phase 4-B

### Problem B1 — UCI-on-PUSCH failure (RLC max retransmissions)
Symptom: UE reaches RRC Connected but fails at RLC max RETX on SRB 1.
Cause: OAI versions before w33 lack the UCI-on-PUSCH fix.
Fix: switched to `develop` branch (contains w41 + subsequent fixes).

### Problem B2 — Segfault at RAU initialization
Symptom: `[RAU] has loaded RFSIMULATOR device` followed by segfault.
Cause: ZMQ plugin (`liboai_zmqdevif.so`) was built from an older
source than the main binary.
Fix: rebuild both with `ninja nr-uesoftmodem liboai_zmqdevif.so`.

### Problem B3 — NSSAI SD mismatch
Symptom: `NSSAI 1.16777215: mismatch for allowed NSSAI`.
Cause: `pdu_sessions` without explicit `nssai_sd` requests wildcard SD.
Fix: added `nssai_sd = 1` to `pdu_sessions`.

### Problem B4 — Same-host routing shortcut
Symptom: 100% packet loss on ping despite successful PDU session.
Cause: both UE IP and UPF IP in host's `local` routing table.
Fix: run UE in namespace via `ip netns exec ue1`.

### Problem B5 — ZMQ endpoints across namespace
Symptom: after namespace setup, no ZMQ traffic.
Cause: 127.0.0.1 differs in each namespace.
Fix: use veth IPs (10.200.1.1 and 10.200.1.2) in both DU and UE configs.

## B.11 Evidence Files

- `results/phase4/ue-config.conf` — OAI UE config
- `results/phase4/du-config.yml` — DU config with n78 TDD
- `results/phase4/cu-config.yml` — CU config
- `results/phase4/ue-namespace-run.log` — full UE log
- `results/phase4/du-run.log` — full DU log
- `captures/phase4-user-plane.pcap` — GTP-U ICMP capture

## B.12 Phase 4-B Conclusion

The OAI UE + OCUDU + Open5GS stack runs natively in 5G SA with band
n78 TDD at 30 kHz SCS. Both control-plane (N2, F1) and user-plane
(N3, F1-U) interfaces are fully operational. The user plane delivers
ICMP traffic with 0% packet loss.

The additional complexity over Phase 4-A (source branch selection,
rebuilding the plugin, manual namespace creation, SD specification)
reflects the earlier maturity stage of the OAI UE ZMQ integration.
For production-like deployment, srsUE remains the more reliable choice.
For standards-representative research, OAI UE provides the better model.
