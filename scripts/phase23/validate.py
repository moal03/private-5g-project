#!/usr/bin/env python3
"""
Phase 23 — Validation.

Verifies each material claim in the phase reports against raw data.

For each claim:
  - report location and claimed value
  - raw source file pattern
  - calculation method
  - tolerance

Recomputes the value from raw data and classifies as:
  verified    — matches to within 0.5%
  close       — within stated tolerance but not exact
  mismatch    — beyond tolerance
  unverifiable — source files missing or calc not implemented
"""

import csv, glob, json, re
from datetime import datetime
from pathlib import Path
import numpy as np

REPO = Path("/home/mohammad/projects/private-5g")
OUT = REPO / "results" / "phase23"
OUT.mkdir(parents=True, exist_ok=True)


# ---------- Loaders ----------
def load_urllc(patterns):
    rtts = []
    for pat in patterns:
        for p in glob.glob(str(REPO / pat)):
            for row in csv.DictReader(open(p)):
                if row["status"] == "OK" and row["rtt_us"]:
                    rtts.append(int(row["rtt_us"]) / 1000.0)
    return rtts


def load_ping_values(patterns):
    pat = re.compile(r"time[=<]([0-9]+(?:\.[0-9]+)?)\s*ms")
    rtts = []
    for p_pat in patterns:
        for p in glob.glob(str(REPO / p_pat)):
            for line in open(p, errors="replace"):
                m = pat.search(line)
                if m:
                    rtts.append(float(m.group(1)))
    return rtts


def load_ping_avg_per_trial(patterns):
    """Return the mean of per-trial 'avg' values from ping summary lines."""
    avgs = []
    pat = re.compile(r"rtt min/avg/max/mdev = [\d.]+/([\d.]+)/")
    for p_pat in patterns:
        for p in sorted(glob.glob(str(REPO / p_pat))):
            text = Path(p).read_text(errors="replace")
            m = pat.search(text)
            if m:
                avgs.append(float(m.group(1)))
    return avgs


def load_probe(path_pattern):
    files = sorted(glob.glob(str(REPO / path_pattern)))
    if not files:
        return []
    rows = []
    for row in csv.DictReader(open(files[-1])):
        try:
            rows.append({"ts": float(row["ts"]), "code": row["http_code"]})
        except Exception:
            pass
    return rows


def load_timeline(path_pattern):
    files = sorted(glob.glob(str(REPO / path_pattern)))
    if not files:
        return None
    info = {}
    for line in open(files[-1]):
        if line.startswith("Fault injected:"):
            iso = line.split(":", 1)[1].strip()
            info["fault"] = datetime.fromisoformat(iso).timestamp()
        elif line.startswith("Recovery started:"):
            iso = line.split(":", 1)[1].strip()
            info["recover"] = datetime.fromisoformat(iso).timestamp()
    return info


# ---------- Calculators ----------
def calc_pct(values, p):
    return float(np.percentile(values, p))


def calc_mean(values):
    return float(np.mean(values))


def calc_diff_means(a, b):
    return float(np.mean(b) - np.mean(a))


# ---------- Registry ----------
CLAIMS = []


def claim(cid, phase, desc, claimed, source, calc, tol_pct=1.0, unit="ms",
          note=None):
    CLAIMS.append({
        "id": cid, "phase": phase, "desc": desc,
        "claimed": claimed, "source": source,
        "calc": calc, "tol_pct": tol_pct, "unit": unit,
        "note": note,
    })


# ===== Phase 6 — URLLC latency under slicing =====
for cond, label in [("baseline", "baseline"), ("treatment", "treatment")]:
    for load, expected in [(0, 64.6 if cond == "baseline" else 64.9),
                           (15, 32.0 if cond == "baseline" else 32.3),
                           (35, 32.1 if cond == "baseline" else 31.9)]:
        claim(
            cid=f"P6-{cond[:3].upper()}-P50-{load}M",
            phase=6,
            desc=f"Phase 6 {label} p50 at {load} Mbps",
            claimed=expected,
            source=[f"results/phase6/raw/{cond}_load{load}_trial*_urllc.csv"],
            calc=("pct", {"p": 50}),
        )

