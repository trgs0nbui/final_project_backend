import uuid

from django.conf import settings
from django.db import models


class Comment(models.Model):
    """
    Represents a comment on a task.

    Permissions:
        - Any project member can view and create comments.
        - Only the comment author or the project owner can edit/delete a comment.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    task = models.ForeignKey(
        'tasks.Task',
        on_delete=models.CASCADE,
        related_name='comments',
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='task_comments',
    )
    content = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'task_comments'
        verbose_name = 'Comment'
        verbose_name_plural = 'Comments'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['task'], name='comment_task_idx'),
            models.Index(fields=['author'], name='comment_author_idx'),
            models.Index(fields=['task', 'created_at'], name='comment_task_created_idx'),
        ]

    def __str__(self):
        return f'Comment by {self.author} on task {self.task_id}'
