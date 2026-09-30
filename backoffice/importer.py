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

from match.models import Match
from players.models import Player
from team.models import Team

MAX_BYTES = 2 * 1024 * 1024
MAX_ROWS = 5000

CREATE, UPDATE, UPSERT = "create", "update", "upsert"
MODES = [
    (CREATE, "Solo crear registros nuevos"),
    (UPDATE, "Solo actualizar registros existentes"),
    (UPSERT, "Crear o actualizar (según exista o no)"),
]


class ImportFileError(ValueError):
    """Error del fichero en su conjunto (no de una fila)."""


def normalize(text):
    text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


# ---------- Conversión de valores ----------

TRUE = {"1", "si", "s", "yes", "y", "true", "verdadero", "x"}
FALSE = {"0", "no", "n", "false", "falso"}


def parse_bool(value):
    v = normalize(value)
    if v in TRUE:
        return True
    if v in FALSE:
        return False
    raise ValidationError(f"«{value}» no es sí/no.")


def parse_date(value):
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y"):
        try:
            return datetime.datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    raise ValidationError(f"«{value}» no es una fecha (usa 2026-10-25 o 25/10/2026).")


def choice_parser(choices):
    options = {}
    for value, label in choices:
        options[normalize(value)] = value
        options[normalize(label)] = value

    def parse(text):
        key = normalize(text)
        if key in options:
            return options[key]
        raise ValidationError(f"«{text}» no es válido; usa {', '.join(v for v, _ in choices)}.")
    return parse


def parse_int(value):
    try:
        return int(str(value).strip())
    except ValueError:
        raise ValidationError(f"«{value}» no es un número.")


@dataclass
class Field:
    name: str
    label: str
    parse: object = str.strip
    required: bool = False
    aliases: tuple = ()
    example: str = ""

    def matches(self, header):
        h = normalize(header)
        return h in {normalize(self.name), normalize(self.label), *(normalize(a) for a in self.aliases)}


ID_FIELD = Field("id", "ID", parse_int, aliases=("pk", "identificador"), example="")


# ---------- Objetos importables ----------

@dataclass
class Entity:
    key: str
    label: str
    model: object
    fields: list
    help: str = ""
    # Campos que se muestran en la previsualización.
    preview: tuple = ()

    def all_fields(self):
        return [ID_FIELD, *self.fields]

    def queryset(self, club):
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
                raise ValidationError(f"No existe un registro con ID {values['id']} en este club.")
            return obj
        return self.find_natural(club, values)

    def find_natural(self, club, values):
        return None

    def natural_key(self, values, obj):
        return None

    def apply(self, club, obj, values):
        for name, value in values.items():
            if name != "id":
                setattr(obj, name, value)

    def new(self, club):
        return self.model(club=club)


class PlayerEntity(Entity):
    def find_natural(self, club, values):
        if values.get("name") and values.get("last_name"):
            return self.queryset(club).filter(name__iexact=values["name"], last_name__iexact=values["last_name"]).first()
        return None

    def natural_key(self, values, obj):
        return (normalize(values.get("name", obj.name)), normalize(values.get("last_name", obj.last_name)))

    def new(self, club):
        return Player(club=club, team=club.own_team)


class TeamEntity(Entity):
    def queryset(self, club):
        return Team.objects.filter(club=club, is_own=False)

    def find_natural(self, club, values):
        if values.get("name"):
            return Team.objects.filter(club=club, name__iexact=values["name"]).first()
        return None

    def natural_key(self, values, obj):
        return normalize(values.get("name", obj.name))

    def new(self, club):
        return Team(club=club, is_own=False)


class MatchEntity(Entity):
    def apply(self, club, obj, values):
        for name, value in values.items():
            if name in ("local", "visiting"):
                team = Team.objects.filter(club=club, name__iexact=value).first()
                if team is None:
                    raise ValidationError({name: f"No hay ningún equipo «{value}» en este club."})
                setattr(obj, name, team)
            elif name != "id":
                setattr(obj, name, value)
        if obj.local_id and obj.local_id == obj.visiting_id:
            raise ValidationError("El equipo local y el visitante no pueden ser el mismo.")
        if obj.local_id and obj.visiting_id and not (obj.local.is_own or obj.visiting.is_own):
            raise ValidationError(f"Uno de los dos equipos tiene que ser {club.own_team}.")


