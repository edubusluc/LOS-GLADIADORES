from django.urls import path
from .views import *
from call.views import delete_call

urlpatterns = (
    path("create_match",create_match, name='create_match'),
    path("list_match",list_match, name='list_match'),
    path("create_call/<int:match_id>/",create_call, name='create_call'),
    path('call_for_match/<int:match_id>/', call_for_match, name='call_for_match'),
    path("create_game/<int:match_id>/",create_game_for_match, name='create_game'),
    path("create_result/<int:game_id>/",create_result, name='create_result'),
    path("existing_call/<int:match_id>/", existing_call_view, name="existing_call"),
    path("edit_call/<int:call_id>/", edit_call, name='edit_call'),
    path("closed_call/<int:call_id>/", closed_call, name="closed_call"),
    path('close_match/<int:match_id>/', close_match, name='close_match'),
    path('delete_call/<int:match_id>/', delete_call, name='delete_call'),
    path('close_call/<int:match_id>/', close_call, name='close_call'),
)