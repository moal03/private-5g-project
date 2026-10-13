# Phase 5 Report — Private 5G Network (NPN)

**Project:** Private 5G Network — Smart Factory Scenario
**Author:** Mohammad
**Date:** 2026-10-13
**Environment:** Ubuntu 26.04 LTS (resolute), kernel 7.0.0-38-generic, 8 CPU cores, 14 GiB RAM

---

## 1. Objective

Design and validate a private 5G network for a smart-factory scenario. The network must:

- Serve only authorised devices (configured test subscriber)
- Provide a dedicated factory data network separate from ordinary internet connectivity
- Enforce traffic isolation between the internet data network and the factory data network
- Produce reproducible, observable evidence for every claim

## 2. Network Model

The 3GPP architecture defines two principal Non-Public Network (NPN) models:

- **SNPN (Stand-alone NPN):** the private network operates independently of public PLMN network functions. Identity is the pair (PLMN ID, NID). Two NID assignment models exist: self-assignment and coordinated assignment.
- **PNI-NPN (Public Network Integrated NPN):** the private network is deployed with support of a public PLMN. Isolation is achieved through a dedicated DNN, a dedicated S-NSSAI, or a Closed Access Group (CAG).

**Implemented in this project:** a lab-scale private 5G network with its own Open5GS core, its own OCUDU CU/DU RAN, a dedicated factory DNN named `factory` separate from the existing `internet` DNN, and host-level firewall isolation between the two DNNs.

This corresponds to a **PNI-NPN-style architecture at the DNN level**, running in a lab with the test PLMN 999/70. It is not a standards-complete SNPN deployment, because SNPN-specific behaviour (PLMN+NID assignment and SNPN-specific network selection) is not implemented. This distinction is stated explicitly to keep the report technically honest.

## 3. Use Case and Requirements

Three logical device groups, mapped to real industrial requirements derived from 5G-ACIA and 3GPP TS 22.104:

| Group | Example Devices | Representative 5G-ACIA Use Case | Key KPIs |
|-------|-----------------|--------------------------------|----------|
| Industrial Control | Robots, PLCs, machine-control gateways | Autonomous Mobile Robots (AMR) | Latency <= 10 ms, reliability 99.999%, message size 40-250 bytes |
| Telemetry and Monitoring | Sensors, gateways | Massive Wireless Sensor Networks | Latency <= 100 ms, data rate 1-100 kbps per device |
| Maintenance and Administration | Engineering terminals, AR devices | AR-assisted maintenance, remote access | Latency <= 50 ms, uplink 4-8 Mb/s |

Observable requirements implemented in this lab:

1. Private access — only a configured subscriber can register
2. Private application — the UE can reach an internal factory server
3. Traffic isolation — traffic from the internet DNN cannot reach the factory network
4. Controlled administration — access to factory services requires the factory DNN
5. Observability — the firewall enforces and counts every dropped packet
6. Reproducibility — the entire configuration is scriptable and persistent

## 4. Architecture

The user-plane path from the UE to the factory application traverses the following layers, in order:

1. The UE runs inside the Linux network namespace `ue1`. It has two TUN interfaces assigned by the OAI UE process: `oaitun_ue1` with address 10.45.0.2 (internet DNN) and `oaitun_ue1p2` with address 10.46.0.2 (factory DNN).
2. The UE process communicates with the OCUDU Distributed Unit over ZeroMQ sample transport across the veth pair connecting `ue1` (10.200.1.2) to the host (10.200.1.1).
3. The OCUDU DU runs the physical, MAC, and RLC layers for band n78 TDD at 30 kHz subcarrier spacing with 20 MHz channel bandwidth.
4. The DU connects to the OCUDU Central Unit over the F1 interface (F1-C for control, F1-U for user data over GTP-U).
5. The OCUDU CU runs the CU-CP and CU-UP functions combined in a single process (`ocu`). It connects to the Open5GS core over N2 (NGAP/SCTP to the AMF) and N3 (GTP-U over UDP to the UPF).
6. Open5GS runs seventeen core network functions including AMF, SMF, UPF, AUSF, UDM, UDR, NRF, and others.
7. The UPF's tunnel interface `ogstun` carries user-plane traffic. It holds two gateways: 10.45.0.1/16 for the internet DNN and 10.46.0.1/16 for the factory DNN.
8. From `ogstun`, traffic is forwarded by the host kernel. Firewall rules on the host forward path enforce DNN isolation.
9. The factory application is served from a separate Linux network namespace called `factory-app`, reachable at 10.60.0.10 through the host interface `factory-host` (10.60.0.1).

