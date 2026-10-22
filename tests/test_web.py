import hashlib
import json
import re
from pathlib import Path

import pytest
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
    assert page.count('class="locked"') == 5
    assert 'href="/step/2"' in page
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


def test_footer_uses_baked_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAIRN_COMMIT", "abc1234")
    with TestClient(create_app()) as client:
        page = client.get("/").text
    assert "commit abc1234" in page


FIXTURES = Path(__file__).parent / "fixtures" / "recordings"


def _ask(question: str, monkeypatch: pytest.MonkeyPatch, folder: Path = FIXTURES) -> str:
    monkeypatch.setenv("CAIRN_RECORDINGS", str(folder))
    with TestClient(create_app()) as client:
        return client.post("/step/2/run", data={"question": question}).text


def test_step2_page_lists_the_questions_with_the_recorded_badge() -> None:
    with TestClient(create_app()) as client:
        page = client.get("/step/2").text
    assert 'class="badge recorded"' in page
    assert "In production" in page
    assert 'value="Q2"' in page and 'value="Q6"' in page


REAL = Path(__file__).parent.parent / "recordings"


def test_q2_replay(monkeypatch: pytest.MonkeyPatch) -> None:
    """Offline replay of the real Opus 4.6 recording: 9-row screen, honest denominators."""
    result = _ask("Q2", monkeypatch, REAL)
    assert 'class="badge recorded"' in result
    assert "Rules fired: none" in result
    assert result.count("<tr><td>") == 9
    assert "not examined" in result and "0/1" in result
    assert "9 screened findings; the clearest is GLAND, ADRENAL Vacuolization in F and M" in result
    recorded = json.loads((REAL / "q2.json").read_text(encoding="utf-8"))
    cost = sum(call["cost_usd"] for call in recorded["calls"])
    assert f"{recorded['date']} | {recorded['region']} | opus-4-6 |" in result
    assert re.search(r"\| [1-9]\d*\.\d s \|", result)
    assert f"| {cost:.2f} USD" in result
    assert "Screen: a finding enters" in result


def test_q2_replay_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _ask("Q2", monkeypatch)
    assert "run_job -&gt; study_design -&gt; incidence" in result
    assert 'class="badge fixture"' in result
    assert "cost n/a" in result
    assert "Screen: a finding enters" in result
    assert result.count("<tr><td>") == 9
    assert "not examined" in result
    assert "The screen examined 80 animals" in result
    assert "Rules fired: none" in result
    assert "incidence, main study" in result and "n=80" in result


@pytest.mark.parametrize(("folder", "marker"), [(FIXTURES, "[n_examined]"), (REAL, "[finding]")])
def test_step2_toggle_shows_markers_and_no_digits(
    monkeypatch: pytest.MonkeyPatch, folder: Path, marker: str
) -> None:
    result = _ask("Q2", monkeypatch, folder)
    toggle = re.search(r"<details>.*?</details>", result, flags=re.S)
    assert toggle is not None
    assert "What the model wrote" in toggle.group(0)
    assert marker in toggle.group(0)
    assert not re.search(r"\d", toggle.group(0))


def test_q6_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    """Deviation D3: the real Q6 recording ends declined, which counts as correct."""
    result = _ask("Q6", monkeypatch, REAL)
    assert "the model declined" in result
    assert "<tr><td>" not in result and "<strong>" not in result


def test_q6_blocked_by_rules_on_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _ask("Q6", monkeypatch)
    assert "Rules fired: 1, 6" in result
    assert "Rule 1" in result and "Rule 6" in result
    assert "<strong>" not in result
    assert "<tr><td>" not in result


def _callout_classes(html: str) -> list[str]:
    return re.findall(r'class="callout (\w+)"', html)


@pytest.mark.parametrize("folder", [FIXTURES, REAL])
def test_q6_callout_is_blocked_and_q2_is_not(monkeypatch: pytest.MonkeyPatch, folder: Path) -> None:
    assert "blocked" in _callout_classes(_ask("Q6", monkeypatch, folder))
    assert "blocked" not in _callout_classes(_ask("Q2", monkeypatch, folder))


