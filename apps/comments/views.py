import logging

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import NotFound

from apps.common.pagination import CustomPageNumberPagination
from apps.projects.repositories import ProjectRepository, ProjectMembershipRepository
from apps.tasks.repositories import TaskRepository
from .repositories import CommentRepository
from .serializers import CommentSerializer
from .services import CommentService

logger = logging.getLogger(__name__)


def get_project_or_404(project_id, user):
    """Lấy project và kiểm tra membership. Trả về 404 nếu không hợp lệ."""
    project = ProjectRepository.get_by_id(project_id)
    if project is None or not ProjectMembershipRepository.is_member(project, user):
        raise NotFound("Dự án không tồn tại hoặc bạn không có quyền truy cập.")
    return project


def get_task_or_404(task_id, project):
    """Lấy task trong phạm vi project. Trả về 404 nếu không tồn tại."""
    task = TaskRepository.get_by_id(task_id)
    if task is None or str(task.project_id) != str(project.id):
        raise NotFound("Công việc không tồn tại.")
    return task


def get_comment_or_404(comment_id, task):
    """Lấy comment trong phạm vi task. Trả về 404 nếu không tồn tại."""
    comment = CommentRepository.get_by_id(comment_id)
    if comment is None or str(comment.task_id) != str(task.id):
        raise NotFound("Bình luận không tồn tại.")
    return comment


class CommentListCreateView(APIView):
    """
    GET  /api/projects/<project_id>/tasks/<task_id>/comments/
         — Danh sách comment của task (phân trang, thành viên).

    POST /api/projects/<project_id>/tasks/<task_id>/comments/
         — Tạo comment mới (thành viên).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, project_id, task_id):
        """Trả về danh sách comment của task."""
        project = get_project_or_404(project_id, request.user)
        task = get_task_or_404(task_id, project)

        comments = CommentRepository.get_by_task(task)

        paginator = CustomPageNumberPagination()
        page = paginator.paginate_queryset(comments, request)
        serializer = CommentSerializer(page, many=True)

        logger.debug(
            f"CommentListCreateView.get: task_id={task_id}, user_id={request.user.id}"
        )
        return paginator.get_paginated_response(serializer.data)

    def post(self, request, project_id, task_id):
        """Tạo comment mới. User phải là thành viên của project."""
        project = get_project_or_404(project_id, request.user)
        task = get_task_or_404(task_id, project)

        serializer = CommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        comment = CommentService.create_comment(
            task=task,
            author=request.user,
            content=serializer.validated_data['content'],
        )

        logger.info(
            f"CommentListCreateView.post: created comment_id={comment.id}, "
            f"task_id={task_id}, user_id={request.user.id}"
        )
        return Response(CommentSerializer(comment).data, status=status.HTTP_201_CREATED)


class CommentDetailView(APIView):
    """
    PATCH  /api/projects/<project_id>/tasks/<task_id>/comments/<comment_id>/
           — Cập nhật nội dung comment (chỉ tác giả).

    DELETE /api/projects/<project_id>/tasks/<task_id>/comments/<comment_id>/
           — Xóa comment (tác giả hoặc project owner).
    """

    permission_classes = [IsAuthenticated]

    def patch(self, request, project_id, task_id, comment_id):
        """Cập nhật nội dung comment. Chỉ tác giả mới có quyền."""
        project = get_project_or_404(project_id, request.user)
        task = get_task_or_404(task_id, project)
        comment = get_comment_or_404(comment_id, task)

        serializer = CommentSerializer(comment, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        updated = CommentService.update_comment(
            comment=comment,
            user=request.user,
            content=serializer.validated_data['content'],
        )

        logger.info(
            f"CommentDetailView.patch: comment_id={comment_id}, user_id={request.user.id}"
        )
        return Response(CommentSerializer(updated).data, status=status.HTTP_200_OK)

    def delete(self, request, project_id, task_id, comment_id):
        """Xóa comment. Tác giả hoặc project owner có quyền."""
        project = get_project_or_404(project_id, request.user)
        task = get_task_or_404(task_id, project)
        comment = get_comment_or_404(comment_id, task)

        CommentService.delete_comment(comment=comment, user=request.user)

        logger.info(
            f"CommentDetailView.delete: comment_id={comment_id}, user_id={request.user.id}"
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
