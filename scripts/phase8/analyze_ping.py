#!/usr/bin/env python3
"""
Phase 8 — Ping RTT analysis.

Reads a Linux ping output file, extracts every RTT sample from the
"time=..." or "time<..." fields, and prints descriptive statistics.

Usage:
    python3 analyze_ping.py PING_OUTPUT.txt
"""

import re
import sys
import statistics
from pathlib import Path


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 analyze_ping.py PING_OUTPUT.txt")
        sys.exit(1)

    path = Path(sys.argv[1])
    if not path.is_file():
        print(f"File not found: {path}")
        sys.exit(1)

    text = path.read_text(errors="replace")

    # Match "time=12.3 ms" or "time<1.00 ms"
    pattern = re.compile(r"\btime[=<]([0-9]+(?:\.[0-9]+)?)\s*ms\b")
    rtt = [float(v) for v in pattern.findall(text)]

    if not rtt:
        print(f"No RTT samples found in {path}")
        sys.exit(1)

    rtt_sorted = sorted(rtt)
    n = len(rtt_sorted)

    def pct(p):
        # Nearest-rank percentile
        k = max(0, min(n - 1, int(round(p / 100.0 * n)) - 1))
        return rtt_sorted[k]

    print(f"File:   {path}")
    print(f"Samples: {n}")
    print(f"Min:     {min(rtt):.3f} ms")
    print(f"Median:  {statistics.median(rtt):.3f} ms")
    print(f"Mean:    {statistics.mean(rtt):.3f} ms")
    print(f"Stdev:   {statistics.stdev(rtt):.3f} ms" if n > 1 else "Stdev:   n/a")
    print(f"P95:     {pct(95):.3f} ms")
    print(f"P99:     {pct(99):.3f} ms")
    print(f"Max:     {max(rtt):.3f} ms")


if __name__ == "__main__":
    main()
