from django.urls import path

from . import views

# Mounted under /api/projects/<project_id>/tasks/<task_id>/comments/
urlpatterns = [
    # GET  → list comments (paginated)
    # POST → create comment
    path('', views.CommentListCreateView.as_view(), name='comment-list-create'),

    # PATCH  → update comment content (author only)
    # DELETE → delete comment (author or project owner)
    path('<uuid:comment_id>/', views.CommentDetailView.as_view(), name='comment-detail'),
]
