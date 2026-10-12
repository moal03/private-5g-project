# Phase 3 Report — First Working 5G Standalone Network

**Project:** Private 5G Network — Smart Factory Scenario
**Author:** Mohammad
**Date:** 2026-10-12
**Environment:** Ubuntu 26.04 LTS (resolute), kernel 7.0.0-38-generic, 8 CPU cores, 14 GiB RAM

---

## 1. Objective

Establish a software-based 5G Standalone (5G SA) network using Open5GS as
the 5G Core and UERANSIM as the simulated RAN and UE. Register a simulated
device, establish a PDU session, assign it an IP address, pass traffic
through the user plane, and prove that the system works using logs and
packet captures.

## 2. System Environment

| Component | Version |
|-----------|---------|
| Operating System | Ubuntu 26.04 LTS (resolute) |
| Kernel | 7.0.0-38-generic |
| CPU | 8 cores |
| RAM | 14 GiB |
| Disk | 304 GB (240 GB free) |
| Open5GS | 2.8.0~resolute6 |
| UERANSIM | v3.3.0 |
| FerretDB | v1.24.2 |
| PostgreSQL | 18.6 |
| mongosh | 2.13.0 |

## 3. Architecture

- **Simulated UE:** UERANSIM nr-ue running inside a Linux network namespace
- **Simulated gNB:** UERANSIM nr-gnb
- **5G Core:** Open5GS (AMF, SMF, UPF, AUSF, UDM, UDR, NRF, PCF, NSSF)
- **Subscriber store:** FerretDB (MongoDB wire protocol) backed by PostgreSQL
- **UPF tunnel interface:** ogstun (10.45.0.1/16)
- **UE address pool:** 10.45.0.0/16
- **Data network:** the host's ogstun interface acts as the N6 anchor for this lab

Key interfaces used:

| Interface | Endpoint A | Endpoint B | Protocol |
|-----------|-----------|-----------|----------|
| N2 | gNB (127.0.0.1) | AMF (127.0.0.5:38412) | NGAP over SCTP |
| N3 | gNB (127.0.0.1:2152) | UPF (127.0.0.7:2152) | GTP-U over UDP |
| N4 | SMF (127.0.0.4:8805) | UPF (127.0.0.7:8805) | PFCP over UDP |
| N6 | UPF | ogstun | IP |

## 4. Addressing and Configuration

| Parameter | Value |
|-----------|-------|
| PLMN | MCC=999, MNC=70 |
| TAC | 1 |
| S-NSSAI | SST=1, SD=000001 |
| DNN | internet |
| IMSI | 999700000000001 |
| UE IP (this session) | 10.45.0.2 |
| UE pool | 10.45.0.0/16 |
| UPF gateway | 10.45.0.1 |

## 5. Installation and Startup

### 5.1 Open5GS

    sudo add-apt-repository ppa:open5gs/latest
    sudo apt update
    sudo apt install -y open5gs

Verification:

    dpkg -l | grep open5gs
    systemctl list-unit-files 'open5gs-*'

### 5.2 Subscriber Store

MongoDB 8.0 was unusable because:
- MongoDB does not support kernels 6.19+
- The MongoDB apt repository returns 403 Forbidden

Solution: FerretDB v1.24.2 + PostgreSQL 18.

    sudo apt install -y postgresql
    sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'open5gs';"

    # Download and install FerretDB 1.24.2
    wget https://github.com/FerretDB/FerretDB/releases/download/v1.24.2/ferretdb-linux-amd64
    sudo mv ferretdb-linux-amd64 /usr/local/bin/ferretdb
    sudo chmod +x /usr/local/bin/ferretdb

    # systemd service
    sudo tee /etc/systemd/system/ferretdb.service <<'EOF'
    [Unit]
    Description=FerretDB
    After=network.target postgresql.service
    Requires=postgresql.service

    [Service]
    Type=simple
    ExecStart=/usr/local/bin/ferretdb \
      --handler=pg \
      --postgresql-url=postgres://postgres:open5gs@localhost:5432/postgres \
      --listen-addr=127.0.0.1:27017
    Restart=on-failure
    User=root

    [Install]
    WantedBy=multi-user.target
    EOF

    sudo systemctl daemon-reload
    sudo systemctl enable --now ferretdb

### 5.3 Subscriber Provisioning

    mongosh open5gs --quiet --eval '
    db.subscribers.insertOne({
      imsi: "999700000000001",
      security: {
        k: "465B5CE8B199B49FAA5F0A2EE238A6BC",
        op: null,
        opc: "E8ED289DEBA952E4283B54E88E6183CA",
        amf: "8000"
      },
      sqn: NumberLong("000000000023"),
      ambr: { downlink: { value: 1, unit: 3 }, uplink: { value: 1, unit: 3 } },
      slice: [{
        sst: 1, sd: "000001", default_indicator: true,
        session: [{
          name: "internet", type: 3,
          qos: { index: 9, arp: { priority_level: 8,
                                  pre_emption_capability: 1,
                                  pre_emption_vulnerability: 1 } },
          ambr: { downlink: { value: 1, unit: 3 }, uplink: { value: 1, unit: 3 } }
        }]
      }],
      access_restriction_data: 32,
      subscriber_status: 0,
      network_access_mode: 0,
      subscribed_rau_tau_timer: 12
    })
    '

