"""Design system checks for the web layer: tokens, no inline styles, no external resources."""

import hashlib
import re
from urllib.parse import urljoin

from fastapi.testclient import TestClient

from cairn.app import create_app
from cairn.web import HERE

STATIC = HERE / "static"
CSS_PATH = STATIC / "cairn.css"
TEMPLATES = sorted((HERE / "templates").glob("*.html"))

COLOUR_LITERAL = re.compile(
    r"#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch)\(|"
    r"(?<![-\w])(?:white|black|red|green|blue|gray|grey|orange|yellow|purple)(?![-\w])"
)
RAW_FONT_SIZE = re.compile(r"(?<![-\w])font-size\s*:(?!\s*var\()")
FONT_FAMILY = re.compile(r"(?<![-\w])font-family\s*:(?!\s*var\()")
FONT_SHORTHAND = re.compile(r"(?<![-\w])font\s*:(?!\s*inherit\b)")
RULE = re.compile(r"([^{}]+)\{([^{}]*)\}")
URL = re.compile(r"url\(\s*[\"']?([^\"')]+)[\"']?\s*\)")
EXTERNAL = re.compile(r"https?://", re.IGNORECASE)
INLINE_STYLE = re.compile(r"<[^>]+\sstyle\s*=", re.IGNORECASE)


def _strip_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)


def design_token_violations(css: str) -> list[str]:
    """Return the problems found outside the :root block of a stylesheet."""
    problems: list[str] = []
    for match in RULE.finditer(_strip_comments(css)):
        selector, body = match.group(1).strip(), match.group(2)
        if selector == ":root":
            continue
        is_font_face = selector == "@font-face"
        if COLOUR_LITERAL.search(body):
            problems.append(f"colour literal in {selector}")
        if RAW_FONT_SIZE.search(body):
            problems.append(f"raw font size in {selector}")
        if not is_font_face and (FONT_FAMILY.search(body) or FONT_SHORTHAND.search(body)):
            problems.append(f"font family in {selector}")
    return problems


def external_references(text: str) -> list[str]:
    return EXTERNAL.findall(text)


def unresolved_css_urls(css: str, client: TestClient) -> list[str]:
    """CSS url() targets that are not a file under static/ served with 200."""
    bad: list[str] = []
    for ref in URL.findall(_strip_comments(css)):
        served = urljoin("/static/cairn.css", ref)
        target = STATIC / served.removeprefix("/static/")
        if (
            not served.startswith("/static/")
            or not target.is_file()
            or client.get(served).status_code != 200
        ):
            bad.append(ref)
    return bad


def test_design_tokens_single_root_block() -> None:
    css = _strip_comments(CSS_PATH.read_text())
    assert len(re.findall(r":root\s*\{", css)) == 1
    assert design_token_violations(css) == []


def test_design_tokens_define_the_adopted_values() -> None:
    css = CSS_PATH.read_text()
    for token, value in {
        "--color-paper": "#fbfaf7",
        "--color-ink": "#1b2430",
        "--color-accent": "#0e4d5c",
        "--color-recorded": "#1d4f91",
        "--color-block": "#a12622",
        "--text-2xs": "11px",
        "--text-2xl": "40px",
        "--space-7": "48px",
        "--radius-md": "8px",
    }.items():
        assert re.search(rf"{token}:\s*{re.escape(value)}\s*;", css), token
    assert "IBM Plex Sans" in css and "IBM Plex Mono" in css
    assert "system-ui" in css


def test_design_tokens_failing_sample() -> None:
    bad = ":root { --c: #fff; }\n.x { color: #123456; font-size: 14px; font-family: serif; }"
    assert design_token_violations(bad) == [
        "colour literal in .x",
        "raw font size in .x",
        "font family in .x",
    ]
    assert design_token_violations(".y { background: rgb(1, 2, 3); font: 14px serif; }")
    good = ".z { color: var(--color-ink); font-size: var(--text-md); }"
    assert design_token_violations(good) == []


def test_design_tokens_templates_have_no_inline_style() -> None:
    assert TEMPLATES
    for template in TEMPLATES:
        assert not INLINE_STYLE.search(template.read_text()), template.name
        assert "<style" not in template.read_text().lower(), template.name
    assert INLINE_STYLE.search('<p style="color:red">x</p>')


def test_no_external_resources_in_templates_and_css() -> None:
    for path in [CSS_PATH, *TEMPLATES]:
        assert external_references(path.read_text()) == [], path.name


def test_no_external_resources_failing_sample() -> None:
    assert external_references('<link href="https://cdn.example/x.css">')
    assert external_references("@import url(http://fonts.example/x.css);")


def test_no_external_resources_css_urls_resolve_to_served_static_files() -> None:
    css = CSS_PATH.read_text()
    refs = URL.findall(css)
    assert len(refs) == 4
    with TestClient(create_app()) as client:
        assert unresolved_css_urls(css, client) == []
        assert unresolved_css_urls("a { background: url(fonts/missing.woff2); }", client) == [
            "fonts/missing.woff2"
        ]
        assert unresolved_css_urls("a { background: url(../outside.png); }", client) == [
            "../outside.png"
        ]


def test_fonts_are_documented_and_small() -> None:
    fonts = STATIC / "fonts"
    notice = (fonts / "NOTICE.txt").read_text()
    files = sorted(fonts.glob("*.woff2"))
    assert len(files) == 4
    assert (fonts / "OFL.txt").read_text().count("SIL Open Font License") >= 1
    for file in files:
        assert hashlib.sha256(file.read_bytes()).hexdigest() in notice, file.name
    total = sum(file.stat().st_size for file in files)
    assert total < 250 * 1024
    print(f"font bytes total: {total}")
