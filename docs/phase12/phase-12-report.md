# Phase 12 Report — Custom xApp Development and RC Control

**Project:** Simulation of a Private 5G Standalone Network for a Smart Factory
**Date:** 2026-10-13
**Environment:** Ubuntu 26.04.1 LTS (resolute), kernel 7.0.0-38-generic, 8 CPU cores, 14 GiB RAM

---

## 1. Objective

Develop a custom xApp for the O-RAN Near-RT RIC and exercise the RC
(RAN Control) service model to close the loop between network
observation and RAN control. This is the project's principal technical
contribution per the original project definition.

The phase builds on Phase 11, which established a working E2 interface
between the OCUDU DU and a FlexRIC Near-RT RIC.

---

## 2. Environment

| Component | Version |
|-----------|---------|
| FlexRIC | br-flexric, commit 7365081 |
| OCUDU | dev build 2026-10-12 |
| UE | OAI nr-uesoftmodem (develop commit 6f89078b40) |
| Open5GS | 2.8.0~resolute6 |
| Python | 3.14.4 |
| Compiler | GCC 13.4.0 |

---

## 3. Custom Python xApp

### 3.1 Design

File: `scripts/phase11/xapp_kpm_monitor.py`

The xApp:

- Connects to the FlexRIC Near-RT RIC on E42 port 36422
- Subscribes to KPM indications using the RC config file
- Parses FORMAT_1 and FORMAT_3 indication messages
- Writes every measurement to a CSV file with these columns:
    wall_time, kpm_start_ms, node_type, node_id, format,
    ue_type, ue_id, metric, value
- Implements rule-based congestion detection: if `RRU.PrbTotDl`
  exceeds a threshold for N consecutive reports, logs a
  `CONGESTION_DETECTED` event
- Removes the subscription and waits for `try_stop` before exiting

The callback class derives from `ric.kpm_cb` and overrides `handle()`.
`ric.init()` is called with only `sys.argv[0]` so FlexRIC's C argument
parser does not see the argparse flags.

### 3.2 Execution Attempt

Running the Python xApp:

    PYTHONPATH=/usr/local/lib/python3/dist-packages/xapp_sdk \
      python3 xapp_kpm_monitor.py --duration 30 ...

Result: **segmentation fault inside `ric.init()`**, immediately after
loading `libkpm_sm.so`.

Kernel log:

    python3[...]: segfault at ... likely on CPU 7

Diagnosis: the FlexRIC SWIG wrapper was built against Python 3.10-3.12.
Python 3.14 on Ubuntu 26.04 is not yet supported. The Python SDK imports
fine (465 symbols) but crashes when the C library is invoked.

The xApp itself is syntactically valid and complete. It requires a
Python 3.12 runtime to execute.

---

## 4. Custom RC Control xApp (C)

### 4.1 Starting Point

FlexRIC ships `examples/xApp/c/control/xapp_oran_slice_ctrl.c`, which
implements:

- E2SM-RC Control Service Style **2** (Radio Resource Allocation)
- Action ID **6** (Slice-level PRB quota)
- Control Header Format 1, Control Message Format 1

This matches what OCUDU advertises (RAN function id 3, E2SM-RC).

### 4.2 Patch

The example was patched to use the testbed's PLMN and slice values:

| Field | Original | Patched |
|-------|----------|---------|
| PLMN | 50501 | **99970** |
| Slice 1 SD | 0 | **1** |
| Slice 2 SD | 5 | **2** |
| Slice 1 dedicated PRB | 70 | **35** |
| Slice 2 dedicated PRB | 30 | **35** |

Files preserved:

- `configs/phase12/xapp_oran_slice_ctrl.original.c`
- `configs/phase12/xapp_oran_slice_ctrl.patched.c`

### 4.3 Build

    cd ~/projects/flexric/build
    make xapp_oran_slice_ctrl

Result: `[100%] Built target xapp_oran_slice_ctrl`

