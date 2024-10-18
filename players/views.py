from django.shortcuts import render, redirect, get_object_or_404
from .forms import *
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from team.models import Team
# Create your views here.

def create_player(request):
    if request.method == "POST":
        form = Playerform(request.POST)

        if form.is_valid():
            player = form.save(commit=False)
            default_team = get_object_or_404(Team, id=1)
            player.team = default_team
            player.save()
            form.save()
            return redirect("list_players") 

    else:
        form = Playerform()  # Crea una nueva instancia del formulario para mostrar en GET

    return render(request, "create_player.html", {"form": form})  # Renderiza el formulario



def list_players(request):
    players_list = Player.objects.all()
    # Número de jugadores por página
    paginator = Paginator(players_list, 10)  # Puedes ajustar el número de jugadores por página

    # Obtén el número de página de la solicitud GET
    page = request.GET.get('page')

    try:
        players = paginator.page(page)
    except PageNotAnInteger:
        players = paginator.page(1)
    except EmptyPage:
        players = paginator.page(paginator.num_pages)

    return render(request, 'list_players.html', {'players': players})


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



def delete_player(request, player_id):
    player = get_object_or_404(Player, id=player_id)
    if request.method == "POST":
        player.delete()
        return redirect('list_players')
    
    return render(request, 'confirm_delete.html', {'player': player})
    

