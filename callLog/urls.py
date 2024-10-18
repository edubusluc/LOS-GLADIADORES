from .views import view_call_log
from django.urls import path
urlpatterns = [
    path('view_call_log/<int:call_id>', view_call_log, name='view_call_log'),
]