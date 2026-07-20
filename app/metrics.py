from prometheus_client import Gauge

instances_configured = Gauge(
    "vmate_instances_configured",
    "Number of vmagent pods discovered via label selector",
)

instances_reachable = Gauge(
    "vmate_instances_reachable",
    "Number of vmagent pods that responded successfully on last poll",
)

targets_total = Gauge(
    "vmate_targets_total",
    "Number of non-up scrape targets (down/unknown) per pod and state — "
    "up targets are not polled or counted",
    ["pod", "state"],
)

job_targets_total = Gauge(
    "vmate_job_targets_total",
    "Number of non-up scrape targets (down/unknown) per job and state, "
    "fleet-wide, excludes ignore_health_jobs — up targets are not polled or counted",
    ["job", "state"],
)

unhealthy_target_info = Gauge(
    "vmate_unhealthy_target_info",
    "Unhealthy scrape targets (value=1 while unhealthy, see /unhealthy for error detail)",
    ["pod", "scrape_pool", "job", "instance"],
)