ENTITIES = {
    e.key: e for e in [
        PlayerEntity(
            "players", "Jugadores", Player,
            [
                Field("name", "Nombre", required=True, aliases=("nombre", "first_name"), example="Ana"),
                Field("last_name", "Apellidos", required=True, aliases=("apellido", "apellidos"), example="García López"),
                Field("position", "Posición", choice_parser(Player.POSITIONS), aliases=("lado",), example="Derecha"),
                Field("skillfull_hand", "Mano", choice_parser(Player.HAND), aliases=("mano_habil",), example="Diestro"),
                Field("in_team", "En plantilla", parse_bool, aliases=("activo", "en_equipo"), example="sí"),
                Field("joined_season", "Temporada de alta", aliases=("temporada",), example="2026-2027"),
            ],
            help="Se buscan por ID o, si no hay ID, por nombre y apellidos dentro del club.",
            preview=("name", "last_name", "position", "in_team"),
        ),
        TeamEntity(
            "teams", "Equipos rivales", Team,
            [
                Field("name", "Nombre", required=True, aliases=("equipo", "nombre_equipo"), example="Pádel Norte"),
                Field("location", "Sede", required=True, aliases=("ubicacion", "direccion", "localizacion"), example="Club Norte, Sevilla"),
                Field("in_group", "En el grupo", parse_bool, aliases=("grupo",), example="sí"),
            ],
            help="Se buscan por ID o, si no hay ID, por nombre dentro del club. El equipo propio no se importa.",
            preview=("name", "location", "in_group"),
        ),
        MatchEntity(
            "matches", "Partidos", Match,
            [
                Field("start_date", "Fecha", parse_date, required=True, aliases=("fecha", "dia"), example="2026-10-25"),
                Field("local", "Local", required=True, aliases=("equipo_local",), example="Los Gladiadores"),
                Field("visiting", "Visitante", required=True, aliases=("equipo_visitante",), example="Pádel Norte"),
                Field("location", "Ubicación", aliases=("sede", "lugar"), example=""),
            ],
            help="Los equipos se indican por su nombre y tienen que existir en el club. Para actualizar un partido hace falta su ID.",
            preview=("start_date", "local", "visiting"),
        ),
    ]
}


# ---------- Lectura del fichero ----------

def decode(data):
    if len(data) > MAX_BYTES:
        raise ImportFileError(f"El fichero pasa de {MAX_BYTES // (1024 * 1024)} MB.")
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            pass
    raise ImportFileError("No se puede leer el fichero: guárdalo como CSV UTF-8.")


def read_csv(text):
    """Devuelve (cabeceras, filas). Detecta si el separador es ; , o tabulador."""
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
    except csv.Error:
        class dialect(csv.excel):
            delimiter = ";" if sample.count(";") > sample.count(",") else ","
    rows = [r for r in csv.reader(io.StringIO(text), dialect) if any(c.strip() for c in r)]
    if not rows:
        raise ImportFileError("El fichero está vacío.")
    headers = [h.strip() for h in rows[0]]
    if len(rows) - 1 > MAX_ROWS:
        raise ImportFileError(f"El fichero tiene {len(rows) - 1} filas; el máximo son {MAX_ROWS}.")
    if len(rows) == 1:
        raise ImportFileError("El fichero solo tiene la fila de cabeceras.")
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
    line: int
    values: dict
    action: str = ""        # "create" | "update"
    errors: list = field(default_factory=list)
    obj: object = None
    before: dict = field(default_factory=dict)

    @property
    def ok(self):
        return not self.errors


def _messages(exc):
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
    missing = [f.label for f in entity.fields if f.required and f.name not in mapping and mode != UPDATE]
    if missing:
        raise ImportFileError(f"Falta emparejar campos obligatorios: {', '.join(missing)}.")
    if mode == UPDATE and "id" not in mapping and not isinstance(entity, (PlayerEntity, TeamEntity)):
        raise ImportFileError("Para actualizar partidos hace falta la columna ID.")

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
            result.errors.append("No existe ese registro y el modo es solo actualizar.")
            continue
        if obj is not None and mode == CREATE:
            result.errors.append(f"Ya existe (ID {obj.pk}) y el modo es solo crear.")
            continue
        if obj is None:
            for f in entity.fields:
                if f.required and f.name not in result.values:
                    result.errors.append(f"{f.label}: obligatorio.")
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
                result.errors.append(f"Repetido en el fichero (igual que la línea {seen[key]}).")
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
