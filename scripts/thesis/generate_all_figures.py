#!/usr/bin/env python3
"""
Generate all thesis figures from the raw experimental data.

Reads:  results/phase6/raw, results/phase7, results/phase8, results/phase10
Writes: figures/phase6/, figures/phase7/, figures/phase8/,
        figures/phase10/, figures/cross-phase/
"""
import csv, glob, json, re
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

REPO = Path("/home/mohammad/projects/private-5g")
FIG  = REPO / "figures"

plt.rcParams.update({
    "font.size": 10,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "figure.dpi": 120,
    "savefig.bbox": "tight",
})


# ---------- loaders ----------
def load_urllc(patterns):
    rtts = []
    for pat in patterns:
        for p in glob.glob(str(REPO / pat)):
            for row in csv.DictReader(open(p)):
                if row["status"] == "OK" and row["rtt_us"]:
                    rtts.append(int(row["rtt_us"]) / 1000.0)
    return np.array(sorted(rtts))


def load_ping(path_pattern):
    pat = re.compile(r"time[=<]([0-9]+(?:\.[0-9]+)?)\s*ms")
    vals = []
    for p in glob.glob(str(REPO / path_pattern)):
        for line in open(p, errors="replace"):
            m = pat.search(line)
            if m:
                vals.append(float(m.group(1)))
    return np.array(sorted(vals))


def load_ping_avg(path_pattern):
    pat = re.compile(r"rtt min/avg/max/mdev = [\d.]+/([\d.]+)/")
    vals = []
    for p in sorted(glob.glob(str(REPO / path_pattern))):
        text = Path(p).read_text(errors="replace")
        m = pat.search(text)
        if m:
            vals.append(float(m.group(1)))
    return vals


def load_probe_csv(path_pattern):
    files = sorted(glob.glob(str(REPO / path_pattern)))
    if not files:
        return []
    rows = []
    for row in csv.DictReader(open(files[-1])):
        try:
            rows.append({"ts": float(row["ts"]),
                         "ms": int(row["elapsed_ms"]) if row["elapsed_ms"] else None,
                         "code": row["http_code"]})
        except Exception:
            pass
    return sorted(rows, key=lambda r: r["ts"])


def load_timeline(path_pattern):
    files = sorted(glob.glob(str(REPO / path_pattern)))
    if not files:
        return {}
    from datetime import datetime
    info = {}
    for line in open(files[-1]):
        if line.startswith("Fault injected:"):
            info["fault"] = datetime.fromisoformat(line.split(":",1)[1].strip()).timestamp()
        elif line.startswith("Recovery started:"):
            info["recover"] = datetime.fromisoformat(line.split(":",1)[1].strip()).timestamp()
    return info


