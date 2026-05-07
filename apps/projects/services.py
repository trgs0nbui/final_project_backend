import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, Q
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from .enums import ProjectRole
from .models import Project, ProjectMembership
from .repositories import ProjectMembershipRepository, ProjectRepository, ProjectOwnerRepository
from .models import ProjectMembership as PM
from .tasks import (
            invalidate_project_members_cache,
            invalidate_search_users_cache,
            invalidate_user_projects_cache, 
            invalidate_project_all_cache
        )

logger = logging.getLogger(__name__)

User = get_user_model()

# Thời gian sống mặc định của cache (giây)
_CACHE_TTL = getattr(settings, 'CACHE_TTL', 300)
# Prefix version để tránh conflict khi thay đổi format cache
_CACHE_VERSION = "v2"
# TTL ngắn hơn cho kết quả tìm kiếm user (thay đổi thường xuyên hơn)
_SEARCH_CACHE_TTL = 60


def _safe_enqueue(task_func, *args, **kwargs):
    """
    Enqueue Celery task an toàn.
    Nếu broker không khả dụng, log lỗi và tiếp tục — không crash request.
    """
    try:
        task_func.delay(*args, **kwargs)
    except Exception as e:
        logger.error(f"Failed to enqueue task {task_func.__name__}: {e}")


def _normalize_query(query: str) -> str:
    """Chuẩn hóa chuỗi tìm kiếm: lowercase + strip whitespace."""
    return query.lower().strip()


