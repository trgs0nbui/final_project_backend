"""
Unit tests cho ProjectService sử dụng pytest-django.
Validates: Requirements 14.2, 14.3, 14.7
"""
import itertools
import uuid

import pytest
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.projects.enums import ProjectRole
from apps.projects.models import Project, ProjectMembership
from apps.projects.services import ProjectService
from apps.users.models import User

# ---------------------------------------------------------------------------
# Counter để sinh project key duy nhất trong mỗi test run
# ---------------------------------------------------------------------------
_project_counter = itertools.count(1)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def owner(db):
    """User đóng vai trò owner của project."""
    return User.objects.create_user(
        username="owner",
        email="owner@example.com",
        password="StrongPass123",
    )


@pytest.fixture
def member(db):
    """User đóng vai trò member thông thường."""
    return User.objects.create_user(
        username="member",
        email="member@example.com",
        password="StrongPass123",
    )


@pytest.fixture
def outsider(db):
    """User không thuộc bất kỳ project nào."""
    return User.objects.create_user(
        username="outsider",
        email="outsider@example.com",
        password="StrongPass123",
    )


@pytest.fixture
def project(owner):
    """Project được tạo bởi owner."""
    key = f"PRJ{next(_project_counter):04d}"
    return ProjectService.create_project(owner=owner, name="Test Project", key=key)


@pytest.fixture
def project_with_member(project, owner, member):
    """Project đã có thêm member."""
    ProjectService.add_member(project, owner, member.id)
    return project


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_extra_user(suffix: str) -> User:
    return User.objects.create_user(
        username=f"user_{suffix}",
        email=f"user_{suffix}@example.com",
        password="StrongPass123",
    )


def _unique_project(owner: User) -> Project:
    key = f"PRJ{next(_project_counter):04d}"
    return ProjectService.create_project(owner=owner, name="Extra Project", key=key)


# ===========================================================================
# create_project
# ===========================================================================

@pytest.mark.django_db
class TestCreateProject:
    """Tests cho ProjectService.create_project — Requirements 14.2"""

    def test_returns_project_instance(self, project):
        assert isinstance(project, Project)

    def test_sets_correct_owner(self, project, owner):
        assert project.owner_id == owner.id

    def test_auto_adds_owner_to_membership(self, project, owner):
        assert ProjectMembership.objects.filter(project=project, user=owner).exists()

    def test_owner_membership_has_owner_role(self, project, owner):
        membership = ProjectMembership.objects.get(project=project, user=owner)
        assert membership.role == ProjectRole.OWNER

    def test_only_one_membership_created(self, project):
        assert ProjectMembership.objects.filter(project=project).count() == 1


# ===========================================================================
# update_project
# ===========================================================================

@pytest.mark.django_db
class TestUpdateProject:
    """Tests cho ProjectService.update_project — Requirements 14.2, 14.7"""

    def test_owner_can_update_project(self, project, owner):
        updated = ProjectService.update_project(project, owner, name="Updated Name")
        assert updated.name == "Updated Name"

    def test_update_persists_to_database(self, project, owner):
        ProjectService.update_project(project, owner, description="New description")
        project.refresh_from_db()
        assert project.description == "New description"

    def test_member_cannot_update_project(self, project_with_member, member):
        with pytest.raises(PermissionDenied):
            ProjectService.update_project(project_with_member, member, name="Hacked")

    def test_outsider_cannot_update_project(self, project, outsider):
        with pytest.raises(PermissionDenied):
            ProjectService.update_project(project, outsider, name="Hacked")


# ===========================================================================
# delete_project
# ===========================================================================