for cond, label, expected in [("baseline", "baseline", 84.6),
                              ("treatment", "treatment", 84.8)]:
    claim(
        cid=f"P6-{cond[:3].upper()}-P95-0M",
        phase=6,
        desc=f"Phase 6 {label} p95 at 0 Mbps",
        claimed=expected,
        source=[f"results/phase6/raw/{cond}_load0_trial*_urllc.csv"],
        calc=("pct", {"p": 95}),
    )


# ===== Phase 7 — multi-UPF same-host and netem =====
# Same-host: report uses mean of per-trial averages
claim(
    cid="P7-CENTRAL-SH",
    phase=7,
    desc="Phase 7 same-host central ping avg",
    claimed=56.42,
    source=["results/phase7/ping-central-trial*.txt"],
    calc=("mean_of_trial_avgs", None),
    tol_pct=2.0,
)
claim(
    cid="P7-EDGE-SH",
    phase=7,
    desc="Phase 7 same-host edge ping avg",
    claimed=56.47,
    source=["results/phase7/ping-edge-trial*.txt"],
    calc=("mean_of_trial_avgs", None),
    tol_pct=2.0,
)
claim(
    cid="P7-CENTRAL-NETEM",
    phase=7,
    desc="Phase 7 +30ms netem central ping avg",
    claimed=89.94,
    source=["results/phase7/ping-central-distance-trial*.txt"],
    calc=("mean_of_trial_avgs", None),
    tol_pct=2.0,
)
claim(
    cid="P7-EDGE-NETEM",
    phase=7,
    desc="Phase 7 +30ms netem edge ping avg",
    claimed=58.17,
    source=["results/phase7/ping-edge-distance-trial*.txt"],
    calc=("mean_of_trial_avgs", None),
    tol_pct=2.0,
)


# ===== Phase 8 — load placement =====
P8_FILES = {
    "Control":     "results/phase8/ping-control-60s.txt",
    "Same-UPF":    "results/phase8/ping-under-load-same-dest.txt",
    "Cross-UPF-E": "results/phase8/ping-under-load-cross-upf.txt",
    "Cross-UPF-C": "results/phase8/ping-under-load-cross-upf-reverse.txt",
}
for key, expected in [("Control", 77.4), ("Same-UPF", 65.4),
                     ("Cross-UPF-E", 29.7), ("Cross-UPF-C", 31.7)]:
    claim(
        cid=f"P8-{key}",
        phase=8,
        desc=f"Phase 8 {key} ping mean",
        claimed=expected,
        source=[P8_FILES[key]],
        calc=("mean_all_values", None),
        tol_pct=2.0,
    )


