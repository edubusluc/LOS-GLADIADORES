"""
URL configuration for snp_gladiadores project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include

from core.views import error_404_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path("", include("post.urls")),
    path('players/', include('players.urls')),
    path('match/', include('match.urls')),
    path('data_analyse/',include('data_analyse.urls')),
    path('team/',include('team.urls')),
    path('callLog/',include('callLog.urls')),
    path('penalty/',include('penalty.urls')),
    path('core/', include('core.urls')),
    
]

handler404 = error_404_view
