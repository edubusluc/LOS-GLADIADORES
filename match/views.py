from django.shortcuts import render, redirect, get_object_or_404
from core.decorators import club_required, club_admin_required
from django.contrib import messages
from .forms import MatchForm
from .models import Match, Game, Result
from . import lineup
from .notifications import send_call_report, report_filename
from call.models import ReportDelivery
from .report import build_report
from .report_pdf import render_report
from django.http import HttpResponse
import logging

logger = logging.getLogger(__name__)
from players.models import Player, current_season
from call.models import Call
from team.models import Team
from datetime import datetime
from callLog.models import CallLog
from penalty.models import Penalty
import json
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.core.exceptions import ValidationError
from django.db.models import Q


CREATE_MATCH_HTML = "create_match.html"
# Create your views here.


def club_match(request, match_id):
    """Partido del club activo o 404: nunca se accede a partidos de otros clubes."""
    return get_object_or_404(Match, public_id=match_id, club=request.club)


def club_call(request, **filters):
    return get_object_or_404(Call, match__club=request.club, **filters)


def club_players(request, ids):
    """Jugadores del club activo cuyos ids vienen del formulario (ignora ids ajenos)."""
    return Player.objects.filter(club=request.club, id__in=[i for i in ids if str(i).isdigit()])


MATCHES_PER_PAGE = 12
ALL_SEASONS = "all"


def match_outcome(match):
    """'V', 'D' o 'E' desde el punto de vista del club; None si el acta sigue abierta."""
    if match.draft_mode or match.result in ("", "NONE", None):
        return None
    if match.result == "Victoria Local":
        return "V" if match.own_is_local else "D"
    if match.result == "Victoria Visitante":
        return "V" if match.own_is_visiting else "D"
    return "E"


@club_required
def list_match(request):
    # Por defecto, la temporada actual; "all" muestra todas.
    season = request.GET.get('season') or current_season()

    club_matches = Match.objects.filter(club=request.club).select_related('local', 'visiting')
    matches = club_matches.order_by('-start_date', '-id')
    if season != ALL_SEASONS:
        matches = matches.filter(season=season)

    # Temporadas para el selector (desc), incluida la actual aunque aún no tenga partidos
    seasons = set(club_matches.values_list('season', flat=True)) | {current_season()}
    seasons = sorted((x for x in seasons if x and x != "NONE"), reverse=True)

    outcomes = [match_outcome(m) for m in matches]
    summary = {
        'played': sum(o is not None for o in outcomes),
        'won': outcomes.count('V'),
        'lost': outcomes.count('D'),
        'pending': outcomes.count(None),
    }

    paginator = Paginator(matches, MATCHES_PER_PAGE)
    page = request.GET.get('page')
    try:
        matches = paginator.page(page)
    except PageNotAnInteger:
        matches = paginator.page(1)
    except EmptyPage:
        matches = paginator.page(paginator.num_pages)

    for m in matches:
        m.outcome = match_outcome(m)

    return render(request, "list_match.html", {
        'matches': matches,
        'seasons': seasons,
        'selected_season': season,
        'all_seasons': ALL_SEASONS,
        'summary': summary,
    })