def test_step2_missing_recording_shows_the_stale_message(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    result = _ask("Q2", monkeypatch, tmp_path)
    assert "stale recording: run make record" in result
    assert "<table>" not in result


def test_step2_always_replays_whatever_the_mode_says(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAIRN_LLM_MODE", "live")
    assert "The screen examined 80 animals" in _ask("Q2", monkeypatch)


def test_step2_rejects_an_unknown_question(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAIRN_RECORDINGS", str(FIXTURES))
    with TestClient(create_app()) as client:
        assert client.post("/step/2/run", data={"question": "Q9"}).status_code == 422


def test_q2_evidence_counts_distinct_animals_not_source_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _ask("Q2", monkeypatch, REAL)
    assert "37 affected, from " in result
    assert "69 animals" not in result


def test_q2_sentence_and_evidence_state_the_same_examined_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sentence and evidence n are one field of one observation; the other count is labelled."""
    result = _ask("Q2", monkeypatch, FIXTURES)  # the real prose no longer states a count
    sentence = re.search(r"examined (?:a total of )?(\d+) animals", result)
    evidence = re.search(r"incidence, [^<]*?, n=(\d+), (\d+) (\w+), from ", result)
    assert sentence and evidence
    assert sentence.group(1) == evidence.group(1)
    assert evidence.group(3) == "affected"


def test_step2_header_badge_follows_the_recordings_served(monkeypatch: pytest.MonkeyPatch) -> None:
    for folder, shown, hidden in ((FIXTURES, "fixture", "recorded"), (REAL, "recorded", "fixture")):
        monkeypatch.setenv("CAIRN_RECORDINGS", str(folder))
        with TestClient(create_app()) as client:
            page = client.get("/step/2").text
        assert f'class="badge {shown}"' in page and f'class="badge {hidden}"' not in page


def test_step2_badge_ignores_unreadable_files_and_empty_folders(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "list.json").write_text("[]", encoding="utf-8")
    (tmp_path / "bad.json").write_text("{not json", encoding="utf-8")
    for folder in (tmp_path, tmp_path / "missing"):
        monkeypatch.setenv("CAIRN_RECORDINGS", str(folder))
        with TestClient(create_app()) as client:
            response = client.get("/step/2")
        assert response.status_code == 200
        page = response.text
        assert 'class="badge none"' in page and 'class="badge recorded"' not in page


def test_q2_prose_names_the_screened_findings_by_sex_and_places_no_table_position(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The prose answers the question: a finding that passes the screen, with its sexes."""
    from cairn.incidence import incidence

    result = _ask("Q2", monkeypatch, REAL)
    prose = re.search(r'<div class="card answer"><p><strong>(.*?)</strong></p>', result, re.S)
    assert prose, "no rendered answer"
    text = prose.group(1)
    findings = incidence().values["findings"]
    named = [f for f in findings if f["tissue"] in text and f["finding"] in text]
    assert named, f"the prose names no finding that passes the screen: {text!r}"
    for finding in named:
        sexes = {
            f["sex"]
            for f in findings
            if (f["tissue"], f["finding"]) == (finding["tissue"], finding["finding"])
        }
        assert all(re.search(rf"\b{sex}\b", text) for sex in sexes), text
    assert not re.search(r"\b(above|below)\b", text)


def test_q2_prose_counts_the_screened_findings_by_reference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The count is a reference to the code's own count and matches the rows of the table."""
    from cairn.incidence import incidence

    result = _ask("Q2", monkeypatch, REAL)
    text = re.search(r'<div class="card answer"><p><strong>(.*?)</strong>', result, re.S).group(1)  # type: ignore[union-attr]
    rows = result.count("<tr><td>")
    assert re.match(rf"{rows} screened findings", text), text
    assert rows == incidence().values["n_findings"]
    toggle = re.search(r"<details>.*?</details>", result, flags=re.S)
    assert toggle and "[n_findings]" in toggle.group(0) and not re.search(r"\d", toggle.group(0))
