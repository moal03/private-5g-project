# Phase 9 Report — Monitoring and Observability

**Project:** Simulation of a Private 5G Standalone Network for a Smart Factory
**Date:** 2026-10-13
**Environment:** Ubuntu 26.04.1 LTS (resolute), kernel 7.0.0-38-generic, 8 CPU cores, 14 GiB RAM

---

## 1. Objective

Add observability to the private 5G testbed. The goal is to collect
real metrics from the 5G Core user-plane functions, from the host, and
from the applications, store them as time-series data, and visualize
them on a dashboard.

The phase is not only about installing tools. It is about obtaining
evidence of a working monitoring pipeline: Prometheus scrapes the
Open5GS UPFs and the host, Grafana queries Prometheus, and a dashboard
shows live values.

---

## 2. Environment

| Component | Version |
|-----------|---------|
| Prometheus | 2.53.5+ds1-3 (Ubuntu repos) |
| prometheus-node-exporter | 1.10.2-1 (Ubuntu repos) |
| Grafana | 13.2.3 (official apt.grafana.com repo) |
| Grafana Prometheus plugin | 13.2.3 (from GitHub release) |
| Open5GS | 2.8.0~resolute6 |
| OCUDU CU/DU | built 2026-10-12 |
| OAI UE | develop commit 6f89078b40 |

---

## 3. Installation

### 3.1 Prometheus and Node Exporter (Ubuntu Repos)

    sudo apt update
    sudo apt install -y prometheus prometheus-node-exporter

Both services started automatically. Prometheus initially failed to
bind port 9090 because seven Open5GS functions were already listening
on 127.0.0.x:9090 (each function binds its own loopback alias to the
same numeric port). The conflict was resolved by moving Prometheus to
port 9095:

    # /etc/default/prometheus
    ARGS=" --web.listen-address=:9095"

After the change:

    prometheus.service: active
    Listening on: *:9095

### 3.2 Grafana (Official Apt Repo)

Grafana was not in the Ubuntu universe repository, so the official
Grafana repository was added:

    curl -fsSL https://apt.grafana.com/gpg.key | \
      sudo gpg --dearmor -o /etc/apt/keyrings/grafana.gpg
    echo "deb [signed-by=/etc/apt/keyrings/grafana.gpg] \
      https://apt.grafana.com stable main" | \
      sudo tee /etc/apt/sources.list.d/grafana.list
    sudo apt update
    sudo apt install -y grafana

The download was 380 MB and completed in 7 minutes.

---

## 4. Prometheus Configuration

Configuration file: /etc/prometheus/prometheus.yml

    global:
      scrape_interval: 15s
      evaluation_interval: 15s

    scrape_configs:
      - job_name: 'prometheus'
        static_configs:
          - targets: ['localhost:9095']

      - job_name: 'node'
        static_configs:
          - targets: ['localhost:9100']

      - job_name: 'open5gs-upf-central'
        static_configs:
          - targets: ['127.0.0.7:9090']
            labels:
              upf: 'central'
              dnn: 'internet'

      - job_name: 'open5gs-upf-edge'
        static_configs:
          - targets: ['127.0.0.8:9091']
            labels:
              upf: 'edge'
              dnn: 'factory'

The two Open5GS UPF metrics endpoints were already configured in
Phase 7 (metrics block on ports 9090 for UPF-A and 9091 for UPF-B).

---

## 5. Prometheus Target Verification

After the configuration was reloaded, four targets were active:

    Job                          Target                 Health
    --------------------------------------------------------------
    node                         localhost:9100/metrics up
    open5gs-upf-central          127.0.0.7:9090/metrics up
    open5gs-upf-edge             127.0.0.8:9091/metrics up
    prometheus                   localhost:9095/metrics up

All four reported health "up" after the first scrape.

---

## 6. Open5GS UPF Metrics Exposed

Both UPFs expose the following metrics via the standard Prometheus text
format. Seven metrics are visible at the time of writing:

    fivegs_ep_n3_gtp_indatapktn3upf
    fivegs_ep_n3_gtp_outdatapktn3upf
    fivegs_upffunction_sm_n4sessionestabreq
    fivegs_upffunction_sm_n4sessionreport
    fivegs_upffunction_sm_n4sessionreportsucc
    fivegs_upffunction_upf_sessionnbr
    fivegs_upffunction_upf_qosflows{dnn="internet"}

The metric names are documented in the Open5GS metrics exporter and
follow the fivegs_ prefix.

---

## 7. Live Metric Snapshot

