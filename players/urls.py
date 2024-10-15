from django.urls import path
from .views import *
from players.views import *

urlpatterns = (
    path("create_player",create_player, name='create_player'),
    path("list_players",list_players, name='list_players'),
    path("edit_player/<int:player_id>",edit_player, name='edit_player'),
    path("delete_player/<int:player_id>",delete_player, name='delete_player'),
)