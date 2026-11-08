import pytest

from app import collector
from app.metrics import (
    instances_configured,
    instances_reachable,
    job_targets_total,
    targets_total,
    unhealthy_target_info,
)


@pytest.fixture(autouse=True)
def reset_collector_state():
    """Gauges live in prometheus_client's global registry and collector's
    dedup sets are module-level, so tests must reset both or leak state into
    each other."""
    targets_total.clear()
    job_targets_total.clear()
    unhealthy_target_info.clear()
    instances_configured.set(0)
    instances_reachable.set(0)
    collector._known_unhealthy.clear()
    collector._known_job_states.clear()
    collector._known_pods.clear()
    collector.unhealthy_targets.clear()
    collector.poll_status.update(last_poll=None, duration=None, pods={})
    yield


def metric_samples(metric):
    """Read a Gauge's current label->value map via the public collect() API,
    without the side effect of .labels(...) silently creating new series."""
    return {
        tuple(sorted(sample.labels.items())): sample.value for family in metric.collect() for sample in family.samples
    }
