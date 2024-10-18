from django.shortcuts import render, redirect, get_object_or_404
from .forms import Teamform
from .models import Team
from django.contrib import messages

# Create your views here.

def list_team(request):
    teams = Team.objects.all()
    return render(request, "list_teams.html", {"teams": teams}) 

def create_team(request):
    if request.method == "POST":
        form = Teamform(request.POST)
        if form.is_valid():
            form.save()
            return redirect("list_teams") 
        else:
            if 'name' in form.errors:
                del form.errors['name']
            messages.error(request, "El nombre del equipo no puede repetirse")
    else:
        form = Teamform() 

    return render(request, "create_team.html", {"form": form})  # Renderiza el formulario


def edit_team(request, team_id):
    team = get_object_or_404(Team, id=team_id)
    if request.method == "POST":
        name = request.POST.get("name")
        in_group = request.POST.get("in_group") == "on"
        team.name = name
        team.in_group = in_group
        team.save()

        return redirect('list_teams')  # Redirigir a la lista de jugadores después de guardar

    context = {
        'team': team  # Asegúrate de pasar el objeto player a la plantilla
    }
    return render(request, 'edit_team.html', context)  # Renderizar con el contexto correcto


