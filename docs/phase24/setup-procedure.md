# Setup Procedure — From Clean Ubuntu 26.04 to Working Testbed

**Target system:** Ubuntu 26.04.1 LTS (Resolute Raccoon), x86_64
**Testbed:** Private 5G SA (Open5GS + OCUDU + OAI UE), Monitoring, RIC
**Reference machine:** See `results/phase24/environment-snapshot.txt`

This procedure rebuilds the testbed from scratch. It is organized
in stages. Each stage is independent enough that it can be verified
before moving on.

---

## 0. Prerequisites

| Item | Minimum | Reference machine |
|------|---------|-------------------|
| CPU | 4 cores | Intel i7-1165G7 (8 threads) |
| RAM | 8 GiB | 14 GiB |
| Disk free | 20 GiB | 232 GiB |
| OS | Ubuntu 24.04+ | Ubuntu 26.04.1 LTS |
| Network | apt + GitHub reachable | apt, GitHub, gitlab.eurecom.fr |
| GPU | not required | none |

**Note on network reachability:** This environment has been tested
from an Iranian IP. Some upstream servers are geo-blocked (MongoDB's
repo, Grafana's plugin CDN). Workarounds are documented per stage.

---

## 1. Base System Packages

    sudo apt update
    sudo apt install -y \
      build-essential cmake make git pkg-config \
      libsctp-dev lksctp-tools \
      libmbedtls-dev libyaml-cpp-dev libfftw3-dev libzmq3-dev \
      libconfig-dev libconfig++-dev libmysqlclient-dev \
      swig patchelf \
      python3 python3-dev python3-pip python3-venv \
      iproute2 iputils-ping tcpdump tshark iperf3 net-tools jq \
      curl gnupg software-properties-common

Verify:

    gcc --version    # 15.2.0 on reference
    gcc-13 --version # 13.4.0 on reference (used for FlexRIC)
    cmake --version  # 4.2.3
    python3 --version # 3.14.4

**Pitfall:** GCC 15.2 is the system default on Ubuntu 26.04.
FlexRIC is not compatible with it. Install gcc-13 as well:

    sudo apt install -y gcc-13 g++-13

---

## 2. Kernel Prerequisites

The testbed requires the `tun` device and the `sctp` kernel module.

    ls /dev/net/tun       # must exist
    lsmod | grep sctp     # must be loaded

If `tun` is missing:

    sudo modprobe tun

If SCTP is not loaded:

    sudo modprobe sctp

Enable IP forwarding for the Open5GS UPFs:

    sudo sysctl -w net.ipv4.ip_forward=1
    echo "net.ipv4.ip_forward=1" | sudo tee /etc/sysctl.d/99-testbed.conf

---

## 3. Open5GS Core (5G SA)

Open5GS is installed from the project's PPA.

    sudo add-apt-repository ppa:open5gs/latest
    sudo apt update
    sudo apt install -y open5gs

**Pitfall (Iran):** The MongoDB repository is geo-blocked. Open5GS
uses MongoDB (via WebUI) for subscriber storage. Two workarounds:

**Option A:** Use a MongoDB mirror reachable from the region.

**Option B (used on reference machine):** Install FerretDB in front
of PostgreSQL. See `docs/phase-3-report.md` for the exact procedure.

Verify:

    systemctl --type=service --state=running | grep open5gs | wc -l
    # Expect 18 on the reference machine
    systemctl status open5gs-amfd --no-pager

The 18 services cover 4G and 5G functions. Only the 5G subset is used.

---

## 4. Subscriber Provisioning

Subscriber records are stored via FerretDB (or MongoDB). A minimal
subscriber with two slices is required:

| Field | Value |
|-------|-------|
| IMSI | 999700000000001 |
| K | 465B5CE8B199B49FAA5F0A2EE238A6BC |
| OPc | E8ED289DEBA952E4283B54E88E6183CA |
| AMF | 8000 |
| Slice 1 | SST=1, SD=000001 |
| Slice 2 | SST=1, SD=000002 |

The reference subscriber JSON is at
`configs/phase6-final/subscriber.json`.

---

## 5. Open5GS Configuration — Two UPFs

Two UPFs are configured, selected by DNN. Full details are in
`docs/phase7/design.md`. Summary:

| File | Purpose |
|------|---------|
| /etc/open5gs/amf.yaml | AMF with two S-NSSAIs |
| /etc/open5gs/smf.yaml | SMF with two UPFs (per-DNN) |
| /etc/open5gs/upf.yaml | Central UPF (DNN=internet) |
| /etc/open5gs/upf-edge.yaml | Edge UPF (DNN=factory) |
| /etc/systemd/system/open5gs-upfd-edge.service | Edge UPF unit |

The edge UPF's systemd unit requires CAP_NET_ADMIN to create the
ogstun2 interface:

    AmbientCapabilities=CAP_NET_ADMIN
    CapabilityBoundingSet=CAP_NET_ADMIN

Reference configs: `configs/phase7/`.

---

## 6. OCUDU RAN (CU + DU)

OCUDU is built from source. It is an O-RAN-oriented 5G RAN.

**Build:**

    mkdir -p ~/projects
    cd ~/projects
    git clone https://gitlab.com/ocudu/ocudu.git ocudu-dev
    cd ocudu-dev
    cmake -S . -B build \
      -DENABLE_EXPORT=ON \
      -DENABLE_ZEROMQ=ON
    cmake --build build --parallel 2
    ctest --output-on-failure

Binaries:

    build/apps/cu/ocu
    build/apps/du/odu

Reference revision: see `results/phase24/dependency-inventory.txt`.

**Reference configs:**

- `configs/ocudu/cu_zmq.yml` — CU
- `configs/ocudu/du_zmq.yml` — DU (Phase 6 slicing)
- `configs/ocudu/du_zmq_e2.yml` — DU with E2 agent (Phase 12)

**Startup order:** CU first, then DU. If the DU fails to connect
to the CU over F1-C, check that the CU is listening on 127.0.0.1:38472.

---

## 7. Software UE (OpenAirInterface)

Two software UEs are supported:

- **srsRAN 4G** (srsUE) — band n3 FDD, 15 kHz SCS. Reference: Phase 4-A.
- **OpenAirInterface** (OAI UE, Duranta fork) — band n78 TDD, 30 kHz SCS.
  Reference: Phase 4-B. **Recommended** for consistency with the RAN.

**Build (OAI UE, Duranta fork):**

    cd ~/projects
    git clone <duranta-oai-repo> duranta-oai
    cd duranta-oai
    git checkout <develop commit>
    # Build per project documentation
    cd cmake_targets/duranta-nrue/build
    # Result: nr-uesoftmodem

Reference revision: see `results/phase24/dependency-inventory.txt`.

**Reference configs:**

- `configs/ocudu/oaiue_zmq.baseline.conf`
- `configs/ocudu/oaiue_zmq.treatment.conf`

---

## 8. Network Namespaces

Three namespaces are used:

| Namespace | Purpose |
|-----------|---------|
| ue1 | Runs the software UE |
| factory-app | Central application (DNN=internet) |
| edge-app | Edge application (DNN=factory) |

The UE namespace is created with a veth pair to the host:

    sudo ip netns add ue1
    sudo ip link add v-eth1 type veth peer name v-ue1
    sudo ip link set v-ue1 netns ue1
    sudo ip addr add 10.200.1.1/24 dev v-eth1
    sudo ip link set v-eth1 up
    sudo ip netns exec ue1 ip link set lo up
    sudo ip netns exec ue1 ip addr add 10.200.1.2/24 dev v-ue1
    sudo ip netns exec ue1 ip link set v-ue1 up

The two application namespaces are created similarly. Full scripts
are in `scripts/phase7/` and `scripts/phase11/`.

**Reference:** `docs/phase5/`, `docs/phase7/design.md`.

---

## 9. Monitoring Stack

| Component | Install source | Port |
|-----------|----------------|------|
| Prometheus | Ubuntu universe | 9095 |
| node-exporter | Ubuntu universe | 9100 |
| Grafana | apt.grafana.com | 3000 |
| Grafana Prometheus plugin | github.com/grafana (manual) | — |

**Pitfall (Iran):** Grafana's plugin CDN is geo-blocked. The
Prometheus datasource plugin must be installed manually:

    # Download from GitHub release, verify SHA1, extract to
    # /var/lib/grafana/plugins/prometheus
    # See docs/phase9/phase-9-report.md for exact URL and hash.

**Pitfall:** Prometheus default port 9090 collides with seven
Open5GS services. Move Prometheus to 9095 via
`/etc/default/prometheus`:

    ARGS=" --web.listen-address=:9095"

**Reference:** `docs/phase9/phase-9-report.md`.

---

## 10. FlexRIC Near-RT RIC (Optional — Phase 12/13)

FlexRIC provides a Near-RT RIC with an E2 interface to OCUDU.

**Build with GCC 13:**

    cd ~/projects
    git clone --branch br-flexric --depth 1 \
      https://gitlab.eurecom.fr/mosaic5g/flexric.git
    cd flexric
    mkdir build && cd build
    CC=gcc-13 CXX=g++-13 cmake \
      -DCMAKE_BUILD_TYPE=Release \
      -DKPM_VERSION=KPM_V3_00 \
      -DXAPP_DB=NONE_XAPP \
      -DCMAKE_INSTALL_PREFIX=/usr/local \
      ..
    make -j$(nproc)
    sudo make install

**Pitfalls:**

1. XAPP_DB is a **string**, not a boolean. Valid values:
   `MYSQL_XAPP`, `SQLITE3_XAPP`, `NONE_XAPP`.

2. The libraries are built with an executable-stack flag. Clear it:

       for lib in $(find /usr/local -name '*.so' | grep flexric); do
         sudo patchelf --clear-execstack "$lib"
       done

3. The Python SDK requires an explicit PYTHONPATH:

       export PYTHONPATH=/usr/local/lib/python3/dist-packages/xapp_sdk:$PYTHONPATH

4. The Python SDK crashes on Python 3.14 (SWIG ABI mismatch). It
   imports successfully but segfaults on `ric.init()`. Python 3.12
   is recommended if the Python xApp is required. The C xApps work
   without Python.

**Reference:** `docs/phase12/phase-12-report.md`, `docs/phase13/phase-13-report.md`.

---

## 11. Verification

After all stages, run the verification script:

    scripts/phase24/verify.sh

It checks every layer and prints a summary. See Section 12 for what
"pass" means.

---

## 12. What "Reproduced" Means

A successfully reproduced testbed satisfies:

| Check | Command | Expected |
|-------|---------|----------|
| Open5GS services up | `systemctl is-active open5gs-amfd` | active |
| CU listening on N2 | `ss -lnp \| grep 38412` | listener |
| DU F1 Setup | `grep "F1 Setup" /tmp/ocudu-du.log` | completed |
| UE registered | `ip netns exec ue1 ip -br addr \| grep oaitun` | 2 interfaces |
| Two PDU sessions | ping both app namespaces | 0% loss |
| Monitoring up | `curl -s localhost:9095` | HTTP response |
| Grafana up | `curl -s localhost:3000` | HTTP response |
| RIC listening (optional) | `ss -lnp \| grep 36421` | SCTP listener |

If all checks pass, the testbed is equivalent to the reference.

---

## 13. Known Deviations from a Fresh Install

The reference machine was built interactively. A fresh install will
produce the same functional testbed with these expected differences:

- **IP addresses assigned by Open5GS to UEs** will increment
  differently (10.45.0.2 vs 10.45.0.5 etc.). The pool is the same;
  the specific address depends on session history.
- **SQN values** in subscriber records increment with each
  registration. Starting values may differ.
- **Log timestamps** obviously differ.
- **Grafana dashboards** must be recreated from the JSON in
  `configs/phase9/dashboard.json`.
- **The RIC's KPM indications and RC control decode** fail on the
  reference OCUDU revision regardless of install. This is documented
  in Phases 12 and 13 and is not a setup issue.

---

## 14. Time Estimate

For a fresh Ubuntu 26.04 with apt and GitHub reachable:

| Stage | Estimated time |
|-------|---------------:|
| 1. Base packages | 10 min |
| 2. Kernel prerequisites | 2 min |
| 3. Open5GS install | 10 min |
| 4. Subscriber provisioning | 15 min |
| 5. Open5GS two-UPF config | 20 min |
| 6. OCUDU build | 25 min |
| 7. OAI UE build | 45 min |
| 8. Namespaces | 10 min |
| 9. Monitoring | 25 min |
| 10. FlexRIC (optional) | 20 min |
| 11. Verification | 5 min |
| **Total** | **~3 hours** |

Network delays can push this to 4–5 hours in regions where some
apt mirrors are slow.

---

## 15. References to Phase Reports

- Base Linux + networking: `docs/phase-3-report.md`
- First 5G SA: `docs/phase-3-report.md`
- OCUDU + OAI UE: `docs/phase-4-report.md`
- Private 5G/NPN: `docs/phase-5-report.md`
- Slicing: `docs/phase6/phase-6-report.md`
- Multi-UPF + edge: `docs/phase7/phase-7-report.md`
- Traffic engineering: `docs/phase8/phase-8-report.md`
- Monitoring: `docs/phase9/phase-9-report.md`
- Fault injection: `docs/phase11/phase-11-report.md`
- Near-RT RIC: `docs/phase12/phase-12-report.md`
- xApp: `docs/phase13/phase-13-report.md`
- Automated experiments: `docs/phase14/phase-14-report.md`
- Cross-phase analysis: `docs/phase15/phase-15-report.md`
- Validation: `docs/phase23/phase-23-report.md`
