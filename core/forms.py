from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.password_validation import MinimumLengthValidator, get_default_password_validators
from django.template.loader import render_to_string
from django.utils.translation import gettext, gettext_lazy as _

from team.models import Team
from .models import Membership

User = get_user_model()


def password_min_length():
    """Longitud mínima de MinimumLengthValidator en AUTH_PASSWORD_VALIDATORS (8 si no está)."""
    for validator in get_default_password_validators():
        if isinstance(validator, MinimumLengthValidator):
            return validator.min_length
    return 8


class ClubForm(forms.Form):
    name = forms.CharField(label=_("Nombre del club"), max_length=100)
    location = forms.CharField(label=_("Localización"), max_length=100)
    gender = forms.ChoiceField(label=_("Categoría"), choices=[("", _("Elige una opción"))] + Team.GENDERS,
                               help_text=_("Los jugadores del club tendrán esta categoría."))
    country = forms.ChoiceField(label=_("Nacionalidad del equipo"), choices=[("", _("Elige una opción"))] + Team.COUNTRIES)
    division = forms.ChoiceField(label=_("División"), choices=[("", _("Elige una opción"))] + Team.DIVISIONS)


class SignUpForm(UserCreationForm):
    email = forms.EmailField(
        label=_("Email"), help_text=_("Te enviaremos la confirmación del registro. También puedes usarlo para iniciar sesión."),
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = _("Usuario")
        self.fields["username"].help_text = _("Letras, números y @ . + - _ (máximo 150).")
        self.fields["password1"].label = _("Contraseña")
        # Lista de requisitos que static/js/password.js va marcando mientras se escribe.
        self.fields["password1"].help_text = render_to_string("includes/password_rules.html", {
            "min_length": password_min_length(),
        })
        self.fields["password1"].widget.attrs["data-password-rules"] = "password-rules"
        self.fields["password2"].label = _("Repite la contraseña")
        self.fields["password2"].help_text = ""

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(gettext("Ya hay una cuenta con este email: inicia sesión con ella."))
        return email


class InviteMemberForm(forms.Form):
    """El capitán invita por email: la cuenta la crea el propio jugador desde el enlace."""
    email = forms.EmailField(
        label=_("Email del jugador"),
        help_text=_("Le enviaremos un enlace para registrarse (o unirse con su cuenta) como miembro. Caduca en 24 horas."),
    )

    def __init__(self, *args, club=None, **kwargs):
        self.club = club
        super().__init__(*args, **kwargs)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if Membership.objects.filter(club=self.club, user__email__iexact=email).exists():
            raise forms.ValidationError(gettext("Ese email ya pertenece a un miembro del club."))
        return email
