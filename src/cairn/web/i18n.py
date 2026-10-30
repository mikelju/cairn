"""UI string catalogue: our own interface text in Spanish and English, no new dependency.

Study data, guideline passages and recorded model prose never pass through here.
The locale is the `lang` query parameter, remembered in a cookie; the default is Spanish.
"""

from typing import Any
from urllib.parse import parse_qs

from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

DEFAULT_LOCALE = "es"
COOKIE = "cairn_lang"
COOKIE_MAX_AGE = 60 * 60 * 24 * 365

EN: dict[str, str] = {
    "html_lang": "en",
    "brand": "Cairn",
    "nav_steps": "Steps",
    "step_1": "Validate",
    "step_2": "Ask",
    "step_3": "Explore",
    "step_4": "Analyse",
    "step_5": "Draft",
    "step_6": "Check",
    "step_7": "Review",
    "role": "Role: Study toxicologist (simulated)",
    "acting_as": "Acting as:",
    "lang_label": "Language",
    "footer_note": "Public sample data · fictional compound · not GxP-validated",
    "footer_build": "commit",
    "footer_snapshot": "snapshot",
}

ES: dict[str, str] = {
    "html_lang": "es",
    "brand": "Cairn",
    "nav_steps": "Pasos",
    "step_1": "Validar",
    "step_2": "Preguntar",
    "step_3": "Explorar",
    "step_4": "Analizar",
    "step_5": "Redactar",
    "step_6": "Comprobar",
    "step_7": "Revisar",
    "role": "Rol: toxicólogo del estudio (simulado)",
    "acting_as": "Actuando como:",
    "lang_label": "Idioma",
    "footer_note": "Datos públicos de ejemplo · compuesto ficticio · no validado GxP",
    "footer_build": "commit",
    "footer_snapshot": "instantánea",
}

CATALOGUES: dict[str, dict[str, str]] = {"en": EN, "es": ES}
LOCALES = tuple(CATALOGUES)


def locale_of(request: Request) -> str:
    """The query parameter wins, then the cookie, then the default."""
    for chosen in (request.query_params.get("lang"), request.cookies.get(COOKIE)):
        if chosen in CATALOGUES:
            return chosen
    return DEFAULT_LOCALE


def context(request: Request, current: int | None = None) -> dict[str, Any]:
    """Template variables for the shell: the catalogue and the toggle links."""
    locale = locale_of(request)
    if request.method == "GET":
        base = request.url
    else:  # a POST page has no GET twin: toggle on the step it shows
        base = request.url.replace(path=f"/step/{current}" if current else "/", query="")
    links = {code: f"{base.path}?{base.include_query_params(lang=code).query}" for code in LOCALES}
    return {"t": CATALOGUES[locale], "locale": locale, "lang_links": links}


class LocaleCookie:
    """ASGI middleware: remember a valid `lang` query parameter in a cookie, redirects included."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        query = parse_qs(scope.get("query_string", b"").decode("latin-1"))
        chosen = (query.get("lang") or [""])[0]
        if chosen not in CATALOGUES:
            await self.app(scope, receive, send)
            return

        async def send_with_cookie(message: Message) -> None:
            if message["type"] == "http.response.start":
                cookie = f"{COOKIE}={chosen}; Path=/; Max-Age={COOKIE_MAX_AGE}; SameSite=Lax"
                message["headers"] = [*message.get("headers", []), (b"set-cookie", cookie.encode())]
            await send(message)

        await self.app(scope, receive, send_with_cookie)
