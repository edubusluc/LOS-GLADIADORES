"""
Los empates se guardaban como «Empate», un valor que no está en Match.POSSIBLE_RESULT («EMPATE»),
así que no se mostraban con su etiqueta. Corrige los que ya hay.
"""
from django.db import migrations


def forwards(apps, schema_editor):
    """Pasa «Empate» al valor de las opciones del campo."""
    apps.get_model("match", "Match").objects.filter(result="Empate").update(result="EMPATE")


class Migration(migrations.Migration):
    """Migración de datos: valor de los empates."""

    dependencies = [("match", "0004_match_type_amistoso")]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
