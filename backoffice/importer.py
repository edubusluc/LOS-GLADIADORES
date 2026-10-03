"""
Importación de datos desde CSV al estilo del Data Import Wizard de Salesforce.

Flujo: subir el fichero → emparejar columnas con campos → previsualizar con la
validación de cada fila → confirmar. Todo entra en una sola transacción: o el fichero
entero o nada. Cada fila pasa por las validaciones del modelo (full_clean), nunca por
SQL libre, y se guarda lo necesario para deshacer la importación.
"""
import csv
import datetime
import io
import re
import unicodedata
from dataclasses import dataclass, field

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import translation
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from match.models import Match
from players.models import Player
from team.models import Team

MAX_BYTES = 2 * 1024 * 1024
MAX_ROWS = 5000

CREATE, UPDATE, UPSERT = "create", "update", "upsert"
MODES = [
    (CREATE, gettext_lazy("Solo crear registros nuevos")),
    (UPDATE, gettext_lazy("Solo actualizar registros existentes")),
    (UPSERT, gettext_lazy("Crear o actualizar (según exista o no)")),
]


class ImportFileError(ValueError):
    """Error del fichero en su conjunto (no de una fila)."""


def normalize(text):
    """Texto sin acentos, en minúsculas y con guiones bajos, para comparar cabeceras y valores."""
    text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


# ---------- Conversión de valores ----------

TRUE = {"1", "si", "s", "yes", "y", "true", "verdadero", "x"}
FALSE = {"0", "no", "n", "false", "falso"}


def parse_bool(value):
    """Convierte sí/no (y variantes: 1/0, x, true...) en bool; si no, ValidationError."""
    v = normalize(value)
    if v in TRUE:
        return True
    if v in FALSE:
        return False
    raise ValidationError(_("«%(value)s» no es sí/no.") % {"value": value})


def parse_date(value):
    """Convierte una fecha en formato ISO o español (25/10/2026, 25-10-2026, 25/10/26) en date."""
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y"):
        try:
            return datetime.datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    raise ValidationError(_("«%(value)s» no es una fecha (usa 2026-10-25 o 25/10/2026).") % {"value": value})


def choice_parser(choices):
    """
    Devuelve un conversor para un campo con choices: admite el valor o la etiqueta,
    sin distinguir mayúsculas ni acentos.
    """
    options = {}
    for value, label in choices:
        options[normalize(value)] = value
        options[normalize(label)] = value

    def parse(text):
        """Valor de la opción cuyo valor o etiqueta coincide con `text`; si no, ValidationError."""
        key = normalize(text)
        if key in options:
            return options[key]
        raise ValidationError(_("«%(value)s» no es válido; usa %(options)s.") % {
            "value": text, "options": ", ".join(v for v, _label in choices),
        })
    return parse


def parse_int(value):
    """Convierte el texto en entero; si no es un número, ValidationError."""
    try:
        return int(str(value).strip())
    except ValueError:
        raise ValidationError(_("«%(value)s» no es un número.") % {"value": value})


@dataclass
class Field:
    """
    Campo importable: nombre en el modelo, etiqueta, conversor del texto, si es obligatorio,
    otros nombres de columna que se reconocen y valor de ejemplo para la plantilla.
    """
    name: str
    label: str
    parse: object = str.strip
    required: bool = False
    aliases: tuple = ()
    example: str = ""

    def matches(self, header):
        """True si la cabecera de una columna del fichero corresponde a este campo."""
        h = normalize(header)
        # La etiqueta cuenta en el idioma activo y en español (las plantillas pueden venir de cualquiera de los dos).
        with translation.override("es"):
            label_es = normalize(self.label)
        return h in {normalize(self.name), normalize(self.label), label_es, *(normalize(a) for a in self.aliases)}


ID_FIELD = Field("id", "ID", parse_int, aliases=("pk", "identificador"), example="")


# ---------- Objetos importables ----------

