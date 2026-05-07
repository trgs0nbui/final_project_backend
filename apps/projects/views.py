import logging

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import NotFound, PermissionDenied
from apps.users.serializers import UserSerializer

from apps.common.pagination import CustomPageNumberPagination
from .repositories import ProjectRepository, ProjectMembershipRepository
from .services import ProjectService
from .serializers import ProjectSerializer, ProjectMembershipSerializer
logger = logging.getLogger(__name__)


def get_project_or_404(pk, user):
    """
    Lấy project theo pk. Trả về 404 nếu không tồn tại hoặc user không phải thành viên.

    Args:
        pk: UUID của project.
        user: User instance đang thực hiện request.

    Returns:
        Project: Instance project tìm được.

    Raises:
        NotFound: Nếu project không tồn tại hoặc user không phải thành viên.
    """
    project = ProjectRepository.get_by_id(pk)
    if project is None or not ProjectMembershipRepository.is_member(project, user):
        raise NotFound("Dự án không tồn tại hoặc bạn không có quyền truy cập.")
    return project


class ProjectListCreateView(APIView):
    """
    GET  /api/projects/  — Danh sách project mà user là thành viên (phân trang).
    POST /api/projects/  — Tạo project mới, user trở thành owner.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Trả về danh sách project mà user đang đăng nhập là thành viên."""
        projects = ProjectService.get_user_projects(request.user)

        paginator = CustomPageNumberPagination()
        page = paginator.paginate_queryset(projects, request)
        serializer = ProjectSerializer(page, many=True)

        logger.debug(f"ProjectListCreateView.get: user_id={request.user.id}")
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        """Tạo project mới. User trở thành owner và được thêm vào membership."""
        serializer = ProjectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated = serializer.validated_data
        project = ProjectService.create_project(
            owner=request.user,
            name=validated['name'],
            description=validated.get('description', ''),
            key=validated['key'],
            project_type=validated['project_type'],
            category=validated.get('category', 'other'),
        )

        logger.info(f"ProjectListCreateView.post: created project_id={project.id} by user_id={request.user.id}")
        return Response(ProjectSerializer(project).data, status=status.HTTP_201_CREATED)


