import asyncio
import logging

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from .collector import collect_all, unhealthy_targets
from .config import settings
from .discovery import discover_pods, load_k8s_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="vmagent-target-exporter")


@app.on_event("startup")
async def startup() -> None:
    load_k8s_config()
    asyncio.create_task(_poll_loop())


async def _poll_loop() -> None:
    while True:
        try:
            await collect_all()
        except Exception:
            logger.exception("collect_all failed")
        await asyncio.sleep(settings.poll_interval)


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics() -> PlainTextResponse:
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/summary")
async def summary() -> dict:
    pods = discover_pods()
    return {
        "configured_pods": [p.name for p in pods],
        "label_selector": settings.label_selector,
        "namespace": settings.namespace,
        "unhealthy_targets": [
            {
                "pod": t.pod,
                "scrape_pool": t.scrape_pool,
                "job": t.job,
                "instance": t.instance,
                "health": t.health,
                "error": t.error,
            }
            for t in unhealthy_targets
        ],
    }


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}
