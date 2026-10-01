import datetime

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from data_analyse import pairs as pair_stats
from match.models import Match
from players.models import Player, SnpAccount, current_season

from .decorators import club_admin_required
from .emails import send_welcome_email
from .forms import ClubForm, SignUpForm, AddMemberForm
from .middleware import SESSION_KEY
from .models import Invitation, Membership
from .services import InvitationError, accept_invitation, create_club

# Invitación pendiente de aceptar mientras el visitante inicia sesión con Google
PENDING_INVITE_KEY = "pending_invitation"
# Hay varios backends de autenticación (usuario/email y Google): al iniciar sesión
# justo después de registrarse hay que indicar cuál se usa.
LOGIN_BACKEND = "django.contrib.auth.backends.ModelBackend"

# Create your views here.


def home(request):
    """Portada del club: logo, próximo partido y jugador/pareja en racha."""
    if not request.user.is_authenticated:
        return render(request, 'landing.html')
    if request.club is None:
        return redirect('no_club')

    club = request.club
    today = datetime.date.today()
    next_match = (
        Match.objects.filter(club=club, start_date__gte=today)
        .select_related('local', 'visiting')
        .order_by('start_date', 'id')
        .first()
    )
    players = Player.objects.filter(club=club, in_team=True)
    hot_player, hot_pair = pair_stats.hot_streaks(pair_stats.club_game_log(club), players)

    return render(request, 'home.html', {
        'own_team': club.own_team,
        'season': current_season(),
        'next_match': next_match,
        'days_left': (next_match.start_date - today).days if next_match else None,
        'hot_player': hot_player,
        'hot_pair': hot_pair,
        # Aviso al administrador (capitán) mientras no haya registrado la cuenta SNP del club.
        'snp_missing': request.membership.is_admin and not SnpAccount.objects.filter(club=club).exists(),
    })

def error_404_view(request, exception):
    return render(request, '404.html', status=404)


def _site_url(request):
    return request.build_absolute_uri("/")


def _style(*forms):
    for form in filter(None, forms):
        for field in form:
            field.field.widget.attrs.update({'class': 'form-control'})


def register_club(request):
    """Alta de un club nuevo. Si el visitante no tiene cuenta, se le crea una."""
    anonymous = not request.user.is_authenticated

    if request.method == "POST":
        club_form = ClubForm(request.POST)
        user_form = SignUpForm(request.POST) if anonymous else None
        if club_form.is_valid() and (user_form is None or user_form.is_valid()):
            with transaction.atomic():
                user = user_form.save() if anonymous else request.user
                club = create_club(club_form.cleaned_data["name"], club_form.cleaned_data["location"], user)
            if anonymous:
                login(request, user, backend=LOGIN_BACKEND)
            request.session[SESSION_KEY] = club.id
            send_welcome_email(user, club, created=True, site_url=_site_url(request))
            messages.success(request, f"Club {club.name} creado correctamente.")
            return redirect("home")
    else:
        club_form = ClubForm()
        user_form = SignUpForm() if anonymous else None

    _style(club_form, user_form)
    return render(request, "register_club.html", {"club_form": club_form, "user_form": user_form})


@login_required
def no_club(request):
    if request.club is not None:
        return redirect("home")
    return render(request, "no_club.html")


@login_required
@require_POST
def switch_club(request):
    membership = get_object_or_404(Membership, user=request.user, club_id=request.POST.get("club_id"))
    request.session[SESSION_KEY] = membership.club_id
    return redirect("home")


@club_admin_required
def club_members(request):
    club = request.club

    if request.method == "POST":
        form = AddMemberForm(request.POST, club=club)
        if form.is_valid():
            membership = form.save()
            send_welcome_email(membership.user, club, site_url=_site_url(request))
            messages.success(request, f"{membership.user.username} añadido al club.")
            return redirect("club_members")
    else:
        form = AddMemberForm(club=club)

    _style(form)
    memberships = club.memberships.select_related("user").order_by("user__username")
    invitations = [
        (inv, request.build_absolute_uri(reverse("invitation", args=[inv.token])))
        for inv in club.invitations.filter(used_at__isnull=True, expires_at__gt=timezone.now())
    ]
    return render(request, "club_members.html", {
        "form": form, "memberships": memberships, "roles": Membership.ROLES, "invitations": invitations,
    })


