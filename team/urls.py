from django.urls import path
from .views import list_team,create_team, edit_team

urlpatterns = [
    path("list_teams",list_team, name='list_teams'), 
    path("create_team",create_team, name='create_team'),
    path("edit_team/<int:team_id>/",edit_team, name='edit_team')
]