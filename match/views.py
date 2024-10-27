from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import *
from .models import *
from call.models import Call
from team.models import Team
from datetime import datetime
from callLog.models import CallLog
from penalty.models import Penalty
from players.views import calculate_score

# Create your views here.
def list_match(request):
    match = Match.objects.all().order_by('-start_date')
    return render(request, "list_match.html", {'match': match})

@login_required
def create_match(request):
    if request.method == "POST":
        # Obtiene los datos del formulario
        local_id = request.POST.get('local')
        visiting_id = request.POST.get('visiting')
        start_date_str = request.POST.get('start_date')

        # Intenta convertir la fecha
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        except ValueError:
            return render(request, "create_match.html", {
                "form": MatchForm(request.POST),
                "error": "Fecha no válida. Usa el formato AAAA-MM-DD."
            })

        # Verifica que todos los campos necesarios están presentes
        try:
            local_team = Team.objects.get(id=local_id)
            visiting_team = Team.objects.get(id=visiting_id)
        except Team.DoesNotExist:
            return render(request, "create_match.html", {
                "form": MatchForm(request.POST),
                "error": "Uno de los equipos no existe."
            })

        # Verifica si el enfrentamiento es válido
        if local_team.name != "LOS GLADIADORES" and visiting_team.name != "LOS GLADIADORES":
            form = MatchForm(request.POST)  # Re-crea el formulario con los datos enviados
            return render(request, "create_match.html", {
                "form": form,
                "error": "No es un enfrentamiento válido. LOS GLADIADORES deben ser locales o visitantes"
            })

        # Verifica si los campos están completos
        if local_id and visiting_id and start_date:
            Match.objects.create(
                local_id=local_id,
                visiting_id=visiting_id,
                start_date=start_date,
            )
            return redirect("list_match")
        else:
            form = MatchForm(request.POST)  # Re-crea el formulario con los datos enviados
            return render(request, "create_match.html", {
                "form": form,
                "error": "Por favor, completa todos los campos."
            })
    else:
        form = MatchForm()

    return render(request, "create_match.html", {"form": form})


@login_required
def create_call(request, match_id):
    players = Player.objects.all()  # Asegúrate de que esto sea correcto
    match = Match.objects.get(id=match_id)  # Asegúrate de que esto sea correcto
    existing_call = Call.objects.filter(match_id=match_id).exists()


    if existing_call:
        return redirect('existing_call', match.id)
    
    player_penalties = {
        player.id: Penalty.objects.filter(player=player).values_list('reason', flat=True) 
        for player in players
    }
    
    
    if request.method == 'POST':
        players = request.POST.getlist('players')
        if not players:
              messages.error(request, "Debes seleccionar al menos un jugador.")
        else:
            call = Call(
                match = match, 
            )
            call.save()
            call.players.set(players)

            call_log = CallLog(
                call = call,
            )
            call_log.save()
            return redirect('call_for_match', match.id)
        
    return render(request, "create_call.html", {"players": players, "match": match, "player_penalties":player_penalties})


def validate_call(call):
    if call.players.all().count() < 10:
        return False, "Para cerrar una convocatoria al menos debes contar con 10 jugadores"
    if call.draft_mode == False:
        return False, "Esta convocatoria ha sido cerrada"
    
    return True, None

@login_required
def close_call(request, match_id):
    call = Call.objects.get(match__id=match_id)
    is_valid, error_message = validate_call(call)

    if not is_valid:
        messages.error(request, error_message)
        return redirect(call_for_match, match_id=match_id)

    if request.method == "POST":
        call.draft_mode = False
        call.save()
        return redirect('call_for_match', call.match.id)
    
    return redirect('call_for_match', call.match.id)

@login_required
def edit_call(request, call_id):
    call = get_object_or_404(Call, id=call_id)
    all_players = Player.objects.all()
    selected_players = call.players.values_list('id', flat=True)
    call_log = get_object_or_404(CallLog, call=call_id)
    
    current_time = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    if call.match.draft_mode == False:
        return redirect('call_for_match', call.match.id)
    else:
        if request.method == "POST":
            selected_players_ids = request.POST.getlist("players")  # Lista de jugadores seleccionados
            selected_set = set(map(int, selected_players_ids))
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
            
            return redirect('call_for_match', call.match.id)



    context = {
        'call': call,
        'all_players': all_players,
        'selected_players': selected_players,
    }
    return render(request, 'edit_call.html', context)

#VISTA POR SI SE INTENTA MODIFICAR UNA CONVOCATORIA YA CERRADA
@login_required
def closed_call(request, call_id):
    call = Call.objects.get(id=call_id)
    return render(request, 'closed_call.html', {'match': call})


#VISTA POR SI SE INTENTA CREAR UNA CONVOCATORIA YA EXISTENTE
@login_required
def existing_call_view(request, match_id):
    match = Match.objects.get(id=match_id)
    return render(request, 'existing_call.html', {'match': match})

#VISTA PARA MOSTRAR LA CONVOCATORIA
def call_for_match(request,match_id):
    try:
        call_for_match = Call.objects.get(match_id=match_id)
    except Call.DoesNotExist:
        match = Match.objects.get(id=match_id)  # Asegúrate de que esto siempre tenga una coincidencia
        return render(request, "call_for_match.html", {
            "match": match,
            "call_for_match": None,  # Indica que no hay convocatoria
            "match_id": match_id,
            "game_for_match": Game.objects.filter(match_id=match_id),
            "backhand_players": [],
            "forehand_players": [],
            "mixed_players": [],
            "no_call": True  # Indicador que puedes usar en tu plantilla
        })

    match = Match.objects.get(id=match_id)
    game_for_match = Game.objects.filter(match_id=match_id)

    backhand_players = []
    forehand_players = []
    mixed_players = []
    players = call_for_match.players.all() 
    for p in players:
        if p.position == "Revés":
            backhand_players.append(p)
        elif p.position == "Derecha":
            forehand_players.append(p)
        else:
            mixed_players.append(p)    
   
    context = {
        'call_for_match': call_for_match,
        "match_id":match_id,
        "game_for_match":game_for_match,
        "match":match,
        "backhand_players": backhand_players,
        "forehand_players": forehand_players,
        "mixed_players": mixed_players,
    }

    return render(request, "call_for_match.html",context)


