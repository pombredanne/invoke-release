from enum import Enum
import os
from typing import (
    Generator,
    List,
    Optional,
)

from invoke_release.errors import ReleaseFailure


__all__ = (
    'AbstractInvokeReleasePlugin',
    'ReleaseStatus',
)


class ReleaseStatus(Enum):
    NOT_PUSHED = 'NOT_PUSHED'
    PUSHED = 'PUSHED'
    ROLLED_BACK = 'ROLLED_BACK'


class AbstractInvokeReleasePlugin(object):
    """
    The base class from which all plugins must extend.
    """

    def __init__(self, *extra_files_to_commit: str) -> None:
        """
        Initialize a plugin.

        :param extra_files_to_commit: If this plugin (or the code constructing it) requires additional files to be
                                      committed during a release (other than the changelog and version file), specify
                                      these files (relative to the project root directory) in this argument.
        """
        self.__extra_files_to_commit: List[str] = list(extra_files_to_commit) if extra_files_to_commit else []

    def get_extra_files_to_commit(self, root_directory: str) -> Generator[str, None, None]:
        """
        Yields an iterator of all the files this plugin has modified (if any) that should be committed (or rolled back,
        as the case may be). This method can (and should) also be used by hook methods in the plugin when iterating
        over the files and modifying them (if applicable). The file names this method returns are absolute file names,
        created by comining the provided relative file names with the `root_directory` argument.

        :param root_directory: The root project directory to combine with the provided relative file names.

        :return: An iterator of all the files modified by this plugin.
        """
        for file_name in self.__extra_files_to_commit:
            yield os.path.join(root_directory, file_name)

    def error_check(self, root_directory: str) -> Optional[List[str]]:
        """
        Invokes a hook for checking error states during `invoke version` calls. Commonly used to warn the user about
        incorrectly configured plugins. Returns a list of error strings, each to be printed as a separate error on
        a new line.

        :param root_directory: The root project directory

        :return: A list of error messages, or None or [] if no error messages.
        """

    def pre_release(self, root_directory: str, old_version: str) -> None:
        """
        Invokes a pre-release hook to execute tasks before the user is prompted for a new version or changelog message.
        Commonly used to run pre-release checks and fail the release if some condition is met or not met.

        :param root_directory: The root project directory
        :param old_version: The version of the project before release

        :raise: ReleaseFailure
        """
        errors = self.error_check(root_directory)
        if errors:
            import pprint
            raise ReleaseFailure(
                f'The {self.__class__.__name__} plugin generated the following errors:\n{pprint.pformat(errors)}',
            )

    def pre_commit(self, root_directory: str, old_version: str, new_version: str) -> None:
        """
        Invokes a post-commit hook to execute tasks after a user has entered a new version and changelog message, but
        before any changes are committed. Commonly used to modify files to be included in the release commit.

        :param root_directory: The root project directory
        :param old_version: The version of the project before release
        :param new_version: The version of the project after release

        :raise: ReleaseFailure
        """

    def pre_push(self, root_directory: str, old_version: str, new_version: str) -> None:
        """
        Invokes a pre-push hook to execute tasks after the release commit has been completed but before the tag is
        created or the changes pushed.

        :param root_directory: The root project directory
        :param old_version: The version of the project before release
        :param new_version: The version of the project after release

        :raise: ReleaseFailure
        """

    def post_release(self, root_directory: str, old_version: str, new_version: str, status: ReleaseStatus) -> None:
        """
        Invokes a post-release hook to execute tasks after the release has completed or rolled back. Will not be called
        if the release is halted due to a `ReleaseFailure` or premature exit.

        :param root_directory: The root project directory
        :param old_version: The version of the project before release
        :param new_version: The version of the project after release
        :param status: A flag indicating whether the release was pushed, not pushed, or rolled back.

        :raise: ReleaseFailure
        """

    def pre_rollback(self, root_directory: str, current_version: str) -> None:
        """
        Invokes a pre-rollback hook to execute tasks before a call to `rollback-release` proceeds. Can be used to run
        pre-rollback checks and cancel the rollback if some condition is met or not met.

        :param root_directory: The root project directory
        :param current_version: The version of the project before rollback

        :raise: ReleaseFailure
        """

    def post_rollback(self, root_directory: str, current_version: str, rollback_to_version: str):
        """
        Invokes a post-rollback hook to execute tasks after a call to `rollback-release` has succeeded. Will not be
        called if the task fails or is canceled for any reason.

        :param root_directory: The root project directory
        :param current_version: The version of the project before rollback
        :param rollback_to_version: The version of the project after rollback

        :raise: ReleaseFailure
        """