@club_admin_required
@require_POST
def create_invitation(request):
    Invitation.objects.create(club=request.club, created_by=request.user)
    messages.success(request, "Invitación creada: copia el enlace y compártelo. Caduca en 24 horas y sirve para una sola persona.")
    return redirect(reverse("club_members") + "#invitaciones")


@club_admin_required
@require_POST
def revoke_invitation(request, invitation_id):
    get_object_or_404(Invitation, public_id=invitation_id, club=request.club, used_at__isnull=True).delete()
    messages.success(request, "Invitación anulada.")
    return redirect(reverse("club_members") + "#invitaciones")


def _join(request, invitation, user):
    """Acepta la invitación para ``user``; devuelve True si ha entrado en el club."""
    try:
        membership = accept_invitation(invitation, user)
    except InvitationError as exc:
        messages.error(request, str(exc))
        return False
    request.session[SESSION_KEY] = membership.club_id
    send_welcome_email(user, membership.club, site_url=_site_url(request))
    messages.success(request, f"¡Bienvenido a {membership.club.name}!")
    return True


def invitation(request, token):
    """
    Enlace de invitación. Un visitante sin cuenta se registra con usuario, email y
    contraseña (o con Google); quien ya tiene sesión iniciada se une con un clic.
    """
    invitation = Invitation.objects.select_related("club").filter(token=token).first()
    if invitation is None or not invitation.is_valid:
        request.session.pop(PENDING_INVITE_KEY, None)
        return render(request, "invitation_invalid.html", {"invitation": invitation}, status=410)
    club = invitation.club

    if request.user.is_authenticated:
        if Membership.objects.filter(user=request.user, club=club).exists():
            request.session.pop(PENDING_INVITE_KEY, None)
            request.session[SESSION_KEY] = club.id
            messages.info(request, f"Ya eres miembro de {club.name}.")
            return redirect("home")
        # Vuelve de iniciar sesión con Google desde esta misma invitación: se une directamente.
        from_google = request.session.pop(PENDING_INVITE_KEY, None) == token
        if request.method == "POST" or from_google:
            _join(request, invitation, request.user)
            return redirect("home")
        return render(request, "invitation.html", {"invitation": invitation, "club": club})

    request.session[PENDING_INVITE_KEY] = token
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                user = form.save()
                try:
                    accept_invitation(invitation, user)
                except InvitationError as exc:
                    transaction.set_rollback(True)
                    messages.error(request, str(exc))
                    return redirect("invitation", token=token)
            request.session.pop(PENDING_INVITE_KEY, None)
            login(request, user, backend=LOGIN_BACKEND)
            request.session[SESSION_KEY] = club.id
            send_welcome_email(user, club, site_url=_site_url(request))
            messages.success(request, f"¡Bienvenido a {club.name}!")
            return redirect("home")
    else:
        form = SignUpForm()

    _style(form)
    return render(request, "invitation.html", {"invitation": invitation, "club": club, "form": form})


def _is_last_admin(membership):
    return membership.is_admin and not membership.club.memberships.filter(role=Membership.ADMIN).exclude(pk=membership.pk).exists()


@club_admin_required
@require_POST
def update_member(request, membership_id):
    membership = get_object_or_404(Membership, public_id=membership_id, club=request.club)
    role = request.POST.get("role")
    email = request.POST.get("email", "").strip()
    try:
        validate_email(email) if email else None
    except ValidationError:
        messages.error(request, f"'{email}' no es un email válido.")
        return redirect("club_members")
    if email != membership.user.email:
        membership.user.email = email
        membership.user.save(update_fields=["email"])
    if role not in dict(Membership.ROLES):
        messages.error(request, "Rol no válido.")
    elif role != Membership.ADMIN and _is_last_admin(membership):
        messages.error(request, "El club debe tener al menos un administrador.")
    else:
        membership.role = role
        membership.save()
    return redirect("club_members")


@club_admin_required
@require_POST
def remove_member(request, membership_id):
    membership = get_object_or_404(Membership, public_id=membership_id, club=request.club)
    if _is_last_admin(membership):
        messages.error(request, "El club debe tener al menos un administrador.")
    else:
        membership.delete()
    return redirect("club_members")
