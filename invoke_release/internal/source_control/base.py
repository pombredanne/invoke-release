from __future__ import annotations

import abc
from enum import Enum
from typing import (
    TYPE_CHECKING,
    List,
    Optional,
)


if TYPE_CHECKING:
    from invoke_release.internal.context import TaskContext


__all__ = (
    'ItemType',
    'SourceControl',
)


class ItemType(Enum):
    BRANCH = 'branch'
    TAG = 'tag'


class SourceControl(metaclass=abc.ABCMeta):
    def __init__(self, context: TaskContext) -> None:
        self._context = context

    @property
    @abc.abstractmethod
    def supports_gpg_signing(self) -> bool:
        """
        Indicates whether this source control supports GPG signing commits and tags.

        :return: `True` if signing is supported, `False` otherwise.
        """

    @abc.abstractmethod
    def get_version(self) -> str:
        """
        Return the version info for this source control provider.

        :return: the version info.
        """

    @staticmethod
    @abc.abstractmethod
    def get_root_directory() -> str:
        """
        Fetch the root directory for this project.

        :return: the root directory.
        """

    @abc.abstractmethod
    def get_branch_name(self) -> str:
        """
        Fetch the current branch name.

        :return: the branch name.
        """

    @abc.abstractmethod
    def create_branch(
        self,
        branch_name: str,
        from_item: Optional[str] = None,
        from_item_type: ItemType = ItemType.BRANCH
    ) -> None:
        """
        Create a new branch.

        :param branch_name: The name of the branch to create
        :param from_item: If specified, this item will be checked out and the new branch created from its head
        :param from_item_type: Indicates the item type for from_item (defaults to a branch)
        """

    @abc.abstractmethod
    def checkout_remote_branch(self, branch_name: str) -> None:
        """
        Create a local branch tracking the named remote branch.

        :param branch_name: The name of the branch to checkout and track
        """

    @abc.abstractmethod
    def delete_branch(self, branch_name: str) -> None:
        """
        Delete a branch.

        :param branch_name: The name of the branch to delete
        """

    @abc.abstractmethod
    def branch_exists_remotely(self, branch_name: str) -> bool:
        """
        Determine if the branch is on remote.

        :param branch_name: The name of the branch to check

        :return: `True` if the branch is on remote, `False` otherwise
        """

    @abc.abstractmethod
    def get_remote_branches_with_commit(self, commit_id: str) -> List[str]:
        """
        Get all remote branches that contain the given commit.

        :param commit_id: The commit identifier

        :return: the list of branches that contain the given commit.
        """

    @abc.abstractmethod
    def create_tag(self, tag_name: str, tag_message: str) -> None:
        """
        Create a tag.

        :param tag_name: The tag name
        :param tag_message: The tag message
        """

    @abc.abstractmethod
    def delete_tag_locally(self, tag_name: str) -> None:
        """
        Delete a tag locally.

        :param tag_name: The tag name
        """

    @abc.abstractmethod
    def delete_tag_remotely(self, tag_name: str) -> None:
        """
        Delete a tag remotely.

        :param tag_name: The tag name
        """

    @abc.abstractmethod
    def fetch_remote_tags(self) -> None:
        """
        Fetch all remote tags not present locally.
        """

    @abc.abstractmethod
    def list_tags(self) -> List[str]:
        """
        List all tags.

        :return: the list of all tags.
        """

    @abc.abstractmethod
    def tag_exists_remotely(self, tag_name: str) -> bool:
        """
        Determine if the tag is on remote.

        :param tag_name: The name of the tag to check

        :return: `True` if the tag is on remote, `False` otherwise.
        """

    @abc.abstractmethod
    def tag_exists_locally(self, tag_name: str) -> bool:
        """
        Determine if the tag exists locally.

        :param tag_name: The name of the tag to check

        :return: `True` if the tag exists locally, `False` otherwise.
        """

    @abc.abstractmethod
    def checkout_item(self, item_name: str) -> None:
        """
        Check out a branch or tag.

        :param item_name: The name of the branch or tag to checkout
        """

    @abc.abstractmethod
    def delete_last_local_commit(self) -> None:
        """
        Delete the last local commit like it never existed.
        """

    @abc.abstractmethod
    def revert_commit(self, commit_id: str, branch_name: str) -> None:
        """
        Create a reverting commit of the given commit and push it to the origin.

        :param commit_id: The commit identifier
        :param branch_name: The name of the branch from which to revert the commit
        """

    @abc.abstractmethod
    def stash_changes(self) -> bool:
        """
        Stashes any pending changes so that the task can execute.

        :return: `True` if changes were stashed, `False` if no changes were stashed
        """

    @abc.abstractmethod
    def unstash_changes(self) -> None:
        """
        Un-stashes any pending changes that were stashed before the task executed.
        """

    @abc.abstractmethod
    def gather_commit_messages_since_last_release(self) -> List[str]:
        """
        Get all commit messages that occurred since the last release.

        :return: the list of commit messages.
        """

    @abc.abstractmethod
    def reset_pending_changes(self) -> None:
        """
        Reset all pending changes that have not yet been committed.
        """

    @abc.abstractmethod
    def commit(self, files: List[str], message: str) -> None:
        """
        Stage and commit changes.

        :param files: The list of files to stage
        :param message: The commit message
        """

    @abc.abstractmethod
    def push(self, item: str, item_type: ItemType = ItemType.BRANCH, set_tracking: bool = False) -> None:
        """
        Push the given branch or tag to the remote origin.

        :param item: The branch or tag name
        :param item_type: The type of the item being pushed
        :param set_tracking: Whether to set the local branch to track the remote branch to which this was pushed
        """

    @abc.abstractmethod
    def pull_if_tracking_remote(self) -> bool:
        """
        If the current branch is tracking a remote branch, pull it to get its latest changes.
        """

    @abc.abstractmethod
    def get_last_commit_identifier(self) -> str:
        """
        Return the identifier of the most-recent commit at the current head.

        :return: the commit identifier.
        """

    @abc.abstractmethod
    def get_commit_title(self, commit_id: str) -> str:
        """
        Return the title (the first line of the commit message, excluding message/details) of the given commit.

        :param commit_id: The commit identifier

        :return: the commit title.
        """

    @abc.abstractmethod
    def open_pull_request(self, title: str, base: str, head: str) -> Optional[str]:
        """
        Open a pull request or equivalent.

        :return: The URL for the pull request, or `None` if one was not opened.
        """