# ==================================================
# Phase 6 — Network slicing
# ==================================================
def phase6_figures():
    out = FIG / "phase6"
    loads = [0, 15, 35]
    colors = {"baseline": "steelblue", "treatment": "indianred"}

    # 1-3. CDF of RTT per load
    for load in loads:
        fig, ax = plt.subplots(figsize=(7, 5))
        for cond in ["baseline", "treatment"]:
            rtts = load_urllc([f"results/phase6/raw/{cond}_load{load}_trial*_urllc.csv"])
            if len(rtts) == 0: continue
            x = np.sort(rtts)
            y = np.arange(1, len(x)+1) / len(x)
            ax.plot(x, y, label=f"{cond} (n={len(x)})", color=colors[cond])
        ax.set_xlabel("RTT (ms)")
        ax.set_ylabel("Empirical CDF")
        ax.set_title(f"Phase 6 — URLLC RTT distribution at {load} Mbps eMBB load")
        ax.legend()
        fig.savefig(out / f"cdf-rtt-load{load}.png")
        plt.close(fig)

    # 4. p50/p95/p99 bar chart
    fig, ax = plt.subplots(figsize=(10, 5))
    metrics = [("p50", 50), ("p95", 95), ("p99", 99)]
    width = 0.12
    idx = np.arange(len(loads))
    for i, (mname, pct) in enumerate(metrics):
        for j, cond in enumerate(["baseline", "treatment"]):
            ys = []
            for load in loads:
                r = load_urllc([f"results/phase6/raw/{cond}_load{load}_trial*_urllc.csv"])
                ys.append(np.percentile(r, pct) if len(r) else 0)
            offset = (i*2 + j - 2.5) * width
            ax.bar(idx + offset, ys, width,
                   label=f"{cond} {mname}",
                   color=colors[cond], alpha=1.0 if mname=="p50" else (0.7 if mname=="p95" else 0.4),
                   edgecolor="black", linewidth=0.4)
    ax.set_xticks(idx)
    ax.set_xticklabels([f"{L} Mbps" for L in loads])
    ax.set_ylabel("RTT (ms)")
    ax.set_title("Phase 6 — Baseline vs treatment URLLC latency by load level")
    ax.legend(ncol=3, fontsize=8)
    fig.savefig(out / "percentile-bars.png")
    plt.close(fig)

    # 5. Per-trial box plot (p50 distribution across trials)
    fig, ax = plt.subplots(figsize=(9, 5))
    data, labels = [], []
    for load in loads:
        for cond in ["baseline", "treatment"]:
            avgs = []
            for t in [1,2,3]:
                r = load_urllc([f"results/phase6/raw/{cond}_load{load}_trial{t}_urllc.csv"])
                if len(r): avgs.append(np.median(r))
            data.append(avgs)
            labels.append(f"{cond[:3]}\n{load}M")
    bp = ax.boxplot(data, tick_labels=labels, patch_artist=True)
    for i, patch in enumerate(bp["boxes"]):
        patch.set_facecolor(colors["baseline"] if "bas" in labels[i] else colors["treatment"])
        patch.set_alpha(0.6)
    ax.set_ylabel("Per-trial median RTT (ms)")
    ax.set_title("Phase 6 — Per-trial median RTT, all conditions")
    fig.savefig(out / "trial-medians-boxplot.png")
    plt.close(fig)

    # 6. Time series of one trial
    fig, ax = plt.subplots(figsize=(10, 4))
    for i, (cond, trial) in enumerate([("baseline", 1), ("treatment", 1)]):
        p = REPO / f"results/phase6/raw/{cond}_load15_trial{trial}_urllc.csv"
        if not p.exists(): continue
        ts, rtt = [], []
        for row in csv.DictReader(open(p)):
            if row["status"] == "OK" and row["rtt_us"]:
                ts.append(float(row["ts"]) - 17400)
                rtt.append(int(row["rtt_us"])/1000.0)
        ax.plot(ts, rtt, label=f"{cond}", alpha=0.6, linewidth=0.8, color=colors[cond])
    ax.set_xlabel("Time (s, offset)")
    ax.set_ylabel("RTT (ms)")
    ax.set_title("Phase 6 — RTT time series, load=15 Mbps, trial 1")
    ax.legend()
    fig.savefig(out / "timeseries-load15-trial1.png")
    plt.close(fig)

    print(f"  Phase 6: 6 figures")


