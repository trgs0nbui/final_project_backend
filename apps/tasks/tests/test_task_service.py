"""
Unit tests cho TaskService sử dụng pytest-django.
Validates: Requirements 14.4, 14.5, 14.7
"""
import itertools
from datetime import date

import pytest
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.projects.services import ProjectService
from apps.tasks.enums import TaskPriority, TaskStatus
from apps.tasks.models import Task
from apps.tasks.services import TaskService
from apps.users.models import User

# ---------------------------------------------------------------------------
# Counter để sinh project key duy nhất trong mỗi test run
# ---------------------------------------------------------------------------
_project_counter = itertools.count(1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _unique_key() -> str:
    return f"TSK{next(_project_counter):04d}"


def _make_user(suffix: str) -> User:
    return User.objects.create_user(
        username=f"user_{suffix}",
        email=f"user_{suffix}@example.com",
        password="StrongPass123",
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def owner(db):
    """User đóng vai trò owner của project."""
    return _make_user("owner")


@pytest.fixture
def member(db):
    """User đóng vai trò member thông thường."""
    return _make_user("member")


@pytest.fixture
def outsider(db):
    """User không thuộc bất kỳ project nào."""
    return _make_user("outsider")


@pytest.fixture
def project(owner):
    """Project được tạo bởi owner, owner tự động là thành viên."""
    return ProjectService.create_project(owner=owner, name="Test Project", key=_unique_key())


@pytest.fixture
def project_with_member(project, owner, member):
    """Project đã có thêm member."""
    ProjectService.add_member(project, owner, member.id)
    return project


@pytest.fixture
def task(project_with_member, owner):
    """Task cơ bản được tạo bởi owner trong project_with_member."""
    return TaskService.create_task(
        project=project_with_member,
        creator=owner,
        title="Base Task",
    )


# ===========================================================================
# create_task
# ===========================================================================

@pytest.mark.django_db
class TestCreateTask:
    """Tests cho TaskService.create_task — Requirements 14.4, 14.7"""

    def test_member_can_create_task(self, project_with_member, member):
        task = TaskService.create_task(
            project=project_with_member,
            creator=member,
            title="Member Task",
        )
        assert isinstance(task, Task)

    def test_owner_can_create_task(self, project_with_member, owner):
        task = TaskService.create_task(
            project=project_with_member,
            creator=owner,
            title="Owner Task",
        )
        assert isinstance(task, Task)

    def test_create_task_sets_created_by(self, project_with_member, owner):
        task = TaskService.create_task(
            project=project_with_member,
            creator=owner,
            title="Task With Creator",
        )
        assert task.created_by_id == owner.id

    def test_create_task_default_status_is_todo(self, project_with_member, owner):
        task = TaskService.create_task(
            project=project_with_member,
            creator=owner,
            title="Default Status Task",
        )
        assert task.status == TaskStatus.TODO

    def test_create_task_default_priority_is_medium(self, project_with_member, owner):
        task = TaskService.create_task(
            project=project_with_member,
            creator=owner,
            title="Default Priority Task",
        )
        assert task.priority == TaskPriority.MEDIUM

    def test_create_task_persists_to_database(self, project_with_member, owner):
        task = TaskService.create_task(
            project=project_with_member,
            creator=owner,
            title="Persisted Task",
        )
        assert Task.objects.filter(id=task.id).exists()

    def test_outsider_cannot_create_task(self, project_with_member, outsider):
        """Non-member phải nhận PermissionDenied khi tạo task."""
        with pytest.raises(PermissionDenied):
            TaskService.create_task(
                project=project_with_member,
                creator=outsider,
                title="Unauthorized Task",
            )

    def test_create_task_with_valid_assignee(self, project_with_member, owner, member):
        """Assignee là thành viên của project — tạo task thành công."""
        task = TaskService.create_task(
            project=project_with_member,
            creator=owner,
            title="Assigned Task",
            assignee=member,
        )
        assert task.assignee_id == member.id

    def test_create_task_with_non_member_assignee_raises_validation_error(
        self, project_with_member, owner, outsider
    ):
        """Assignee không phải thành viên phải raise ValidationError — Requirement 14.4."""
        with pytest.raises(ValidationError):
            TaskService.create_task(
                project=project_with_member,
                creator=owner,
                title="Bad Assignee Task",
                assignee=outsider,
            )

    def test_create_task_with_null_assignee_is_allowed(self, project_with_member, owner):
        """assignee=None phải được chấp nhận."""
        task = TaskService.create_task(
            project=project_with_member,
            creator=owner,
            title="No Assignee Task",
            assignee=None,
        )
        assert task.assignee is None


# ===========================================================================
# delete_task
# ===========================================================================

@pytest.mark.django_db
class TestDeleteTask:
    """Tests cho TaskService.delete_task — Requirements 14.4, 14.7"""

    def test_owner_can_delete_task(self, task, owner):
        """Chỉ owner mới xóa được task — Requirement 14.4."""
        task_id = task.id
        TaskService.delete_task(task, owner)
        assert not Task.objects.filter(id=task_id).exists()

    def test_member_cannot_delete_task(self, task, member):
        """Member không phải owner phải nhận PermissionDenied."""
        with pytest.raises(PermissionDenied):
            TaskService.delete_task(task, member)

    def test_outsider_cannot_delete_task(self, task, outsider):
        """Non-member phải nhận PermissionDenied khi xóa task."""
        with pytest.raises(PermissionDenied):
            TaskService.delete_task(task, outsider)


# ===========================================================================
# filter_tasks — helpers
# ===========================================================================

def _create_task(project, creator, **kwargs) -> Task:
    """Shortcut để tạo task với các trường tùy chọn."""
    return TaskService.create_task(project=project, creator=creator, **kwargs)


def _filter(project, user, **filters):
    """Shortcut gọi filter_tasks và trả về list."""
    return list(TaskService.filter_tasks(project, user, filters))


# ===========================================================================
# filter_tasks — status
# ===========================================================================

@pytest.mark.django_db
class TestFilterByStatus:
    """Tests lọc task theo status — Requirement 14.5"""

    def test_filter_by_todo_status(self, project_with_member, owner):
        t1 = _create_task(project_with_member, owner, title="Todo Task", status=TaskStatus.TODO)
        _create_task(project_with_member, owner, title="Done Task", status=TaskStatus.DONE)

        results = _filter(project_with_member, owner, status=TaskStatus.TODO)
        assert t1 in results
        assert all(t.status == TaskStatus.TODO for t in results)

    def test_filter_by_in_progress_status(self, project_with_member, owner):
        t1 = _create_task(project_with_member, owner, title="WIP Task", status=TaskStatus.IN_PROGRESS)
        _create_task(project_with_member, owner, title="Todo Task", status=TaskStatus.TODO)

        results = _filter(project_with_member, owner, status=TaskStatus.IN_PROGRESS)
        assert t1 in results
        assert all(t.status == TaskStatus.IN_PROGRESS for t in results)

    def test_filter_by_done_status(self, project_with_member, owner):
        t1 = _create_task(project_with_member, owner, title="Done Task", status=TaskStatus.DONE)
        _create_task(project_with_member, owner, title="Todo Task", status=TaskStatus.TODO)

        results = _filter(project_with_member, owner, status=TaskStatus.DONE)
        assert t1 in results
        assert all(t.status == TaskStatus.DONE for t in results)

    def test_filter_excludes_other_statuses(self, project_with_member, owner):
        _create_task(project_with_member, owner, title="Todo", status=TaskStatus.TODO)
        _create_task(project_with_member, owner, title="Done", status=TaskStatus.DONE)

        results = _filter(project_with_member, owner, status=TaskStatus.IN_PROGRESS)
        assert results == []

    def test_non_member_cannot_filter_tasks(self, project_with_member, outsider):
        with pytest.raises(PermissionDenied):
            _filter(project_with_member, outsider, status=TaskStatus.TODO)


# ===========================================================================
# filter_tasks — assignee
# ===========================================================================

@pytest.mark.django_db
class TestFilterByAssignee:
    """Tests lọc task theo assignee — Requirement 14.5"""

    def test_filter_by_assignee_returns_assigned_tasks(self, project_with_member, owner, member):
        t1 = _create_task(project_with_member, owner, title="Assigned", assignee=member)
        _create_task(project_with_member, owner, title="Unassigned")

        results = _filter(project_with_member, owner, assignee=member.id)
        assert t1 in results
        assert all(t.assignee_id == member.id for t in results)

    def test_filter_by_assignee_excludes_other_assignees(self, project_with_member, owner, member):
        _create_task(project_with_member, owner, title="Assigned to member", assignee=member)
        t2 = _create_task(project_with_member, owner, title="Assigned to owner", assignee=owner)

        results = _filter(project_with_member, owner, assignee=owner.id)
        assert t2 in results
        assert all(t.assignee_id == owner.id for t in results)

    def test_filter_by_nonexistent_assignee_returns_empty(self, project_with_member, owner):
        _create_task(project_with_member, owner, title="Some Task", assignee=owner)

        import uuid
        results = _filter(project_with_member, owner, assignee=uuid.uuid4())
        assert results == []


# ===========================================================================
# filter_tasks — priority
# ===========================================================================

@pytest.mark.django_db
class TestFilterByPriority:
    """Tests lọc task theo priority — Requirement 14.5"""

    def test_filter_by_low_priority(self, project_with_member, owner):
        t1 = _create_task(project_with_member, owner, title="Low", priority=TaskPriority.LOW)
        _create_task(project_with_member, owner, title="High", priority=TaskPriority.HIGH)

        results = _filter(project_with_member, owner, priority=TaskPriority.LOW)
        assert t1 in results
        assert all(t.priority == TaskPriority.LOW for t in results)

    def test_filter_by_medium_priority(self, project_with_member, owner):
        t1 = _create_task(project_with_member, owner, title="Medium", priority=TaskPriority.MEDIUM)
        _create_task(project_with_member, owner, title="High", priority=TaskPriority.HIGH)

        results = _filter(project_with_member, owner, priority=TaskPriority.MEDIUM)
        assert t1 in results
        assert all(t.priority == TaskPriority.MEDIUM for t in results)

    def test_filter_by_high_priority(self, project_with_member, owner):
        t1 = _create_task(project_with_member, owner, title="High", priority=TaskPriority.HIGH)
        _create_task(project_with_member, owner, title="Low", priority=TaskPriority.LOW)

        results = _filter(project_with_member, owner, priority=TaskPriority.HIGH)
        assert t1 in results
        assert all(t.priority == TaskPriority.HIGH for t in results)

    def test_filter_by_priority_excludes_others(self, project_with_member, owner):
        _create_task(project_with_member, owner, title="Low", priority=TaskPriority.LOW)
        _create_task(project_with_member, owner, title="Medium", priority=TaskPriority.MEDIUM)

        results = _filter(project_with_member, owner, priority=TaskPriority.HIGH)
        assert results == []


# ===========================================================================
# filter_tasks — due_date range
# ===========================================================================

@pytest.mark.django_db
class TestFilterByDueDate:
    """Tests lọc task theo khoảng due_date — Requirement 14.5"""

    def test_filter_due_date_from_inclusive(self, project_with_member, owner):
        """due_date_from phải bao gồm ngày bắt đầu (>=)."""
        t1 = _create_task(project_with_member, owner, title="On From", due_date=date(2025, 6, 1))
        t2 = _create_task(project_with_member, owner, title="After From", due_date=date(2025, 6, 15))
        _create_task(project_with_member, owner, title="Before From", due_date=date(2025, 5, 31))

        results = _filter(project_with_member, owner, due_date_from=date(2025, 6, 1))
        assert t1 in results
        assert t2 in results
        assert all(t.due_date >= date(2025, 6, 1) for t in results)

    def test_filter_due_date_to_inclusive(self, project_with_member, owner):
        """due_date_to phải bao gồm ngày kết thúc (<=)."""
        t1 = _create_task(project_with_member, owner, title="On To", due_date=date(2025, 6, 30))
        t2 = _create_task(project_with_member, owner, title="Before To", due_date=date(2025, 6, 15))
        _create_task(project_with_member, owner, title="After To", due_date=date(2025, 7, 1))

        results = _filter(project_with_member, owner, due_date_to=date(2025, 6, 30))
        assert t1 in results
        assert t2 in results
        assert all(t.due_date <= date(2025, 6, 30) for t in results)

    def test_filter_due_date_range_both_bounds_inclusive(self, project_with_member, owner):
        """Khoảng [from, to] phải bao gồm cả hai đầu — Requirement 14.5."""
        t_start = _create_task(project_with_member, owner, title="Start", due_date=date(2025, 6, 1))
        t_mid = _create_task(project_with_member, owner, title="Mid", due_date=date(2025, 6, 15))
        t_end = _create_task(project_with_member, owner, title="End", due_date=date(2025, 6, 30))
        _create_task(project_with_member, owner, title="Before", due_date=date(2025, 5, 31))
        _create_task(project_with_member, owner, title="After", due_date=date(2025, 7, 1))

        results = _filter(
            project_with_member, owner,
            due_date_from=date(2025, 6, 1),
            due_date_to=date(2025, 6, 30),
        )
        assert t_start in results
        assert t_mid in results
        assert t_end in results
        assert len(results) == 3

    def test_filter_due_date_excludes_null_due_dates(self, project_with_member, owner):
        """Task không có due_date không được trả về khi lọc theo khoảng ngày."""
        _create_task(project_with_member, owner, title="No Due Date")
        t1 = _create_task(project_with_member, owner, title="Has Due Date", due_date=date(2025, 6, 15))

        results = _filter(
            project_with_member, owner,
            due_date_from=date(2025, 6, 1),
            due_date_to=date(2025, 6, 30),
        )
        assert t1 in results
        assert all(t.due_date is not None for t in results)

    def test_filter_due_date_range_no_match_returns_empty(self, project_with_member, owner):
        _create_task(project_with_member, owner, title="Outside Range", due_date=date(2025, 8, 1))

        results = _filter(
            project_with_member, owner,
            due_date_from=date(2025, 6, 1),
            due_date_to=date(2025, 6, 30),
        )
        assert results == []


# ===========================================================================
# filter_tasks — search
# ===========================================================================

@pytest.mark.django_db
class TestFilterBySearch:
    """Tests tìm kiếm keyword trong title và description — Requirement 14.5"""

    def test_search_matches_title_case_insensitive(self, project_with_member, owner):
        """Tìm kiếm trong title không phân biệt hoa thường."""
        t1 = _create_task(project_with_member, owner, title="Fix Login Bug")
        _create_task(project_with_member, owner, title="Add Dashboard Feature")

        results = _filter(project_with_member, owner, search="login")
        assert t1 in results

        results_upper = _filter(project_with_member, owner, search="LOGIN")
        assert t1 in results_upper

        results_mixed = _filter(project_with_member, owner, search="Login")
        assert t1 in results_mixed

    def test_search_matches_description_case_insensitive(self, project_with_member, owner):
        """Tìm kiếm trong description không phân biệt hoa thường."""
        t1 = _create_task(
            project_with_member, owner,
            title="Generic Task",
            description="This task involves the payment gateway integration",
        )
        _create_task(project_with_member, owner, title="Other Task", description="Unrelated content")

        results = _filter(project_with_member, owner, search="payment")
        assert t1 in results

        results_upper = _filter(project_with_member, owner, search="PAYMENT")
        assert t1 in results_upper

    def test_search_matches_partial_keyword(self, project_with_member, owner):
        """Tìm kiếm theo từ khóa một phần (icontains)."""
        t1 = _create_task(project_with_member, owner, title="Authentication Service")
        _create_task(project_with_member, owner, title="Database Migration")

        results = _filter(project_with_member, owner, search="auth")
        assert t1 in results

    def test_search_returns_both_title_and_description_matches(self, project_with_member, owner):
        """Kết quả bao gồm cả task khớp qua title lẫn description."""
        t_title = _create_task(project_with_member, owner, title="Deploy API")
        t_desc = _create_task(
            project_with_member, owner,
            title="Backend Work",
            description="Deploy the new API version",
        )
        _create_task(project_with_member, owner, title="Unrelated Task")

        results = _filter(project_with_member, owner, search="deploy")
        assert t_title in results
        assert t_desc in results

    def test_search_no_match_returns_empty(self, project_with_member, owner):
        _create_task(project_with_member, owner, title="Fix Bug")

        results = _filter(project_with_member, owner, search="xyznonexistent")
        assert results == []


# ===========================================================================
# filter_tasks — combined filters
# ===========================================================================

@pytest.mark.django_db
class TestFilterCombined:
    """Tests kết hợp nhiều filter cùng lúc (AND logic) — Requirement 14.5"""

    def test_status_and_priority_combined(self, project_with_member, owner):
        """Kết hợp status + priority phải áp dụng AND logic."""
        t_match = _create_task(
            project_with_member, owner,
            title="Match",
            status=TaskStatus.IN_PROGRESS,
            priority=TaskPriority.HIGH,
        )
        _create_task(
            project_with_member, owner,
            title="Wrong Priority",
            status=TaskStatus.IN_PROGRESS,
            priority=TaskPriority.LOW,
        )
        _create_task(
            project_with_member, owner,
            title="Wrong Status",
            status=TaskStatus.DONE,
            priority=TaskPriority.HIGH,
        )

        results = _filter(
            project_with_member, owner,
            status=TaskStatus.IN_PROGRESS,
            priority=TaskPriority.HIGH,
        )
        assert t_match in results
        assert len(results) == 1

    def test_status_and_assignee_combined(self, project_with_member, owner, member):
        """Kết hợp status + assignee phải áp dụng AND logic."""
        t_match = _create_task(
            project_with_member, owner,
            title="Match",
            status=TaskStatus.TODO,
            assignee=member,
        )
        _create_task(
            project_with_member, owner,
            title="Wrong Assignee",
            status=TaskStatus.TODO,
            assignee=owner,
        )
        _create_task(
            project_with_member, owner,
            title="Wrong Status",
            status=TaskStatus.DONE,
            assignee=member,
        )

        results = _filter(
            project_with_member, owner,
            status=TaskStatus.TODO,
            assignee=member.id,
        )
        assert t_match in results
        assert len(results) == 1

    def test_search_and_status_combined(self, project_with_member, owner):
        """Kết hợp search + status phải áp dụng AND logic."""
        t_match = _create_task(
            project_with_member, owner,
            title="Fix Login Bug",
            status=TaskStatus.IN_PROGRESS,
        )
        _create_task(
            project_with_member, owner,
            title="Fix Login Bug",
            status=TaskStatus.DONE,
        )
        _create_task(
            project_with_member, owner,
            title="Unrelated Task",
            status=TaskStatus.IN_PROGRESS,
        )

        results = _filter(
            project_with_member, owner,
            search="login",
            status=TaskStatus.IN_PROGRESS,
        )
        assert t_match in results
        assert len(results) == 1

    def test_due_date_range_and_priority_combined(self, project_with_member, owner):
        """Kết hợp due_date range + priority phải áp dụng AND logic."""
        t_match = _create_task(
            project_with_member, owner,
            title="Match",
            priority=TaskPriority.HIGH,
            due_date=date(2025, 6, 15),
        )
        _create_task(
            project_with_member, owner,
            title="Wrong Priority",
            priority=TaskPriority.LOW,
            due_date=date(2025, 6, 15),
        )
        _create_task(
            project_with_member, owner,
            title="Out of Range",
            priority=TaskPriority.HIGH,
            due_date=date(2025, 8, 1),
        )

        results = _filter(
            project_with_member, owner,
            priority=TaskPriority.HIGH,
            due_date_from=date(2025, 6, 1),
            due_date_to=date(2025, 6, 30),
        )
        assert t_match in results
        assert len(results) == 1

    def test_all_filters_combined(self, project_with_member, owner, member):
        """Kết hợp tất cả filter cùng lúc."""
        t_match = _create_task(
            project_with_member, owner,
            title="Deploy Auth Service",
            description="Deploy the authentication module",
            status=TaskStatus.IN_PROGRESS,
            priority=TaskPriority.HIGH,
            assignee=member,
            due_date=date(2025, 6, 15),
        )
        # Sai status
        _create_task(
            project_with_member, owner,
            title="Deploy Auth Service",
            status=TaskStatus.DONE,
            priority=TaskPriority.HIGH,
            assignee=member,
            due_date=date(2025, 6, 15),
        )
        # Sai priority
        _create_task(
            project_with_member, owner,
            title="Deploy Auth Service",
            status=TaskStatus.IN_PROGRESS,
            priority=TaskPriority.LOW,
            assignee=member,
            due_date=date(2025, 6, 15),
        )
        # Sai assignee
        _create_task(
            project_with_member, owner,
            title="Deploy Auth Service",
            status=TaskStatus.IN_PROGRESS,
            priority=TaskPriority.HIGH,
            assignee=owner,
            due_date=date(2025, 6, 15),
        )
        # Ngoài khoảng ngày
        _create_task(
            project_with_member, owner,
            title="Deploy Auth Service",
            status=TaskStatus.IN_PROGRESS,
            priority=TaskPriority.HIGH,
            assignee=member,
            due_date=date(2025, 8, 1),
        )
        # Không khớp search
        _create_task(
            project_with_member, owner,
            title="Unrelated Task",
            status=TaskStatus.IN_PROGRESS,
            priority=TaskPriority.HIGH,
            assignee=member,
            due_date=date(2025, 6, 15),
        )

        results = _filter(
            project_with_member, owner,
            status=TaskStatus.IN_PROGRESS,
            priority=TaskPriority.HIGH,
            assignee=member.id,
            due_date_from=date(2025, 6, 1),
            due_date_to=date(2025, 6, 30),
            search="auth",
        )
        assert t_match in results
        assert len(results) == 1

    def test_no_filters_returns_all_project_tasks(self, project_with_member, owner):
        """Không có filter nào thì trả về tất cả task của project."""
        t1 = _create_task(project_with_member, owner, title="Task 1")
        t2 = _create_task(project_with_member, owner, title="Task 2")
        t3 = _create_task(project_with_member, owner, title="Task 3")

        results = _filter(project_with_member, owner)
        assert t1 in results
        assert t2 in results
        assert t3 in results

    def test_filter_only_returns_tasks_of_given_project(self, owner):
        """Filter không trả về task của project khác."""
        project_a = ProjectService.create_project(owner=owner, name="Project A", key=_unique_key())
        project_b = ProjectService.create_project(owner=owner, name="Project B", key=_unique_key())

        t_a = _create_task(project_a, owner, title="Task in A", status=TaskStatus.TODO)
        _create_task(project_b, owner, title="Task in B", status=TaskStatus.TODO)

        results = _filter(project_a, owner, status=TaskStatus.TODO)
        assert t_a in results
        assert all(t.project_id == project_a.id for t in results)


# ===========================================================================
# update_task
# ===========================================================================

@pytest.mark.django_db
class TestUpdateTask:
    """Tests cho TaskService.update_task — Requirements 14.4, 14.7"""

    def test_member_can_update_task_title(self, task, project_with_member, member):
        """Member của project có thể cập nhật title của task."""
        updated = TaskService.update_task(task, member, title="Updated Title")
        assert updated.title == "Updated Title"

    def test_owner_can_update_task(self, task, owner):
        """Owner của project có thể cập nhật task."""
        updated = TaskService.update_task(task, owner, title="Owner Updated")
        assert updated.title == "Owner Updated"

    def test_update_task_persists_to_database(self, task, owner):
        """Thay đổi phải được lưu vào database."""
        TaskService.update_task(task, owner, description="New description")
        task.refresh_from_db()
        assert task.description == "New description"

    def test_update_task_returns_task_instance(self, task, owner):
        """update_task phải trả về Task instance."""
        result = TaskService.update_task(task, owner, title="Return Check")
        assert isinstance(result, Task)

    def test_outsider_cannot_update_task(self, task, outsider):
        """Non-member phải nhận PermissionDenied khi cập nhật task."""
        with pytest.raises(PermissionDenied):
            TaskService.update_task(task, outsider, title="Hacked")

    def test_update_task_with_valid_assignee(self, task, owner, project_with_member, member):
        """Cập nhật assignee thành member hợp lệ phải thành công."""
        updated = TaskService.update_task(task, owner, assignee=member)
        assert updated.assignee_id == member.id

    def test_update_task_with_non_member_assignee_raises_validation_error(
        self, task, owner, outsider
    ):
        """Cập nhật assignee thành non-member phải raise ValidationError."""
        with pytest.raises(ValidationError):
            TaskService.update_task(task, owner, assignee=outsider)

    def test_update_task_with_null_assignee_is_allowed(self, task, owner, member):
        """Cập nhật assignee=None (bỏ gán) phải được chấp nhận."""
        # Gán member trước
        TaskService.update_task(task, owner, assignee=member)
        # Bỏ gán
        updated = TaskService.update_task(task, owner, assignee=None)
        assert updated.assignee is None

    def test_update_task_status(self, task, owner):
        """Cập nhật status của task."""
        updated = TaskService.update_task(task, owner, status=TaskStatus.IN_PROGRESS)
        assert updated.status == TaskStatus.IN_PROGRESS

    def test_update_task_priority(self, task, owner):
        """Cập nhật priority của task."""
        updated = TaskService.update_task(task, owner, priority=TaskPriority.HIGH)
        assert updated.priority == TaskPriority.HIGH