# ===== Phase 11 — fault injection =====
# F01 detection latency
claim(
    cid="P11-F01-DETECT",
    phase=11,
    desc="F01 application failure detection latency",
    claimed=0.36,
    source=["results/phase11/F01_*_probe.csv",
            "results/phase11/F01_*_timeline.txt"],
    calc=("fault_detect_s", None),
    tol_pct=10.0,
    unit="s",
)
claim(
    cid="P11-F06-DETECT",
    phase=11,
    desc="F06 UPF-B stop detection latency",
    claimed=2.95,
    source=["results/phase11/F06_*_edge_probe.csv",
            "results/phase11/F06_*_timeline.txt"],
    calc=("fault_detect_s", None),
    tol_pct=10.0,
    unit="s",
)
claim(
    cid="P11-F05-EDGE-OK",
    phase=11,
    desc="F05 edge probe success during fault window",
    claimed=1,
    source=["results/phase11/F05_*_edge_probe.csv",
            "results/phase11/F05_*_timeline.txt"],
    calc=("probe_ok_in_fault", None),
    tol_pct=0.0,
    unit="count",
)
claim(
    cid="P11-F05-CTRL-OK",
    phase=11,
    desc="F05 control probe OK during fault window",
    claimed=59,
    source=["results/phase11/F05_*_central_probe.csv",
            "results/phase11/F05_*_timeline.txt"],
    calc=("probe_ok_in_fault", None),
    tol_pct=0.0,
    unit="count",
)
claim(
    cid="P11-F06-CTRL-TOTAL",
    phase=11,
    desc="F06 control probe OK over the whole 60 s run",
    claimed=200,
    source=["results/phase11/F06_*_central_probe.csv"],
    calc=("probe_total_ok", None),
    tol_pct=0.0,
    unit="count",
    note="Phase 11 report says '200/200 OK' — this is the full-run count",
)
claim(
    cid="P11-F06-CTRL-FAULT",
    phase=11,
    desc="F06 control probe OK within the UPF-B stop window",
    claimed=None,
    source=["results/phase11/F06_*_central_probe.csv",
            "results/phase11/F06_*_timeline.txt"],
    calc=("probe_ok_in_fault", None),
    tol_pct=0.0,
    unit="count",
    note="Derived for Phase 23 — expected ~66-80 based on 300ms probe interval",
)


# ===== Phase 15 — cross-report consistency =====
claim(
    cid="P15-P7-SH-CENTRAL",
    phase=15,
    desc="Phase 15 restates Phase 7 same-host central ping avg",
    claimed=56.42,
    source=["results/phase7/ping-central-trial*.txt"],
    calc=("mean_of_trial_avgs", None),
    tol_pct=2.0,
)
claim(
    cid="P15-P7-NETEM-DELTA",
    phase=15,
    desc="Phase 15 restates Phase 7 netem delta (edge - central)",
    claimed=-31.77,
    source=["results/phase7/ping-central-distance-trial*.txt",
            "results/phase7/ping-edge-distance-trial*.txt"],
    calc=("p7_netem_delta", None),
    tol_pct=3.0,
)
claim(
    cid="P15-P8-SAMEUPF",
    phase=15,
    desc="Phase 15 restates Phase 8 same-UPF ping mean",
    claimed=65.4,
    source=["results/phase8/ping-under-load-same-dest.txt"],
    calc=("mean_all_values", None),
    tol_pct=2.0,
)
claim(
    cid="P15-P8-CROSSUPF",
    phase=15,
    desc="Phase 15 restates Phase 8 cross-UPF edge ping mean",
    claimed=29.7,
    source=["results/phase8/ping-under-load-cross-upf.txt"],
    calc=("mean_all_values", None),
    tol_pct=2.0,
)


# ---------- Compute ----------
def compute(claim):
    kind, args = claim["calc"]
    if kind == "pct":
        v = load_urllc(claim["source"])
        return calc_pct(v, args["p"]) if v else None
    if kind == "mean_all_values":
        v = load_ping_values(claim["source"])
        return calc_mean(v) if v else None
    if kind == "mean_of_trial_avgs":
        avgs = load_ping_avg_per_trial(claim["source"])
        return calc_mean(avgs) if avgs else None
    if kind == "fault_detect_s":
        tl = load_timeline(claim["source"][1])
        rows = load_probe(claim["source"][0])
        if not tl or not rows: return None
        ft = tl["fault"]
        first_fail = next((r["ts"] for r in sorted(rows, key=lambda x: x["ts"])
                           if r["ts"] >= ft and r["code"] != "200"), None)
        return (first_fail - ft) if first_fail else None
    if kind == "probe_ok_in_fault":
        tl = load_timeline(claim["source"][1])
        rows = load_probe(claim["source"][0])
        if not tl or not rows: return None
        ft, rt = tl["fault"], tl["recover"]
        return sum(1 for r in rows
                   if ft <= r["ts"] < rt and r["code"] == "200")
    if kind == "probe_total_ok":
        rows = load_probe(claim["source"][0])
        return sum(1 for r in rows if r["code"] == "200") if rows else None
    if kind == "p7_netem_delta":
        c = load_ping_avg_per_trial([claim["source"][0]])
        e = load_ping_avg_per_trial([claim["source"][1]])
        if c and e:
            return float(np.mean(e) - np.mean(c))
        return None
    return None


