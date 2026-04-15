# CUCM Prometheus Exporter

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A Prometheus exporter for Cisco Unified Communications Manager (CUCM) that collects real-time performance counters and device registration data from one or more CUCM servers, bundled with a pre-built Grafana dashboard. Supports monitoring an entire CUCM cluster from a single exporter instance.

## What It Does

This exporter connects to two CUCM SOAP APIs and translates their data into Prometheus metrics:

- **PerfMon API**: Collects 500+ performance counters across 17 object categories (calls, CPU, memory, disk, SIP, database replication, TFTP, Tomcat, media resources, and more)
- **RISPort70 API**: Collects device registration data (phones, SIP trunks, media resources) with status, IP addresses, and metadata

The included Grafana dashboard provides 41 panels across 10 rows covering call activity, device registration, system resources, network health, SIP statistics, throttling alerts, service health, and media resource utilization.

## Architecture

```
┌──────────────┐      SOAP/HTTPS       ┌───────────────┐        ┌────────────────┐
│  Prometheus   │ ──── scrape ────────> │ CUCM Exporter │ ─────> │  CUCM Pub      │
│  (port 9090)  │ <── /metrics ──────── │  (port 9100)  │ ─────> │  CUCM Sub 1    │
└──────┬───────┘                        └───────────────┘ ─────> │  CUCM Sub N    │
       │                                                         └────────────────┘
       v
┌──────────────┐
│   Grafana     │   (cucm_host label on every metric
│  (port 3000)  │    for per-server filtering)
└──────────────┘
```

On each Prometheus scrape (every 60 seconds by default), the exporter:

1. Calls `perfmonCollectCounterData` once per PerfMon object per server (17 calls per server)
2. Calls `selectCmDevice` once per server via RISPort70 to get all device registrations
3. Translates the SOAP XML responses into Prometheus gauge metrics with a `cucm_host` label identifying each server
4. Returns everything on the `/metrics` HTTP endpoint

## Quick Start with Docker

```bash
git clone <repo-url> && cd promethius_cucm

# Edit your CUCM server list
vi config/exporter_config.yaml

# Start the full stack
docker compose -f docker/docker-compose.yml up --build -d
```

Then open:

| Service   | URL                        | Credentials |
|-----------|----------------------------|-------------|
| Exporter  | http://localhost:9100/metrics | n/a       |
| Prometheus| http://localhost:9090        | n/a        |
| Grafana   | http://localhost:3000        | admin/admin |

The CUCM Overview dashboard is auto-provisioned in the "CUCM" folder in Grafana.

## Quick Start without Docker

```bash
cd promethius_cucm

# Create a virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Option A: Use the config file
vi config/exporter_config.yaml   # edit host/credentials
python -m cucm_exporter.main --config config/exporter_config.yaml

# Option B: Use environment variables
export CUCM_HOST=10.0.0.1
export CUCM_USERNAME=administrator
export CUCM_PASSWORD=yourpassword
python -m cucm_exporter.main
```

Metrics will be served at http://localhost:9100/metrics.

## Configuration

The exporter supports two configuration methods. Environment variables always take priority over the YAML file.

### YAML Config File

The default config file is at `config/exporter_config.yaml`:

```yaml
# Multi-server: monitor a full CUCM cluster
servers:
  - name: "cucm-pub"
    host: "192.168.1.20"
    port: 8443
    username: "administrator"
    password: "yourpassword"
    verify_ssl: false
  - name: "cucm-sub"
    host: "192.168.1.21"
    port: 8443
    username: "administrator"
    password: "yourpassword"
    verify_ssl: false

exporter:
  port: 9100
  log_level: "INFO"
  scrape_timeout: 55

perfmon:
  enabled: true
  objects:
    - "Cisco CallManager"
    - "Memory"
    - "Processor"
    # ... see file for full list

risport:
  enabled: true
  max_devices: 2000
  device_info_enabled: true
```

