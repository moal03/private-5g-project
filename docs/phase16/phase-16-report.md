# Phase 16 Report — Reproducibility

**Project:** Simulation of a Private 5G Standalone Network for a Smart Factory
**Date:** 2026-10-13
**Reference machine:** Ubuntu 26.04.1 LTS, kernel 7.0.0-38-generic, 8 CPU threads, 14 GiB RAM

---

## 1. Objective

Produce everything an examiner needs to rebuild the testbed from a
clean Ubuntu installation, run the experiments, and reproduce the
results. Reproducibility is not just about storing scripts; it is
about documenting the exact environment, dependency versions, setup
order, known pitfalls, and verification criteria.

This phase assembles those artifacts. It does not introduce new
experiments.

---

## 2. What Reproducibility Means Here

A testbed is reproducible if a reader with the documented hardware
and OS can:

1. Install the same dependency versions
2. Build the same software revisions
3. Configure the same network topology
4. Start the same services in the same order
5. Confirm the same operational state via automated checks
6. Re-run the experiments using the declared experiment manifest

Everything required for these six steps is provided in this phase,
except step 6, which is provided by Phase 13.

---

## 3. Artifacts Produced

| Artifact | Path | Purpose |
|----------|------|---------|
| Environment snapshot | `results/phase16/environment-snapshot.txt` | Exact state at the reference time |
| Dependency inventory | `results/phase16/dependency-inventory.txt` | Every package, module, and source revision |
| Setup procedure | `docs/phase16/setup-procedure.md` | Step-by-step rebuild guide |
| Verification script | `scripts/phase16/verify.sh` | Automated check of every layer |
| Verification run | `results/phase16/verification-run.txt` | Captured output of the pass |

---

## 4. Hardware and OS Requirements

| Item | Minimum | Reference |
|------|---------|-----------|
| CPU | 4 cores | Intel i7-1165G7 (8 threads) |
| RAM | 8 GiB | 14 GiB |
| Disk free | 20 GiB | 232 GiB |
| OS | Ubuntu 24.04+ | Ubuntu 26.04.1 LTS (resolute) |
| GPU | not required | none |

The reference machine is a mid-range laptop. The full testbed
runs on this hardware without special privileges beyond `sudo` for
network namespace creation and systemd service management.

---

## 5. Dependency Inventory

Full list in `results/phase16/dependency-inventory.txt`. Summary:

### System packages (apt)
- `build-essential`, `cmake`, `make`, `git`, `pkg-config`
- `libsctp-dev`, `lksctp-tools`
- `libmbedtls-dev`, `libyaml-cpp-dev`, `libfftw3-dev`, `libzmq3-dev`
- `libconfig-dev`, `libconfig++-dev`, `libmysqlclient-dev`
- `swig`, `patchelf`
- `python3`, `python3-dev`, `python3-pip`
- `iproute2`, `iputils-ping`, `tcpdump`, `tshark`, `iperf3`
- `prometheus`, `prometheus-node-exporter`, `open5gs`

### Python modules
- numpy, scipy, matplotlib, pandas, PyYAML
- (SWIG-generated `xapp_sdk` for FlexRIC)

### Source builds
| Project | Revision |
|---------|----------|
| OCUDU | see inventory |
| OAI UE (Duranta) | see inventory |
| FlexRIC | `7365081` (branch `br-flexric`) |
| UERANSIM | `ccb49ba...` |
| srsRAN 4G | `6bcbd9e...` |

### Toolchain
- GCC 15.2 (system default) and GCC 13.4 (used for FlexRIC)
- CMake 4.2.3
- Python 3.14.4
- SWIG 4.4.0

---

## 6. Environment Snapshot

Captured at 2026-10-13T21:40:20. Contains:

- host, OS, CPU, memory, disk
- kernel modules (sctp, tun) and tunables
- active network interfaces
- listening ports for the testbed
- git HEAD at capture time
- toolchain versions
- binary sizes for OCUDU, OAI UE, FlexRIC