@dataclass
class Entity:
    """
    Objeto importable (jugadores, equipos, partidos): su modelo, sus campos y cómo se
    buscan, crean y rellenan sus registros dentro de un club. Las subclases ajustan cada caso.
    """
    key: str
    label: str
    model: object
    fields: list
    help: str = ""
    # Campos que se muestran en la previsualización.
    preview: tuple = ()

    def all_fields(self):
        """Campos que se pueden emparejar: el ID y los propios del objeto."""
        return [ID_FIELD, *self.fields]

    def queryset(self, club):
        """Registros del club entre los que se busca."""
        return self.model.objects.filter(club=club)

    # Campos que no se importan pero sí cuentan para las validaciones (restricciones únicas).
    ALWAYS_VALIDATED = {"club", "team", "is_own", "local", "visiting"}

    def not_validated(self):
        """Campos del modelo que no vienen del fichero: no se validan (fotos, puntuaciones...)."""
        imported = {f.name for f in self.fields} | self.ALWAYS_VALIDATED
        return [f.name for f in self.model._meta.concrete_fields if f.name not in imported]

    def find(self, club, values):
        """Registro existente al que se refiere la fila (por ID o por su clave natural), o None."""
        if values.get("id") is not None:
            obj = self.queryset(club).filter(pk=values["id"]).first()
            if obj is None:
                raise ValidationError(_("No existe un registro con ID %(id)s en este club.") % {"id": values["id"]})
            return obj
        return self.find_natural(club, values)

    def find_natural(self, club, values):
        """Registro que corresponde a la fila por su clave natural; por defecto no hay y devuelve None."""
        return None

    def natural_key(self, values, obj):
        """Clave para detectar filas repetidas en el fichero; None si el objeto no tiene clave natural."""
        return None

    def apply(self, club, obj, values):
        """Copia en el registro los valores de la fila (salvo el ID)."""
        for name, value in values.items():
            if name != "id":
                setattr(obj, name, value)

    def new(self, club):
        """Registro nuevo (sin guardar) del club."""
        return self.model(club=club)


class PlayerEntity(Entity):
    """Jugadores del club; la clave natural es nombre y apellidos."""
    def find_natural(self, club, values):
        """Jugador del club con el mismo nombre y apellidos (sin distinguir mayúsculas), o None."""
        if values.get("name") and values.get("last_name"):
            return self.queryset(club).filter(name__iexact=values["name"], last_name__iexact=values["last_name"]).first()
        return None

    def natural_key(self, values, obj):
        """Nombre y apellidos normalizados (los de la fila o, si faltan, los del registro)."""
        return (normalize(values.get("name", obj.name)), normalize(values.get("last_name", obj.last_name)))

    def new(self, club):
        """Jugador nuevo del equipo propio del club."""
        return Player(club=club, team=club.own_team)


class TeamEntity(Entity):
    """Equipos rivales del club (el equipo propio no se importa); la clave natural es el nombre."""
    def queryset(self, club):
        """Solo los equipos rivales del club."""
        return Team.objects.filter(club=club, is_own=False)

    def find_natural(self, club, values):
        """Equipo del club con ese nombre (sin distinguir mayúsculas), o None."""
        if values.get("name"):
            return Team.objects.filter(club=club, name__iexact=values["name"]).first()
        return None

    def natural_key(self, values, obj):
        """Nombre normalizado del equipo."""
        return normalize(values.get("name", obj.name))

    def new(self, club):
        """Equipo rival nuevo del club."""
        return Team(club=club, is_own=False)


class MatchEntity(Entity):
    """Partidos del club; se identifican solo por ID y los equipos se indican por su nombre."""
    def apply(self, club, obj, values):
        """
        Copia los valores de la fila; local y visitante se buscan por nombre entre los equipos
        del club. Uno de los dos tiene que ser el equipo propio y no pueden ser el mismo.
        """
        for name, value in values.items():
            if name in ("local", "visiting"):
                team = Team.objects.filter(club=club, name__iexact=value).first()
                if team is None:
                    raise ValidationError({name: _("No hay ningún equipo «%(team)s» en este club.") % {"team": value}})
                setattr(obj, name, team)
            elif name != "id":
                setattr(obj, name, value)
        if obj.local_id and obj.local_id == obj.visiting_id:
            raise ValidationError(_("El equipo local y el visitante no pueden ser el mismo."))
        if obj.local_id and obj.visiting_id and not (obj.local.is_own or obj.visiting.is_own):
            raise ValidationError(_("Uno de los dos equipos tiene que ser %(team)s.") % {"team": club.own_team})


