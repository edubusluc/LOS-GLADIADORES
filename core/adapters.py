from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        # Las cuentas con contraseña se crean desde una invitación, al registrar un
        # club o las crea un administrador: el alta genérica de allauth queda cerrada.
        return False

    def add_message(self, *args, **kwargs):
        # Sin avisos de allauth ("Has iniciado sesión como..."): la app ya muestra los suyos.
        pass


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def is_open_for_signup(self, request, sociallogin):
        # Cualquiera puede crear su cuenta con Google; para ver datos de un club
        # tiene que unirse con una invitación o registrar el suyo.
        return True
