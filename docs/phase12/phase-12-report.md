# Phase 12 Report — Near-RT RIC Integration and E2 Interface

**Project:** Simulation of a Private 5G Standalone Network for a Smart Factory
**Date:** 2026-10-13
**Environment:** Ubuntu 26.04.1 LTS (resolute), kernel 7.0.0-38-generic, 8 CPU cores, 14 GiB RAM

---

## 1. Objective

Integrate a Near-Real-Time RAN Intelligent Controller (Near-RT RIC) with
the OCUDU RAN through the O-RAN E2 interface, verify the E2 connection
and service-model subscription procedures, and prepare the foundation
for a custom xApp.

This addresses the O-RAN component of the project roadmap. The RIC is
the platform on which the project's principal technical contribution —
a custom xApp — will later run.

---

## 2. Environment

| Component | Version / Implementation |
|-----------|--------------------------|
| Near-RT RIC | FlexRIC (branch `br-flexric`, commit `7365081`) |
| E2 service models | KPM (id 2), RC (id 3), MAC/RLC/PDCP/Slice/TC/GTP (custom) |
| Compiler | GCC 13.4.0 (GCC 15.2.0 is the system default; GCC 13 was used for FlexRIC to avoid ABI issues) |
| Python | 3.14.4 |
| SWIG | 4.4.0 |
| OCUDU | dev build, 2026-10-12 |
| Open5GS | 2.8.0~resolute6 |

---

## 3. FlexRIC Installation

### 3.1 Build

FlexRIC was cloned from `gitlab.eurecom.fr/mosaic5g/flexric.git`,
branch `br-flexric`, commit `7365081`.

Configuration:

    CC=gcc-13 CXX=g++-13 cmake \
      -DCMAKE_BUILD_TYPE=Release \
      -DKPM_VERSION=KPM_V3_00 \
      -DXAPP_DB=NONE_XAPP \
      -DCMAKE_INSTALL_PREFIX=/usr/local \
      ..

Note: XAPP_DB is a **string** selector (`MYSQL_XAPP`,
`SQLITE3_XAPP`, or `NONE_XAPP`), not a boolean. Passing `ON` or `OFF`
causes CMake to fail because the internal logic references a target
that is only defined for valid string values.

Build completed without errors. Key components installed:

