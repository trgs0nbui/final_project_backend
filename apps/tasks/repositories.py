import logging
from typing import Optional

from django.db.models import Q, QuerySet

from apps.projects.models import Project, ProjectMembership
from django.utils import timezone

from .models import Task

logger = logging.getLogger(__name__)


class TaskRepository:
    """
    Đảm nhận toàn bộ thao tác database liên quan đến model Task.
    Không chứa business logic — chỉ thực hiện CRUD và truy vấn thuần túy.
    """

    @staticmethod
    def create(project: Project, creator, title: str, **kwargs) -> Task:
        """
        Tạo và lưu một Task mới vào database.

        Args:
            project: Project instance chứa task.
            creator: User instance — sẽ được gán vào created_by.
            title: Tiêu đề của task.
            **kwargs: Các trường bổ sung hợp lệ: description, assignee, status, priority, due_date.

        Returns:
            Task: Instance vừa được tạo.
        """
        allowed = {'description', 'assignee', 'status', 'priority', 'due_date'}
        extra = {k: v for k, v in kwargs.items() if k in allowed}

        task = Task.objects.create(
            project=project,
            title=title,
            created_by=creator,
            **extra,
        )
        logger.debug(f"TaskRepository.create: id={task.id}, project_id={project.id}, creator_id={creator.id}")
        return task

    @staticmethod
    def get_by_id(task_id) -> Optional[Task]:
        """
        Lấy Task theo primary key. Trả về None nếu không tìm thấy.

        Args:
            task_id: UUID của task.

        Returns:
            Task | None
        """
        try:
            return Task.objects.select_related('project', 'assignee', 'created_by').get(id=task_id)
        except Task.DoesNotExist:
            return None

    @staticmethod
    def update(task: Task, **fields) -> Task:
        """
        Cập nhật các trường được chỉ định của Task và lưu vào database.
        Luôn bao gồm 'updated_at' trong update_fields.

        Args:
            task: Task instance cần cập nhật.
            **fields: Các trường và giá trị mới (title, description, assignee, status, priority, due_date).

        Returns:
            Task: Instance sau khi cập nhật.
        """
        allowed = {'title', 'description', 'assignee', 'status', 'priority', 'due_date'}
        update_fields = []

        for field, value in fields.items():
            if field in allowed:
                setattr(task, field, value)
                update_fields.append(field)

        if update_fields:
            task.save(update_fields=update_fields + ['updated_at'])
            logger.debug(f"TaskRepository.update: id={task.id}, fields={update_fields}")

        return task

    @staticmethod
    def delete(task: Task) -> None:
        """
        Xóa Task khỏi database.

        Args:
            task: Task instance cần xóa.
        """
        task_id = task.id
        task.delete()
        logger.debug(f"TaskRepository.delete: id={task_id}")

    @staticmethod
    def filter_by_project(project: Project, filters: dict) -> QuerySet:
        """
        Trả về queryset Task của project sau khi áp dụng các tiêu chí lọc.
        Tất cả tiêu chí đều tùy chọn và được kết hợp bằng AND logic.

        Args:
            project: Project instance cần lấy danh sách task.
            filters: Dict chứa các tiêu chí lọc (tất cả tùy chọn):
                - status (str): Lọc theo trạng thái chính xác.
                - assignee (str | UUID): Lọc theo assignee_id chính xác.
                - priority (str): Lọc theo mức độ ưu tiên chính xác.
                - due_date_from (date): Lọc task có due_date >= giá trị này.
                - due_date_to (date): Lọc task có due_date <= giá trị này.
                - search (str): Tìm kiếm trong title hoặc description (không phân biệt hoa thường).

        Returns:
            QuerySet[Task]: Queryset đã được lọc, chưa phân trang.
        """
        queryset = Task.objects.filter(project=project).select_related('assignee', 'created_by').order_by('-created_at')

        status = filters.get('status')
        if status is not None:
            queryset = queryset.filter(status=status)

        assignee = filters.get('assignee')
        if assignee is not None:
            queryset = queryset.filter(assignee_id=assignee)

        priority = filters.get('priority')
        if priority is not None:
            queryset = queryset.filter(priority=priority)

        due_date_from = filters.get('due_date_from')
        if due_date_from is not None:
            queryset = queryset.filter(due_date__gte=due_date_from)

        due_date_to = filters.get('due_date_to')
        if due_date_to is not None:
            queryset = queryset.filter(due_date__lte=due_date_to)

        search = filters.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(description__icontains=search)
            )

        return queryset


