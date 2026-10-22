"""Design system checks for the web layer: tokens, no inline styles, no external resources."""

import hashlib
import json
import re
from typing import Any
from urllib.parse import urljoin

import pytest
from fastapi.testclient import TestClient

from cairn.app import create_app
from cairn.web import HERE, templates

STATIC = HERE / "static"
REAL_RECORDINGS = HERE.parents[2] / "recordings"
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


COMPONENTS = HERE / "templates" / "_components.html"
PAGE_TEMPLATES = [t for t in TEMPLATES if t.name not in ("_components.html", "base.html")]
LEAKS = {
    "table": re.compile(r"<table\b", re.IGNORECASE),
    "badge": re.compile(r"class=\"[^\"]*\bbadge\b"),
    "trace": re.compile(r"class=\"[^\"]*\btrace\b"),
    "callout": re.compile(r"class=\"[^\"]*\bcallout\b"),
}
BADGE_KINDS = ["REAL", "RECORDED", "SIMULATED", "FIXTURE"]


def component_leaks(template_text: str) -> list[str]:
    """Component markup written by hand in a page template instead of through a macro."""
    return [name for name, pattern in LEAKS.items() if pattern.search(template_text)]


def badge_css_problems(css: str) -> list[str]:
    """Kinds whose rule does not set a distinct look (fill or border style) and glyph."""
    looks: dict[str, tuple[str, str, str]] = {}
    glyphs: dict[str, str] = {}
    for selector, body in RULE.findall(_strip_comments(css)):
        found = re.fullmatch(r"\s*\.badge\.(\w+?)(::before)?\s*", selector)
        if not found:
            continue
        kind, is_glyph = found.group(1), bool(found.group(2))
        if is_glyph:
            content = re.search(r"content\s*:\s*([^;]+);?", body)
            glyphs[kind] = content.group(1).strip() if content else ""
        else:
            fill = re.search(r"background\s*:\s*([^;]+)", body)
            style = re.search(r"border-style\s*:\s*([^;]+)", body)
            colour = re.search(r"border-color\s*:\s*([^;]+)", body)
            looks[kind] = (
                fill.group(1).strip() if fill else "",
                style.group(1).strip() if style else "solid",
                colour.group(1).strip() if colour else "",
            )
    problems = []
    for kind in (k.lower() for k in BADGE_KINDS):
        if kind not in looks:
            problems.append(f"no rule for {kind}")
        if not glyphs.get(kind):
            problems.append(f"no glyph for {kind}")
    if len(set(looks.values())) < len(looks):
        problems.append("two kinds share the same fill, border style and colour")
    if len(set(glyphs.values())) < len(glyphs):
        problems.append("two kinds share a glyph")
    if len({look[1] for look in looks.values()}) < 3:
        problems.append("fewer than three border styles")
    return problems


def test_shared_components_exist_and_replace_anatomy() -> None:
    assert COMPONENTS.is_file()
    assert not (HERE / "templates" / "_anatomy.html").exists()
    text = COMPONENTS.read_text(encoding="utf-8")
    for macro in (
        "shell_header",
        "shell_footer",
        "step_header",
        "badge",
        "badge_meta",
        "data_table",
        "trace",
        "evidence_panel",
        "callout",
        "disclosure",
        "in_production",
    ):
        assert re.search(rf"\{{% macro {macro}\(", text), macro
    for name, pattern in LEAKS.items():
        assert pattern.search(text), name
    assert "<details" in text


def test_shared_components_pages_write_no_component_markup() -> None:
    assert PAGE_TEMPLATES
    for template in PAGE_TEMPLATES:
        text = template.read_text(encoding="utf-8")
        assert component_leaks(text) == [], template.name
        assert "_anatomy" not in text, template.name


def test_shared_components_failing_sample() -> None:
    assert component_leaks("<table><tr><td>x</td></tr></table>") == ["table"]
    assert component_leaks('<span class="badge real">REAL</span>') == ["badge"]
    assert component_leaks('<p class="trace">a</p><div class="callout stale">b</div>') == [
        "trace",
        "callout",
    ]
    assert component_leaks("{{ a.data_table(h, rows) }}") == []


