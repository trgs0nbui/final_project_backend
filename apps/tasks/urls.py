from django.urls import path

from . import views

# ── Project-scoped task URLs ─────────────────────────────────────────────────
# Mounted under /api/projects/<project_id>/tasks/ in config/urls.py

project_task_urlpatterns = [
    # GET  /api/projects/<project_id>/tasks/          → list tasks (filter/search/pagination)
    # POST /api/projects/<project_id>/tasks/          → create task (member only)
    path('', views.TaskListCreateView.as_view(), name='task-list-create'),

    # GET    /api/projects/<project_id>/tasks/<task_id>/  → retrieve task detail (member)
    # PUT    /api/projects/<project_id>/tasks/<task_id>/  → update task (member)
    # PATCH  /api/projects/<project_id>/tasks/<task_id>/  → partial update task (member)
    # DELETE /api/projects/<project_id>/tasks/<task_id>/  → delete task (owner only)
    path('<uuid:task_id>/', views.TaskDetailView.as_view(), name='task-detail'),
]

# ── Cross-project "my tasks" URLs ────────────────────────────────────────────
# Mounted under /api/tasks/ in config/urls.py

my_task_urlpatterns = [
    # GET /api/tasks/          → tasks assigned to current user (all projects)
    path('', views.MyTaskListView.as_view(), name='my-task-list'),

    # GET /api/tasks/stats/    → stats for tasks assigned to current user
    path('stats/', views.MyTaskStatsView.as_view(), name='my-task-stats'),
]

# Default export — used by project-scoped mount
urlpatterns = project_task_urlpatterns