from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.password_validation import validate_password

from .models import Membership

User = get_user_model()


class ClubForm(forms.Form):
    name = forms.CharField(label="Nombre del club", max_length=100)
    location = forms.CharField(label="Localización", max_length=100)


class SignUpForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")


class AddMemberForm(forms.Form):
    username = forms.CharField(label="Usuario", max_length=150)
    password = forms.CharField(
        label="Contraseña", required=False, widget=forms.PasswordInput,
        help_text="Solo si el usuario no existe todavía: se creará con esta contraseña.",
    )
    email = forms.EmailField(
        label="Email", required=False,
        help_text="Los administradores con email reciben el informe al cerrar cada convocatoria.",
    )
    role = forms.ChoiceField(label="Rol", choices=Membership.ROLES, initial=Membership.MEMBER)

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
                raise forms.ValidationError("El usuario no existe: indica una contraseña para crearlo.")
            validate_password(password, User(username=username))
        elif Membership.objects.filter(user=user, club=self.club).exists():
            raise forms.ValidationError("Ese usuario ya es miembro del club.")

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
