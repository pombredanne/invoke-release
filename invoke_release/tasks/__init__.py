import warnings

from invoke_release.config import config
from invoke_release.tasks.branch_task import branch
from invoke_release.tasks.release_task import release
from invoke_release.tasks.rollback_release_task import rollback_release
from invoke_release.tasks.version_task import version


__all__ = (
    'branch',
    'release',
    'rollback_release',
    'version',
)


def configure_release_parameters(**kwargs):
    warnings.warn(
        '`configure_release_parameters` is deprecated. Please use `invoke_release.config.config.configure`, instead.',
        DeprecationWarning,
        stacklevel=2,
    )

    config.configure(**kwargs)
