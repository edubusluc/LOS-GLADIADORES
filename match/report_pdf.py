"""
PDF del informe de convocatoria con el estilo de Zyra (fondo oscuro, acento lima).
Pensado para caber en dos páginas A4: la primera con el contexto del partido y
los convocados; la segunda con parejas y las dos alineaciones recomendadas.
"""
import io
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext as _
from reportlab.graphics.shapes import Circle, Drawing, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, Frame, KeepTogether, PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle,
)

# Paleta de la web
BG = colors.HexColor("#0B0B0B")
SURFACE = colors.HexColor("#151515")
SURFACE_2 = colors.HexColor("#1D1D1D")
BORDER = colors.HexColor("#333333")
LIME = colors.HexColor("#B4F100")
INK = colors.HexColor("#0A0A0A")
TEXT = colors.HexColor("#F4F4F4")
MUTED = colors.HexColor("#A3A3A3")
CORAL = colors.HexColor("#FF5C63")

FONT_DIR = Path(settings.BASE_DIR) / "static" / "zyra" / "fonts"
LOGO = Path(settings.BASE_DIR) / "static" / "zyra" / "logo.png"
PAGE_W, PAGE_H = A4
MARGIN = 14 * mm
TOP_MARGIN = 24 * mm       # deja aire bajo la línea de la cabecera
BOTTOM_MARGIN = 16 * mm    # y sobre el pie
CONTENT_W = PAGE_W - 2 * MARGIN

# Escala de espaciado vertical: todos los bloques usan estos valores para que el
# ritmo sea el mismo en las dos páginas.
SECTION_GAP = 6 * mm       # entre secciones
HEADING_GAP = 2.5 * mm     # título de sección -> su contenido
NOTE_GAP = 2 * mm          # tabla -> nota aclaratoria
GUTTER = 6 * mm            # separación entre columnas
PANEL_PAD = 9              # relleno interior de las tarjetas (pt)

_fonts_ready = False


def _register_fonts():
    global _fonts_ready
    if _fonts_ready:
        return
    for name, file in (("Archivo", "Archivo-Regular.ttf"), ("Archivo-Bold", "Archivo-Bold.ttf"),
                       ("Archivo-Black", "Archivo-ExtraBold.ttf"), ("Syncopate", "Syncopate-Bold.ttf")):
        pdfmetrics.registerFont(TTFont(name, str(FONT_DIR / file)))
    _fonts_ready = True


def _styles():
    base = dict(fontName="Archivo", fontSize=8.5, leading=11, textColor=TEXT, alignment=TA_LEFT)
    return {
        "title": ParagraphStyle("title", fontName="Syncopate", fontSize=17, leading=21, textColor=TEXT),
        "subtitle": ParagraphStyle("subtitle", **{**base, "fontSize": 10, "leading": 13, "textColor": MUTED}),
        "section": ParagraphStyle("section", fontName="Archivo-Black", fontSize=9.5, leading=12,
                                  textColor=TEXT, spaceAfter=HEADING_GAP),
        "subsection": ParagraphStyle("subsection", fontName="Archivo-Bold", fontSize=6.5, leading=8,
                                     textColor=MUTED, spaceAfter=1.5 * mm),
        "body": ParagraphStyle("body", **base),
        "list": ParagraphStyle("list", **{**base, "spaceAfter": 2}),
        "muted": ParagraphStyle("muted", **{**base, "textColor": MUTED, "fontSize": 7.5, "leading": 9.5}),
        "cell": ParagraphStyle("cell", **{**base, "fontSize": 8, "leading": 10}),
        "cell_bold": ParagraphStyle("cell_bold", **{**base, "fontName": "Archivo-Bold", "fontSize": 8, "leading": 10}),
        "kpi_value": ParagraphStyle("kpi_value", fontName="Archivo-Black", fontSize=17, leading=19, textColor=TEXT),
        "kpi_label": ParagraphStyle("kpi_label", fontName="Archivo-Bold", fontSize=6.5, leading=8, textColor=MUTED),
        "lineup_title": ParagraphStyle("lineup_title", fontName="Archivo-Black", fontSize=10, leading=13,
                                       textColor=LIME, spaceAfter=HEADING_GAP),
    }


