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

## Puntos SNP automáticos

Cada administrador guarda en *Menú → Cuenta SNP* el usuario y la contraseña de SNP
(snpgalaxy.com) de su capitán y, solo si la cuenta tiene varios equipos, el número del
equipo. Usuario y contraseña se guardan cifrados (`core/crypto.py`). El proceso
programado `update_snp_scores` (lunes a las 23:00) recorre los clubes uno a uno, entra
en SNP con su cuenta, navega Series Nacionales → España → Mis equipos → el equipo, lee
los puntos de los jugadores (`players/scraper.py`) y actualiza los «Puntos SNP». Los
nombres se cruzan sin tener en cuenta mayúsculas, tildes, la categoría final (500,
Future) ni el segundo apellido si falta en un lado; lo que no encaja se muestra en la
página de la cuenta SNP. Solo el staff puede lanzarlo a mano, desde el back-office
(*Ejecutar ahora*) o con `python manage.py update_snp_scores [--club <slug>]`.

Define una clave de cifrado propia en `.env` (si falta se deriva de
`DJANGO_SECRET_KEY`, y cambiar esa clave dejaría ilegibles las cuentas guardadas):

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# FIELD_ENCRYPTION_KEY=<la clave que imprime>
```

### Desplegar esta versión

```bash
pip install -r requirements.txt   # añade cryptography
playwright install chromium       # navegador que usa el scraper
python manage.py makemigrations players
python manage.py migrate          # crea players_snpaccount
```

## Correos

Todos los correos salen de join.zyra@gmail.com con el mismo pie corporativo (logo de
Zyra y contacto), montado en `core/emails.py` y `core/templates/emails/layout.html`.
El logo va incrustado en el propio correo (`static/zyra/email-logo.png`).

## Back-office

Panel para el dueño de la plataforma en `/backoffice/`: dashboard con KPIs de todos los
clubes, listado y ficha de clubes y de usuarios. Solo entra el personal de Zyra
(usuarios con `is_staff`); al resto se le responde 404. Los usuarios staff ven el
enlace *Back-office* en el menú de usuario. La consola SQL y la
importación de datos son solo para superusuarios.

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

### Carga y usuarios conectados

La página *Carga y conectados* (`/backoffice/load/`) y el KPI *Conectados ahora* del
dashboard salen de `backoffice.middleware.ActivityMiddleware`, que:

- apunta la última actividad de cada usuario con sesión (como mucho una vez por minuto;
  cuenta como conectado si ha hecho algo en los últimos 5 minutos y se borra al cerrar
  sesión);
- suma por minuto las peticiones, el tiempo de respuesta, las lentas (más de 1 s) y los
  errores 500. Los estáticos no cuentan. Cada proceso acumula en memoria y vuelca a la
  base de datos cada 15 segundos.

Las métricas de más de 30 días las borra cada noche el proceso programado
`purge_request_metrics`.

### Procesos programados

Los procesos se definen en `backoffice/jobs.py`: cada uno es un comando de Django con
su horario en formato cron (hora de Madrid). Para añadir uno, crea el comando y añade
una entrada a `JOBS`. En *Back-office → Procesos* se ven todos, con su última y
próxima ejecución, y se pueden pausar o ejecutar a mano. Cada ejecución queda en el
log con su salida y, si falla, el error; además se envía un email al personal de Zyra.

Un único lanzador ejecuta lo que toca. **El servidor tiene que llamarlo cada minuto**;
si no lo hace, el back-office avisa de que el lanzador no está en marcha:

```bash
python manage.py run_scheduler
```

Con cron, por ejemplo (ajusta las rutas):

```
* * * * * cd /ruta/a/LOS-GLADIADORES && /ruta/a/python manage.py run_scheduler >> /tmp/zyra-scheduler.log 2>&1
```

**Ejecutar ahora** no espera al lanzador: arranca el proceso en el momento y abre su
ficha con la **traza en directo** (se va guardando cada segundo, con la hora de cada
línea). Si el proceso ya está en marcha, no se lanza otra vez. Puedes cerrar la página:
la ejecución sigue y la traza queda en el log.

### Consola SQL

*Back-office → Consola SQL* (solo superusuarios) ejecuta consultas **de solo lectura**
sobre toda la base de datos, al estilo del Data Export de Salesforce:

- Solo una sentencia `SELECT` o `WITH`. La lectura la garantiza la base de datos:
  `PRAGMA query_only` en SQLite, transacción `READ ONLY` en PostgreSQL.
- Máximo 10 segundos por consulta, 500 filas en pantalla y 50.000 al exportar.
- Exporta a CSV (UTF-8 con `;`, se abre bien en Excel en español).
- Las contraseñas, sesiones y tokens no se pueden consultar y se ocultan en un `SELECT *`.
- Consultas guardadas, esquema de tablas a la vista y registro de todas las consultas
  lanzadas (quién, cuándo y cuántas filas).
- **Campos de los registros relacionados**, como en Salesforce: en una clave ajena se
  puede seguir con un punto. Por ejemplo
  `SELECT local_id, local_id.name, visiting.name FROM match_match LIMIT 100`
  (vale con o sin `_id`, con alias de tabla y hasta 4 saltos, p. ej.
  `local_id.club_id.name`). La consola lo convierte en `LEFT JOIN` y enseña el SQL
  ejecutado. En el esquema, las claves ajenas indican a qué tabla apuntan. No funciona
  dentro de subconsultas.
- **Autocompletado** mientras escribes: tablas tras `FROM`/`JOIN`, columnas de las tablas
  de la consulta (tras `SELECT`, una coma, `WHERE`…) y, al poner un punto tras una clave
  ajena (`local_id.`), los campos de la tabla relacionada. Flechas para elegir, Tab o
  Enter para insertar, Esc para cerrar y Ctrl + Espacio para abrir la lista a mano.

### Importar datos

*Back-office → Importar datos* (solo superusuarios) carga jugadores, equipos rivales o
partidos de un club desde un CSV: subir → emparejar columnas → previsualizar → confirmar.

- Modos: solo crear, solo actualizar o crear y actualizar. Los registros existentes se
  buscan por `id` o por su clave natural (nombre y apellidos, nombre del equipo).
- Cada fila pasa las validaciones del modelo; si alguna falla no se importa nada y se
  pueden descargar los errores.
- Cada importación queda en el historial y se puede **deshacer**.
- Edición masiva: exporta desde la consola SQL con la columna `id`, edita en Excel e
  importa en modo actualizar.

### Desplegar esta versión

```bash
python manage.py makemigrations backoffice
python manage.py migrate          # crea las tablas del back-office
```

y programa `run_scheduler` cada minuto como se explica arriba.
