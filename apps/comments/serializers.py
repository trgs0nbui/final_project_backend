from rest_framework import serializers

from apps.users.serializers import UserSerializer
from .models import Comment


class CommentSerializer(serializers.ModelSerializer):
    """
    Serializer cho Comment.

    - author là read-only (được set từ request.user trong view).
    - content là trường duy nhất có thể write.
    """

    author = UserSerializer(read_only=True)

    class Meta:
        model = Comment
        fields = [
            'id',
            'task',
            'author',
            'content',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'task', 'author', 'created_at', 'updated_at']

    def validate_content(self, value: str) -> str:
        """Nội dung comment không được để trống hoặc chỉ có khoảng trắng."""
        if not value or not value.strip():
            raise serializers.ValidationError('Nội dung bình luận không được để trống.')
        return value.strip()