def _pips(results, size=6.5):
    """Últimos resultados como círculos (lima = victoria, coral = derrota)."""
    d = Drawing(5 * (size + 2), size + 2)
    for i, won in enumerate(results):
        d.add(Circle(i * (size + 2) + size / 2 + 1, size / 2 + 1, size / 2,
                     fillColor=LIME if won else CORAL, strokeColor=None))
    return d


def _badge(text, fill=LIME, fg=INK, width=16 * mm):
    d = Drawing(width, 12)
    d.add(Rect(0, 0, width, 12, rx=6, ry=6, fillColor=fill, strokeColor=None))
    d.add(String(width / 2, 3.2, text, fontName="Archivo-Black", fontSize=7, fillColor=fg, textAnchor="middle"))
    return d


def _wl(wins, losses):
    """'3V-2D' (victorias-derrotas) en el idioma activo."""
    return _("%(wins)sV-%(losses)sD") % {"wins": wins, "losses": losses}


def _record(wins, played):
    if not played:
        return "—"
    return f"{_wl(wins, played - wins)} · {round(wins / played * 100)}%"


def _streak_label(kind, n):
    """'3V' / '2D' (racha de victorias o derrotas) en el idioma activo."""
    return (_("%(n)sV") if kind == "V" else _("%(n)sD")) % {"n": n}


def _streak(streak):
    kind, n = streak
    return _streak_label(kind, n) if kind else "—"


def _columns(left, right, left_w):
    """Dos columnas alineadas arriba, sin relleno y separadas por GUTTER."""
    t = Table([[left, right]], colWidths=[left_w + GUTTER, CONTENT_W - left_w - GUTTER])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (0, 0), GUTTER),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return t


def _panel(content, padding=PANEL_PAD):
    """Tarjeta oscura con borde fino (como .z-card)."""
    t = Table([[content]], colWidths=[CONTENT_W])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), SURFACE),
        ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
        ("ROUNDEDCORNERS", [8, 8, 8, 8]),
        ("LEFTPADDING", (0, 0), (-1, -1), padding),
        ("RIGHTPADDING", (0, 0), (-1, -1), padding),
        ("TOPPADDING", (0, 0), (-1, -1), padding),
        ("BOTTOMPADDING", (0, 0), (-1, -1), padding),
    ]))
    return t


def _data_table(header, rows, col_widths, st, highlight_first=False):
    data = [[Paragraph(h.upper(), st["kpi_label"]) for h in header]] + rows
    t = Table(data, colWidths=col_widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), SURFACE_2),
        ("BACKGROUND", (0, 1), (-1, -1), SURFACE),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, BORDER),
        ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
        ("ROUNDEDCORNERS", [8, 8, 8, 8]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]
    if highlight_first:
        style.append(("LINEBEFORE", (0, 1), (0, 2), 2.5, LIME))
    t.setStyle(TableStyle(style))
    return t


def _kpis(items, st):
    cells = [[Paragraph(label.upper(), st["kpi_label"]), Paragraph(value, st["kpi_value"])] for label, value in items]
    widths = [CONTENT_W / len(items)] * len(items)
    inner = [Table([[c[0]], [c[1]]], colWidths=[widths[0] - 8]) for c in cells]
    for t in inner:
        t.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 1),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
    t = Table([inner], colWidths=widths)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), SURFACE),
        ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
        ("LINEAFTER", (0, 0), (-2, -1), 0.6, BORDER),
        ("LINEBEFORE", (0, 0), (0, -1), 3, LIME),
        ("ROUNDEDCORNERS", [8, 8, 8, 8]),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return t


