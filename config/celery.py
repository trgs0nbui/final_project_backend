import os

from celery import Celery

# Đặt settings module mặc định cho Celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')

app = Celery('task_management')

# Đọc cấu hình từ Django settings với namespace CELERY_
# Ví dụ: CELERY_BROKER_URL → broker_url
app.config_from_object('django.conf:settings', namespace='CELERY')

# Tự động phát hiện tasks từ tất cả INSTALLED_APPS
app.autodiscover_tasks()