## 5. Addressing Plan

| Purpose | Address | Interface |
|---------|---------|-----------|
| Internet UE pool | 10.45.0.0/16 | oaitun_ue1 (UE IP = 10.45.0.2) |
| Factory UE pool | 10.46.0.0/16 | oaitun_ue1p2 (UE IP = 10.46.0.2) |
| UPF internet gateway | 10.45.0.1 | ogstun |
| UPF factory gateway | 10.46.0.1 | ogstun |
| Factory app subnet | 10.60.0.0/24 | factory-host / factory-ns |
| Factory host side | 10.60.0.1 | factory-host |
| Factory application server | 10.60.0.10 | factory-ns |
| Namespace veth | 10.200.1.0/24 | v-eth1 / v-ue1 |

No subnet overlap exists with the Open5GS core loopback addresses (127.0.0.x), which is required for unambiguous routing.

## 6. Subscriber and Session Configuration

Subscriber 999700000000001 was extended in Phase 5 to include:

- Slice: SST = 1, SD = 000001
- Two PDU sessions under the same slice: `internet` and `factory`
- Both with 5QI = 9 and default ARP

SMF and UPF session configuration (identical in both files):

    session:
      - subnet: 10.45.0.0/16
        gateway: 10.45.0.1
        dnn: internet
      - subnet: 2001:db8:cafe::/48
        gateway: 2001:db8:cafe::1
        dnn: internet
      - subnet: 10.46.0.0/16
        gateway: 10.46.0.1
        dnn: factory

Both files were validated with `yaml.safe_load` before restarting the services.

## 7. Factory Data Network

A Linux network namespace `factory-app` simulates the factory application server:

- veth pair `factory-host` (host side) and `factory-ns` (namespace side)
- Application server on 10.60.0.10 running Python's built-in HTTP server on port 8080
- A static route back to the UE factory pool: `10.46.0.0/16 via 10.60.0.1`

The veth approach isolates the factory application from the host's ordinary network stack, which is closer to a real deployment than binding a server on the host's primary interface.

## 8. Access Control

DNN isolation is enforced at the host forwarding layer using nftables, not only at the UE's routing table. This ensures the isolation holds even if the UE is compromised and its route table is modified.

Rules installed:

    table inet filter {
        chain forward {
            type filter hook forward priority filter; policy accept;
            ip saddr 10.45.0.0/16 ip daddr 10.60.0.0/24 counter drop
            ip saddr 10.60.0.0/24 ip daddr 10.45.0.0/16 counter drop
        }
    }

The `counter` keyword ensures every dropped packet is counted, which provides measurable evidence for the isolation claim. Rules are persisted via the systemd service `nftables-phase5.service`, enabled at boot.

## 9. Test Results

| Test | Description | Result |
|------|-------------|--------|
| NPN-01 | Start core, CU, DU, UE | PASS |
| NPN-02 | UE registers with the core | PASS (Registration Accept received) |
| NPN-03 | Factory DNN session established | PASS (PDU Session ID 2 accepted) |
| NPN-04 | UE receives factory IP | PASS (10.46.0.2 assigned) |
| NPN-05 | UE reaches factory application | PASS (0% loss ping, HTTP 200) |
| NPN-06 | Unauthorised destination blocked | PASS (100% loss, firewall counters increased) |
| NPN-07 | Return path verification | PASS (verified via routing and pings) |
| NPN-08 | Reproducibility after restart | PASS (services enabled and tested) |
| NPN-09 | Evidence captured | PASS (results/phase5/ directory) |
| NPN-10 | Configuration review for secrets | PASS (no credentials in repo) |

