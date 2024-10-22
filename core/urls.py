from django.contrib import admin
from django.urls import path, include
from .views import *
from players.views import *
from django.contrib.auth import views as auth_views

urlpatterns = (
    path("", home, name="home"),
    path('login/', auth_views.LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
)