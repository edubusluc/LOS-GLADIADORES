from django import forms
from .models import Player

class PlayerForm (forms.ModelForm):
    class Meta:
        model = Player
        fields = ['name', 'last_name', 'position', 'skillfull_hand', 'photo']

class SnpAccountForm(forms.Form):
    username = forms.CharField(label="Usuario de SNP", max_length=150)
    password = forms.CharField(
        label="Contraseña de SNP", required=False, widget=forms.PasswordInput(render_value=False),
        help_text="Se guarda cifrada. Déjala vacía para mantener la actual.",
    )
    team = forms.CharField(
        label="Equipo en SNP (opcional)", max_length=1000, required=False,
        help_text="Solo si la cuenta tiene varios equipos: el número del equipo (p. ej. 4380) o la dirección de su página en SNP.",
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
            raise forms.ValidationError("Escribe la contraseña de SNP.")
        return password

    def clean_team(self):
        from .scraper import parse_team_id
        value = self.cleaned_data["team"].strip()
        if not value:
            return ""
        number = parse_team_id(value)
        if not number:
            raise forms.ValidationError("Escribe el número del equipo (p. ej. 4380) o la dirección de su página en SNP.")
        return number
