#!/usr/bin/env python3
"""
Phase 17 — Generate 10 publication-quality figures for the thesis.

Reads results/*.csv and master_summary.csv, produces:
  figures/F01_scalability.{pdf,png}
  ... F10_summary.{pdf,png}
"""

import csv
import re
import statistics
from pathlib import Path
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

WORK = Path("/home/mohammad/projects/ns3-lena-sweep")
RESULTS = WORK / "results"
FIGDIR = WORK / "figures"
FIGDIR.mkdir(exist_ok=True)

plt.rcParams.update({
    "font.size": 10,
    "axes.titlesize": 11,
    "axes.labelsize": 10,
    "legend.fontsize": 9,
    "figure.dpi": 120,
    "savefig.bbox": "tight",
})

COLOR = {
    "blue":   "#1f77b4",
    "orange": "#ff7f0e",
    "green":  "#2ca02c",
    "red":    "#d62728",
    "purple": "#9467bd",
    "brown":  "#8c564b",
}

def load(path):
    if not path.exists():
        return []
    with open(path) as f:
        return list(csv.DictReader(f))

def flt(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None

def save(fig, stem):
    pdf = FIGDIR / f"{stem}.pdf"
    png = FIGDIR / f"{stem}.png"
    fig.savefig(pdf)
    fig.savefig(png, dpi=150)
    plt.close(fig)
    print(f"  wrote {pdf.name}  and  {png.name}")

# ============================================================
# F01 — Scalability: delay and throughput vs UE count
# ============================================================
def f01():
    rows = load(RESULTS / "s1_ngmn.csv")
    by = defaultdict(lambda: {"d": [], "t": []})
    for r in rows:
        ue = r.get("ue_count")
        d = flt(r.get("mean_delay_ms"))
        t = flt(r.get("mean_throughput_mbps"))
        if ue is None: continue
        if d is not None: by[int(ue)]["d"].append(d)
        if t is not None: by[int(ue)]["t"].append(t)
    ues = sorted(by.keys())
    dmean = [statistics.mean(by[u]["d"]) for u in ues]
    dsd   = [statistics.stdev(by[u]["d"]) if len(by[u]["d"]) > 1 else 0 for u in ues]
    tmean = [statistics.mean(by[u]["t"]) for u in ues]
    tsd   = [statistics.stdev(by[u]["t"]) if len(by[u]["t"]) > 1 else 0 for u in ues]

    fig, ax1 = plt.subplots(figsize=(7, 4))
    ax1.errorbar(ues, dmean, yerr=dsd, marker="o", color=COLOR["blue"],
                 capsize=3, label="Mean delay")
    ax1.set_xlabel("Number of UEs")
    ax1.set_ylabel("Mean delay (ms)", color=COLOR["blue"])
    ax1.tick_params(axis="y", labelcolor=COLOR["blue"])
    ax1.grid(True, alpha=0.3)

    ax2 = ax1.twinx()
    ax2.errorbar(ues, tmean, yerr=tsd, marker="s", color=COLOR["orange"],
                 capsize=3, label="Aggregate throughput")
    ax2.set_ylabel("Aggregate throughput (Mbps)", color=COLOR["orange"])
    ax2.tick_params(axis="y", labelcolor=COLOR["orange"])

    ax1.set_title("S1 — Scalability: NGMN mixed traffic, UMi, 3.5 GHz")
    save(fig, "F01_scalability")

# ============================================================
# F02 — TDD pattern
# ============================================================
def f02():
    rows = load(RESULTS / "s13_tdd.csv")
    by = defaultdict(lambda: {"d": [], "t": []})
    for r in rows:
        p = r.get("pattern")
        d = flt(r.get("mean_delay_ms"))
        t = flt(r.get("mean_flow_throughput_mbps"))
        if p is None: continue
        if d is not None: by[p]["d"].append(d)
        if t is not None: by[p]["t"].append(t)
    order = ["8dl2ul", "6dl4ul", "lte_style", "4dl6ul", "2dl8ul"]
    labels = ["8DL\n2UL", "6DL\n4UL", "LTE\nstyle", "4DL\n6UL", "2DL\n8UL"]
    dmean = [statistics.mean(by[p]["d"]) for p in order]
    dsd   = [statistics.stdev(by[p]["d"]) if len(by[p]["d"]) > 1 else 0 for p in order]

    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.bar(labels, dmean, yerr=dsd, capsize=4,
                  color=[COLOR["blue"], COLOR["blue"], COLOR["green"],
                         COLOR["orange"], COLOR["red"]])
    for b, v in zip(bars, dmean):
        ax.text(b.get_x() + b.get_width()/2, v + 15, f"{v:.0f}",
                ha="center", fontsize=9)
    ax.set_ylabel("Mean flow delay (ms)")
    ax.set_title("S13 — TDD pattern impact at 30 UEs, NGMN mixed")
    ax.grid(True, axis="y", alpha=0.3)
    save(fig, "F02_tdd_pattern")

# ============================================================
# F03 — Numerology
# ============================================================
def f03():
    rows = load(RESULTS / "s10_numerology.csv")
    by = defaultdict(list)
    for r in rows:
        run = r.get("run", "")
        m = re.match(r"s10_num(\d)_seed\d+", run)
        if not m: continue
        d = flt(r.get("mean_flow_delay_ms"))
        if d is not None:
            by[int(m.group(1))].append(d)
    nums = sorted(by.keys())
    means = [statistics.mean(by[n]) for n in nums]
    sds   = [statistics.stdev(by[n]) if len(by[n]) > 1 else 0 for n in nums]
    labels = [f"μ={n}\n({15 * 2**n} kHz)" for n in nums]

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(labels, means, yerr=sds, capsize=4,
           color=[COLOR["red"], COLOR["orange"], COLOR["blue"], COLOR["green"]])
    ax.set_yscale("log")
    ax.set_ylabel("Mean flow delay (ms, log scale)")
    ax.set_title("S10 — Numerology sweep (15 kHz → 120 kHz SCS)")
    ax.grid(True, axis="y", alpha=0.3, which="both")
    save(fig, "F03_numerology")

# ============================================================
# F04 — Bandwidth
# ============================================================
def f04():
    rows = load(RESULTS / "s11_bandwidth.csv")
    by = defaultdict(list)
    for r in rows:
        run = r.get("run", "")
        m = re.match(r"s11_(\d+m)_seed\d+", run)
        if not m: continue
        d = flt(r.get("mean_flow_delay_ms"))
        if d is not None:
            by[m.group(1)].append(d)
    order = ["10m", "20m", "40m", "80m"]
    order = [o for o in order if o in by]
    means = [statistics.mean(by[o]) for o in order]
    sds   = [statistics.stdev(by[o]) if len(by[o]) > 1 else 0 for o in order]

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(order, means, yerr=sds, capsize=4,
           color=[COLOR["red"], COLOR["orange"], COLOR["blue"], COLOR["green"]][:len(order)])
    ax.set_yscale("log")
    ax.set_ylabel("Mean flow delay (ms, log scale)")
    ax.set_xlabel("Bandwidth")
    ax.set_title("S11 — Bandwidth sweep")
    ax.grid(True, axis="y", alpha=0.3, which="both")
    save(fig, "F04_bandwidth")

# ============================================================
# F05 — Notching
# ============================================================
def f05():
    rows = load(RESULTS / "s8_notching.csv")
    by = defaultdict(list)
    for r in rows:
        run = r.get("run", "")
        m = re.match(r"s8_(\w+)_seed\d+", run)
        if not m: continue
        d = flt(r.get("mean_flow_delay_ms"))
        if d is not None:
            by[m.group(1)].append(d)
    order = ["none", "light", "heavy"]
    order = [o for o in order if o in by]
    means = [statistics.mean(by[o]) for o in order]
    sds   = [statistics.stdev(by[o]) if len(by[o]) > 1 else 0 for o in order]

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(order, means, yerr=sds, capsize=4,
           color=[COLOR["green"], COLOR["orange"], COLOR["red"]][:len(order)])
    ax.set_ylabel("Mean flow delay (ms)")
    ax.set_title("S8 — Notching (ICIC) impact")
    ax.grid(True, axis="y", alpha=0.3)
    save(fig, "F05_notching")

# ============================================================
# F06 — XR traffic
# ============================================================
def f06():
    rows = load(RESULTS / "s9_xr.csv")
    by_d = defaultdict(list)
    by_t = defaultdict(list)
    for r in rows:
        run = r.get("run", "")
        m = re.match(r"s9_(\w+)_seed\d+", run)
        if not m: continue
        d = flt(r.get("mean_flow_delay_ms"))
        t = flt(r.get("mean_flow_throughput_mbps"))
        if d is not None: by_d[m.group(1)].append(d)
        if t is not None: by_t[m.group(1)].append(t)
    order = ["light", "medium", "heavy"]
    order = [o for o in order if o in by_d]
    dmeans = [statistics.mean(by_d[o]) for o in order]
    tmeans = [statistics.mean(by_t[o]) for o in order]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))
    ax1.bar(order, dmeans, color=[COLOR["green"], COLOR["orange"], COLOR["red"]][:len(order)])
    ax1.set_ylabel("Mean flow delay (ms)")
    ax1.set_title("S9 — XR traffic: delay")
    ax1.grid(True, axis="y", alpha=0.3)

    ax2.bar(order, tmeans, color=[COLOR["green"], COLOR["orange"], COLOR["red"]][:len(order)])
    ax2.set_ylabel("Mean flow throughput (Mbps)")
    ax2.set_title("S9 — XR traffic: throughput")
    ax2.grid(True, axis="y", alpha=0.3)

    fig.suptitle("S9 — 3GPP XR traffic (AR/VR/CG): heavy = network overload", y=1.02)
    save(fig, "F06_xr")