class ProjectDetailView(APIView):
    """
    GET    /api/projects/<pk>/  — Chi tiết project.
    PUT    /api/projects/<pk>/  — Cập nhật toàn bộ project (owner only).
    PATCH  /api/projects/<pk>/  — Cập nhật một phần project (owner only).
    DELETE /api/projects/<pk>/  — Xóa project (owner only).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        """Trả về thông tin chi tiết của project nếu user là thành viên."""
        project = get_project_or_404(pk, request.user)
        logger.debug(f"ProjectDetailView.get: project_id={pk}, user_id={request.user.id}")
        return Response(ProjectSerializer(project).data, status=status.HTTP_200_OK)

    def put(self, request, pk):
        """Cập nhật toàn bộ project. Chỉ owner mới có quyền thực hiện."""
        project = get_project_or_404(pk, request.user)
        serializer = ProjectSerializer(project, data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = ProjectService.update_project(project, request.user, **serializer.validated_data)

        logger.info(f"ProjectDetailView.put: project_id={pk}, user_id={request.user.id}")
        return Response(ProjectSerializer(updated).data, status=status.HTTP_200_OK)

    def patch(self, request, pk):
        """Cập nhật một phần project. Chỉ owner mới có quyền thực hiện."""
        project = get_project_or_404(pk, request.user)
        serializer = ProjectSerializer(project, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated = ProjectService.update_project(project, request.user, **serializer.validated_data)

        logger.info(f"ProjectDetailView.patch: project_id={pk}, user_id={request.user.id}")
        return Response(ProjectSerializer(updated).data, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        """Xóa project cùng toàn bộ task liên quan. Chỉ owner mới có quyền thực hiện."""
        project = get_project_or_404(pk, request.user)
        ProjectService.delete_project(project, request.user)

        logger.info(f"ProjectDetailView.delete: project_id={pk}, user_id={request.user.id}")
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProjectMemberListCreateView(APIView):
    """
    GET  /api/projects/<pk>/members/  — Danh sách thành viên của project (phân trang).
    POST /api/projects/<pk>/members/  — Thêm thành viên mới vào project (owner only).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        """Trả về danh sách thành viên của project nếu user là thành viên."""
        project = get_project_or_404(pk, request.user)
        members = ProjectService.get_members(project, request.user)

        paginator = CustomPageNumberPagination()
        page = paginator.paginate_queryset(members, request)
        serializer = ProjectMembershipSerializer(page, many=True)

        logger.debug(f"ProjectMemberListCreateView.get: project_id={pk}, user_id={request.user.id}")
        return paginator.get_paginated_response(serializer.data)

    def post(self, request, pk):
        """Thêm thành viên mới vào project. Chỉ owner mới có quyền thực hiện."""
        project = get_project_or_404(pk, request.user)

        user_id = request.data.get('user_id')
        if not user_id:
            return Response(
                {'user_id': ['user_id là bắt buộc.']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        membership = ProjectService.add_member(project, request.user, user_id)

        logger.info(
            f"ProjectMemberListCreateView.post: added user_id={user_id} "
            f"to project_id={pk} by owner_id={request.user.id}"
        )
        return Response(ProjectMembershipSerializer(membership).data, status=status.HTTP_201_CREATED)


class ProjectMemberDestroyView(APIView):
    """
    DELETE /api/projects/<pk>/members/<user_id>/  — Xóa thành viên khỏi project (owner only).
    """

    permission_classes = [IsAuthenticated]

    def delete(self, request, pk, user_id):
        """Xóa thành viên khỏi project. Chỉ owner mới có quyền thực hiện."""
        project = get_project_or_404(pk, request.user)
        ProjectService.remove_member(project, request.user, user_id)

        logger.info(
            f"ProjectMemberDestroyView.delete: removed user_id={user_id} "
            f"from project_id={pk} by owner_id={request.user.id}"
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProjectMemberSearchView(APIView):
    """
    GET /api/projects/<pk>/members/search/?q=<query>

    Tìm kiếm user trong hệ thống theo username hoặc email để thêm vào project.
    Chỉ trả về user chưa là thành viên của project.
    Chỉ owner mới có quyền gọi endpoint này.

    Query params:
        q (str, required): Chuỗi tìm kiếm (tối thiểu 2 ký tự).

    Returns:
        200: Danh sách user khớp với query, tối đa 10 kết quả.
        400: Nếu q thiếu hoặc quá ngắn.
        403: Nếu user không phải owner.
        404: Nếu project không tồn tại hoặc user không phải thành viên.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        """Tìm kiếm user chưa là thành viên của project để thêm vào."""
        project = get_project_or_404(pk, request.user)

        # Chỉ owner mới có quyền tìm kiếm để thêm thành viên
        if project.owner_id != request.user.id:
            
            raise PermissionDenied("Bạn không có quyền thêm thành viên vào dự án này.")

        q = request.query_params.get('q', '').strip()
        if len(q) < 2:
            return Response(
                {'q': ['Chuỗi tìm kiếm phải có ít nhất 2 ký tự.']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        users = ProjectService.search_users_to_add(project, q)

        
        return Response(UserSerializer(users, many=True).data, status=status.HTTP_200_OK)


class ProjectMemberStatsView(APIView):
    """
    GET /api/projects/member-stats/

    Trả về tổng số thành viên trong tất cả projects mà user hiện tại là owner.

    Returns:
        {
            "total_members": int,   — tổng thành viên trong các project user là owner
            "owned_projects": int,  — số project user là owner
        }
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        stats = ProjectService.get_member_stats(request.user)
        logger.debug(f"ProjectMemberStatsView.get: user_id={request.user.id}, stats={stats}")
        return Response(stats, status=status.HTTP_200_OK)
