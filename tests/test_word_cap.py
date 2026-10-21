import re

import pytest

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
    assert 1 in steps
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
