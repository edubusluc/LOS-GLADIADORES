from django.contrib import admin
from .models import Call


@admin.register(Call)
class CallAdmin(admin.ModelAdmin):
    list_display = ("__str__", "club", "match_date", "draft_mode")
    list_filter = ("match__club", "draft_mode")
    list_select_related = ("match__club", "match__local", "match__visiting")
    filter_horizontal = ("players",)

    @admin.display(description="Club", ordering="match__club__name")
    def club(self, obj):
        return obj.match.club

    @admin.display(description="Fecha", ordering="match__start_date")
    def match_date(self, obj):
        return obj.match.start_date
