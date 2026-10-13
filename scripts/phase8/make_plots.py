#!/usr/bin/env python3
"""
Phase 8 — Generate plots from the measured data.

Reads:
  results/phase8/rtt-percentiles-all.txt   (from analyze_ping.py)
  results/phase8/experiment-register.csv   (load sweep + latencies)

Writes PNGs to:
  figures/phase8/
"""

import csv
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = Path("/home/mohammad/projects/private-5g")
RESULTS = REPO / "results" / "phase8"
FIGURES = REPO / "figures" / "phase8"
FIGURES.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------
# 1. Parse ping percentiles from the analyzer output
# ---------------------------------------------------------------------
def parse_percentiles(path):
    text = path.read_text()
    blocks = re.split(r"=+\nFILE: (.+?)\.txt\n=+\n", text)
    # blocks = ['', 'name1', 'body1', 'name2', 'body2', ...]
    data = {}
    for i in range(1, len(blocks), 2):
        name = blocks[i].strip()
        body = blocks[i + 1]
        row = {}
        for key in ("Min", "Median", "Mean", "P95", "P99", "Max"):
            m = re.search(rf"{key}:\s+([0-9.]+)\s+ms", body)
            if m:
                row[key] = float(m.group(1))
        data[name] = row
    return data


ping = parse_percentiles(RESULTS / "rtt-percentiles-all.txt")
print("Loaded ping files:", list(ping.keys()))


# ---------------------------------------------------------------------
# 2. Parse the load sweep from the CSV register
# ---------------------------------------------------------------------
def load_sweep():
    offered, delivered, loss = [], [], []
    with open(RESULTS / "experiment-register.csv") as f:
        for row in csv.DictReader(f):
            if row["condition"] != "load":
                continue
            try:
                o = float(row["offered_mbps"])
            except ValueError:
                continue
            if row["receiver_mbps"].strip() == "":
                # control channel failed — skip
                continue
            offered.append(o)
            delivered.append(float(row["receiver_mbps"]))
            loss.append(float(row["packet_loss_pct"]) if row["packet_loss_pct"] else 0.0)
    return offered, delivered, loss


offered, delivered, loss = load_sweep()
print("Load sweep points:", list(zip(offered, delivered, loss)))


# ---------------------------------------------------------------------
# 3. Plot: offered vs delivered UDP (load sweep)
# ---------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(8, 5))
ax.plot(offered, delivered, "o-", color="steelblue", markersize=8)
ax.plot([0, max(offered) + 1], [0, max(offered) + 1],
        "--", color="gray", linewidth=1, label="1:1 (delivered = offered)")
ax.axvline(10, color="orange", linestyle=":", linewidth=1)
ax.text(10.2, 2, "10 Mbps offered", color="orange", fontsize=9)
ax.set_xlabel("Offered UDP rate (Mbps)")
ax.set_ylabel("Delivered receiver rate (Mbps)")
ax.set_title("Phase 8 — Offered vs delivered UDP throughput")
ax.set_xlim(0, max(offered) + 2)
ax.set_ylim(0, max(delivered) + 2)
ax.grid(True, alpha=0.3)
ax.legend()
fig.tight_layout()
out = FIGURES / "load-sweep-throughput.png"
fig.savefig(out, dpi=120)
plt.close(fig)
print("Wrote", out)


# ---------------------------------------------------------------------
# 4. Plot: offered vs packet loss
# ---------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(8, 5))
ax.plot(offered, loss, "s-", color="firebrick", markersize=8)
ax.set_xlabel("Offered UDP rate (Mbps)")
ax.set_ylabel("Packet loss (%)")
ax.set_title("Phase 8 — Offered UDP rate vs packet loss")
ax.set_xlim(0, max(offered) + 2)
ax.set_ylim(-0.5, max(loss) + 1 if max(loss) > 0 else 1)
ax.grid(True, alpha=0.3)
fig.tight_layout()
out = FIGURES / "load-sweep-loss.png"
fig.savefig(out, dpi=120)
plt.close(fig)
print("Wrote", out)


# ---------------------------------------------------------------------
# 5. Plot: latency under load — 4 conditions (median RTT)
# ---------------------------------------------------------------------
labels = [
    "Control\n(idle)",
    "Same-UPF\nunder load",
    "Cross-UPF\n(edge probe)",
    "Cross-UPF\n(central probe)",
]
keys = [
    "ping-control-60s",
    "ping-under-load-same-dest",
    "ping-under-load-cross-upf",
    "ping-under-load-cross-upf-reverse",
]
medians = [ping[k]["Median"] for k in keys]
p95s = [ping[k]["P95"] for k in keys]
p99s = [ping[k]["P99"] for k in keys]

x = range(len(labels))
width = 0.27

fig, ax = plt.subplots(figsize=(10, 5))
ax.bar([i - width for i in x], medians, width, label="Median", color="steelblue")
ax.bar(list(x), p95s, width, label="P95", color="orange")
ax.bar([i + width for i in x], p99s, width, label="P99", color="firebrick")
ax.set_xticks(list(x))
ax.set_xticklabels(labels)
ax.set_ylabel("RTT (ms)")
ax.set_title("Phase 8 — Latency under competing load (8 Mbps UDP)")
ax.legend()
ax.grid(True, axis="y", alpha=0.3)
fig.tight_layout()
out = FIGURES / "latency-under-load.png"
fig.savefig(out, dpi=120)
plt.close(fig)
print("Wrote", out)


# ---------------------------------------------------------------------
# 6. Plot: idle vs loaded RTT (control vs cross-UPF)
# ---------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(9, 5))
ax.plot([ping["ping-control-60s"]["Min"], ping["ping-control-60s"]["Median"],
         ping["ping-control-60s"]["P95"], ping["ping-control-60s"]["P99"],
         ping["ping-control-60s"]["Max"]],
        [0, 1, 2, 3, 4], "o-", color="steelblue", label="Control (idle)", markersize=8)
ax.plot([ping["ping-under-load-cross-upf"]["Min"], ping["ping-under-load-cross-upf"]["Median"],
         ping["ping-under-load-cross-upf"]["P95"], ping["ping-under-load-cross-upf"]["P99"],
         ping["ping-under-load-cross-upf"]["Max"]],
        [0, 1, 2, 3, 4], "s-", color="seagreen", label="Cross-UPF under load", markersize=8)
ax.set_yticks([0, 1, 2, 3, 4])
ax.set_yticklabels(["Min", "Median", "P95", "P99", "Max"])
ax.set_xlabel("RTT (ms)")
ax.set_title("Phase 8 — RTT percentiles: idle vs cross-UPF under load")
ax.grid(True, axis="x", alpha=0.3)
ax.legend()
fig.tight_layout()
out = FIGURES / "rtt-percentiles-idle-vs-crossupf.png"
fig.savefig(out, dpi=120)
plt.close(fig)
print("Wrote", out)

print()
print("All plots written to", FIGURES)