def validate_game_for_match(call):
    if not call:
        return False, "No se pueden crear partidos, no existe ninguna convocatoria."
    if call.players.all().count() < 10:
        return False, "Para crear los partidos debes contar al menos con 10 jugadores"
    if call.draft_mode != False:
        return False, "Para crear los partidos debes confirmar la convocatoria"

    
    return True, None

#FUNCIÓN PARA CREAR PARTIDOS DENTRO DE UN ENFRENTAMIENTO
@login_required
def create_game_for_match(request, match_id):
    call = Call.objects.filter(match_id=match_id).first()
    match = get_object_or_404(Match, id=match_id)
    team = Team.objects.filter(name="LOS GLADIADORES").first()

    is_valid, error_message = validate_game_for_match(call)
    if not is_valid:
        messages.error(request, error_message)
        return redirect('call_for_match', match_id=match_id)

    if request.method == "POST":
        all_games_data, error_messages = process_games_data(request, match, team)

        if error_messages:
            for error_message in error_messages:
                messages.error(request, error_message)
            return render(request, "create_game.html", {
                "call": call,
                "match": match,
                "team": team,
                "post_data": request.POST
            })

        # Guardar los datos de los partidos en la base de datos
        save_games(all_games_data)
        return redirect('call_for_match', match_id=match.id)

    return render(request, "create_game.html", {"call": call})


def process_games_data(request, match, team):
    """
    Procesa los datos de los partidos y retorna una lista con los datos válidos y una lista con mensajes de error.
    """
    all_games_data = []
    error_messages = []

    for i in range(1, 6):  # Iterar por los partidos 1 a 5
        player_1_id = request.POST.get(f'player_1_{i}')
        player_2_id = request.POST.get(f'player_2_{i}')
        n_game = request.POST.get(f'n_game_{i}')

        if not player_1_id or not player_2_id:
            error_messages.append(f"Por favor selecciona ambos jugadores para el partido {n_game}.")
            continue

        player_1 = get_object_or_404(Player, id=player_1_id)
        player_2 = get_object_or_404(Player, id=player_2_id)
        score = 3 if int(n_game) in [1, 2] else 2

        # Determinar si los jugadores son locales o visitantes
        game_data = {
            'match': match,
            'n_game': n_game,
            'player_1_local': player_1 if match.local.name == team.name else None,
            'player_2_local': player_2 if match.local.name == team.name else None,
            'player_1_visiting': player_1 if match.visiting.name == team.name else None,
            'player_2_visiting': player_2 if match.visiting.name == team.name else None,
            'score': score
        }
        all_games_data.append(game_data)

    return all_games_data, error_messages


def save_games(all_games_data):
    """
    Guarda los datos de todos los partidos en la base de datos.
    """
    for game_data in all_games_data:
        Game.objects.create(
            match=game_data['match'],
            n_game=game_data['n_game'],
            player_1_local=game_data['player_1_local'],
            player_2_local=game_data['player_2_local'],
            player_1_visiting=game_data['player_1_visiting'],
            player_2_visiting=game_data['player_2_visiting'],
            score=game_data['score']
        )
    


@login_required
def create_result(request, game_id):
    game = get_object_or_404(Game, id=game_id)

    if request.method == "POST":
        set1_local = request.POST.get('set1_local')
        set1_visiting = request.POST.get('set1_visiting')
        set2_local = request.POST.get('set2_local')
        set2_visiting = request.POST.get('set2_visiting')
        set3_local = request.POST.get('set3_local')
        set3_visiting = request.POST.get('set3_visiting')

        result = Result(
            game=game,
            set1_local=set1_local,
            set1_visiting=set1_visiting,
            set2_local=set2_local,
            set2_visiting=set2_visiting,
            set3_local=set3_local,
            set3_visiting=set3_visiting,
        )

        try:
            result.result = result.determine_winner()
            result.save()

            if result.determine_winner() == "Victoria Local":
                game.winner = "Local"
            else:
                game.winner = "Visitante"
            game.save()
            return redirect('call_for_match', match_id=game.match.id)

        except ValidationError as e:
            return render(request, "create_result.html", {
                "game": game,
                "set1_local": set1_local,
                "set1_visiting": set1_visiting,
                "set2_local": set2_local,
                "set2_visiting": set2_visiting,
                "set3_local": set3_local,
                "set3_visiting": set3_visiting,
                "error": str(e), 
            })

    return render(request, "create_result.html", {"game": game})


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

@login_required
def close_match(request, match_id):
    match = Match.objects.get(id=match_id)
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

    # Actualizar el rendimiento de los jugadores
    if match.local.name == "LOS GLADIADORES":
        update_player_scores(games, is_local=True)
    elif match.local.name == "LOS GLADIADORES":
        update_player_scores(games, is_local=False)

    return redirect('list_match')


def update_player_scores(games, is_local):
    for game in games:
        if is_local:
            players = [game.player_1_local, game.player_2_local]
        else:
            players = [game.player_1_visiting, game.player_2_visiting]

        for player in players:
            player_score = calculate_score(player)
            player.score = player_score
            player.save()


    

    



    