@club_admin_required
def create_match(request):
    club = request.club
    own_team = club.own_team
    if request.method == "POST":
        # Obtiene los datos del formulario
        local_id = request.POST.get('local')
        visiting_id = request.POST.get('visiting')
        start_date_str = request.POST.get('start_date')

        # Intenta convertir la fecha
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        except (TypeError, ValueError):
            return render(request, CREATE_MATCH_HTML, {
                "form": MatchForm(request.POST, club=club),
                "error": "Fecha no válida. Usa el formato AAAA-MM-DD."
            })

        # Verifica que todos los campos necesarios están presentes
        try:
            local_team = Team.objects.get(id=local_id, club=club)
            visiting_team = Team.objects.get(id=visiting_id, club=club)
        except (Team.DoesNotExist, ValueError):
            return render(request, CREATE_MATCH_HTML, {
                "form": MatchForm(request.POST, club=club),
                "error": "Uno de los equipos no existe."
            })

        # Verifica si el enfrentamiento es válido
        if local_team == visiting_team or own_team not in (local_team, visiting_team):
            form = MatchForm(request.POST, club=club)  # Re-crea el formulario con los datos enviados
            return render(request, CREATE_MATCH_HTML, {
                "form": form,
                "error": f"No es un enfrentamiento válido. {own_team} debe ser local o visitante"
            })

        # Verifica si los campos están completos
        if local_id and visiting_id and start_date:
            Match.objects.create(
                club=club,
                local_id=local_id,
                visiting_id=visiting_id,
                start_date=start_date,
            )
            return redirect("list_match")  # Redirección después de crear el partido
        else:
            form = MatchForm(request.POST, club=club)  # Re-crea el formulario con los datos enviados
            return render(request,CREATE_MATCH_HTML, {
                "form": form,
                "error": "Por favor, completa todos los campos."
            })
    else:
        form = MatchForm(club=club)

    return render(request, CREATE_MATCH_HTML, {"form": form})

@club_admin_required
def delete_match(request, match_id):
    try:
        match = club_match(request, match_id)
        if match.draft_mode != False:

            if request.method == 'POST':
                # Eliminar el partido si el usuario confirma
                match.delete()
                return redirect('list_match')

            return render(request, 'delete_match.html', {'match': match})
        else:
            messages.error(request, "No se puede eliminar un partido ya confirmado")

            return redirect('list_match')
    except Match.DoesNotExist:
        messages.error(request, "El partido no existe")
        return redirect('list_match')


def selectable_players(club, include_ids=()):
    """
    Jugadores para el selector de convocatorias: los que están en el equipo
    (más los ya convocados aunque ya no estén), en orden alfabético y con sus
    sanciones en `penalty_reasons`.
    """
    players = list(
        Player.objects.filter(club=club)
        .filter(Q(in_team=True) | Q(id__in=list(include_ids)))
        .order_by('name', 'last_name')
    )
    reasons = {}
    for pid, reason in Penalty.objects.filter(player__in=players).values_list('player_id', 'reason'):
        reasons.setdefault(pid, []).append(reason)
    for p in players:
        p.penalty_reasons = reasons.get(p.id, [])
    return players


@club_admin_required
def create_call(request, match_id):
    match = club_match(request, match_id)
    if Call.objects.filter(match=match).exists() or match.draft_mode == False:
        return redirect('existing_call', match.public_id)

    selected_ids = []
    if request.method == 'POST':
        chosen = club_players(request, request.POST.getlist('players'))
        selected_ids = list(chosen.values_list('id', flat=True))
        if not selected_ids:
            messages.error(request, "Debes seleccionar al menos un jugador.")
        else:
            call = Call.objects.create(match=match)
            call.players.set(selected_ids)
            CallLog.objects.create(call=call, text="")
            return redirect('call_for_match', match.public_id)

    return render(request, "create_call.html", {
        "players": selectable_players(request.club),
        "selected_players": selected_ids,
        "match": match,
    })


def validate_call(call):
    if call.players.all().count() < 10:
        return False, "Para cerrar una convocatoria al menos debes contar con 10 jugadores"
    if call.draft_mode == False:
        return False, "Esta convocatoria ha sido cerrada"
    
    return True, None

@club_admin_required
def close_call(request, match_id):
    call = club_call(request, match__public_id=match_id)
    is_valid, error_message = validate_call(call)

    if not is_valid:
        messages.error(request, error_message)
        return redirect(call_for_match, match_id=match_id)

    if request.method == "POST":
        call.draft_mode = False
        call.save()
        _send_report(request, call, "Convocatoria cerrada")
        return redirect('call_for_match', call.match.public_id)

    return redirect('call_for_match', call.match.public_id)