def _on_page(canvas, doc, report):
    canvas.saveState()
    canvas.setFillColor(BG)
    canvas.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
    # Cabecera: logo + ZYRA a la izquierda, club y fecha a la derecha
    top = PAGE_H - 11 * mm
    if LOGO.exists():
        canvas.drawImage(str(LOGO), MARGIN, top - 3.2 * mm, width=7 * mm, height=7 * mm, mask="auto")
    canvas.setFillColor(TEXT)
    canvas.setFont("Syncopate", 12)
    canvas.drawString(MARGIN + 9 * mm, top - 1.3 * mm, "ZYRA")
    canvas.setFont("Archivo-Bold", 8)
    canvas.setFillColor(MUTED)
    canvas.drawRightString(PAGE_W - MARGIN, top, report["club"].name.upper())
    canvas.drawRightString(PAGE_W - MARGIN, top - 3.8 * mm,
                           _("Generado el %(date)s") % {"date": timezone.localtime().strftime("%d/%m/%Y %H:%M")})
    canvas.setStrokeColor(BORDER)
    canvas.line(MARGIN, top - 6 * mm, PAGE_W - MARGIN, top - 6 * mm)
    # Pie
    canvas.setFont("Archivo", 7)
    canvas.drawString(MARGIN, 8 * mm, _("Informe automático de convocatoria · Zyra"))
    canvas.drawRightString(PAGE_W - MARGIN, 8 * mm, _("Página %(page)s de %(total)s") % {"page": doc.page, "total": 2})
    canvas.restoreState()


