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
THREAD_COOKIE = "cairn_thread"
# The checks below read English strings, and the pages default to Spanish.
# The thread follows the visitor by cookie, so the jar keeps what Set-Cookie sends.
JAR = {COOKIE: "en"}


def _headers() -> dict[str, str]:
    return {"Cookie": "; ".join(f"{name}={value}" for name, value in JAR.items())}


def _remember(response: object) -> None:
    for line in response.headers.get_all("Set-Cookie") or []:  # type: ignore[attr-defined]
        name, _, rest = line.partition("=")
        JAR[name.strip()] = rest.partition(";")[0]


def get(path: str) -> tuple[int, bytes]:
    try:
        with http.urlopen(http.Request(BASE + path, headers=_headers())) as response:
            _remember(response)
            return response.status, response.read()
    except HTTPError as error:  # urllib raises on 4xx/5xx; the check reports it as a failure
        return error.code, error.read()


def post(path: str, fields: dict[str, str]) -> str:
    """The page the POST ends on: urllib follows the 303 to a GET by itself."""
    with http.urlopen(
        http.Request(BASE + path, data=urlencode(fields).encode(), headers=_headers())
    ) as response:
        _remember(response)
        return str(response.read().decode())


def _calibration() -> str:
    """The n and kappa step 5 must show; empty when the image lacks the result file."""
    if not KAPPA_PATH.is_file():
        return ""
    result = json.loads(KAPPA_PATH.read_text(encoding="utf-8"))
    return f"n={result['n']} | kappa {result['kappa']:.2f}"


def _judged(page: str) -> bool:
    """The draft says "N/N sentences judged" with N above zero."""
    text = re.sub(r"<[^>]+>", " ", page)
    found = re.search(r"(\d+)/(\d+)\s+sentences judged", text)
    return found is not None and found.group(1) == found.group(2) and int(found.group(1)) > 0


def people_decide() -> bool:
    """Decide and draft end to end: example, confirm, author refused, reviewer approves."""
    page = get("/decide")[1].decode()
    if THREAD_COOKIE not in JAR or CATALOGUES["en"]["s4_example"] not in page:
        print("decide screen has no thread cookie or no example button")
        return False
    calibration = _calibration()
    post("/decide/example", {})
    final = post("/decide/confirm", {"actor": "R. Reviewer"})
    refused = post("/draft/approve", {"actor": "A. Author"})
    approved = post("/draft/approve", {"actor": "R. Reviewer"})
    draft = get("/draft")[1].decode()
    checks = {
        "step 5 has the final text": any(c["disc_final_text"] in final for c in CATALOGUES.values())
        and "RECORDED" in final,
        "step 5 has the judge panel": CATALOGUES["en"]["s5_judge_h"] in final,
        "step 5 panel shows the recorded n and kappa": bool(calibration) and calibration in final,
        "step 5 judged every sentence": _judged(final),
        "draft has the chain": "Verified." in draft and "chained entries" in draft,
        "draft has the session and the same hash over MCP and REST": (
            CATALOGUES["en"]["s7_by_model"].format(n=0) in draft
            and CATALOGUES["en"]["s7_tile_numbers"] in draft
            and CATALOGUES["en"]["s7_same"] in draft
            and CATALOGUES["en"]["s7_differ"] not in draft
            and CATALOGUES["en"]["s7_chain_value"].format(n="", state="verified").strip() in draft
        ),
        "author refused with 403": "403 · Authors cannot approve their own draft" in refused,
        "reviewer approves": "Approved by R. Reviewer" in approved,
    }
    for name, ok in checks.items():
        print("decide-draft:", name, "ok" if ok else "FAILED")
    return all(checks.values())


def main() -> int:
    server = subprocess.Popen(["uvicorn", "cairn.app:create_app", "--factory", "--port", "8000"])
    try:
        for _ in range(120):
            if socket.socket().connect_ex(("127.0.0.1", 8000)) == 0:
                break
            time.sleep(1)
        failed = False
        for path in ("/", "/study", "/ask", "/decide", "/draft", "/healthz"):
            status = get(path)[0]
            print(path, status)
            failed = failed or status != 200
        if failed:
            print("a route did not answer 200")
            return 1
        with http.urlopen(http.Request(BASE + "/ask/run", data=b"question=G2")) as response:
            answer = response.read()
        link = re.search(rb'href="(/highlight/[^"]+)"', answer)
        if link is None:
            print("the G2 answer has no highlighted page link")
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
        request = http.Request(BASE + "/ask/run", data=b"question=Q2")
        with http.urlopen(request) as response:
            body = response.read()
            ok = response.status == 200 and b"RECORDED" in body
            print("POST /ask/run", response.status, "RECORDED" if ok else "missing RECORDED")
        return 0 if ok and people_decide() else 1
    finally:
        server.terminate()


if __name__ == "__main__":
    sys.exit(main())