@pytest.mark.django_db
class TestDeleteProject:
    """Tests cho ProjectService.delete_project — Requirements 14.2, 14.7"""

    def test_owner_can_delete_project(self, project, owner):
        project_id = project.id
        ProjectService.delete_project(project, owner)
        assert not Project.objects.filter(id=project_id).exists()

    def test_delete_cascades_memberships(self, project_with_member, owner):
        project_id = project_with_member.id
        ProjectService.delete_project(project_with_member, owner)
        assert not ProjectMembership.objects.filter(project_id=project_id).exists()

    def test_member_cannot_delete_project(self, project_with_member, member):
        with pytest.raises(PermissionDenied):
            ProjectService.delete_project(project_with_member, member)

    def test_outsider_cannot_delete_project(self, project, outsider):
        with pytest.raises(PermissionDenied):
            ProjectService.delete_project(project, outsider)


# ===========================================================================
# add_member
# ===========================================================================

@pytest.mark.django_db
class TestAddMember:
    """Tests cho ProjectService.add_member — Requirements 14.3, 14.7"""

    def test_owner_can_add_member(self, project, owner, member):
        membership = ProjectService.add_member(project, owner, member.id)
        assert isinstance(membership, ProjectMembership)

    def test_added_member_has_member_role(self, project, owner, member):
        membership = ProjectService.add_member(project, owner, member.id)
        assert membership.role == ProjectRole.MEMBER

    def test_add_member_persists_to_database(self, project, owner, member):
        ProjectService.add_member(project, owner, member.id)
        assert ProjectMembership.objects.filter(project=project, user=member).exists()

    def test_add_duplicate_member_raises_validation_error(self, project, owner, member):
        ProjectService.add_member(project, owner, member.id)
        with pytest.raises(ValidationError):
            ProjectService.add_member(project, owner, member.id)

    def test_add_owner_again_raises_validation_error(self, project, owner):
        """Owner đã là thành viên — thêm lại phải raise ValidationError."""
        with pytest.raises(ValidationError):
            ProjectService.add_member(project, owner, owner.id)

    def test_member_cannot_add_new_member(self, project_with_member, member):
        another = _make_extra_user("another")
        with pytest.raises(PermissionDenied):
            ProjectService.add_member(project_with_member, member, another.id)

    def test_add_nonexistent_user_raises_not_found(self, project, owner):
        with pytest.raises(NotFound):
            ProjectService.add_member(project, owner, uuid.uuid4())


# ===========================================================================
# remove_member
# ===========================================================================

@pytest.mark.django_db
class TestRemoveMember:
    """Tests cho ProjectService.remove_member — Requirements 14.3, 14.7"""

    def test_owner_can_remove_member(self, project_with_member, owner, member):
        ProjectService.remove_member(project_with_member, owner, member.id)
        assert not ProjectMembership.objects.filter(
            project=project_with_member, user=member
        ).exists()

    def test_cannot_remove_owner_from_project(self, project, owner):
        with pytest.raises(ValidationError):
            ProjectService.remove_member(project, owner, owner.id)

    def test_member_cannot_remove_other_member(self, project_with_member, owner, member):
        another = _make_extra_user("another2")
        ProjectService.add_member(project_with_member, owner, another.id)
        with pytest.raises(PermissionDenied):
            ProjectService.remove_member(project_with_member, member, another.id)

    def test_remove_nonmember_raises_not_found(self, project, owner, outsider):
        with pytest.raises(NotFound):
            ProjectService.remove_member(project, owner, outsider.id)

    def test_outsider_cannot_remove_member(self, project_with_member, member, outsider):
        with pytest.raises(PermissionDenied):
            ProjectService.remove_member(project_with_member, outsider, member.id)


# ===========================================================================
# get_members
# ===========================================================================

@pytest.mark.django_db
class TestGetMembers:
    """Tests cho ProjectService.get_members — Requirements 14.3"""

    def test_owner_can_list_members(self, project_with_member, owner):
        members = ProjectService.get_members(project_with_member, owner)
        assert members.count() == 2

    def test_member_can_list_members(self, project_with_member, member):
        members = ProjectService.get_members(project_with_member, member)
        assert members.count() == 2

    def test_outsider_cannot_list_members(self, project, outsider):
        with pytest.raises(PermissionDenied):
            ProjectService.get_members(project, outsider)
