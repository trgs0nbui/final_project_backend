import logging

from django.db import transaction

from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import Task
from .repositories import TaskMembershipRepository, TaskRepository

logger = logging.getLogger(__name__)


class TaskService:
    """
    Service xử lý logic nghiệp vụ liên quan đến Task.
    Mọi thao tác database được uỷ quyền cho TaskRepository và TaskMembershipRepository.
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

        task = TaskRepository.update(task, **data)
        logger.info(f"Task updated: id={task.id}, by user_id={user.id}")
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
        TaskRepository.delete(task)
        logger.info(f"Task deleted: id={task_id}, by user_id={user.id}")

    @staticmethod
    def filter_tasks(project, user, filters: dict):
        """
        Lọc danh sách Task trong project theo các tiêu chí. User phải là thành viên của project.

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
            QuerySet[Task]: Queryset đã được lọc, chưa phân trang.

        Raises:
            PermissionDenied: Nếu user không phải là thành viên của project.
        """
        if not TaskMembershipRepository.is_member(project, user):
            logger.warning(
                f"User id={user.id} attempted to filter tasks in project id={project.id} without membership"
            )
            raise PermissionDenied("Bạn không phải là thành viên của dự án này.")

        return TaskRepository.filter_by_project(project, filters)