def test_shared_components_render_through_the_macros() -> None:
    module: Any = templates.get_template("_components.html").module
    table = str(module.data_table(["A", "B"], [["x", "not examined"]], new=True))
    assert '<tr class="new">' in table and 'class="not-examined">not examined' in table
    assert "<thead>" in table and "<tbody>" in table
    assert "Trace: a -&gt; b" in str(module.trace("a -> b"))


def test_badge_each_kind_renders_its_word_and_a_distinct_class() -> None:
    module: Any = templates.get_template("_components.html").module
    classes = set()
    for kind in BADGE_KINDS:
        html = str(module.badge(kind))
        assert f">{kind}</span>" in html
        found = re.search(r'class="badge (\w+)"', html)
        assert found is not None
        classes.add(found.group(1))
    assert len(classes) == 4


def test_badge_css_gives_each_kind_a_different_look_and_glyph() -> None:
    assert badge_css_problems(CSS_PATH.read_text(encoding="utf-8")) == []


def test_badge_css_failing_sample() -> None:
    same = (
        ".badge.real { background: var(--a); }\n.badge.recorded { background: var(--a); }\n"
        ".badge.simulated { background: var(--a); }\n.badge.fixture { background: var(--a); }\n"
        '.badge.real::before { content: "x"; }\n.badge.recorded::before { content: "x"; }'
    )
    problems = badge_css_problems(same)
    assert "two kinds share a glyph" in problems
    assert "two kinds share the same fill, border style and colour" in problems
    assert "no glyph for simulated" in problems


def test_badge_recorded_keeps_its_metadata_and_simulated_its_production_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CAIRN_RECORDINGS", str(REAL_RECORDINGS))
    recorded = json.loads((REAL_RECORDINGS / "q2.json").read_text(encoding="utf-8"))
    with TestClient(create_app()) as client:
        result = client.post("/step/2/run", data={"question": "Q2"}).text
        step1 = client.get("/step/1").text
    meta = re.search(r'<p class="meta">(.*?)</p>', result, flags=re.S)
    assert meta is not None and 'class="badge recorded"' in meta.group(1)
    assert str(recorded["date"]) in meta.group(1) and str(recorded["region"]) in meta.group(1)
    assert "opus-4-6" in meta.group(1)
    assert re.search(r"\| \d+\.\d s \|", meta.group(1)) and "USD" in meta.group(1)
    assert 'class="badge simulated"' in step1 and "In production" in step1


# --- Contrast and focus (C7) ---

ROOT_BLOCK = re.compile(r":root\s*\{([^{}]*)\}")
HEX_TOKEN = re.compile(r"--([\w-]+)\s*:\s*(#[0-9a-fA-F]{6})\s*;")
BODY = 4.5  # body text
LARGE = 3.0  # text of 18 px and above or 14 px bold, control borders, focus outline

# (foreground token, background token, minimum ratio, where it is used)
CONTRAST_PAIRS: list[tuple[str, str, float, str]] = [
    ("ink", "paper", BODY, "body text"),
    ("ink", "surface", BODY, "cards, tables, callouts"),
    ("muted", "paper", BODY, ".meta, .prod, .lede on the page"),
    ("muted", "surface", BODY, "header, footer, legend cards, evidence"),
    ("muted", "not-examined", BODY, "td.not-examined"),
    ("accent", "paper", BODY, "summary toggle, step links"),
    ("accent", "surface", BODY, ".brand, summary"),
    ("on-accent", "accent", BODY, ".num, button"),
    ("on-accent", "real", BODY, ".badge.real"),
    ("recorded", "recorded-tint", BODY, ".badge.recorded"),
    ("simulated", "surface", BODY, ".badge.simulated"),
    ("fixture", "fixture-tint", BODY, ".badge.fixture (hatch tint)"),
    ("fixture", "surface", BODY, ".badge.fixture (hatch white)"),
    ("ink", "accent-tint", BODY, ".callout.rules"),
    ("ink", "block-tint", BODY, ".callout.blocked"),
    ("ink", "warning-tint", BODY, ".callout.stale"),
    ("ink", "new-row", BODY, "tr.new td"),
    ("control-border", "paper", LARGE, "control and rule borders"),
    ("control-border", "surface", LARGE, "select border, table header rule"),
    ("accent", "paper", LARGE, "focus outline on paper"),
    ("accent", "surface", LARGE, "focus outline on surface"),
    ("accent", "accent-tint", LARGE, "focus outline on tinted callouts"),
]