def render_report(report):
    """Devuelve los bytes del PDF."""
    _register_fonts()
    st = _styles()
    match, venue = report["match"], report["venue_label"]
    own = match.local if match.own_is_local else match.visiting
    story = []

    # ---------------- Página 1 ----------------
    story.append(Paragraph(_("INFORME DE CONVOCATORIA"), st["title"]))
    story.append(Spacer(1, 1 * mm))
    story.append(Paragraph(
        _("<b>%(own)s</b> vs <b>%(rival)s</b> · %(date)s · "
          "jugáis como <font color='#B4F100'><b>%(venue)s</b></font> · temporada %(season)s") % {
            "own": own, "rival": report['rival'], "date": f"{match.start_date:%d/%m/%Y}",
            "venue": venue.upper(), "season": match.season},
        st["subtitle"]))
    story.append(Spacer(1, 5 * mm))

    s = report["season"]
    prec = report["precedents"]
    prec_w = sum(p["outcome"] == "V" for p in prec)
    story.append(_kpis([
        (_("Convocados"), str(len(report["called"]))),
        (_("Temporada"), _wl(s['won'], s['played'] - s['won'])),
        (_("Como %(venue)s") % {"venue": venue}, _wl(s['venue_won'], s['venue_played'] - s['venue_won'])),
        ((_("Vs %(rival)s") % {"rival": report['rival']})[:22], _wl(prec_w, len(prec) - prec_w) if prec else "—"),
    ], st))

    # Precedentes y rachas, en dos columnas
    prec_col_w = CONTENT_W * 0.56 - GUTTER
    if prec:
        prec_rows = [[Paragraph(f"{p['date']:%d/%m/%Y}", st["cell"]), Paragraph(p["venue"], st["cell"]),
                      Paragraph(f"<b>{p['score']}</b>", st["cell"]),
                      _badge(_("VICTORIA") if p["outcome"] == "V" else _("DERROTA") if p["outcome"] == "D" else _("EMPATE"),
                             fill=LIME if p["outcome"] == "V" else CORAL if p["outcome"] == "D" else MUTED)]
                     for p in prec]
        prec_block = [Paragraph(_("PRECEDENTES CONTRA %(rival)s") % {"rival": str(report['rival']).upper()}, st["section"]),
                      _data_table([_("Fecha"), _("Sede"), _("Puntos"), ""], prec_rows,
                                  [22 * mm, 22 * mm, 18 * mm, prec_col_w - 62 * mm], st)]
    else:
        prec_block = [Paragraph(_("PRECEDENTES CONTRA %(rival)s") % {"rival": str(report['rival']).upper()}, st["section"]),
                      Paragraph(_("Primer enfrentamiento contra este equipo."), st["muted"])]

    def streak_lines(items, color):
        if not items:
            return [Paragraph(_("Nadie con 2 o más resultados seguidos."), st["muted"])]
        return [Paragraph(f"<font color='{color}'><b>{_streak_label(f.streak[0], f.streak[1])}</b></font>  {f.name}", st["list"])
                for f in items]

    streak_block = [Paragraph(_("JUGADORES EN RACHA"), st["section"]),
                    *streak_lines(report["hot"], "#B4F100"),
                    Spacer(1, 3 * mm),
                    Paragraph(_("EN MALA RACHA"), st["subsection"]),
                    *streak_lines(report["cold"], "#FF5C63")]
    story.append(Spacer(1, SECTION_GAP))
    story.append(_columns(prec_block, streak_block, prec_col_w))

    # Convocados
    story.append(Spacer(1, SECTION_GAP))
    story.append(Paragraph(_("CONVOCADOS · RENDIMIENTO COMO %(venue)s") % {"venue": venue.upper()}, st["section"]))
    player_rows = [[
        Paragraph(f"<b>{f.name}</b>", st["cell"]),
        Paragraph(f.player.get_position_display() if f.player.position else "—", st["cell"]),
        Paragraph(f"{f.snp:g}" if f.snp else "—", st["cell"]),
        Paragraph(_record(f.venue_wins, f.venue_played), st["cell"]),
        Paragraph(_record(f.wins, f.played), st["cell"]),
        Paragraph(f"<font color='{'#B4F100' if f.streak[0] == 'V' else '#FF5C63'}'><b>{_streak(f.streak)}</b></font>", st["cell"]),
        _pips(f.form),
        Paragraph(f"<b>{round(f.strength * 100)}%</b>", st["cell"]),
    ] for f in report["players"]]
    story.append(_data_table(
        [_("Jugador"), _("Posición"), "SNP", _("Como %(venue)s") % {"venue": venue}, _("Global"), _("Racha"),
         _("Forma"), _("Estim.")],
        player_rows, [44 * mm, 19 * mm, 13 * mm, 30 * mm, 30 * mm, 13 * mm, 17 * mm, 16 * mm], st))
    note = _("Estim.: probabilidad estimada de ganar un partido (historial, rendimiento en la sede, forma y racha).")
    if report["hidden_players"]:
        note += " " + _("%(n)s convocados más no caben en la tabla.") % {"n": report['hidden_players']}
    story.append(Spacer(1, NOTE_GAP))
    story.append(Paragraph(note, st["muted"]))

    # Reparto de partidos en la temporada (toda la plantilla)
    def usage_table(rows):
        body = [[
            Paragraph(f"<font color='{'#B4F100' if u['called_now'] else '#F4F4F4'}'>"
                      f"<b>{u['player'].name} {u['player'].get_first_last_name()}</b></font>", st["cell"]),
            Paragraph(f"<b>{u['games']}</b>", st["cell"]),
            Paragraph(str(u["calls"]), st["cell"]),
            Paragraph(f"{u['last']:%d/%m}" if u["last"] else "—", st["cell"]),
        ] for u in rows]
        half = (CONTENT_W - GUTTER) / 2
        return _data_table([_("Jugador"), _("Partidos"), _("Convoc."), _("Último")], body,
                           [half - 49 * mm, 18 * mm, 16 * mm, 15 * mm], st)

    never = report["never_played"]
    usage_block = _columns(
        [Paragraph(_("JUGADORES CON MÁS PARTIDOS"), st["section"]), usage_table(report["most_games"])],
        [Paragraph(_("JUGADORES CON MENOS PARTIDOS"), st["section"]), usage_table(report["least_games"])],
        (CONTENT_W - GUTTER) / 2)
    story.append(Spacer(1, SECTION_GAP))
    story.append(KeepTogether([
        usage_block,
        Spacer(1, NOTE_GAP),
        Paragraph(
            _("Temporada %(season)s, toda la plantilla (%(n)s jugadores).") % {
                "season": match.season, "n": report['squad_size']} + " "
            + ("<font color='#FF5C63'><b>" + _("%(n)s sin jugar todavía.") % {"n": never} + "</b></font> "
               if never else _("Todos han jugado ya.") + " ")
            + _("En <font color='#B4F100'><b>lima</b></font>, convocados para este partido.") + " "
            + _("Convoc.: convocatorias cerradas en la temporada."),
            st["muted"]),
    ]))

    # ---------------- Página 2 ----------------
    story.append(PageBreak())
    story.append(Paragraph(_("PAREJAS CON HISTORIAL ENTRE LOS CONVOCADOS"), st["section"]))
    if report["pairs"]:
        pair_rows = [[
            Paragraph(f"<b>{p.name}</b>", st["cell"]),
            Paragraph(f"{p.snp_sum:g}", st["cell"]),
            Paragraph(_record(p.venue_wins, p.venue_played), st["cell"]),
            Paragraph(_record(p.wins, p.played), st["cell"]),
            Paragraph(_streak(p.streak), st["cell"]),
        ] for p in report["pairs"]]
        story.append(_data_table([_("Pareja"), _("Suma SNP"), _("Como %(venue)s") % {"venue": venue}, _("Juntos"), _("Racha")],
                                 pair_rows, [70 * mm, 18 * mm, 36 * mm, 36 * mm, 22 * mm], st))
    else:
        story.append(Paragraph(_("Ninguna pareja de convocados ha jugado junta todavía."), st["muted"]))

    story.append(Spacer(1, SECTION_GAP))
    story.append(Paragraph(_("ALINEACIONES RECOMENDADAS"), st["section"]))
    if not report["enough_players"]:
        story.append(Paragraph(_("Hacen falta al menos 10 convocados para proponer una alineación."), st["body"]))
    lineup_w = CONTENT_W - 2 * PANEL_PAD
    for i, item in enumerate(report["lineups"]):
        if i:
            story.append(Spacer(1, 4 * mm))
        lineup = item["lineup"]
        rows = [[
            Paragraph(f"<b>{row['n']}</b>", st["cell_bold"]),
            _badge(_("%(n)s PTS") % {"n": row['value']}, fill=LIME if row['value'] == 3 else SURFACE_2,
                   fg=INK if row['value'] == 3 else TEXT, width=13 * mm),
            Paragraph(f"<b>{row['pair'].name}</b>", st["cell"]),
            Paragraph(f"{row['pair'].snp_sum:g}", st["cell"]),
            Paragraph(f"<b>{row['pct']}%</b>", st["cell"]),
        ] for row in lineup.rows]
        table = _data_table([_("Partido"), _("Valor"), _("Pareja"), _("Suma SNP"), _("Victoria est.")], rows,
                            [16 * mm, 18 * mm, lineup_w - 76 * mm, 20 * mm, 22 * mm], st, highlight_first=True)
        block = [
            Paragraph(_("%(title)s · %(pct)s%% DE GANAR LA ELIMINATORIA") % {
                "title": item['title'].upper(), "pct": round(lineup.win * 100)},
                      st["lineup_title"]),
            table,
            Spacer(1, 3 * mm),
            Paragraph(item["explanation"], st["body"]),
        ]
        if lineup.bench:
            block.append(Spacer(1, NOTE_GAP))
            block.append(Paragraph(_("Descansan: %(names)s") % {"names": ", ".join(f.name for f in lineup.bench)}, st["muted"]))
        story.append(KeepTogether([_panel(block)]))

    story.append(Spacer(1, SECTION_GAP))
    story.append(Paragraph(
        _("Formato SNP: 5 partidos; los partidos 1 y 2 valen 3 puntos y los 3, 4 y 5 valen 2. Las parejas se "
          "ordenan por la suma de puntos SNP de sus jugadores y se necesitan 7 de 12 puntos para ganar la "
          "eliminatoria. Las estimaciones se basan en el historial del club y son orientativas."),
        st["muted"]))

    buffer = io.BytesIO()
    doc = BaseDocTemplate(
        buffer, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=TOP_MARGIN, bottomMargin=BOTTOM_MARGIN,
        title=_("Informe de convocatoria · %(own)s vs %(rival)s") % {"own": own, "rival": report['rival']}, author="Zyra",
    )
    # Marco sin relleno: los títulos y las tablas (que miden CONTENT_W) quedan alineados al mismo margen
    frame = Frame(MARGIN, BOTTOM_MARGIN, CONTENT_W, PAGE_H - TOP_MARGIN - BOTTOM_MARGIN,
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(frames=[frame], onPage=lambda c, d: _on_page(c, d, report))])
    doc.build(story)
    return buffer.getvalue()
