# Phase 8 Report — Traffic Engineering and Performance Analysis

**Project:** Simulation of a Private 5G Standalone Network for a Smart Factory
**Date:** 2026-10-13
**Environment:** Ubuntu 26.04.1 LTS (resolute), kernel 7.0.0-38-generic, 8 CPU cores, 14 GiB RAM

---

## 1. Objective

Measure how the simulated private 5G network behaves as offered traffic
increases, what limits its throughput, and whether separating a
latency-sensitive flow onto a different UPF changes its latency under
competing load.

---

## 2. Experimental Setup

### 2.1 Removal of Phase 7 Netem

Before starting Phase 8, the 30 ms netem delay that had been applied to
ogstun in Phase 7 was removed.

Before removal:

~~~
qdisc netem 8001: root refcnt 2 limit 1000 delay 30ms seed 6947328496463431017
~~~

Command used:

~~~
sudo tc qdisc del dev ogstun root
~~~

After removal:

~~~
qdisc fq_codel 0: root refcnt 2 limit 10240p flows 1024 quantum 1514 target 5ms interval 100ms memory_limit 32Mb ecn drop_batch 64
~~~

### 2.2 Stack State at Phase 8 Start

~~~
CU:     1 process (ocu)
DU:     1 process (odu)
UE:     2 processes (nr-uesoftmodem + sudo wrapper)
Open5GS: 18 services running
Namespaces: ue1, factory-app, edge-app
UE interfaces: oaitun_ue1 (10.45.0.2), oaitun_ue1p2 (10.46.0.2)
ogstun:  10.45.0.1/16 (UPF-A)
ogstun2: 10.46.0.1/16 (UPF-B)
iperf3 servers: factory-app 5201, edge-app 5201
~~~

### 2.3 Test Endpoints

| Endpoint | IP | Namespace | Path |
|----------|----|-----------|------|
| Central app | 10.60.0.10 | factory-app | UE -> UPF-A |
| Edge app | 10.70.0.10 | edge-app | UE -> UPF-B |

### 2.4 Tool Versions

~~~
iperf3:   3.20
tc:       iproute2-6.19.0
python3:  3.14.4
ping:     iputils 20250605
~~~

### 2.5 Directories Created

~~~
docs/phase8/
logs/phase8/
results/phase8/
scripts/phase8/
figures/phase8/
~~~

### 2.6 Baseline Snapshot Files

Eleven files saved to logs/phase8/:

~~~
start-time.txt
host.txt
cpu.txt
memory.txt
interfaces.txt
routes.txt
rules.txt
tool-versions.txt
services.txt
processes.txt
topology-state.txt
~~~

---

## 3. Idle Baseline (No Competing Traffic)

### 3.1 Idle Ping

Command form:

~~~
sudo ip netns exec ue1 ping -n -i 0.2 -c 300 -I <iface> <dst>
~~~

**Central - via oaitun_ue1 -> 10.60.0.10:**

~~~
300 packets transmitted, 300 received, 0% packet loss, time 59947ms
rtt min/avg/max/mdev = 25.498/75.535/150.850/21.587 ms
~~~

**Edge - via oaitun_ue1p2 -> 10.70.0.10:**

~~~
300 packets transmitted, 300 received, 0% packet loss, time 59949ms
rtt min/avg/max/mdev = 28.703/77.788/142.754/21.040 ms
~~~

**Summary table:**

| Path | Sent | Recv | Loss | Min | Avg | Max | mdev |
|------|------|------|------|-----|-----|-----|------|
| Central | 300 | 300 | 0% | 25.5 ms | 75.5 ms | 150.9 ms | 21.6 ms |
| Edge | 300 | 300 | 0% | 28.7 ms | 77.8 ms | 142.8 ms | 21.0 ms |

### 3.2 Idle TCP

Command form:

~~~
sudo ip netns exec ue1 iperf3 -c <dst> -t 60 -i 5 --json
~~~

**Central:**

~~~
sender:   8.23 Mbps  retrans: 334
receiver: 7.90 Mbps
~~~

**Edge:**

~~~
sender:   8.65 Mbps  retrans: 1747
receiver: 7.52 Mbps
~~~

### 3.3 Idle UDP

Command form:

~~~
sudo ip netns exec ue1 iperf3 -c <dst> -u -b <rate>M -l 1200 -t <dur> --json
~~~

| Test | Sender | Jitter | Loss |
|------|--------|--------|------|
| 1 Mbps central | 1.00 Mbps | 5.32 ms | 0/6251 = 0% |
| 1 Mbps edge | 1.00 Mbps | 5.20 ms | 0/6251 = 0% |
| 5 Mbps central | 5.00 Mbps | 3.27 ms | 0/15628 = 0% |
| 10 Mbps central | 10.00 Mbps | 1.68 ms | 0/31256 = 0% |

---

## 4. Offered-Load Sweep

Command form:

~~~
sudo ip netns exec ue1 iperf3 -c 10.60.0.10 -u -b <rate>M -l 1200 -t <dur> -i 5
~~~

