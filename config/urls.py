from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("apps.users.urls")),
    path('api/projects/', include('apps.projects.urls')),
    path('api/projects/<uuid:project_id>/tasks/', include('apps.tasks.urls')),
]