def _send_report(request, call, done):
    """
    Informe PDF a los administradores: se intenta al momento y lo que falle se reintenta
    solo (send_call_reports). Si falla el envío, la convocatoria queda cerrada igualmente.
    """
    try:
        deliveries = send_call_report(call, sender=request.user)
    except Exception:
        logger.exception("No se pudo enviar el informe de la convocatoria %s", call.pk)
        messages.warning(request, f"{done}, pero no se pudo enviar el informe por email. "
                                  "Puedes descargarlo desde esta página.")
        return
    if not deliveries:
        messages.info(request, f"{done}. Ningún administrador tiene email: añádelo en "
                               "Miembros para recibir el informe automáticamente.")
        return
    sent = [d.email for d in deliveries if d.status == ReportDelivery.SENT]
    pending = [d.email for d in deliveries if d.status != ReportDelivery.SENT]
    if sent:
        messages.success(request, f"{done}. Informe enviado a {', '.join(sent)}.")
    if pending:
        messages.warning(request, f"{'' if sent else done + '. '}No se pudo enviar el informe a {', '.join(pending)}: "
                                  "se reintentará automáticamente. Mientras, puedes descargarlo desde esta página.")


@club_admin_required
def resend_call_report(request, match_id):
    """Vuelve a enviar el informe de una convocatoria cerrada a los administradores."""
    call = club_call(request, match__public_id=match_id)
    if request.method == "POST" and not call.draft_mode:
        _send_report(request, call, "Informe reenviado")
    return redirect('call_for_match', call.match.public_id)


@club_admin_required
def call_report_pdf(request, match_id):
    """Descarga manual del informe de convocatoria."""
    call = club_call(request, match__public_id=match_id)
    pdf = render_report(build_report(call))
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{report_filename(call.match)}"'
    return response

@club_admin_required
def edit_call(request, call_id):
    call = club_call(request, public_id=call_id)
    selected_players = list(call.players.values_list('id', flat=True))
    all_players = selectable_players(request.club, include_ids=selected_players)
    call_log, _ = CallLog.objects.get_or_create(call=call, defaults={'text': ''})
    
    current_time = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    if call.match.draft_mode == False:
        return redirect('call_for_match', call.match.public_id)
    else:
        if request.method == "POST":
            selected_players_ids = list(club_players(request, request.POST.getlist("players")).values_list('id', flat=True))
            selected_set = set(selected_players_ids)
            call_set = set(selected_players)

            added_players = selected_set - call_set
            removed_players = call_set - selected_set

            # Definir si el mensaje es para convocatoria abierta o cerrada
            status_message = "convocatoria abierta" if call.draft_mode else "convocatoria cerrada"

            # Inicializar el log_text
            log_text = ""

            # Construir el mensaje para los jugadores añadidos
            if added_players:
                added_player_names = [Player.objects.get(id=player_id).name for player_id in added_players]
                log_text += f"Jugadores añadidos con la {status_message}: " + ", ".join(added_player_names) + f" el día {current_time};"

            # Construir el mensaje para los jugadores eliminados
            if removed_players:
                removed_player_names = [Player.objects.get(id=player_id).name for player_id in removed_players]
                log_text += f"Jugadores eliminados con la {status_message}: " + ", ".join(removed_player_names) + f" el día {current_time};"

            # Guardar el log si hay algún mensaje
            if log_text.strip():  # Verifica que log_text no esté vacío
                call_log.text += log_text
                call_log.save()

            # Actualizar la convocatoria con los jugadores seleccionados
            call.players.set(selected_players_ids)
            call.save()
            
            return redirect('call_for_match', call.match.public_id)



    context = {
        'call': call,
        'all_players': all_players,
        'selected_players': selected_players,
    }
    return render(request, 'edit_call.html', context)

#VISTA POR SI SE INTENTA MODIFICAR UNA CONVOCATORIA YA CERRADA
@club_admin_required
def closed_call(request, call_id):
    call = club_call(request, public_id=call_id)
    return render(request, 'closed_call.html', {'match': call})


#VISTA POR SI SE INTENTA CREAR UNA CONVOCATORIA YA EXISTENTE
@club_admin_required
def existing_call_view(request, match_id):
    match = club_match(request, match_id)
    return render(request, 'existing_call.html', {'match': match})

