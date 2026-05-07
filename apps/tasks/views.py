import logging

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import NotFound, ValidationError

from django.contrib.auth import get_user_model

from apps.common.pagination import CustomPageNumberPagination
from apps.projects.repositories import ProjectRepository, ProjectMembershipRepository
from .models import Task
from .repositories import TaskRepository
from .services import TaskService
from .serializers import TaskFilterSerializer, TaskSerializer

logger = logging.getLogger(__name__)


def get_project_or_404(project_id, user):
    """
    Lấy project theo project_id. Trả về 404 nếu không tồn tại hoặc user không phải thành viên.

    Args:
        project_id: UUID của project.
        user: User instance đang thực hiện request.

    Returns:
        Project: Instance project tìm được.

    Raises:
        NotFound: Nếu project không tồn tại hoặc user không phải thành viên.
    """
    project = ProjectRepository.get_by_id(project_id)
    if project is None or not ProjectMembershipRepository.is_member(project, user):
        raise NotFound("Dự án không tồn tại hoặc bạn không có quyền truy cập.")
    return project


def get_task_or_404(task_id, project):
    """
    Lấy task theo task_id trong phạm vi project. Trả về 404 nếu không tồn tại.

    Args:
        task_id: UUID của task.
        project: Project instance chứa task.

    Returns:
        Task: Instance task tìm được.

    Raises:
        NotFound: Nếu task không tồn tại hoặc không thuộc project.
    """
    task = TaskRepository.get_by_id(task_id)
    if task is None or str(task.project_id) != str(project.id):
        raise NotFound("Công việc không tồn tại.")
    return task


