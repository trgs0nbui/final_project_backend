from rest_framework import serializers

from apps.users.serializers import UserSerializer
from .enums import ProjectCategory, ProjectType
from .models import Project, ProjectMembership


class ProjectSerializer(serializers.ModelSerializer):
    """
    Serializer cho Project.
    Trả về thông tin chi tiết dự án, bao gồm owner dạng nested read-only
    và task_count — số lượng task thuộc project (annotated từ queryset).
    Field `key` được tự động chuyển thành chữ hoa trước khi validate.
    """

    owner = UserSerializer(read_only=True)
    task_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Project
        fields = [
            'id',
            'name',
            'key',
            'description',
            'project_type',
            'category',
            'owner',
            'task_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'owner', 'task_count', 'created_at', 'updated_at']

    def validate_key(self, value: str) -> str:
        """
        Chuyển key thành chữ hoa và kiểm tra tính duy nhất.
        Khi update, bỏ qua instance hiện tại khi kiểm tra unique.
        """
        value = value.upper()
        qs = Project.objects.filter(key=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('Project key này đã được sử dụng.')
        return value

    def validate_project_type(self, value: str) -> str:
        """Kiểm tra project_type thuộc tập giá trị hợp lệ."""
        valid = [choice[0] for choice in ProjectType.choices]
        if value not in valid:
            raise serializers.ValidationError(
                f'project_type không hợp lệ. Chọn một trong: {", ".join(valid)}.'
            )
        return value

    def validate_category(self, value: str) -> str:
        """Kiểm tra category thuộc tập giá trị hợp lệ."""
        valid = [choice[0] for choice in ProjectCategory.choices]
        if value not in valid:
            raise serializers.ValidationError(
                f'category không hợp lệ. Chọn một trong: {", ".join(valid)}.'
            )
        return value


class ProjectMembershipSerializer(serializers.ModelSerializer):
    """
    Serializer cho ProjectMembership.
    Trả về thông tin thành viên dự án, bao gồm user dạng nested.
    """

    user = UserSerializer(read_only=True)

    class Meta:
        model = ProjectMembership
        fields = [
            "id",
            "user",
            "role",
            "joined_at",
        ]
        read_only_fields = ["id", "user", "joined_at"]
