"""The counter that still checks the static mockups (change 004 D23: the app itself has no cap)."""

from main_counter import WORD_CAP, rendered_problems, rendered_words


def _page(body: str, lede: str = "One short sentence.") -> str:
    lede_p = f'<p class="lede">{lede}</p>'
    return f"<header>chrome words</header><main>{lede_p}{body}</main><footer>more chrome</footer>"


def test_rendered_counter_ignores_header_and_footer() -> None:
    assert rendered_words(_page("<p>a b c</p>")) == 3 + 3


def test_rendered_counter_fails_an_over_cap_main_area() -> None:
    body = "<p>" + " ".join(["word"] * WORD_CAP) + "</p>"
    assert rendered_problems(_page(body)) == ["step words"]


def test_rendered_counter_counts_a_table_body_as_one_word() -> None:
    rows = "<tr><td>" + " ".join(["cell"] * 50) + "</td></tr>" * 3
    table = f"<table><thead><tr><th>Rule Animal</th></tr></thead><tbody>{rows}</tbody></table>"
    assert rendered_words(_page(table, lede="Lede.")) == 1 + 2 + 1


def test_rendered_counter_counts_an_answer_unit_as_one_word() -> None:
    text = " ".join(["ans"] * 50)
    unit = (
        f'<article class="answer-panel"><p class="answer-unit">{text}</p>'
        "<p>one two three</p></article>"
    )
    assert rendered_words(_page(unit, lede="Lede.")) == 1 + 1 + 3  # the sibling is counted


def test_rendered_counter_counts_a_closed_details_by_its_summary() -> None:
    inner = "<p>" + " ".join(["hidden"] * 40) + "</p>"
    closed = f"<details><summary>Show more</summary>{inner}</details>"
    opened = f"<details open><summary>Show more</summary>{inner}</details>"
    assert rendered_words(_page(closed, lede="Lede.")) == 1 + 2
    assert rendered_words(_page(opened, lede="Lede.")) == 1 + 2 + 40


def test_rendered_counter_counts_options_and_drops_scripts() -> None:
    body = "<select><option>Q1 first</option><option>Q2</option></select><script>x y z</script>"
    assert rendered_words(_page(body, lede="Lede.")) == 1 + 3


def test_rendered_lede_must_be_one_short_sentence() -> None:
    assert rendered_problems(_page("")) == []
    assert rendered_problems(_page("", lede="One. Two.")) == ["lede"]
    assert rendered_problems(_page("", lede=" ".join(["word"] * 26) + ".")) == ["lede"]
    assert rendered_problems(_page("", lede=" ".join(["word"] * 25) + ".")) == []