# ============================================================
# F07 — Simple QoS
# ============================================================
def f07():
    rows = load(RESULTS / "s5_simple_qos.csv")
    by_d = defaultdict(list)
    by_t = defaultdict(list)
    for r in rows:
        run = r.get("run", "")
        m = re.match(r"s5_(\w+)_seed\d+", run)
        if not m: continue
        d = flt(r.get("mean_flow_delay_ms"))
        t = flt(r.get("mean_flow_throughput_mbps"))
        if d is not None: by_d[m.group(1)].append(d)
        if t is not None: by_t[m.group(1)].append(t)
    cfgs = sorted(by_d.keys())
    dmeans = [statistics.mean(by_d[c]) for c in cfgs]
    tmeans = [statistics.mean(by_t[c]) for c in cfgs]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))
    ax1.bar(cfgs, dmeans, color=[COLOR["blue"], COLOR["orange"]])
    ax1.set_ylabel("Mean flow delay (ms)")
    ax1.set_title("S5 — Simple QoS: delay")
    ax1.grid(True, axis="y", alpha=0.3)

    ax2.bar(cfgs, tmeans, color=[COLOR["blue"], COLOR["orange"]])
    ax2.set_ylabel("Mean flow throughput (Mbps)")
    ax2.set_title("S5 — Simple QoS: throughput")
    ax2.grid(True, axis="y", alpha=0.3)

    fig.suptitle("S5 — Simple QoS scheduler comparison")
    save(fig, "F07_qos")

