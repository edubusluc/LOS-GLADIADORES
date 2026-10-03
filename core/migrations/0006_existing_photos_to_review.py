from django.db import migrations

from core.public_id import new_public_id


def existing_photos_to_review(apps, schema_editor):
    """Las fotos subidas antes de existir la revisión quedan pendientes de revisar en el back-office."""
    PhotoCheck = apps.get_model("core", "PhotoCheck")
    # Las subidas desde 0004_photo_check ya tienen su registro.
    registered = set(PhotoCheck.objects.exclude(photo="").values_list("photo", flat=True))
    checks = []
    for model_name, app in (("Team", "team"), ("Player", "players")):
        model = apps.get_model(app, model_name)
        field = "team" if model_name == "Team" else "player"
        for obj in model.objects.exclude(photo__isnull=True).exclude(photo="").only("id", "club_id", "photo"):
            if obj.photo.name in registered:
                continue
            checks.append(PhotoCheck(
                public_id=new_public_id("PHC"), club_id=obj.club_id, photo=obj.photo.name,
                status="unchecked", reason="Subida antes de la revisión de fotos", **{f"{field}_id": obj.id},
            ))
    PhotoCheck.objects.bulk_create(checks)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0005_photo_removal"),
        ("players", "0006_player_user"),
    ]

    operations = [
        migrations.RunPython(existing_photos_to_review, migrations.RunPython.noop),
    ]