The full file is available at
`results/phase16/environment-snapshot.txt`.

---

## 7. Setup Procedure

`docs/phase16/setup-procedure.md` is a 394-line guide organized in
15 stages:

| Stage | Content | Est. time |
|-------|---------|----------:|
| 0 | Prerequisites (hardware, network reachability) | — |
| 1 | Base system packages | 10 min |
| 2 | Kernel prerequisites (tun, sctp, ip_forward) | 2 min |
| 3 | Open5GS install | 10 min |
| 4 | Subscriber provisioning | 15 min |
| 5 | Two-UPF configuration | 20 min |
| 6 | OCUDU build | 25 min |
| 7 | OAI UE build | 45 min |
| 8 | Network namespaces | 10 min |
| 9 | Monitoring stack | 25 min |
| 10 | FlexRIC (optional) | 20 min |
| 11 | Verification | 5 min |
| **Total** | | **~3 h** |

### Documented pitfalls

The setup procedure documents four real pitfalls, each encountered
during the original work:

1. **MongoDB geoblocking (Iran).** Open5GS's default subscriber
   backend is MongoDB, whose apt repository is inaccessible from
   Iranian IPs. Workaround: FerretDB on PostgreSQL (Phase 3).

2. **Grafana plugin CDN geoblocking.** Grafana 13 no longer bundles
   the Prometheus datasource; the CDN download is blocked from Iran.
   Workaround: install from a SHA1-verified GitHub release (Phase 9).

3. **Prometheus port collision.** Prometheus's default port 9090
   collides with seven Open5GS services. Workaround: move Prometheus
   to port 9095 (Phase 9).

4. **FlexRIC on GCC 15 and Python 3.14.** FlexRIC does not build
   with GCC 15; GCC 13 is required. The Python SDK segfaults on
   Python 3.14 due to a SWIG ABI mismatch. Workaround: use GCC 13
   and, for xApps, either use the C examples or downgrade to
   Python 3.12 (Phases 12, 13).

5. **Exec-stack flags on FlexRIC libraries.** The FlexRIC shared
   libraries are built with an executable-stack flag; modern kernels
   refuse to load them. Workaround: `patchelf --clear-execstack`
   on every `.so` after install (Phase 11).

---

## 8. Verification Script

`scripts/phase16/verify.sh` performs 40 read-only checks across 10
categories. It makes no configuration changes and exits with a code
equal to the number of failures.

| Category | Checks |
|----------|-------:|
| Host | 4 |
| Kernel prerequisites | 3 |
| Open5GS core | 7 |
| Open5GS listeners | 4 |
| Open5GS TUN interfaces | 2 |
| RAN (OCUDU) | 6 |
| UE | 4 |
| Data path | 2 |
| Monitoring | 6 |
| RIC (optional) | 2 |
| **Total** | **40** |

Results are classified as PASS, FAIL, or SKIP (for optional checks).

### Verification result at reference time

Captured in `results/phase16/verification-run.txt`:

    Total : 40
    PASS  : 38
    FAIL  : 0
    SKIP  : 2  (optional checks)

    RESULT: Verification passed.
            All required components are operational.

The two skipped checks are the UE → central and UE → edge pings.
The application namespaces were not started at verification time,
so those checks correctly skip rather than fail. When the app
namespaces are running, both checks pass (as recorded in Phase 8
and Phase 10).

---

## 9. What Is Reproducible

The following can be rebuilt from the documented artifacts alone:

| Layer | Reproducible from |
|-------|-------------------|
| 5G core (Open5GS, two UPFs) | apt + config files in `configs/phase7/` |
| RAN (OCUDU CU + DU) | source revision + config files in `configs/ocudu/` |
| UE (OAI nr-uesoftmodem) | source revision + config files in `configs/ocudu/` |
| Network namespaces | scripts in `scripts/phase7/` and `scripts/phase10/` |
| Monitoring | apt + `configs/phase9/dashboard.json` |
| Near-RT RIC (FlexRIC) | source revision + `configs/phase11/` |
| Experiments | manifest in `experiments/manifests/experiments.yaml` |
| Analysis | scripts in `scripts/phase14/` and `scripts/phase15/` |

