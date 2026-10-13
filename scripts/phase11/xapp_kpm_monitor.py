#!/usr/bin/env python3
"""
Phase 11 custom xApp — KPM Monitoring with Rule-Based Congestion Alert.

Subscribes to E2SM-KPM indications from the OCUDU DU via FlexRIC.
Writes every measurement to CSV. Detects congestion when a selected
metric exceeds a threshold for N consecutive KPM reports.

The KPM subscription parameters (interval, metrics, format) come from
/usr/local/etc/flexric/xapp_kpm.conf, which FlexRIC reads automatically.
"""

import argparse
import csv
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

import xapp_sdk as ric


# ---------------------------------------------------------------------
# KPM callback (runs in a C++ thread)
# ---------------------------------------------------------------------
class KPMCallback(ric.kpm_cb):
    def __init__(self, session):
        ric.kpm_cb.__init__(self)
        self.session = session

    def handle(self, ind):
        try:
            self.session.on_indication(ind)
        except Exception as e:
            print(f"[callback error] {type(e).__name__}: {e}", flush=True)


# ---------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------
class Session:
    def __init__(self, csv_path, threshold, required_consecutive):
        self.csv_path = csv_path
        self.threshold = threshold
        self.required_consecutive = required_consecutive
        self.csv_file = open(csv_path, "w", newline="")
        self.writer = csv.writer(self.csv_file)
        self.writer.writerow([
            "wall_time", "kpm_start_ms", "node_type", "node_id",
            "format", "ue_type", "ue_id", "metric", "value",
        ])
        self.csv_file.flush()

        # Congestion detection state
        self.prb_history = []           # rolling list of (timestamp, prb_value)
        self.congested = False
        self.congestion_events = []     # list of (start_ts, end_ts)
        self.sample_count = 0
        self.bytes_written = 0

    def log(self, msg):
        ts = datetime.now().isoformat(timespec="milliseconds")
        print(f"[{ts}] {msg}", flush=True)

    def on_indication(self, ind):
        kpm_start = None
        node_type = "?"
        node_id = "?"
        try:
            if ind.hdr:
                kpm_start = int(ind.hdr.kpm_ric_ind_hdr_format_1.collectStartTime)
            if ind.id:
                node_type = str(ind.id.type)
                node_id = str(getattr(ind.id.nb_id, "nb_id", "?"))
        except Exception:
            pass

        wall = datetime.now().isoformat(timespec="milliseconds")

        if ind.msg.type == ric.FORMAT_1_INDICATION_MESSAGE:
            self._handle_format1(wall, kpm_start, node_type, node_id, ind.msg.frm_1)
        elif ind.msg.type == ric.FORMAT_3_INDICATION_MESSAGE:
            self._handle_format3(wall, kpm_start, node_type, node_id, ind.msg.frm_3)
        else:
            self.log(f"unsupported format {ind.msg.type}")

    def _metric_name(self, meas_info):
        try:
            if meas_info.meas_type.type == ric.NAME_MEAS_TYPE:
                return str(meas_info.meas_type.name)
            elif meas_info.meas_type.type == ric.ID_MEAS_TYPE:
                return f"id_{meas_info.meas_type.id}"
        except Exception:
            pass
        return "unknown"

    def _metric_value(self, meas_record):
        try:
            if meas_record.value == ric.INTEGER_MEAS_VALUE:
                return int(meas_record.int_val)
            elif meas_record.value == ric.REAL_MEAS_VALUE:
                return float(meas_record.real_val)
            elif meas_record.value == ric.NO_VALUE_MEAS_VALUE:
                return None
        except Exception:
            pass
        return None

    def _handle_format1(self, wall, kpm_start, node_type, node_id, frm):
        try:
            n_data = int(frm.meas_data_lst_len)
            n_info = int(frm.meas_info_lst_len)
        except Exception:
            return
        for md in frm.meas_data_lst:
            try:
                records = list(md.meas_record_lst)
                infos = list(frm.meas_info_lst)
            except Exception:
                continue
            for rec, info in zip(records, infos):
                name = self._metric_name(info)
                value = self._metric_value(rec)
                self.writer.writerow([
                    wall, kpm_start or "", node_type, node_id,
                    "1", "", "", name, value if value is not None else "",
                ])
                self.bytes_written += 1
                self._check_congestion(wall, name, value)
        self.csv_file.flush()

    def _handle_format3(self, wall, kpm_start, node_type, node_id, frm):
        try:
            ue_list = list(frm.ue_meas_report_lst)
        except Exception:
            return
        for ue in ue_list:
            ue_type = "?"
            ue_id = "?"
            try:
                ue_type = str(ue.ue_id.type)
                if hasattr(ue.ue_id, "gnb_du_ue_id"):
                    ue_id = str(ue.ue_id.gnb_du_ue_id.gnb_cu_ue_f1ap)
                elif hasattr(ue.ue_id, "gnb_cu_up_ue_id"):
                    ue_id = str(ue.ue_id.gnb_cu_up_ue_id)
            except Exception:
                pass
            try:
                ue_md = ue.meas_data_lst
                infos = list(ue.meas_info_lst)
            except Exception:
                continue
            for md in ue_md:
                try:
                    records = list(md.meas_record_lst)
                except Exception:
                    continue
                for rec, info in zip(records, infos):
                    name = self._metric_name(info)
                    value = self._metric_value(rec)
                    self.writer.writerow([
                        wall, kpm_start or "", node_type, node_id,
                        "3", ue_type, ue_id, name, value if value is not None else "",
                    ])
                    self.bytes_written += 1
                    self._check_congestion(wall, name, value)
        self.csv_file.flush()

    def _check_congestion(self, wall, metric, value):
        if metric != "RRU.PrbTotDl" or value is None:
            return
        try:
            v = float(value)
        except Exception:
            return

        self.sample_count += 1
        self.prb_history.append((wall, v))
        if len(self.prb_history) > self.required_consecutive:
            self.prb_history.pop(0)

        recently_high = (len(self.prb_history) == self.required_consecutive
                         and all(x[1] > self.threshold for x in self.prb_history))

        if not self.congested and recently_high:
            self.congested = True
            self.congestion_events.append({"start": wall, "end": None})
            self.log(f"CONGESTION_DETECTED  PRB_DL={v:.2f} > {self.threshold} "
                     f"for {self.required_consecutive} samples")
        elif self.congested and v < self.threshold * 0.8:
            self.congested = False
            if self.congestion_events and self.congestion_events[-1]["end"] is None:
                self.congestion_events[-1]["end"] = wall
            self.log(f"CONGESTION_CLEARED   PRB_DL={v:.2f} < {self.threshold * 0.8:.2f}")

    def close(self):
        self.csv_file.flush()
        self.csv_file.close()
        print(f"\n=== Session summary ===")
        print(f"  CSV:              {self.csv_path}")
        print(f"  Rows written:     {self.bytes_written}")
        print(f"  PRB samples:      {self.sample_count}")
        print(f"  Congestion events: {len(self.congestion_events)}")
        for i, ev in enumerate(self.congestion_events, 1):
            print(f"    [{i}] start={ev['start']}  end={ev['end']}")


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------
def get_oran_tti(tti):
    return {
        1: ric.Interval_ms_1,
        2: ric.Interval_ms_2,
        5: ric.Interval_ms_5,
        10: ric.Interval_ms_10,
        100: ric.Interval_ms_100,
        1000: ric.Interval_ms_1000,
    }.get(tti)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--duration", type=int, default=30,
                   help="seconds to run (default 30)")
    p.add_argument("--threshold", type=float, default=0.5,
                   help="PRB utilization threshold (0..1) for congestion alert")
    p.add_argument("--consecutive", type=int, default=3,
                   help="number of consecutive samples above threshold")
    p.add_argument("--out", required=True, help="output CSV path")
    args = p.parse_args()

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    session = Session(args.out, args.threshold, args.consecutive)
    session.log(f"Starting xApp: duration={args.duration}s "
                f"threshold={args.threshold} consecutive={args.consecutive}")
    session.log(f"CSV output: {args.out}")

    # Connect to RIC. Pass only argv[0] so FlexRIC's C parser doesn't
    # see our argparse flags (it would reject unknown options).
    ric.init([sys.argv[0]])

    oran_sm = ric.get_oran_sm_conf()
    conn = ric.conn_e2_nodes()
    if len(conn) == 0:
        session.log("ERROR: no E2 nodes connected")
        session.close()
        return 1
    session.log(f"Connected E2 nodes: {len(conn)}")
    for i, node in enumerate(conn):
        session.log(f"  Node {i}: type={node.id.type} nb_id={node.id.nb_id.nb_id}")

    # Subscribe per SM config
    kpm_handlers = []
    for sm in oran_sm:
        if sm.name != "KPM":
            continue
        tti = get_oran_tti(sm.time)
        actions = [a.name for a in sm.actions]
        session.log(f"KPM subscription: interval={sm.time}ms "
                    f"format={sm.format} actions={len(actions)}")
        session.log(f"  Actions: {', '.join(actions)}")

        for node in conn:
            cb = KPMCallback(session)
            h = ric.report_kpm_sm(node.id, tti, actions, cb)
            kpm_handlers.append(h)
            session.log(f"  Subscribed on node {node.id.nb_id.nb_id}")

    # Run
    session.log(f"Running for {args.duration}s — Ctrl+C to stop early")
    try:
        time.sleep(args.duration)
    except KeyboardInterrupt:
        session.log("Interrupted by user")

    # Unsubscribe
    session.log("Removing KPM subscriptions...")
    for h in kpm_handlers:
        try:
            ric.rm_report_kpm_sm(h)
        except Exception as e:
            session.log(f"  rm handler error: {e}")

    # Wait for try_stop (FlexRIC deadlock avoidance)
    session.log("Waiting for clean shutdown...")
    waited = 0
    while ric.try_stop == 0 and waited < 5:
        time.sleep(0.5)
        waited += 1

    session.close()
    session.log("xApp done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
