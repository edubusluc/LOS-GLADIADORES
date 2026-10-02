import datetime

from django.forms import Select
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from data_analyse import pairs as pair_stats
from match.models import Match
from players.models import Player, SnpAccount, current_season

from .adapters import GOOGLE_NEW_ACCOUNT_KEY
from .decorators import club_admin_required
from .emails import send_invitation_email, send_welcome_email
from .forms import ClubForm, InviteMemberForm, SignUpForm
from .middleware import SESSION_KEY
from .models import Invitation, Membership
from .services import InvitationError, accept_invitation, create_club

# Invitación pendiente de aceptar mientras el visitante inicia sesión con Google
PENDING_INVITE_KEY = "pending_invitation"
# Parámetro con el que el botón de Google del alta de club vuelve a register_club
FROM_GOOGLE_PARAM = "google"
# Hay varios backends de autenticación (usuario/email y Google): al iniciar sesión
# justo después de registrarse hay que indicar cuál se usa.
LOGIN_BACKEND = "django.contrib.auth.backends.ModelBackend"

User = get_user_model()


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
        # Aviso al capitán mientras no haya registrado la cuenta SNP del club.
        'snp_missing': request.membership.is_admin and not SnpAccount.objects.filter(club=club).exists(),
    })

def error_404_view(request, exception):
    return render(request, '404.html', status=404)


def _site_url(request):
    return request.build_absolute_uri("/")


def _style(*forms):
    for form in filter(None, forms):
        for field in form:
            css = 'form-select' if isinstance(field.field.widget, Select) else 'form-control'
            field.field.widget.attrs.update({'class': css})


def register_club(request):
    """Alta de un club nuevo. Si el visitante no tiene cuenta, se le crea una."""
    anonymous = not request.user.is_authenticated

    # Vuelve de "Crear mi cuenta con Google". Si el email ya tenía cuenta, Google ha
    # iniciado sesión en ella: no es un alta nueva, así que va a su portada.
    if not anonymous and request.GET.get(FROM_GOOGLE_PARAM):
        if request.session.pop(GOOGLE_NEW_ACCOUNT_KEY, False):
            return redirect("register_club")
        messages.info(request, _("Ya tenías una cuenta con este email. Has iniciado sesión con ella."))
        return redirect("home")

    if request.method == "POST":
        club_form = ClubForm(request.POST)
        user_form = SignUpForm(request.POST) if anonymous else None
        if club_form.is_valid() and (user_form is None or user_form.is_valid()):
            with transaction.atomic():
                user = user_form.save() if anonymous else request.user
                data = club_form.cleaned_data
                club = create_club(data["name"], data["location"], user, gender=data["gender"], country=data["country"],
                                   division=data["division"])
            if anonymous:
                login(request, user, backend=LOGIN_BACKEND)
            request.session[SESSION_KEY] = club.id
            send_welcome_email(user, club, created=True, site_url=_site_url(request))
            messages.success(request, _("Club %(club)s creado correctamente.") % {"club": club.name})
            return redirect("home")
    else:
        club_form = ClubForm()
        user_form = SignUpForm() if anonymous else None

    _style(club_form, user_form)
    return render(request, "register_club.html", {
        "club_form": club_form, "user_form": user_form,
        "google_next": f"{reverse('register_club')}?{FROM_GOOGLE_PARAM}=1",
    })


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
def club_members(request, invite_form=None):
    club = request.club
    invite_form = invite_form or InviteMemberForm(club=club)
    _style(invite_form)
    memberships = club.memberships.select_related("user").order_by("user__username")
    invitations = club.invitations.filter(used_at__isnull=True, expires_at__gt=timezone.now())
    return render(request, "club_members.html", {
        "invite_form": invite_form, "memberships": memberships, "roles": Membership.ROLES, "invitations": invitations,
    })


@club_admin_required
@require_POST
def create_invitation(request):
    """
    El capitán invita a un jugador por email. Las cuentas las crea cada jugador
    desde el enlace; el capitán ya no puede crear usuarios. Volver a invitar al
    mismo email sustituye la invitación pendiente por una nueva.
    """
    club = request.club
    form = InviteMemberForm(request.POST, club=club)
    if not form.is_valid():
        return club_members(request, invite_form=form)

    email = form.cleaned_data["email"]
    club.invitations.filter(email__iexact=email, used_at__isnull=True).delete()
    invitation = Invitation.objects.create(club=club, created_by=request.user, email=email)
    url = request.build_absolute_uri(reverse("invitation", args=[invitation.token]))
    if send_invitation_email(invitation, url):
        messages.success(request, _("Invitación enviada a %(email)s. El enlace caduca en 24 horas.") % {"email": email})
    else:
        invitation.delete()
        messages.error(request, _("No se pudo enviar el correo a %(email)s. Inténtalo de nuevo más tarde.") % {"email": email})
    return redirect(reverse("club_members") + "#invitaciones")


@club_admin_required
@require_POST
def revoke_invitation(request, invitation_id):
    get_object_or_404(Invitation, public_id=invitation_id, club=request.club, used_at__isnull=True).delete()
    messages.success(request, _("Invitación anulada."))
    return redirect(reverse("club_members") + "#invitaciones")


@require_POST
def password_check(request):
    """
    Comprueba, mientras se escribe, las reglas de contraseña que solo conoce el
    servidor (parecido al usuario/email y contraseñas comunes) para la lista de
    requisitos de los formularios de registro. Solo responde sí/no por regla.
    """
    user = User(username=request.POST.get("username", ""), email=request.POST.get("email", ""))
    codes = set()
    try:
        validate_password(request.POST.get("password", ""), user)
    except ValidationError as exc:
        codes = {error.code for error in exc.error_list}
    return JsonResponse({
        "similar": "password_too_similar" not in codes,
        "common": "password_too_common" not in codes,
    })


def _join(request, invitation, user):
    """Acepta la invitación para ``user``; devuelve True si ha entrado en el club."""
    try:
        membership = accept_invitation(invitation, user)
    except InvitationError as exc:
        messages.error(request, str(exc))
        return False
    request.session[SESSION_KEY] = membership.club_id
    send_welcome_email(user, membership.club, site_url=_site_url(request))
    messages.success(request, _("¡Bienvenido a %(club)s!") % {"club": membership.club.name})
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
            messages.info(request, _("Ya eres miembro de %(club)s.") % {"club": club.name})
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
            messages.success(request, _("¡Bienvenido a %(club)s!") % {"club": club.name})
            return redirect("home")
    else:
        form = SignUpForm(initial={"email": invitation.email})

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
        messages.error(request, _("'%(email)s' no es un email válido.") % {"email": email})
        return redirect("club_members")
    if email != membership.user.email:
        membership.user.email = email
        membership.user.save(update_fields=["email"])
    if role not in dict(Membership.ROLES):
        messages.error(request, _("Rol no válido."))
    elif role != Membership.ADMIN and _is_last_admin(membership):
        messages.error(request, _("El club debe tener al menos un capitán."))
    else:
        membership.role = role
        membership.save()
    return redirect("club_members")


@club_admin_required
@require_POST
def remove_member(request, membership_id):
    membership = get_object_or_404(Membership, public_id=membership_id, club=request.club)
    if _is_last_admin(membership):
        messages.error(request, _("El club debe tener al menos un capitán."))
    else:
        membership.delete()
    return redirect("club_members")
