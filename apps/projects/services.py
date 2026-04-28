import logging

from django.contrib.auth import get_user_model
from django.db import transaction

from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from .enums import ProjectRole
from .models import Project, ProjectMembership
from .repositories import ProjectMembershipRepository, ProjectRepository

logger = logging.getLogger(__name__)

User = get_user_model()


class ProjectService:
    """
    Service xử lý logic nghiệp vụ liên quan đến Project và ProjectMembership.
    Mọi thao tác database được uỷ quyền cho ProjectRepository và ProjectMembershipRepository.
    """

    @staticmethod
    @transaction.atomic
    def create_project(owner, name: str, description: str = '', **kwargs) -> Project:
        """
        Tạo một Project mới và tự động thêm owner vào ProjectMembership với role=owner.

        Args:
            owner: User instance — chủ sở hữu của project.
            name: Tên của project.
            description: Mô tả project (tùy chọn).
            **kwargs: Các trường bổ sung: key (str), project_type (str), category (str).

        Returns:
            Project: Instance project vừa được tạo.
        """
        project = ProjectRepository.create(
            owner=owner,
            name=name,
            description=description,
            **kwargs,
        )
        ProjectMembershipRepository.create(project=project, user=owner, role=ProjectRole.OWNER)

        logger.info(f"Project created: id={project.id}, name='{project.name}', owner_id={owner.id}")
        return project

    @staticmethod
    def get_user_projects(user):
        """
        Trả về queryset các Project mà user là thành viên (Owner hoặc Member).

        Args:
            user: User instance cần lấy danh sách project.

        Returns:
            QuerySet[Project]
        """
        return ProjectRepository.get_projects_for_user(user)

    @staticmethod
    @transaction.atomic
    def update_project(project: Project, user, **data) -> Project:
        """
        Cập nhật thông tin Project. Chỉ Owner mới có quyền thực hiện.

        Args:
            project: Project instance cần cập nhật.
            user: User instance thực hiện thao tác.
            **data: Các trường cần cập nhật (name, description).

        Returns:
            Project: Instance project sau khi cập nhật.

        Raises:
            PermissionDenied: Nếu user không phải là owner của project.
        """
        if project.owner_id != user.id:
            logger.warning(
                f"User id={user.id} attempted to update project id={project.id} without owner permission"
            )
            raise PermissionDenied("Bạn không có quyền cập nhật dự án này.")

        project = ProjectRepository.update(project, **data)
        logger.info(f"Project updated: id={project.id}, by user_id={user.id}")
        return project

    @staticmethod
    @transaction.atomic
    def delete_project(project: Project, user) -> None:
        """
        Xóa Project cùng toàn bộ Task liên quan (CASCADE). Chỉ Owner mới có quyền thực hiện.

        Args:
            project: Project instance cần xóa.
            user: User instance thực hiện thao tác.

        Raises:
            PermissionDenied: Nếu user không phải là owner của project.
        """
        if project.owner_id != user.id:
            logger.warning(
                f"User id={user.id} attempted to delete project id={project.id} without owner permission"
            )
            raise PermissionDenied("Bạn không có quyền xóa dự án này.")

        project_id = project.id
        ProjectRepository.delete(project)
        logger.info(f"Project deleted: id={project_id}, by user_id={user.id}")

    @staticmethod
    @transaction.atomic
    def add_member(project: Project, owner, user_id) -> ProjectMembership:
        """
        Thêm một User vào ProjectMembership với role=member. Chỉ Owner mới có quyền thực hiện.

        Args:
            project: Project instance cần thêm thành viên.
            owner: User instance thực hiện thao tác (phải là owner).
            user_id: ID của User cần thêm vào project.

        Returns:
            ProjectMembership: Instance membership vừa được tạo.

        Raises:
            PermissionDenied: Nếu owner không phải là owner của project.
            NotFound: Nếu user_id không tồn tại trong hệ thống.
            ValidationError: Nếu user đã là thành viên của project.
        """
        if project.owner_id != owner.id:
            logger.warning(
                f"User id={owner.id} attempted to add member to project id={project.id} without owner permission"
            )
            raise PermissionDenied("Bạn không có quyền thêm thành viên vào dự án này.")

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            logger.warning(f"Attempted to add non-existent user_id={user_id} to project id={project.id}")
            raise NotFound("Người dùng không tồn tại.")

        if ProjectMembershipRepository.membership_exists_for_user_id(project, user_id):
            raise ValidationError("Người dùng đã là thành viên của dự án này.")

        membership = ProjectMembershipRepository.create(project=project, user=user, role=ProjectRole.MEMBER)
        logger.info(f"Member added: user_id={user.id} to project_id={project.id}, by owner_id={owner.id}")
        return membership

    @staticmethod
    @transaction.atomic
    def remove_member(project: Project, owner, user_id) -> None:
        """
        Xóa một User khỏi ProjectMembership. Chỉ Owner mới có quyền thực hiện.
        Không thể xóa chính Owner khỏi project.

        Args:
            project: Project instance cần xóa thành viên.
            owner: User instance thực hiện thao tác (phải là owner).
            user_id: ID của User cần xóa khỏi project.

        Raises:
            PermissionDenied: Nếu owner không phải là owner của project.
            ValidationError: Nếu cố gắng xóa owner khỏi project.
            NotFound: Nếu user_id không phải thành viên của project.
        """
        if project.owner_id != owner.id:
            logger.warning(
                f"User id={owner.id} attempted to remove member from project id={project.id} without owner permission"
            )
            raise PermissionDenied("Bạn không có quyền xóa thành viên khỏi dự án này.")

        # Không cho phép xóa owner khỏi project
        if str(project.owner_id) == str(user_id):
            raise ValidationError("Không thể xóa owner khỏi dự án.")

        membership = ProjectMembershipRepository.get_membership_by_user_id(project, user_id)
        if membership is None:
            logger.warning(
                f"Attempted to remove non-member user_id={user_id} from project id={project.id}"
            )
            raise NotFound("Người dùng không phải là thành viên của dự án này.")

        ProjectMembershipRepository.delete(membership)
        logger.info(f"Member removed: user_id={user_id} from project_id={project.id}, by owner_id={owner.id}")

    @staticmethod
    def get_members(project: Project, user):
        """
        Trả về danh sách ProjectMembership của project. User phải là thành viên mới có quyền xem.

        Args:
            project: Project instance cần lấy danh sách thành viên.
            user: User instance thực hiện thao tác.

        Returns:
            QuerySet[ProjectMembership]

        Raises:
            PermissionDenied: Nếu user không phải là thành viên của project.
        """
        if not ProjectMembershipRepository.is_member(project, user):
            logger.warning(
                f"User id={user.id} attempted to list members of project id={project.id} without membership"
            )
            raise PermissionDenied("Bạn không phải là thành viên của dự án này.")

        return ProjectMembershipRepository.list_members(project)