| Offered | Duration | Sender | Receiver | Jitter | Loss | Result |
|---------|----------|--------|----------|--------|------|--------|
| 1 Mbps | 60 s | 1.00 Mbps | 1.00 Mbps | 5.32 ms | 0% | OK |
| 5 Mbps | 60 s | 5.00 Mbps | 5.00 Mbps | 3.27 ms | 0% | OK |
| 10 Mbps | 30 s | 10.00 Mbps | 10.00 Mbps | 1.68 ms | 0% | OK |
| 11 Mbps | 15 s | 11.00 Mbps | 8.55 Mbps | 1.464 ms | 0% | OK (drain 19.30 s) |
| 12 Mbps | 15 s | - | - | - | - | control failed |
| 13 Mbps | 15 s | 13.00 Mbps | 8.60 Mbps | 1.602 ms | 0% | OK (drain 22.68 s) |
| 14 Mbps | 15 s | - | - | - | - | control failed |
| 15 Mbps | 30 s | - | - | - | - | control failed |
| 20 Mbps | 30 s | - | - | - | - | control failed |
| 25 Mbps | 30 s | - | - | - | - | control failed |
| 30 Mbps | 30 s | - | - | - | - | control failed |

Control channel error when it occurred:

~~~
"error": "unable to receive control message - port may not be available,
the other side may have stopped running, etc.: Connection reset by peer"
~~~

After each failed run, CU, DU, and UE remained running; the UE retained
both IP addresses.

Drain times on successful runs:

~~~
11 Mbps offered -> 19.30 s total (test duration was 15 s)
13 Mbps offered -> 22.68 s total (test duration was 15 s)
~~~

---

## 5. Latency Under Competing Load

All tests used 300-packet ping at 200 ms interval, ~60 s duration, with
8 Mbps UDP load where applicable. Loss was 0% in every test.

### 5.1 Condition 1 - Control (idle, no load)

~~~
300 packets transmitted, 300 received, 0% packet loss, time 59949ms
rtt min/avg/max/mdev = 17.644/77.373/130.478/21.080 ms
~~~

### 5.2 Condition 2 - Same-UPF (load and probe both to 10.60.0.10)

~~~
300 packets transmitted, 300 received, 0% packet loss, time 59940ms
rtt min/avg/max/mdev = 52.015/65.374/175.147/13.081 ms
~~~

UDP load summary:

~~~
[  5]   0.00-60.08  sec  57.2 MBytes  7.99 Mbits/sec  1.794 ms  0/50009 (0%)  receiver
~~~

### 5.3 Condition 3 - Cross-UPF (probe to 10.70.0.10, load to 10.60.0.10)

~~~
300 packets transmitted, 300 received, 0% packet loss, time 59961ms
rtt min/avg/max/mdev = 21.555/29.735/104.272/10.757 ms
~~~

UDP load summary:

~~~
[  5]   0.00-60.06  sec  57.2 MBytes  7.99 Mbits/sec  1.999 ms  0/50009 (0%)  receiver
~~~

### 5.4 Condition 4 - Cross-UPF reverse (probe to 10.60.0.10, load to 10.70.0.10)

~~~
300 packets transmitted, 300 received, 0% packet loss, time 59969ms
rtt min/avg/max/mdev = 21.569/31.676/120.439/11.579 ms
~~~

UDP load summary:

~~~
[  5]   0.00-60.08  sec  57.2 MBytes  7.99 Mbits/sec  1.939 ms  0/50009 (0%)  receiver
~~~

### 5.5 Summary Table

| Condition | Probe dst | Load dst | Ping avg | mdev | min | max | Loss |
|-----------|-----------|----------|----------|------|-----|-----|------|
| 1. Control | central | none | 77.4 ms | 21.1 | 17.6 | 130.5 | 0% |
| 2. Same-UPF | central | central | 65.4 ms | 13.1 | 52.0 | 175.1 | 0% |
| 3. Cross-UPF (edge) | edge | central | 29.7 ms | 10.8 | 21.6 | 104.3 | 0% |
| 4. Cross-UPF (central) | central | edge | 31.7 ms | 11.6 | 21.6 | 120.4 | 0% |

---

## 6. Files Produced

### 6.1 Logs (logs/phase8/)

~~~
start-time.txt
host.txt
cpu.txt
memory.txt
interfaces.txt
routes.txt
rules.txt
tool-versions.txt
services.txt
processes.txt
topology-state.txt
~~~

### 6.2 Results (results/phase8/)

~~~
ping-idle-central.txt
ping-idle-edge.txt
ping-control-60s.txt
ping-under-load-same-dest.txt
ping-under-load-cross-upf.txt
ping-under-load-cross-upf-reverse.txt
tcp-idle-central-forward.json
tcp-idle-edge-forward.json
udp-idle-central-1m.json
udp-idle-edge-1m.json
udp-idle-central-5m.json
udp-load-central-10m.json
udp-load-central-11m.txt
udp-load-central-12m.txt
udp-load-central-13m.txt
udp-load-central-14m.txt
udp-load-central-15m.json
udp-load-central-20m.json
udp-load-central-25m.json
udp-load-central-30m.json
udp-load-under-ping.txt
udp-load-while-edge-ping.txt
udp-load-while-central-ping.txt
saturation-finding.txt
latency-under-load-comparison.txt
~~~

### 6.3 Docs (docs/phase8/)

~~~
topology.md
phase-8-report.md
~~~

---

**End of Phase 8 Report**
