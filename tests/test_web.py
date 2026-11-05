import hashlib
import importlib
import json
import re
import shutil
import sqlite3
from html import unescape
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from cairn import app as app_module
from cairn.app import create_app
from cairn.decisions import finding_key
from cairn.fetch import VENDORED_DIR
from cairn.ingest import DEFAULT_DB, ingest
from cairn.web import HERE, i18n
from cairn.web.i18n import COOKIE
from screens import LANGS, STATE_MARKERS, main_copy, rendered_state


def test_healthz_and_landing_page() -> None:
    with TestClient(create_app()) as client:
        assert client.get("/healthz").status_code == 200
        page = client.get("/?lang=en").text
    assert "Public sample data · fictional compound · not GxP-validated" in page
    assert "Role: Study toxicologist (simulated)" in page
    assert re.search(r"v0\.1\.0 · commit \S+ · snapshot [0-9a-f]{12}", page)
    assert page.count('class="locked"') == 0
    assert 'href="/study"' in page
    assert "/static/vendor/htmx.min.js" in page


def test_static_htmx_is_the_pinned_file() -> None:
    notice = (HERE / "static" / "vendor" / "htmx.NOTICE.txt").read_text()
    with TestClient(create_app()) as client:
        body = client.get("/static/vendor/htmx.min.js").content
    assert hashlib.sha256(body).hexdigest() in notice


def _english(client: TestClient) -> TestClient:
    client.cookies.set(COOKIE, "en")
    return client


def _text(html: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", html).split())


def _main_outside_inside(page: str) -> str:
    main = re.search(r"<main.*?</main>", page, re.S)
    assert main, "no main"
    return re.sub(r'<details class="inside">.*?</details>', "", main.group(0), flags=re.S)


def test_step1_summary_comes_from_the_data() -> None:
    with TestClient(create_app()) as client:
        _english(client)
        page = client.get("/study").text
    assert 'class="num">124<' in page and 'class="num">4<' in page
    assert "doses: 0, 20, 200, 400 mg/kg/day" in page
    assert "job runner: in process." in _inside(page)


def test_step1_run_shows_quarantine_and_computed_means() -> None:
    with TestClient(create_app()) as client:
        _english(client)
        result = client.post("/study/run").text
    assert "Impossible values set apart: 12" in result
    assert result.count('class="new"') == 3 + 12  # the short table and the full list
    assert "Show all values · 12 rows" in result
    assert "-23,450 h*ng/mL" in result and "exposure (AUC), day 1" in result
    assert "Values set apart: 12" in result and "males, 20 mg/kg, day 1" in result
    assert "h*ng/mL: 2,821 with" in result and "(n=3)" in result
    assert "15,956 without" in result and "(n=2)" in result


def test_step1_without_injection_every_count_is_twelve() -> None:
    page = rendered_state("study_after", "en")
    shown = _text(_main_outside_inside(page))
    assert "Impossible values set apart: 12" in shown and "· 12 rows" in shown
    assert _text(_inside(page)).count("Values set apart: 12") == 1
    assert "13" not in re.sub(r"PDS2014-\d+", "", shown)
    assert "New value set apart" not in shown and "injected" not in _text(page).lower()


def test_step1_injection_is_one_value_with_one_animal_everywhere() -> None:
    page = rendered_state("study_injected", "en")
    shown = _text(_main_outside_inside(page))
    inside = _text(_inside(page))
    assert "Impossible values set apart: 13" in shown and "· 13 rows" in shown
    assert "Values set apart: 13." in inside and "Values set apart: 12" not in inside
    animal = re.search(r"Injected value: animal (PDS2014-\d+)", inside)
    assert animal, "the Inside panel does not name the injected animal"
    first_row = re.search(
        r"<tr class=\"new\"><td>(PDS2014-\d+)</td><td>concentration, day 1</td>", page
    )
    assert first_row and first_row.group(1) == animal.group(1)
    assert "-1 ng/mL" in page
    # the full list holds 13 rows and the injected animal is the only one with a concentration
    assert page.count("concentration, day") == 2  # short table and full list
    assert "New value set apart: mean AUC (males, 20 mg/kg, day 1) stays 15,956 h*ng/mL" in shown


def test_step1_main_has_no_upper_case_send_terms() -> None:
    allowed = {"AUC", "FDA"}
    for state in ("study_before", "study_after", "study_injected"):
        for lang in ("es", "en"):
            shown = re.sub(
                r"PDS2014-\d+", "", _text(_main_outside_inside(rendered_state(state, lang)))
            )
            assert set(re.findall(r"[A-Z]{3,}", shown)) <= allowed, (state, lang)


def test_step1_switches_fire_their_rule_without_touching_the_sources(tmp_path: Path) -> None:
    db = tmp_path / "cairn.duckdb"
    ingest(db_path=db)
    vendored = sorted(VENDORED_DIR.glob("*"))
    watched = [db, *vendored] + ([DEFAULT_DB] if DEFAULT_DB.exists() else [])
    before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in watched]
    expected = {
        "negative": "concentration",
        "duplicate": "animal ID repeated",
        "dose": "dose group missing",
    }
    with TestClient(create_app()) as client:
        _english(client)
        plain = client.post("/study/run", data={"switch": "none"}).text
        for switch, shown in expected.items():
            result = client.post("/study/run", data={"switch": switch}).text
            if switch == "negative":
                assert "Impossible values set apart: 13" in result and "Undo" in result
            else:  # the validator reports these rules and does not quarantine them
                assert "Impossible values set apart: 12" in result
                assert "Also reported, not set apart:" in result
                assert "Undo" not in result
            assert shown in result
            assert all(other not in result for o, other in expected.items() if o != switch)
            assert shown not in plain
        assert client.post("/study/run", data={"switch": "bogus"}).status_code == 422
    assert "Impossible values set apart: 12" in plain
    assert [hashlib.sha256(p.read_bytes()).hexdigest() for p in watched] == before


