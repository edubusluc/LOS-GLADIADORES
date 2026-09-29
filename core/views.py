from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from .decorators import club_admin_required
from .forms import ClubForm, SignUpForm, AddMemberForm
from .middleware import SESSION_KEY
from .models import Membership
from .services import create_club

# Create your views here.


def home(request):
    return render(request, 'home.html')

def error_404_view(request, exception):
    return render(request, '404.html', status=404)


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
                login(request, user)
            request.session[SESSION_KEY] = club.id
            messages.success(request, f"Club {club.name} creado correctamente.")
            return redirect("home")
    else:
        club_form = ClubForm()
        user_form = SignUpForm() if anonymous else None

    for form in filter(None, (club_form, user_form)):
        for field in form:
            field.field.widget.attrs.update({'class': 'form-control'})

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
            messages.success(request, f"{membership.user.username} añadido al club.")
            return redirect("club_members")
    else:
        form = AddMemberForm(club=club)

    for field in form:
        field.field.widget.attrs.update({'class': 'form-control'})

    memberships = club.memberships.select_related("user").order_by("user__username")
    return render(request, "club_members.html", {"form": form, "memberships": memberships, "roles": Membership.ROLES})


def _is_last_admin(membership):
    return membership.is_admin and not membership.club.memberships.filter(role=Membership.ADMIN).exclude(pk=membership.pk).exists()


@club_admin_required
@require_POST
def update_member(request, membership_id):
    membership = get_object_or_404(Membership, id=membership_id, club=request.club)
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
    membership = get_object_or_404(Membership, id=membership_id, club=request.club)
    if _is_last_admin(membership):
        messages.error(request, "El club debe tener al menos un administrador.")
    else:
        membership.delete()
    return redirect("club_members")
