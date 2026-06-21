import logging
from collections import defaultdict
from dataclasses import dataclass

import httpx

from .config import settings
from .discovery import VmagentPod, discover_pods
from .metrics import (
    instances_configured,
    instances_reachable,
    targets_total,
    unhealthy_target_info,
)

logger = logging.getLogger(__name__)


@dataclass
class UnhealthyTarget:
    pod: str
    scrape_pool: str
    job: str
    instance: str
    error: str
    health: str


# shared state read by /summary
unhealthy_targets: list[UnhealthyTarget] = []


async def poll_pod(client: httpx.AsyncClient, pod: VmagentPod) -> dict | None:
    try:
        r = await client.get(pod.targets_url, timeout=settings.vmagent_timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.warning("failed to poll %s: %s", pod.name, e)
        return None


def _clear_pod_metrics(pod_name: str) -> None:
    for state in ("up", "down", "unknown"):
        targets_total.labels(pod=pod_name, state=state).set(0)


_known_unhealthy: dict[str, set[tuple]] = defaultdict(set)


async def collect_all() -> None:
    global unhealthy_targets

    pods = discover_pods()
    instances_configured.set(len(pods))

    reachable = 0
    all_unhealthy: list[UnhealthyTarget] = []

    async with httpx.AsyncClient() as client:
        for pod in pods:
            data = await poll_pod(client, pod)
            if data is None:
                _clear_pod_metrics(pod.name)
                continue

            reachable += 1
            active = data.get("data", {}).get("activeTargets", [])

            counts: dict[str, int] = defaultdict(int)
            current_unhealthy: set[tuple] = set()

            for t in active:
                health = t.get("health", "unknown")
                counts[health] += 1

                if health != "up":
                    labels_map = t.get("labels", {})
                    key = (
                        pod.name,
                        t.get("scrapePool", ""),
                        labels_map.get("job", ""),
                        labels_map.get("instance", ""),
                    )
                    current_unhealthy.add(key)
                    unhealthy_target_info.labels(
                        pod=key[0],
                        scrape_pool=key[1],
                        job=key[2],
                        instance=key[3],
                    ).set(1)
                    all_unhealthy.append(UnhealthyTarget(
                        pod=key[0],
                        scrape_pool=key[1],
                        job=key[2],
                        instance=key[3],
                        error=t.get("lastError", ""),
                        health=health,
                    ))

            for state in ("up", "down", "unknown"):
                targets_total.labels(pod=pod.name, state=state).set(counts[state])

            for stale in _known_unhealthy[pod.name] - current_unhealthy:
                unhealthy_target_info.labels(
                    pod=stale[0],
                    scrape_pool=stale[1],
                    job=stale[2],
                    instance=stale[3],
                ).set(0)

            _known_unhealthy[pod.name] = current_unhealthy

    instances_reachable.set(reachable)
    unhealthy_targets = all_unhealthy
