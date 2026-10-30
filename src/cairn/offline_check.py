"""Offline smoke check run inside the container with no network (make demo-offline-check)."""

from __future__ import annotations

import json
import re
import socket
import subprocess
import sys
import time
import urllib.request as http
from urllib.error import HTTPError
from urllib.parse import urlencode

from cairn.judge import KAPPA_PATH
from cairn.web.i18n import CATALOGUES, COOKIE

BASE = "http://127.0.0.1:8000"
# The checks below read English strings, and the pages default to Spanish.
ENGLISH = {"Cookie": f"{COOKIE}=en"}


def get(path: str) -> tuple[int, bytes]:
    try:
        with http.urlopen(http.Request(BASE + path, headers=ENGLISH)) as response:
            return response.status, response.read()
    except HTTPError as error:  # urllib raises on 4xx/5xx; the check reports it as a failure
        return error.code, error.read()


def post(path: str, fields: dict[str, str]) -> str:
    with http.urlopen(
        http.Request(BASE + path, data=urlencode(fields).encode(), headers=ENGLISH)
    ) as response:
        return str(response.read().decode())


def _calibration() -> str:
    """The n and kappa step 5 must show; empty when the image lacks the result file."""
    if not KAPPA_PATH.is_file():
        return ""
    result = json.loads(KAPPA_PATH.read_text(encoding="utf-8"))
    return f"n={result['n']} | kappa {result['kappa']:.2f}"


def _judged(page: str) -> bool:
    """Step 5 says "N/N sentences judged" with N above zero."""
    text = re.sub(r"<[^>]+>", " ", page)
    found = re.search(r"(\d+)/(\d+)\s+sentences judged", text)
    return found is not None and found.group(1) == found.group(2) and int(found.group(1)) > 0


def people_decide() -> bool:
    """Steps 4 to 7 end to end: example fill, confirm, author refused, reviewer approves, chain."""
    page = get("/step/4")[1].decode()
    found = re.search(r'name="thread" value="([0-9a-f]+)"', page)
    if found is None or CATALOGUES["en"]["s4_example"] not in page:
        print("step 4 has no thread or no example button")
        return False
    thread = found.group(1)
    calibration = _calibration()
    post("/step/4/example", {"thread": thread})
    final = post("/step/4/confirm", {"thread": thread, "actor": "R. Reviewer"})
    refused = post("/step/5/approve", {"thread": thread, "actor": "A. Author"})
    approved = post("/step/5/approve", {"thread": thread, "actor": "R. Reviewer"})
    step6 = get(f"/step/6?thread={thread}")[1].decode()
    step7 = get(f"/step/7?thread={thread}")[1].decode()
    checks = {
        "step 5 has the final text": any(c["disc_final_text"] in final for c in CATALOGUES.values())
        and "RECORDED" in final,
        "step 5 has the judge panel": "Judge panel" in final,
        "step 5 panel shows the recorded n and kappa": bool(calibration) and calibration in final,
        "step 5 judged every sentence": _judged(final),
        "step 6 has the chain": "Verified." in step6 and "chained entries" in step6,
        "step 7 has the session and the same hash over MCP and REST": (
            "0 by the model" in step7 and "Same hash, same Observation." in step7
        ),
        "author refused with 403": "403 · Authors cannot approve their own draft" in refused,
        "reviewer approves": "Approved by R. Reviewer" in approved,
    }
    for name, ok in checks.items():
        print("steps 4-7:", name, "ok" if ok else "FAILED")
    return all(checks.values())


def main() -> int:
    server = subprocess.Popen(["uvicorn", "cairn.app:create_app", "--factory", "--port", "8000"])
    try:
        for _ in range(120):
            if socket.socket().connect_ex(("127.0.0.1", 8000)) == 0:
                break
            time.sleep(1)
        failed = False
        for path in ("/", "/step/1", "/step/2", "/step/3", "/explore", "/healthz"):
            status = get(path)[0]
            print(path, status)
            failed = failed or status != 200
        if failed:
            print("a route did not answer 200")
            return 1
        _, step3 = get("/step/3")
        link = re.search(rb'href="(/highlight/[^"]+)"', step3)
        if link is None:
            print("step 3 has no highlighted page link")
            return 1
        status, page = get(link.group(1).decode())
        print(link.group(1).decode(), status)
        image = re.search(rb'src="(/highlights/[^"]+\.png)"', page)
        if image is None:
            print("highlight page has no PNG")
            return 1
        status, png = get(image.group(1).decode())
        print(image.group(1).decode(), status, (png[:4] == b"\x89PNG" and "PNG") or "not a PNG")
        if png[:4] != b"\x89PNG":
            return 1
        request = http.Request(BASE + "/step/2/run", data=b"question=Q2")
        with http.urlopen(request) as response:
            body = response.read()
            ok = response.status == 200 and b"RECORDED" in body
            print("POST /step/2/run", response.status, "RECORDED" if ok else "missing RECORDED")
        return 0 if ok and people_decide() else 1
    finally:
        server.terminate()


if __name__ == "__main__":
    sys.exit(main())
