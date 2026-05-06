from django.contrib import admin
from .models import Comment


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('id', 'task', 'author', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('content', 'author__username', 'task__title')
    readonly_fields = ('id', 'created_at', 'updated_at')
