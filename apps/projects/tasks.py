import logging

from celery import shared_task
from django.core.cache import cache

logger = logging.getLogger(__name__)

_CACHE_VERSION = "v2"


@shared_task
def invalidate_user_projects_cache(user_id):
    key = f"{_CACHE_VERSION}:user_projects:{user_id}"
    cache.delete(key)
    logger.info(f"Cache invalidated: key={key}, task=invalidate_user_projects_cache")


@shared_task
def invalidate_project_members_cache(project_id):
    key = f"{_CACHE_VERSION}:project_members:{project_id}"
    cache.delete(key)
    logger.info(f"Cache invalidated: key={key}, task=invalidate_project_members_cache")


@shared_task
def invalidate_search_users_cache(project_id):
    pattern = f"{_CACHE_VERSION}:search_users:{project_id}:*"
    try:
        keys = cache.keys(pattern)
        count = len(keys) if keys else 0
        if keys:
            cache.delete_many(keys)
        logger.info(f"Cache invalidated: pattern={pattern}, count={count}, task=invalidate_search_users_cache")
    except Exception as e:
        logger.error(f"Failed to invalidate search_users cache for project {project_id}: {e}")


@shared_task
def invalidate_project_all_cache(project_id, member_user_ids=None):
    keys_to_delete = []
    keys_to_delete.append(f"{_CACHE_VERSION}:project_members:{project_id}")

    try:
        task_keys = cache.keys(f"{_CACHE_VERSION}:project_tasks:{project_id}:*")
        if task_keys:
            keys_to_delete.extend(task_keys)
    except Exception as e:
        logger.error(f"Failed to get project_tasks keys for project {project_id}: {e}")

    try:
        search_keys = cache.keys(f"{_CACHE_VERSION}:search_users:{project_id}:*")
        if search_keys:
            keys_to_delete.extend(search_keys)
    except Exception as e:
        logger.error(f"Failed to get search_users keys for project {project_id}: {e}")

    if member_user_ids:
        for uid in member_user_ids:
            keys_to_delete.append(f"{_CACHE_VERSION}:user_projects:{uid}")

    if keys_to_delete:
        cache.delete_many(keys_to_delete)

    logger.info(
        f"Cache invalidated: project_id={project_id}, "
        f"keys_count={len(keys_to_delete)}, task=invalidate_project_all_cache"
    )
