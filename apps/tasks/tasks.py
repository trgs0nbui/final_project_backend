import logging

from celery import shared_task
from django.core.cache import cache

logger = logging.getLogger(__name__)

_CACHE_VERSION = "v2"


@shared_task
def invalidate_project_tasks_cache(project_id):
    pattern = f"{_CACHE_VERSION}:project_tasks:{project_id}:*"
    try:
        keys = cache.keys(pattern)
        count = len(keys) if keys else 0
        if keys:
            cache.delete_many(keys)
        logger.info(f"Cache invalidated: pattern={pattern}, count={count}, task=invalidate_project_tasks_cache")
    except Exception as e:
        logger.error(f"Failed to invalidate project_tasks cache for project {project_id}: {e}")
