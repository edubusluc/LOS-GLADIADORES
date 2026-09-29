from django.urls import path
from .views import team_statistics, statistics_per_player, statistics_per_pair, warnings_statistics

urlpatterns = [
    path("team_statistics",team_statistics, name='team_statistics'),
    path("player_statistics", statistics_per_player, name='player_statistics'),
    path("pair_statistics", statistics_per_pair, name='pair_statistics'),
    path("warnings", warnings_statistics, name='warnings_statistics'),
]
