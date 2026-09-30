from django.shortcuts import render, redirect, get_object_or_404
from core.decorators import club_required, club_admin_required
from .forms import PlayerForm
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.contrib import messages
from match.models import Game
from players.models import Player
from django.db.models import Q
import os
from dotenv import load_dotenv


# Create your views here.


@club_admin_required
def create_player(request):
    if request.method == "POST":
        form = PlayerForm(request.POST, request.FILES)
        if form.is_valid():
            player = form.save(commit=False)
            player.club = request.club
            player.team = request.club.own_team
            player.save()
            return redirect("list_players")
        else: 
            messages.error(request, "Error al crear el jugador. Por favor, verifica los datos.")
    else:
        form = PlayerForm()

    # Agregar clases a cada campo
    for field in form:
        field.field.widget.attrs.update({'class': 'form-control'})

    return render(request, "create_player.html", {"form": form})


ORDER_FIELDS = {'name', '-name', 'last_name', '-last_name', 'position', '-position', 'snp_score', '-snp_score'}


@club_required
def list_players(request):
    order_by = request.GET.get('order_by', 'name')
    if order_by not in ORDER_FIELDS:
        order_by = 'name'
    search = request.GET.get('search', '').strip()

    players = Player.objects.filter(club=request.club)
    if request.membership.is_admin:
        players = players.order_by('-in_team', order_by)
    else:
        players = players.filter(in_team=True).order_by(order_by)

    if search:
        players = players.filter(
            Q(name__icontains=search) | Q(last_name__icontains=search)
        )

    paginator = Paginator(players, 6)  # Puedes ajustar el número de jugadores por página

    page = request.GET.get('page')

    try:
        players = paginator.page(page)
    except PageNotAnInteger:
        players = paginator.page(1)
    except EmptyPage:
        players = paginator.page(paginator.num_pages)

    return render(request, 'list_players.html', {
        'players': players,
        'order_by': order_by,
        'search': search,
    })

@club_admin_required
def edit_player(request, player_id):
    player = get_object_or_404(Player, id=player_id, club=request.club)  # Asegúrate de que estás usando el modelo correcto

    if request.method == "POST":
        name = request.POST.get("name")
        position = request.POST.get("position")
        skillfull_hand = request.POST.get("skillfull_hand")
        joined_season = request.POST.get("joined_season")
        in_team = 'in_team' in request.POST

        player.name = name
        player.position = position
        player.skillfull_hand = skillfull_hand
        player.in_team = in_team
        player.joined_season = joined_season
        player.save()

        return redirect('list_players')  # Redirigir a la lista de jugadores después de guardar

    context = {
        'player': player  # Asegúrate de pasar el objeto player a la plantilla
    }
    return render(request, 'edit_player.html', context)  # Renderizar con el contexto correcto


@club_required
def show_player(request, player_id):
    player = get_object_or_404(Player, id=player_id, club=request.club)
    games = Game.objects.filter(
        (Q(player_1_local=player) | Q(player_2_local=player) |
        Q(player_1_visiting=player) | Q(player_2_visiting=player)) &
        Q(draft_mode=False)
    ).select_related(
        'match__local', 'match__visiting',
        'player_1_local', 'player_2_local', 'player_1_visiting', 'player_2_visiting',
    ).order_by('-match__start_date')[:5]
    return render(request, "player_detail.html", {"player": player, "games": games})


@club_admin_required
def manage_roster(request):
    """Marca de una vez qué jugadores están en el equipo."""
    players = Player.objects.filter(club=request.club).order_by('name', 'last_name')

    if request.method == "POST":
        in_team_ids = {int(i) for i in request.POST.getlist('in_team') if i.isdigit()}
        joined = players.filter(id__in=in_team_ids, in_team=False).update(in_team=True)
        left = players.exclude(id__in=in_team_ids).filter(in_team=True).update(in_team=False)
        if joined or left:
            messages.success(request, f"Plantilla actualizada: {joined} alta{'s' if joined != 1 else ''} y {left} baja{'s' if left != 1 else ''}.")
        else:
            messages.info(request, "No había cambios que guardar.")
        return redirect('manage_roster')

    return render(request, 'manage_roster.html', {
        'players': players,
        'in_team_count': sum(p.in_team for p in players),
    })


def find_player_score(player_name, scores_list):
    # Filtrar la lista para encontrar al jugador por nombre
    player_scores = [player for player in scores_list if player['name'].lower() == player_name.lower()]
    
    if player_scores:
        return player_scores[0]  # Retornar el primer resultado encontrado
    else:
        return None  # Retornar None si no se encuentra el jugador
    


#SNP SCORE
# load_dotenv()
# def get_snp_score(request):
#     dicc = scrape_scores("https://intranet.seriesnacionalesdepadel.com/equipo/view/4380", "jedu937", os.getenv('SCRAPPER_KEY'))

#     if dicc:
#         for p in dicc:
#             name = p["name"]
#             score = p["score"]
#             name_parts = name.split()

#             if not name_parts:
#                 continue  # Salta si el nombre está vacío

#             name, last_name = extract_name_last_name(name_parts)

#             try:
#                 player = Player.objects.get(name__iexact=name, last_name__icontains=last_name)
#                 player.snp_score = score
#                 player.save()
#             except Player.DoesNotExist:  # Manejo específico de la excepción
#                 messages.error(request, f"NO se encontró al jugador {name} {last_name}")
#                 return redirect("list_players")

#         return redirect("list_players")
#     else:
#         messages.error(request, "No se ha podido actualizar la puntuación")
#         return redirect("list_players")

# def extract_name_last_name(name_parts):
#     """Extrae el nombre y el apellido(s) de la lista de partes del nombre."""
#     if len(name_parts) == 2:
#         return name_parts[0], name_parts[1]
#     elif len(name_parts) == 3:
#         return name_parts[0], ' '.join(name_parts[1:])
#     else:
#         return ' '.join(name_parts[:2]), ' '.join(name_parts[2:])







    