def test_templates_hold_no_literal_means() -> None:
    pattern = re.compile(r"2,?821|2,?820|15,?956")
    for template in (HERE / "templates").glob("*.html"):
        assert not pattern.search(template.read_text(encoding="utf-8")), template.name


def _inside(page: str) -> str:
    """The folded Inside panel of a screen."""
    panel = re.search(r'<details class="inside">.*?</details>', page, re.S)
    assert panel, "no Inside panel"
    return panel.group(0)


def test_footer_uses_baked_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAIRN_COMMIT", "abc1234")
    with TestClient(create_app()) as client:
        landing = client.get("/").text
        screen = client.get("/study").text
    assert "commit abc1234" in landing
    assert "commit abc1234" in _inside(screen) and "commit abc1234" not in screen.replace(
        _inside(screen), ""
    )


FIXTURES = Path(__file__).parent / "fixtures" / "recordings"


def _ask(
    question: str, monkeypatch: pytest.MonkeyPatch, folder: Path = FIXTURES, lang: str = "en"
) -> str:
    monkeypatch.setenv("CAIRN_RECORDINGS", str(folder))
    with TestClient(create_app()) as client:
        client.cookies.set(COOKIE, lang)
        return client.post("/ask/run", data={"question": question}).text


PROV_BODY = re.compile(r'<div class="prov-body">.*?</div></details>', re.S)


def _outside_sources(html: str) -> str:
    """The answer without the sources that provenance tags open."""
    return PROV_BODY.sub("</details>", html)


def _prose_text(html: str) -> str:
    """What the prose says: the text and the chips, not the sources behind them."""
    prose = re.search(r'<div class="prose answer-unit">(.*?)</div>', _outside_sources(html), re.S)
    assert prose, "no rendered answer"
    return " ".join(unescape(re.sub(r"<[^>]+>", "", prose.group(1))).split())


def _model_text_toggle(html: str) -> str:
    """The closed disclosure of the model text, whatever the locale."""
    label = r"(?:Ver texto generado|Show model text)"
    found = re.search(
        rf'<details class="pill"><summary class="pill">{label}.*?</details>', html, re.S
    )
    assert found, "no model text toggle"
    return found.group(0)


def test_step2_page_lists_the_questions_with_the_recorded_badge() -> None:
    with TestClient(create_app()) as client:
        page = _english(client).get("/ask").text
    assert 'class="badge recorded"' in page
    assert "In production" in _inside(page)
    assert '"question": "Q2"' in page and '"question": "Q6"' in page


REAL = Path(__file__).parent / "fixtures" / "recordings_real_shape"


def _as_bedrock(folder: Path, target: Path) -> Path:
    """A copy of the real-shape fixtures that claims to be recorded, to test the recorded badge."""
    for source in folder.glob("*.json"):
        data = json.loads(source.read_text(encoding="utf-8"))
        data["source"] = "bedrock"
        (target / source.name).write_text(json.dumps(data), encoding="utf-8")
    return target


def test_q2_replay(monkeypatch: pytest.MonkeyPatch) -> None:
    """Offline replay of the real-shape Opus 4.6 fixture: 9-row screen, honest denominators."""
    result = _ask("Q2", monkeypatch, REAL)
    assert 'class="badge fixture"' in result
    assert "Rules fired: none" in result
    assert _outside_sources(result).count("<tr><td>") == 9
    assert "not examined" in result and "0/1" in result
    assert (
        "9 screened findings; the clearest is adrenal gland, vacuolization in female and male"
        in (_prose_text(result))
    )
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
    assert _outside_sources(result).count("<tr><td>") == 9
    assert "not examined" in result
    assert "The screen examined 80 animals" in _prose_text(result)
    assert "Rules fired: none" in result
    assert "incidence, main study" in result and "n=80" in result


@pytest.mark.parametrize(("folder", "marker"), [(FIXTURES, "[n_examined]"), (REAL, "[finding]")])
def test_step2_toggle_shows_markers_and_no_digits(
    monkeypatch: pytest.MonkeyPatch, folder: Path, marker: str
) -> None:
    result = _ask("Q2", monkeypatch, folder, lang="es")
    toggle = _model_text_toggle(result)
    assert marker in toggle
    assert not re.search(r"\d", toggle.split("</summary>")[1])


def test_q6_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    """Deviation D3: the real Q6 recording ends declined, which counts as correct."""
    result = _ask("Q6", monkeypatch, REAL)
    assert "It declines" in result
    assert "<tr><td>" not in result and 'class="prose' not in result


def test_q6_blocked_by_rules_on_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _ask("Q6", monkeypatch)
    trace = result[result.index('<div id="inside-trace" hx-swap-oob="true">') :]
    assert "Rules fired: 1, 6" in trace
    assert 'class="prose' not in result
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
    assert "The screen examined 80 animals" in _prose_text(_ask("Q2", monkeypatch))


