from django import forms
from django.utils.translation import gettext_lazy as _
from core.images import clean_photo_field
from .models import Player

def with_placeholder(choices):
    """Las opciones con «NONE» (sin indicar) al principio y rotulada «Elige una opción»."""
    return [("NONE", _("Elige una opción"))] + [c for c in choices if c[0] != "NONE"]


class PlayerForm (forms.ModelForm):
    class Meta:
        model = Player
        fields = ['name', 'last_name', 'position', 'skillfull_hand', 'photo']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['position'].choices = with_placeholder(Player.POSITIONS)
        self.fields['skillfull_hand'].choices = with_placeholder(Player.HAND)

    def clean_photo(self):
        # Se valida, reduce y pasa a WebP antes de guardarla (core/images.py).
        return clean_photo_field(self)

class SnpAccountForm(forms.Form):
    username = forms.CharField(label=_("Usuario de SNP"), max_length=150)
    password = forms.CharField(
        label=_("Contraseña de SNP"), required=False, widget=forms.PasswordInput(render_value=False),
        help_text=_("Se guarda cifrada. Déjala vacía para mantener la actual."),
    )
    team = forms.CharField(
        label=_("Equipo en SNP (opcional)"), max_length=1000, required=False,
        help_text=_("Solo si la cuenta tiene varios equipos: el número del equipo (p. ej. 4380) o la dirección de su página en SNP."),
    )

    def __init__(self, *args, has_password=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.has_password = has_password
        for f in self.fields.values():
            f.widget.attrs["class"] = "form-control"
        self.fields["username"].widget.attrs["autocomplete"] = "off"
        self.fields["password"].widget.attrs["autocomplete"] = "new-password"

    def clean_password(self):
        password = self.cleaned_data["password"]
        if not password and not self.has_password:
            raise forms.ValidationError(_("Escribe la contraseña de SNP."))
        return password

    def clean_team(self):
        from .scraper import parse_team_id
        value = self.cleaned_data["team"].strip()
        if not value:
            return ""
        number = parse_team_id(value)
        if not number:
            raise forms.ValidationError(_("Escribe el número del equipo (p. ej. 4380) o la dirección de su página en SNP."))
        return number
