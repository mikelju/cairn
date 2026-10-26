"""Offline smoke check run inside the container with no network (make demo-offline-check)."""

from __future__ import annotations

import re
import socket
import subprocess
import sys
import time
import urllib.request as http

BASE = "http://127.0.0.1:8000"


def get(path: str) -> tuple[int, bytes]:
    with http.urlopen(BASE + path) as response:
        return response.status, response.read()


def main() -> int:
    server = subprocess.Popen(["uvicorn", "cairn.app:create_app", "--factory", "--port", "8000"])
    try:
        for _ in range(120):
            if socket.socket().connect_ex(("127.0.0.1", 8000)) == 0:
                break
            time.sleep(1)
        for path in ("/", "/step/1", "/step/2", "/step/3", "/explore", "/healthz"):
            print(path, get(path)[0])
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
        return 0 if ok else 1
    finally:
        server.terminate()


if __name__ == "__main__":
    sys.exit(main())
