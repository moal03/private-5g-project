# Phase 17 — Source Patches to 5G-LENA

The ns-3 5G-LENA NGMN mixed-traffic example
(`contrib/nr/examples/cttc-nr-traffic-ngmn-mixed.cc` in ns-3.46) was patched
in three places to match the real testbed.

## Patch 1 — Carrier frequency

From: `m_centralFrequency = 2e9;`
To:   `m_centralFrequency = 3.5e9;  // band n78`

## Patch 2 — TDD pattern (initial, hardcoded)

From: `StringValue("F|F|F|F|F|F|F|F|F|F|")`
To:   `StringValue("DL|DL|DL|DL|DL|DL|UL|UL|UL|UL|")`

Applied at 3 places (one per gNB sector).

## Patch 3 — TDD pattern as a CLI parameter

The TDD pattern was converted to a runtime parameter:

    std::string tddPattern = "DL|DL|DL|DL|DL|DL|UL|UL|UL|UL|";
    cmd.AddValue("tddPattern", "TDD pattern (e.g. DL|DL|...)", tddPattern);

The pattern string is then passed into `Set5gLenaSimulatorParameters(...)`
as a new `std::string tddPattern` argument, where it replaces the three
hardcoded `StringValue(...)` calls.

## Reproducing the patches

The pre-patched backups are available in the ns-3 tree:

    cttc-nr-traffic-ngmn-mixed.cc.orig              (original, 2 GHz, FDD pattern)
    cttc-nr-traffic-ngmn-mixed.cc.pre-tdd-param     (after Patch 1 and Patch 2)

The patched file is `cttc-nr-traffic-ngmn-mixed.cc`.

## Effect

Without patches: 2 GHz carrier, FDD-style all-flexible pattern, single
frequency choice.

With patches: 3.5 GHz carrier (band n78), TDD 6DL+4UL pattern, and a
`--tddPattern` CLI flag that permits sweeping the DL/UL split without
recompiling. This is what enabled Study S13 (the TDD pattern sweep).