# ============================================================
# F08 — MIMO vs SISO
# ============================================================
def f08():
    rows = load(RESULTS / "s7_mimo.csv")
    by_d = defaultdict(list)
    for r in rows:
        run = r.get("run", "")
        m = re.match(r"s7_(\w+)_seed\d+", run)
        if not m: continue
        d = flt(r.get("mean_flow_delay_ms"))
        if d is not None: by_d[m.group(1)].append(d)
    cfgs = ["siso", "mimo"]
    cfgs = [c for c in cfgs if c in by_d]
    means = [statistics.mean(by_d[c]) for c in cfgs]
    sds   = [statistics.stdev(by_d[c]) if len(by_d[c]) > 1 else 0 for c in cfgs]

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar([c.upper() for c in cfgs], means, yerr=sds, capsize=4,
           color=[COLOR["blue"], COLOR["green"]])
    ax.set_ylabel("Mean flow delay (ms)")
    ax.set_title("S7 — MIMO vs SISO delay")
    ax.grid(True, axis="y", alpha=0.3)
    save(fig, "F08_mimo")

# ============================================================
# F09 — Cross-study throughput overview
# ============================================================
def f09():
    studies = [
        ("S1 30UE",     "s1_ngmn.csv",       "mean_throughput_mbps",          lambda r: r.get("ue_count") == "30"),
        ("S1 90UE",     "s1_ngmn.csv",       "mean_throughput_mbps",          lambda r: r.get("ue_count") == "90"),
        ("S1 150UE",    "s1_ngmn.csv",       "mean_throughput_mbps",          lambda r: r.get("ue_count") == "150"),
        ("S13 6DL4UL",  "s13_tdd.csv",       "mean_flow_throughput_mbps",     lambda r: r.get("pattern") == "6dl4ul"),
        ("S13 8DL2UL",  "s13_tdd.csv",       "mean_flow_throughput_mbps",     lambda r: r.get("pattern") == "8dl2ul"),
        ("S10 num3",    "s10_numerology.csv","mean_flow_throughput_mbps",     lambda r: r.get("run","").startswith("s10_num3")),
        ("S11 20m",     "s11_bandwidth.csv", "mean_flow_throughput_mbps",     lambda r: r.get("run","").startswith("s11_20m")),
        ("S7 mimo",     "s7_mimo.csv",       "mean_flow_throughput_mbps",     lambda r: r.get("run","").startswith("s7_mimo")),
        ("S9 light",    "s9_xr.csv",         "mean_flow_throughput_mbps",     lambda r: r.get("run","").startswith("s9_light")),
    ]
    labels, means = [], []
    for label, fname, col, pred in studies:
        rows = [r for r in load(RESULTS / fname) if pred(r)]
        vals = [flt(r.get(col)) for r in rows]
        vals = [v for v in vals if v is not None]
        if vals:
            labels.append(label)
            means.append(statistics.mean(vals))

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.barh(labels, means, color=COLOR["blue"])
    ax.set_xlabel("Aggregate / mean throughput (Mbps)")
    ax.set_title("S-cross — Throughput across studies (selected configurations)")
    ax.grid(True, axis="x", alpha=0.3)
    save(fig, "F09_throughput_overview")

