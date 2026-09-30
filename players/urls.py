from django.urls import path
from .views import create_player, list_players, edit_player, show_player, manage_roster, snp_account, snp_account_delete

urlpatterns = (
    path("create_player",create_player, name='create_player'),
    path("list_players",list_players, name='list_players'),
    path("edit_player/<int:player_id>",edit_player, name='edit_player'),
    path("player_details/<int:player_id>/",show_player, name = 'show_player' ),
    path("snp/", snp_account, name="snp_account"),
    path("snp/delete/", snp_account_delete, name="snp_account_delete"),
    path("roster/", manage_roster, name="manage_roster"),
)