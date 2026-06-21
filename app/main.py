import asyncio
import logging

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from .collector import collect_all, unhealthy_targets
from .config import settings
from .discovery import discover_pods, load_k8s_config

logging.basicConfig(level=logging.INFO)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

app = FastAPI(title="vmagent-target-exporter")


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
<html><head><title>vmagent-target-exporter</title></head>
<body>
<h2>vmagent-target-exporter</h2>
<ul>
  <li><a href="/unhealthy">/unhealthy</a> — all unhealthy targets across all pods</li>
  <li><a href="/summary">/summary</a> — discovered pods and config</li>
  <li><a href="/metrics">/metrics</a> — Prometheus metrics</li>
  <li><a href="/healthz">/healthz</a> — health check</li>
</ul>
<p><em>Per-pod: /{pod}/unhealthy</em></p>
</body></html>
""")


@app.get("/unhealthy")
async def all_unhealthy() -> dict:
    return {
        "count": len(unhealthy_targets),
        "targets": [_target_dict(t) for t in unhealthy_targets],
    }


@app.get("/{pod}/unhealthy")
async def pod_unhealthy(pod: str) -> dict:
    targets = [t for t in unhealthy_targets if t.pod == pod]
    if not targets and pod not in {t.pod for t in unhealthy_targets}:
        pods = discover_pods()
        if pod not in {p.name for p in pods}:
            raise HTTPException(status_code=404, detail=f"pod {pod!r} not found")
    return {
        "pod": pod,
        "count": len(targets),
        "targets": [_target_dict(t) for t in targets],
    }


@app.get("/summary")
async def summary() -> dict:
    pods = discover_pods()
    return {
        "namespace": settings.namespace,
        "label_selector": settings.label_selector,
        "poll_interval": settings.poll_interval,
        "configured_pods": [p.name for p in pods],
    }


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics() -> PlainTextResponse:
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


def _target_dict(t) -> dict:
    return {
        "pod": t.pod,
        "scrape_pool": t.scrape_pool,
        "job": t.job,
        "instance": t.instance,
        "health": t.health,
        "error": t.error,
    }
