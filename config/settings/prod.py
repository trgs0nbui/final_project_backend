import os
import logging

from .base import *

DEBUG = False
ALLOWED_HOSTS = []

# Production yêu cầu REDIS_URL được cấu hình tường minh
_redis_url = os.getenv('REDIS_URL')
if not _redis_url:
    logging.getLogger(__name__).warning(
        "REDIS_URL is not set in production environment. "
        "Falling back to default redis://localhost:6379/0. "
        "Please configure REDIS_URL explicitly."
    )
