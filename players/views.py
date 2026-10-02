from django.shortcuts import render, redirect, get_object_or_404
from core.decorators import club_required, club_admin_required
from .forms import PlayerForm, SnpAccountForm, with_placeholder
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.contrib import messages
from match.models import Game
from players.models import Player, SnpAccount, SnpTeamImport
from core.crypto import DecryptionError
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Q
from django.utils.translation import gettext as _, ngettext
from . import snp_import
from core import similarity


# Create your views here.


@club_admin_required
def create_player(request):
    similar = []
    if request.method == "POST":
        form = PlayerForm(request.POST, request.FILES)
        if form.is_valid():
            # Jugadores con nombre y apellidos iguales o parecidos: se pregunta antes de crearlo.
            similar = similarity.similar_players(request.club, form.cleaned_data['name'], form.cleaned_data['last_name'])
            if similarity.is_check_request(request):
                return JsonResponse({"valid": True, "similar": [str(p) for p in similar]})
            if not similar or similarity.confirmed(request):
                player = form.save(commit=False)
                player.club = request.club
                player.team = request.club.own_team  # save() le copia la categoría del equipo
                player.save()
                return redirect("list_players")
        else:
            if similarity.is_check_request(request):
                return JsonResponse({"valid": False, "similar": []})
            messages.error(request, _("Error al crear el jugador. Por favor, verifica los datos."))
    else:
        form = PlayerForm()

    # Agregar clases a cada campo
    for field in form:
        field.field.widget.attrs.update({'class': 'form-control'})

    return render(request, "create_player.html", {
        "form": form,
        "similar": [str(p) for p in similar],
        "own_team": request.club.own_team,
    })


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

    context = {
        'players': players,
        'order_by': order_by,
        'search': search,
    }
    if request.membership.is_admin:
        context.update(_complete_team_context(request.club))
    return render(request, 'list_players.html', context)


def _complete_team_context(club):
    """Estado del botón «Completar equipo» (solo con cuenta SNP; una vez al mes)."""
    if not SnpAccount.objects.filter(club=club).exists():
        return {}
    last = snp_import.last_import_this_month(club)
    return {
        'snp_import_enabled': True,
        'snp_import': snp_import.active_import(club),
        'snp_import_last': last,
        'snp_import_next': snp_import.next_month_start() if last else None,
    }

@club_admin_required
def edit_player(request, player_id):
    player = get_object_or_404(Player, public_id=player_id, club=request.club)  # Asegúrate de que estás usando el modelo correcto

    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        last_name = (request.POST.get("last_name") or "").strip()
        position = request.POST.get("position")
        skillfull_hand = request.POST.get("skillfull_hand")
        joined_season = request.POST.get("joined_season")
        in_team = 'in_team' in request.POST

        if name:
            player.name = name
        if last_name:
            player.last_name = last_name
        player.position = position
        player.skillfull_hand = skillfull_hand
        player.in_team = in_team
        player.joined_season = joined_season
        player.save()

        return redirect('list_players')  # Redirigir a la lista de jugadores después de guardar

    context = {
        'player': player,
        'positions': with_placeholder(Player.POSITIONS),
        'hands': with_placeholder(Player.HAND),
    }
    return render(request, 'edit_player.html', context)  # Renderizar con el contexto correcto


@club_required
def show_player(request, player_id):
    player = get_object_or_404(Player, public_id=player_id, club=request.club)
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
            joined_text = ngettext("%(n)s alta", "%(n)s altas", joined) % {"n": joined}
            left_text = ngettext("%(n)s baja", "%(n)s bajas", left) % {"n": left}
            messages.success(request, _("Plantilla actualizada: %(joined)s y %(left)s.") % {"joined": joined_text, "left": left_text})
        else:
            messages.info(request, _("No había cambios que guardar."))
        return redirect('manage_roster')

    return render(request, 'manage_roster.html', {
        'players': players,
        'in_team_count': sum(p.in_team for p in players),
    })


@club_admin_required
def snp_account(request):
    """Cuenta SNP del capitán: con ella se descargan cada semana los puntos SNP de los jugadores."""
    account = SnpAccount.objects.filter(club=request.club).first()
    if request.method == "POST":
        form = SnpAccountForm(request.POST, has_password=account is not None)
        if form.is_valid():
            account = account or SnpAccount(club=request.club)
            account.username = form.cleaned_data["username"]
            if form.cleaned_data["password"]:
                account.password = form.cleaned_data["password"]
            account.team_id = form.cleaned_data["team"]
            account.updated_by = request.user
            account.save()
            messages.success(request, _("Cuenta SNP guardada. Los puntos se actualizarán cada lunes por la noche."))
            return redirect("snp_account")
    else:
        initial = {}
        if account:
            initial["team"] = account.team_id
            try:
                initial["username"] = account.username
            except DecryptionError:
                messages.error(request, _("No se ha podido leer la cuenta guardada (¿ha cambiado la clave de cifrado?). Vuelve a introducirla."))
        form = SnpAccountForm(initial=initial, has_password=account is not None)
    return render(request, "snp_account.html", {
        "form": form, "account": account,
    })


@club_admin_required
@require_POST
def snp_account_delete(request):
    SnpAccount.objects.filter(club=request.club).delete()
    messages.success(request, _("Cuenta SNP borrada."))
    return redirect("snp_account")


# ---------- «Completar equipo» con los jugadores de SNP ----------

def _blocked_this_month(request):
    last = snp_import.last_import_this_month(request.club)
    if last:
        messages.error(request, _("El equipo ya se ha completado este mes. Podrás volver a hacerlo a partir del %(date)s.")
                       % {"date": f"{snp_import.next_month_start():%d/%m/%Y}"})
    return last is not None


@club_admin_required
@require_POST
def complete_team_start(request):
    if not SnpAccount.objects.filter(club=request.club).exists():
        messages.error(request, _("Primero registra la cuenta SNP del capitán."))
        return redirect("snp_account")
    if not _blocked_this_month(request) and not snp_import.active_import(request.club):
        snp_import.start_search(request.club, request.user)
    return redirect("list_players")


@club_admin_required
def complete_team_status(request, import_id):
    team_import = get_object_or_404(SnpTeamImport, public_id=import_id, club=request.club)
    return JsonResponse({"status": team_import.status, "message": team_import.message})


@club_admin_required
@require_POST
def complete_team_confirm(request, import_id):
    team_import = get_object_or_404(SnpTeamImport, public_id=import_id, club=request.club, source=SnpTeamImport.WEB)
    if team_import.status != SnpTeamImport.READY or not team_import.to_add or _blocked_this_month(request):
        return redirect("list_players")
    team_import = snp_import.confirm(team_import)
    messages.success(request, _("Equipo completado: %(message)s") % {"message": team_import.message})
    return redirect("list_players")


@club_admin_required
@require_POST
def complete_team_cancel(request, import_id):
    SnpTeamImport.objects.filter(
        public_id=import_id, club=request.club, status__in=[SnpTeamImport.RUNNING, SnpTeamImport.READY],
    ).update(status=SnpTeamImport.CANCELLED)
    return redirect("list_players")
