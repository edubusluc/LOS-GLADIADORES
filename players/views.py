from django.shortcuts import render, redirect, get_object_or_404
from core.decorators import club_required, club_admin_required
from .forms import PlayerForm, SnpAccountForm
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.contrib import messages
from match.models import Game
from players.models import Player, SnpAccount
from players.scraper import team_id
from players.snp import sync_club
from core.crypto import DecryptionError
from django.views.decorators.http import require_POST
from django.db.models import Q


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


@club_admin_required
def snp_account(request):
    """Cuenta SNP del capitán: con ella se descargan cada día los puntos SNP de los jugadores."""
    account = SnpAccount.objects.filter(club=request.club).first()
    if request.method == "POST":
        form = SnpAccountForm(request.POST, has_password=account is not None)
        if form.is_valid():
            account = account or SnpAccount(club=request.club)
            account.username = form.cleaned_data["username"]
            if form.cleaned_data["password"]:
                account.password = form.cleaned_data["password"]
            account.team_url = form.cleaned_data["team_url"]
            account.updated_by = request.user
            account.save()
            messages.success(request, "Cuenta SNP guardada. Los puntos se actualizarán cada mañana.")
            return redirect("snp_account")
    else:
        initial = {}
        if account:
            initial["team_url"] = account.team_url
            try:
                initial["username"] = account.username
            except DecryptionError:
                messages.error(request, "No se ha podido leer la cuenta guardada (¿ha cambiado la clave de cifrado?). Vuelve a introducirla.")
        form = SnpAccountForm(initial=initial, has_password=account is not None)
    return render(request, "snp_account.html", {
        "form": form, "account": account, "team_id": team_id(account.team_url) if account else None,
    })


@club_admin_required
@require_POST
def snp_sync(request):
    account = get_object_or_404(SnpAccount, club=request.club)
    result = sync_club(account)
    (messages.success if result.ok else messages.error)(request, result.message)
    return redirect("snp_account")


@club_admin_required
@require_POST
def snp_account_delete(request):
    SnpAccount.objects.filter(club=request.club).delete()
    messages.success(request, "Cuenta SNP borrada.")
    return redirect("snp_account")