def test_step2_rejects_an_unknown_question(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAIRN_RECORDINGS", str(FIXTURES))
    with TestClient(create_app()) as client:
        assert client.post("/ask/run", data={"question": "Q9"}).status_code == 422


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
    sentence = re.search(r"examined (?:a total of )?(\d+) animals", _prose_text(result))
    evidence = re.search(r"incidence, [^<]*?, n=(\d+), (\d+) (\w+), from ", result)
    assert sentence and evidence
    assert sentence.group(1) == evidence.group(1)
    assert evidence.group(3) == "affected"


def test_step2_header_badge_follows_the_recordings_served(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    recorded = _as_bedrock(REAL, tmp_path)
    cases = ((FIXTURES, "fixture", "recorded"), (recorded, "recorded", "fixture"))
    for folder, shown, hidden in cases:
        monkeypatch.setenv("CAIRN_RECORDINGS", str(folder))
        with TestClient(create_app()) as client:
            page = client.get("/ask").text
        assert f'class="badge {shown}"' in page and f'class="badge {hidden}"' not in page


def test_step2_badge_ignores_unreadable_files_and_empty_folders(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "list.json").write_text("[]", encoding="utf-8")
    (tmp_path / "bad.json").write_text("{not json", encoding="utf-8")
    for folder in (tmp_path, tmp_path / "missing"):
        monkeypatch.setenv("CAIRN_RECORDINGS", str(folder))
        with TestClient(create_app()) as client:
            response = client.get("/ask")
        assert response.status_code == 200
        page = response.text
        assert 'class="badge none"' in page and 'class="badge recorded"' not in page


def test_q2_prose_names_the_screened_findings_by_sex_and_places_no_table_position(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The prose answers the question: a finding that passes the screen, with its sexes."""
    from cairn.incidence import incidence

    result = _ask("Q2", monkeypatch, REAL)
    text = _prose_text(result)
    findings = incidence().values["findings"]
    names = i18n.CATALOGUES["en"]
    named = [
        f
        for f in findings
        if names.get(finding_key(f"{f['tissue']} {f['finding']}"), "").lower() in text
    ]
    assert named, f"the prose names no finding that passes the screen: {text!r}"
    for finding in named:
        sexes = {
            f["sex"]
            for f in findings
            if (f["tissue"], f["finding"]) == (finding["tissue"], finding["finding"])
        }
        words = {"F": "female", "M": "male"}
        assert all(re.search(rf"\b{words[sex]}\b", text) for sex in sexes), text
    assert not re.search(r"\b(above|below)\b", text)


def test_q2_prose_counts_the_screened_findings_by_reference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The count is a reference to the code's own count and matches the rows of the table."""
    from cairn.incidence import incidence

    result = _ask("Q2", monkeypatch, REAL)
    text = _prose_text(result)
    rows = _outside_sources(result).count("<tr><td>")
    assert re.match(rf"{rows} screened findings", text), text
    assert rows == incidence().values["n_findings"]
    toggle = _model_text_toggle(result)
    assert "[n_findings]" in toggle
    assert not re.search(r"\d", toggle.split("</summary>")[1])


def _explore(question: str, lang: str = "en") -> str:
    with TestClient(create_app()) as client:
        return client.post(f"/ask/run?lang={lang}", data={"question": question}).text


def test_ask_page_has_a_button_for_every_question() -> None:
    from cairn.questions import QUESTIONS

    with TestClient(create_app()) as client:
        page = client.get("/ask?lang=en").text
    for question_id in (*QUESTIONS, "NS1", "NS2"):
        assert f'"question": "{question_id}"' in page
    assert len(QUESTIONS) == 11
    assert "live model calls." in _inside(page) and 'class="badge recorded"' in page


@pytest.mark.parametrize(
    "question", ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7", "Q8", "G1", "G2", "G3", "NS1", "NS2"]
)
def test_every_ask_question_replays_offline(question: str) -> None:
    result = _explore(question)
    trace = result[result.index('<div id="inside-trace" hx-swap-oob="true">') :]
    assert 'class="badge recorded"' in trace
    assert 'answer-unit"' in result or 'class="callout blocked"' in result


def test_ask_marks_the_trick_questions() -> None:
    with TestClient(create_app()) as client:
        page = client.get("/ask?lang=en").text
    assert page.count('class="trick-tag"') == 4
    for question in ("Q4", "Q6", "Q7", "Q8"):
        button = re.search(rf'<button[^>]*"question": "{question}".*?</button>', page, re.S)
        assert button and "trick-tag" in button.group(0), question
    button = re.search(r'<button[^>]*"question": "Q2".*?</button>', page, re.S)
    assert button and "trick-tag" not in button.group(0)


def test_old_explore_routes_are_gone() -> None:
    with TestClient(create_app()) as client:
        assert client.post("/explore/run", data={"question": "Q2"}).status_code in (404, 405)
        moved = client.get("/explore", follow_redirects=False)
    assert moved.status_code == 303 and moved.headers["location"].startswith("/ask")


@pytest.mark.parametrize("question", ["G1", "G2", "G3"])
def test_ask_guideline_questions_render_quotes_from_quoteref(question: str) -> None:
    result = _explore(question)
    assert 'class="badge recorded"' in result
    assert "<blockquote" not in result
    assert 'class="prov prov-quote"' in result
    assert "official page" in result and "#page=" in result
    assert "Rules fired: none" in result


def test_ask_rejects_an_unknown_question() -> None:
    with TestClient(create_app()) as client:
        assert client.post("/ask/run", data={"question": "Q99"}).status_code == 422


def _fixed_answers() -> str:
    with TestClient(create_app()) as client:
        return "".join(
            client.post("/ask/run?lang=en", data={"question": q}).text for q in ("NS1", "NS2")
        )


def test_step3_shows_the_two_fixed_queries_without_the_passage_ranking() -> None:
    from cairn import retrieval

    with TestClient(create_app()) as client:
        page = client.get("/ask?lang=en").text
    fixed = [q for q in retrieval.load_fixed_queries() if q["used_by"] == "nonclinical-summary"]
    assert len(fixed) == 2
    assert '"question": "NS1"' in page and '"question": "NS2"' in page
    for word in ("Show passage ranking", "Show lower ranks", "<th>Lex</th>", "<th>Fused</th>"):
        assert word not in page + _fixed_answers()


def test_step3_counts_quotes_on_the_cited_page() -> None:
    answers = _fixed_answers()
    assert answers.count('<details class="prov prov-quote">') == 6
    assert answers.count("#page=") >= 6


def test_navigation_has_no_locked_step() -> None:
    with TestClient(create_app()) as client:
        page = client.get("/ask?lang=en").text
    assert re.search(r'<a href="/ask" aria-current="page"><span [^>]*>2</span>', page)
    assert page.count('class="locked"') == 0


def test_highlight_route_serves_only_committed_pngs() -> None:
    from cairn.highlight import load_highlights

    entry = load_highlights()[0]
    name = Path(entry["image"]).name
    with TestClient(create_app()) as client:
        ok = client.get(f"/highlights/{name}")
        assert ok.status_code == 200 and ok.headers["content-type"] == "image/png"
        assert ok.content.startswith(b"\x89PNG")
        assert client.get("/highlights/nope.png").status_code == 404
        assert client.get("/highlights/..%2Fhighlights.json").status_code == 404


def test_highlight_route_page_shows_the_image_and_the_official_link() -> None:
    from cairn.highlight import load_highlights

    entry = load_highlights()[0]
    with TestClient(create_app()) as client:
        page = client.get(f"/highlight/{entry['sentence_id']}").text
        assert client.get("/highlight/unknown.s9").status_code == 404
    assert f'src="/{entry["image"]}"' in page
    assert f'href="{entry["link"]}"' in page and "#page=" in entry["link"]


def test_highlight_route_links_every_step3_quotation() -> None:
    page = _fixed_answers()
    with TestClient(create_app()) as client:
        links = re.findall(r'href="(/highlight/[^"]+)">highlighted page', page)
        assert len(links) == 6
        for link in links:
            assert client.get(link).status_code == 200
    assert page.count("official page") == 6 and "#page=" in page


def test_explore_quotations_link_the_highlighted_page() -> None:
    result = _explore("G2")
    assert "highlighted page" in result and 'href="/highlight/' in result
    assert "official page" in result and "#page=" in result


def test_explore_guideline_quotations_sit_inside_the_answer_card() -> None:
    result = _explore("G1")
    assert "<blockquote" not in result and "col-right" not in result
    assert result.index('class="card answer"') < result.index('class="prov prov-quote"')


def test_step3_quote_link_and_nav_follow_the_cited_sentence_page() -> None:
    from cairn.highlight import cited_page
    from cairn.passages import stored_passages

    passage = stored_passages()["M4S-2.6-01"]
    assert cited_page(passage, "M4S-2.6-01.s12") == 8 != passage.page_start
    with TestClient(create_app()) as client:
        explore = client.get("/ask").text
        entry = client.get("/highlight/M4S-2.6-01.s12").text
    assert explore.count('aria-current="page"') == 1
    assert 'aria-current="page"' not in entry


def test_step3_quote_cite_and_links_use_the_cited_sentence_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from cairn import web
    from cairn.passages import stored_passages

    real = stored_passages()
    passage = real["M4S-2.6-01"]
    later = next(s for s in passage.sentences if s.sentence_id == "M4S-2.6-01.s12")
    moved = passage.model_copy(update={"sentences": [later, *passage.sentences]})
    assert passage.page_start == 7
    monkeypatch.setattr(web, "stored_passages", lambda: {**real, passage.passage_id: moved})
    quote = next(q for q in web._step3_context()["quotes"] if q["text"] == later.text)
    assert quote["cite"].endswith(" 8") and quote["link"].endswith("#page=8")
    assert quote["highlight"] == "/highlight/M4S-2.6-01.s12"
    assert "#page=8" in _fixed_answers()


def test_web_parses_passages_and_highlights_once_per_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from cairn import highlight, passages

    calls = {"passages": 0, "highlights": 0}
    real_p, real_h = passages.load_passages, highlight.load_highlights

    def count_p(*args: object) -> object:
        calls["passages"] += 1
        return real_p(*args)  # type: ignore[arg-type]

    def count_h(*args: object) -> object:
        calls["highlights"] += 1
        return real_h(*args)  # type: ignore[arg-type]

    passages.stored_passages.cache_clear()
    highlight.highlights_by_sentence.cache_clear()
    monkeypatch.setattr(passages, "load_passages", count_p)
    monkeypatch.setattr(highlight, "load_highlights", count_h)
    with TestClient(create_app()) as client:
        for _ in range(3):
            assert client.get("/ask").status_code == 200
            assert client.get("/highlight/M4S-2.6-01.s12").status_code == 200
    assert calls == {"passages": 1, "highlights": 1}
    passages.stored_passages.cache_clear()
    highlight.highlights_by_sentence.cache_clear()


def _filled(client: TestClient) -> str:
    """Start the thread on /decide, fill the example and return its id (the cookie)."""
    client.get("/decide")
    id_ = client.cookies.get("cairn_thread")
    assert id_
    client.post("/decide/choose", data={"sex": "F", "related": "20", "adverse": "200"})
    client.post("/decide/choose", data={"sex": "M", "related": "400", "adverse": "400"})
    return id_


def _decided(client: TestClient) -> str:
    id_ = _filled(client)
    client.post("/decide/confirm", data={"actor": "R. Reviewer"})
    return id_


def test_decide_and_draft_people_decide_and_the_author_cannot_approve() -> None:
    with TestClient(create_app()) as client:
        client.cookies.set(COOKIE, "en")
        step4 = client.get("/decide").text  # starts a thread and sets the cookie
        assert client.cookies.get("cairn_thread")
        assert "Acting as: A. Author" in step4
        assert "checked" not in step4 and "selected" not in step4  # nothing preselected
        assert step4.count("not decided yet") == 2 and "NOAEL, Females: 400" not in step4
        assert "no decision yet" not in step4 and "Decide" in step4
        client.post("/decide/choose", data={"sex": "F", "related": "20", "adverse": "200"})
        client.post("/decide/choose", data={"sex": "M", "related": "400", "adverse": "400"})
        one = client.post("/decide/confirm", data={"actor": "R. Reviewer", "sex": "F"})
        assert "NOAEL, Females: 20 mg/kg" in one.text and "Confirm Males" in one.text
        confirmed = client.post("/decide/confirm", data={"actor": "R. Reviewer", "sex": "M"})
        assert (
            "Acting as: R. Reviewer" in confirmed.text and "Show draft in English" in confirmed.text
        )
        refused = client.post("/draft/approve", data={"actor": "A. Author"})
        assert (
            refused.status_code == 403
            and "The author cannot sign; another person signs." in refused.text
        )
        assert "Rejected" not in refused.text and "(403)" not in refused.text
        done = client.post("/draft/approve", data={"actor": "R. Reviewer"})
        assert "Approved by R. Reviewer" in done.text


@pytest.mark.parametrize(("lang", "text"), [("es", "sin decidir"), ("en", "not decided yet")])
def test_draft_with_nothing_decided_is_200_and_says_so(lang: str, text: str) -> None:
    with TestClient(create_app()) as client:
        reply = client.get(f"/draft?lang={lang}")
    assert reply.status_code == 200 and text in reply.text


def test_decide_pages_redirect_on_409_and_reject_bad_input() -> None:
    with TestClient(create_app(), follow_redirects=False) as client:
        id_ = _filled(client)
        client.post("/decide/confirm", data={"actor": "R. Reviewer"})
        again = client.post(
            "/decide/choose", data={"sex": "F", "related": "20", "adverse": "200"}
        )  # back button
        assert again.status_code == 303 and again.headers["location"].startswith("/draft?actor=")
        twice = client.post("/draft/approve", data={"actor": "R. Reviewer"})
        assert twice.status_code == 200
        second = client.post("/draft/approve", data={"actor": "R. Reviewer"})
        assert second.status_code == 303 and second.headers["location"].startswith("/draft?actor=")
        for reply in (
            client.get("/draft?actor=Mallory"),
            client.post("/draft/approve", data={"actor": "Mallory"}),
            client.post("/decide/confirm", data={"actor": "Mallory"}),
        ):
            assert reply.status_code == 422
        client.cookies.clear()
        fresh = _filled(client)
        assert fresh != id_
        slot = client.get(f"/api/threads/{fresh}").json()["slots"][0]["slot"]
        bad = client.post("/decide/choose", data={"sex": "F", "adverse": "x"})
        assert bad.status_code == 422
        assert slot


def test_draft_without_judge_recordings_shows_not_judged_and_the_rules_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = tmp_path / "recordings"
    shutil.copytree("recordings", folder, ignore=shutil.ignore_patterns("j-*.json"))
    for name in ("cairn.web.people", "cairn.web.threads"):
        monkeypatch.setattr(importlib.import_module(name), "RECORDINGS_DIR", folder)
    monkeypatch.setenv("CAIRN_THREADS_DB", str(tmp_path / "threads.db"))
    with TestClient(create_app()) as client:
        client.cookies.set("cairn_lang", "en")
        _decided(client)
        page = client.get("/draft?actor=R.%20Reviewer").text
        assert "Judge panel" in page and "never blocks" in page and "0/16" in page
        assert "not judged" in page and "EXAMPLE" in page and "RECORDED" in page
        assert "8/8" in page and "rules passed" in page
        assert "Checks" not in page
        done = client.post("/draft/approve", data={"actor": "R. Reviewer"})
        assert "Approved by R. Reviewer" in done.text


def test_draft_with_the_real_recordings_shows_real_verdicts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CAIRN_THREADS_DB", str(tmp_path / "threads.db"))
    with TestClient(create_app()) as client:
        client.cookies.set("cairn_lang", "en")
        _decided(client)
        page = client.get("/draft?actor=R.%20Reviewer").text
        assert "16/16" in page and "sentences judged" in page and "sonnet-4-6" in page
        assert "n=24" in page and "kappa 1.00" in page and "EXAMPLE" in page


def test_draft_lists_each_warning_and_the_example_and_approval_still_works(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import test_judge as tj
    from cairn.decisions import enumerate_slots, example_decisions
    from cairn.gateway import DEFAULT_MODEL, LLMGateway, Mode
    from cairn.judge import EXAMPLE_OBS, EXAMPLE_SENTENCE
    from cairn.recording import ReplayClient, recorded_model
    from cairn.workflow import (
        build_ledger,
        draft_key,
        draft_sections,
        final_sentences,
        gather_state,
        shown_facts,
    )

    folder = tmp_path / "recordings"
    shutil.copytree("recordings", folder, ignore=shutil.ignore_patterns("j-*.json"))
    for name in ("cairn.web.people", "cairn.web.threads"):
        monkeypatch.setattr(importlib.import_module(name), "RECORDINGS_DIR", folder)
    monkeypatch.setenv("CAIRN_THREADS_DB", str(tmp_path / "threads.db"))
    state = gather_state()
    model = recorded_model(folder, "DRAFT", DEFAULT_MODEL)
    replay = ReplayClient.load(folder, draft_key(model))
    state["sections"] = draft_sections(state, LLMGateway(Mode.REPLAY, client=replay), model)
    slots = enumerate_slots(build_ledger(state))
    state["decisions"] = [d.model_dump() for d in example_decisions(slots, "A", "2026-10-28")]
    state["confirmed"] = ["F", "M"]
    first, facts = final_sentences(state)[0]
    tj.save_recording(folder, first, facts, tj.reply("overstated", "magnitude", "Too strong."))
    example = shown_facts(build_ledger(gather_state()), EXAMPLE_OBS)
    tj.save_recording(folder, EXAMPLE_SENTENCE, example, tj.reply("overstated", "causal"))
    with TestClient(create_app()) as client:
        client.cookies.set("cairn_lang", "en")
        _decided(client)
        page = client.get("/draft?actor=R.%20Reviewer").text
        assert "warning: magnitude" in page and "Too strong." in page
        assert "warning: causal" in page and "EXAMPLE" in page and "It claims cause." in page
        assert "not judged" in page  # the other sentences have no recording
        done = client.post("/draft/approve", data={"actor": "R. Reviewer"})
        assert "Approved by R. Reviewer" in done.text


def test_draft_shows_rules_chain_status_and_the_production_note() -> None:
    with TestClient(create_app(), follow_redirects=False) as client:
        _english(client)
        _decided(client)
        page = client.get("/draft").text
        assert (
            'class="badge recorded"' in page and "passed" in page and "<td>fired</td>" not in page
        )
        assert "Verified." in _inside(page) and "chained entries" in _inside(page)
        assert "8/8" in page and "rules passed" in page
        assert "not a validated or external log" in _inside(page)
        inside = _inside(page)
        assert "In production" in inside and "an editor with tracked changes" in inside
        assert "an external append-only log" in inside


def test_draft_closes_the_session_with_one_tool_over_mcp_and_rest() -> None:
    with TestClient(create_app(), follow_redirects=False) as client:
        _english(client)
        _decided(client)
        client.post("/draft/approve", data={"actor": "R. Reviewer"})
        page = client.get("/draft").text
        assert 'class="badge recorded"' in page and "Same hash, same Observation." in page
        assert "Approved by R. Reviewer" in page
        assert "numbers by code (0 by the model)" in page and "quotes verbatim" in page
        assert (
            re.search(r"\d+ entries, verified", page)
            and "R. Reviewer" in page
            and "8 of 8 passed" in page
        )
        assert "Show production table" not in page and "In production" in _inside(page)
        hashes = re.findall(r"<td>(?:MCP|REST)</td><td>([0-9a-f]{16})</td>", _inside(page))
        assert len(hashes) == 2 and hashes[0] == hashes[1]
        assert client.get("/docs").status_code == 200
        assert client.get("/mcp").status_code < 500
        assert 'href="/docs"' in page
        assert "github.com" not in page and 'href="/mcp"' not in page


def test_draft_rest_door_goes_through_the_http_route(monkeypatch: pytest.MonkeyPatch) -> None:
    with TestClient(create_app(), follow_redirects=False) as client:
        _english(client)
        _decided(client)
        monkeypatch.setattr(
            app_module, "call_tool", lambda name, args: {"content_sha256": "x" * 64}
        )
        page = client.get("/draft").text
    assert "The hashes differ." in page and "Same hash" not in page
    assert "xxxxxxxxxxxxxxxx" in page


def test_draft_survives_a_non_http_error_in_the_rest_door(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(name: str, args: dict[str, Any]) -> dict[str, Any]:
        raise KeyError(name)

    with TestClient(create_app(), follow_redirects=False) as client:
        _english(client)
        _decided(client)
        monkeypatch.setattr(app_module, "call_tool", broken)
        reply = client.get("/draft")
    assert reply.status_code == 200
    assert "HTTP 500" in reply.text and "The hashes differ." in reply.text


def test_draft_says_where_the_chain_is_broken(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = tmp_path / "threads.db"
    monkeypatch.setenv("CAIRN_THREADS_DB", str(db))
    with TestClient(create_app(), follow_redirects=False) as client:
        _english(client)
        id_ = _decided(client)
        with sqlite3.connect(db) as conn:
            conn.execute("UPDATE audit SET actor = 'X' WHERE thread_id = ? AND seq = 3", (id_,))
        page = client.get("/draft").text
        assert "Broken at entry 3." in page and "Verified." not in page


@pytest.mark.parametrize("lang", ["es", "en"])
def test_landing_shows_one_h1_a_real_marked_sentence_and_one_primary_action(lang: str) -> None:
    from cairn.web.i18n import CATALOGUES

    with TestClient(create_app()) as client:
        page = client.get(f"/?lang={lang}").text
    main = page.split("<main", 1)[1].split("</main>", 1)[0]
    assert page.count("<h1") == 1
    assert CATALOGUES[lang]["land_title"] in unescape(main)
    sentence = re.search(
        r'<div class="lede answer" lang="en">(.*?)</div>\s*</div>\s*<p class="meta">', main, re.S
    )
    assert sentence and 'class="prov prov-data"' in sentence.group(1)
    plain = re.sub(r'<details class="prov .*?</details>', " ", sentence.group(1), flags=re.S)
    assert not re.search(r"\d", re.sub(r"<[^>]+>", "", plain))  # every digit sits in a tag
    assert len(re.findall(r'class="btn-primary"', main)) == 1
    assert 'class="btn-primary" href="/study"' in main
    for gone in ('class="journey"', 'class="path"', 'class="cue', 'class="legend"', 'class="badge'):
        assert gone not in main
    assert "aria-current" not in main and 'aria-current="page"' not in page


def _flat(html: str) -> str:
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", html)).split())


@pytest.mark.parametrize("lang", ["es", "en"])
def test_landing_sentence_is_the_recorded_body_weight_answer_of_ask(lang: str) -> None:
    with TestClient(create_app()) as client:
        landing = client.get(f"/?lang={lang}").text
        ask = client.post(f"/ask/run?lang={lang}", data={"question": "Q3"}).text
    lede = re.search(
        r'<div class="lede answer" lang="en">(.*?)</div>\s*</div>\s*<p class="meta">', landing, re.S
    )
    assert lede
    chips = re.findall(r'<details class="prov .*?</details>', lede.group(1), re.S)
    assert len(chips) >= 4 and all(chip in ask for chip in chips)  # figures only, no terms
    shown = _flat(lede.group(1)).removesuffix(" ...")
    assert shown in _flat(ask) and shown.endswith("lower than control")
    assert "9.3" not in _flat(landing)


@pytest.mark.parametrize("lang", ["es", "en"])
def test_landing_quote_is_english_and_labelled_en_in_both_locales(lang: str) -> None:
    with TestClient(create_app()) as client:
        landing = client.get(f"/?lang={lang}").text
    assert '<span class="lang-tag">EN</span>' in landing
    assert '<div class="lede answer" lang="en">' in landing


@pytest.mark.parametrize("lang", ["es", "en"])
def test_explore_strings_come_from_the_active_catalogue(lang: str) -> None:
    from cairn.web.i18n import CATALOGUES

    other = CATALOGUES["en" if lang == "es" else "es"]
    own = CATALOGUES[lang]
    with TestClient(create_app()) as client:
        page = client.get(f"/ask?lang={lang}").text
    answer = _explore("Q2", lang)
    for key in ("step_2", "s2_lede"):
        assert own[key] in page
        assert other[key] not in page
    for key in ("exp_rules",):
        assert own[key] in answer and other[key] not in answer
    assert f"<th>{own['exp_th_sex']}</th>" in answer


def test_explore_recorded_prose_is_identical_in_both_locales() -> None:
    def prose(html: str) -> str:
        return _prose_text(html)

    assert prose(_explore("Q1", "es")) == prose(_explore("Q1", "en"))


def test_decide_first_render_shows_incidence_examples_and_no_noael() -> None:
    from cairn.incidence import incidence

    adrenal = [
        row
        for row in incidence().values["findings"]
        if row["tissue"] == "GLAND, ADRENAL" and row["finding"] == "Vacuolization"
    ]
    with TestClient(create_app()) as client:
        client.cookies.set(COOKIE, "en")
        main = client.get("/decide").text.split("<main")[1].split("</main>")[0]
    assert " checked" not in main and " selected" not in main
    assert "ADRENAL" not in main and "Adrenal gland, vacuolization" in main
    assert main.count("not decided yet") == 2 and "400 mg/kg" not in main
    for row in adrenal:
        for group in row["groups"]:
            assert f"{group['affected']}/{group['examined']}" in main
    assert main.count(">example<") == 9 and "REAL" not in main


def _stored(client: TestClient, sex: str) -> tuple[float | None, float | None]:
    id_ = client.cookies.get("cairn_thread")
    slot = next(
        s["slot"]
        for s in client.get(f"/api/threads/{id_}").json()["slots"]
        if s["finding"] == "GLAND, ADRENAL Vacuolization" and s["sex"] == sex
    )
    decision = next(
        (d for d in client.get(f"/api/threads/{id_}").json()["decisions"] if d["dec_id"] == slot),
        None,
    )
    assert decision is not None
    return decision["treatment_related_from"], decision["adverse_from"]


def test_decide_stores_what_the_person_chose_and_never_infers_relatedness() -> None:
    with TestClient(create_app(), follow_redirects=False) as client:
        client.get("/decide")
        only_adverse = client.post("/decide/choose", data={"sex": "F", "adverse": "200"})
        assert only_adverse.status_code == 422
        below = client.post("/decide/choose", data={"sex": "F", "related": "400", "adverse": "200"})
        assert below.status_code == 422
        id_ = client.cookies.get("cairn_thread")
        assert client.get(f"/api/threads/{id_}").json()["decisions"] == []  # still undecided
        # Incidence would suggest 20 for females; the person says 200 and code keeps it.
        client.post("/decide/choose", data={"sex": "F", "related": "200", "adverse": "200"})
        assert _stored(client, "F") == (200, 200)
        client.cookies.clear()
        client.get("/decide")
        client.post("/decide/choose", data={"sex": "M", "related": "20", "adverse": "none"})
        assert _stored(client, "M") == (20, None)


DOSES = ("20", "200", "400")


@pytest.mark.parametrize("sex", ["F", "M"])
def test_stored_related_and_adverse_equal_the_posted_values_for_every_dose(sex: str) -> None:
    """Behavioural: whatever the incidence, the stored choice is exactly what the person posted."""
    with TestClient(create_app(), follow_redirects=False) as client:
        client.get("/decide")
        for related in ("none", *DOSES):
            for adverse in ("none", *DOSES):
                valid = (related == "none" and adverse == "none") or (
                    related != "none" and (adverse == "none" or float(related) <= float(adverse))
                )
                reply = client.post(
                    "/decide/choose", data={"sex": sex, "related": related, "adverse": adverse}
                )
                if not valid:
                    assert reply.status_code == 422
                    continue
                assert reply.status_code == 303
                want = (
                    None if related == "none" else float(related),
                    None if adverse == "none" else float(adverse),
                )
                assert (
                    _stored(
                        client,
                        sex,
                    )
                    == want
                )


def _decisions(client: TestClient) -> list[dict[str, Any]]:
    id_ = client.cookies.get("cairn_thread")
    decisions: list[dict[str, Any]] = client.get(f"/api/threads/{id_}").json()["decisions"]
    return decisions


CHIP = re.compile(
    r"<dt>Decided by</dt><dd>(.*?)</dd><dt>Role</dt><dd>(.*?)</dd><dt>Value</dt><dd>(.*?)</dd>"
)


def test_example_decisions_are_labelled_as_examples_end_to_end() -> None:
    with TestClient(create_app()) as client:
        client.cookies.set(COOKIE, "en")
        _decided(client)
        by_actor = [d["actor"] for d in _decisions(client)]
        assert by_actor.count("Example") == 9 and by_actor.count("A. Author") == 2
        draft = client.get("/draft").text
        decide = client.get("/decide").text
    chips = CHIP.findall(draft)
    kidney = [who for who, _, value in chips if value.startswith("KIDNEY Necrosis")]
    assert kidney and set(kidney) == {"Preloaded example"}
    own = [c for c in chips if c[0] in ("A. Author", "R. Reviewer")]
    assert own and all("ADRENAL" in c[2] or c[2].startswith("NOAEL") for c in own)
    counts = re.search(r"(\d+) decisions by people, (\d+) from preloaded examples", draft)
    assert counts
    assert int(counts.group(2)) == sum(1 for c in chips if c[0] == "Preloaded example")
    assert int(counts.group(1)) == len(own)
    assert "count toward the NOAEL" in decide


def test_every_decision_chip_shows_who_and_a_nonempty_role() -> None:
    with TestClient(create_app()) as client:
        client.cookies.set(COOKIE, "en")
        _decided(client)
        html = client.get("/draft").text
    chips = CHIP.findall(html)
    assert chips and all(who.strip() and role.strip() for who, role, _ in chips)


def test_change_before_confirming_and_start_over() -> None:
    with TestClient(create_app(), follow_redirects=False) as client:
        client.get("/decide")
        client.post("/decide/choose", data={"sex": "F", "related": "20", "adverse": "200"})
        plain = client.get("/decide").text
        assert "/decide?change=F" in plain
        assert plain.count('action="/decide/choose"') == 1  # only males, still undecided
        changing = client.get("/decide?change=F").text
        assert changing.count('action="/decide/choose"') == 2
        client.post("/decide/choose", data={"sex": "F", "related": "400", "adverse": "400"})
        assert _stored(client, "F") == (400, 400)
        old = client.cookies.get("cairn_thread")
        reply = client.post("/restart")
        assert reply.status_code == 303 and client.cookies.get("cairn_thread") != old
        assert _decisions(client) == []


def test_confirm_refusals_are_shown_not_redirected() -> None:
    with TestClient(create_app(), follow_redirects=False) as client:
        client.cookies.set(COOKIE, "en")
        client.get("/decide")
        none = client.post("/decide/confirm", data={"actor": "R. Reviewer", "sex": "F"})
        assert none.status_code == 409 and "has no decision yet" in none.text
        both = client.post("/decide/confirm", data={"actor": "R. Reviewer"})
        assert both.status_code == 409 and "has no decision yet" in both.text


def test_noael_unit_is_per_day_on_decide_and_draft() -> None:
    with TestClient(create_app()) as client:
        client.cookies.set(COOKIE, "en")
        _filled(client)
        one = client.post("/decide/confirm", data={"actor": "R. Reviewer", "sex": "F"}).text
        assert "NOAEL, Females: 20 mg/kg/day" in one


def test_no_screen_has_upper_case_send_terms_outside_the_prose() -> None:
    """The landing and the four screens, every state: only AUC and FDA stay in capitals."""
    allowed = {"AUC", "FDA", "NOAEL"}
    for state in STATE_MARKERS:
        for lang in LANGS:
            shown = re.sub(r"PDS2014-\d+", "", main_copy(rendered_state(state, lang), prose=False))
            assert set(re.findall(r"\b[A-Z]{3,}\b", shown)) <= allowed, (state, lang)