### Legacy Single-Server Config

If you only have one server, you can use the old `cucm` section or environment variables instead of the `servers` list:

```yaml
# Legacy format (still works if 'servers' list is absent)
cucm:
  host: "192.168.1.20"
  port: 8443
  username: "administrator"
  password: "yourpassword"
```

### Environment Variables

Environment variables override YAML values. For multi-server setups, use the YAML `servers` list. These env vars provide single-server fallback:

| Variable | Description | Default |
|----------|-------------|---------|
| `CUCM_HOST` | CUCM server IP or hostname | (required) |
| `CUCM_PORT` | CUCM HTTPS port | `8443` |
| `CUCM_USERNAME` | API username | (required) |
| `CUCM_PASSWORD` | API password | (required) |
| `CUCM_VERIFY_SSL` | Verify SSL certificates | `false` |
| `EXPORTER_PORT` | Metrics HTTP port | `9100` |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | `INFO` |
| `SCRAPE_TIMEOUT` | Max seconds per SOAP request | `55` |
| `PERFMON_ENABLED` | Enable PerfMon collection | `true` |
| `PERFMON_OBJECTS` | Comma-separated list of PerfMon objects | (see defaults below) |
| `RISPORT_ENABLED` | Enable RISPort70 collection | `true` |
| `RISPORT_MAX_DEVICES` | Max devices per RISPort query | `2000` |
| `RISPORT_DEVICE_INFO` | Export per-device info metrics | `true` |
| `CUCM_CONFIG_FILE` | Path to YAML config file | none |

### CLI Arguments

```
python -m cucm_exporter.main [--config PATH] [--port PORT]
```

- `--config`: Path to YAML config file
- `--port`: Override the exporter HTTP port

### Priority Order

Environment variables > YAML config file > built-in defaults

## Default PerfMon Objects

The exporter collects from 17 PerfMon objects by default:

| Category | Objects |
|----------|---------|
| **Core** | Cisco CallManager (134 counters), Cisco CallManager System Performance (29) |
| **SIP** | Cisco SIP Stack (173), Cisco SIP Station (19) |
| **System** | Memory (23), Processor (9), System (21), Network Interface (12), Partition (10), TCP (9) |
| **Services** | DB Local\_DSN (8), DB Change Notification Server (5), Replication State (2), Cisco TFTP (46), Cisco Tomcat JVM (3), Cisco Tomcat Connector (7), Cisco Media Streaming App (35) |

To add more objects, add them to the `perfmon.objects` list in the YAML config or set the `PERFMON_OBJECTS` environment variable. The CUCM server has 90 PerfMon objects total; use the PerfMon API's `perfmonListCounter` operation to discover all available objects on your system.

## Metric Naming

CUCM counter names are converted to Prometheus format:

| CUCM Object + Counter | Prometheus Metric |
|---|---|
| Cisco CallManager / CallsActive | `cucm_callmanager_calls_active{cucm_host="cucm-pub"}` |
| Memory / % Mem Used | `cucm_memory_mem_used_percent{cucm_host="cucm-pub"}` |
| Processor(0) / % CPU Time | `cucm_processor_cpu_time_percent{cucm_host="cucm-pub", instance="0"}` |
| Network Interface(eth0) / Rx Bytes | `cucm_network_interface_rx_bytes{cucm_host="cucm-pub", instance="eth0"}` |

Every metric includes a `cucm_host` label identifying which server it came from. Multi-instance objects (Processor, Network Interface, Partition, DB Local\_DSN, Tomcat Connector) also include an `instance` label.

### RISPort Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `cucm_devices_total{cucm_host, device_class, status}` | Gauge | Device count by class and registration status |
| `cucm_phones_registered{cucm_host}` | Gauge | Number of registered phones |
| `cucm_sip_trunks_total{cucm_host}` | Gauge | Total SIP trunks |
| `cucm_media_resources_registered{cucm_host}` | Gauge | Registered media resources |
| `cucm_device_info{cucm_host, device_name, ip_address, firmware, ...}` | Gauge | Per-device detail (value always 1) |
| `cucm_risport_devices_returned{cucm_host}` | Gauge | Devices in last API response |