# ==================================================
# Phase 7 — Multi-UPF edge
# ==================================================
def phase7_figures():
    out = FIG / "phase7"

    sh_c = load_ping_avg("results/phase7/ping-central-trial*.txt")
    sh_e = load_ping_avg("results/phase7/ping-edge-trial*.txt")
    dd_c = load_ping_avg("results/phase7/ping-central-distance-trial*.txt")
    dd_e = load_ping_avg("results/phase7/ping-edge-distance-trial*.txt")

    # 7. Bar chart of the four conditions
    fig, ax = plt.subplots(figsize=(8, 5))
    x = np.arange(2); w = 0.35
    vals_c = [np.mean(sh_c), np.mean(dd_c)] if sh_c and dd_c else [0, 0]
    vals_e = [np.mean(sh_e), np.mean(dd_e)] if sh_e and dd_e else [0, 0]
    bars1 = ax.bar(x - w/2, vals_c, w, label="Central (UPF-A)", color="steelblue")
    bars2 = ax.bar(x + w/2, vals_e, w, label="Edge (UPF-B)", color="seagreen")
    for b in list(bars1) + list(bars2):
        ax.text(b.get_x() + b.get_width()/2, b.get_height() + 1,
                f"{b.get_height():.1f}", ha="center", fontsize=9)
    ax.set_xticks(x)
    ax.set_xticklabels(["Same host", "+30 ms netem on central"])
    ax.set_ylabel("Ping average RTT (ms)")
    ax.set_title("Phase 7 — Central vs edge UPF latency")
    ax.legend()
    fig.savefig(out / "central-vs-edge-bars.png")
    plt.close(fig)

    # 8. Per-trial paired comparison
    fig, ax = plt.subplots(figsize=(9, 5))
    trials = [1, 2, 3]
    sh_diff = []
    dd_diff = []
    for t in trials:
        c = load_ping_avg(f"results/phase7/ping-central-trial{t}.txt")
        e = load_ping_avg(f"results/phase7/ping-edge-trial{t}.txt")
        sh_diff.append(np.mean(e) - np.mean(c) if c and e else 0)
        c = load_ping_avg(f"results/phase7/ping-central-distance-trial{t}.txt")
        e = load_ping_avg(f"results/phase7/ping-edge-distance-trial{t}.txt")
        dd_diff.append(np.mean(e) - np.mean(c) if c and e else 0)
    x = np.arange(3); w = 0.35
    ax.bar(x - w/2, sh_diff, w, label="Same host", color="steelblue")
    ax.bar(x + w/2, dd_diff, w, label="+30 ms netem", color="orange")
    ax.axhline(0, color="black", linewidth=0.6)
    ax.set_xticks(x)
    ax.set_xticklabels([f"Trial {t}" for t in trials])
    ax.set_ylabel("Edge RTT − Central RTT (ms)")
    ax.set_title("Phase 7 — Per-trial edge advantage (negative = edge faster)")
    ax.legend()
    fig.savefig(out / "per-trial-deltas.png")
    plt.close(fig)

    # 9. CDF overlay — same-host vs netem for central and edge
    fig, ax = plt.subplots(figsize=(8, 5))
    sh_c_all = load_ping("results/phase7/ping-central-trial*.txt")
    sh_e_all = load_ping("results/phase7/ping-edge-trial*.txt")
    dd_c_all = load_ping("results/phase7/ping-central-distance-trial*.txt")
    dd_e_all = load_ping("results/phase7/ping-edge-distance-trial*.txt")
    for label, data, color in [
        ("central same-host", sh_c_all, "steelblue"),
        ("edge same-host", sh_e_all, "seagreen"),
        ("central +30 ms", dd_c_all, "indianred"),
        ("edge +30 ms", dd_e_all, "orange"),
    ]:
        if len(data) == 0: continue
        x = np.sort(data); y = np.arange(1, len(x)+1) / len(x)
        ax.plot(x, y, label=label, color=color)
    ax.set_xlabel("Ping RTT (ms)")
    ax.set_ylabel("Empirical CDF")
    ax.set_title("Phase 7 — RTT distributions, same-host vs simulated distance")
    ax.legend()
    fig.savefig(out / "cdf-all-conditions.png")
    plt.close(fig)

    print(f"  Phase 7: 3 figures")


