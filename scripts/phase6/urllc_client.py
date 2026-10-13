#!/usr/bin/env python3
"""
URLLC UDP echo client. Sends periodic packets, records per-packet RTT.
Writes to CSV: timestamp,seq,rtt_us,status
"""
import argparse
import csv
import socket
import struct
import sys
import time

parser = argparse.ArgumentParser()
parser.add_argument("--server", required=True, help="Destination IP")
parser.add_argument("--port", type=int, default=9200)
parser.add_argument("--bind", default="", help="Local bind IP (optional)")
parser.add_argument("--rate", type=int, default=50, help="Packets per second")
parser.add_argument("--duration", type=int, default=30, help="Seconds")
parser.add_argument("--out", required=True, help="Output CSV path")
parser.add_argument("--payload-size", type=int, default=32, help="Bytes of payload beyond 8-byte header")
args = parser.parse_args()

interval = 1.0 / args.rate
payload = b"\x00" * args.payload_size

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
if args.bind:
    sock.bind((args.bind, 0))
sock.settimeout(1.0)

end_time = time.monotonic() + args.duration
seq = 0
sent = 0
received = 0

with open(args.out, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["ts", "seq", "rtt_us", "status"])
    while time.monotonic() < end_time:
        ts_send = time.monotonic()
        pkt = struct.pack("!Q", seq) + payload
        try:
            sock.sendto(pkt, (args.server, args.port))
            sent += 1
            # Receive reply
            data, _ = sock.recvfrom(2048)
            ts_recv = time.monotonic()
            rtt_us = int((ts_recv - ts_send) * 1_000_000)
            w.writerow([f"{ts_send:.6f}", seq, rtt_us, "OK"])
            received += 1
        except socket.timeout:
            w.writerow([f"{ts_send:.6f}", seq, "", "TIMEOUT"])
        except Exception as e:
            w.writerow([f"{ts_send:.6f}", seq, "", f"ERR:{e}"])

        seq += 1
        # Sleep to maintain rate
        next_send = ts_send + interval
        delta = next_send - time.monotonic()
        if delta > 0:
            time.sleep(delta)

print(f"Done. Sent={sent} Received={received} Loss={100*(sent-received)/sent:.2f}%", flush=True)
