import httpx

from app import collector
from app.config import settings
from app.discovery import VmagentPod
from app.metrics import instances_reachable, job_targets_total, targets_total, unhealthy_target_info
from tests.conftest import metric_samples


def make_pod(name: str) -> VmagentPod:
    return VmagentPod(name=name, pod_ip="10.0.0.1", node="node-1")


def target(job, instance, health, scrape_pool="pool", error=""):
    return {
        "health": health,
        "labels": {"job": job, "instance": instance},
        "scrapePool": scrape_pool,
        "lastError": error,
    }


def make_poll_pod(pods_targets: dict):
    """Fake replacement for collector.poll_pod: yields canned targets per pod
    name instead of streaming from a real vmagent."""

    async def fake_poll_pod(client, pod):
        for t in pods_targets.get(pod.name, []):
            yield t

    return fake_poll_pod


async def test_collect_all_counts_by_pod_and_job(monkeypatch):
    pod_a = make_pod("vmagent-0")
    monkeypatch.setattr(collector, "discover_pods", lambda: [pod_a])
    monkeypatch.setattr(
        collector,
        "poll_pod",
        make_poll_pod(
            {
                "vmagent-0": [
                    target("job-x", "10.0.0.1:9100", "up"),
                    target("job-x", "10.0.0.2:9100", "down", error="boom"),
                    target("job-y", "10.0.0.3:9100", "unknown"),
                ]
            }
        ),
    )

    await collector.collect_all()

    pod_values = metric_samples(targets_total)
    assert pod_values[(("pod", "vmagent-0"), ("state", "up"))] == 1
    assert pod_values[(("pod", "vmagent-0"), ("state", "down"))] == 1
    assert pod_values[(("pod", "vmagent-0"), ("state", "unknown"))] == 1

    job_values = metric_samples(job_targets_total)
    assert job_values[(("job", "job-x"), ("state", "up"))] == 1
    assert job_values[(("job", "job-x"), ("state", "down"))] == 1
    assert job_values[(("job", "job-y"), ("state", "unknown"))] == 1

    unhealthy_values = metric_samples(unhealthy_target_info)
    key = (("instance", "10.0.0.2:9100"), ("job", "job-x"), ("pod", "vmagent-0"), ("scrape_pool", "pool"))
    assert unhealthy_values[key] == 1
    assert len(collector.unhealthy_targets) == 2
    assert instances_reachable._value.get() == 1


async def test_unreachable_pod_zeroes_metrics_instead_of_crashing(monkeypatch):
    pod_a = make_pod("vmagent-0")
    monkeypatch.setattr(collector, "discover_pods", lambda: [pod_a])

    async def failing_poll_pod(client, pod):
        raise httpx.ConnectError("connection refused")
        yield  # pragma: no cover - makes this an async generator function

    monkeypatch.setattr(collector, "poll_pod", failing_poll_pod)

    await collector.collect_all()

    assert instances_reachable._value.get() == 0
    pod_values = metric_samples(targets_total)
    assert pod_values[(("pod", "vmagent-0"), ("state", "up"))] == 0
    assert pod_values[(("pod", "vmagent-0"), ("state", "down"))] == 0


async def test_ignore_lists_filter_independently(monkeypatch):
    pod_a = make_pod("vmagent-0")
    monkeypatch.setattr(collector, "discover_pods", lambda: [pod_a])
    monkeypatch.setattr(settings, "ignore_info_jobs", ["noisy-info"])
    monkeypatch.setattr(settings, "ignore_health_jobs", ["noisy-health"])

    monkeypatch.setattr(
        collector,
        "poll_pod",
        make_poll_pod(
            {
                "vmagent-0": [
                    target("noisy-info", "10.0.0.1:9100", "down"),
                    target("noisy-health", "10.0.0.2:9100", "down"),
                    target("normal", "10.0.0.3:9100", "down"),
                ]
            }
        ),
    )

    await collector.collect_all()

    job_values = metric_samples(job_targets_total)
    # noisy-info is still counted in target-count metrics ...
    assert job_values[(("job", "noisy-info"), ("state", "down"))] == 1
    # ... but excluded from the unhealthy-target detail metric
    unhealthy_values = metric_samples(unhealthy_target_info)
    assert not any(("job", "noisy-info") in k for k in unhealthy_values)

    # noisy-health is excluded from target-count metrics entirely
    assert (("job", "noisy-health"), ("state", "down")) not in job_values
    assert job_values[(("job", "normal"), ("state", "down"))] == 1


async def test_stale_pod_metrics_are_removed_not_zeroed(monkeypatch):
    """Regression test: pods that vanish from discovery (e.g. scale-down)
    must have their metrics removed, not just left frozen at their last
    value forever."""
    pods = [make_pod("vmagent-0"), make_pod("vmagent-1")]
    monkeypatch.setattr(collector, "discover_pods", lambda: pods)
    monkeypatch.setattr(
        collector,
        "poll_pod",
        make_poll_pod(
            {
                "vmagent-0": [target("job-x", "10.0.0.1:9100", "down")],
                "vmagent-1": [target("job-x", "10.0.0.2:9100", "down")],
            }
        ),
    )
    await collector.collect_all()
    assert (("pod", "vmagent-1"), ("state", "down")) in metric_samples(targets_total)

    pods.pop()  # vmagent-1 disappears from discovery
    await collector.collect_all()

    remaining = metric_samples(targets_total)
    assert (("pod", "vmagent-1"), ("state", "down")) not in remaining
    assert (("pod", "vmagent-1"), ("state", "up")) not in remaining


async def test_recovered_target_is_removed_not_zeroed(monkeypatch):
    """Regression test: unhealthy_target_info must .remove() recovered
    targets instead of .set(0), or every instance ever seen as unhealthy
    stays in the registry forever."""
    pod_a = make_pod("vmagent-0")
    monkeypatch.setattr(collector, "discover_pods", lambda: [pod_a])

    pods_targets = {"vmagent-0": [target("job-x", "10.0.0.1:9100", "down")]}
    monkeypatch.setattr(collector, "poll_pod", make_poll_pod(pods_targets))
    await collector.collect_all()

    key = (("instance", "10.0.0.1:9100"), ("job", "job-x"), ("pod", "vmagent-0"), ("scrape_pool", "pool"))
    assert metric_samples(unhealthy_target_info)[key] == 1

    pods_targets["vmagent-0"] = [target("job-x", "10.0.0.1:9100", "up")]
    await collector.collect_all()

    assert key not in metric_samples(unhealthy_target_info)


async def test_poll_status_records_reachability_per_pod(monkeypatch):
    pod_a, pod_b = make_pod("vmagent-0"), make_pod("vmagent-1")
    monkeypatch.setattr(collector, "discover_pods", lambda: [pod_a, pod_b])

    async def poll_pod(client, pod):
        if pod.name == "vmagent-1":
            raise httpx.ConnectError("connection refused")
        for t in [target("job-x", "10.0.0.1:9100", "up"), target("job-x", "10.0.0.2:9100", "down")]:
            yield t

    monkeypatch.setattr(collector, "poll_pod", poll_pod)

    await collector.collect_all()

    assert collector.poll_status["last_poll"] is not None
    assert collector.poll_status["pods"]["vmagent-0"] == {
        "reachable": True,
        "error": None,
        "up": 1,
        "down": 1,
        "unknown": 0,
    }
    assert collector.poll_status["pods"]["vmagent-1"] == {"reachable": False, "error": "connection refused"}
