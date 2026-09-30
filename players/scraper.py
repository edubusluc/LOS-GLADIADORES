"""
Descarga de los puntos SNP de los jugadores de un equipo desde snpgalaxy.com.

Entra con la cuenta de SNP del capitán, navega como él (Series Nacionales → España →
Mis equipos → el equipo) y lee la tabla de jugadores (todas las páginas). Devuelve una lista de ``{"name": ..., "score": ...}``
con el nombre tal y como aparece en SNP; el cruce con nuestros jugadores está en
players/snp.py.
"""
import base64
import binascii
import re

from playwright.sync_api import Error as PlaywrightError, sync_playwright

LOGIN_URL = "https://snpgalaxy.com/usuario/login"
LOGIN_BUTTONS = ('input[type="submit"][value="Iniciar Sesión"]', 'button[type="submit"]:has-text("Iniciar Sesión")',
                 'input[type="submit"]', 'button[type="submit"]')
USERNAME_FIELDS = ('input[name="email"]', 'input[name="usuario"]', 'input[name="username"]',
                   'input[type="email"]', 'input[type="text"]')
RESULTS_TABLE = "table.results"
NEXT_PAGE = 'a.pag_numerada.page-link[num_pagina="{}"]'
SERIES_MENU = 'a.menu-link.menu-toggle:has([data-i18n="Series Nacionales"])'
SPAIN_LINK = 'a.menu-link:has([data-i18n="España"])'
MY_TEAMS = '.card-equipos'
TEAM_LINKS = '#form_equipos table.results tbody td:first-child a[href*="/equipo/view/"]'
MAX_PAGES = 30
TIMEOUT_MS = 30_000


class SnpScrapeError(Exception):
    """Error que se puede enseñar tal cual al administrador del club."""


def parse_team_id(value):
    """
    Número del equipo en SNP a partir de lo que pegue el administrador: el número
    (4380), la página del equipo (.../equipo/view/4380) o un enlace de snpgalaxy.com
    que la lleve codificada en base64 tras ``u_:``. None si no se reconoce.
    """
    value = (value or "").strip()
    if value.isdigit():
        return value
    candidates = [value]
    encoded = re.search(r"/u_:([A-Za-z0-9+/=_-]+)", value)
    if encoded:
        text = encoded.group(1)
        try:
            candidates.append(base64.b64decode(text + "=" * (-len(text) % 4), altchars=b"+/").decode())
        except (binascii.Error, UnicodeDecodeError):
            pass
    for candidate in candidates:
        match = re.search(r"/equipo/view/(\d+)", candidate)
        if match:
            return match.group(1)
    return None


def parse_score(text):
    """'1.234,5' -> 1234.5; '12,5 / 3' -> 12.5; vacío o ilegible -> 0.0."""
    text = (text or "").split("/")[0].strip()
    if not text:
        return 0.0
    try:
        return float(text.replace(".", "").replace(",", "."))
    except ValueError:
        return 0.0


def _first_visible(page, selectors):
    for selector in selectors:
        element = page.query_selector(selector)
        if element and element.is_visible():
            return element
    return None


def _login(page, username, password):
    page.goto(LOGIN_URL, timeout=TIMEOUT_MS)
    user_field = _first_visible(page, USERNAME_FIELDS)
    password_field = page.query_selector('input[type="password"]')
    if not user_field or not password_field:
        raise SnpScrapeError("No se ha encontrado el formulario de inicio de sesión de SNP.")
    user_field.fill(username)
    password_field.fill(password)
    button = _first_visible(page, LOGIN_BUTTONS)
    if not button:
        raise SnpScrapeError("No se ha encontrado el botón «Iniciar Sesión» de SNP.")
    button.click()
    page.wait_for_load_state("load", timeout=TIMEOUT_MS)
    page.wait_for_timeout(2000)
    still_on_login = "/usuario/login" in page.url and page.query_selector('input[type="password"]')
    if still_on_login:
        raise SnpScrapeError("SNP no ha aceptado el usuario o la contraseña.")


def _frame_label(frame, page):
    if frame == page.main_frame:
        return "la página principal"
    return f"el iframe «{frame.name or '(sin nombre)'}» ({frame.url})"


