#!/usr/bin/env python3
"""
Parse all four ns-3 5G-LENA study outputs into structured CSVs.

S1: NGMN scalability          — stdout of cttc-nr-traffic-ngmn-mixed
S2: Multi-flow QoS scheduler  — stdout of cttc-nr-multi-flow-qos-sched
S3: Realistic beamforming     — SQLite DB from cttc-realistic-beamforming
S4: Fronthaul XR              — stdout of cttc-nr-fh-xr
"""

import csv
import re
import sqlite3
from pathlib import Path

WORK = Path("/home/mohammad/projects/ns3-lena-sweep")
RESULTS = WORK / "results"
RESULTS.mkdir(parents=True, exist_ok=True)


def parse_stdout_summary(log_path, metrics):
    """Extract the final summary lines from a stdout log."""
    try:
        text = log_path.read_text(errors="replace")
    except Exception:
        return None
    out = {}
    for name, pattern in metrics.items():
        matches = re.findall(pattern, text)
        if matches:
            try:
                out[name] = float(matches[-1])
            except ValueError:
                out[name] = None
        else:
            out[name] = None
    return out


# ---------- S1 ----------
def parse_s1():
    dir_root = WORK / "s1_ngmn"
    rows = []
    for run in sorted(dir_root.iterdir()):
        if not run.is_dir(): continue
        m = re.match(r"s1_(\d+)ue_seed(\d+)", run.name)
        if not m: continue
        d = parse_stdout_summary(run / "stdout.log", {
            "mean_delay_ms":  r"Mean delay:\s*([\d.]+)",
            "median_delay_ms": r"Median delay:\s*([\d.]+)",
            "mean_throughput_mbps": r"Mean flow throughput:\s*([\d.]+)",
        })
        if d is None: continue
        d.update({"ue_count": int(m.group(1)), "seed": int(m.group(2))})
        rows.append(d)

    out = RESULTS / "s1_ngmn.csv"
    if rows:
        with open(out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=[
                "ue_count", "seed", "mean_delay_ms", "median_delay_ms",
                "mean_throughput_mbps"])
            w.writeheader(); w.writerows(rows)
    print(f"  S1: {len(rows)} runs → {out}")


# ---------- S2 ----------
def parse_s2_per_flow():
    """Extract per-flow summary from S2 Throughputs*.txt files."""
    dir_root = WORK / "s2_qos"
    rows = []
    for run in sorted(dir_root.iterdir()):
        if not run.is_dir(): continue
        m = re.match(r"s2_(\w+)_sc(\d+)_seed(\d+)", run.name)
        if not m: continue
        for tp_file in run.glob("Throughput*.txt"):
            try:
                with open(tp_file) as f:
                    reader = csv.DictReader(f, delimiter="\t")
                    for i, r in enumerate(reader):
                        try:
                            rows.append({
                                "scheduler": m.group(1),
                                "scenario": int(m.group(2)),
                                "seed": int(m.group(3)),
                                "flow_idx": i,
                                "source_port": int(r["source_port"]),
                                "dest_port": int(r["dest_port"]),
                                "throughput_mbps": float(r["Throughput"]),
                                "delay_ms": float(r["Delay"]),
                            })
                        except Exception:
                            continue
            except Exception as e:
                print(f"    [warn] {tp_file}: {e}")
    out = RESULTS / "s2_flows.csv"
    if rows:
        with open(out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)
    print(f"  S2 flows: {len(rows)} flow rows -> {out}")


def parse_s2_packets():
    """Extract per-packet delay samples from S2 Delays*.txt files.
    Use for distributions, not means."""
    dir_root = WORK / "s2_qos"
    rows = []
    for run in sorted(dir_root.iterdir()):
        if not run.is_dir(): continue
        m = re.match(r"s2_(\w+)_sc(\d+)_seed(\d+)", run.name)
        if not m: continue
        for delay_file in run.glob("Delay*.txt"):
            try:
                with open(delay_file) as f:
                    reader = csv.DictReader(f, delimiter="\t")
                    for r in reader:
                        try:
                            rows.append({
                                "scheduler": m.group(1),
                                "scenario": int(m.group(2)),
                                "seed": int(m.group(3)),
                                "source_address": r["source_address"],
                                "source_port": int(r["source_port"]),
                                "dest_address": r["dest_address"],
                                "dest_port": int(r["dest_port"]),
                                "delay_ms": float(r["delay"]) * 1000,
                            })
                        except Exception:
                            continue
            except Exception as e:
                print(f"    [warn] {delay_file}: {e}")
    # This file can be large (~68k rows). Only write if < 200k rows.
    out = RESULTS / "s2_packets.csv"
    if rows and len(rows) < 200000:
        with open(out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)
        print(f"  S2 packets: {len(rows)} packet rows -> {out}")
    else:
        print(f"  S2 packets: skipped ({len(rows)} rows, too large or empty)")


