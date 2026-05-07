# Đảm bảo Celery app được khởi tạo khi Django start
from .celery import app as celery_app

__all__ = ('celery_app',)
