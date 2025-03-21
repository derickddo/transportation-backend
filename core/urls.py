from django.urls import path, include
from rest_framework.routers import DefaultRouter
from django.contrib import admin


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
    
]
