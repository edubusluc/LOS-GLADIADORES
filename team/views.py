from django.shortcuts import render, redirect, get_object_or_404
from .forms import Teamform
from .models import Team
from django.contrib import messages
from django.views.decorators.http import require_GET, require_http_methods
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage

# Create your views here.
@require_GET
def list_team(request):
    # Determina si el usuario está autenticado para filtrar el queryset
    teams = Team.objects.all() if request.user.is_authenticated else Team.objects.filter(in_group=True)
    paginator = Paginator(teams, 4)  # Número de equipos por página
    page = request.GET.get('page')

    try:
        teams = paginator.page(page)
    except PageNotAnInteger:
        teams = paginator.page(1)
    except EmptyPage:
        teams = paginator.page(paginator.num_pages)

    return render(request, "list_teams.html", {"teams": teams})

@login_required
@require_http_methods(["GET", "POST"])
def create_team(request):
    if request.method == "POST":
        form = Teamform(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect("list_teams")
        else:
            messages.error(request, "Error al crear el equipo. Por favor, verifica los datos.")

    else:
        form = Teamform()

    for field in form:
        field.field.widget.attrs.update({'class': 'form-control'})

    return render(request, "create_team.html", {"form": form})

@login_required
@require_http_methods(["GET", "POST"])
def edit_team(request, team_id):
    team = get_object_or_404(Team, id=team_id)

    if request.method == "POST":
        form = Teamform(request.POST, instance=team)
        if form.is_valid():
            form.save(commit=False)  # Guarda el equipo
            team.in_group = 'in_group' in request.POST
            team.save()           
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



