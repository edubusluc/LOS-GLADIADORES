from django.urls import path
from .views import *

urlpatterns = [
    path("team_statistics",team_statistics, name='team_statistics')
]