class ProjectService:
    """
    Service xử lý logic nghiệp vụ liên quan đến Project và ProjectMembership.
    Mọi thao tác database được uỷ quyền cho ProjectRepository và ProjectMembershipRepository.
    Cache layer được nhúng trực tiếp vào các read methods.
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
            **kwargs: Các trường bổ sung.

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

        # Invalidate cache danh sách project của owner
        _safe_enqueue(invalidate_user_projects_cache, str(owner.id))

        return project

    @staticmethod
    def get_user_projects(user):
        """
        Trả về queryset các Project mà user là thành viên (Owner hoặc Member).
        Kết quả được cache trong Redis với key user_projects:{user_id}.

        Args:
            user: User instance cần lấy danh sách project.

        Returns:
            QuerySet[Project]
        """
        cache_key = f"{_CACHE_VERSION}:user_projects:{user.id}"

        try:
            cached_ids = cache.get(cache_key)
            if cached_ids is not None:
                logger.debug(f"Cache hit: key={cache_key}, method=get_user_projects")
                # Trả về QuerySet lọc theo IDs đã cache — annotate task_count để giữ nguyên interface
                return (
                    Project.objects
                    .filter(id__in=cached_ids)
                    .select_related('owner')
                    .annotate(task_count=Count('tasks', distinct=True))
                    .order_by('-created_at')
                )

            logger.debug(f"Cache miss: key={cache_key}, method=get_user_projects")
            queryset = ProjectRepository.get_projects_for_user(user)

            # Chỉ cache danh sách IDs (nhẹ, serialize được)
            project_ids = list(queryset.values_list('id', flat=True))
            cache.set(cache_key, [str(pid) for pid in project_ids], _CACHE_TTL)
            return queryset

        except Exception as e:
            logger.error(f"Redis error in get_user_projects (key={cache_key}): {e}")
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

        # Invalidate cache user_projects cho tất cả thành viên
        member_ids = list(
            ProjectMembership.objects.filter(project=project).values_list('user_id', flat=True)
        )
        for uid in member_ids:
            _safe_enqueue(invalidate_user_projects_cache, str(uid))

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

        project_id = str(project.id)

        # Lấy danh sách member_ids trước khi xóa (CASCADE sẽ xóa memberships)
        member_ids = list(
            ProjectMembership.objects.filter(project=project).values_list('user_id', flat=True)
        )
        member_id_strs = [str(uid) for uid in member_ids]

        ProjectRepository.delete(project)
        logger.info(f"Project deleted: id={project_id}, by user_id={user.id}")

        # Invalidate toàn bộ cache liên quan đến project
        _safe_enqueue(invalidate_project_all_cache, project_id, member_id_strs)

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

        # Invalidate cache liên quan
        _safe_enqueue(invalidate_project_members_cache, str(project.id))
        _safe_enqueue(invalidate_user_projects_cache, str(user_id))
        _safe_enqueue(invalidate_search_users_cache, str(project.id))

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

        # Invalidate cache liên quan
        _safe_enqueue(invalidate_project_members_cache, str(project.id))
        _safe_enqueue(invalidate_user_projects_cache, str(user_id))

    @staticmethod
    def search_users_to_add(project: Project, query: str):
        """
        Tìm kiếm user theo username hoặc email để thêm vào project.
        Chỉ trả về user chưa là thành viên của project, tối đa 10 kết quả.
        Kết quả được cache với TTL ngắn (60 giây).

        Args:
            project: Project instance.
            query: Chuỗi tìm kiếm (username hoặc email, tối thiểu 2 ký tự).

        Returns:
            QuerySet[User] hoặc list (từ cache)
        """
        normalized = _normalize_query(query)
        cache_key = f"{_CACHE_VERSION}:search_users:{project.id}:{normalized}"

        try:
            cached = cache.get(cache_key)
            if cached is not None:
                logger.debug(f"Cache hit: key={cache_key}, method=search_users_to_add")
                # cached là list of dicts — trả về QuerySet lọc theo IDs
                cached_ids = [item['id'] for item in cached]
                return User.objects.filter(id__in=cached_ids).order_by('username')

            logger.debug(f"Cache miss: key={cache_key}, method=search_users_to_add")

            existing_member_ids = ProjectMembership.objects.filter(
                project=project
            ).values_list('user_id', flat=True)

            queryset = (
                User.objects
                .filter(
                    Q(username__icontains=query) | Q(email__icontains=query)
                )
                .exclude(id__in=existing_member_ids)
                .filter(is_active=True)
                .order_by('username')[:10]
            )

            serialized = list(queryset.values('id', 'username', 'email'))
            cache.set(cache_key, serialized, _SEARCH_CACHE_TTL)
            return queryset

        except Exception as e:
            logger.error(f"Redis error in search_users_to_add (key={cache_key}): {e}")
            # Fallback: query DB trực tiếp
            existing_member_ids = ProjectMembership.objects.filter(
                project=project
            ).values_list('user_id', flat=True)
            return (
                User.objects
                .filter(Q(username__icontains=query) | Q(email__icontains=query))
                .exclude(id__in=existing_member_ids)
                .filter(is_active=True)
                .order_by('username')[:10]
            )

    @staticmethod
    def get_member_stats(user) -> dict:
        """
        Trả về thống kê thành viên cho các project mà user là owner.

        Args:
            user: User instance.

        Returns:
            dict: {
                "total_members": int,  — tổng membership trong các project user là owner
                "owned_projects": int, — số project user là owner
            }
        """
        
        owned_ids = ProjectOwnerRepository.get_owned_project_ids(user)
        total_members = ProjectMembershipRepository.count_members_in_projects(owned_ids)

        stats = {
            'total_members': total_members,
            'owned_projects': len(owned_ids),
        }
        logger.debug(f"ProjectService.get_member_stats: user_id={user.id}, stats={stats}")
        return stats

    @staticmethod
    def get_members(project: Project, user):        
        """
        Trả về danh sách ProjectMembership của project.
        User phải là thành viên mới có quyền xem.
        Kết quả được cache trong Redis với key project_members:{project_id}.

        Args:
            project: Project instance cần lấy danh sách thành viên.
            user: User instance thực hiện thao tác.

        Returns:
            QuerySet[ProjectMembership] hoặc list (từ cache)

        Raises:
            PermissionDenied: Nếu user không phải là thành viên của project.
        """
        # Permission check TRƯỚC cache — không cache kết quả của PermissionDenied
        if not ProjectMembershipRepository.is_member(project, user):
            logger.warning(
                f"User id={user.id} attempted to list members of project id={project.id} without membership"
            )
            raise PermissionDenied("Bạn không phải là thành viên của dự án này.")

        cache_key = f"{_CACHE_VERSION}:project_members:{project.id}"

        try:
            cached_ids = cache.get(cache_key)
            if cached_ids is not None:
                logger.debug(f"Cache hit: key={cache_key}, method=get_members")
                # Trả về QuerySet lọc theo IDs đã cache — giữ nguyên interface
                return (
                    PM.objects
                    .filter(id__in=cached_ids)
                    .select_related('user')
                    .order_by('joined_at')
                )

            logger.debug(f"Cache miss: key={cache_key}, method=get_members")
            queryset = ProjectMembershipRepository.list_members(project)

            # Chỉ cache danh sách IDs
            membership_ids = list(queryset.values_list('id', flat=True))
            cache.set(cache_key, [str(mid) for mid in membership_ids], _CACHE_TTL)
            return queryset

        except Exception as e:
            logger.error(f"Redis error in get_members (key={cache_key}): {e}")
            return ProjectMembershipRepository.list_members(project)
