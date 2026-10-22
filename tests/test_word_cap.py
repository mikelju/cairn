import re
from html.parser import HTMLParser

import pytest
from fastapi.testclient import TestClient

from cairn.app import create_app
from cairn.web import HERE

STEP_WORD_CAP = 93
SENTENCE_WORD_CAP = 25


def visible_words(html: str) -> list[str]:
    """Words a visitor reads: Jinja tags dropped, expressions count as one word, tags stripped."""
    text = re.sub(r"\{%.*?%\}|\{#.*?#\}", " ", html, flags=re.S)
    text = re.sub(r"\{\{.*?\}\}", " x ", text, flags=re.S)
    text = re.sub(r"<(script|style)\b.*?</\1>", " ", text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return text.split()


def over_cap(html: str) -> list[str]:
    """Reasons a step breaks the cap: too many words, or a lede that is not one short sentence."""
    problems = []
    if len(visible_words(html)) > STEP_WORD_CAP:
        problems.append("step words")
    ledes = re.findall(r'class="lede">(.*?)</p>', html, flags=re.S)
    ledes += re.findall(r'a\.step\(\d+, "[^"]*", "[^"]*", "([^"]*)"\)', html)
    for lede in ledes:
        sentences = [s for s in re.split(r"(?<=[.!?])\s", lede.strip()) if s]
        if len(sentences) > 1 or len(visible_words(lede)) > SENTENCE_WORD_CAP:
            problems.append("lede")
    return problems


def step_sources() -> dict[int, str]:
    folder = HERE / "templates"
    steps: dict[int, str] = {}
    for path in sorted(folder.glob("step[0-9]*.html")):
        number = int(re.match(r"step(\d+)", path.name).group(1))  # type: ignore[union-attr]
        steps[number] = steps.get(number, "") + path.read_text(encoding="utf-8")
    return steps


def test_each_step_template_is_within_the_word_cap() -> None:
    steps = step_sources()
    assert 1 in steps and 2 in steps
    for number, html in steps.items():
        assert over_cap(html) == [], f"step {number} is over the cap"


def test_cap_fails_on_an_over_cap_sample() -> None:
    long_lede = " ".join(["word"] * 30)
    assert over_cap(f'<p class="lede">{long_lede}.</p>') == ["lede"]
    assert over_cap('<p class="lede">One. Two.</p>') == ["lede"]
    assert over_cap(f'{{% call a.step(2, "T", "REAL", "{long_lede}.") %}}') == ["lede"]
    body = "<p>" + " ".join(["word"] * (STEP_WORD_CAP + 1)) + "</p>"
    assert over_cap(body) == ["step words"]


@pytest.mark.parametrize("sample", ["{{ a }} {% if b %}hi{% endif %}", "<style>x y z</style>ok"])
def test_visible_words_ignores_markup(sample: str) -> None:
    assert len(visible_words(sample)) <= 2


# Rendered-page counter (plan "Counting rule"): what a visitor reads inside <main>.
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "wbr"}
DROPPED_TAGS = {"script", "style", "template"}


class _MainCounter(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.words = 0
        self.lede = ""
        self.stack: list[tuple[str, bool, bool]] = []  # tag, hides its text, is the lede
        self.in_main = False

    def _hidden(self) -> bool:
        return any(hide for _, hide, _ in self.stack)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in VOID_TAGS:
            return
        values = dict(attrs)
        if tag == "main":
            self.in_main = True
        hide = tag in DROPPED_TAGS
        if tag == "tbody" and self.in_main and not self._hidden():
            self.words += 1
            hide = True
        if self.stack and self.stack[-1][0] == "details-closed" and tag != "summary":
            hide = True
        name = tag
        if tag == "details":
            name = "details" if "open" in values else "details-closed"
        is_lede = "lede" in (values.get("class") or "").split()
        self.stack.append((name, hide, is_lede))

    def handle_endtag(self, tag: str) -> None:
        if tag in VOID_TAGS:
            return
        names = (tag, "details-closed") if tag == "details" else (tag,)
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] in names:
                del self.stack[index:]
                break
        if tag == "main":
            self.in_main = False

    def handle_data(self, data: str) -> None:
        if not self.in_main or self._hidden():
            return
        words = data.split()
        self.words += len(words)
        if any(lede for _, _, lede in self.stack):
            self.lede += " " + data


def rendered_words(html: str) -> int:
    """Words in the rendered <main>; a tbody is one word, a closed details its summary."""
    counter = _MainCounter()
    counter.feed(html)
    return counter.words


def rendered_lede(html: str) -> str:
    counter = _MainCounter()
    counter.feed(html)
    return " ".join(counter.lede.split())


def rendered_problems(html: str) -> list[str]:
    problems = []
    if rendered_words(html) > STEP_WORD_CAP:
        problems.append("step words")
    lede = rendered_lede(html)
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", lede) if s]
    if len(sentences) != 1 or len(lede.split()) > SENTENCE_WORD_CAP:
        problems.append("lede")
    return problems


def with_result(page: str, fragment: str) -> str:
    """The GET page with the POST fragment inside #result, as HTMX places it."""
    return page.replace('<div id="result"></div>', f'<div id="result">{fragment}</div>')


def rendered_state(name: str) -> str:
    with TestClient(create_app()) as client:
        if name == "landing":
            return client.get("/").text
        page = client.get("/step/1").text
        if name == "step1_before":
            return page
        data = {"inject": "on"} if name == "step1_injected" else None
        return with_result(page, client.post("/step/1/run", data=data).text)


def _page(body: str, lede: str = "One short sentence.") -> str:
    lede_p = f'<p class="lede">{lede}</p>'
    return f"<header>chrome words</header><main>{lede_p}{body}</main><footer>more chrome</footer>"


def test_rendered_counter_ignores_header_and_footer() -> None:
    assert rendered_words(_page("<p>a b c</p>")) == 3 + 3


def test_rendered_counter_fails_an_over_cap_main_area() -> None:
    body = "<p>" + " ".join(["word"] * STEP_WORD_CAP) + "</p>"
    assert rendered_problems(_page(body)) == ["step words"]


def test_rendered_counter_counts_a_table_body_as_one_word() -> None:
    rows = "<tr><td>" + " ".join(["cell"] * 50) + "</td></tr>" * 3
    table = f"<table><thead><tr><th>Rule Animal</th></tr></thead><tbody>{rows}</tbody></table>"
    assert rendered_words(_page(table, lede="Lede.")) == 1 + 2 + 1


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


def test_result_fragment_lands_inside_the_result_element() -> None:
    page = _page('<div id="result"></div>')
    assert rendered_words(with_result(page, "<p>a b</p>")) == rendered_words(page) + 2


@pytest.mark.parametrize("state", ["landing", "step1_before", "step1_after", "step1_injected"])
def test_word_cap_rendered(state: str) -> None:
    html = rendered_state(state)
    print(state, rendered_words(html), rendered_lede(html))
    assert rendered_problems(html) == [], state
