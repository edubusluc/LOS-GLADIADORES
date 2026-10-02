from django.shortcuts import render, redirect, get_object_or_404
from .forms import Teamform
from .models import Team
from django.contrib import messages
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_http_methods
from core.decorators import club_required, club_admin_required
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Q
from django.http import JsonResponse
from core import similarity

# Create your views here.
@club_required
@require_GET
def list_team(request):
    search = request.GET.get('search', '').strip()

    # Los capitanes ven también los equipos fuera de grupo
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
    similar = []
    if request.method == "POST":
        form = Teamform(request.POST, request.FILES, club=request.club)
        if form.is_valid():
            # Equipos con un nombre igual o parecido: se pregunta antes de crearlo.
            similar = similarity.similar_teams(request.club, form.cleaned_data['name'])
            if similarity.is_check_request(request):
                return JsonResponse({"valid": True, "similar": [similar_team_label(t) for t in similar]})
            if not similar or similarity.confirmed(request):
                team = form.save(commit=False)
                team.club = request.club
                team.save()
                return redirect("list_teams")
        else:
            if similarity.is_check_request(request):
                return JsonResponse({"valid": False, "similar": []})
            messages.error(request, _("Error al crear el equipo. Por favor, verifica los datos."))

    else:
        form = Teamform(club=request.club)

    for field in form:
        field.field.widget.attrs.update({'class': 'form-select' if field.name in ('gender', 'country', 'division') else 'form-control'})

    return render(request, "create_team.html", {
        "form": form,
        "similar": [similar_team_label(t) for t in similar],
    })


def similar_team_label(team):
    """«Tomares (Masculino · España · 500)», o solo el nombre si no tiene categoría ni país."""
    details = " · ".join(str(d) for d in (team.get_gender_display(), team.get_country_display(),
                                          team.get_division_display()) if d)
    return f"{team.name} ({details})" if details else team.name

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
        'genders': Team.GENDERS,
        'countries': Team.COUNTRIES,
        'divisions': Team.DIVISIONS,
    }
    return render(request, 'edit_team.html', context)



