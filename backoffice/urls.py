from django.urls import path

from . import views

app_name = "backoffice"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("load/", views.load, name="load"),
    path("jobs/", views.job_list, name="job_list"),
    path("jobs/runs/", views.run_list, name="run_list"),
    path("jobs/runs/<pid:run_id>/", views.run_detail, name="run_detail"),
    path("jobs/runs/<pid:run_id>/live/", views.run_live, name="run_live"),
    path("jobs/<str:name>/", views.job_detail, name="job_detail"),
    path("jobs/<str:name>/toggle/", views.job_toggle, name="job_toggle"),
    path("jobs/<str:name>/run/", views.job_run_now, name="job_run_now"),
    path("sql/", views.sql_console, name="sql_console"),
    path("sql/log/", views.sql_log, name="sql_log"),
    path("sql/saved/<pid:query_id>/delete/", views.sql_delete_saved, name="sql_delete_saved"),
    path("import/", views.import_list, name="import_list"),
    path("import/template/<str:entity>.csv", views.import_template, name="import_template"),
    path("import/<pid:job_id>/map/", views.import_map, name="import_map"),
    path("import/<pid:job_id>/preview/", views.import_preview, name="import_preview"),
    path("import/<pid:job_id>/confirm/", views.import_confirm, name="import_confirm"),
    path("import/<pid:job_id>/undo/", views.import_undo, name="import_undo"),
    path("clubs/", views.club_list, name="club_list"),
    path("clubs/<pid:club_id>/", views.club_detail, name="club_detail"),
    path("users/", views.user_list, name="user_list"),
    path("users/<int:user_id>/", views.user_detail, name="user_detail"),
    path("users/<int:user_id>/photos/delete/", views.user_photos_delete, name="user_photos_delete"),
    path("photos/", views.photo_list, name="photo_list"),
    path("photos/<pid:check_id>/delete/", views.photo_delete, name="photo_delete"),
    path("photos/<pid:check_id>/reviewed/", views.photo_reviewed, name="photo_reviewed"),
]
