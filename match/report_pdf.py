"""
PDF del informe de convocatoria con el estilo de Zyra (fondo oscuro, acento lima).
Pensado para caber en dos páginas A4: la primera con el contexto del partido y
los convocados; la segunda con parejas y las dos alineaciones recomendadas.
"""
import io
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from reportlab.graphics.shapes import Circle, Drawing, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
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
CONTENT_W = PAGE_W - 2 * MARGIN

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
                                  textColor=TEXT, spaceBefore=9, spaceAfter=5),
        "body": ParagraphStyle("body", **base),
        "muted": ParagraphStyle("muted", **{**base, "textColor": MUTED, "fontSize": 7.5, "leading": 9.5}),
        "cell": ParagraphStyle("cell", **{**base, "fontSize": 8, "leading": 10}),
        "cell_bold": ParagraphStyle("cell_bold", **{**base, "fontName": "Archivo-Bold", "fontSize": 8, "leading": 10}),
        "kpi_value": ParagraphStyle("kpi_value", fontName="Archivo-Black", fontSize=17, leading=19, textColor=TEXT),
        "kpi_label": ParagraphStyle("kpi_label", fontName="Archivo-Bold", fontSize=6.5, leading=8, textColor=MUTED),
        "lineup_title": ParagraphStyle("lineup_title", fontName="Archivo-Black", fontSize=10, leading=13, textColor=LIME),
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


def _record(wins, played):
    if not played:
        return "—"
    return f"{wins}V-{played - wins}D · {round(wins / played * 100)}%"


def _streak(streak):
    kind, n = streak
    return f"{n}{kind}" if kind else "—"


def _panel(content, padding=8):
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
    canvas.drawRightString(PAGE_W - MARGIN, top - 3.8 * mm, timezone.localtime().strftime("Generado el %d/%m/%Y %H:%M"))
    canvas.setStrokeColor(BORDER)
    canvas.line(MARGIN, top - 6 * mm, PAGE_W - MARGIN, top - 6 * mm)
    # Pie
    canvas.setFont("Archivo", 7)
    canvas.drawString(MARGIN, 8 * mm, "Informe automático de convocatoria · Zyra")
    canvas.drawRightString(PAGE_W - MARGIN, 8 * mm, f"Página {doc.page} de 2")
    canvas.restoreState()


