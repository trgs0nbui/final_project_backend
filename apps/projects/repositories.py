import logging
from typing import Optional

from django.contrib.auth import get_user_model
from django.db.models import Count, QuerySet

from .enums import ProjectRole
from .models import Project, ProjectMembership

logger = logging.getLogger(__name__)

User = get_user_model()


class ProjectRepository:
    """
    Đảm nhận toàn bộ thao tác database liên quan đến model Project.
    Không chứa business logic — chỉ thực hiện CRUD và truy vấn thuần túy.
    """

    @staticmethod
    def create(owner, name: str, description: str = '', **kwargs) -> Project:
        """
        Tạo và lưu một Project mới vào database.

        Args:
            owner: User instance — chủ sở hữu project.
            name: Tên project.
            description: Mô tả project (tùy chọn).
            **kwargs: Các trường bổ sung hợp lệ: key, project_type, category.

        Returns:
            Project: Instance vừa được tạo.
        """
        allowed = {'key', 'project_type', 'category'}
        extra = {k: v for k, v in kwargs.items() if k in allowed}

        project = Project.objects.create(
            owner=owner,
            name=name,
            description=description,
            **extra,
        )
        logger.debug(f"ProjectRepository.create: id={project.id}, owner_id={owner.id}")
        return project

    @staticmethod
    def get_by_id(project_id) -> Optional[Project]:
        """
        Lấy Project theo primary key. Trả về None nếu không tìm thấy.

        Args:
            project_id: UUID của project.

        Returns:
            Project | None
        """
        try:
            return Project.objects.select_related('owner').get(id=project_id)
        except Project.DoesNotExist:
            return None

    @staticmethod
    def get_projects_for_user(user) -> QuerySet:
        """
        Trả về queryset các Project mà user là thành viên (owner hoặc member).
        Annotate thêm task_count — số lượng task thuộc mỗi project.
        Sử dụng select_related để tránh N+1 khi truy cập project.owner.

        Args:
            user: User instance.

        Returns:
            QuerySet[Project]
        """
        return (
            Project.objects
            .filter(memberships__user=user)
            .select_related('owner')
            .annotate(task_count=Count('tasks', distinct=True))
            .distinct()
            .order_by('-created_at')
        )

    @staticmethod
    def update(project: Project, **fields) -> Project:
        """
        Cập nhật các trường được chỉ định của Project và lưu vào database.
        Luôn bao gồm 'updated_at' trong update_fields.

        Args:
            project: Project instance cần cập nhật.
            **fields: Các trường và giá trị mới (name, description, key, project_type, category).

        Returns:
            Project: Instance sau khi cập nhật.
        """
        allowed = {'name', 'description', 'key', 'project_type', 'category'}
        update_fields = []

        for field, value in fields.items():
            if field in allowed:
                setattr(project, field, value)
                update_fields.append(field)

        if update_fields:
            project.save(update_fields=update_fields + ['updated_at'])
            logger.debug(f"ProjectRepository.update: id={project.id}, fields={update_fields}")

        return project

    @staticmethod
    def delete(project: Project) -> None:
        """
        Xóa Project khỏi database. Task liên quan bị xóa theo CASCADE.

        Args:
            project: Project instance cần xóa.
        """
        project_id = project.id
        project.delete()
        logger.debug(f"ProjectRepository.delete: id={project_id}")


class ProjectMembershipRepository:
    """
    Đảm nhận toàn bộ thao tác database liên quan đến model ProjectMembership.
    Không chứa business logic — chỉ thực hiện CRUD và truy vấn thuần túy.
    """

    @staticmethod
    def create(project: Project, user, role: ProjectRole) -> ProjectMembership:
        """
        Tạo và lưu một ProjectMembership mới vào database.

        Args:
            project: Project instance.
            user: User instance.
            role: ProjectRole enum value (OWNER hoặc MEMBER).

        Returns:
            ProjectMembership: Instance vừa được tạo.
        """
        membership = ProjectMembership.objects.create(
            project=project,
            user=user,
            role=role,
        )
        logger.debug(
            f"ProjectMembershipRepository.create: project_id={project.id}, "
            f"user_id={user.id}, role={role}"
        )
        return membership

    @staticmethod
    def get_membership(project: Project, user) -> Optional[ProjectMembership]:
        """
        Lấy membership của một user trong project. Trả về None nếu không tồn tại.

        Args:
            project: Project instance.
            user: User instance.

        Returns:
            ProjectMembership | None
        """
        try:
            return ProjectMembership.objects.select_related('user').get(
                project=project, user=user
            )
        except ProjectMembership.DoesNotExist:
            return None

    @staticmethod
    def get_membership_by_user_id(project: Project, user_id) -> Optional[ProjectMembership]:
        """
        Lấy membership theo user_id trong project. Trả về None nếu không tồn tại.

        Args:
            project: Project instance.
            user_id: UUID của user.

        Returns:
            ProjectMembership | None
        """
        try:
            return ProjectMembership.objects.select_related('user').get(
                project=project, user_id=user_id
            )
        except ProjectMembership.DoesNotExist:
            return None

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
    def membership_exists_for_user_id(project: Project, user_id) -> bool:
        """
        Kiểm tra user_id có phải là thành viên của project hay không.

        Args:
            project: Project instance.
            user_id: UUID của user.

        Returns:
            bool
        """
        return ProjectMembership.objects.filter(project=project, user_id=user_id).exists()

    @staticmethod
    def list_members(project: Project) -> QuerySet:
        """
        Trả về queryset tất cả ProjectMembership của project.
        Sử dụng select_related để tránh N+1 khi truy cập membership.user.

        Args:
            project: Project instance.

        Returns:
            QuerySet[ProjectMembership]
        """
        return (
            ProjectMembership.objects
            .filter(project=project)
            .select_related('user')
            .order_by('joined_at')
        )

    @staticmethod
    def delete(membership: ProjectMembership) -> None:
        """
        Xóa một ProjectMembership khỏi database.

        Args:
            membership: ProjectMembership instance cần xóa.
        """
        membership_id = membership.id
        membership.delete()
        logger.debug(f"ProjectMembershipRepository.delete: id={membership_id}")

    @staticmethod
    def count_members_in_projects(project_ids) -> int:
        """
        Đếm tổng số membership trong danh sách project_ids.

        Args:
            project_ids: Iterable các UUID project.

        Returns:
            int: Tổng số membership.
        """
        return ProjectMembership.objects.filter(project_id__in=project_ids).count()


class ProjectOwnerRepository:
    """
    Đảm nhận các truy vấn liên quan đến quyền sở hữu project.
    Tách biệt để view/service không truy cập model trực tiếp.
    """

    @staticmethod
    def get_owned_project_ids(user) -> list:
        """
        Trả về danh sách UUID (dạng str) của các project mà user là owner.

        Args:
            user: User instance.

        Returns:
            list[str]: Danh sách project id.
        """
        ids = list(
            Project.objects
            .filter(owner=user)
            .values_list('id', flat=True)
        )
        logger.debug(f"ProjectOwnerRepository.get_owned_project_ids: user_id={user.id}, count={len(ids)}")
        return [str(pid) for pid in ids]
