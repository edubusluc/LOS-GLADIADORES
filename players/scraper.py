"""
Descarga de los puntos SNP de los jugadores de un equipo desde snpgalaxy.com.

Entra con la cuenta de SNP del capitán, abre la página del equipo y lee la tabla de
jugadores (todas las páginas). Devuelve una lista de ``{"name": ..., "score": ...}``
con el nombre tal y como aparece en SNP; el cruce con nuestros jugadores está en
players/snp.py.
"""
import base64
import binascii
import re

LOGIN_URL = "https://snpgalaxy.com/usuario/login"
LOGIN_BUTTONS = ('input[type="submit"][value="Iniciar Sesión"]', 'button[type="submit"]:has-text("Iniciar Sesión")',
                 'input[type="submit"]', 'button[type="submit"]')
USERNAME_FIELDS = ('input[name="email"]', 'input[name="usuario"]', 'input[name="username"]',
                   'input[type="email"]', 'input[type="text"]')
RESULTS_TABLE = "table.results"
NEXT_PAGE = 'a.pag_numerada.page-link[num_pagina="{}"]'
MAX_PAGES = 30
TIMEOUT_MS = 30_000


class SnpScrapeError(Exception):
    """Error que se puede enseñar tal cual al administrador del club."""


def team_page_urls(team_url):
    """
    Direcciones a probar para abrir la página del equipo, en orden.

    Los enlaces de snpgalaxy.com llevan la dirección real codificada en base64 tras
    ``u_:`` (p. ej. .../u_:aHR0cHM6Ly9...=, que es
    https://seriesnacionalesdepadel.snpgalaxy.com/equipo/view/4380). Esa dirección
    identifica al equipo; el resto del enlace parece ligado a la sesión del usuario,
    así que se prueba primero la dirección real y después el enlace tal cual.
    """
    urls = []
    match = re.search(r"/u_:([A-Za-z0-9+/=_-]+)", team_url)
    if match:
        encoded = match.group(1)
        try:
            decoded = base64.b64decode(encoded + "=" * (-len(encoded) % 4), altchars=b"+/").decode()
        except (binascii.Error, UnicodeDecodeError):
            decoded = ""
        if decoded.startswith("http"):
            urls.append(decoded)
    urls.append(team_url)
    return list(dict.fromkeys(urls))


def team_id(team_url):
    """Número del equipo en SNP (4380 en .../equipo/view/4380), o None."""
    for url in team_page_urls(team_url):
        match = re.search(r"/equipo/view/(\d+)", url)
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


def _open_team_page(page, team_url):
    for url in team_page_urls(team_url):
        try:
            page.goto(url, timeout=TIMEOUT_MS)
            page.wait_for_selector(RESULTS_TABLE, timeout=15_000)
            return
        except Exception:
            continue
    raise SnpScrapeError("No se ha podido abrir la página del equipo en SNP o no tiene la tabla de jugadores.")


def _read_rows(page):
    rows = []
    for row in page.query_selector_all(f"{RESULTS_TABLE} tbody tr"):
        name_cell = row.query_selector("td:nth-child(2)")
        value_cell = row.query_selector("td:nth-child(3)")
        name = name_cell.inner_text().strip() if name_cell else ""
        if name:
            rows.append({"name": name, "score": parse_score(value_cell.inner_text() if value_cell else "")})
    return rows


def scrape_scores(username, password, team_url):
    """Puntos SNP de los jugadores del equipo. Lanza SnpScrapeError si algo falla."""
    from playwright.sync_api import Error as PlaywrightError, sync_playwright

    players = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                _login(page, username, password)
                _open_team_page(page, team_url)
                for page_number in range(2, MAX_PAGES + 2):
                    players.extend(_read_rows(page))
                    next_button = page.query_selector(NEXT_PAGE.format(page_number))
                    if not next_button or not next_button.is_visible():
                        break
                    next_button.click()
                    # La paginación recarga la tabla en la misma página.
                    page.wait_for_timeout(3000)
                    page.wait_for_selector(RESULTS_TABLE, timeout=TIMEOUT_MS)
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