Captured at 2026-10-13T19:14:13:

    upf_sessions_central: 1   [dnn=internet, upf=central]
    upf_sessions_edge:    1   [dnn=factory,  upf=edge]

    qos_flows: 1   [dnn=internet, upf=central]
    qos_flows: 1   [dnn=factory,  upf=edge]

    n3_ingress_central: 0
    n3_ingress_edge:    0
    n3_egress_central:  0
    n3_egress_edge:     0

    n4_requests:   2   [upf=central]
    n4_requests:   2   [upf=edge]

    n4_reports_ok: 1   [upf=central]
    n4_reports_ok: 0   [upf=edge]

    host_cpu_nonidle: 31.82 %   [cpu=0]
    host_cpu_nonidle: 26.84 %   [cpu=1]
    host_cpu_nonidle: 30.24 %   [cpu=2]
    host_cpu_nonidle: 27.93 %   [cpu=3]
    host_cpu_nonidle: 23.53 %   [cpu=4]
    host_cpu_nonidle: 25.80 %   [cpu=5]
    host_cpu_nonidle: 27.76 %   [cpu=6]
    host_cpu_nonidle: 26.73 %   [cpu=7]

The values confirm that the monitoring pipeline is collecting real
data:

- 1 active session on each UPF (one per UE PDU session)
- 1 QoS flow per DNN
- 2 N4 session establishment requests per UPF (matching the two UE
  sessions, one internet and one factory)
- N3 GTP-U counters at 0 because no traffic was flowing at the moment
  of the snapshot
- Per-core CPU utilization in the 23–32% range

---

## 8. Grafana Configuration

### 8.1 Data Source

The Prometheus data source was created through the Grafana HTTP API:

    curl -s -u admin:admin -X POST http://localhost:3000/api/datasources \
      -H "Content-Type: application/json" \
      -d '{"name":"Prometheus","type":"prometheus",
           "url":"http://localhost:9095","access":"proxy",
           "isDefault":true,"jsonData":{"timeInterval":"15s"}}'

Result:

    {"id": 2, "uid": "dg148jlnd3wg0d",
     "name": "Prometheus", "type": "prometheus",
     "url": "http://localhost:9095"}

### 8.2 Data Source Health

    curl ... /api/datasources/uid/dg148jlnd3wg0d/health

Returned:

    {"status": "OK",
     "message": "Successfully queried the Prometheus API.",
     "details": {"application": "Prometheus"}}

### 8.3 Query through Grafana

A direct query through the Grafana proxy was tested:

    curl ... /api/datasources/proxy/uid/dg148jlnd3wg0d/api/v1/query?query=fivegs_upffunction_upf_sessionnbr

Returned a Prometheus vector result with two entries:

    fivegs_upffunction_upf_sessionnbr{dnn="internet", upf="central"} = 1
    fivegs_upffunction_upf_sessionnbr{dnn="factory",  upf="edge"}    = 1

---

## 9. Dashboard

### 9.1 Panels Created

The dashboard "Private 5G — Phase 9" was created through the Grafana
API. It has 6 timeseries panels:

| # | Panel | Metric |
|---|-------|--------|
| 1 | UPF Sessions (both) | fivegs_upffunction_upf_sessionnbr, per UPF |
| 2 | QoS Flows per DNN | fivegs_upffunction_upf_qosflows |
| 3 | N3 GTP-U Ingress (packets/s) | rate(fivegs_ep_n3_gtp_indatapktn3upf[1m]) |
| 4 | N3 GTP-U Egress (packets/s) | rate(fivegs_ep_n3_gtp_outdatapktn3upf[1m]) |
| 5 | N4 Session Establishments | fivegs_upffunction_sm_n4sessionestabreq and reportsucc |
| 6 | Host CPU — non-idle % | (1 - rate(node_cpu_seconds_total{mode="idle"}[1m])) * 100 |

### 9.2 Dashboard Registration

The dashboard was registered with the following API response:

    {"id": 2349141595406336,
     "uid": "a4ql9t",
     "slug": "private-5g-e28094-phase-9",
     "url": "/d/a4ql9t/private-5g-e28094-phase-9",
     "status": "success",
     "version": 1}

### 9.3 Access

The dashboard is reachable at:

    http://localhost:3000/d/a4ql9t/private-5g-e28094-phase-9

The default credentials for this Grafana instance are admin/admin.
Grafana requires authentication before rendering the dashboard, so an
unauthenticated request returns HTTP 302 redirecting to the login page.
This is expected behavior.

---

## 10. Methodological Notes

### 10.1 Geo-blocked Plugin