def root_colours(css: str) -> dict[str, str]:
    match = ROOT_BLOCK.search(_strip_comments(css))
    assert match is not None
    return {name.removeprefix("color-"): value for name, value in HEX_TOKEN.findall(match.group(1))}


def _luminance(hex_colour: str) -> float:
    channels = [int(hex_colour[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast_ratio(foreground: str, background: str) -> float:
    a, b = sorted((_luminance(foreground), _luminance(background)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def contrast_failures(
    colours: dict[str, str], pairs: list[tuple[str, str, float, str]] = CONTRAST_PAIRS
) -> list[str]:
    failures: list[str] = []
    for fg, bg, minimum, where in pairs:
        if fg not in colours or bg not in colours:
            failures.append(f"missing token for {fg}/{bg} ({where})")
            continue
        ratio = contrast_ratio(colours[fg], colours[bg])
        if ratio < minimum:
            failures.append(f"{fg} on {bg} is {ratio:.2f}:1, needs {minimum}:1 ({where})")
    return failures


def test_contrast_every_pair_in_use_meets_its_threshold() -> None:
    colours = root_colours(CSS_PATH.read_text())
    assert contrast_failures(colours) == []


def test_contrast_known_ratios() -> None:
    assert contrast_ratio("#000000", "#ffffff") == pytest.approx(21.0)
    assert contrast_ratio("#ffffff", "#ffffff") == pytest.approx(1.0)


def test_contrast_failing_sample() -> None:
    bad = {"ink": "#cccccc", "paper": "#ffffff", "control-border": "#eeeeee", "surface": "#ffffff"}
    failures = contrast_failures(
        bad,
        [
            ("ink", "paper", BODY, "body"),
            ("control-border", "surface", LARGE, "border"),
            ("ink", "gone", BODY, "missing"),
        ],
    )
    assert len(failures) == 3
    assert "ink on paper" in failures[0] and "missing token" in failures[2]


def focus_gaps(css: str) -> list[str]:
    """Interactive selectors with no :focus-visible rule that sets an outline."""
    selectors: set[str] = set()
    for match in RULE.finditer(_strip_comments(css)):
        if "outline" not in match.group(2):
            continue
        for sel in match.group(1).split(","):
            sel = sel.strip()
            if sel.endswith(":focus-visible"):
                selectors.add(sel.removesuffix(":focus-visible"))
    wanted = ("a", "button", "select", "input", "summary", "[tabindex]")
    return [s for s in wanted if s not in selectors]


def test_focus_visible_outline_on_every_interactive_element() -> None:
    assert focus_gaps(CSS_PATH.read_text()) == []


def test_focus_visible_failing_sample() -> None:
    sample = (
        "a:focus-visible, button:focus-visible { outline: 2px solid red; } "
        "select:focus-visible { color: red; }"
    )
    assert focus_gaps(sample) == ["select", "input", "summary", "[tabindex]"]


def test_narrow_width_rule_collapses_grids_to_one_column() -> None:
    css = _strip_comments(CSS_PATH.read_text())
    match = re.search(r"@media\s*\(max-width:\s*(\d+)px\)\s*\{(.*)\}\s*$", css, flags=re.S)
    assert match is not None and 800 <= int(match.group(1)) <= 960
    assert ".two-col" in match.group(2) and "grid-template-columns" in match.group(2)
    assert not COLOUR_LITERAL.search(match.group(2))
