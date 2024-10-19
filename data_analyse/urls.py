from django.urls import path
from .views import team_statistics, statistics_per_player

urlpatterns = [
    path("team_statistics",team_statistics, name='team_statistics'),
    path("player_statistics", statistics_per_player, name='player_statistics')
]