#VISTA PARA MOSTRAR LA CONVOCATORIA
POSITION_GROUPS = (("Derecha", "Derecha"), ("Revés", "Revés"), ("Mixto", "Mixtos"))


@club_required
def call_for_match(request, match_id):
    match = club_match(request, match_id)
    call = Call.objects.filter(match=match).first()
    games = list(
        Game.objects.filter(match=match).order_by("n_game")
        .select_related("player_1_local", "player_2_local", "player_1_visiting", "player_2_visiting")
        .prefetch_related("results")
    )
    for g in games:
        g.result = next(iter(g.results.all()), None)  # usa el prefetch: sin consulta extra por partido

    groups = []
    if call:
        players = list(call.players.order_by("name", "last_name"))
        playing = {pid for g in games for pid in (g.player_1_local_id, g.player_2_local_id,
                                                  g.player_1_visiting_id, g.player_2_visiting_id) if pid}
        for p in players:
            p.is_playing = p.id in playing
        known = {key for key, _ in POSITION_GROUPS}
        for key, label in POSITION_GROUPS:
            members = [p for p in players if p.position == key or (key == "Mixto" and p.position not in known)]
            groups.append({"label": label, "players": members})

    return render(request, "call_for_match.html", {
        "call_for_match": call,
        "match_id": match.public_id,
        "game_for_match": games,
        "games_count": len(games),
        "match": match,
        "groups": groups,
        "players_count": sum(len(g["players"]) for g in groups),
        "report_deliveries": list(call.report_deliveries.order_by("email")) if call else [],
    })


def validate_game_for_match(call):
    if not call:
        return False, "No se pueden crear partidos, no existe ninguna convocatoria."
    if call.players.all().count() < 10:
        return False, "Para crear los partidos debes contar al menos con 10 jugadores"
    if call.draft_mode != False:
        return False, "Para crear los partidos debes confirmar la convocatoria"

    
    return True, None

#FUNCIÓN PARA CREAR PARTIDOS DENTRO DE UN ENFRENTAMIENTO
@club_admin_required
def create_game_for_match(request, match_id):
    match = club_match(request, match_id)
    call = Call.objects.filter(match=match).first()

    is_valid, error_message = validate_game_for_match(call)
    if not is_valid:
        messages.error(request, error_message)
        return redirect('call_for_match', match_id=match_id)

    if match.games.exists():
        messages.info(request, "Los partidos ya están creados: puedes cambiar las parejas desde aquí.")
        return redirect('edit_games_match', match_id=match.public_id)

    if request.method == "POST":
        try:
            lineup.create_games(match, lineup.parse_lineup(request.POST.get("ordered_games"), call))
        except lineup.LineupError as e:
            messages.error(request, str(e))
            return redirect('create_game', match_id=match.public_id)
        messages.success(request, "Partidos creados.")
        return redirect('call_for_match', match_id=match.public_id)

    return render(request, "create_game.html", {
        "call": call,
        "match": match,
        "players": call.players.order_by('name', 'last_name'),
        "games_per_match": lineup.GAMES_PER_MATCH,
    })


SET_FIELDS = ('set1_local', 'set1_visiting', 'set2_local', 'set2_visiting', 'set3_local', 'set3_visiting')


def _save_result(request, game, result, template):
    """Valida y guarda el resultado de un partido; si hay errores, vuelve al formulario."""
    values = {f: request.POST.get(f, '').strip() for f in SET_FIELDS}
    for field, value in values.items():
        setattr(result, field, value)
    try:
        result.full_clean(exclude=['game', 'result'] + list(SET_FIELDS), validate_unique=False)
        result.result = result.determine_winner()
        result.save()
    except ValidationError as e:
        return render(request, template, {"game": game, "result": result, "values": values, "errors": e.messages})

    game.winner = "Local" if result.result == "Victoria Local" else "Visitante"
    game.save(update_fields=['winner'])
    return redirect('call_for_match', match_id=game.match.public_id)


