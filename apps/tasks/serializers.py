from rest_framework import serializers

from apps.projects.models import ProjectMembership
from apps.users.serializers import UserSerializer
from .enums import TaskPriority, TaskStatus
from .models import Task


class TaskSerializer(serializers.ModelSerializer):
    """
    Serializer cho Task.

    - Validate status và priority theo enum.
    - Validate assignee là thành viên của project (lấy project từ context).
    - created_by và project là read-only; assignee có thể được set qua assignee_id.
    """

    assignee = UserSerializer(read_only=True)
    assignee_id = serializers.UUIDField(
        write_only=True,
        required=False,
        allow_null=True,
        help_text='UUID của user được giao task. Phải là thành viên của project.',
    )
    created_by = UserSerializer(read_only=True)

    class Meta:
        model = Task
        fields = [
            'id',
            'project',
            'title',
            'description',
            'assignee',
            'assignee_id',
            'status',
            'priority',
            'due_date',
            'created_by',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'project', 'assignee', 'created_by', 'created_at', 'updated_at']

    def validate_status(self, value: str) -> str:
        """Kiểm tra status thuộc tập giá trị hợp lệ."""
        valid = [choice[0] for choice in TaskStatus.choices]
        if value not in valid:
            raise serializers.ValidationError(
                f'status không hợp lệ. Chọn một trong: {", ".join(valid)}.'
            )
        return value

    def validate_priority(self, value: str) -> str:
        """Kiểm tra priority thuộc tập giá trị hợp lệ."""
        valid = [choice[0] for choice in TaskPriority.choices]
        if value not in valid:
            raise serializers.ValidationError(
                f'priority không hợp lệ. Chọn một trong: {", ".join(valid)}.'
            )
        return value

    def validate_assignee_id(self, value):
        """
        Kiểm tra assignee_id là thành viên của project.
        Project được lấy từ serializer context (key: 'project').
        """
        if value is None:
            return value

        project = self.context.get('project')
        if project is None:
            raise serializers.ValidationError(
                'Không thể xác thực assignee: thiếu thông tin project trong context.'
            )

        is_member = ProjectMembership.objects.filter(
            project=project,
            user_id=value,
        ).exists()

        if not is_member:
            raise serializers.ValidationError(
                'Assignee phải là thành viên của project.'
            )

        return value


class TaskFilterSerializer(serializers.Serializer):
    """
    Serializer để validate các tham số filter khi lấy danh sách Task.

    Các tham số được hỗ trợ:
        - status: lọc theo trạng thái task
        - priority: lọc theo mức độ ưu tiên
        - assignee: UUID của user được giao task
        - due_date_from: ngày bắt đầu khoảng due_date (bao gồm)
        - due_date_to: ngày kết thúc khoảng due_date (bao gồm)
        - search: tìm kiếm theo title hoặc description (case-insensitive)
    """

    status = serializers.ChoiceField(
        choices=TaskStatus.choices,
        required=False,
        help_text=f'Lọc theo status. Giá trị hợp lệ: {", ".join(s[0] for s in TaskStatus.choices)}.',
    )
    priority = serializers.ChoiceField(
        choices=TaskPriority.choices,
        required=False,
        help_text=f'Lọc theo priority. Giá trị hợp lệ: {", ".join(p[0] for p in TaskPriority.choices)}.',
    )
    assignee = serializers.UUIDField(
        required=False,
        help_text='UUID của user được giao task.',
    )
    due_date_from = serializers.DateField(
        required=False,
        help_text='Ngày bắt đầu khoảng due_date (YYYY-MM-DD, bao gồm).',
    )
    due_date_to = serializers.DateField(
        required=False,
        help_text='Ngày kết thúc khoảng due_date (YYYY-MM-DD, bao gồm).',
    )
    search = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text='Tìm kiếm theo title hoặc description (không phân biệt hoa thường).',
    )

    def validate(self, data: dict) -> dict:
        """
        Kiểm tra due_date_from không lớn hơn due_date_to khi cả hai được cung cấp.
        """
        due_date_from = data.get('due_date_from')
        due_date_to = data.get('due_date_to')

        if due_date_from and due_date_to and due_date_from > due_date_to:
            raise serializers.ValidationError(
                {'due_date_from': 'due_date_from không được lớn hơn due_date_to.'}
            )

        return data
