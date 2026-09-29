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
equipos rivales, partidos, convocatorias, publicaciones y estadísticas, y sus usuarios
(`core.Membership`) solo pueden ver los datos de los clubes a los que pertenecen.

- **Administrador**: gestiona jugadores, equipos, partidos, convocatorias, publicaciones y miembros.
- **Miembro**: solo consulta.

Un club nuevo se registra desde `/core/register_club/`; los administradores añaden
miembros desde `/core/members/`. Si un usuario pertenece a varios clubes, elige el
activo con el selector de la barra superior.

### Actualizar una base de datos existente

```bash
python manage.py makemigrations core team players match post
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