ENTITIES = {
    e.key: e for e in [
        PlayerEntity(
            "players", gettext_lazy("Jugadores"), Player,
            [
                Field("name", gettext_lazy("Nombre"), required=True, aliases=("nombre", "first_name"), example="Ana"),
                Field("last_name", gettext_lazy("Apellidos"), required=True, aliases=("apellido", "apellidos"), example="García López"),
                Field("position", gettext_lazy("Posición"), choice_parser(Player.POSITIONS), aliases=("lado",), example="Derecha"),
                Field("skillfull_hand", gettext_lazy("Mano"), choice_parser(Player.HAND), aliases=("mano_habil",), example="Diestro"),
                Field("in_team", gettext_lazy("En plantilla"), parse_bool, aliases=("activo", "en_equipo"), example="sí"),
                Field("joined_season", gettext_lazy("Temporada de alta"), aliases=("temporada",), example="2026-2027"),
            ],
            help=gettext_lazy("Se buscan por ID o, si no hay ID, por nombre y apellidos dentro del club."),
            preview=("name", "last_name", "position", "in_team"),
        ),
        TeamEntity(
            "teams", gettext_lazy("Equipos rivales"), Team,
            [
                Field("name", gettext_lazy("Nombre"), required=True, aliases=("equipo", "nombre_equipo"), example="Pádel Norte"),
                Field("location", gettext_lazy("Sede"), required=True, aliases=("ubicacion", "direccion", "localizacion"), example="Club Norte, Sevilla"),
                Field("in_group", gettext_lazy("En el grupo"), parse_bool, aliases=("grupo",), example="sí"),
            ],
            help=gettext_lazy("Se buscan por ID o, si no hay ID, por nombre dentro del club. El equipo propio no se importa."),
            preview=("name", "location", "in_group"),
        ),
        MatchEntity(
            "matches", gettext_lazy("Partidos"), Match,
            [
                Field("start_date", gettext_lazy("Fecha"), parse_date, required=True, aliases=("fecha", "dia"), example="2026-10-25"),
                Field("local", gettext_lazy("Local"), required=True, aliases=("equipo_local",), example="Mi equipo"),
                Field("visiting", gettext_lazy("Visitante"), required=True, aliases=("equipo_visitante",), example="Pádel Norte"),
                Field("location", gettext_lazy("Ubicación"), aliases=("sede", "lugar"), example=""),
            ],
            help=gettext_lazy("Los equipos se indican por su nombre y tienen que existir en el club. Para actualizar un partido hace falta su ID."),
            preview=("start_date", "local", "visiting"),
        ),
    ]
}


# ---------- Lectura del fichero ----------