@club_admin_required
def create_result(request, game_id):
    game = get_object_or_404(Game.objects.select_related('match__local', 'match__visiting'), public_id=game_id, match__club=request.club)
    if not game.match.draft_mode:
        messages.error(request, "No se pueden añadir resultados a un partido ya confirmado")
        return redirect('call_for_match', match_id=game.match.public_id)
    if game.results.exists():
        return redirect('edit_result', game_id=game.public_id)

    if request.method == "POST":
        return _save_result(request, game, Result(game=game), "create_result.html")
    return render(request, "create_result.html", {"game": game, "values": {}})


@club_admin_required
def edit_result(request, game_id):
    game = get_object_or_404(Game.objects.select_related('match__local', 'match__visiting'), public_id=game_id, match__club=request.club)
    match = game.match
    result = get_object_or_404(Result, game=game)

    if not match.draft_mode:
        messages.error(request, "No se pueden editar los resultados de un partido ya confirmado")
        return redirect('call_for_match', match_id=match.public_id)

    if request.method == "POST":
        return _save_result(request, game, result, "edit_result.html")
    values = {f: '' if getattr(result, f) is None else getattr(result, f) for f in SET_FIELDS}
    return render(request, "edit_result.html", {"game": game, "result": result, "values": values})



def calculate_points(games):
    points_local = 0
    points_visiting = 0
    
    for g in games:
        if g.winner == "Visitante":
            points_visiting = points_visiting + g.score
        else:
            points_local = points_local + g.score
    
    return points_local, points_visiting

def determine_match_result(points_local, points_visiting):
    if points_local > points_visiting:
        return "Victoria Local"
    elif points_local < points_visiting:
        return "Victoria Visitante"
    else:
        return "Empate"
   
def valid_close_match(games,match):
    if match.draft_mode == False:
        return False, "No se pueden cerrar actas, el partido ya ha sido cerrado"
    if len(games) < 5:
        return False, "No se pueden cerrar actas, se requieren al menos 5 partidos."
    
    for g in games:
        if g.results.first() is None:
            return False, "No se pueden cerrar actas, algunos partidos no tienen resultado."
    
    return True, None     

@club_admin_required
def close_match(request, match_id):
    match = club_match(request, match_id)
    games = match.games.all()

    # Validar si se pueden cerrar las actas
    is_valid, error_message = valid_close_match(games, match)
    if not is_valid:
        messages.error(request, error_message)
        return redirect(call_for_match, match_id=match_id)

    # Calcular puntos y actualizar ganadores
    points_local, points_visiting = calculate_points(games)

    # Dar por finalizado los juegos
    for game in games:
        game.draft_mode = False
        game.save()

    # Determinar el resultado del partido
    match.result = determine_match_result(points_local, points_visiting)
    match.result_points = f"{points_local}/{points_visiting}"
    match.draft_mode = False
    match.save()

    return redirect('list_match')


@club_admin_required
def edit_game_match(request, match_id):
    match = club_match(request, match_id)

    if not match.draft_mode:
        messages.error(request, "No se pueden editar los partidos que se encuentran ya confirmados")
        return redirect('call_for_match', match_id=match_id)

    games = list(Game.objects.filter(match=match).order_by('n_game'))
    if not games:
        return redirect('create_game', match_id=match.public_id)
    call = club_call(request, match__public_id=match_id)

    if request.method == "POST":
        try:
            lineup.update_games(match, lineup.parse_lineup(request.POST.get("ordered_games"), call, match_games=games))
        except lineup.LineupError as e:
            messages.error(request, str(e))
            return redirect('edit_games_match', match_id=match.public_id)
        messages.success(request, "Parejas actualizadas.")
        return redirect('call_for_match', match_id=match.public_id)

    games_data = [
        {
            'gameId': game.id,
            'n_game': game.n_game,
            'player1Id': game.player_1_local_id or game.player_1_visiting_id,
            'player2Id': game.player_2_local_id or game.player_2_visiting_id,
        }
        for game in games
    ]

    return render(request, "edit_game_match.html", {
        "games": games_data,
        "match": match,
        "call": call,
        "players": call.players.order_by('name', 'last_name'),
    })








    

    



    





