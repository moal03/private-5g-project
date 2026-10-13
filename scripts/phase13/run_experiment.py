#!/usr/bin/env python3
"""
Phase 13 — Experiment orchestrator.
"""

import argparse
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml

REPO = Path("/home/mohammad/projects/private-5g")
RESULTS_ROOT = REPO / "experiments" / "results"


def list_experiments(manifest):
    print(f"{'NAME':<28} {'CATEGORY':<12} {'DURATION':>9}  DESCRIPTION")
    print("-" * 100)
    for e in manifest["experiments"]:
        print(f"{e['name']:<28} {e['category']:<12} {e['duration_s']:>7}s  {e['description']}")


def select(manifest, only=None, category=None, tag=None):
    selected = manifest["experiments"]
    if only:
        selected = [e for e in selected if e["name"] == only]
    if category:
        selected = [e for e in selected if e["category"] == category]
    if tag:
        selected = [e for e in selected if tag in e.get("tags", [])]
    return selected


def run_one(exp, dry=False):
    name = exp["name"]
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = RESULTS_ROOT / name / ts
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'=' * 70}")
    print(f"  Experiment:  {name}")
    print(f"  Category:    {exp['category']}")
    print(f"  Description: {exp['description']}")
    print(f"  Output:      {out_dir}")
    print(f"{'=' * 70}")

    meta = {
        "name": name,
        "description": exp["description"],
        "category": exp["category"],
        "tags": exp.get("tags", []),
        "depends_on": exp.get("depends_on", []),
        "expected_duration_s": exp["duration_s"],
        "command": exp["command"],
        "started_at": datetime.now().isoformat(),
    }
    with open(out_dir / "metadata.yaml", "w") as f:
        yaml.safe_dump(meta, f, sort_keys=False)

    if dry:
        print("  [dry-run] command would run here")
        return {"name": name, "status": "dry-run", "output_dir": str(out_dir)}

    t0 = time.monotonic()
    status = "unknown"
    duration = 0.0
    try:
        completed = subprocess.run(
            ["bash", "-lc", exp["command"]],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=exp["duration_s"] + 180,
        )
        duration = time.monotonic() - t0
        with open(out_dir / "stdout.log", "w") as f:
            f.write(completed.stdout or "")
        with open(out_dir / "stderr.log", "w") as f:
            f.write(completed.stderr or "")
        status = "ok" if completed.returncode == 0 else f"exit-{completed.returncode}"
        print(f"  Status: {status}  ({duration:.1f}s)")
    except subprocess.TimeoutExpired:
        duration = time.monotonic() - t0
        status = "timeout"
        print(f"  TIMEOUT after {duration:.1f}s")

    copied = []
    for pattern in exp.get("artifacts", []):
        for p in REPO.glob(pattern):
            if p.is_file():
                dest = out_dir / "artifacts" / p.name
                dest.parent.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.copy2(p, dest)
                    copied.append(str(p.relative_to(REPO)))
                except Exception as ex:
                    print(f"  [warn] could not copy {p}: {ex}")
    if copied:
        print(f"  Artifacts copied: {len(copied)}")
        for c in copied:
            print(f"    {c}")

    meta["finished_at"] = datetime.now().isoformat()
    meta["duration_actual_s"] = round(duration, 2)
    meta["status"] = status
    meta["artifacts_copied"] = copied
    with open(out_dir / "metadata.yaml", "w") as f:
        yaml.safe_dump(meta, f, sort_keys=False)

    return {"name": name, "status": status, "duration": duration,
            "output_dir": str(out_dir), "artifacts": copied}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", required=True)
    p.add_argument("--list", action="store_true")
    p.add_argument("--only")
    p.add_argument("--category")
    p.add_argument("--tag")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    with open(args.manifest) as f:
        manifest = yaml.safe_load(f)

    exps = select(manifest, only=args.only, category=args.category, tag=args.tag)

    if args.list:
        list_experiments({"experiments": exps})
        return

    if not exps:
        print("No experiments match the selection.")
        sys.exit(1)

    print(f"Running {len(exps)} experiment(s) from {args.manifest}")
    print(f"Output root: {RESULTS_ROOT}")

    results = []
    for e in exps:
        r = run_one(e, dry=args.dry_run)
        results.append(r)

    print(f"\n{'=' * 70}")
    print(f"  Summary")
    print(f"{'=' * 70}")
    ok = sum(1 for r in results if r["status"] == "ok")
    print(f"  Total: {len(results)}   OK: {ok}   Failed: {len(results) - ok}")
    for r in results:
        d = r.get("duration", 0)
        print(f"  {r['status']:<10} {r['name']:<28} {d:>6.1f}s")
    print()


if __name__ == "__main__":
    main()
