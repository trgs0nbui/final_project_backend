import logging

from django.db import transaction

from rest_framework.exceptions import PermissionDenied

from apps.projects.models import ProjectMembership
from .models import Comment
from .repositories import CommentRepository

logger = logging.getLogger(__name__)


def _is_project_member(project, user) -> bool:
    """Kiểm tra user có phải là thành viên của project không."""
    return ProjectMembership.objects.filter(project=project, user=user).exists()


class CommentService:
    """
    Service xử lý logic nghiệp vụ liên quan đến Comment.
    """

    @staticmethod
    @transaction.atomic
    def create_comment(task, author, content: str) -> Comment:
        """
        Tạo comment mới trên task. Author phải là thành viên của project.

        Args:
            task: Task instance.
            author: User instance — tác giả.
            content: Nội dung comment.

        Returns:
            Comment: Instance vừa được tạo.

        Raises:
            PermissionDenied: Nếu author không phải thành viên của project.
        """
        if not _is_project_member(task.project, author):
            logger.warning(
                f"User id={author.id} attempted to comment on task id={task.id} "
                f"without project membership"
            )
            raise PermissionDenied("Bạn không phải là thành viên của dự án này.")

        comment = CommentRepository.create(task=task, author=author, content=content)
        logger.info(
            f"Comment created: id={comment.id}, task_id={task.id}, author_id={author.id}"
        )
        return comment

    @staticmethod
    @transaction.atomic
    def update_comment(comment: Comment, user, content: str) -> Comment:
        """
        Cập nhật nội dung comment. Chỉ tác giả mới có quyền chỉnh sửa.

        Args:
            comment: Comment instance cần cập nhật.
            user: User instance thực hiện thao tác.
            content: Nội dung mới.

        Returns:
            Comment: Instance sau khi cập nhật.

        Raises:
            PermissionDenied: Nếu user không phải tác giả của comment.
        """
        if comment.author_id != user.id:
            logger.warning(
                f"User id={user.id} attempted to edit comment id={comment.id} "
                f"owned by user id={comment.author_id}"
            )
            raise PermissionDenied("Bạn không có quyền chỉnh sửa bình luận này.")

        comment = CommentRepository.update(comment, content=content)
        logger.info(f"Comment updated: id={comment.id}, by user_id={user.id}")
        return comment

    @staticmethod
    @transaction.atomic
    def delete_comment(comment: Comment, user) -> None:
        """
        Xóa comment. Tác giả hoặc owner của project đều có quyền xóa.

        Args:
            comment: Comment instance cần xóa.
            user: User instance thực hiện thao tác.

        Raises:
            PermissionDenied: Nếu user không phải tác giả hoặc project owner.
        """
        is_author = comment.author_id == user.id
        is_project_owner = comment.task.project.owner_id == user.id

        if not is_author and not is_project_owner:
            logger.warning(
                f"User id={user.id} attempted to delete comment id={comment.id} "
                f"without permission"
            )
            raise PermissionDenied("Bạn không có quyền xóa bình luận này.")

        comment_id = comment.id
        CommentRepository.delete(comment)
        logger.info(f"Comment deleted: id={comment_id}, by user_id={user.id}")
