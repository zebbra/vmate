from prometheus_client import Gauge, Info

instances_configured = Gauge(
    "vmagent_instances_configured",
    "Number of vmagent pods discovered via label selector",
)

instances_reachable = Gauge(
    "vmagent_instances_reachable",
    "Number of vmagent pods that responded successfully on last poll",
)

targets_total = Gauge(
    "vmagent_targets_total",
    "Number of scrape targets per pod and state",
    ["pod", "state"],
)

unhealthy_target_info = Gauge(
    "vmagent_unhealthy_target_info",
    "Unhealthy scrape targets with error detail (value=1 while unhealthy)",
    ["pod", "scrape_pool", "job", "instance", "error"],
)
