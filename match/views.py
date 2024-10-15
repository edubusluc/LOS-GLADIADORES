from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .forms import *
from .models import *
from call.models import Call
from team.models import Team

# Create your views here.
def list_match(request):
    match = Match.objects.all()
    return render(request, "list_match.html", {'match': match})

def create_match(request):
    team = Team.objects.all()
    if request.method == "POST":
        form = MatchForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("list_match") 

    else:
        form = MatchForm()  # Crea una nueva instancia del formulario para mostrar en GET

    return render(request, "create_match.html", {"form": form, "team":team})  # Renderiza el formulario


def create_call(request, match_id):
    players = Player.objects.all()  # Asegúrate de que esto sea correcto
    match = Match.objects.get(id=match_id)  # Asegúrate de que esto sea correcto
    existing_call = Call.objects.filter(match_id=match_id).exists()


    if existing_call:
        return redirect('existing_call', match.id)
    
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
            return redirect('call_for_match', match.id)
        
    return render(request, "create_call.html", {"players": players, "match": match})

def validate_call(call):
    if call.players.all().count() < 10:
        return False, "Para cerrar una convocatoria al menos debes contar con 10 jugadores"
    if call.draft_mode == False:
        return False, "Esta convocatoria ha sido cerrada"
    
    return True, None

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


def edit_call(request, call_id):
    call = get_object_or_404(Call, id = call_id)
    all_players = Player.objects.all()
    selected_players = call.players.values_list('id', flat=True)

    if call.draft_mode == False:
        return redirect('closed_call', call.id)

    if request.method == "POST":
        selected_players_ids = request.POST.getlist("players")  # Lista de jugadores seleccionados
        # Actualizar la convocatoria con los jugadores seleccionados
        call.players.set(selected_players_ids)
        call.save()

        return redirect('call_for_match', call.match.id)
    context = {
        'call': call,
        'all_players': all_players,
        'selected_players': selected_players
    }
    return render(request, 'edit_call.html',context)

#VISTA POR SI SE INTENTA MODIFICAR UNA CONVOCATORIA YA CERRADA
def closed_call(request, call_id):
    call = Call.objects.get(id=call_id)
    return render(request, 'closed_call.html', {'match': call})


#VISTA POR SI SE INTENTA CREAR UNA CONVOCATORIA YA EXISTENTE
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

    equipo_local = Team.objects.get(id=match.local.id)
    equipo_visitante = Team.objects.get(id=match.visiting.id)
    
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


def create_game_for_match(request, match_id):
    call = Call.objects.filter(match_id=match_id).first()
    match = get_object_or_404(Match, id=match_id)
    
    is_valid, error_message = validate_game_for_match(call)
    if not is_valid:
        messages.error(request, error_message)
        return redirect(call_for_match, match_id=match_id)

    if request.method == "POST":
        for i in range(1, 6):  # Para los partidos 1 a 5
            local_players = (request.POST.get(f'player_1_{i}'), request.POST.get(f'player_2_{i}')) if match.local.id == 1 else (None, None)
            visiting_players = (request.POST.get(f'player_1_{i}'), request.POST.get(f'player_2_{i}')) if match.visiting.id == 1 else (None, None)

            player_1_local, player_2_local = local_players
            player_1_visiting, player_2_visiting = visiting_players

            # Obtener objetos Player si existen
            if player_1_local and player_2_local:
                player_1_local = get_object_or_404(Player, id=player_1_local)
                player_2_local = get_object_or_404(Player, id=player_2_local)
            if player_1_visiting and player_2_visiting:
                player_1_visiting = get_object_or_404(Player, id=player_1_visiting)
                player_2_visiting = get_object_or_404(Player, id=player_2_visiting)

            n_game = request.POST.get(f'n_game_{i}')  # Obtener el número del partido  
            if (player_1_local and player_2_local) or (player_1_visiting and player_2_visiting):
                score = 3 if int(n_game) in [1, 2] else 2
                game = Game(
                    match=match,
                    n_game=n_game,
                    player_1_local=player_1_local,
                    player_2_local=player_2_local,
                    player_1_visiting=player_1_visiting,
                    player_2_visiting=player_2_visiting,
                    score=score
                )
                game.save()  # Guarda el partido en la base de datos
            else:
                messages.error(request, f"Por favor selecciona ambos jugadores para el partido {n_game}.")
                
        return redirect('call_for_match', match_id=match.id)

    return render(request, "create_game.html", {"call": call})



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
            game = game,
            set1_local = set1_local,
            set1_visiting = set1_visiting,
            set2_local = set2_local,
            set2_visiting = set2_visiting,
            set3_local = set3_local,
            set3_visiting = set3_visiting,
        )
        result.result = result.determine_winner()
        result.save()
        
        if result.determine_winner() == "Victoria Local":
            game.winner = "Local"
        else:
            game.winner = "Visitante"
        game.save()
        return redirect('call_for_match', match_id=game.match.id)  
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

def close_match(request, match_id):
    match = Match.objects.get(id=match_id)
    games = match.games.all()

    # Validar si se pueden cerrar las actas
    is_valid, error_message = valid_close_match(games,match)
    if not is_valid:
        messages.error(request, error_message)
        return redirect(call_for_match, match_id=match_id)

    # Calcular puntos y actualizar ganadores
    points_local, points_visiting = calculate_points(games)

    # Determinar el resultado del partido
    match.result = determine_match_result(points_local, points_visiting)
    match.result_points = f"{points_local}/{points_visiting}"
    match.draft_mode = False
    match.save()
    return redirect('list_match')


    

    



    





