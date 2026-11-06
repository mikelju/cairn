"""Word counter of a rendered <main>; only the static mockups of docs/plans still use it."""

import re
from html.parser import HTMLParser

WORD_CAP = 60
SENTENCE_WORD_CAP = 25
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
        unit = "answer-unit" in (values.get("class") or "").split()
        in_closed = bool(self.stack) and self.stack[-1][0] == "details-closed" and tag != "summary"
        if (tag == "tbody" or unit) and self.in_main and not self._hidden() and not in_closed:
            self.words += 1
            hide = True
        if in_closed:
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


def rendered_problems(html: str, cap: int = WORD_CAP) -> list[str]:
    problems = []
    if rendered_words(html) > cap:
        problems.append("step words")
    lede = rendered_lede(html)
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", lede) if s]
    if len(sentences) != 1 or len(lede.split()) > SENTENCE_WORD_CAP:
        problems.append("lede")
    return problems