# ==================================================
# Phase 8 — Traffic engineering
# ==================================================
def phase8_figures():
    out = FIG / "phase8"
    if not (FIG / "phase8").exists():
        pass

    # 10-11. Load sweep (offered vs delivered, offered vs loss)
    offered, delivered, loss = [], [], []
    for p in sorted(glob.glob(str(REPO / "results/phase8/udp-load-central-*.json"))):
        m = re.search(r"udp-load-central-(\d+)m\.json", p)
        if not m: continue
        try:
            d = json.load(open(p))
            s = d["end"]["sum"]
            offered.append(int(m.group(1)))
            delivered.append(s["bits_per_second"]/1e6)
            loss.append(s.get("lost_percent", 0))
        except Exception:
            pass

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(offered, delivered, "o-", color="steelblue", markersize=8)
    ax.plot([0, max(offered)+2], [0, max(offered)+2], "--", color="gray", label="1:1")
    ax.axhline(8.6, color="red", linestyle=":", label="Ceiling ~8.6 Mbps")
    ax.set_xlabel("Offered UDP rate (Mbps)")
    ax.set_ylabel("Delivered receiver rate (Mbps)")
    ax.set_title("Phase 8 — Offered vs delivered UDP throughput")
    ax.legend()
    fig.savefig(out / "offered-vs-delivered.png")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(offered, loss, color="firebrick")
    ax.set_xlabel("Offered UDP rate (Mbps)")
    ax.set_ylabel("Packet loss (%)")
    ax.set_title("Phase 8 — Packet loss vs offered rate")
    fig.savefig(out / "offered-vs-loss.png")
    plt.close(fig)

    # 12. Four-condition bar chart
    conditions = [
        ("Control (idle)",        "ping-control-60s.txt", "steelblue"),
        ("Same-UPF under load",   "ping-under-load-same-dest.txt", "indianred"),
        ("Cross-UPF (edge)",      "ping-under-load-cross-upf.txt", "seagreen"),
        ("Cross-UPF (central)",   "ping-under-load-cross-upf-reverse.txt", "orange"),
    ]
    labels, medians, p95s = [], [], []
    for label, fname, _ in conditions:
        p = REPO / "results/phase8" / fname
        if not p.exists(): continue
        data = load_ping(f"results/phase8/{fname}")
        if len(data) == 0: continue
        labels.append(label); medians.append(np.median(data)); p95s.append(np.percentile(data, 95))

    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(labels)); w = 0.35
    b1 = ax.bar(x - w/2, medians, w, label="median", color="steelblue")
    b2 = ax.bar(x + w/2, p95s, w, label="p95", color="orange")
    for b in list(b1) + list(b2):
        ax.text(b.get_x() + b.get_width()/2, b.get_height() + 1,
                f"{b.get_height():.1f}", ha="center", fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=15, ha="right")
    ax.set_ylabel("RTT (ms)")
    ax.set_title("Phase 8 — Latency by load placement (four conditions)")
    ax.legend()
    fig.savefig(out / "load-placement-bars.png")
    plt.close(fig)

    # 13. CDF of four conditions
    fig, ax = plt.subplots(figsize=(9, 5))
    for label, fname, color in conditions:
        p = REPO / "results/phase8" / fname
        if not p.exists(): continue
        data = load_ping(f"results/phase8/{fname}")
        if len(data) == 0: continue
        x = np.sort(data); y = np.arange(1, len(x)+1) / len(x)
        ax.plot(x, y, label=label, color=color)
    ax.set_xlabel("Ping RTT (ms)")
    ax.set_ylabel("Empirical CDF")
    ax.set_title("Phase 8 — RTT distributions across load placements")
    ax.legend()
    fig.savefig(out / "cdf-four-conditions.png")
    plt.close(fig)

    print(f"  Phase 8: 4 figures")


