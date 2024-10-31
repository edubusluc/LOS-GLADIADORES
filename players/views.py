import unicodedata
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .forms import PlayerForm
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.contrib import messages
from match.models import Game
from players.models import Player
from django.db.models import Q

from .scraper import scrape_scores
# Create your views here.


@login_required
def create_player(request):
    if request.method == "POST":
        form = PlayerForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect("list_players")
        else: 
            messages.error(request, "Error al crear el jugador. Por favor, verifica los datos.")
    else:
        form = PlayerForm()

    # Agregar clases a cada campo
    for field in form:
        field.field.widget.attrs.update({'class': 'form-control'})

    return render(request, "create_player.html", {"form": form})



def list_players(request):
    order_by = request.GET.get('order_by', 'name')
    players = Player.objects.all().order_by(order_by)
    paginator = Paginator(players, 6)  # Puedes ajustar el número de jugadores por página

    # Obtén el número de página de la solicitud GET
    page = request.GET.get('page')  

    try:
        players = paginator.page(page)
    except PageNotAnInteger:
        players = paginator.page(1)
    except EmptyPage:
        players = paginator.page(paginator.num_pages)

    return render(request, 'list_players.html', {'players': players, 'order_by':order_by})

@login_required
def edit_player(request, player_id):
    player = get_object_or_404(Player, id=player_id)  # Asegúrate de que estás usando el modelo correcto

    if request.method == "POST":
        name = request.POST.get("name")
        position = request.POST.get("position")
        skillfull_hand = request.POST.get("skillfull_hand")

        player.name = name
        player.position = position
        player.skillfull_hand = skillfull_hand
        player.save()

        return redirect('list_players')  # Redirigir a la lista de jugadores después de guardar

    context = {
        'player': player  # Asegúrate de pasar el objeto player a la plantilla
    }
    return render(request, 'edit_player.html', context)  # Renderizar con el contexto correcto


@login_required
def delete_player(request, player_id):
    player = get_object_or_404(Player, id=player_id)
    if request.method == "POST":
        player.delete()
        return redirect('list_players')
    
    return render(request, 'confirm_delete.html', {'player': player})

def show_player(request, player_id):
    player = get_object_or_404(Player, id=player_id)
    games = Game.objects.filter(
        (Q(player_1_local=player) | Q(player_2_local=player) |
        Q(player_1_visiting=player) | Q(player_2_visiting=player)) &
        Q(draft_mode=False)
    ).order_by('-match__start_date')[:5]
    # Calcula la puntuación, si es necesario
    normalized_score = calculate_score(player)  # Llama a la función y guarda el resultado
    emoticon = get_emoticon(normalized_score)
    return render(request, "player_detail.html", {"player": player,
                                                   "score": normalized_score,
                                                   'emoticon': emoticon,
                                                   "games":games})

def get_emoticon(score):
    if 0 <= score <= 3:
        return "📉📉"
    elif 4 <= score <= 6:
        return "😄"
    elif 7 <= score <= 8:
        return "😎"
    elif 9 <= score <= 10:
        return "🔥"
    else:
        return ""

@login_required
def force_update_score(request):
    players = Player.objects.all()
    for player in players:
        score = calculate_score(player)
        player.score = score
        player.save()
    return redirect("list_players")


def calculate_score(player):
    games = Game.objects.filter(
        (Q(player_1_local=player) | Q(player_2_local=player) |
        Q(player_1_visiting=player) | Q(player_2_visiting=player)) &
        Q(draft_mode=False)
    ).order_by('-match__start_date')[:3]

    games_win = 0
    games_lost = 0
    consecutive_wins = 0
    max_consecutive_wins = 0
    three_point_wins = 0

    if len(games) == 0: 
        normalized_score = -1
    else:
        for game in games:
            if player in [game.player_1_local, game.player_2_local]:  # Jugador local
                if game.winner == "Local":
                    games_win += 1
                    consecutive_wins += 1
                    if game.score == 3: three_point_wins +=1
                elif game.winner == "Visitante":
                    games_lost += 1
                    consecutive_wins = 0  # Rompe la racha
            elif player in [game.player_1_visiting, game.player_2_visiting]:  # Jugador visitante
                if game.winner == "Visitante":
                    games_win += 1
                    consecutive_wins += 1
                    if game.score == 3: three_point_wins +=1
                elif game.winner == "Local":
                    games_lost += 1
                    consecutive_wins = 0  # Rompe la racha

            # Actualiza la máxima racha de victorias
            max_consecutive_wins = max(max_consecutive_wins, consecutive_wins)

        # Puntuación básica
        score = games_win * 4 - games_lost

    # Bonificación por rachas de victorias
        score += (max_consecutive_wins - 1) * 3  #

        # Bonificación por victorias en partidos de 3 puntos
        score += three_point_wins * 2  # 2 puntos extra por cada victoria en un partido de 3 puntos

        # Calcular el número de partidos jugados
        total_games_played = games_win + games_lost
        # Ajustar la puntuación máxima según el número de partidos jugados
        max_possible_score = total_games_played * 3 + (max_consecutive_wins - 1) * 2 + three_point_wins * 2

        # Puntuación normalizada
        normalized_score = max(0, min(10, (score / max_possible_score) * 10)) if max_possible_score > 0 else 0
    
    return round(normalized_score)  # Retorna la puntuación normalizada



def find_player_score(player_name, scores_list):
    # Filtrar la lista para encontrar al jugador por nombre
    player_scores = [player for player in scores_list if player['name'].lower() == player_name.lower()]
    
    if player_scores:
        return player_scores[0]  # Retornar el primer resultado encontrado
    else:
        return None  # Retornar None si no se encuentra el jugador
    


#SNP SCORE
def get_snp_score(request):
    dicc = scrape_scores("https://intranet.seriesnacionalesdepadel.com/equipo/view/4380", "jedu937", "j3du")

    for p in dicc:
        name = p["name"]
        score = p["score"]
        name_parts = name.split()

        if len(name_parts) == 2:
            name = name_parts[0]
            last_name = name_parts[1]

            try:
                player = Player.objects.get(name__iexact=name, last_name__icontains=last_name)
                player.snp_score = score
                player.save()
            except: 
                print(f"NO se encontro al jugador {name} {last_name}")

        if len(name_parts) == 3:
            name = name_parts[0]
            last_name = ' '.join(name_parts[1:])
            try:
                player = Player.objects.get(name__iexact=name, last_name__icontains=last_name)
                player.snp_score = score
                player.save()
            except: 
                print(f"NO se encontro al jugador {name} {last_name}")
        
        if len(name_parts) > 3:
            name = ' '.join(name_parts[:2])
            last_name = ' '.join(name_parts[2:])
            try:
                player = Player.objects.get(name__iexact=name, last_name__icontains=last_name)
                player.snp_score = score
                player.save()
            except: 
                print(f"NO se encontro al jugador {name} {last_name}")
    return redirect("list_players")







    

