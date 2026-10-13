#!/usr/bin/env python3
"""
F01 probe: continuous HTTP GET against a target URL.
Logs each attempt to CSV: ts, elapsed_ms, http_code, status
"""
import argparse, csv, time, urllib.request, urllib.error

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", required=True)
    p.add_argument("--duration", type=int, default=40)
    p.add_argument("--interval", type=float, default=0.2)
    p.add_argument("--out", required=True)
    args = p.parse_args()

    end = time.monotonic() + args.duration
    with open(args.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ts", "elapsed_ms", "http_code", "status"])
        while time.monotonic() < end:
            t0 = time.monotonic()
            code = "ERR"
            status = "ERR"
            try:
                r = urllib.request.urlopen(args.url, timeout=2)
                code = r.status
                status = "OK" if code == 200 else f"HTTP_{code}"
                r.close()
            except urllib.error.HTTPError as e:
                code = e.code
                status = f"HTTP_{code}"
            except Exception as e:
                code = "ERR"
                status = type(e).__name__
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            w.writerow([f"{time.time():.3f}", elapsed_ms, code, status])
            f.flush()
            next_t = t0 + args.interval
            delta = next_t - time.monotonic()
            if delta > 0:
                time.sleep(delta)
    print(f"Done: {args.out}")

if __name__ == "__main__":
    main()
