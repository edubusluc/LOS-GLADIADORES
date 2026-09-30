from django.contrib import admin
from .models import Match, Game, Result


class GameInline(admin.TabularInline):
    model = Game
    extra = 0
    fields = ("n_game", "player_1_local", "player_2_local", "player_1_visiting", "player_2_visiting", "winner", "draft_mode")


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ("__str__", "club", "start_date", "season", "result", "result_points", "draft_mode")
    list_filter = ("club", "season", "result", "draft_mode")
    search_fields = ("local__name", "visiting__name", "location")
    date_hierarchy = "start_date"
    list_select_related = ("club", "local", "visiting")
    inlines = [GameInline]


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ("match", "n_game", "winner", "draft_mode")
    list_filter = ("match__club", "draft_mode")
    list_select_related = ("match__local", "match__visiting")


@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = ("game", "result", "set1_local", "set1_visiting", "set2_local", "set2_visiting", "set3_local", "set3_visiting")
    list_filter = ("game__match__club",)
