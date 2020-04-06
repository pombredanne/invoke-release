from typing import List

from invoke_release.internal.context import TaskContext
from invoke_release.internal.utils import set_map
from invoke_release.plugins.base import ReleaseStatus


__all__ = (
    'get_extra_files_to_commit',
    'post_release',
    'post_rollback',
    'pre_commit',
    'pre_push',
    'pre_release',
    'pre_rollback',
)


def get_extra_files_to_commit(context: TaskContext) -> List[str]:
    return list(set_map(
        lambda plugin: plugin.get_extra_files_to_commit(context.config.root_directory),
        context.config.plugins,
    ))


def pre_release(context: TaskContext, old_version: str) -> None:
    for plugin in context.config.plugins:
        plugin.pre_release(context.config.root_directory, old_version)


def pre_commit(context: TaskContext, old_version: str, new_version: str) -> None:
    for plugin in context.config.plugins:
        plugin.pre_commit(context.config.root_directory, old_version, new_version)


def pre_push(context: TaskContext, old_version: str, new_version: str) -> None:
    for plugin in context.config.plugins:
        plugin.pre_push(context.config.root_directory, old_version, new_version)


def post_release(context: TaskContext, old_version: str, new_version: str, status: ReleaseStatus) -> None:
    for plugin in context.config.plugins:
        plugin.post_release(context.config.root_directory, old_version, new_version, status)


def pre_rollback(context: TaskContext, current_version: str) -> None:
    for plugin in context.config.plugins:
        plugin.pre_rollback(context.config.root_directory, current_version)


def post_rollback(context: TaskContext, current_version: str, rollback_to_version: str) -> None:
    for plugin in context.config.plugins:
        plugin.post_rollback(context.config.root_directory, current_version, rollback_to_version)