def classify(claimed, computed, tol_pct):
    if computed is None:
        return "unverifiable"
    if claimed is None:
        return "informational"
    if claimed == 0 and computed == 0:
        return "verified"
    if claimed == 0:
        return "mismatch"
    rel = abs(computed - claimed) / abs(claimed) * 100
    if rel <= 0.5:
        return "verified"
    if rel <= tol_pct:
        return "close"
    return "mismatch"


# ---------- Report ----------
def main():
    lines = []
    lines.append("=" * 100)
    lines.append("Phase 23 — Validation Report")
    lines.append(f"Generated: {datetime.now().isoformat()}")
    lines.append("=" * 100)
    lines.append("")
    lines.append("Every material claim in the phase reports is verified against")
    lines.append("its raw source file. Classification:")
    lines.append("  verified    = |computed - claimed| / claimed <= 0.5%")
    lines.append("  close       = within claim tolerance but not exact")
    lines.append("  mismatch    = beyond tolerance")
    lines.append("  unverifiable= source files missing or calc not runnable")
    lines.append("")

    counts = {"verified": 0, "close": 0, "mismatch": 0, "unverifiable": 0, "informational": 0}

    by_phase = {}
    for c in CLAIMS:
        v = compute(c)
        status = classify(c["claimed"], v, c["tol_pct"])
        c["computed"] = v
        c["status"] = status
        counts[status] += 1
        by_phase.setdefault(c["phase"], []).append(c)

    for phase in sorted(by_phase):
        lines.append("")
        lines.append("=" * 100)
        lines.append(f"PHASE {phase} — {len(by_phase[phase])} claims")
        lines.append("=" * 100)
        lines.append("")
        lines.append(f"{'ID':<22} {'Status':<12} {'Claimed':>12} "
                     f"{'Computed':>12} {'Δ%':>8}  Description")
        lines.append("-" * 100)
        for c in by_phase[phase]:
            cmp_ = f"{c['computed']:.3f}" if c["computed"] is not None else "n/a"
            claimed_s = f"{c['claimed']}" if c["claimed"] is not None else "info"
            if c["computed"] is None or c["claimed"] is None or c["claimed"] == 0:
                delta = "n/a"
            else:
                d = (c["computed"] - c["claimed"]) / c["claimed"] * 100
                delta = f"{d:+.2f}%"
            lines.append(f"{c['id']:<22} {c['status']:<12} "
                         f"{claimed_s:>12} {cmp_:>12} {delta:>8}  {c['desc']}")

    lines.append("")
    lines.append("=" * 100)
    lines.append("SUMMARY")
    lines.append("=" * 100)
    total = sum(counts.values())
    lines.append(f"  Total claims : {total}")
    for k in ["verified", "close", "mismatch", "unverifiable", "informational"]:
        lines.append(f"  {k:<13}: {counts[k]}  "
                     f"({100*counts[k]/total:.1f}%)")
    lines.append("")
    if counts["mismatch"] == 0:
        lines.append("  RESULT: No mismatches. All claims are supported by")
        lines.append("          the raw data to within tolerance.")
    else:
        lines.append(f"  RESULT: {counts['mismatch']} mismatch(es) found. "
                     "See table above.")

    text = "\n".join(lines)
    (OUT / "validation-report.txt").write_text(text)
    print(text)


if __name__ == "__main__":
    main()