# ============================================================
# F10 — Summary: two strongest studies together
# ============================================================
def f10():
    # left: scalability delay
    rows = load(RESULTS / "s1_ngmn.csv")
    by = defaultdict(list)
    for r in rows:
        ue = r.get("ue_count")
        d = flt(r.get("mean_delay_ms"))
        if ue and d is not None:
            by[int(ue)].append(d)
    ues = sorted(by.keys())
    dmean = [statistics.mean(by[u]) for u in ues]
    dsd   = [statistics.stdev(by[u]) if len(by[u]) > 1 else 0 for u in ues]

    # right: TDD
    rows2 = load(RESULTS / "s13_tdd.csv")
    by2 = defaultdict(list)
    for r in rows2:
        p = r.get("pattern")
        d = flt(r.get("mean_delay_ms"))
        if p and d is not None:
            by2[p].append(d)
    order = ["8dl2ul", "6dl4ul", "lte_style", "4dl6ul", "2dl8ul"]
    order = [o for o in order if o in by2]
    dmean2 = [statistics.mean(by2[o]) for o in order]
    dsd2   = [statistics.stdev(by2[o]) if len(by2[o]) > 1 else 0 for o in order]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4))

    ax1.errorbar(ues, dmean, yerr=dsd, marker="o", capsize=3, color=COLOR["blue"])
    ax1.set_xlabel("Number of UEs")
    ax1.set_ylabel("Mean delay (ms)")
    ax1.set_title("(a) Scalability (S1)")
    ax1.grid(True, alpha=0.3)

    ax2.bar([o.replace("dl","DL").replace("ul","UL").replace("_","\n") for o in order],
            dmean2, yerr=dsd2, capsize=3,
            color=[COLOR["blue"], COLOR["blue"], COLOR["green"], COLOR["orange"], COLOR["red"]])
    ax2.set_ylabel("Mean delay (ms)")
    ax2.set_title("(b) TDD pattern (S13)")
    ax2.grid(True, axis="y", alpha=0.3)

    fig.suptitle("Simulation summary — two strongest scaling results", y=1.02)
    save(fig, "F10_summary")

# ============================================================
# Run all
# ============================================================
print("=== Generating figures ===")
f01(); f02(); f03(); f04(); f05()
f06(); f07(); f08(); f09(); f10()

print()
print("=== Final figure list ===")
for f in sorted(FIGDIR.glob("*.pdf")):
    print(f"  {f.name}  ({f.stat().st_size:,} bytes)")
