"""Registro de las convocatorias en el admin de Django."""
from django.contrib import admin
from .models import Call


@admin.register(Call)
class CallAdmin(admin.ModelAdmin):
    """Convocatorias en el admin, con el club y la fecha del partido."""
    list_display = ("__str__", "club", "match_date", "draft_mode")
    list_filter = ("match__club", "draft_mode")
    list_select_related = ("match__club", "match__local", "match__visiting")
    filter_horizontal = ("players",)

    @admin.display(description="Club", ordering="match__club__name")
    def club(self, obj):
        """Club del partido de la convocatoria."""
        return obj.match.club

    @admin.display(description="Fecha", ordering="match__start_date")
    def match_date(self, obj):
        """Fecha de inicio del partido de la convocatoria."""
        return obj.match.start_date