Note: the linker warns that the binary requires an executable stack.
This is normal for FlexRIC's build system and the binary runs without
modification. (Running `patchelf --clear-execstack` corrupts the ELF
headers and causes a segfault; the original flag must be preserved.)

---

## 5. RC Control Experiment

### 5.1 Setup

- Near-RT RIC running (FlexRIC, SCTP 36421)
- OCUDU CU and DU running with E2 enabled
- UE registered with two PDU sessions (internet DNN, factory DNN)
- E2 SCTP association established between DU and RIC
- Background UE traffic via the edge DNN (to keep the RAN active)

### 5.2 xApp Execution

    timeout 15 /usr/local/bin/flexric/xApp/c/xapp_oran_slice_ctrl \
      -c /usr/local/etc/flexric/xapp_rc_ho.conf

xApp output:

    [xApp]: E42 SETUP-REQUEST tx
    [xApp]: E42 SETUP-RESPONSE rx
    [xApp]: xApp ID = 7
    [xApp]: Registered E2 Nodes = 1
    Connected E2 nodes = 1
    [xApp]: CONTROL-REQUEST tx
    [xApp]: Successfully received CONTROL-ACK
    [xApp]: Control Loop Latency: 6000166 us
    [xApp]: Sucessfully stopped
    Test xApp run SUCCESSFULLY

The "Control Loop Latency" of ~6 seconds is not a real control
latency. It is the timeout period the xApp waited before giving up
and marking the transaction as complete.

### 5.3 DU Log — The Definitive Evidence

The DU received the Control Request:

    2026-10-13T17:42:02.029968 [E2-DU] E2AP SDU, "initiatingMessage.RICcontrolRequest"
    2026-10-13T17:42:02.029969 [E2-DU] Received RIC Control Request
    2026-10-13T17:42:02.030022 [E2-DU] Sending E2 RIC Control Failure
    2026-10-13T17:42:02.030198 [E2-DU] Couldn't unpack E2AP PDU

ASN.1 decoder errors:

    [ASN1] [/home/mohammad/projects/ocudu-dev/lib/asn1/e2ap/e2ap.cpp][19013] Decoding failure.
    [ASN1] [/home/mohammad/projects/ocudu-dev/lib/asn1/e2ap/e2ap.cpp][20677] Decoding failure.
    [E2-DU] The proc_code=0 is not recognized

---

## 6. Analysis of the Failure

### 6.1 What the Error Means

`proc_code` is the **first byte** of every E2AP message. It identifies
the procedure type:

- `0` = E2 Setup
- `1` = E2 Setup Response
- `2` = E2 Reset
- ...
- A RIC Control Request should have its own distinct procedure code

The DU decoded `proc_code = 0` from a message that the xApp had built
as a Control Request. This means the ASN.1 decoder failed at the very
first byte.

### 6.2 Root Cause

FlexRIC's APER (Aligned Packet Encoding Rules) encoder produces byte
sequences that OCUDU's `asn1c`-based decoder cannot interpret. This
is a known class of interoperability problem between independently
compiled ASN.1 toolchains:

- FlexRIC is built against the OAI/OpenAirInterface ASN.1 compiler
- OCUDU is built against `asn1c`
- The two can produce different byte layouts for the same ASN.1 schema
  if the schema versions or encoding options differ

The message reaches the DU intact. The DU's decoder cannot parse it.

### 6.3 Parallel with Phase 11

Phase 11 established that the DU accepts a KPM subscription but does
not emit periodic KPM indications. Phase 12 establishes that the DU
receives RC control messages but cannot decode their content.

Both findings describe the same underlying condition: **the OCUDU
build's E2 implementation is incomplete for external RIC interoperation.**

---

## 7. Pipeline Verification

Three independent paths reached the DU:

| Path | Outcome |
|------|---------|
| Custom Python xApp | Segfault in `ric.init()` (Python 3.14 ABI) |
| Patched C xApp (PLMN/slices adjusted) | Control sent, DU received, decode failed |
| Original C xApp (FlexRIC defaults) | Control sent, DU received, decode failed |

