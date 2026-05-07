from django.urls import path

from . import views

urlpatterns = [
    # Project CRUD
    # GET  /api/projects/          → list projects (user is member)
    # POST /api/projects/          → create project
    path('', views.ProjectListCreateView.as_view(), name='project-list-create'),

    # GET    /api/projects/<id>/   → retrieve project detail
    # PATCH  /api/projects/<id>/   → update project (owner only)
    # PUT    /api/projects/<id>/   → update project (owner only)
    # DELETE /api/projects/<id>/   → delete project (owner only)
    path('<uuid:pk>/', views.ProjectDetailView.as_view(), name='project-detail'),

    # Project membership
    # GET  /api/projects/<id>/members/          → list members
    # POST /api/projects/<id>/members/          → add member (owner only)
    path('<uuid:pk>/members/', views.ProjectMemberListCreateView.as_view(), name='project-member-list-create'),

    # DELETE /api/projects/<id>/members/<user_id>/  → remove member (owner only)
    path('<uuid:pk>/members/<uuid:user_id>/', views.ProjectMemberDestroyView.as_view(), name='project-member-destroy'),

    # GET /api/projects/<id>/members/search/?q=  → search users to add (owner only)
    path('<uuid:pk>/members/search/', views.ProjectMemberSearchView.as_view(), name='project-member-search'),

    # GET /api/projects/member-stats/  → total members in owned projects
    path('member-stats/', views.ProjectMemberStatsView.as_view(), name='project-member-stats'),
]
