from django.shortcuts import render, redirect, get_object_or_404
from .forms import Teamform
from .models import Team
from django.contrib import messages
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_http_methods
from core.decorators import club_required, club_admin_required
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Q

# Create your views here.
@club_required
@require_GET
def list_team(request):
    search = request.GET.get('search', '').strip()

    # Los administradores ven también los equipos fuera de grupo
    teams = Team.objects.filter(club=request.club)
    teams = teams.order_by('-in_group', 'name') if request.membership.is_admin else teams.filter(in_group=True).order_by('name')

    if search:
        teams = teams.filter(
            Q(name__icontains=search) | Q(location__icontains=search)
        )

    paginator = Paginator(teams, 4)  # Número de equipos por página
    page = request.GET.get('page')

    try:
        teams = paginator.page(page)
    except PageNotAnInteger:
        teams = paginator.page(1)
    except EmptyPage:
        teams = paginator.page(paginator.num_pages)

    return render(request, "list_teams.html", {"teams": teams, "search": search})

@club_admin_required
@require_http_methods(["GET", "POST"])
def create_team(request):
    if request.method == "POST":
        form = Teamform(request.POST, request.FILES, club=request.club)
        if form.is_valid():
            team = form.save(commit=False)
            team.club = request.club
            team.save()
            return redirect("list_teams")
        else:
            messages.error(request, _("Error al crear el equipo. Por favor, verifica los datos."))

    else:
        form = Teamform(club=request.club)

    for field in form:
        field.field.widget.attrs.update({'class': 'form-control'})

    return render(request, "create_team.html", {"form": form})

@club_admin_required
@require_http_methods(["GET", "POST"])
def edit_team(request, team_id):
    team = get_object_or_404(Team, public_id=team_id, club=request.club)

    if request.method == "POST":
        form = Teamform(request.POST, request.FILES, instance=team, club=request.club)  # Agregar request.FILES aquí
        if form.is_valid():
            form.save(commit=False)  # Guarda el equipo
            team.in_group = 'in_group' in request.POST
            team.save()
            return redirect('list_teams')
        else:
            messages.error(request, _("Error al editar el equipo. Por favor, verifica los datos."))
    else:
        form = Teamform(instance=team, club=request.club)

    context = {
        'form': form,  
        'team': team,
    }
    return render(request, 'edit_team.html', context)



