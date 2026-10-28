import hashlib
import json
import re
import shutil
import sys
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
    assert page.count('class="locked"') == 1
    assert 'href="/step/2"' in page and 'href="/step/3"' in page
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


def test_step2_header_badge_follows_the_recordings_served(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    recorded = _as_bedrock(REAL, tmp_path)
    cases = ((FIXTURES, "fixture", "recorded"), (recorded, "recorded", "fixture"))
    for folder, shown, hidden in cases:
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


def _explore(question: str) -> str:
    with TestClient(create_app()) as client:
        return client.post("/explore/run", data={"question": question}).text


def test_explore_page_has_a_button_for_every_question() -> None:
    from cairn.questions import QUESTIONS

    with TestClient(create_app()) as client:
        page = client.get("/explore").text
    for question_id in QUESTIONS:
        assert f'"question": "{question_id}"' in page
    assert len(QUESTIONS) == 11
    assert "In production" in page and 'class="badge recorded"' in page


@pytest.mark.parametrize("question", ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7", "Q8"])
def test_explore_study_questions_replay_offline(question: str) -> None:
    result = _explore(question)
    assert 'class="badge recorded"' in result
    assert "Rules fired:" in result


@pytest.mark.parametrize("question", ["G1", "G2", "G3"])
def test_explore_guideline_questions_render_quotes_from_quoteref(question: str) -> None:
    result = _explore(question)
    assert 'class="badge recorded"' in result
    assert "<blockquote" in result
    assert "official page" in result and "#page=" in result
    assert "Rules fired: none" in result


def test_explore_rejects_an_unknown_question() -> None:
    with TestClient(create_app()) as client:
        assert client.post("/explore/run", data={"question": "Q99"}).status_code == 422


def test_step3_shows_the_two_fixed_queries_with_ranks_and_the_build_badge() -> None:
    from cairn import retrieval

    with TestClient(create_app()) as client:
        page = client.get("/step/3").text
    fixed = [q for q in retrieval.load_fixed_queries() if q["used_by"] == "nonclinical-summary"]
    assert len(fixed) == 2
    for query in fixed:
        assert query["query"] in page
        top = retrieval.cached_guidance(query["query"]).hits[0]
        assert f"<td>{top.fused_rank}</td>" in page
    assert page.count("<tr>") >= 2 * (1 + 3)  # a header row and three passages per query
    assert 'class="badge computed-at-build"' in page and "COMPUTED AT BUILD" in page
    assert "Lower ranks" in page and "In production" in page
    assert "<th>Lex</th>" in page and "<th>Sem</th>" in page and "<th>Fused</th>" in page


def test_step3_counts_quotes_verbatim_on_the_cited_page() -> None:
    with TestClient(create_app()) as client:
        page = client.get("/step/3").text
    match = re.search(r"Quotes: (\d+) · verbatim on the cited page: (\d+)/(\d+)", page)
    assert match, "no quotes line"
    total, verbatim, of = map(int, match.groups())
    assert total == of == 6
    assert verbatim == total


def test_navigation_unlocks_step_3_and_keeps_the_rest_locked() -> None:
    with TestClient(create_app()) as client:
        page = client.get("/step/3").text
    assert '<a href="/step/3" aria-current="step">3 Explore</a>' in page
    assert page.count('class="locked"') == 1


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
    with TestClient(create_app()) as client:
        page = client.get("/step/3").text
        links = re.findall(r'href="(/highlight/[^"]+)">highlighted page', page)
        assert len(links) == 6
        for link in links:
            assert client.get(link).status_code == 200
    assert page.count("official page") == 6 and "#page=" in page


def test_explore_quotations_link_the_highlighted_page() -> None:
    result = _explore("G2")
    assert "highlighted page" in result and 'href="/highlight/' in result
    assert "official page" in result and "#page=" in result


def test_explore_guideline_quotations_sit_in_the_right_column() -> None:
    result = _explore("G1")
    right = result.split('<div class="col-right card">', 1)[1]
    assert right.count("<blockquote") >= 1
    assert "<blockquote" not in result.split('<div class="col-right card">', 1)[0]


def test_step3_quote_link_and_nav_follow_the_cited_sentence_page() -> None:
    from cairn.highlight import cited_page
    from cairn.passages import stored_passages

    passage = stored_passages()["M4S-2.6-01"]
    assert cited_page(passage, "M4S-2.6-01.s12") == 8 != passage.page_start
    with TestClient(create_app()) as client:
        explore = client.get("/explore").text
        entry = client.get("/highlight/M4S-2.6-01.s12").text
    assert 'aria-current="step"' not in explore
    assert 'aria-current="step"' not in entry


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
    with TestClient(create_app()) as client:
        page = client.get("/step/3").text
    assert "#page=8" in page


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
            assert client.get("/step/3").status_code == 200
            assert client.get("/highlight/M4S-2.6-01.s12").status_code == 200
    assert calls == {"passages": 1, "highlights": 1}
    passages.stored_passages.cache_clear()
    highlight.highlights_by_sentence.cache_clear()


def test_steps_4_and_5_people_decide_and_the_author_cannot_approve() -> None:
    with TestClient(create_app()) as client:
        step4 = client.get("/step/4").text  # starts a thread and follows the redirect
        thread = re.search(r'name="thread" value="([0-9a-f]+)"', step4)
        assert thread and "Acting as: A. Author" in step4 and "disabled" in step4
        id_ = thread.group(1)
        assert "Draft with empty slots" in step4 and "no decision yet" in step4
        client.post("/step/4/example", data={"thread": id_})
        confirmed = client.post("/step/4/confirm", data={"thread": id_, "actor": "R. Reviewer"})
        assert "Acting as: R. Reviewer" in confirmed.text and "Final text" in confirmed.text
        refused = client.post("/step/5/approve", data={"thread": id_, "actor": "A. Author"})
        assert "403 · Authors cannot approve their own draft. Enforced by the API" in refused.text
        done = client.post("/step/5/approve", data={"thread": id_, "actor": "R. Reviewer"})
        assert "Approved by R. Reviewer" in done.text


def _filled_thread(client: TestClient) -> str:
    step4 = client.get("/step/4", follow_redirects=True).text
    match = re.search(r'name="thread" value="([0-9a-f]+)"', step4)
    assert match
    client.post("/step/4/example", data={"thread": match.group(1)})
    return match.group(1)


def test_step_pages_redirect_on_409_and_reject_bad_input() -> None:
    with TestClient(create_app(), follow_redirects=False) as client:
        id_ = _filled_thread(client)
        client.post("/step/4/confirm", data={"thread": id_, "actor": "R. Reviewer"})
        again = client.post("/step/4/example", data={"thread": id_})  # back button, Fill example
        assert again.status_code == 303 and "/step/5?thread=" + id_ in again.headers["location"]
        twice = client.post("/step/5/approve", data={"thread": id_, "actor": "R. Reviewer"})
        assert twice.status_code == 200
        second = client.post("/step/5/approve", data={"thread": id_, "actor": "R. Reviewer"})
        assert second.status_code == 303 and "/step/5?thread=" in second.headers["location"]
        for reply in (
            client.get(f"/step/5?thread={id_}&actor=Mallory"),
            client.post("/step/5/approve", data={"thread": id_, "actor": "Mallory"}),
            client.post("/step/4/confirm", data={"thread": id_, "actor": "Mallory"}),
            client.post("/step/4/decide", data={}),
        ):
            assert reply.status_code == 422
        fresh = _filled_thread(client)
        slot = client.get(f"/api/threads/{fresh}").json()["slots"][0]["slot"]
        bad = client.post(
            "/step/4/decide", data={"thread": fresh, "t_" + slot: "x", "a_" + slot: "x"}
        )
        assert bad.status_code == 422


def test_step4_decide_recomputes_the_fragment_without_the_page() -> None:
    with TestClient(create_app()) as client:
        id_ = _filled_thread(client)
        slots = client.get(f"/api/threads/{id_}").json()["slots"]
        data = {"thread": id_}
        for slot in slots:
            dose = str(max(slot["doses"]))
            data |= {"t_" + slot["slot"]: dose, "a_" + slot["slot"]: dose}
        reply = client.post("/step/4/decide", data=data)
        assert reply.status_code == 200
        assert "NOAEL" in reply.text and "<html" not in reply.text


def _step5_thread(client: TestClient) -> str:
    id_ = _filled_thread(client)
    client.post("/step/4/confirm", data={"thread": id_, "actor": "R. Reviewer"})
    return id_


def test_step5_without_judge_recordings_shows_not_judged_and_the_rules_line() -> None:
    with TestClient(create_app()) as client:
        id_ = _step5_thread(client)
        page = client.get(f"/step/5?thread={id_}&actor=R.%20Reviewer").text
        assert "Judge panel" in page and "never blocks" in page and "0 of " in page
        assert "not judged" in page and "EXAMPLE" in page and "RECORDED" in page
        assert "Rules: 8 of 8 passed, see step 6" in page and f"/step/6?thread={id_}" in page
        assert "Checks" not in page
        done = client.post("/step/5/approve", data={"thread": id_, "actor": "R. Reviewer"})
        assert "Approved by R. Reviewer" in done.text


def test_step5_lists_each_warning_and_the_example_and_approval_still_works(
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
    shutil.copytree("recordings", folder)  # the real draft, no judge files yet
    for name in ("cairn.web.people", "cairn.web.threads"):
        monkeypatch.setattr(sys.modules[name], "RECORDINGS_DIR", folder)
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
        id_ = _step5_thread(client)
        page = client.get(f"/step/5?thread={id_}&actor=R.%20Reviewer").text
        assert "warning: magnitude" in page and "Too strong." in page
        assert "warning: causal" in page and "EXAMPLE" in page and "It claims cause." in page
        done = client.post("/step/5/approve", data={"thread": id_, "actor": "R. Reviewer"})
        assert "Approved by R. Reviewer" in done.text


def test_step6_shows_rules_chain_status_and_the_production_note() -> None:
    with TestClient(create_app(), follow_redirects=False) as client:
        assert client.get("/step/6").headers["location"] == "/step/4"
        id_ = _filled_thread(client)
        early = client.get(f"/step/6?thread={id_}")
        assert early.status_code == 303 and early.headers["location"] == f"/step/4?thread={id_}"
        client.post("/step/4/confirm", data={"thread": id_, "actor": "R. Reviewer"})
        page = client.get(f"/step/6?thread={id_}").text
        assert 'class="badge real"' in page and "passed" in page and "fired" not in page
        assert page.count("<tr>") == 9 and "Audit chain: " in page and "entries, verified." in page
        assert "not a validated or external log" in page
        assert "In production" in page and "external append-only log" in page
        assert client.get(f"/step/6?thread={id_}&actor=Mallory").status_code == 422