def _find(page, selector, what, log, url_pattern=None, timeout_ms=TIMEOUT_MS):
    """
    Busca ``selector`` visible en la página y en todos sus iframes (SNP carga parte de
    su contenido dentro de iframes) hasta que aparezca. Devuelve (frame, elemento).
    ``url_pattern`` limita la búsqueda a los frames cuya dirección encaje.
    """
    waited = 0
    while True:
        for frame in page.frames:
            if url_pattern and not re.search(url_pattern, frame.url):
                continue
            try:
                element = frame.query_selector(selector)
                if element and element.is_visible():
                    log(f"Encontrado en {_frame_label(frame, page)}: {what}.")
                    return frame, element
            except PlaywrightError:
                continue  # el frame se está recargando
        if waited >= timeout_ms:
            frames = "; ".join(_frame_label(f, page) for f in page.frames)
            log(f"No se encuentra {what}. Frames en la página: {frames}")
            raise SnpScrapeError(f"No se ha encontrado {what} en SNP (ni en la página ni en sus iframes).")
        page.wait_for_timeout(500)
        waited += 500


def _open_team_page(page, team_id, log):
    """
    Series Nacionales → España → Mis equipos → el equipo, como lo haría el capitán.
    Devuelve el frame donde está la tabla de jugadores.
    """
    _find(page, SERIES_MENU, "el menú «Series Nacionales»", log)[1].click()
    _find(page, SPAIN_LINK, "la opción «España»", log)[1].click()
    page.wait_for_load_state("load", timeout=TIMEOUT_MS)
    _find(page, MY_TEAMS, "el botón «Mis equipos»", log)[1].click()
    frame, _ = _find(page, TEAM_LINKS, "la tabla «Mis equipos»", log)

    teams = {}
    for link in frame.query_selector_all(TEAM_LINKS):
        found = re.search(r"/equipo/view/(\d+)", link.get_attribute("href") or "")
        if found:
            teams.setdefault(found.group(1), (link, link.inner_text().strip()))
    if team_id:
        if team_id not in teams:
            raise SnpScrapeError(f"El equipo {team_id} no aparece en «Mis equipos» de esta cuenta SNP.")
        link = teams[team_id][0]
    elif len(teams) == 1:
        link = next(iter(teams.values()))[0]
    elif not teams:
        raise SnpScrapeError("Esta cuenta SNP no tiene ningún equipo en «Mis equipos».")
    else:
        names = ", ".join(f"{name} ({number})" for number, (_, name) in teams.items())
        raise SnpScrapeError(f"La cuenta tiene varios equipos; indica cuál en la cuenta SNP: {names}.")

    link.click()
    frame, _ = _find(page, RESULTS_TABLE, "la tabla de jugadores", log, url_pattern=r"/equipo/view/\d+")
    return frame


def _read_rows(page):
    rows = []
    for row in page.query_selector_all(f"{RESULTS_TABLE} tbody tr"):
        name_cell = row.query_selector("td:nth-child(2)")
        value_cell = row.query_selector("td:nth-child(3)")
        name = name_cell.inner_text().strip() if name_cell else ""
        if name:
            rows.append({"name": name, "score": parse_score(value_cell.inner_text() if value_cell else "")})
    return rows


def scrape_scores(username, password, team_id=None, headed=False, log=None):
    """
    Puntos SNP de los jugadores del equipo ``team_id`` (o del único equipo de la cuenta
    si no se indica). Lanza SnpScrapeError si algo falla.

    ``headed`` abre el navegador a la vista (y más despacio) para seguir la ejecución;
    ``log`` recibe una línea por cada paso.
    """
    log = log or (lambda message: None)
    players = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=not headed, slow_mo=500 if headed else 0)
            try:
                page = browser.new_page()
                log("Iniciando sesión en SNP…")
                _login(page, username, password)
                log("Sesión iniciada. Abriendo Series Nacionales → España → Mis equipos…")
                frame = _open_team_page(page, team_id, log)
                log(f"Página del equipo abierta: {frame.url}")
                for page_number in range(2, MAX_PAGES + 2):
                    rows = _read_rows(frame)
                    log(f"Página {page_number - 1} de la tabla: {len(rows)} jugadores.")
                    players.extend(rows)
                    next_button = frame.query_selector(NEXT_PAGE.format(page_number))
                    if not next_button or not next_button.is_visible():
                        break
                    next_button.click()
                    # La paginación recarga la tabla en la misma página.
                    page.wait_for_timeout(3000)
                    frame.wait_for_selector(RESULTS_TABLE, timeout=TIMEOUT_MS)
            finally:
                browser.close()
    except PlaywrightError as exc:
        raise SnpScrapeError(f"Error del navegador al leer SNP: {str(exc).splitlines()[0]}") from exc
    if not players:
        raise SnpScrapeError("La tabla de jugadores de SNP está vacía.")
    # Algunas páginas pueden repetir filas: nos quedamos con la primera aparición.
    unique = {}
    for player in players:
        unique.setdefault(player["name"], player)
    return list(unique.values())
