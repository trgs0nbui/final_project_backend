import uuid

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models

from .enums import ProjectCategory, ProjectRole, ProjectType

# Project key phải là chữ hoa, số và dấu gạch ngang, dài 2–10 ký tự.
# Ví dụ hợp lệ: "PROJ", "MY-APP", "SVC01"
project_key_validator = RegexValidator(
    regex=r'^[A-Z0-9][A-Z0-9\-]{1,9}$',
    message=(
        'Project key chỉ được chứa chữ hoa (A–Z), số (0–9) và dấu gạch ngang (-). '
        'Độ dài từ 2 đến 10 ký tự và phải bắt đầu bằng chữ hoa hoặc số.'
    ),
)


class Project(models.Model):
    """
    Represents a project that can have multiple members and tasks.

    Fields:
        key          — Mã định danh ngắn do owner tự đặt (VD: "PROJ", "MY-APP").
                       Duy nhất toàn hệ thống, chỉ chứa A–Z, 0–9, dấu '-', dài 2–10 ký tự.
        project_type — Phân loại dự án theo lĩnh vực: software / business / service.
        category     — Danh mục chi tiết hơn trong lĩnh vực đó (enum cố định).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    key = models.CharField(
        max_length=10,
        unique=True,
        validators=[project_key_validator],
        default='KEY',
        help_text='Mã định danh ngắn của dự án (VD: PROJ, MY-APP). Chỉ A–Z, 0–9, dấu "-", 2–10 ký tự.',
    )
    description = models.TextField(blank=True)
    project_type = models.CharField(
        max_length=20,
        choices=ProjectType.choices,
        default=ProjectType.SOFTWARE,
        help_text='Loại dự án: software, business hoặc service.',
    )
    category = models.CharField(
        max_length=20,
        choices=ProjectCategory.choices,
        default=ProjectCategory.OTHER,
        help_text='Danh mục của dự án.',
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='owned_projects',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'projects'
        verbose_name = 'Project'
        verbose_name_plural = 'Projects'
        indexes = [
            models.Index(fields=['key'], name='idx_project_key'),
            models.Index(fields=['project_type'], name='idx_project_type'),
            models.Index(fields=['category'], name='idx_project_category'),
        ]

    def __str__(self):
        return f'[{self.key}] {self.name}'


class ProjectMembership(models.Model):
    """
    Represents a user's membership in a project with an assigned role.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='memberships',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='project_memberships',
    )
    role = models.CharField(max_length=10, choices=ProjectRole.choices)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'project_memberships'
        unique_together = [('project', 'user')]
        verbose_name = 'Project Membership'
        verbose_name_plural = 'Project Memberships'

    def __str__(self):
        return f"{self.user} - {self.project} ({self.role})"
