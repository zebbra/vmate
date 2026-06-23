import logging
from collections import defaultdict
from dataclasses import dataclass

import httpx

from .config import settings
from .discovery import VmagentPod, discover_pods
from .metrics import (
    instances_configured,
    instances_reachable,
    job_targets_total,
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


# shared state read by API endpoints — mutated in place to avoid import-reference issues
unhealthy_targets: list[UnhealthyTarget] = []

_known_unhealthy: dict[str, set[tuple]] = defaultdict(set)
_known_job_states: set[tuple] = set()


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


async def collect_all() -> None:
    pods = discover_pods()
    instances_configured.set(len(pods))

    reachable = 0
    all_unhealthy: list[UnhealthyTarget] = []
    job_counts: dict[tuple[str, str], int] = defaultdict(int)  # (job, state) -> count

    async with httpx.AsyncClient() as client:
        for pod in pods:
            data = await poll_pod(client, pod)
            if data is None:
                _clear_pod_metrics(pod.name)
                continue

            reachable += 1
            active = data.get("data", {}).get("activeTargets", [])

            pod_counts: dict[str, int] = defaultdict(int)
            current_unhealthy: set[tuple] = set()

            for t in active:
                health = t.get("health", "unknown")
                labels_map = t.get("labels", {})
                job = labels_map.get("job", "")

                if job not in settings.ignore_health_jobs:
                    pod_counts[health] += 1
                    job_counts[(job, health)] += 1

                if health != "up":
                    key = (
                        pod.name,
                        t.get("scrapePool", ""),
                        job,
                        labels_map.get("instance", ""),
                    )
                    all_unhealthy.append(
                        UnhealthyTarget(
                            pod=key[0],
                            scrape_pool=key[1],
                            job=key[2],
                            instance=key[3],
                            error=t.get("lastError", ""),
                            health=health,
                        )
                    )
                    if job not in settings.ignore_info_jobs:
                        current_unhealthy.add(key)
                        unhealthy_target_info.labels(
                            pod=key[0],
                            scrape_pool=key[1],
                            job=key[2],
                            instance=key[3],
                        ).set(1)

            for state in ("up", "down", "unknown"):
                targets_total.labels(pod=pod.name, state=state).set(pod_counts[state])

            for stale in _known_unhealthy[pod.name] - current_unhealthy:
                unhealthy_target_info.labels(
                    pod=stale[0],
                    scrape_pool=stale[1],
                    job=stale[2],
                    instance=stale[3],
                ).set(0)

            _known_unhealthy[pod.name] = current_unhealthy

    # update job_targets_total, zero out stale job/state combos
    global _known_job_states
    current_job_states: set[tuple] = set()
    for (job, state), count in job_counts.items():
        job_targets_total.labels(job=job, state=state).set(count)
        current_job_states.add((job, state))
    for stale in _known_job_states - current_job_states:
        job_targets_total.labels(job=stale[0], state=stale[1]).set(0)
    _known_job_states = current_job_states

    instances_reachable.set(reachable)
    unhealthy_targets.clear()
    unhealthy_targets.extend(all_unhealthy)

    total_up = sum(c for (_, state), c in job_counts.items() if state == "up")
    total_down = sum(c for (_, state), c in job_counts.items() if state == "down")
    log = logger.warning if reachable != len(pods) else logger.info
    log(
        "poll done: %d/%d pods reachable, %d up, %d down, %d unhealthy targets",
        reachable,
        len(pods),
        total_up,
        total_down,
        len(all_unhealthy),
    )