# ==================================================
# Phase 10 — Fault injection
# ==================================================
def phase10_figures():
    out = FIG / "phase10"

    fault_specs = [
        ("F01", "Application HTTP failure"),
        ("F02", "netem delay 50 ms"),
        ("F03", "netem loss 1%"),
        ("F04", "tbf 2 mbit cap"),
        ("F05", "UE route blackhole"),
        ("F06", "UPF-B stop"),
    ]

    # 14. Detection latency bar
    detections = []
    for fid, name in fault_specs:
        tl = load_timeline(f"results/phase10/{fid}_*_timeline.txt")
        # try edge or generic probe
        for probe_kind in ["edge", "probe"]:
            pattern = f"results/phase10/{fid}_*_{probe_kind}_probe.csv" if probe_kind == "edge" else f"results/phase10/{fid}_*_probe.csv"
            rows = load_probe_csv(pattern)
            if rows and "fault" in tl:
                first_fail = next((r["ts"] for r in rows
                                   if r["ts"] >= tl["fault"] and r["code"] != "200"), None)
                if first_fail:
                    detections.append((fid, first_fail - tl["fault"]))
                break

    fig, ax = plt.subplots(figsize=(9, 5))
    labels = [d[0] for d in detections]
    vals = [d[1] for d in detections]
    colors_ = ["steelblue" if v < 1 else "orange" for v in vals]
    ax.bar(labels, vals, color=colors_)
    for i, v in enumerate(vals):
        ax.text(i, v + 0.05, f"{v:.2f}s", ha="center", fontsize=9)
    ax.set_ylabel("Detection latency (s)")
    ax.set_title("Phase 10 — Fault detection latency per fault")
    fig.savefig(out / "detection-latency.png")
    plt.close(fig)

    # 15. F06 isolation proof — success rate over time
    tl = load_timeline("results/phase10/F06_*_timeline.txt")
    edge = load_probe_csv("results/phase10/F06_*_edge_probe.csv")
    central = load_probe_csv("results/phase10/F06_*_central_probe.csv")

    if tl and edge and central:
        fig, ax = plt.subplots(figsize=(10, 5))
        t0 = tl["fault"]
        for label, rows, color in [("Edge (UPF-B)", edge, "indianred"),
                                    ("Central (UPF-A)", central, "seagreen")]:
            ts = [(r["ts"] - t0) for r in rows if r["ts"] >= t0 - 5 and r["ts"] <= t0 + 60]
            ok = [1 if r["code"] == "200" else 0 for r in rows
                  if r["ts"] >= t0 - 5 and r["ts"] <= t0 + 60]
            ax.scatter(ts, ok, label=label, color=color, s=8, alpha=0.6)
        ax.axvline(0, color="black", linestyle="--", label="Fault injected")
        if "recover" in tl:
            ax.axvline(tl["recover"] - t0, color="green", linestyle="--", label="Recovery started")
        ax.set_yticks([0, 1])
        ax.set_yticklabels(["Fail", "OK"])
        ax.set_xlabel("Time relative to fault (s)")
        ax.set_title("Phase 10 F06 — UPF-B stopped: isolation proof (60 s window)")
        ax.legend(loc="center right", fontsize=8)
        fig.savefig(out / "f06-isolation-proof.png")
        plt.close(fig)

    # 16. F01 application failure — success timeline
    tl = load_timeline("results/phase10/F01_*_timeline.txt")
    rows = load_probe_csv("results/phase10/F01_*_probe.csv")
    if tl and rows:
        fig, ax = plt.subplots(figsize=(10, 5))
        t0 = tl["fault"]
        ts = [(r["ts"] - t0) for r in rows]
        ok = [1 if r["code"] == "200" else 0 for r in rows]
        colors_scatter = ["seagreen" if o else "indianred" for o in ok]
        ax.scatter(ts, ok, c=colors_scatter, s=15)
        ax.axvline(0, color="black", linestyle="--", label="Fault injected")
        if "recover" in tl:
            ax.axvline(tl["recover"] - t0, color="green", linestyle="--", label="Recovery started")
        ax.set_yticks([0, 1])
        ax.set_yticklabels(["Fail", "OK"])
        ax.set_xlabel("Time relative to fault (s)")
        ax.set_title("Phase 10 F01 — Application HTTP failure timeline")
        ax.legend(loc="center right", fontsize=8)
        fig.savefig(out / "f01-application-timeline.png")
        plt.close(fig)

    print(f"  Phase 10: 3 figures")


