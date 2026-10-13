#!/usr/bin/env python3
"""
URLLC echo server. Binds to a given address:port, echoes back any
UDP packet received. Prints a line per received packet (optional).
"""
import argparse
import socket

parser = argparse.ArgumentParser()
parser.add_argument("--bind", required=True)
parser.add_argument("--port", type=int, default=9200)
parser.add_argument("--verbose", action="store_true")
args = parser.parse_args()

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((args.bind, args.port))

print(f"URLLC echo server listening on {args.bind}:{args.port}", flush=True)

count = 0
while True:
    try:
        data, addr = sock.recvfrom(2048)
        sock.sendto(data, addr)
        count += 1
        if args.verbose and count % 100 == 0:
            print(f"echoed {count} packets (last from {addr})", flush=True)
    except KeyboardInterrupt:
        print(f"\nStopped after {count} packets.", flush=True)
        break
