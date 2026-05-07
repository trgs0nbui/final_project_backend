import hashlib
import json
import logging

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import Task
from .repositories import TaskMembershipRepository, TaskRepository,  MyTaskRepository
from .tasks import invalidate_project_tasks_cache


logger = logging.getLogger(__name__)

# Thời gian sống mặc định của cache (giây)
_CACHE_TTL = getattr(settings, 'CACHE_TTL', 300)
# Prefix version để tránh conflict khi thay đổi format cache
_CACHE_VERSION = "v2"


def _safe_enqueue(task_func, *args, **kwargs):
    """
    Enqueue Celery task an toàn.
    Nếu broker không khả dụng, log lỗi và tiếp tục — không crash request.
    """
    try:
        task_func.delay(*args, **kwargs)
    except Exception as e:
        logger.error(f"Failed to enqueue task {task_func.__name__}: {e}")


def _make_filters_hash(filters: dict) -> str:
    """
    Tạo MD5 hash từ filters dict đã sắp xếp theo key.
    Đảm bảo cùng filters luôn cho cùng hash (deterministic).
    """
    sorted_json = json.dumps(filters, sort_keys=True, default=str)
    return hashlib.md5(sorted_json.encode()).hexdigest()


class TaskService:
    """
    Service xử lý logic nghiệp vụ liên quan đến Task.
    Mọi thao tác database được uỷ quyền cho TaskRepository và TaskMembershipRepository.
    Cache layer được nhúng vào filter_tasks để giảm tải DB.
    """

    @staticmethod
    @transaction.atomic
    def create_task(project, creator, title: str, **kwargs) -> Task:
        """
        Tạo một Task mới trong project. Creator phải là thành viên của project.

        Args:
            project: Project instance chứa task.
            creator: User instance tạo task — sẽ được gán vào created_by.
            title: Tiêu đề của task.
            **kwargs: Các trường bổ sung: description, assignee, status, priority, due_date.

        Returns:
            Task: Instance task vừa được tạo.

        Raises:
            PermissionDenied: Nếu creator không phải là thành viên của project.
            ValidationError: Nếu assignee được cung cấp nhưng không phải thành viên của project.
        """
        if not TaskMembershipRepository.is_member(project, creator):
            logger.warning(
                f"User id={creator.id} attempted to create task in project id={project.id} without membership"
            )
            raise PermissionDenied("Bạn không phải là thành viên của dự án này.")

        assignee = kwargs.get('assignee')
        if assignee is not None and not TaskMembershipRepository.is_member_by_id(project, assignee.id):
            raise ValidationError("Người được giao việc không phải là thành viên của dự án này.")

        task = TaskRepository.create(project=project, creator=creator, title=title, **kwargs)
        logger.info(
            f"Task created: id={task.id}, title='{task.title}', "
            f"project_id={project.id}, creator_id={creator.id}"
        )

        # Invalidate cache danh sách task của project
        _safe_enqueue(invalidate_project_tasks_cache, str(project.id))

        return task

    @staticmethod
    @transaction.atomic
    def update_task(task: Task, user, **data) -> Task:
        """
        Cập nhật thông tin Task. User phải là thành viên của project chứa task.

        Args:
            task: Task instance cần cập nhật.
            user: User instance thực hiện thao tác.
            **data: Các trường cần cập nhật: title, description, assignee, status, priority, due_date.

        Returns:
            Task: Instance task sau khi cập nhật.

        Raises:
            PermissionDenied: Nếu user không phải là thành viên của project.
            ValidationError: Nếu assignee được cung cấp nhưng không phải thành viên của project.
        """
        if not TaskMembershipRepository.is_member(task.project, user):
            logger.warning(
                f"User id={user.id} attempted to update task id={task.id} without membership"
            )
            raise PermissionDenied("Bạn không phải là thành viên của dự án này.")

        assignee = data.get('assignee')
        if 'assignee' in data and assignee is not None:
            if not TaskMembershipRepository.is_member_by_id(task.project, assignee.id):
                raise ValidationError("Người được giao việc không phải là thành viên của dự án này.")

        project_id = str(task.project_id)
        task = TaskRepository.update(task, **data)
        logger.info(f"Task updated: id={task.id}, by user_id={user.id}")

        # Invalidate cache danh sách task của project
        _safe_enqueue(invalidate_project_tasks_cache, project_id)

        return task

    @staticmethod
    @transaction.atomic
    def delete_task(task: Task, user) -> None:
        """
        Xóa Task. Chỉ Owner của project mới có quyền thực hiện.

        Args:
            task: Task instance cần xóa.
            user: User instance thực hiện thao tác.

        Raises:
            PermissionDenied: Nếu user không phải là owner của project chứa task.
        """
        if task.project.owner_id != user.id:
            logger.warning(
                f"User id={user.id} attempted to delete task id={task.id} without owner permission"
            )
            raise PermissionDenied("Bạn không có quyền xóa công việc này.")

        task_id = task.id
        project_id = str(task.project_id)

        TaskRepository.delete(task)
        logger.info(f"Task deleted: id={task_id}, by user_id={user.id}")

        # Invalidate cache danh sách task của project
        _safe_enqueue(invalidate_project_tasks_cache, project_id)

    @staticmethod
    def filter_tasks(project, user, filters: dict):
        """
        Lọc danh sách Task trong project theo các tiêu chí. User phải là thành viên của project.
        Kết quả được cache trong Redis với key project_tasks:{project_id}:{filters_hash}.

        Args:
            project: Project instance cần lấy danh sách task.
            user: User instance thực hiện thao tác.
            filters: Dict chứa các tiêu chí lọc (tất cả tùy chọn):
                - status (str): Lọc theo trạng thái chính xác.
                - assignee (str | UUID): Lọc theo assignee_id chính xác.
                - priority (str): Lọc theo mức độ ưu tiên chính xác.
                - due_date_from (date): Lọc task có due_date >= giá trị này.
                - due_date_to (date): Lọc task có due_date <= giá trị này.
                - search (str): Tìm kiếm trong title hoặc description (không phân biệt hoa thường).

        Returns:
            QuerySet[Task] hoặc list (từ cache): Queryset đã được lọc, chưa phân trang.

        Raises:
            PermissionDenied: Nếu user không phải là thành viên của project.
        """
        # Permission check TRƯỚC cache — không cache kết quả của PermissionDenied
        if not TaskMembershipRepository.is_member(project, user):
            logger.warning(
                f"User id={user.id} attempted to filter tasks in project id={project.id} without membership"
            )
            raise PermissionDenied("Bạn không phải là thành viên của dự án này.")

        filters_hash = _make_filters_hash(filters)
        cache_key = f"{_CACHE_VERSION}:project_tasks:{project.id}:{filters_hash}"

        try:
            cached_ids = cache.get(cache_key)
            if cached_ids is not None:
                logger.debug(f"Cache hit: key={cache_key}, method=filter_tasks")
                # Trả về QuerySet lọc theo IDs đã cache — giữ nguyên interface
                return (
                    Task.objects
                    .filter(id__in=cached_ids)
                    .select_related('assignee', 'created_by')
                    .order_by('-created_at')
                )

            logger.debug(f"Cache miss: key={cache_key}, method=filter_tasks")
            queryset = TaskRepository.filter_by_project(project, filters)

            # Chỉ cache danh sách IDs
            task_ids = list(queryset.values_list('id', flat=True))
            cache.set(cache_key, [str(tid) for tid in task_ids], _CACHE_TTL)
            return queryset

        except Exception as e:
            logger.error(f"Redis error in filter_tasks (key={cache_key}): {e}")
            return TaskRepository.filter_by_project(project, filters)

    @staticmethod
    def get_my_tasks(user, filters: dict = None):
        """
        Trả về queryset Task được giao cho user trên tất cả project.
        Uỷ quyền truy vấn DB cho MyTaskRepository.

        Args:
            user: User instance.
            filters: Dict tùy chọn với các key: status, priority, search.

        Returns:
            QuerySet[Task]
        """
        queryset = MyTaskRepository.get_assigned_tasks(user, filters or {})
        logger.debug(f"TaskService.get_my_tasks: user_id={user.id}, filters={filters}")
        return queryset

    @staticmethod
    def get_my_task_stats(user) -> dict:
        """
        Trả về thống kê tasks được giao cho user trên tất cả project.
        Uỷ quyền tính toán cho MyTaskRepository.

        Args:
            user: User instance.

        Returns:
            dict: { total_assigned, high_priority_todo, overdue, in_progress, done }
        """
        stats = MyTaskRepository.get_stats(user)
        logger.debug(f"TaskService.get_my_task_stats: user_id={user.id}, stats={stats}")
        return stats