Grafana 13 does not bundle the Prometheus datasource plugin in the
.deb package. When Grafana started, it attempted to download the plugin
from its own CDN and received:

    Failed to install plugin pluginId=prometheus
    error="...403: AccessDenied...
    We're sorry, but this service is not available in your location"

This is the same style of restriction that affected MongoDB in Phase 3.
The workaround was to download the plugin release directly from GitHub:

    GitHub release URL:
    https://github.com/grafana/grafana-prometheus-datasource/releases/download/v13.2.3/prometheus-13.2.3.linux_amd64.zip

The SHA1 checksum was verified before installation:

    Expected: 5446c4e7b1efa5211924e2697f96a52d3732c07a
    Actual:   5446c4e7b1efa5211924e2697f96a52d3732c07a

The zip was extracted into /var/lib/grafana/plugins/prometheus and
Grafana was restarted. The Prometheus datasource then appeared in the
plugin list and could be selected normally.

### 10.2 Port Collision Between Prometheus and Open5GS

Prometheus's default port (9090) conflicted with seven Open5GS
functions, each bound to 127.0.0.x:9090 on separate loopback aliases.
Prometheus was moved to port 9095 to avoid the conflict.

### 10.3 Interference with the Radio Path

During the Grafana download (7 minutes of sustained disk and CPU
activity), the UE's registration with the 5G Core expired. The AMF
reported:

    Unknown UE by 5G-S_TMSI
    Handling service request failed [Not registered]

Both PDU sessions were lost and the UE entered RRC IDLE. After the
download finished, a clean restart of the DU and UE restored full
connectivity: both PDU sessions re-established and both
central/edge ping tests passed with 0% loss.

This is a genuine observation about the software testbed's sensitivity
to host contention and is documented in the limitations.

---

## 11. Files Produced

### 11.1 Configs (configs/phase9/)

    dashboard.json                  — dashboard source (6 panels)
    dashboard-from-grafana.json     — dashboard as served by Grafana

### 11.2 Logs (logs/phase9/)

    final-state.txt                 — full stack and monitoring state
    prometheus-targets.json         — /api/v1/targets from Prometheus

### 11.3 Results (results/phase9/)

    metric-snapshot.txt             — live values from 10 queries

### 11.4 Directories Created

    configs/phase9/
    docs/phase9/
    logs/phase9/
    results/phase9/
    scripts/phase9/

---

## 12. Limitations

1. **Metrics coverage is partial.** In Open5GS 2.8.0, only the UPF
   exposes native Prometheus metrics. The AMF, SMF, and other control
   plane functions do not. Monitoring of the control plane relies on
   systemd logs (journalctl), which are not integrated into Grafana.

2. **No RAN metrics yet.** The OCUDU CU and DU do not expose
   Prometheus metrics in the current configuration. Adding them would
   require an E2/KPM interface, which is Phase 12 (RIC) work.

3. **Host-based only.** All monitoring is on the single host. In a
   real private 5G deployment, the RAN and edge UPF would run on
   separate hardware.

4. **Default credentials.** Grafana was left with the default
   admin/admin login. For a real deployment, the password should be
   changed immediately.

5. **No alerting rules configured.** Alerting is out of scope for
   Phase 9. Rules would need to be defined in Prometheus or Grafana
   separately.

6. **No log aggregation.** Loki was not deployed. Application and
   core logs are still read manually with journalctl or tail.

7. **UE registration timeout during heavy disk I/O.** As noted in
   Section 10.3, sustained high I/O on the host causes the UE's
   registration to expire. This is a limitation of running the entire
   testbed on one machine.

---

## 13. Conclusion

Phase 9 produced a working end-to-end monitoring pipeline for the
private 5G testbed:

- Prometheus (on port 9095) scrapes four targets.
- Node Exporter (on port 9100) exposes host metrics.
- Both Open5GS UPFs expose their metrics on ports 9090 and 9091.
- All four Prometheus targets report "up".
- Grafana (on port 3000) queries Prometheus via a datasource that
  returned "Successfully queried the Prometheus API".
- A six-panel dashboard shows UPF sessions, QoS flows, N3 GTP-U
  traffic, N4 session events, and per-core host CPU.

Two real-world constraints were documented:

1. The Prometheus datasource plugin for Grafana 13 is geo-blocked
   from the official Grafana CDN. It was installed from a
   SHA1-verified GitHub release as a documented workaround.

2. Heavy disk activity during installation caused the UE to lose
   its 5G registration. A restart restored the data path.

The dashboard and metric pipeline give a foundation for Phase 12
(Near-RT RIC and xApp) where additional RAN-level metrics will be
correlated with what the UPF and host already report.

---

**End of Phase 9 Report**
