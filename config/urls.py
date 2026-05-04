from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),

    # Authentication & User profile
    # POST /api/auth/register/
    # POST /api/auth/login/
    # POST /api/auth/token/refresh/
    # GET  /api/auth/verify-email/
    # GET  /api/users/me/
    # PATCH /api/users/me/
    path("api/", include("apps.users.urls")),

    # Project CRUD & Member management
    # GET  /api/projects/
    # POST /api/projects/
    # GET/PUT/PATCH/DELETE /api/projects/<id>/
    # GET/POST /api/projects/<id>/members/
    # DELETE   /api/projects/<id>/members/<user_id>/
    path("api/projects/", include("apps.projects.urls")),

    # Task CRUD (nested under project)
    # GET  /api/projects/<project_id>/tasks/
    # POST /api/projects/<project_id>/tasks/
    # GET/PUT/PATCH/DELETE /api/projects/<project_id>/tasks/<task_id>/
    path("api/projects/<uuid:project_id>/tasks/", include("apps.tasks.urls")),
]
