import hashlib
import re
from pathlib import Path

from fastapi.testclient import TestClient

from cairn.app import create_app
from cairn.ingest import DEFAULT_DB, ingest
from cairn.web import HERE


def test_healthz_and_landing_page() -> None:
    with TestClient(create_app()) as client:
        assert client.get("/healthz").status_code == 200
        page = client.get("/").text
    for badge in ("REAL", "RECORDED", "SIMULATED"):
        assert f'class="badge {badge.lower()}"' in page
    assert "Public sample data · fictional compound · not GxP-validated" in page
    assert "Role: Study toxicologist (simulated)" in page
    assert re.search(r"v0\.1\.0 · commit \S+ · snapshot [0-9a-f]{12}", page)
    assert page.count('class="locked"') == 6
    assert 'href="/step/2"' not in page
    assert "/static/vendor/htmx.min.js" in page


def test_static_htmx_is_the_pinned_file() -> None:
    notice = (HERE / "static" / "vendor" / "htmx.NOTICE.txt").read_text()
    with TestClient(create_app()) as client:
        body = client.get("/static/vendor/htmx.min.js").content
    assert hashlib.sha256(body).hexdigest() in notice


def test_step1_run_shows_quarantine_and_computed_means() -> None:
    with TestClient(create_app()) as client:
        assert "In production" in client.get("/step/1").text
        assert 'class="badge simulated"' in client.get("/step/1").text
        result = client.post("/step/1/run").text
    assert "<strong>12</strong> quarantined" in result
    assert result.count("pp_auc_positive") == 12
    assert "2,821 with the bad value (n=3)" in result
    assert "15,956 without it (n=2)" in result


def test_inject_switch_fires_rule_without_touching_duckdb(tmp_path: Path) -> None:
    db = tmp_path / "cairn.duckdb"
    ingest(db_path=db)
    watched = [db] + ([DEFAULT_DB] if DEFAULT_DB.exists() else [])
    before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in watched]
    with TestClient(create_app()) as client:
        result = client.post("/step/1/run", data={"inject": "on"}).text
        plain = client.post("/step/1/run").text
    assert "<strong>13</strong> quarantined, including the injected row" in result
    assert 'class="new"' in result
    assert "pc_concentration_positive" in result
    assert "pc_concentration_positive" not in plain
    assert "<strong>12</strong>" in plain
    assert [hashlib.sha256(p.read_bytes()).hexdigest() for p in watched] == before


def test_templates_hold_no_literal_means() -> None:
    pattern = re.compile(r"2,?821|2,?820|15,?956")
    for template in (HERE / "templates").glob("*.html"):
        assert not pattern.search(template.read_text(encoding="utf-8")), template.name