class TaskListCreateView(APIView):
    """
    GET  /api/projects/<project_id>/tasks/  — Danh sách task với filter/search/pagination.
    POST /api/projects/<project_id>/tasks/  — Tạo task mới (thành viên).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, project_id):
        """
        Trả về danh sách task của project với filter và phân trang.
        Validate tham số filter; trả về 400 nếu không hợp lệ.
        """
        project = get_project_or_404(project_id, request.user)

        # Validate filter params
        filter_serializer = TaskFilterSerializer(data=request.query_params)
        if not filter_serializer.is_valid():
            return Response(filter_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        filters = filter_serializer.validated_data
        tasks = TaskService.filter_tasks(project, request.user, filters)

        paginator = CustomPageNumberPagination()
        page = paginator.paginate_queryset(tasks, request)
        serializer = TaskSerializer(page, many=True)

        logger.debug(
            f"TaskListCreateView.get: project_id={project_id}, "
            f"user_id={request.user.id}, filters={filters}"
        )
        return paginator.get_paginated_response(serializer.data)

    def post(self, request, project_id):
        """
        Tạo task mới trong project. User phải là thành viên của project.
        """
        project = get_project_or_404(project_id, request.user)

        serializer = TaskSerializer(data=request.data, context={'project': project})
        serializer.is_valid(raise_exception=True)

        validated = serializer.validated_data

        # Resolve assignee từ assignee_id nếu có
        assignee = None
        assignee_id = validated.pop('assignee_id', None)
        if assignee_id is not None:
            User = get_user_model()
            try:
                assignee = User.objects.get(id=assignee_id)
            except User.DoesNotExist:
                return Response(
                    {'assignee_id': ['Người dùng không tồn tại.']},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        task = TaskService.create_task(
            project=project,
            creator=request.user,
            title=validated['title'],
            description=validated.get('description', ''),
            assignee=assignee,
            status=validated.get('status', 'todo'),
            priority=validated.get('priority', 'medium'),
            due_date=validated.get('due_date'),
        )

        logger.info(
            f"TaskListCreateView.post: created task_id={task.id}, "
            f"project_id={project_id}, user_id={request.user.id}"
        )
        return Response(TaskSerializer(task).data, status=status.HTTP_201_CREATED)


class TaskDetailView(APIView):
    """
    GET    /api/projects/<project_id>/tasks/<task_id>/  — Chi tiết task (thành viên).
    PUT    /api/projects/<project_id>/tasks/<task_id>/  — Cập nhật toàn bộ task (thành viên).
    PATCH  /api/projects/<project_id>/tasks/<task_id>/  — Cập nhật một phần task (thành viên).
    DELETE /api/projects/<project_id>/tasks/<task_id>/  — Xóa task (owner only).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, project_id, task_id):
        """Trả về thông tin chi tiết của task nếu user là thành viên của project."""
        project = get_project_or_404(project_id, request.user)
        task = get_task_or_404(task_id, project)

        logger.debug(
            f"TaskDetailView.get: task_id={task_id}, "
            f"project_id={project_id}, user_id={request.user.id}"
        )
        return Response(TaskSerializer(task).data, status=status.HTTP_200_OK)

    def put(self, request, project_id, task_id):
        """Cập nhật toàn bộ task. User phải là thành viên của project."""
        project = get_project_or_404(project_id, request.user)
        task = get_task_or_404(task_id, project)

        serializer = TaskSerializer(task, data=request.data, context={'project': project})
        serializer.is_valid(raise_exception=True)

        validated = serializer.validated_data
        update_data = self._resolve_assignee(validated)

        updated = TaskService.update_task(task, request.user, **update_data)

        logger.info(
            f"TaskDetailView.put: task_id={task_id}, "
            f"project_id={project_id}, user_id={request.user.id}"
        )
        return Response(TaskSerializer(updated).data, status=status.HTTP_200_OK)

    def patch(self, request, project_id, task_id):
        """Cập nhật một phần task. User phải là thành viên của project."""
        project = get_project_or_404(project_id, request.user)
        task = get_task_or_404(task_id, project)

        serializer = TaskSerializer(task, data=request.data, partial=True, context={'project': project})
        serializer.is_valid(raise_exception=True)

        validated = serializer.validated_data
        update_data = self._resolve_assignee(validated)

        updated = TaskService.update_task(task, request.user, **update_data)

        logger.info(
            f"TaskDetailView.patch: task_id={task_id}, "
            f"project_id={project_id}, user_id={request.user.id}"
        )
        return Response(TaskSerializer(updated).data, status=status.HTTP_200_OK)

    def delete(self, request, project_id, task_id):
        """
        Xóa task. Chỉ Owner của project mới có quyền thực hiện.
        Member nhận 403; non-member nhận 404.
        """
        project = get_project_or_404(project_id, request.user)
        task = get_task_or_404(task_id, project)

        TaskService.delete_task(task, request.user)

        logger.info(
            f"TaskDetailView.delete: task_id={task_id}, "
            f"project_id={project_id}, user_id={request.user.id}"
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @staticmethod
    def _resolve_assignee(validated: dict) -> dict:
        """
        Chuyển đổi assignee_id thành assignee instance trong validated data.
        Trả về dict đã được xử lý để truyền vào TaskService.update_task.
        """
        data = dict(validated)
        assignee_id = data.pop('assignee_id', ...)  # sentinel để phân biệt "không có" vs None

        if assignee_id is ...:
            # assignee_id không có trong request (partial update) — không thay đổi assignee
            return data

        if assignee_id is None:
            data['assignee'] = None
            return data

        User = get_user_model()
        try:
            data['assignee'] = User.objects.get(id=assignee_id)
        except User.DoesNotExist:
            raise ValidationError({'assignee_id': 'Người dùng không tồn tại.'})

        return data


class MyTaskListView(APIView):
    """
    GET /api/tasks/  — Danh sách task được giao cho user hiện tại,
    across tất cả projects mà user là thành viên.

    Query params (tùy chọn):
        status   — lọc theo trạng thái (todo | in_progress | done)
        priority — lọc theo độ ưu tiên (low | medium | high)
        search   — tìm kiếm theo title hoặc description
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        filters = {
            'status': request.query_params.get('status', ''),
            'priority': request.query_params.get('priority', ''),
            'search': request.query_params.get('search', ''),
        }
        # Loại bỏ key có giá trị rỗng để repository không lọc thừa
        filters = {k: v for k, v in filters.items() if v}

        queryset = TaskService.get_my_tasks(request.user, filters)

        paginator = CustomPageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = TaskSerializer(page, many=True)

        logger.debug(
            f"MyTaskListView.get: user_id={request.user.id}, filters={filters}"
        )
        return paginator.get_paginated_response(serializer.data)


class MyTaskStatsView(APIView):
    """
    GET /api/tasks/stats/  — Thống kê tasks được giao cho user hiện tại.

    Returns:
        {
            "total_assigned": int,       — tổng tasks được giao
            "high_priority_todo": int,   — tasks high priority chưa done
            "overdue": int,              — tasks quá hạn chưa done
            "in_progress": int,          — tasks đang thực hiện
            "done": int,                 — tasks đã hoàn thành
        }
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        stats = TaskService.get_my_task_stats(request.user)
        logger.debug(f"MyTaskStatsView.get: user_id={request.user.id}, stats={stats}")
        return Response(stats, status=status.HTTP_200_OK)