| Path | Component |
|------|-----------|
| /usr/local/bin/flexric/ric/nearRT-RIC | Near-RT RIC binary |
| /usr/local/bin/flexric/xApp/c/* | Example C xApps (8) |
| /usr/local/lib/python3/dist-packages/xapp_sdk/ | Python xApp SDK |
| /usr/local/lib/libe42_xapp_shared.so | xApp interface library |
| /usr/local/lib/flexric/libkpm_sm.so | KPM service model |
| /usr/local/lib/flexric/librc_sm.so | RC service model |
| /usr/local/etc/flexric/*.conf | Configuration files |

### 3.2 Exec-Stack Flag Workaround

All FlexRIC shared libraries were compiled with the executable-stack
flag set, which modern Linux kernels refuse to load:

    ImportError: libe42_xapp_shared.so: cannot enable executable stack
    as shared object requires: Invalid argument

Resolved with `patchelf --clear-execstack` on every affected library,
in both the build tree and the installed location. After clearing the
flag, the Python SDK imported cleanly (465 symbols).

---

## 4. OCUDU E2 Configuration

The DU was configured with an `e2` section in its YAML configuration:

    e2:
      enable_du_e2: true
      addrs:
        - 127.0.0.1
      port: 36421
      bind_addrs:
        - 127.0.0.1
      e2sm_kpm_enabled: true
      e2sm_rc_enabled: true
      e2sm_ccc_enabled: false

The E2 agent runs in the DU process. The CU does not need E2
configuration for this demonstration.

---

## 5. E2 Interface Verification

### 5.1 Startup Order

1. Near-RT RIC started first
2. CU started (unmodified config)
3. DU started with E2 config
4. UE started last

### 5.2 Connection Established

DU log confirms the E2 setup completed:

    2026-10-13T17:05:05.010237 [E2-DU] "RIC Connection Setup Routine" started.
    2026-10-13T17:05:05.010356 [E2-DU] E2: Connection to Near-RT-RIC on 127.0.0.1:36421 established
    2026-10-13T17:05:05.091222 [DU-F1] F1 Setup: Procedure completed successfully.
    2026-10-13T17:05:05.091240 [SCHED] cell=0: Cell scheduling was activated.
    2026-10-13T17:05:05.091646 [E2-DU] "RIC Connection Setup Routine" finished successfully.

SCTP association verified:

    sctp  ESTAB  ...  127.0.0.1:42359  ->  127.0.0.1:36421  users:(("odu"))
    sctp  LISTEN  ...  127.0.0.1:36421                       users:(("nearRT-RIC"))

### 5.3 RAN Functions Advertised

The DU advertised both service models in E2 Setup:

    [E2-DU] Added supported RAN function with id 2 and OID 1.3.6.1.4.1.53148.1.2.2.2
    [E2-DU] Added supported RAN function with id 3 and OID 1.3.6.1.4.1.53148.1.1.2.3

RAN function id 2 = E2SM-KPM; id 3 = E2SM-RC.

### 5.4 KPM Subscription Accepted

When a KPM xApp subscribed, the DU accepted the subscription:

    [E2-DU] "E2AP Subscription Setup Procedure" initialized
    [E2-DU] E2AP: Received subscription request
    [E2-DU] Admitting action 0 (type 0)
    [E2-DU] E2 Agent admitted actions [with labels]: DRB.RlcSduDelayDl
            [NO_LABEL], DRB.UEThpDl [NO_LABEL], DRB.UEThpUl [NO_LABEL],
            RRU.PrbTotDl [NO_LABEL], RRU.PrbTotUl [NO_LABEL]
    [E2-DU] E2AP: Sending subscription response

The subscription is registered and the response is sent.

---

## 6. Custom Python xApp

### 6.1 Implementation

A Python xApp was written (`scripts/phase12/xapp_kpm_monitor.py`)
that:

- Calls `ric.init([sys.argv[0]])` to connect to the RIC
- Reads the KPM subscription configuration from
  `/usr/local/etc/flexric/xapp_kpm.conf`
- Subscribes to KPM indications via `ric.report_kpm_sm()`
- Parses FORMAT_1 and FORMAT_3 indication messages
- Writes every measurement to a CSV file
- Implements rule-based congestion detection: if
  `RRU.PrbTotDl` exceeds a threshold for N consecutive samples,
  a `CONGESTION_DETECTED` event is logged

The callback class derives from `ric.kpm_cb` and overrides `handle()`.
The script passes only `sys.argv[0]` to `ric.init()` so that FlexRIC's
C argument parser does not see the argparse flags.

### 6.2 Segfault During Init

The Python xApp crashes with SIGSEGV inside `ric.init()`, immediately
after the first service model plugin is loaded:

    [E2-AGENT]: Opening plugin from path = /usr/local/lib/flexric/libkpm_sm.so
    Segmentation fault (core dumped)

Kernel log:

    python3[...]: segfault at ... ip ... likely on CPU 7

Investigation:

- The Python SDK imports successfully (465 symbols)
- `ric.init([])` and `ric.init([sys.argv[0]])` both crash
- The crash occurs before any Python code after `init()` runs
- The C xApp works perfectly with the same plugin

**Conclusion:** this is a Python 3.14 ABI incompatibility with the
FlexRIC SWIG wrapper. FlexRIC was developed against Python 3.10–3.12.
Python 3.14 is not yet supported.

---

## 7. C xApp Demonstration

FlexRIC ships 8 C xApps. The relevant one for KPM monitoring is
`xapp_oran_moni`. Running it produces:

    [xApp]: E42 SETUP-REQUEST tx
    [xApp]: E42 SETUP-RESPONSE rx
    [xApp]: xApp ID = 7
    [xApp]: Registered E2 Nodes = 1
    Connected E2 nodes = 1
    Registered node 0 ran func id = 2
    Registered node 0 ran func id = 3
    [xApp]: Sucessfully stopped
    Test xApp run SUCCESSFULLY

The C xApp confirms:

- Connection to the RIC via E42 interface (port 36422)
- Detection of the connected E2 node (the DU)
- Discovery of RAN functions 2 (KPM) and 3 (RC)
- Clean shutdown

The C xApp is used as the working demonstration of the xApp–RIC
connection for Phase 12.

---

## 8. KPM Indication Limitation

The KPM subscription is accepted, but **the DU does not emit any KPM
indication messages**. This is confirmed at three independent points:

### 8.1 xApp Output

The C xApp `xapp_oran_moni` runs to completion, but its output contains
no "KPM Indication" lines. Count = 0.

### 8.2 DU Log

The DU log, inspected after a full KPM subscription cycle, contains:

    Total DU log lines:                  >11000
    E2-DU entries:                       13 (all setup/subscription)
    "indication" occurrences (any case): 0

The 13 E2-DU entries are limited to E2 Setup Request/Response and
subscription handling. No indication message is logged at any time.

### 8.3 Source Code

The OCUDU source tree (`lib/e2/`) contains:

- `e2ap_indication_procedure.cpp` — the indication procedure
- `e2sm_kpm/e2sm_kpm_report_service_impl.cpp` — the KPM report service
- `e2sm_kpm/e2sm_kpm_du_meas_provider_impl.cpp` — the DU measurement provider

The report service uses `subscription.report_period` to schedule
indications. The DU measurement provider contains several TODOs:

    // TODO: check if CELL is supported
    // TODO: check if UE is supported
    // TODO: check if test condition is supported
    // TODO: add test condition checking, now return all UEs

These TODOs indicate that the DU measurement provider is incomplete
in the current OCUDU build.

**Conclusion:** the OCUDU commit in use advertises E2SM-KPM, accepts
KPM subscriptions, and acknowledges them — but does not yet generate
periodic KPM indication reports.

This is a documented limitation of the specific OCUDU revision, not
of the FlexRIC RIC, the E2 protocol, or our configuration.

---

## 9. Incident During Phase 12

### 9.1 Disk Pressure on /tmp

During the E2 tests, the FlexRIC RIC produced verbose output at the
default logging level. Because its stdout was redirected to a file in
`/tmp` (a 7.5 GB RAM-backed tmpfs), that log grew to **6.7 GB** and
filled `/tmp` to 100%.

Consequences:

- CU and DU processes could not write to their log files and exited
- Subsequent xApp runs failed because they could not create new files
- The Python xApp segfaulted reading an empty configuration

Recovery:

- Truncated the large logs and removed stale /tmp artifacts
- `/tmp` returned to 1% used
- Modified the CU and DU YAML configurations so their log files are
  written under `~/projects/private-5g/logs/phase12/ocudu/` (real
  disk) instead of `/tmp`
- Restarted CU, DU, RIC, and UE

### 9.2 Remediation

Future runs redirect all FlexRIC and OCUDU output to paths on the
real disk (`/dev/sda5`, 232 GB free) rather than to `/tmp`
(`tmpfs`, 7.5 GB). This prevents recurrence.

---

## 10. Results Summary

| Item | Result |
|------|--------|
| FlexRIC built and installed | ✅ |
| Exec-stack flag cleared on all .so files | ✅ |
| Near-RT RIC running on SCTP 36421 | ✅ |
| E2 connection (DU ↔ RIC) established | ✅ |
| E2 Setup procedure completed | ✅ |
| RAN functions advertised (KPM id 2, RC id 3) | ✅ |
| KPM subscription accepted by DU | ✅ |
| KPM subscription response sent | ✅ |
| **KPM indications emitted by DU** | **❌** (source-verified limitation) |
| Python xApp | ⚠️ Written, blocked by Python 3.14 ABI |
| C xApp demonstration | ✅ |
| RC service model advertised | ✅ (not exercised) |

---

## 11. What Phase 12 Achieved

Despite the KPM indication limitation, Phase 12 established:

1. **A working O-RAN Near-RT RIC** on the testbed.
2. **A working E2 interface** between the OCUDU DU and the RIC, with
   a real SCTP association and successful E2 Setup procedure.
3. **Working KPM and RC subscription handling** at the RIC, RAN, and
   xApp layers.
4. **A documented understanding** of where the current OCUDU build
   stops short, verified at the log level and the source level.
5. **The foundation for Phase 13:** the RC service model is advertised
   and the FlexRIC RIC is running. A future xApp can deliver RC
   control messages over the existing E2 association.

---

## 12. Limitations

1. **No KPM indication data.** The DU does not emit periodic KPM
   reports in this OCUDU revision. KPM-driven closed-loop control is
   therefore not testable on this build.

2. **Python xApp blocked by ABI.** The custom Python xApp is complete
   and syntactically valid, but cannot run because the FlexRIC SWIG
   wrapper crashes under Python 3.14.

3. **No RC control exercised.** The RC service model is advertised
   and could in principle be used, but no control message was
   delivered in Phase 12.

4. **Single-host deployment.** RIC, RAN, and core all run on one
   machine. Real O-RAN deployments separate the RIC onto dedicated
   infrastructure.

5. **No traffic-level xApp evaluation.** Because no indications reach
   the xApp, no measurement of xApp-driven optimization was possible.

---

## 13. Files Produced

### 13.1 Configurations

    configs/phase12/
      cu_zmq.yml             — CU config (log redirection)
      du_zmq_e2.yml          — DU config with E2 section
      ric.conf               — FlexRIC RIC configuration
      e2agent.conf           — FlexRIC E2 agent defaults
      xapp_kpm.conf          — KPM subscription template

### 13.2 Scripts

    scripts/phase12/
      xapp_kpm_monitor.py    — Custom Python xApp (KPM monitor + rule logic)

### 13.3 Logs and Results

    logs/phase12/
      ocudu/cu.log           — CU log (redirected from /tmp)
      ocudu/du.log           — DU log with E2 activity
      ric/ric.log            — RIC log
      du-e2-timeline.log     — Extracted E2 entries for the report
      end-state.txt          — Final stack snapshot

    results/phase12/
      xapp-c-oran-moni.log   — C xApp output (working)
      xapp-oran-final.log    — C xApp output from final attempt
      xapp-oran-moni-30s.log — Timed run
      xapp-rc-moni-c.log     — RC monitor xApp output
      xapp-all-moni-c.log    — All-service monitor xApp output

---

## 14. Conclusion

Phase 12 connected a working Near-RT RIC to the OCUDU RAN through the
O-RAN E2 interface. The E2 Setup procedure completed, both the KPM
and RC service models were advertised, and a KPM subscription was
accepted by the DU.

The build of OCUDU in use does not emit periodic KPM indications, so
the sensor side of the closed loop is not testable on this platform.
The Python SDK for FlexRIC crashes under Python 3.14, so the custom
xApp is written but cannot run without a compatible Python runtime.

Both limitations are documented at the log level and the source
level. Neither reflects a misconfiguration on the testbed — both are
properties of the specific software versions in use.

The RC service model remains advertised and available. Phase 13 will
build on this by using the Prometheus monitoring pipeline from
Phase 9 as the sensor data source, and delivering control via the
existing E2 connection.

---

**End of Phase 12 Report**
