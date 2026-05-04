from django.urls import path

from . import views

# These URLs are mounted under /api/projects/<project_id>/tasks/ in config/urls.py
# so project_id is available as a URL kwarg in all views below.

urlpatterns = [
    # GET  /api/projects/<project_id>/tasks/          → list tasks (with filter/search/pagination)
    # POST /api/projects/<project_id>/tasks/          → create task (member only)
    path('', views.TaskListCreateView.as_view(), name='task-list-create'),

    # GET    /api/projects/<project_id>/tasks/<task_id>/  → retrieve task detail (member)
    # PUT    /api/projects/<project_id>/tasks/<task_id>/  → update task (member)
    # PATCH  /api/projects/<project_id>/tasks/<task_id>/  → partial update task (member)
    # DELETE /api/projects/<project_id>/tasks/<task_id>/  → delete task (owner only)
    path('<uuid:task_id>/', views.TaskDetailView.as_view(), name='task-detail'),
]
