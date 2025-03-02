from django.urls import path
from .views import create_player, list_players, edit_player, show_player, force_update_score

urlpatterns = (
    path("create_player",create_player, name='create_player'),
    path("list_players",list_players, name='list_players'),
    path("edit_player/<int:player_id>",edit_player, name='edit_player'),
    path("player_details/<int:player_id>/",show_player, name = 'show_player' ),
    # path("update_score/", get_snp_score, name="update_score"),
    path("force_update_score/", force_update_score, name="force_update_score"),
)