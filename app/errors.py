import re


def prettify(error: str) -> str:
    # HTTP error with response body
    m = re.search(
        r'unexpected status code.*?(\d{3}).*?response body: "(.+?)"?\s*$',
        error,
        re.DOTALL,
    )
    if m:
        status = m.group(1)
        body = m.group(2).replace("\\n", "\n").strip()
        body = re.sub(r"^An error has occurred while serving metrics:\s*\n+", "", body).strip()
        lines = [l.strip() for l in body.split("\n") if l.strip()]
        body = lines[-1] if lines else body
        # if still long, take after last ": "
        if len(body) > 80:
            body = body.rsplit(": ", 1)[-1]
        return f"HTTP {status}: {body}"

    # Go-style error with trailing (reason)
    m = re.search(r"\(([^()]+)\)\s*$", error)
    if m:
        return m.group(1)

    return error