def parse_s2():
    dir_root = WORK / "s2_qos"
    rows = []
    for run in sorted(dir_root.iterdir()):
        if not run.is_dir(): continue
        m = re.match(r"s2_(\w+)_sc(\d+)_seed(\d+)", run.name)
        if not m: continue
        d = parse_stdout_summary(run / "stdout.log", {
            "mean_flow_delay_ms": r"Mean flow delay:\s*([\d.]+)",
            "mean_flow_throughput_mbps": r"Mean flow throughput:\s*([\d.]+)",
        })
        if d is None: continue
        d.update({
            "scheduler": m.group(1),
            "scenario": int(m.group(2)),
            "seed": int(m.group(3)),
        })
        rows.append(d)

    out = RESULTS / "s2_qos.csv"
    if rows:
        with open(out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=[
                "scheduler", "scenario", "seed",
                "mean_flow_delay_ms", "mean_flow_throughput_mbps"])
            w.writeheader(); w.writerows(rows)
    print(f"  S2: {len(rows)} runs → {out}")


# ---------- S3 ----------
def parse_s3():
    dir_root = WORK / "s3_beamforming"
    rows = []
    for run in sorted(dir_root.iterdir()):
        if not run.is_dir(): continue
        m = re.match(r"s3_(\w+)_(UMa|UMi|InH-OfficeOpen)_seed(\d+)", run.name)
        if not m: continue
        db = run / "realistic_beamforming.db"
        if not db.exists(): continue
        try:
            conn = sqlite3.connect(str(db))
            cur = conn.execute(
                "SELECT SINR, SINR_DB, Distance, BeamformingType, "
                "RngRun, Numerology, Scenario FROM results LIMIT 1")
            r = cur.fetchone()
            conn.close()
        except Exception as e:
            print(f"    [warn] DB error in {run.name}: {e}")
            continue
        if not r: continue
        rows.append({
            "algorithm":     m.group(1),
            "scenario":      m.group(2),
            "seed":          int(m.group(3)),
            "SINR":          r[0],
            "SINR_dB":       r[1],
            "distance_m":    r[2],
            "db_beamforming": r[3],
            "db_rng_run":    r[4],
            "db_numerology": r[5],
            "db_scenario":   r[6],
        })

    out = RESULTS / "s3_beamforming.csv"
    if rows:
        with open(out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)
    print(f"  S3: {len(rows)} runs → {out}")


# ---------- S4 ----------
def parse_s4():
    dir_root = WORK / "s4_fronthaul"
    rows = []
    for run in sorted(dir_root.iterdir()):
        if not run.is_dir(): continue
        m = re.match(r"s4_(light|medium|heavy)_seed(\d+)", run.name)
        if not m: continue
        d = parse_stdout_summary(run / "stdout.log", {
            "mean_flow_delay_ms": r"Mean flow delay:\s*([\d.]+)",
            "mean_flow_throughput_mbps": r"Mean flow throughput:\s*([\d.]+)",
            "elapsed_wall_s": r"Elapsed wall clock:\s*(\d+)s",
        })
        if d is None: continue
        d.update({"mix": m.group(1), "seed": int(m.group(2))})
        rows.append(d)

    out = RESULTS / "s4_fronthaul.csv"
    if rows:
        with open(out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=[
                "mix", "seed", "mean_flow_delay_ms",
                "mean_flow_throughput_mbps", "elapsed_wall_s"])
            w.writeheader(); w.writerows(rows)
    print(f"  S4: {len(rows)} runs → {out}")


# ---------- Summary ----------
def write_summary():
    summary = RESULTS / "summary.txt"
    lines = []
    for name in ["s1_ngmn", "s2_qos", "s3_beamforming", "s4_fronthaul"]:
        csv_path = RESULTS / f"{name}.csv"
        if not csv_path.exists():
            lines.append(f"\n=== {name.upper()} — MISSING ===\n")
            continue
        with open(csv_path) as f:
            rows = list(csv.DictReader(f))
        lines.append(f"\n=== {name.upper()} — {len(rows)} runs ===\n")
        if not rows: continue
        header = list(rows[0].keys())
        lines.append("  " + "  ".join(f"{h:<22}" for h in header))
        for r in rows:
            lines.append("  " + "  ".join(f"{str(r[h])[:20]:<22}" for h in header))

    summary.write_text("\n".join(lines))
    print(f"  Summary → {summary}")


# ---------- Main ----------
print("=== Parsing all studies ===")
parse_s1()
parse_s2()
parse_s2_per_flow()
parse_s2_packets()
parse_s3()
parse_s4()
write_summary()
print()
print("All CSV files written to:", RESULTS)


