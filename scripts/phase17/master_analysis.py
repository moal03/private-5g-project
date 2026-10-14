#!/usr/bin/env python3
"""
Phase 17 — Master analysis across all 13 simulation studies.

Reads every result CSV, computes per-configuration aggregates
(mean, stdev, min, max, n), and writes:
  - results/master_summary.csv    (machine-readable)
  - results/master_summary.txt    (human-readable thesis text)
"""

import csv
import re
import statistics
from pathlib import Path
from collections import defaultdict

WORK = Path("/home/mohammad/projects/ns3-lena-sweep")
RESULTS = WORK / "results"

def load(path):
    if not path.exists():
        return []
    with open(path) as f:
        return list(csv.DictReader(f))

def agg(values):
    values = [v for v in values if v is not None]
    if not values:
        return None
    if len(values) == 1:
        return {"n": 1, "mean": values[0], "stdev": 0.0,
                "min": values[0], "max": values[0]}
    return {
        "n": len(values),
        "mean": statistics.mean(values),
        "stdev": statistics.stdev(values),
        "min": min(values),
        "max": max(values),
    }

lines = []
csv_rows = []

def section(title):
    lines.append("")
    lines.append("=" * 70)
    lines.append(f"  {title}")
    lines.append("=" * 70)

def report(group_label, key_fn, delay_key, thp_key, rows):
    """Group rows by key_fn(row), report mean±stdev of delay and throughput."""
    by = defaultdict(lambda: {"delay": [], "thp": []})
    for r in rows:
        k = key_fn(r)
        d = r.get(delay_key)
        t = r.get(thp_key)
        if k is None:
            continue
        if d not in (None, "", "None"):
            try: by[k]["delay"].append(float(d))
            except ValueError: pass
        if t not in (None, "", "None"):
            try: by[k]["thp"].append(float(t))
            except ValueError: pass

    if not by:
        lines.append("  (no data)")
        return

    lines.append(f"  {'config':<22} {'n':>3}  {'delay mean±sd (ms)':<24}  {'thp mean±sd (Mbps)':<24}")
    lines.append("  " + "-" * 76)

    def sort_key(x):
        try:
            return (0, float(x))
        except (ValueError, TypeError):
            return (1, str(x))

    for k in sorted(by.keys(), key=sort_key):
        ds = agg(by[k]["delay"])
        ts = agg(by[k]["thp"])
        d_str = f"{ds['mean']:.2f} ± {ds['stdev']:.2f}" if ds else "—"
        t_str = f"{ts['mean']:.2f} ± {ts['stdev']:.2f}" if ts else "—"
        n = max(ds["n"] if ds else 0, ts["n"] if ts else 0)
        lines.append(f"  {str(k):<22} {n:>3}  {d_str:<24}  {t_str:<24}")
        csv_rows.append({
            "study": group_label, "config": k, "n": n,
            "delay_mean_ms": f"{ds['mean']:.4f}" if ds else "",
            "delay_stdev_ms": f"{ds['stdev']:.4f}" if ds else "",
            "thp_mean_mbps": f"{ts['mean']:.4f}" if ts else "",
            "thp_stdev_mbps": f"{ts['stdev']:.4f}" if ts else "",
        })

def config_from_run(prefix):
    """Extract config token from a run id like s5_sc0_seed1."""
    def f(r):
        run = r.get("run", "")
        m = re.match(rf"{prefix}_([a-zA-Z0-9.]+)_seed\d+", run)
        return m.group(1) if m else run
    return f

# ============================================================
# S1 — scalability (UE count). Columns: ue_count, seed,
# mean_delay_ms, median_delay_ms, mean_throughput_mbps
# ============================================================
section("S1 — Scalability: UE count sweep (NGMN mixed, UMi, 3.5 GHz)")
rows = load(RESULTS / "s1_ngmn.csv")
report("S1_scalability", lambda r: r.get("ue_count"),
       "mean_delay_ms", "mean_throughput_mbps", rows)

# ============================================================
# S13 — TDD pattern. Columns: pattern, seed, mean_delay_ms,
# mean_flow_throughput_mbps
# ============================================================
section("S13 — TDD pattern sweep (30 UEs, 5 s, NGMN mixed)")
rows = load(RESULTS / "s13_tdd.csv")
report("S13_tdd", lambda r: r.get("pattern"),
       "mean_delay_ms", "mean_flow_throughput_mbps", rows)

# ============================================================
# Wave 2 studies (S5–S12). Columns: run, mean_flow_delay_ms,
# mean_flow_throughput_mbps. Config is the token between the
# study prefix and _seedN.
# ============================================================
wave2 = [
    ("S5 — Simple QoS scheduler",         "s5_simple_qos.csv",  "s5"),
    ("S6 — Carrier aggregation",          "s6_ca.csv",          "s6"),
    ("S7 — MIMO vs SISO",                 "s7_mimo.csv",        "s7"),
    ("S8 — Notching (ICIC) sweep",        "s8_notching.csv",    "s8"),
    ("S9 — 3GPP XR traffic (AR/VR/CG)",   "s9_xr.csv",          "s9"),
    ("S10 — Numerology sweep",            "s10_numerology.csv", "s10"),
    ("S11 — Bandwidth sweep",             "s11_bandwidth.csv",  "s11"),
    ("S12 — Frequency sweep",             "s12_frequency.csv",  "s12"),
]
for label, fname, prefix in wave2:
    section(label)
    rows = load(RESULTS / fname)
    report(prefix, config_from_run(prefix),
           "mean_flow_delay_ms", "mean_flow_throughput_mbps", rows)

# ============================================================
# Write outputs
# ============================================================
summary_txt = "\n".join(lines) + "\n"
(RESULTS / "master_summary.txt").write_text(summary_txt)

with open(RESULTS / "master_summary.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(csv_rows[0].keys()))
    w.writeheader(); w.writerows(csv_rows)

print(summary_txt)
print()
print(f"Wrote: {RESULTS/'master_summary.txt'}")
print(f"Wrote: {RESULTS/'master_summary.csv'}  ({len(csv_rows)} rows)")
