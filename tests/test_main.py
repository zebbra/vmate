import httpx
import pytest

from app import main
from app.collector import UnhealthyTarget, unhealthy_targets


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_healthz(client):
    r = await client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_config_endpoint_reflects_settings(client):
    r = await client.get("/config")
    assert r.status_code == 200
    body = r.json()
    assert body["namespace"] == main.settings.namespace
    assert body["poll_interval"] == main.settings.poll_interval


async def test_unhealthy_endpoint_parses_errors_by_default(client):
    unhealthy_targets.clear()
    unhealthy_targets.append(
        UnhealthyTarget(
            pod="vmagent-0",
            scrape_pool="pool",
            job="job-x",
            instance="10.0.0.1:9100",
            error='unexpected status code returned when scraping "http://10.0.0.1:9100/metrics": '
            '503; expecting 200; response body: "service unavailable"',
            health="down",
        )
    )

    r = await client.get("/unhealthy")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 1
    assert body["targets"][0]["error"] == "service unavailable"
    assert body["targets"][0]["error_code"] == 503


async def test_unhealthy_endpoint_raw_skips_parsing(client):
    unhealthy_targets.clear()
    unhealthy_targets.append(
        UnhealthyTarget(
            pod="vmagent-0",
            scrape_pool="pool",
            job="job-x",
            instance="10.0.0.1:9100",
            error="some raw unparsed error",
            health="down",
        )
    )

    r = await client.get("/unhealthy?raw=true")
    body = r.json()
    assert body["targets"][0]["error"] == "some raw unparsed error"
    assert "error_code" not in body["targets"][0]


async def test_job_unhealthy_filters_by_job(client):
    unhealthy_targets.clear()
    unhealthy_targets.append(
        UnhealthyTarget(pod="vmagent-0", scrape_pool="pool", job="job-x", instance="i1", error="", health="down")
    )
    unhealthy_targets.append(
        UnhealthyTarget(pod="vmagent-0", scrape_pool="pool", job="job-y", instance="i2", error="", health="down")
    )

    r = await client.get("/job/job-x/unhealthy")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 1
    assert body["targets"][0]["job"] == "job-x"


async def test_job_unhealthy_404_for_unknown_job(client):
    unhealthy_targets.clear()
    r = await client.get("/job/nonexistent/unhealthy")
    assert r.status_code == 404
