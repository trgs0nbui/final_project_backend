import logging
from typing import Optional

from django.db.models import QuerySet

from .models import Comment

logger = logging.getLogger(__name__)


class CommentRepository:
    """
    Đảm nhận toàn bộ thao tác database liên quan đến model Comment.
    Không chứa business logic — chỉ thực hiện CRUD và truy vấn thuần túy.
    """

    @staticmethod
    def create(task, author, content: str) -> Comment:
        """
        Tạo và lưu một Comment mới vào database.

        Args:
            task: Task instance chứa comment.
            author: User instance — tác giả của comment.
            content: Nội dung comment.

        Returns:
            Comment: Instance vừa được tạo.
        """
        comment = Comment.objects.create(task=task, author=author, content=content)
        logger.debug(
            f"CommentRepository.create: id={comment.id}, "
            f"task_id={task.id}, author_id={author.id}"
        )
        return comment

    @staticmethod
    def get_by_id(comment_id) -> Optional[Comment]:
        """
        Lấy Comment theo primary key. Trả về None nếu không tìm thấy.

        Args:
            comment_id: UUID của comment.

        Returns:
            Comment | None
        """
        try:
            return Comment.objects.select_related('author', 'task').get(id=comment_id)
        except Comment.DoesNotExist:
            return None

    @staticmethod
    def get_by_task(task) -> QuerySet:
        """
        Trả về queryset tất cả Comment của một task, sắp xếp theo thời gian tạo.

        Args:
            task: Task instance.

        Returns:
            QuerySet[Comment]
        """
        return (
            Comment.objects
            .filter(task=task)
            .select_related('author')
            .order_by('created_at')
        )

    @staticmethod
    def update(comment: Comment, content: str) -> Comment:
        """
        Cập nhật nội dung comment.

        Args:
            comment: Comment instance cần cập nhật.
            content: Nội dung mới.

        Returns:
            Comment: Instance sau khi cập nhật.
        """
        comment.content = content
        comment.save(update_fields=['content', 'updated_at'])
        logger.debug(f"CommentRepository.update: id={comment.id}")
        return comment

    @staticmethod
    def delete(comment: Comment) -> None:
        """
        Xóa Comment khỏi database.

        Args:
            comment: Comment instance cần xóa.
        """
        comment_id = comment.id
        comment.delete()
        logger.debug(f"CommentRepository.delete: id={comment_id}")