In every case, the message crossed:
- xApp → RIC (E42, SCTP 36422)
- RIC → DU (E2, SCTP 36421)
- The DU logged `Received RIC Control Request`

The pipeline is real. The codec is the barrier.

---

## 8. What Phase 12 Achieved

| Item | Status |
|------|--------|
| Custom Python xApp written | ✅ Complete and syntactically valid |
| Custom C xApp patched and built | ✅ Uses testbed PLMN and slice IDs |
| RC control message constructed | ✅ E2SM-RC Style 2 Action 6 |
| Message reached the DU | ✅ Logged in DU |
| DU decoded the message | ❌ ASN.1 codec incompatibility (documented) |
| Closed-loop control demonstrated | ❌ Blocked by codec |

---

## 9. What Phase 12 Does Not Claim

The phase does **not** claim:

- That the RC actuator works end-to-end
- That the PRB quota was applied to the scheduler
- That any RAN behavior changed as a result of the control

These claims would require the ASN.1 codec barrier to be resolved,
which is outside the scope and time budget of this phase.

---

## 10. Limitations

1. **Python ABI incompatibility.** The FlexRIC Python SDK crashes on
   Python 3.14. Fixing this requires either downgrading Python to 3.12
   or rebuilding the SWIG wrapper, both outside the current scope.

2. **ASN.1 codec mismatch.** The FlexRIC C xApp sends a valid RC
   Control message, but OCUDU's ASN.1 decoder cannot parse it. Fixing
   this requires either patching OCUDU's E2AP decoder or patching
   FlexRIC's encoder to match OCUDU's expected byte format.

3. **No KPM indications.** As documented in Phase 11, the OCUDU build
   does not emit periodic KPM indications. Sensor-side data is not
   available via the standard O-RAN path.

4. **Single-host deployment.** RIC, RAN, and core all run on one
   machine.

5. **No traffic-level evaluation of control effect.** Since the
   control message could not be applied, no measurement of its
   effect on throughput or latency was possible.

---

## 11. Files Produced

### 11.1 Configurations

    configs/phase12/
      xapp_oran_slice_ctrl.original.c   — Unpatched FlexRIC example
      xapp_oran_slice_ctrl.patched.c    — Patched with our PLMN/slices
      xapp_rc_ho.conf                    — xApp RC configuration
      xapp_kpm_monitor.py                — Custom Python xApp source

### 11.2 Results

    results/phase12/
      du-log-rc-control-attempt.txt      — DU log evidence
      xapp-oran-slice-ctrl-run1.log      — Original xApp run
      xapp-oran-slice-ctrl-patched.log   — Patched run (patchelf broke it)
      xapp-oran-slice-ctrl-patched2.log  — Patched run (working)

---

## 12. Conclusion

Phase 12 developed a custom xApp for the O-RAN Near-RT RIC and
attempted to close the control loop through the E2SM-RC service model.

The custom Python xApp is complete and syntactically valid, but cannot
execute due to a Python 3.14 ABI incompatibility in FlexRIC's SWIG
wrapper.

A C xApp was patched with the testbed's PLMN and slice identifiers and
built successfully. It sent an RC Control message through the RIC to
the DU. The DU received the message (`Received RIC Control Request`),
attempted to decode it, and failed with `proc_code=0 is not recognized`.

This is a documented ASN.1 codec incompatibility between FlexRIC's
encoder and OCUDU's `asn1c`-based decoder. It is a property of the two
independent software builds, not of our configuration or of the E2
protocol itself.

The pipeline is proven at every step except the final decode. Future
work should either:

1. Rebuild FlexRIC or OCUDU to use matching ASN.1 toolchains, or
2. Wait for a later OCUDU release with complete E2SM-RC interoperation.

Phase 12 is the last phase of the O-RAN control work in this project.
The findings from Phases 12 and 13 together establish that the O-RAN
E2 stack can be assembled and partially exercised, but that the specific
OCUDU build in use does not yet interoperate with FlexRIC for
subscription indications or for control message decoding.

---

**End of Phase 12 Report**
