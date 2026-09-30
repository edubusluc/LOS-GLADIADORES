# Zyra

Aplicación web para gestionar equipos de pádel: jugadores, convocatorias,
partidos y estadísticas. Diseño oscuro con acento lima, responsive (barra de
navegación inferior en móvil).

El paquete de configuración de Django se llama `zyra` (antes `snp_gladiadores`):

- Ajustes: `zyra.settings`
- WSGI: `zyra.wsgi.application`

Si despliegas en PythonAnywhere, actualiza el fichero WSGI del panel para usar
`DJANGO_SETTINGS_MODULE = "zyra.settings"`.

Los recursos de marca (logo, favicon, icono para móvil) están en `static/zyra/`.


## Multi-club

La aplicación gestiona varios clubes. Cada club (`core.Club`) tiene sus propios jugadores,
equipos rivales, partidos, convocatorias y estadísticas, y sus usuarios
(`core.Membership`) solo pueden ver los datos de los clubes a los que pertenecen.

- **Administrador**: gestiona jugadores, equipos, partidos, convocatorias y miembros.
- **Miembro**: solo consulta.

Un club nuevo se registra desde `/core/register_club/`. Desde *Miembros del club*
(`/core/members/`) los administradores pueden:

- **Generar una invitación**: un enlace de un solo uso, válido 24 horas, para que un
  jugador se registre (usuario, email y contraseña, o con Google) y entre como miembro.
  Si ya tiene cuenta, inicia sesión y se une con un clic.
- **Añadir miembro** directamente, creando la cuenta o eligiendo una existente y su rol.

Se puede iniciar sesión con el usuario o con el email. Al registrarse (con invitación o
creando un club) se envía un correo de bienvenida con el usuario, el equipo y sus
administradores. Si un usuario pertenece a varios clubes, elige el
activo con el selector de la barra superior.

### Actualizar una base de datos existente

```bash
python manage.py makemigrations core team players match
python manage.py migrate
# Crea el club "LOS GLADIADORES", le asigna todos los datos existentes
# y da de alta a los usuarios actuales como administradores.
python manage.py assign_default_club --name "LOS GLADIADORES"
```

### Partidos duplicados y restricciones de integridad

Desde esta versión la base de datos impide que un enfrentamiento tenga dos
partidos con el mismo número o que un partido tenga dos resultados. Si tu base
de datos ya tiene duplicados, límpialos **antes** de migrar:

```bash
python manage.py fix_duplicate_games --dry-run   # muestra qué se borraría
python manage.py fix_duplicate_games             # conserva el que tiene resultado o el más reciente
python manage.py makemigrations match
python manage.py migrate
```

### Portada y ubicación de los partidos

La portada muestra el escudo del equipo propio, el próximo partido (con enlace a
Google Maps) y el jugador y la pareja con la racha de victorias activa más larga.
El módulo de publicaciones ya no existe.

Cada partido guarda una **copia** de la ubicación del equipo local al crearse
(`Match.location`): si el equipo cambia de sede, los partidos ya creados no cambian.
Para rellenar los partidos que ya existían:

```bash
python manage.py makemigrations match
python manage.py migrate
python manage.py fill_match_locations
```

Las tablas antiguas de publicaciones (`post_post`, `post_image`) quedan en la base
de datos sin uso; se pueden borrar a mano si se quiere.

## Informe automático al cerrar una convocatoria

Al cerrar una convocatoria se genera un PDF (2 páginas, estilo Zyra) y se envía
por email a los **administradores del club que tengan email** (se configura en
*Miembros*). Incluye el rendimiento de convocados y parejas como local o
visitante según el partido, jugadores en racha, precedentes contra el rival y
dos alineaciones recomendadas según el formato de la SNP. También se puede
descargar desde el detalle del partido (botón *Informe PDF*).

Los informes se envían desde **join.zyra@gmail.com** (Gmail ya viene
configurado). Solo falta la contraseña de aplicación de esa cuenta, que nunca
se guarda en el código: defínela como variable de entorno (o en `.env`):

```
EMAIL_HOST_PASSWORD=contraseña_de_aplicación_de_16_letras
```

La contraseña de aplicación se crea en la cuenta de Google de join.zyra@gmail.com:
Seguridad → Verificación en dos pasos → Contraseñas de aplicaciones.

Sin `EMAIL_HOST_PASSWORD` los correos se muestran en la consola (útil en desarrollo).
Si el envío falla, la convocatoria se cierra igualmente y se avisa en pantalla.

## Inicio de sesión con Google

Se usa [django-allauth](https://docs.allauth.org/). El botón de Google solo aparece
si están definidas las variables de entorno `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET`
(o en `.env`); nunca van en el código.

1. En [Google Cloud Console](https://console.cloud.google.com/) abre *Google Auth Platform*:
   - *Información de la marca*: nombre Zyra y correo de asistencia join.zyra@gmail.com.
   - *Público*: tipo *Externo* y **Publicar app** para que pueda entrar cualquier cuenta de Google.
   - *Acceso a los datos*: permisos `openid`, `userinfo.email` y `userinfo.profile`.
2. En *Clientes → Crear cliente*, tipo *Aplicación web*:
   - Origen autorizado: `http://127.0.0.1:8000`
   - URI de redirección autorizado: `http://127.0.0.1:8000/accounts/google/login/callback/`
   - Al desplegar, añade también el origen `https://<tu-dominio>` y el URI
     `https://<tu-dominio>/accounts/google/login/callback/`.
3. Copia el ID y el secreto al `.env` (junto a `manage.py`) y reinicia el servidor.

Si alguien entra con Google y ya existe una cuenta con ese email, entra en esa cuenta.

### Desplegar esta versión

```bash
pip install -r requirements.txt   # instala django-allauth
python manage.py makemigrations core
python manage.py migrate          # crea core_invitation y las tablas de allauth
```

## Correos

Todos los correos salen de join.zyra@gmail.com con el mismo pie corporativo (logo de
Zyra y contacto), montado en `core/emails.py` y `core/templates/emails/layout.html`.
El logo va incrustado en el propio correo (`static/zyra/email-logo.png`).

## Back-office

Panel para el dueño de la plataforma en `/backoffice/`: dashboard con KPIs de todos los
clubes, listado y ficha de clubes y de usuarios. Solo entra el personal de Zyra
(usuarios con `is_staff`); al resto se le responde 404. Los usuarios staff ven el
enlace *Back-office* en el menú de usuario. El plan completo está en
`/mnt/project-files/crm/plan-crm.md` (consola SQL, importación, procesos programados…).

Para darte acceso a ti mismo:

```bash
python manage.py createsuperuser        # si aún no tienes superusuario
# o, con un usuario que ya existe:
python manage.py shell -c "from django.contrib.auth.models import User; User.objects.filter(username='TU_USUARIO').update(is_staff=True)"
```

El Django admin queda como herramienta de emergencia **solo para superusuarios**. Su
ruta es `/admin/` por defecto; en producción conviene cambiarla por una menos obvia
con la variable de entorno `ADMIN_URL` (por ejemplo `ADMIN_URL=gestion-9f3k/`, con la
barra final).

Esta versión no cambia modelos: no hace falta `makemigrations` ni `migrate`.
