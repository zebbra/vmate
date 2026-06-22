![vmate](vmate-banner.png)

# vmate — Victoria Metrics Agent Target Exporter

## Motivation

In a typical VictoriaMetrics setup you run multiple vmagent instances — often as a sharded StatefulSet — scraping thousands of targets across different namespaces. Each pod only exposes its own `/targets` UI, and on production clusters no ingress is configured at all. Finding out *why* a target is down (404, auth failure, timeout, DNS error) means port-forwarding to individual pods and clicking around — not scalable across a fleet.

vmate solves this by polling every vmagent pod's `/api/v1/targets` endpoint from inside the cluster, aggregating the results, and exposing them both as Prometheus metrics and a simple JSON API.

## How it works

1. On startup (and every poll cycle) vmate discovers vmagent pods via the Kubernetes API using a configurable label selector.
2. Each pod's `/api/v1/targets` is queried concurrently.
3. Unhealthy targets are aggregated, error messages are parsed into structured fields (`error`, `error_code`, `target_url`), and results are held in memory.
4. Prometheus metrics are updated and the JSON API is served — no persistent storage needed.

## Endpoints

| Endpoint | Description |
|---|---|
| `/` | Index with links |
| `/metrics` | Prometheus metrics |
| `/unhealthy` | All unhealthy targets across all pods |
| `/unhealthy?raw=true` | Same but with unparsed error strings |
| `/pod/{pod}/unhealthy` | Unhealthy targets for a specific vmagent pod |
| `/job/{job}/unhealthy` | Unhealthy targets for a specific scrape job |
| `/summary` | Runtime state: discovered pods, unhealthy count and affected jobs |
| `/config` | Static settings: label selector, intervals, blacklists |
| `/healthz` | Health check |

## Metrics

| Metric | Labels | Description |
|---|---|---|
| `vmagent_instances_configured` | — | Pods discovered via label selector |
| `vmagent_instances_reachable` | — | Pods that responded on last poll |
| `vmagent_targets_total` | `pod`, `state` | Target counts per pod and state |
| `vmagent_job_targets_total` | `job`, `state` | Fleet-wide target counts per job and state |
| `vmagent_unhealthy_target_info` | `pod`, `scrape_pool`, `job`, `instance` | 1 per unhealthy target, 0 on recovery |

## Configuration

All options are set via environment variables with the `VMTE_` prefix.

| Variable | Default | Description |
|---|---|---|
| `VMTE_NAMESPACE` | `monitoring` | Namespace to discover vmagent pods in |
| `VMTE_LABEL_SELECTOR` | `app.kubernetes.io/instance=victoria-metrics-agent` | Label selector for vmagent pods |
| `VMTE_VMAGENT_PORT` | `8429` | Port to query on each vmagent pod |
| `VMTE_POLL_INTERVAL` | `60` | Seconds between poll cycles |
| `VMTE_VMAGENT_TIMEOUT` | `10` | Per-pod request timeout in seconds |
| `VMTE_IGNORE_INFO_JOBS` | `` | Comma-separated jobs excluded from `vmagent_unhealthy_target_info` and `/unhealthy` endpoints |
| `VMTE_IGNORE_HEALTH_JOBS` | `` | Comma-separated jobs excluded from all target count metrics |

`VMTE_IGNORE_INFO_JOBS` and `VMTE_IGNORE_HEALTH_JOBS` are independent — useful for suppressing noise from known-flapping jobs without losing health counts, or vice versa.
