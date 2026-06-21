import asyncio
import logging

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from .collector import collect_all, unhealthy_targets
from .config import settings
from .discovery import discover_pods, load_k8s_config
from .errors import parse_error

logging.basicConfig(level=logging.INFO)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

app = FastAPI(title="vmate")


@app.on_event("startup")
async def startup() -> None:
    load_k8s_config()
    pods = discover_pods()
    logger.info(
        "starting: label_selector=%r namespace=%r discovered %d pod(s): %s",
        settings.label_selector,
        settings.namespace,
        len(pods),
        [p.name for p in pods],
    )
    asyncio.create_task(_poll_loop())


async def _poll_loop() -> None:
    while True:
        try:
            await collect_all()
        except Exception:
            logger.exception("collect_all failed")
        await asyncio.sleep(settings.poll_interval)


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    return HTMLResponse("""
<html><head><title>vmate</title></head>
<body>
<h2>vmate — Victoria Metrics Agent Target Exporter</h2>
<ul>
  <li><a href="/unhealthy">/unhealthy</a> — all unhealthy targets across all pods</li>
  <li><a href="/pod/{pod}/unhealthy">/pod/{pod}/unhealthy</a> — unhealthy targets for a specific pod</li>
  <li><a href="/job/{job}/unhealthy">/job/{job}/unhealthy</a> — unhealthy targets for a specific job</li>
  <li><a href="/summary">/summary</a> — discovered pods and config</li>
  <li><a href="/metrics">/metrics</a> — Prometheus metrics</li>
  <li><a href="/healthz">/healthz</a> — health check</li>
</ul>
</body></html>
""")


@app.get("/unhealthy")
async def all_unhealthy(raw: bool = False) -> dict:
    return {
        "count": len(unhealthy_targets),
        "targets": [_target_dict(t, raw) for t in unhealthy_targets],
    }


@app.get("/pod/{pod}/unhealthy")
async def pod_unhealthy(pod: str, raw: bool = False) -> dict:
    pods = discover_pods()
    if pod not in {p.name for p in pods}:
        raise HTTPException(status_code=404, detail=f"pod {pod!r} not found")
    targets = [t for t in unhealthy_targets if t.pod == pod]
    return {
        "pod": pod,
        "count": len(targets),
        "targets": [_target_dict(t, raw) for t in targets],
    }


@app.get("/job/{job}/unhealthy")
async def job_unhealthy(job: str, raw: bool = False) -> dict:
    targets = [t for t in unhealthy_targets if t.job == job]
    if not targets:
        if job not in {t.job for t in unhealthy_targets}:
            raise HTTPException(status_code=404, detail=f"job {job!r} not found or has no unhealthy targets")
    return {
        "job": job,
        "count": len(targets),
        "targets": [_target_dict(t, raw) for t in targets],
    }


@app.get("/summary")
async def summary() -> dict:
    pods = discover_pods()
    return {
        "namespace": settings.namespace,
        "label_selector": settings.label_selector,
        "poll_interval": settings.poll_interval,
        "configured_pods": [p.name for p in pods],
        "ignore_info_jobs": settings.ignore_info_jobs,
        "ignore_health_jobs": settings.ignore_health_jobs,
    }


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics() -> PlainTextResponse:
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


def _target_dict(t, raw: bool = False) -> dict:
    base = {
        "pod": t.pod,
        "scrape_pool": t.scrape_pool,
        "job": t.job,
        "instance": t.instance,
        "health": t.health,
    }
    if raw:
        base["error"] = t.error
    else:
        base.update(parse_error(t.error))
    return base
