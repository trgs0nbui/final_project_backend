from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from apps.tasks.urls import my_task_urlpatterns

urlpatterns = [
    path("admin/", admin.site.urls),

    # Authentication & User profile
    path("api/", include("apps.users.urls")),

    # Project CRUD & Member management
    path("api/projects/", include("apps.projects.urls")),

    # Task CRUD (nested under project)
    path("api/projects/<uuid:project_id>/tasks/", include("apps.tasks.urls")),

    # My tasks — cross-project task views for the authenticated user
    # GET /api/tasks/          → tasks assigned to current user
    # GET /api/tasks/stats/    → stats for tasks assigned to current user
    path("api/tasks/", include((my_task_urlpatterns, "tasks"))),

    # Comments (nested under tasks)
    path(
        "api/projects/<uuid:project_id>/tasks/<uuid:task_id>/comments/",
        include("apps.comments.urls"),
    ),
]

# Serve uploaded media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