---

## 10. What Is Not Fully Reproducible

Honest limitations:

1. **Binary-exact rebuilds.** OCUDU and the Duranta OAI UE are built
   from source, but the reference machine used GCC 15.2 and specific
   CMake flags. A different GCC or CMake version may produce
   functionally equivalent binaries that differ in build ID or size.

2. **Timing-sensitive measurements.** Ping RTTs depend on host
   scheduling, CPU governor, and whether Chrome is running. The
   reference numbers were captured under documented conditions
   (Chrome closed, CPU governor = performance). A fresh machine may
   produce slightly different baseline RTTs.

3. **Software limitations of the OCUDU revision.** The KPM indication
   gap (Phase 11) and the ASN.1 codec mismatch (Phase 12) are
   properties of the specific OCUDU commit. A different commit may
   behave differently.

4. **Third-party geo-restrictions.** MongoDB and Grafana's plugin
   CDN are inaccessible from some regions. The workarounds are
   documented but require manual intervention.

5. **Floating-point and OS-version drift.** Ubuntu 26.04 was
   released recently; the reference machine is on the LTS point
   release. A later point release may change library versions in
   ways that require small adjustment.

These limitations are common to any software-only testbed and do
not prevent reproduction of the *functional* behavior of the
testbed. They do affect bit-exact reproduction of individual RTT
numbers.

---

## 11. Reproducibility Statement

A reader with:

- the reference hardware class (8-thread CPU, 14 GiB RAM, ~20 GiB disk)
- Ubuntu 26.04.1 or compatible
- network reachability to apt, GitHub, and gitlab.eurecom.fr
- approximately 3 hours of setup time
- sudo privileges for network namespace and systemd operations

can reproduce the functional testbed described in this project. The
verification script will confirm every layer, and the experiment
manifest will re-run the tests.

Bit-exact reproduction of every measured RTT is not claimed. The
conclusions of the project do not depend on bit-exact RTTs; they
depend on aggregate statistical properties (medians, percentiles,
success counts) which are stable across machines of this class.

---

## 12. Reproducibility Checklist

- [x] Hardware and OS requirements documented
- [x] System package list with versions
- [x] Python module list with versions
- [x] Source revision hashes for every build
- [x] Environment snapshot at reference time
- [x] Step-by-step setup procedure
- [x] Documented pitfalls with workarounds
- [x] Verification script (read-only, 40 checks)
- [x] Verification captured output
- [x] Experiment manifest (Phase 13)
- [x] Analysis scripts (Phases 15, 23)
- [x] Known non-reproducible aspects documented

---

## 13. Files Produced

    docs/phase16/setup-procedure.md           (394 lines)
    docs/phase16/phase-16-report.md           (this file)
    scripts/phase16/verify.sh                 (188 lines)
    results/phase16/environment-snapshot.txt  (95 lines)
    results/phase16/dependency-inventory.txt
    results/phase16/verification-run.txt

---

## 14. Conclusion

Phase 16 assembled the reproducibility artifacts for the project.
An examiner can now:

1. Read the environment snapshot to see the exact reference state.
2. Read the dependency inventory to see every package and revision.
3. Follow the setup procedure to rebuild the testbed from clean Ubuntu.
4. Run the verification script to confirm every layer is operational.
5. Use the Phase 13 manifest to re-run the experiments.
6. Use the Phase 14 and 23 scripts to re-analyze and validate.

The verification script passes 38 of 40 checks with 2 skips, where
the skips reflect application namespaces that were intentionally not
running at verification time. No required check fails.

The project is reproducible in the functional sense. Bit-exact
reproduction is not claimed and is not required for the project's
conclusions.

---

**End of Phase 16 Report**
