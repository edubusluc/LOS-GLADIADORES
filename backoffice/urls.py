from django.urls import path

from . import views

app_name = "backoffice"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("load/", views.load, name="load"),
    path("jobs/", views.job_list, name="job_list"),
    path("jobs/runs/", views.run_list, name="run_list"),
    path("jobs/runs/<int:run_id>/", views.run_detail, name="run_detail"),
    path("jobs/<str:name>/", views.job_detail, name="job_detail"),
    path("jobs/<str:name>/toggle/", views.job_toggle, name="job_toggle"),
    path("jobs/<str:name>/run/", views.job_run_now, name="job_run_now"),
    path("clubs/", views.club_list, name="club_list"),
    path("clubs/<int:club_id>/", views.club_detail, name="club_detail"),
    path("users/", views.user_list, name="user_list"),
    path("users/<int:user_id>/", views.user_detail, name="user_detail"),
]