### Meta Metrics

| Metric | Description |
|--------|-------------|
| `cucm_up{cucm_host}` | 1 if CUCM server is reachable, 0 if collection failed |
| `cucm_scrape_duration_seconds{cucm_host}` | Time taken to collect metrics from that server |

## Grafana Dashboard

The pre-built dashboard (`grafana/dashboards/cucm_overview.json`) includes a **CUCM Server** dropdown at the top (the `cucm_host` template variable) that lets you filter by server or select "All" to compare servers side by side. Timeseries panels show one line per server for easy comparison.

Panels:

| Row | Panels |
|-----|--------|
| **Exporter Health** | CUCM status, scrape duration, device count, heartbeat |
| **Call Activity** | Active calls, attempted, completed, call volume over time |
| **Device Registration** | Registered phones, SIP trunks, media resources, devices by class/status |
| **System Resources** | Memory gauge, CPU per core, disk usage by partition |
| **Network** | RX/TX byte rates, TCP connections, network errors |
| **SIP Health** | INVITE rate, station connections, rejected registrations, 5xx errors |
| **System Performance** | Code Yellow/Red events, throttling, queue signals |
| **Service Health** | DB replication state, TFTP heartbeat, Tomcat JVM, DB connections |
| **Media Resources** | MTP, transcoder, conference bridge, MOH usage (collapsed) |
| **Device Table** | Full device list with name, IP, class, status, protocol, firmware (collapsed) |

## Rate Limiting

The CUCM PerfMon API allows up to 18 requests per minute per server. With 17 PerfMon objects plus 1 RISPort call, each scrape uses 18 requests per server. The default Prometheus scrape interval is set to 60 seconds to stay within this limit. Each server is queried independently; one server failing does not affect the others.

If you reduce the scrape interval below 60 seconds, you may see 500 errors from CUCM as the rate limit kicks in. The exporter handles these gracefully (per-object error isolation; one failed object does not affect others).

## Project Structure

```
promethius_cucm/
├── cucm_exporter/
│   ├── __init__.py
│   ├── main.py                 # Entry point
│   ├── config.py               # Configuration loading
│   ├── collector.py            # Top-level Prometheus collector
│   ├── perfmon_collector.py    # PerfMon SOAP client + metrics
│   ├── risport_collector.py    # RISPort70 SOAP client + metrics
│   ├── soap_client.py          # Shared SOAP HTTP client
│   ├── metric_naming.py        # Name conversion (CamelCase to snake_case)
│   └── constants.py            # SOAP templates, defaults, mappings
├── config/
│   └── exporter_config.yaml    # Default configuration
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml      # Full stack (exporter + Prometheus + Grafana)
├── prometheus/
│   └── prometheus.yml          # Prometheus scrape config
├── grafana/
│   ├── provisioning/           # Auto-provisioned datasource + dashboard loader
│   └── dashboards/
│       └── cucm_overview.json  # Pre-built Grafana dashboard
└── requirements.txt
```

## Requirements

- Python 3.10+
- Network access to the CUCM server on port 8443
- A CUCM user account with API access (typically an administrator account)
- Docker and Docker Compose (for containerized deployment)

## CUCM APIs Used

- **PerfMon API** (`/perfmonservice2/services/PerfmonService`): `perfmonCollectCounterData` for counter values, `perfmonListCounter` for discovery
- **RISPort70 API** (`/realtimeservice2/services/RISService70`): `selectCmDevice` for device registration data

Both APIs use SOAP over HTTPS with HTTP Basic Authentication. The exporter disables SSL certificate verification by default since CUCM typically uses self-signed certificates.
