"""The offline smoke check finds the highlighted page and its PNG the way the app renders them."""

from __future__ import annotations

import re

from fastapi.testclient import TestClient

from cairn.app import create_app


def test_offline_check_patterns_reach_a_highlight_page_and_png() -> None:
    with TestClient(create_app()) as client:
        link = re.search(rb'href="(/highlight/[^"]+)"', client.get("/step/3").content)
        assert link is not None
        page = client.get(link.group(1).decode())
        image = re.search(rb'src="(/highlights/[^"]+\.png)"', page.content)
        assert image is not None
        assert client.get(image.group(1).decode()).content.startswith(b"\x89PNG")
