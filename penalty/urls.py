"""URLs de advertencias."""
from .views import create_penalty
from django.urls import path
urlpatterns = [
    path('create_penalty/<pid:call_id>/', create_penalty, name='create_penalty'),
]