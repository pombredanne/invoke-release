from unittest import mock

import pytest

from invoke_release.internal.context import TaskContext
from invoke_release.internal.plugins import (
    get_extra_files_to_commit,
    post_release,
    post_rollback,
    pre_commit,
    pre_push,
    pre_release,
    pre_rollback,
)
from invoke_release.plugins.base import ReleaseStatus


@pytest.fixture(scope='function')
def mock_config() -> mock.MagicMock:
    mock_config = mock.MagicMock()
    mock_config.root_directory = '/path/to/root/dir'
    mock_config.plugins = [
        mock.MagicMock(),
        mock.MagicMock(),
    ]
    return mock_config


def test_get_extra_files_to_commit(mock_config: mock.MagicMock, task_context: TaskContext) -> None:
    mock_config.plugins[0].get_extra_files_to_commit.return_value = (f for f in ['file1.rst', 'file2.md'])
    mock_config.plugins[1].get_extra_files_to_commit.return_value = (f for f in ['file1.rst', 'file3.txt', 'file4.py'])

    extra_files = get_extra_files_to_commit(task_context)
    assert 'file1.rst' in extra_files
    assert 'file2.md' in extra_files
    assert 'file3.txt' in extra_files
    assert 'file4.py' in extra_files
    assert len(extra_files) == 4


def test_pre_release(mock_config: mock.MagicMock, task_context: TaskContext) -> None:
    pre_release(task_context, '1.2.3')

    mock_config.plugins[0].pre_release.assert_called_once_with('/path/to/root/dir', '1.2.3')
    mock_config.plugins[1].pre_release.assert_called_once_with('/path/to/root/dir', '1.2.3')


def test_pre_commit(mock_config: mock.MagicMock, task_context: TaskContext) -> None:
    pre_commit(task_context, '1.2.3', '1.3.0')

    mock_config.plugins[0].pre_commit.assert_called_once_with('/path/to/root/dir', '1.2.3', '1.3.0')
    mock_config.plugins[1].pre_commit.assert_called_once_with('/path/to/root/dir', '1.2.3', '1.3.0')


def test_pre_push(mock_config: mock.MagicMock, task_context: TaskContext) -> None:
    pre_push(task_context, '1.2.3', '1.3.0')

    mock_config.plugins[0].pre_push.assert_called_once_with('/path/to/root/dir', '1.2.3', '1.3.0')
    mock_config.plugins[1].pre_push.assert_called_once_with('/path/to/root/dir', '1.2.3', '1.3.0')


def test_post_release(mock_config: mock.MagicMock, task_context: TaskContext) -> None:
    post_release(task_context, '1.2.3', '1.3.0', ReleaseStatus.PUSHED)

    mock_config.plugins[0].post_release.assert_called_once_with(
        '/path/to/root/dir',
        '1.2.3',
        '1.3.0',
        ReleaseStatus.PUSHED,
    )
    mock_config.plugins[1].post_release.assert_called_once_with(
        '/path/to/root/dir',
        '1.2.3',
        '1.3.0',
        ReleaseStatus.PUSHED,
    )


def test_pre_rollback(mock_config: mock.MagicMock, task_context: TaskContext) -> None:
    pre_rollback(task_context, '1.3.0')

    mock_config.plugins[0].pre_rollback.assert_called_once_with('/path/to/root/dir', '1.3.0')
    mock_config.plugins[1].pre_rollback.assert_called_once_with('/path/to/root/dir', '1.3.0')


def test_post_rollback(mock_config: mock.MagicMock, task_context: TaskContext) -> None:
    post_rollback(task_context, '1.3.0', '1.2.3')

    mock_config.plugins[0].post_rollback.assert_called_once_with('/path/to/root/dir', '1.3.0', '1.2.3')
    mock_config.plugins[1].post_rollback.assert_called_once_with('/path/to/root/dir', '1.3.0', '1.2.3')
