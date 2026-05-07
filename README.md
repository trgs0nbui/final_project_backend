# Task Management System — Backend

Backend API cho hệ thống quản lý công việc theo nhóm, xây dựng bằng **Django REST Framework** với xác thực JWT, phân quyền theo vai trò, tìm kiếm/lọc công việc và phân trang.

> **Xem thêm:**
> - 🐳 Hướng dẫn chạy toàn bộ stack bằng Docker → [`infra/README.md`](../infra/README.md)
> - 🖥️ Hướng dẫn setup frontend Vue 3 → [`task-management-frontend/README.md`](../task-management-frontend/README.md)

---

## Mục Lục

- [Kiến Trúc Hệ Thống](#kiến-trúc-hệ-thống)
- [Yêu Cầu Hệ Thống](#yêu-cầu-hệ-thống)
- [Cài Đặt Môi Trường](#cài-đặt-môi-trường)
- [Cấu Hình Biến Môi Trường](#cấu-hình-biến-môi-trường)
- [Cài Đặt Database](#cài-đặt-database)
- [Chạy Migration](#chạy-migration)
- [Khởi Động Server](#khởi-động-server)
- [Chạy Tests](#chạy-tests)
- [Cấu Trúc Dự Án](#cấu-trúc-dự-án)
- [API Endpoints](#api-endpoints)

---

## Kiến Trúc Hệ Thống

```
┌─────────────────┐
│   Frontend      │  Vue 3 + Vite + Element Plus
│   :5173         │  → task-management-frontend/
└────────┬────────┘
         │ HTTP (CORS)
         ▼
┌─────────────────┐
│   Backend       │  Django REST Framework + JWT
│   :8000         │  → task-management-backend/
└────────┬────────┘
         │
    ┌────┴────┬──────────┐
    ▼         ▼          ▼
┌────────┐ ┌──────┐ ┌────────┐
│ Postgres│ │Redis │ │Celery  │
│  :5432  │ │:6379 │ │Worker  │
└─────────┘ └──────┘ └────────┘
```

**Môi trường Development:**
- Backend chạy tại `http://localhost:8000` (Django dev server)
- Frontend chạy tại `http://localhost:5173` (Vite dev server)
- Database: PostgreSQL local hoặc Docker
- Cache & Celery broker: Redis

**Môi trường Production:**
- Backend: Gunicorn WSGI server
- Frontend: Static files build bằng Vite, serve qua Nginx
- Nginx: Reverse proxy, serve static/media files
- Tất cả services chạy trong Docker containers

> Xem hướng dẫn đầy đủ về Docker setup tại [`infra/README.md`](../infra/README.md)

---

## Yêu Cầu Hệ Thống

| Thành phần | Phiên bản tối thiểu |
|---|---|
| Python | ≥ 3.11 |
| PostgreSQL | ≥ 13 |
| pip | ≥ 23 |

Kiểm tra phiên bản hiện tại:

```bash
python --version
psql --version
```

---

## Cài Đặt Môi Trường

### 1. Clone repository

```bash
git clone <repository-url>
cd task-management-backend
```

### 2. Tạo và kích hoạt virtual environment

**Linux / macOS:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows (Command Prompt):**

```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

**Windows (PowerShell):**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Cài đặt dependencies

Môi trường phát triển (bao gồm pytest, coverage):

```bash
pip install -r requirements/dev.txt
```

Môi trường production:

```bash
pip install -r requirements/prod.txt
```

---

## Cấu Hình Biến Môi Trường

### 1. Tạo file `.env` từ template

```bash
cp .env.example .env
```

### 2. Chỉnh sửa file `.env`

Mở file `.env` và cập nhật các giá trị phù hợp với môi trường của bạn:

```dotenv
# Django Core
SECRET_KEY=your-secret-key-here-change-in-production
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database (PostgreSQL)
POSTGRES_DB=taskmanager_dev
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your-db-password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
```

> **Lưu ý:** Không bao giờ commit file `.env` vào version control. File này đã được thêm vào `.gitignore`.

### Mô tả các biến môi trường

| Biến | Bắt buộc | Mô tả |
|---|---|---|
| `SECRET_KEY` | ✅ | Django secret key — dùng giá trị ngẫu nhiên dài ≥ 50 ký tự trong production |
| `DEBUG` | ✅ | `True` cho development, `False` cho production |
| `ALLOWED_HOSTS` | ✅ | Danh sách host được phép, phân cách bằng dấu phẩy |
| `POSTGRES_DB` | ✅ | Tên database PostgreSQL |
| `POSTGRES_USER` | ✅ | Username PostgreSQL |
| `POSTGRES_PASSWORD` | ✅ | Password PostgreSQL |
| `POSTGRES_HOST` | ✅ | Host PostgreSQL (mặc định: `localhost`) |
| `POSTGRES_PORT` | ✅ | Port PostgreSQL (mặc định: `5432`) |
| `EMAIL_HOST_USER` | ❌ | Gmail address dùng để gửi email xác thực |
| `EMAIL_HOST_PASSWORD` | ❌ | Gmail App Password (không phải password thường) |
| `FRONTEND_URL` | ❌ | URL frontend dùng trong link email xác thực (mặc định: `http://localhost:5173`) |

> **Lấy Gmail App Password:** Vào [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords), bật 2-Step Verification, tạo App Password cho "Mail".

> **`FRONTEND_URL`** phải trỏ về địa chỉ của frontend Vue, không phải backend. Trong dev là `http://localhost:5173`, trong production là domain thực của bạn. Backend dùng giá trị này để tạo link xác thực email gửi cho người dùng — link sẽ dẫn đến route `/verify-email?token=...` trên frontend. Xem thêm luồng xác thực tại [`task-management-frontend/README.md`](../task-management-frontend/README.md#luồng-xác-thực-email).

---

## Cài Đặt Database

### 1. Tạo database PostgreSQL

Đăng nhập vào PostgreSQL và tạo database:

```bash
psql -U postgres
```

```sql
CREATE DATABASE taskmanager_dev;
\q
```

Hoặc dùng lệnh một dòng:

```bash
createdb -U postgres taskmanager_dev
```

---

## Chạy Migration

Sau khi cấu hình database, chạy migration để tạo các bảng:

```bash
python manage.py migrate
```

Kiểm tra trạng thái migration:

```bash
python manage.py showmigrations
```

Tạo migration mới khi thay đổi model:

```bash
python manage.py makemigrations
```

---

## Khởi Động Server

### Development server

```bash
python manage.py runserver
```

Server sẽ chạy tại `http://127.0.0.1:8000/`.

Chỉ định host và port khác:

```bash
python manage.py runserver 0.0.0.0:8080
```

### Kiểm tra server hoạt động

Sau khi khởi động, thử gọi API đăng ký:

```bash
curl -X POST http://localhost:8000/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "email": "test@example.com", "password": "password123", "confirm_password": "password123"}'
```

Kết quả mong đợi: HTTP 201 với thông tin user và thông báo kiểm tra email.

> **Lưu ý:** Sau khi đăng ký, người dùng cần xác thực email trước khi đăng nhập. Backend gửi link xác thực về địa chỉ email đã đăng ký. Link trỏ về frontend tại `{FRONTEND_URL}/verify-email?token=...`. Xem thêm tại [`task-management-frontend/README.md`](../task-management-frontend/README.md#luồng-xác-thực-email).

### Chạy với Docker

Nếu muốn chạy backend cùng toàn bộ stack (PostgreSQL, Redis, Celery, Frontend) bằng Docker, xem hướng dẫn tại [`infra/README.md`](../infra/README.md).

---

## Chạy Tests

### Chạy toàn bộ test suite với pytest

```bash
pytest
```

### Chạy với báo cáo coverage

```bash
pytest --cov=apps --cov-report=term-missing
```

### Chạy test của một app cụ thể

```bash
pytest apps/users/tests/
pytest apps/projects/tests/
pytest apps/tasks/tests/
```

### Chạy một file test cụ thể

```bash
pytest apps/users/tests/test_user_service.py
```

### Chạy bằng Django test runner (thay thế)

```bash
python manage.py test
```

> **Lưu ý:** Cấu hình pytest nằm trong `pytest.ini`. Mặc định sử dụng settings `config.settings.dev`.

---

## Cấu Trúc Dự Án

```
task-management-backend/
├── apps/
│   ├── common/          # Pagination và utilities dùng chung
│   ├── users/           # App quản lý người dùng và xác thực
│   ├── projects/        # App quản lý dự án và thành viên
│   └── tasks/           # App quản lý công việc
├── config/
│   ├── settings/
│   │   ├── base.py      # Cấu hình chung
│   │   ├── dev.py       # Cấu hình development
│   │   └── prod.py      # Cấu hình production
│   ├── urls.py          # URL routing gốc
│   ├── wsgi.py
│   └── asgi.py
├── requirements/
│   ├── base.txt         # Dependencies cơ bản
│   ├── dev.txt          # Dependencies development
│   └── prod.txt         # Dependencies production
├── .env.example         # Template biến môi trường
├── manage.py
├── pytest.ini
└── README.md
```

---

## API Endpoints

### Authentication

| Method | Endpoint | Mô tả |
|---|---|---|
| POST | `/api/auth/register/` | Đăng ký tài khoản mới — gửi email xác thực |
| POST | `/api/auth/login/` | Đăng nhập, nhận JWT tokens (yêu cầu email đã xác thực) |
| POST | `/api/auth/token/refresh/` | Làm mới access token |
| GET | `/api/auth/verify-email/?token=<token>` | Xác thực email từ link trong email |

> Luồng đăng ký → xác thực email → đăng nhập được xử lý hoàn toàn trên frontend. Xem chi tiết tại [`task-management-frontend/README.md`](../task-management-frontend/README.md#luồng-xác-thực-email).

### Users

| Method | Endpoint | Mô tả |
|---|---|---|
| GET | `/api/users/me/` | Xem hồ sơ cá nhân |
| PATCH | `/api/users/me/` | Cập nhật hồ sơ cá nhân (`full_name`, `avatar_url`) |
| POST | `/api/users/me/avatar/` | Upload ảnh đại diện (multipart, tối đa 2MB) |

### Projects

| Method | Endpoint | Mô tả |
|---|---|---|
| GET | `/api/projects/` | Danh sách dự án của user |
| POST | `/api/projects/` | Tạo dự án mới |
| GET | `/api/projects/{id}/` | Chi tiết dự án |
| PATCH | `/api/projects/{id}/` | Cập nhật dự án (Owner) |
| DELETE | `/api/projects/{id}/` | Xóa dự án (Owner) |
| GET | `/api/projects/{id}/members/` | Danh sách thành viên |
| POST | `/api/projects/{id}/members/` | Thêm thành viên (Owner) |
| DELETE | `/api/projects/{id}/members/{user_id}/` | Xóa thành viên (Owner) |

### Tasks

| Method | Endpoint | Mô tả |
|---|---|---|
| GET | `/api/projects/{id}/tasks/` | Danh sách công việc (hỗ trợ filter) |
| POST | `/api/projects/{id}/tasks/` | Tạo công việc mới |
| GET | `/api/projects/{id}/tasks/{task_id}/` | Chi tiết công việc |
| PATCH | `/api/projects/{id}/tasks/{task_id}/` | Cập nhật công việc |
| DELETE | `/api/projects/{id}/tasks/{task_id}/` | Xóa công việc (Owner) |

#### Tham số filter cho Task

| Tham số | Ví dụ | Mô tả |
|---|---|---|
| `status` | `?status=todo` | Lọc theo trạng thái: `todo`, `in_progress`, `done` |
| `priority` | `?priority=high` | Lọc theo độ ưu tiên: `low`, `medium`, `high` |
| `assignee` | `?assignee=<user_id>` | Lọc theo người được giao |
| `due_date_from` | `?due_date_from=2025-01-01` | Lọc từ ngày (YYYY-MM-DD) |
| `due_date_to` | `?due_date_to=2025-12-31` | Lọc đến ngày (YYYY-MM-DD) |
| `search` | `?search=keyword` | Tìm kiếm trong title và description |

---

## Xác Thực

Tất cả endpoints (trừ đăng ký, đăng nhập và xác thực email) yêu cầu JWT access token trong header:

```
Authorization: Bearer <access_token>
```

- **Access token** có hiệu lực trong **60 phút**
- **Refresh token** có hiệu lực trong **7 ngày**

Token được quản lý tự động bởi frontend (tự động refresh khi hết hạn). Xem chi tiết tại [`task-management-frontend/README.md`](../task-management-frontend/README.md).

---

## Liên Kết Liên Quan

| Tài liệu | Mô tả |
|---|---|
| [`infra/README.md`](../infra/README.md) | Hướng dẫn chạy toàn bộ stack bằng Docker (dev & prod) |
| [`task-management-frontend/README.md`](../task-management-frontend/README.md) | Hướng dẫn setup và chạy frontend Vue 3 |
