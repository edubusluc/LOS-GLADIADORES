from django.shortcuts import render, redirect, get_object_or_404
from .forms import Teamform
from .models import Team
from django.contrib import messages
from django.views.decorators.http import require_GET, require_http_methods
from django.contrib.auth.decorators import login_required

# Create your views here.
@require_GET
def list_team(request):
    teams = Team.objects.all()
    return render(request, "list_teams.html", {"teams": teams}) 


@require_http_methods(["GET", "POST"])
def create_team(request):
    if request.method == "POST":
        form = Teamform(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Equipo creado con éxito.")
            return redirect("list_teams")
        else:
            messages.error(request, "Error al crear el equipo. Por favor, verifica los datos.")

    else:
        form = Teamform()

    return render(request, "create_team.html", {"form": form})

@require_http_methods(["GET", "POST"])
def edit_team(request, team_id):
    team = get_object_or_404(Team, id=team_id)

    if request.method == "POST":
        form = Teamform(request.POST, instance=team)
        if form.is_valid():
            form.save()  # Guarda el equipo
            messages.success(request, "Equipo editado con éxito.")
            return redirect('list_teams')
        else:
            messages.error(request, "Error al editar el equipo. Por favor, verifica los datos.")

    else:
        form = Teamform(instance=team)  

    context = {
        'form': form,  
        'team': team,
    }
    return render(request, 'edit_team.html', context)  



