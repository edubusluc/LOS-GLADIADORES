from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import MatchForm
from .models import Match, Game, Result
from players.models import Player
from call.models import Call
from team.models import Team
from datetime import datetime
from callLog.models import CallLog
from penalty.models import Penalty
from players.views import calculate_score
import json
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage


CREATE_MATCH_HTML = "create_match.html"
LOS_GLADIADORES = "LOS GLADIADORES"
# Create your views here.
def list_match(request):
    matches = Match.objects.all().order_by('-start_date')
    paginator = Paginator(matches, 5)
    page = request.GET.get('page')

    try:
        matches = paginator.page(page)
    except PageNotAnInteger:
        matches = paginator.page(1)
    except EmptyPage:
        matches = paginator.page(paginator.num_pages)

    return render(request, "list_match.html", {'matches': matches})

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
            return render(request, CREATE_MATCH_HTML, {
                "form": MatchForm(request.POST),
                "error": "Fecha no válida. Usa el formato AAAA-MM-DD."
            })

        # Verifica que todos los campos necesarios están presentes
        try:
            local_team = Team.objects.get(id=local_id)
            visiting_team = Team.objects.get(id=visiting_id)
        except Team.DoesNotExist:
            return render(request, CREATE_MATCH_HTML, {
                "form": MatchForm(request.POST),
                "error": "Uno de los equipos no existe."
            })

        # Verifica si el enfrentamiento es válido
        if local_team.name != LOS_GLADIADORES and visiting_team.name != LOS_GLADIADORES:
            form = MatchForm(request.POST)  # Re-crea el formulario con los datos enviados
            return render(request, CREATE_MATCH_HTML, {
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
            return redirect("list_match")  # Redirección después de crear el partido
        else:
            form = MatchForm(request.POST)  # Re-crea el formulario con los datos enviados
            return render(request,CREATE_MATCH_HTML, {
                "form": form,
                "error": "Por favor, completa todos los campos."
            })
    else:
        form = MatchForm()

    return render(request, CREATE_MATCH_HTML, {"form": form})

@login_required
def delete_match(request, match_id):
    try:
        match = get_object_or_404(Match, id=match_id)
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


@login_required
def create_call(request, match_id):
    players = Player.objects.all()  
    match = Match.objects.get(id=match_id) 
    existing_call = Call.objects.filter(match_id=match_id).exists()


    if existing_call or match.draft_mode == False:
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
    game_for_match = Game.objects.filter(match_id=match_id).order_by("n_game")

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

    if Game.objects.filter(match=match).exists():
        messages.error(request, "Ya se han creado los partidos para este enfrentamiento.")
        return redirect('call_for_match', match_id=match_id)

    is_valid, error_message = validate_game_for_match(call)
    if not is_valid:
        messages.error(request, error_message)
        return redirect('call_for_match', match_id=match_id)

    if request.method == "POST":
        ordered_games_data = json.loads(request.POST.get("ordered_games", "[]"))

        for idx, game in enumerate(ordered_games_data, start=1):
            try:
                player_1 = Player.objects.get(id=game['player1Id'])
                player_2 = Player.objects.get(id=game['player2Id'])
            except Player.DoesNotExist:
                messages.error(request, "Uno de los jugadores no existe.")
                return redirect('call_for_match', match_id=match_id)

            if match.local.name == LOS_GLADIADORES:
                new_game = Game(
                    match=match,
                    n_game=idx,  # Asigna el número de juego según el índice
                    player_1_local=player_1,
                    player_2_local=player_2,
                    player_1_visiting=None,  # Si es local, puedes dejarlo en None
                    player_2_visiting=None,  # Si es local, puedes dejarlo en None
                    score=calculate_score(idx),
                    winner=None,  # Asigna el ganador si es necesario
                    draft_mode=False  # Cambia según la lógica de tu aplicación
                )
            elif match.visiting.name == LOS_GLADIADORES:
                new_game = Game(
                    match=match,
                    n_game=idx,  # Asigna el número de juego según el índice
                    player_1_local=None,
                    player_2_local=None,
                    player_1_visiting=player_1,
                    player_2_visiting=player_2,
                    score=calculate_score(idx),
                    winner=None,  # Asigna el ganador si es necesario
                    draft_mode=False  # Cambia según la lógica de tu aplicación
                )
            else:
                messages.error(request, "El partido no es de LOS GLADIADORES.")
                return redirect('create_game', match_id=match_id)

            try:
                new_game.save()
            except Exception as e:
                messages.error(request, f"Error al guardar el juego: {str(e)}")
                return redirect('create_game', match_id=match_id)

        return redirect('call_for_match', match_id=match.id)

    return render(request, "create_game.html", {"call": call})

    
def calculate_score(index):
    if index == 1 or index == 2: return 3
    else: return 2

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
            # Pasa los valores de los campos al contexto para que se mantengan
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



@login_required
def edit_result(request, game_id):
    game = get_object_or_404(Game, id=game_id)
    match = game.match
    result = get_object_or_404(Result, game=game)  # Obtener el resultado del juego

    if not match.draft_mode:
        messages.error(request, "No se pueden editar los resultados de un partido ya confirmado")
        return redirect('call_for_match', match_id=match.id)

    if request.method == "POST":
        set1_local = request.POST.get('set1_local')
        set1_visiting = request.POST.get('set1_visiting')
        set2_local = request.POST.get('set2_local')
        set2_visiting = request.POST.get('set2_visiting')
        set3_local = request.POST.get('set3_local')
        set3_visiting = request.POST.get('set3_visiting')

        # Asignar los nuevos valores a los sets
        result.set1_local = set1_local
        result.set1_visiting = set1_visiting
        result.set2_local = set2_local
        result.set2_visiting = set2_visiting
        result.set3_local = set3_local
        result.set3_visiting = set3_visiting

        try:
            # Determinar el ganador basado en los sets actualizados
            result.result = result.determine_winner()
            result.save()

            # Actualizar el ganador del partido en base al resultado
            if result.result == "Victoria Local":
                game.winner = "Local"
            else:
                game.winner = "Visitante"
            game.save()

            # Redirigir al detalle del partido después de guardar
            return redirect('call_for_match', match_id=game.match.id)

        except ValidationError as e:
            # Si hay un error de validación, devolver el formulario con el mensaje de error
            return render(request, "edit_result.html", {
                "game": game,
                "result": result,
                "set1_local": set1_local,
                "set1_visiting": set1_visiting,
                "set2_local": set2_local,
                "set2_visiting": set2_visiting,
                "set3_local": set3_local,
                "set3_visiting": set3_visiting,
                "error": str(e),
            })

    return render(request, "edit_result.html", {"result": result, "game": game})



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
    if match.local.name == LOS_GLADIADORES:
        update_player_scores(games, is_local=True)
    elif match.visiting.name == LOS_GLADIADORES:
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

@login_required
def edit_game_match(request, match_id):
    match = get_object_or_404(Match, id=match_id)

    if not match.draft_mode:
        messages.error(request, "No se pueden editar los partidos que se encuentran ya confirmados")
        return redirect('call_for_match', match_id=match_id)
    
    games = Game.objects.filter(match_id=match_id).order_by('n_game')

    def get_player(game_data, player_key):
        """Obtiene un jugador dado un diccionario de datos de juego y la clave del jugador."""
        try:
            return Player.objects.get(id=game_data[player_key])
        except Player.DoesNotExist:
            return None

    def update_game(game, player_1, player_2, idx):
        """Actualiza un juego con los jugadores y el número de juego."""
        if match.local.name == "LOS GLADIADORES":
            game.player_1_local = player_1
            game.player_2_local = player_2
            game.player_1_visiting = None
            game.player_2_visiting = None
        elif match.visiting.name == "LOS GLADIADORES":
            game.player_1_visiting = player_1
            game.player_2_visiting = player_2
            game.player_1_local = None
            game.player_2_local = None

        game.n_game = idx
        game.draft_mode = True

    def is_player_repeated(player_1, player_2, used_players):
        """Verifica si los jugadores ya han sido asignados."""
        message=""
        flag = False
        if player_1.id in used_players:
                message = f"El jugador {player_1} se encuentra repetido."
                flag = True
        if player_2.id in used_players:
                message = f"El jugador {player_1} se encuentra repetido."
                flag = True

        return flag, message

    if request.method == "POST":
        ordered_games_data = json.loads(request.POST.get("ordered_games", "[]"))
        used_players = set()

        for idx, game_data in enumerate(ordered_games_data, start=1):
            game = Game.objects.filter(id=game_data['gameId']).first()
            if not game:
                messages.error(request, "Uno de los juegos no existe.")
                return redirect('edit_game_match', match_id=match_id)

            player_1 = get_player(game_data, 'player1Id')
            player_2 = get_player(game_data, 'player2Id')

            if not player_1 or not player_2:
                messages.error(request, "Uno de los jugadores no existe.")
                return redirect('edit_game_match', match_id=match_id)

            if player_1 == player_2:
                messages.error(request, f"Existe un jugador repetido en el partido: {game.n_game}")
                return redirect(request.path)
            
            flag, message = is_player_repeated(player_1, player_2, used_players)
            if flag:
                messages.error(request, f"{message}")
                return redirect(request.path)

            used_players.add(player_1.id)
            used_players.add(player_2.id)

            update_game(game, player_1, player_2, idx)

            try:
                game.save()
            except Exception as e:
                messages.error(request, f"Error al actualizar el juego: {str(e)}")
                return redirect('edit_game_match', match_id=match_id)

        messages.success(request, "Juegos actualizados exitosamente.")
        return redirect('call_for_match', match_id=match.id)

    games_data = [
        {
            'gameId': game.id,
            'n_game': game.n_game,
            'player1Id': game.player_1_local.id if game.player_1_local else game.player_1_visiting.id,
            'player2Id': game.player_2_local.id if game.player_2_local else game.player_2_visiting.id,
        }
        for game in games
    ]

    call = Call.objects.get(match_id=match_id)

    return render(request, "edit_game_match.html", {"games": games_data, "match": match, "call": call})








    

    



    