def render_report(report):
    """Devuelve los bytes del PDF."""
    _register_fonts()
    st = _styles()
    match, venue = report["match"], report["venue_label"]
    own = match.local if match.own_is_local else match.visiting
    story = []

    # ---------------- Página 1 ----------------
    story.append(Paragraph("INFORME DE CONVOCATORIA", st["title"]))
    story.append(Spacer(1, 2))
    story.append(Paragraph(
        f"<b>{own}</b> vs <b>{report['rival']}</b> · {match.start_date:%d/%m/%Y} · "
        f"jugáis como <font color='#B4F100'><b>{venue.upper()}</b></font> · temporada {match.season}",
        st["subtitle"]))
    story.append(Spacer(1, 8))

    s = report["season"]
    prec = report["precedents"]
    prec_w = sum(p["outcome"] == "V" for p in prec)
    story.append(_kpis([
        ("Convocados", str(len(report["called"]))),
        ("Temporada", f"{s['won']}V-{s['played'] - s['won']}D"),
        (f"Como {venue}", f"{s['venue_won']}V-{s['venue_played'] - s['venue_won']}D"),
        (f"Vs {report['rival']}"[:22], f"{prec_w}V-{len(prec) - prec_w}D" if prec else "—"),
    ], st))

    # Precedentes y rachas, en dos columnas
    if prec:
        prec_rows = [[Paragraph(f"{p['date']:%d/%m/%Y}", st["cell"]), Paragraph(p["venue"], st["cell"]),
                      Paragraph(f"<b>{p['score']}</b>", st["cell"]),
                      _badge("VICTORIA" if p["outcome"] == "V" else "DERROTA" if p["outcome"] == "D" else "EMPATE",
                             fill=LIME if p["outcome"] == "V" else CORAL if p["outcome"] == "D" else MUTED)]
                     for p in prec]
        prec_block = [Paragraph(f"PRECEDENTES CONTRA {str(report['rival']).upper()}", st["section"]),
                      _data_table(["Fecha", "Sede", "Puntos", ""], prec_rows,
                                  [20 * mm, 18 * mm, 14 * mm, 20 * mm], st)]
    else:
        prec_block = [Paragraph(f"PRECEDENTES CONTRA {str(report['rival']).upper()}", st["section"]),
                      Paragraph("Primer enfrentamiento contra este equipo.", st["muted"])]

    def streak_lines(items, color):
        if not items:
            return [Paragraph("Nadie con 2 o más resultados seguidos.", st["muted"])]
        return [Paragraph(f"<font color='{color}'><b>{f.streak[1]}{f.streak[0]}</b></font>  {f.name}", st["body"])
                for f in items]

    streak_block = [Paragraph("JUGADORES EN RACHA", st["section"]),
                    *streak_lines(report["hot"], "#B4F100"),
                    Spacer(1, 4),
                    Paragraph("EN MALA RACHA", st["kpi_label"]),
                    *streak_lines(report["cold"], "#FF5C63")]
    two_cols = Table([[prec_block, streak_block]], colWidths=[CONTENT_W * 0.56, CONTENT_W * 0.44])
    two_cols.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                  ("RIGHTPADDING", (0, 0), (0, 0), 10)]))
    story.append(two_cols)

    # Convocados
    story.append(Paragraph(f"CONVOCADOS · RENDIMIENTO COMO {venue.upper()}", st["section"]))
    player_rows = [[
        Paragraph(f"<b>{f.name}</b>", st["cell"]),
        Paragraph(f.player.position or "—", st["cell"]),
        Paragraph(f"{f.snp:g}" if f.snp else "—", st["cell"]),
        Paragraph(_record(f.venue_wins, f.venue_played), st["cell"]),
        Paragraph(_record(f.wins, f.played), st["cell"]),
        Paragraph(f"<font color='{'#B4F100' if f.streak[0] == 'V' else '#FF5C63'}'><b>{_streak(f.streak)}</b></font>", st["cell"]),
        _pips(f.form),
        Paragraph(f"<b>{round(f.strength * 100)}%</b>", st["cell"]),
    ] for f in report["players"]]
    story.append(_data_table(
        ["Jugador", "Posición", "SNP", f"Como {venue}", "Global", "Racha", "Forma", "Estim."],
        player_rows, [44 * mm, 19 * mm, 13 * mm, 30 * mm, 30 * mm, 13 * mm, 17 * mm, 16 * mm], st))
    note = "Estim.: probabilidad estimada de ganar un partido (historial, rendimiento en la sede, forma y racha)."
    if report["hidden_players"]:
        note += f" {report['hidden_players']} convocados más no caben en la tabla."
    story.append(Spacer(1, 3))
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
        half = (CONTENT_W - 6 * mm) / 2
        return _data_table(["Jugador", "Partidos", "Convoc.", "Último"], body,
                           [half - 49 * mm, 18 * mm, 16 * mm, 15 * mm], st)

    never = report["never_played"]
    usage_block = Table([[
        [Paragraph("JUGADORES CON MÁS PARTIDOS", st["section"]), usage_table(report["most_games"])],
        [Paragraph("JUGADORES CON MENOS PARTIDOS", st["section"]), usage_table(report["least_games"])],
    ]], colWidths=[(CONTENT_W + 6 * mm) / 2, (CONTENT_W - 6 * mm) / 2])
    usage_block.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                     ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (0, 0), 6 * mm)]))
    story.append(KeepTogether([
        usage_block,
        Spacer(1, 3),
        Paragraph(
            f"Temporada {match.season}, toda la plantilla ({report['squad_size']} jugadores). "
            + (f"<font color='#FF5C63'><b>{never} sin jugar todavía.</b></font> " if never else "Todos han jugado ya. ")
            + "En <font color='#B4F100'><b>lima</b></font>, convocados para este partido. "
            "Convoc.: convocatorias cerradas en la temporada.",
            st["muted"]),
    ]))

    # ---------------- Página 2 ----------------
    story.append(PageBreak())
    story.append(Paragraph("PAREJAS CON HISTORIAL ENTRE LOS CONVOCADOS", st["section"]))
    if report["pairs"]:
        pair_rows = [[
            Paragraph(f"<b>{p.name}</b>", st["cell"]),
            Paragraph(f"{p.snp_sum:g}", st["cell"]),
            Paragraph(_record(p.venue_wins, p.venue_played), st["cell"]),
            Paragraph(_record(p.wins, p.played), st["cell"]),
            Paragraph(_streak(p.streak), st["cell"]),
        ] for p in report["pairs"]]
        story.append(_data_table(["Pareja", "Suma SNP", f"Como {venue}", "Juntos", "Racha"],
                                 pair_rows, [70 * mm, 18 * mm, 36 * mm, 36 * mm, 22 * mm], st))
    else:
        story.append(Paragraph("Ninguna pareja de convocados ha jugado junta todavía.", st["muted"]))

    story.append(Paragraph("ALINEACIONES RECOMENDADAS", st["section"]))
    if not report["enough_players"]:
        story.append(Paragraph("Hacen falta al menos 10 convocados para proponer una alineación.", st["body"]))
    for item in report["lineups"]:
        lineup = item["lineup"]
        rows = [[
            Paragraph(f"<b>{row['n']}</b>", st["cell_bold"]),
            _badge(f"{row['value']} PTS", fill=LIME if row['value'] == 3 else SURFACE_2,
                   fg=INK if row['value'] == 3 else TEXT, width=13 * mm),
            Paragraph(f"<b>{row['pair'].name}</b>", st["cell"]),
            Paragraph(f"{row['pair'].snp_sum:g}", st["cell"]),
            Paragraph(f"<b>{row['pct']}%</b>", st["cell"]),
        ] for row in lineup.rows]
        table = _data_table(["Partido", "Valor", "Pareja", "Suma SNP", "Victoria est."], rows,
                            [16 * mm, 18 * mm, 86 * mm, 20 * mm, 22 * mm], st, highlight_first=True)
        block = [
            Paragraph(f"{item['title'].upper()} · {round(lineup.win * 100)}% DE GANAR LA ELIMINATORIA",
                      st["lineup_title"]),
            Spacer(1, 4),
            table,
            Spacer(1, 5),
            Paragraph(item["explanation"], st["body"]),
        ]
        if lineup.bench:
            block.append(Paragraph("Descansan: " + ", ".join(f.name for f in lineup.bench), st["muted"]))
        story.append(KeepTogether([_panel(block)]))
        story.append(Spacer(1, 7))

    story.append(Paragraph(
        "Formato SNP: 5 partidos; los partidos 1 y 2 valen 3 puntos y los 3, 4 y 5 valen 2. Las parejas se "
        "ordenan por la suma de puntos SNP de sus jugadores y se necesitan 7 de 12 puntos para ganar la "
        "eliminatoria. Las estimaciones se basan en el historial del club y son orientativas.",
        st["muted"]))

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=22 * mm, bottomMargin=14 * mm,
        title=f"Informe de convocatoria · {own} vs {report['rival']}", author="Zyra",
    )
    doc.build(story, onFirstPage=lambda c, d: _on_page(c, d, report),
              onLaterPages=lambda c, d: _on_page(c, d, report))
    return buffer.getvalue()