class MyTaskRepository:
    """
    Đảm nhận các truy vấn cross-project cho tasks được giao cho một user cụ thể.
    Tách biệt khỏi TaskRepository để rõ ràng về phạm vi truy vấn.
    """

    @staticmethod
    def get_assigned_tasks(user, filters: dict = None) -> QuerySet:
        """
        Trả về queryset Task được giao cho user trên tất cả project mà user là thành viên.

        Args:
            user: User instance.
            filters: Dict tùy chọn với các key: status, priority, search.

        Returns:
            QuerySet[Task]
        """

        member_project_ids = (
            ProjectMembership.objects
            .filter(user=user)
            .values_list('project_id', flat=True)
        )

        queryset = (
            Task.objects
            .filter(project_id__in=member_project_ids, assignee=user)
            .select_related('assignee', 'created_by', 'project')
            .order_by('-created_at')
        )

        if filters:
            task_status = filters.get('status')
            if task_status:
                queryset = queryset.filter(status=task_status)

            priority = filters.get('priority')
            if priority:
                queryset = queryset.filter(priority=priority)

            search = filters.get('search', '').strip()
            if search:
                queryset = queryset.filter(
                    Q(title__icontains=search) | Q(description__icontains=search)
                )

        logger.debug(f"MyTaskRepository.get_assigned_tasks: user_id={user.id}")
        return queryset

    @staticmethod
    def get_stats(user) -> dict:
        """
        Tính toán thống kê tasks được giao cho user trên tất cả project.

        Args:
            user: User instance.

        Returns:
            dict: {
                total_assigned, high_priority_todo, overdue, in_progress, done
            }
        """

        member_project_ids = (
            ProjectMembership.objects
            .filter(user=user)
            .values_list('project_id', flat=True)
        )

        base_qs = Task.objects.filter(
            project_id__in=member_project_ids,
            assignee=user,
        )

        today = timezone.now().date()

        stats = {
            'total_assigned': base_qs.count(),
            'high_priority_todo': base_qs.filter(priority='high').exclude(status='done').count(),
            'overdue': base_qs.filter(due_date__lt=today).exclude(status='done').count(),
            'in_progress': base_qs.filter(status='in_progress').count(),
            'done': base_qs.filter(status='done').count(),
        }

        logger.debug(f"MyTaskRepository.get_stats: user_id={user.id}, stats={stats}")
        return stats


class TaskMembershipRepository:
    """
    Đảm nhận các truy vấn kiểm tra membership liên quan đến Task.
    Tách biệt khỏi ProjectMembershipRepository để TaskService không phụ thuộc trực tiếp
    vào app projects ở tầng repository.
    """

    @staticmethod
    def is_member(project: Project, user) -> bool:
        """
        Kiểm tra user có phải là thành viên của project hay không.

        Args:
            project: Project instance.
            user: User instance.

        Returns:
            bool: True nếu user là thành viên, False nếu không.
        """
        return ProjectMembership.objects.filter(project=project, user=user).exists()

    @staticmethod
    def is_member_by_id(project: Project, user_id) -> bool:
        """
        Kiểm tra user_id có phải là thành viên của project hay không.

        Args:
            project: Project instance.
            user_id: UUID của user.

        Returns:
            bool
        """
        return ProjectMembership.objects.filter(project=project, user_id=user_id).exists()