# ============================================================
# WAVE 2 PARSERS (S5-S12)
# ============================================================
def parse_simple_dir(study_dir_name, csv_name, patterns):
    """Parse stdout.log from a study dir. patterns = {name: regex}."""
    dir_root = WORK / study_dir_name
    if not dir_root.exists():
        return
    rows = []
    for run in sorted(dir_root.iterdir()):
        if not run.is_dir(): continue
        m = re.match(r"(s\d+_\w+(?:_\w+)*_seed\d+)", run.name)
        log = run / "stdout.log"
        if not log.exists(): continue
        text = log.read_text(errors="replace")
        row = {"run": run.name}
        for key, pat in patterns.items():
            matches = re.findall(pat, text)
            if matches:
                try:
                    row[key] = float(matches[-1])
                except ValueError:
                    row[key] = matches[-1]
            else:
                row[key] = None
        rows.append(row)
    if rows:
        out = RESULTS / csv_name
        with open(out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)
        print(f"  {study_dir_name}: {len(rows)} runs -> {out}")


parse_simple_dir("s5_simple_qos", "s5_simple_qos.csv", {
    "mean_flow_delay_ms": r"Mean flow delay:\s*([\d.]+)",
    "mean_flow_throughput_mbps": r"Mean flow throughput:\s*([\d.]+)",
})
parse_simple_dir("s6_ca", "s6_ca.csv", {
    "mean_flow_delay_ms": r"Mean flow delay:\s*([\d.]+)",
    "mean_flow_throughput_mbps": r"Mean flow throughput:\s*([\d.]+)",
})
parse_simple_dir("s7_mimo", "s7_mimo.csv", {
    "mean_flow_delay_ms": r"Mean flow delay:\s*([\d.]+)",
    "mean_flow_throughput_mbps": r"Mean flow throughput:\s*([\d.]+)",
})
parse_simple_dir("s8_notching", "s8_notching.csv", {
    "mean_flow_delay_ms": r"Mean flow delay:\s*([\d.]+)",
    "mean_flow_throughput_mbps": r"Mean flow throughput:\s*([\d.]+)",
})
parse_simple_dir("s9_xr", "s9_xr.csv", {
    "mean_flow_delay_ms": r"Mean flow delay:\s*([\d.]+)",
    "mean_flow_throughput_mbps": r"Mean flow throughput:\s*([\d.]+)",
})
parse_simple_dir("s10_numerology", "s10_numerology.csv", {
    "mean_flow_delay_ms": r"Mean flow delay:\s*([\d.]+)",
    "mean_flow_throughput_mbps": r"Mean flow throughput:\s*([\d.]+)",
})
parse_simple_dir("s11_bandwidth", "s11_bandwidth.csv", {
    "mean_flow_delay_ms": r"Mean flow delay:\s*([\d.]+)",
    "mean_flow_throughput_mbps": r"Mean flow throughput:\s*([\d.]+)",
})
parse_simple_dir("s12_frequency", "s12_frequency.csv", {
    "mean_flow_delay_ms": r"Mean flow delay:\s*([\d.]+)",
    "mean_flow_throughput_mbps": r"Mean flow throughput:\s*([\d.]+)",
})


# ============================================================
# S13 — TDD pattern sweep
# ============================================================
def parse_s13():
    dir_root = WORK / "s13_tdd"
    if not dir_root.exists():
        return
    rows = []
    for run in sorted(dir_root.iterdir()):
        if not run.is_dir(): continue
        m = re.match(r"s13_(\w+)_seed(\d+)", run.name)
        if not m: continue
        log = run / "stdout.log"
        if not log.exists(): continue
        text = log.read_text(errors="replace")
        delay = re.findall(r"Mean delay:\s*([\d.]+)", text)
        thp = re.findall(r"Mean flow throughput:\s*([\d.]+)", text)
        rows.append({
            "pattern": m.group(1),
            "seed": int(m.group(2)),
            "mean_delay_ms": float(delay[-1]) if delay else None,
            "mean_flow_throughput_mbps": float(thp[-1]) if thp else None,
        })
    if rows:
        out = RESULTS / "s13_tdd.csv"
        with open(out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)
        print(f"  s13_tdd: {len(rows)} runs -> {out}")


parse_s13()


# ============================================================
# S13 — TDD pattern sweep
# ============================================================
def parse_s13():
    dir_root = WORK / "s13_tdd"
    if not dir_root.exists():
        return
    rows = []
    for run in sorted(dir_root.iterdir()):
        if not run.is_dir(): continue
        m = re.match(r"s13_(\w+)_seed(\d+)", run.name)
        if not m: continue
        log = run / "stdout.log"
        if not log.exists(): continue
        text = log.read_text(errors="replace")
        delay = re.findall(r"Mean delay:\s*([\d.]+)", text)
        thp = re.findall(r"Mean flow throughput:\s*([\d.]+)", text)
        rows.append({
            "pattern": m.group(1),
            "seed": int(m.group(2)),
            "mean_delay_ms": float(delay[-1]) if delay else None,
            "mean_flow_throughput_mbps": float(thp[-1]) if thp else None,
        })
    if rows:
        out = RESULTS / "s13_tdd.csv"
        with open(out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)
        print(f"  s13_tdd: {len(rows)} runs -> {out}")


parse_s13()
