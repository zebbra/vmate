from app.errors import parse_error


def test_plain_message_passes_through():
    result = parse_error("connection refused")
    assert result == {"error": "connection refused", "target_url": None, "error_code": None}


def test_http_status_error_extracts_code_url_and_body():
    error = (
        'unexpected status code returned when scraping "http://10.0.0.1:9100/metrics": '
        '503; expecting 200; response body: "service unavailable"'
    )
    result = parse_error(error)
    assert result == {
        "error": "service unavailable",
        "target_url": "http://10.0.0.1:9100/metrics",
        "error_code": 503,
    }


def test_http_status_error_strips_vm_banner_and_keeps_last_line():
    error = (
        'unexpected status code returned when scraping "http://10.0.0.1:9100/metrics": '
        "500; expecting 200; response body: "
        '"An error has occurred while serving metrics:\\n\\nboom"'
    )
    result = parse_error(error)
    assert result["error_code"] == 500
    assert result["error"] == "boom"


def test_request_failure_extracts_url_and_go_error():
    error = (
        'cannot perform request to "http://10.0.0.5:9100/metrics": '
        'Get "http://10.0.0.5:9100/metrics": dial tcp 10.0.0.5:9100: '
        "connect: connection refused"
    )
    result = parse_error(error)
    assert result["target_url"] == "http://10.0.0.5:9100/metrics"
    assert result["error_code"] is None
    assert result["error"] == "dial tcp 10.0.0.5:9100: connect: connection refused"