Detailed evidence is in `results/phase5/connectivity-tests.txt`:

- Test 1 (UE to internet gateway 10.45.0.1): 3/3 packets received, 0% loss
- Test 2 (UE to factory server 10.60.0.10 via factory DNN): 3/3 packets, 0% loss
- Test 3 (UE to factory server forced via internet DNN): 0/3 packets, 100% loss
- Test 4 (HTTP request from UE to factory server via factory DNN): HTTP 200 with directory listing
- Test 5 (firewall counter after Test 3): 6 packets dropped total

## 10. Troubleshooting

### Problem 1 — Factory gateway missing on ogstun after restart

**Symptom:** Pings from the UE to the factory server failed silently after restarting the UPF.
**Cause:** Open5GS UPF only adds an ogstun gateway when a UE requests that DNN. The factory gateway was added manually and was not persistent.
**Fix:** Created a systemd service `phase5-ogstun-factory-gw.service` that runs after `open5gs-upfd.service` and ensures `10.46.0.1/16` is present on ogstun.

### Problem 2 — factory-app namespace could not reply to UE

**Symptom:** The UE could send packets to 10.60.0.10 but replies never arrived.
**Cause:** The `factory-app` namespace had no route to the UE factory pool (10.46.0.0/16).
**Fix:** Added `ip route add 10.46.0.0/16 via 10.60.0.1` inside the namespace.

### Problem 3 — UE could not reach 10.60.0.0/24

**Symptom:** The UE had a factory IP but could not reach the factory application subnet.
**Cause:** The UE namespace's routing table had no entry for 10.60.0.0/24.
**Fix:** Added `ip route add 10.60.0.0/24 dev oaitun_ue1p2` inside the UE namespace.

### Problem 4 — Same-host routing shortcut (carried over from Phase 4)

**Symptom:** Traffic between the UE and the UPF would take the kernel's `lo` shortcut, bypassing the GTP-U tunnel.
**Cause:** Both the UE IP and the UPF gateway IP were present in the host's local routing table.
**Fix:** The UE continues to run inside namespace `ue1`, keeping its IPs invisible to the host kernel.

## 11. Security Considerations

- **Subscriber credentials:** Only test values are used. The authentication key (K) and operator code (OPc) are documented as lab-only and are not production secrets.
- **Management interface:** Open5GS WebUI is not installed (unavailable on this Ubuntu release). Subscriber management is done via a local MongoDB connection.
- **Firewall policy:** Default-accept at the host forwarding layer, with explicit DNN isolation rules. This is intentional so that factory traffic between the two namespaces is allowed, while traffic from internet DNN to factory network is blocked.
- **Configuration backups:** All Phase 4 configurations are preserved as `*.phase4-working` snapshots in the project repo. The Phase 5 configs are stored as `*.phase5`.
- **Evidence:** All saved logs and pcaps are sanitised. Authentication secrets do not appear in any committed file.

## 12. Limitations

- The lab demonstrates DNN-level isolation but is not a standards-complete SNPN. SNPN-specific features (PLMN+NID, SNPN network selection) are not implemented.
- Firewall isolation is enforced at the host's forwarding layer, not inside the UPF itself. A truly hardened deployment would enforce policies at the UPF.
- The factory application is a Python HTTP server. It demonstrates reachability but is not an industrial protocol or real control system.
- No Closed Access Group (CAG) is configured. Access control relies on subscriber authorisation (which DNNs a subscriber may use) and firewall policy (which destinations a DNN may reach).
- The radio link is software-simulated through ZeroMQ. No RF measurements are possible.

## 13. Conclusion

Phase 5 delivers a functional private 5G network with:

1. A dedicated factory DNN alongside the existing internet DNN
2. Verified DNN-level isolation enforced by firewall counters
3. A reachable factory application server accessible only from the factory DNN
4. Persistent, reproducible startup via systemd services
5. A complete test suite with PASS/FAIL evidence

The network is ready for Phase 6 (Network Slicing and QoS), which will investigate whether different traffic classes receive different treatment and whether resource isolation can be observed across slices.
