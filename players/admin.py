from django.contrib import admin
from .models import Player


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ("name", "last_name", "club", "position", "skillfull_hand", "in_team", "joined_season")
    list_filter = ("club", "in_team", "position")
    search_fields = ("name", "last_name")
    list_select_related = ("club",)
