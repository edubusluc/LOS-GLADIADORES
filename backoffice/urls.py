from django.urls import path

from . import views

app_name = "backoffice"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("load/", views.load, name="load"),
    path("clubs/", views.club_list, name="club_list"),
    path("clubs/<int:club_id>/", views.club_detail, name="club_detail"),
    path("users/", views.user_list, name="user_list"),
    path("users/<int:user_id>/", views.user_detail, name="user_detail"),
]