def decode(data):
    """Decodifica el fichero subido (UTF-8 o, si no, Windows-1252) comprobando su tamaño máximo."""
    if len(data) > MAX_BYTES:
        raise ImportFileError(_("El fichero pasa de %(mb)s MB.") % {"mb": MAX_BYTES // (1024 * 1024)})
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            pass
    raise ImportFileError(_("No se puede leer el fichero: guárdalo como CSV UTF-8."))


def read_csv(text):
    """Devuelve (cabeceras, filas). Detecta si el separador es ; , o tabulador."""
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
    except csv.Error:
        class dialect(csv.excel):
            """Dialecto de reserva si no se detecta el separador: ; o , (el que más aparezca)."""
            delimiter = ";" if sample.count(";") > sample.count(",") else ","
    rows = [r for r in csv.reader(io.StringIO(text), dialect) if any(c.strip() for c in r)]
    if not rows:
        raise ImportFileError(_("El fichero está vacío."))
    headers = [h.strip() for h in rows[0]]
    if len(rows) - 1 > MAX_ROWS:
        raise ImportFileError(_("El fichero tiene %(rows)s filas; el máximo son %(max)s.") % {"rows": len(rows) - 1, "max": MAX_ROWS})
    if len(rows) == 1:
        raise ImportFileError(_("El fichero solo tiene la fila de cabeceras."))
    return headers, rows[1:]


def guess_mapping(entity, headers):
    """Empareja cada campo con la columna del fichero que se llama igual (o parecido)."""
    mapping = {}
    for f in entity.all_fields():
        for i, header in enumerate(headers):
            if f.matches(header) and i not in mapping.values():
                mapping[f.name] = i
                break
    return mapping


# ---------- Validación y aplicación ----------

@dataclass
class RowResult:
    """
    Resultado de validar una fila: valores convertidos, acción (crear o actualizar),
    errores, el objeto preparado y los valores anteriores (para poder deshacer).
    """
    line: int
    values: dict
    action: str = ""        # "create" | "update"
    errors: list = field(default_factory=list)
    obj: object = None
    before: dict = field(default_factory=dict)

    @property
    def ok(self):
        """True si la fila no tiene errores."""
        return not self.errors


def _messages(exc):
    """Mensajes de un ValidationError, con el nombre del campo delante cuando lo hay."""
    if hasattr(exc, "message_dict"):
        out = []
        for name, msgs in exc.message_dict.items():
            prefix = "" if name == "__all__" else f"{name}: "
            out += [prefix + m for m in msgs]
        return out
    return list(exc.messages)


def process(entity, club, mode, headers, rows, mapping, save=False):
    """
    Valida (y si save=True, guarda) todas las filas. Devuelve la lista de RowResult.
    Con save=True hay que llamarla dentro de una transacción.
    """
    fields = {f.name: f for f in entity.all_fields()}
    missing = [str(f.label) for f in entity.fields if f.required and f.name not in mapping and mode != UPDATE]
    if missing:
        raise ImportFileError(_("Falta emparejar campos obligatorios: %(fields)s.") % {"fields": ", ".join(missing)})
    if mode == UPDATE and "id" not in mapping and not isinstance(entity, (PlayerEntity, TeamEntity)):
        raise ImportFileError(_("Para actualizar partidos hace falta la columna ID."))

    results, seen = [], {}
    for n, row in enumerate(rows, start=2):  # la línea 1 son las cabeceras
        result = RowResult(line=n, values={})
        results.append(result)
        # 1. Convertir cada celda.
        for name, index in mapping.items():
            raw = row[index].strip() if index < len(row) else ""
            if raw == "":
                continue  # celda vacía: en altas vale el valor por defecto; en actualizaciones no se toca
            try:
                result.values[name] = fields[name].parse(raw)
            except ValidationError as exc:
                result.errors.append(f"{fields[name].label}: {' '.join(exc.messages)}")
        if result.errors:
            continue
        # 2. Buscar si ya existe.
        try:
            obj = entity.find(club, result.values)
        except ValidationError as exc:
            result.errors += exc.messages
            continue
        if obj is None and mode == UPDATE:
            result.errors.append(_("No existe ese registro y el modo es solo actualizar."))
            continue
        if obj is not None and mode == CREATE:
            result.errors.append(_("Ya existe (ID %(id)s) y el modo es solo crear.") % {"id": obj.pk})
            continue
        if obj is None:
            for f in entity.fields:
                if f.required and f.name not in result.values:
                    result.errors.append(_("%(field)s: obligatorio.") % {"field": f.label})
            if result.errors:
                continue
            obj, result.action = entity.new(club), CREATE
        else:
            result.action = UPDATE
            result.before = {name: _plain(getattr(obj, name)) for name in result.values if name != "id"}
        # 3. Aplicar y validar con las reglas del modelo.
        try:
            entity.apply(club, obj, result.values)
            obj.full_clean(exclude=entity.not_validated())
        except ValidationError as exc:
            result.errors += _messages(exc)
            continue
        key = entity.natural_key(result.values, obj) or (("id", obj.pk) if obj.pk else None)
        if key is not None:
            if key in seen:
                result.errors.append(_("Repetido en el fichero (igual que la línea %(line)s).") % {"line": seen[key]})
                continue
            seen[key] = n
        result.obj = obj
        if save:
            obj.save()
    return results


def _plain(value):
    """Valor guardable en JSON para poder deshacer."""
    if hasattr(value, "pk"):
        return value.pk
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    return value


def run_import(job):
    """Aplica una importación validada. Devuelve las filas; si alguna falla, no guarda nada."""
    entity = ENTITIES[job.entity]
    headers, rows = read_csv(job.content)
    with transaction.atomic():
        results = process(entity, job.club, job.mode, headers, rows, job.mapping, save=True)
        if any(not r.ok for r in results):
            transaction.set_rollback(True)
            return results
    job.result = {
        "created": [r.obj.pk for r in results if r.action == CREATE],
        "updated": [{"id": r.obj.pk, "before": r.before} for r in results if r.action == UPDATE],
    }
    return results


def undo_import(job):
    """Deshace una importación: borra lo creado y restaura los valores anteriores de lo actualizado."""
    entity = ENTITIES[job.entity]
    model = entity.model
    with transaction.atomic():
        created = model.objects.filter(club=job.club, pk__in=job.result.get("created", []))
        deleted = created.count()
        created.delete()
        restored = 0
        for item in job.result.get("updated", []):
            obj = model.objects.filter(club=job.club, pk=item["id"]).first()
            if obj is None:
                continue
            for name, value in item["before"].items():
                f = model._meta.get_field(name)
                if f.is_relation:
                    setattr(obj, f.attname, value)
                else:
                    setattr(obj, name, f.to_python(value))
            obj.save()
            restored += 1
    return deleted, restored


def template_csv(entity):
    """CSV de ejemplo con las cabeceras (y una fila de muestra) de un objeto."""
    out = io.StringIO()
    out.write("﻿")
    writer = csv.writer(out, delimiter=";")
    writer.writerow([f.label for f in entity.all_fields()])
    writer.writerow([f.example for f in entity.all_fields()])
    return out.getvalue()
