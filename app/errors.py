import re


def parse_error(error: str) -> dict:
    url = None
    code = None
    message = error

    # extract first URL
    url_match = re.search(r'"(https?://[^"]+)"', error)
    if url_match:
        url = url_match.group(1)

    # unexpected status code returned when scraping "URL": CODE; expecting NNN; response body: "BODY"
    http_match = re.match(
        r'unexpected status code returned when scraping "[^"]+": (\d{3}); expecting \d+; response body: "(.+?)"?\s*$',
        error,
        re.DOTALL,
    )
    if http_match:
        code = int(http_match.group(1))
        body = http_match.group(2).replace("\\n", "\n").strip()
        body = re.sub(
            r"^An error has occurred while serving metrics:\s*\n+", "", body
        ).strip()
        lines = [ln.strip() for ln in body.split("\n") if ln.strip()]
        message = lines[-1] if lines else body
        return {"error": message, "target_url": url, "error_code": code}

    # cannot perform request to "URL": Get "URL": <go error>
    req_match = re.match(
        r'cannot perform request to "[^"]+": .+?: (.+)$', error, re.DOTALL
    )
    if req_match:
        message = req_match.group(1).strip()
        return {"error": message, "target_url": url, "error_code": None}

    return {"error": message, "target_url": url, "error_code": None}