# ==================================================
# Cross-phase summary figures
# ==================================================
def crossphase_figures():
    out = FIG / "cross-phase"

    # 17. Hypothesis status chart
    fig, ax = plt.subplots(figsize=(10, 5))
    hyps = ["H1\nSlicing", "H2\nEdge UPF", "H3\nAdaptive", "H4\nScalability", "H5\nResilience"]
    status = ["Not\nsupported", "Partial\n(sim. dist.)", "Not\ntested", "Partial", "Partial"]
    colors_ = ["firebrick", "orange", "gray", "orange", "orange"]
    y_pos = np.arange(len(hyps))
    ax.barh(y_pos, [1]*len(hyps), color=colors_, height=0.6)
    for i, s in enumerate(status):
        ax.text(0.5, i, s, ha="center", va="center", color="white", fontweight="bold")
    ax.set_yticks(y_pos)
    ax.set_yticklabels(hyps)
    ax.set_xlim(0, 1)
    ax.set_xticks([])
    ax.set_title("Hypothesis outcome summary")
    fig.savefig(out / "hypothesis-status.png")
    plt.close(fig)

    # 18. Data volume summary
    fig, ax = plt.subplots(figsize=(9, 5))
    phases = ["6\n(slicing)", "7\n(edge)", "8\n(traffic)", "10\n(faults)", "11\n(RIC)", "12\n(xApp)"]
    packets = [95412, 1294, 172000, 3182, 0, 0]
    # Use more realistic: Phase6 = 18 trials * ~1000-7200 = many
    # Let's compute from actual files
    n6 = 0
    for p in glob.glob(str(REPO / "results/phase6/raw/*_urllc.csv")):
        n6 += sum(1 for _ in open(p)) - 1
    n7 = 0
    for p in glob.glob(str(REPO / "results/phase7/ping-*.txt")):
        n7 += sum(1 for line in open(p, errors="replace") if "time=" in line)
    n8 = 0
    for p in glob.glob(str(REPO / "results/phase8/ping-*.txt")):
        n8 += sum(1 for line in open(p, errors="replace") if "time=" in line)
    n10 = 0
    for p in glob.glob(str(REPO / "results/phase10/F0*_*_probe.csv")):
        n10 += sum(1 for _ in open(p)) - 1

    vals = [n6, n7, n8, n10]
    names = ["Phase 6\nslicing", "Phase 7\nedge", "Phase 8\ntraffic", "Phase 10\nfaults"]
    ax.bar(names, vals, color="steelblue")
    for i, v in enumerate(vals):
        ax.text(i, v*1.02, f"{v:,}", ha="center", fontsize=9)
    ax.set_ylabel("Recorded packets / RTT samples")
    ax.set_title("Data volume by experimental phase")
    fig.savefig(out / "data-volume.png")
    plt.close(fig)

    # 19. RQ summary
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.axis("off")
    rows = [
        ["RQ1 — Slicing",         "Not supported",            "Phase 6"],
        ["RQ2 — Edge UPF",        "Supported (sim. distance)", "Phase 7"],
        ["RQ3 — Adaptive O-RAN",  "Not tested (limitations)",  "Phases 11-12"],
        ["RQ4 — Scalability",     "Ceiling ~8.6 Mbps",         "Phase 8"],
        ["RQ5 — Resilience",      "Partial (no auto-recovery)", "Phase 10"],
    ]
    table = ax.table(cellText=rows,
                     colLabels=["Research question", "Result", "Source phase"],
                     loc="center", cellLoc="left", colWidths=[0.32, 0.38, 0.20])
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 2)
    for i in range(len(rows)+1):
        for j in range(3):
            cell = table[(i, j)]
            if i == 0:
                cell.set_facecolor("#3a6ea5")
                cell.set_text_props(color="white", fontweight="bold")
            else:
                cell.set_facecolor("#f0f0f0" if i % 2 else "#ffffff")
    ax.set_title("Research questions — summary of outcomes", pad=20, fontsize=12)
    fig.savefig(out / "rq-summary-table.png")
    plt.close(fig)

    print(f"  Cross-phase: 3 figures")


# ==================================================
def main():
    print("Generating figures...")
    phase6_figures()
    phase7_figures()
    phase8_figures()
    phase10_figures()
    crossphase_figures()
    total = len(list(FIG.rglob("*.png")))
    print(f"\nTotal PNG files under figures/: {total}")


if __name__ == "__main__":
    main()
