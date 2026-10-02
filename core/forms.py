from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.password_validation import validate_password
from django.utils.translation import gettext, gettext_lazy as _

from team.models import Team
from .models import Membership

User = get_user_model()


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
        self.fields["password1"].help_text = _("Al menos 8 caracteres; no puede ser solo números ni parecerse a tu usuario.")
        self.fields["password2"].label = _("Repite la contraseña")
        self.fields["password2"].help_text = ""

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(gettext("Ya hay una cuenta con este email: inicia sesión con ella."))
        return email


class AddMemberForm(forms.Form):
    username = forms.CharField(label=_("Usuario"), max_length=150)
    password = forms.CharField(
        label=_("Contraseña"), required=False, widget=forms.PasswordInput,
        help_text=_("Solo si el usuario no existe todavía: se creará con esta contraseña."),
    )
    email = forms.EmailField(
        label=_("Email"), required=False,
        help_text=_("Los capitanes con email reciben el informe al cerrar cada convocatoria."),
    )
    role = forms.ChoiceField(label=_("Rol"), choices=Membership.ROLES, initial=Membership.MEMBER)

    def __init__(self, *args, club=None, **kwargs):
        self.club = club
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        username = cleaned.get("username")
        if not username:
            return cleaned

        user = User.objects.filter(username=username).first()
        if user is None:
            password = cleaned.get("password")
            if not password:
                raise forms.ValidationError(gettext("El usuario no existe: indica una contraseña para crearlo."))
            validate_password(password, User(username=username))
        elif Membership.objects.filter(user=user, club=self.club).exists():
            raise forms.ValidationError(gettext("Ese usuario ya es miembro del club."))

        cleaned["user"] = user
        return cleaned

    def save(self):
        user = self.cleaned_data["user"]
        email = self.cleaned_data.get("email", "")
        if user is None:
            user = User.objects.create_user(
                username=self.cleaned_data["username"],
                password=self.cleaned_data["password"],
                email=email,
            )
        elif email and not user.email:
            user.email = email
            user.save(update_fields=["email"])
        return Membership.objects.create(user=user, club=self.club, role=self.cleaned_data["role"])