### 5.4 AMF Configuration

The AMF `plmn_support` section was edited to explicitly include SD 000001:

    plmn_support:
      - plmn_id:
          mcc: 999
          mnc: 70
        s_nssai:
          - sst: 1
            sd: 000001

### 5.5 UERANSIM Build

    git clone https://github.com/aligungr/UERANSIM.git
    cd UERANSIM
    make -j"$(nproc)"

### 5.6 UERANSIM Configurations

- gNB slice: sst=1, sd=1
- UE slices: sst=1, sd=1 (in sessions, configured-nssai, default-nssai)
- UE useNamespace: true (critical for same-host deployments)

## 6. Registration and Authentication

Sanitized UE log excerpt:

    [nas] [debug] Authentication Request received
    [nas] [debug] Received SQN [000000000221]
    [nas] [debug] Security Mode Command received
    [nas] [info] UE switches to state [MM-REGISTERED/NORMAL-SERVICE]
    [nas] [info] Initial Registration is successful
    [nas] [info] PDU Session establishment is successful PSI[1]
    [app] [info] Connection setup for PDU session[1] is successful,
                TUN interface[uesimtun0, 10.45.0.2] is up
                in namespace[ueransim-999700000000001-internet-psi1].

The AMF log showed a corresponding sequence of NGAP InitialUEMessage,
Registration request, and PDU session establishment for the same SUCI.

## 7. PDU Session Establishment

- Requested DNN: internet
- Requested S-NSSAI: SST=1, SD=000001
- Assigned UE address: 10.45.0.2
- Assigned tunnel interface: uesimtun0 (inside the UE's namespace)
- Namespace: ueransim-999700000000001-internet-psi1

UPF log confirmed the session:

    [upf] INFO: [Added] Number of UPF-Sessions is now 1
    [upf] INFO: UE F-SEID[UP:0x68f CP:0x96a] APN[internet]
                PDN-Type[1] IPv4[10.45.0.2]

## 8. User-Plane Validation

All measurements were performed from inside the UE's namespace:

    sudo ip netns exec ueransim-999700000000001-internet-psi1 \
      ping -c 5 10.45.0.1

Result:

    5 packets transmitted, 5 received, 0% packet loss
    rtt min/avg/max/mdev = 0.661/1.133/2.161/0.543 ms

TCP throughput (three 20-second runs, using iperf3):

    Run 1: 2.35 GB, 1.01 Gbit/s, 18238 retransmissions
    Run 2: 2.35 GB, 1.01 Gbit/s, 23612 retransmissions
    Run 3: 2.35 GB, 1.01 Gbit/s, 20696 retransmissions

UDP test (5 Mbps target, 20 seconds):

    Transfer: 11.9 MB
    Bitrate:  5.00 Mbit/s
    Jitter:   0.207 ms (receiver)
    Loss:     0/9274 (0%)

## 9. Packet Analysis

### N2 (SCTP port 38412)

Captured SCTP heartbeat exchange between gNB (127.0.0.1) and AMF (127.0.0.5).
Confirmed the N2 control plane is continuously monitored.

### N3 (UDP port 2152)

Captured 10 packets during a 5-packet ping:

    127.0.0.1.2152 > 127.0.0.7.2152: UDP, length 100
    127.0.0.7.2152 > 127.0.0.1.2152: UDP, length 100
    (repeated 5 times)

Hex dump confirmed:
- Uplink GTP-U message type 0xff (G-PDU)
- Inner IP: 10.45.0.2 → 10.45.0.1 (ICMP echo request)
- Downlink GTP-U message type 0xff (G-PDU)
- Inner IP: 10.45.0.1 → 10.45.0.2 (ICMP echo reply)

### N4 (UDP port 8805)

Captured PFCP Association Setup Request/Response and heartbeat exchanges
between SMF (127.0.0.4) and UPF (127.0.0.7).

## 10. Troubleshooting

### Problem 1 — WebUI package unavailable

Symptom: `apt install open5gs-webui` returned "Unable to locate package".
Root cause: Open5GS does not publish a WebUI package for Ubuntu 26.04.
Fix: Used `mongosh` to manage subscribers directly.

### Problem 2 — open5gs-dbctl not installed

Symptom: `open5gs-dbctl: command not found`.
Root cause: The CLI helper is not bundled on resolute.
Fix: Used `mongosh` to insert subscriber records.

### Problem 3 — MongoDB fails on kernel 7.0

Symptom: `MongoDB cannot start: Linux kernel versions 6.19 and newer`.
Also: MongoDB apt repo returned 403 Forbidden.
Fix: Replaced MongoDB with FerretDB + PostgreSQL.

### Problem 4 — FerretDB authentication failure

Symptom: `FATAL: password authentication failed for user "postgres"`.
Root cause: FerretDB connected to PostgreSQL without a password.
Fix: Set a postgres password and updated the service URL.

### Problem 5 — Subscriber SQN out of range

Symptom (UE log): `Authentication Failure due to SQN out of range`.
Root cause: The subscriber record did not include an `sqn` field.
Fix: Added `sqn: NumberLong("000000000023")` to the subscriber record.

### Problem 6 — AMF rejects with cause 62

Symptom (AMF log): `No Allowed-NSSAI` and `Registration reject [62]`.
Root cause: The UE sent SD = 0xffffff because `configured-nssai` had no SD.
Fix: Added `sd: 1` to all three slice sections in ue.yaml.

### Problem 7 — AMF still rejects with cause 62

Symptom (AMF log): `Cannot find Requested NSSAI [1]` with SD=0x1.
Root cause: The AMF's plmn_support.s_nssai did not advertise SD 000001.
Fix: Added `sd: 000001` to the AMF's `s_nssai` list using nano (not heredoc).

### Problem 8 — AMF config corrupted twice

Symptom: `Scanner error` on line 2 and line 302.
Root cause: A `sudo tee` heredoc was pasted into the file itself, leaving
literal command text and a stray `EOF` at the end.
Fix: Restored from backup and edited with nano.

### Problem 9 — gNB NG Setup failed with slice-not-supported

Symptom: `NG Setup procedure is failed. Cause: radio-network/slice-not-supported`.
Root cause: The gNB slices list only had `sst: 1`, no SD.
Fix: Added `sd: 1` to the gNB's slices configuration.

### Problem 10 — TUN configuration failure (missing rt_tables)

Symptom (UE log): `Could not open '/etc/iproute2/rt_tables'`.
Root cause: The /etc/iproute2 directory did not exist.
Fix: `sudo mkdir -p /etc/iproute2` and created an empty rt_tables file.

### Problem 11 — Same-host routing leakage (user plane failed)

Symptom: Ping through uesimtun0 returned 100% packet loss.
Diagnostic:
  - TX counter on uesimtun0 increased with each ping
  - RX counter stayed at 0
  - No GTP-U packets were seen on lo during the ping
  - `ip route get 10.45.0.X from 10.45.0.1` returned
    `local 10.45.0.X dev lo table local`

Root cause: When UERANSIM and Open5GS run on the same host, the kernel's
local routing table treats the UE's IP as a local address, so traffic
shortcuts through loopback instead of being forwarded through the GTP-U
tunnel.

Fix: Enabled the UERANSIM UE network namespace:

    useNamespace: true

After restarting the UE, the routing decision changed to:

    10.45.0.X from 10.45.0.1 dev ogstun uid 1000

The ping and iperf3 tests then succeeded.

### Problem 12 — GTP-U Error Indication "Context Not Found"

Symptom: After the SMF was restarted, packets were forwarded but the UPF
returned a GTP-U Error Indication with cause "Context Not Found". The
capture showed GTP-U message type `1a` (Error Indication) instead of `ff`
(G-PDU).

Root cause: The SMF restart released the UPF session, but the UE still
held an old TEID. The UPF had no matching session for the incoming TEID.

Fix: Restarted the gNB and UE together so the SMF created a fresh session
with a TEID the UPF recognized. After this, the capture showed `ff` in
both directions, confirming real data forwarding.

## 11. Limitations

- UERANSIM provides a software simulation. The radio link between the UE
  and gNB is not an RF channel; no path loss, fading, interference, or
  MIMO behavior is modelled.
- The throughput and jitter figures reported here are characteristics of
  the software simulator and the host CPU, not of a real 5G NR deployment.
- The retransmission counts in the TCP tests reflect loopback-level packet
  handling, not radio-level losses.
- The user plane requires a network namespace for the UE to work correctly
  on a single host. A multi-host deployment would eliminate this requirement.
- The scenario does not implement true 3GPP URLLC guarantees, only URLLC-like
  traffic patterns at the application level.

## 12. Conclusion

Phase 3 achieved all nine of its defined objectives:

1. Open5GS core services start successfully.
2. A subscriber exists in the core database with matching authentication.
3. The simulated gNB establishes its N2 connection to the AMF.
4. The simulated UE registers and authenticates successfully.
5. The UE establishes a PDU session and receives an IP address (10.45.0.2).
6. The UE can reach a test endpoint through the UPF and N6 data network.
7. N2, N3, and N4 packet captures confirm each interface is working.
8. Two failure modes were diagnosed and corrected (routing leakage and
   stale UPF session), with the corrections preserved in this document.
9. The complete setup is documented and reproducible from the commands
   and configuration files recorded here.

The network is ready for Phase 4, where the UERANSIM gNB will be replaced
by the OCUDU CU/DU architecture.
