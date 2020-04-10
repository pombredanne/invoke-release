from typing import Generator
from unittest import mock

import pytest

from invoke_release.errors import ReleaseFailure
from invoke_release.tasks import rollback_release
from invoke_release.version import __version__

from tests import InteractiveTester
from tests.unit import TaskBootstrap


@pytest.fixture(scope='function')
def module_being_tested() -> str:
    return 'invoke_release.tasks.rollback_release_task'


@pytest.fixture(scope='function')
def mock_read_project_version() -> Generator[mock.MagicMock, None, None]:
    with mock.patch('invoke_release.tasks.rollback_release_task.read_project_version') as m:
        yield m


@pytest.fixture(scope='function')
def mock_pre_rollback() -> Generator[mock.MagicMock, None, None]:
    with mock.patch('invoke_release.tasks.rollback_release_task.pre_rollback') as m:
        yield m


@pytest.fixture(scope='function')
def mock_post_rollback() -> Generator[mock.MagicMock, None, None]:
    with mock.patch('invoke_release.tasks.rollback_release_task.post_rollback') as m:
        yield m


def test_not_configured(task_bootstrap: TaskBootstrap, mock_read_project_version: mock.MagicMock) -> None:
    task_bootstrap.config.is_configured = False
    task_bootstrap.io.error_output_exit.side_effect = SystemExit

    with pytest.raises(SystemExit):
        rollback_release.body('', verbose=True, no_stash=False)

    task_bootstrap.io_constructor.assert_called_once_with(True)
    task_bootstrap.io.error_output_exit.assert_called_once_with(
        'Cannot `invoke rollback_release` before calling `invoke_release.config.config.configure`.',
    )

    assert mock_read_project_version.call_count == 0


def test_master_pre_rollback_failed(
    task_bootstrap: TaskBootstrap,
    mock_read_project_version: mock.MagicMock,
    mock_pre_rollback: mock.MagicMock,
) -> None:
    task_bootstrap.config.is_configured = True
    task_bootstrap.config.module_name = 'extra_library'
    task_bootstrap.config.display_name = 'My Extra Library'
    task_bootstrap.config.release_message_template = 'Released My Extra Library version {}'
    task_bootstrap.config.version_file_name = '/path/to/extra_library/extra_library/version.txt'
    task_bootstrap.config.master_branch = 'development'

    tester = InteractiveTester(
        task_bootstrap.io,
        rollback_release,
        [task_bootstrap.source, mock_read_project_version],
        verbose=True,
        no_stash=False,
    )

    mock_read_project_version.return_value = '4.5.1'
    mock_pre_rollback.side_effect = ReleaseFailure('No worky!')
    task_bootstrap.source.get_branch_name.return_value = 'development'
    task_bootstrap.io.error_output_exit.side_effect = SystemExit

    tester.start()

    tester.wait_for_finish()

    mock_read_project_version.assert_called_once_with(
        'extra_library',
        '/path/to/extra_library/extra_library/version.txt',
    )
    assert mock_pre_rollback.call_count == 1
    assert mock_pre_rollback.call_args[0][1] == '4.5.1'
    task_bootstrap.source.get_branch_name.assert_called_once_with()

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Invoke Release {}', __version__)
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_has_calls([
        mock.call('No worky!')
    ], any_order=False)


def test_not_master_exit_at_prompt(
    task_bootstrap: TaskBootstrap,
    mock_read_project_version: mock.MagicMock,
) -> None:
    task_bootstrap.config.is_configured = True
    task_bootstrap.config.module_name = 'extra_library'
    task_bootstrap.config.display_name = 'My Extra Library'
    task_bootstrap.config.release_message_template = 'Released My Extra Library version {}'
    task_bootstrap.config.version_file_name = '/path/to/extra_library/extra_library/version.txt'
    task_bootstrap.config.master_branch = 'root'

    tester = InteractiveTester(
        task_bootstrap.io,
        rollback_release,
        [task_bootstrap.source, mock_read_project_version],
        verbose=True,
        no_stash=False,
    )

    mock_read_project_version.return_value = '4.5.1'
    task_bootstrap.source.get_branch_name.return_value = 'development'

    tester.start()

    prompt = tester.wait_for_prompt()

    mock_read_project_version.assert_called_once_with(
        'extra_library',
        '/path/to/extra_library/extra_library/version.txt',
    )
    task_bootstrap.source.get_branch_name.assert_called_once_with()

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Invoke Release {}', __version__)
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == (
        'You are currently on branch "{branch}" instead of "{master}." Rolling back on a branch other than '
        '{master} can be dangerous.\nAre you sure you want to continue rolling back on "{branch}?" (y/N):'
    )
    assert prompt.args == ()
    assert prompt.kwargs == {
        'branch': 'development',
        'master': 'root',
    }

    tester.respond_to_prompt('n')

    tester.wait_for_finish()

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Canceling release rollback!')
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()


def test_not_master_continue_at_prompt_last_commit_not_release_commit(
    task_bootstrap: TaskBootstrap,
    mock_read_project_version: mock.MagicMock,
) -> None:
    task_bootstrap.config.is_configured = True
    task_bootstrap.config.module_name = 'extra_library'
    task_bootstrap.config.display_name = 'My Extra Library'
    task_bootstrap.config.release_message_template = 'Released My Extra Library version {}'
    task_bootstrap.config.version_file_name = '/path/to/extra_library/extra_library/version.txt'
    task_bootstrap.config.master_branch = 'master'

    tester = InteractiveTester(
        task_bootstrap.io,
        rollback_release,
        [task_bootstrap.source, mock_read_project_version],
        verbose=True,
        no_stash=False,
    )

    mock_read_project_version.return_value = '4.5.1'
    task_bootstrap.source.get_branch_name.return_value = '4.5.x'

    tester.start()

    prompt = tester.wait_for_prompt()

    mock_read_project_version.assert_called_once_with(
        'extra_library',
        '/path/to/extra_library/extra_library/version.txt',
    )
    task_bootstrap.source.get_branch_name.assert_called_once_with()

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Invoke Release {}', __version__)
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == (
        'You are currently on branch "{branch}" instead of "{master}." Rolling back on a branch other than '
        '{master} can be dangerous.\nAre you sure you want to continue rolling back on "{branch}?" (y/N):'
    )
    assert prompt.args == ()
    assert prompt.kwargs == {
        'branch': '4.5.x',
        'master': 'master',
    }

    task_bootstrap.source.stash_changes.return_value = False
    task_bootstrap.source.get_last_commit_identifier.return_value = '1234abc'
    task_bootstrap.source.get_commit_title.return_value = 'Not a release commit'

    tester.respond_to_prompt('y')

    tester.wait_for_finish()

    task_bootstrap.source.stash_changes.assert_called_once_with()
    task_bootstrap.source.get_last_commit_identifier.assert_called_once_with()
    task_bootstrap.source.get_commit_title.assert_called_once_with('1234abc')
    assert task_bootstrap.source.unstash_changes.call_count == 0

    task_bootstrap.io.standard_output.assert_not_called()
    task_bootstrap.io.error_output.assert_has_calls([
        mock.call('Cannot roll back because last commit is not the release commit.'),
    ], any_order=False)
    task_bootstrap.io.error_output_exit.assert_not_called()


def test_release_on_multiple_remote_branches(
    task_bootstrap: TaskBootstrap,
    mock_read_project_version: mock.MagicMock,
) -> None:
    task_bootstrap.config.is_configured = True
    task_bootstrap.config.module_name = 'extra_library'
    task_bootstrap.config.display_name = 'My Extra Library'
    task_bootstrap.config.release_message_template = 'Released My Extra Library version {}'
    task_bootstrap.config.version_file_name = '/path/to/extra_library/extra_library/version.txt'
    task_bootstrap.config.master_branch = 'master'

    tester = InteractiveTester(
        task_bootstrap.io,
        rollback_release,
        [task_bootstrap.source, mock_read_project_version],
        verbose=True,
        no_stash=False,
    )

    mock_read_project_version.return_value = '4.5.1'
    task_bootstrap.source.get_branch_name.return_value = 'master'
    task_bootstrap.source.stash_changes.return_value = True
    task_bootstrap.source.get_last_commit_identifier.return_value = 'abc1234'
    task_bootstrap.source.get_commit_title.return_value = 'Released My Extra Library version 4.5.1'
    task_bootstrap.source.get_remote_branches_with_commit.return_value = ['origin/master', 'origin/4.5.x']

    tester.start()

    tester.wait_for_finish()

    mock_read_project_version.assert_called_once_with(
        'extra_library',
        '/path/to/extra_library/extra_library/version.txt',
    )
    task_bootstrap.source.get_branch_name.assert_called_once_with()
    task_bootstrap.source.stash_changes.assert_called_once_with()
    task_bootstrap.source.get_last_commit_identifier.assert_called_once_with()
    task_bootstrap.source.get_commit_title.assert_called_once_with('abc1234')
    task_bootstrap.source.unstash_changes.assert_called_once_with()

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Invoke Release {}', __version__)
    ], any_order=False)
    task_bootstrap.io.error_output.assert_has_calls([
        mock.call(
            f"Cannot roll back because release commit is on multiple remote "
            f"branches: {['origin/master', 'origin/4.5.x']}",
        )
    ], any_order=False)
    task_bootstrap.io.error_output_exit.assert_not_called()


def test_release_on_inconsequential_remote_branch_exit_at_prompt(
    task_bootstrap: TaskBootstrap,
    mock_read_project_version: mock.MagicMock,
) -> None:
    task_bootstrap.config.is_configured = True
    task_bootstrap.config.module_name = 'extra_library'
    task_bootstrap.config.display_name = 'My Extra Library'
    task_bootstrap.config.release_message_template = 'Released My Extra Library version {}'
    task_bootstrap.config.version_file_name = '/path/to/extra_library/extra_library/version.txt'
    task_bootstrap.config.master_branch = 'master'

    tester = InteractiveTester(
        task_bootstrap.io,
        rollback_release,
        [task_bootstrap.source, mock_read_project_version],
        verbose=True,
        no_stash=False,
    )

    mock_read_project_version.return_value = '4.5.1'
    task_bootstrap.source.get_branch_name.return_value = 'master'
    task_bootstrap.source.stash_changes.return_value = True
    task_bootstrap.source.get_last_commit_identifier.return_value = 'abc1234'
    task_bootstrap.source.get_commit_title.return_value = 'Released My Extra Library version 4.5.1'
    task_bootstrap.source.get_remote_branches_with_commit.return_value = ['origin/test_something']

    tester.start()

    prompt = tester.wait_for_prompt()

    mock_read_project_version.assert_called_once_with(
        'extra_library',
        '/path/to/extra_library/extra_library/version.txt',
    )
    task_bootstrap.source.get_branch_name.assert_called_once_with()
    task_bootstrap.source.stash_changes.assert_called_once_with()
    task_bootstrap.source.get_last_commit_identifier.assert_called_once_with()
    task_bootstrap.source.get_commit_title.assert_called_once_with('abc1234')
    assert task_bootstrap.source.unstash_changes.call_count == 0

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Release tag {} will be deleted locally and remotely (if applicable).', '4.5.1'),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == 'Do you want to proceed with deleting this tag? (y/N):'
    assert prompt.args == ()
    assert prompt.kwargs == {}

    tester.respond_to_prompt('n')

    tester.wait_for_finish()

    task_bootstrap.source.unstash_changes.assert_called_once_with()

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Canceling release rollback!'),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()


def test_release_on_no_remote_branch_continue_at_prompt(
    task_bootstrap: TaskBootstrap,
    mock_read_project_version: mock.MagicMock,
    mock_post_rollback: mock.MagicMock,
) -> None:
    task_bootstrap.config.is_configured = True
    task_bootstrap.config.module_name = 'extra_library'
    task_bootstrap.config.display_name = 'My Extra Library'
    task_bootstrap.config.release_message_template = 'Released My Extra Library version {}'
    task_bootstrap.config.version_file_name = '/path/to/extra_library/extra_library/version.txt'
    task_bootstrap.config.master_branch = 'master'

    tester = InteractiveTester(
        task_bootstrap.io,
        rollback_release,
        [task_bootstrap.source, mock_read_project_version],
        verbose=True,
        no_stash=True,
    )

    mock_read_project_version.return_value = '4.5.1'
    task_bootstrap.source.get_branch_name.return_value = 'master'
    task_bootstrap.source.stash_changes.return_value = True
    task_bootstrap.source.get_last_commit_identifier.return_value = 'abc1234'
    task_bootstrap.source.get_commit_title.return_value = 'Released My Extra Library version 4.5.1'
    task_bootstrap.source.get_remote_branches_with_commit.return_value = []

    tester.start()

    prompt = tester.wait_for_prompt()

    mock_read_project_version.assert_called_once_with(
        'extra_library',
        '/path/to/extra_library/extra_library/version.txt',
    )
    task_bootstrap.source.get_branch_name.assert_called_once_with()
    assert task_bootstrap.source.stash_changes.call_count == 0
    task_bootstrap.source.get_last_commit_identifier.assert_called_once_with()
    task_bootstrap.source.get_commit_title.assert_called_once_with('abc1234')
    assert task_bootstrap.source.unstash_changes.call_count == 0

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Release tag {} will be deleted locally and remotely (if applicable).', '4.5.1'),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == 'Do you want to proceed with deleting this tag? (y/N):'
    assert prompt.args == ()
    assert prompt.kwargs == {}

    task_bootstrap.source.tag_exists_locally.return_value = False
    task_bootstrap.source.tag_exists_remotely.return_value = False

    tester.respond_to_prompt('y')

    prompt = tester.wait_for_prompt()

    task_bootstrap.source.tag_exists_locally.assert_called_once_with('4.5.1')
    task_bootstrap.source.tag_exists_remotely.assert_called_once_with('4.5.1')
    assert task_bootstrap.source.delete_tag_locally.call_count == 0
    assert task_bootstrap.source.delete_tag_remotely.call_count == 0

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('The release tag has been deleted from local and remote (if applicable).'),
        mock.call('The release commit is only present locally, not on the remote origin.'),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == 'Are you ready to delete the commit like it never happened? (y/N):'
    assert prompt.args == ()
    assert prompt.kwargs == {}

    mock_read_project_version.return_value = '4.5.0'

    tester.respond_to_prompt('y')

    tester.wait_for_finish()

    assert task_bootstrap.source.revert_commit.call_count == 0
    task_bootstrap.source.delete_last_local_commit.assert_called_once_with()
    mock_read_project_version.assert_called_once_with(
        'extra_library',
        '/path/to/extra_library/extra_library/version.txt',
        reload=True,
    )
    assert task_bootstrap.source.unstash_changes.call_count == 0
    assert mock_post_rollback.call_count == 1
    assert mock_post_rollback.call_args[0][1] == '4.5.1'
    assert mock_post_rollback.call_args[0][2] == '4.5.0'


def test_release_on_master_remote_branch_continue_at_prompt(
    task_bootstrap: TaskBootstrap,
    mock_read_project_version: mock.MagicMock,
    mock_post_rollback: mock.MagicMock,
) -> None:
    task_bootstrap.config.is_configured = True
    task_bootstrap.config.module_name = 'extra_library'
    task_bootstrap.config.display_name = 'My Extra Library'
    task_bootstrap.config.release_message_template = 'Released My Extra Library version {}'
    task_bootstrap.config.version_file_name = '/path/to/extra_library/extra_library/version.txt'
    task_bootstrap.config.master_branch = 'master'

    tester = InteractiveTester(
        task_bootstrap.io,
        rollback_release,
        [task_bootstrap.source, mock_read_project_version],
        verbose=True,
        no_stash=True,
    )

    mock_read_project_version.return_value = '4.5.1'
    task_bootstrap.source.get_branch_name.return_value = 'master'
    task_bootstrap.source.stash_changes.return_value = True
    task_bootstrap.source.get_last_commit_identifier.return_value = 'def5678'
    task_bootstrap.source.get_commit_title.return_value = 'Released My Extra Library version 4.5.1'
    task_bootstrap.source.get_remote_branches_with_commit.return_value = ['origin/master']

    tester.start()

    prompt = tester.wait_for_prompt()

    mock_read_project_version.assert_called_once_with(
        'extra_library',
        '/path/to/extra_library/extra_library/version.txt',
    )
    task_bootstrap.source.get_branch_name.assert_called_once_with()
    assert task_bootstrap.source.stash_changes.call_count == 0
    task_bootstrap.source.get_last_commit_identifier.assert_called_once_with()
    task_bootstrap.source.get_commit_title.assert_called_once_with('def5678')
    assert task_bootstrap.source.unstash_changes.call_count == 0

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Release tag {} will be deleted locally and remotely (if applicable).', '4.5.1'),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == 'Do you want to proceed with deleting this tag? (y/N):'
    assert prompt.args == ()
    assert prompt.kwargs == {}

    task_bootstrap.source.tag_exists_locally.return_value = True
    task_bootstrap.source.tag_exists_remotely.return_value = True

    tester.respond_to_prompt('y')

    prompt = tester.wait_for_prompt()

    task_bootstrap.source.tag_exists_locally.assert_called_once_with('4.5.1')
    task_bootstrap.source.tag_exists_remotely.assert_called_once_with('4.5.1')
    task_bootstrap.source.delete_tag_locally.assert_called_once_with('4.5.1')
    task_bootstrap.source.delete_tag_remotely.assert_called_once_with('4.5.1')

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('The release tag has been deleted from local and remote (if applicable).'),
        mock.call('The release commit is present on the remote origin.'),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == 'Do you want to revert the commit and immediately push it to the remote origin? (y/N):'
    assert prompt.args == ()
    assert prompt.kwargs == {}

    mock_read_project_version.return_value = '4.5.0'

    tester.respond_to_prompt('y')

    tester.wait_for_finish()

    task_bootstrap.source.revert_commit.assert_called_once_with('def5678', 'master')
    assert task_bootstrap.source.delete_last_local_commit.call_count == 0
    mock_read_project_version.assert_called_once_with(
        'extra_library',
        '/path/to/extra_library/extra_library/version.txt',
        reload=True,
    )
    assert task_bootstrap.source.unstash_changes.call_count == 0
    assert mock_post_rollback.call_count == 1
    assert mock_post_rollback.call_args[0][1] == '4.5.1'
    assert mock_post_rollback.call_args[0][2] == '4.5.0'


def test_release_on_master_remote_branch_do_not_revert_commit(
    task_bootstrap: TaskBootstrap,
    mock_read_project_version: mock.MagicMock,
    mock_post_rollback: mock.MagicMock,
) -> None:
    task_bootstrap.config.is_configured = True
    task_bootstrap.config.module_name = 'extra_library'
    task_bootstrap.config.display_name = 'My Extra Library'
    task_bootstrap.config.release_message_template = 'Released My Extra Library version {}'
    task_bootstrap.config.version_file_name = '/path/to/extra_library/extra_library/version.txt'
    task_bootstrap.config.master_branch = 'master'

    tester = InteractiveTester(
        task_bootstrap.io,
        rollback_release,
        [task_bootstrap.source, mock_read_project_version],
        verbose=True,
        no_stash=True,
    )

    mock_read_project_version.return_value = '4.5.1'
    task_bootstrap.source.get_branch_name.return_value = 'master'
    task_bootstrap.source.stash_changes.return_value = True
    task_bootstrap.source.get_last_commit_identifier.return_value = 'def5678'
    task_bootstrap.source.get_commit_title.return_value = 'Released My Extra Library version 4.5.1'
    task_bootstrap.source.get_remote_branches_with_commit.return_value = ['origin/master']

    tester.start()

    prompt = tester.wait_for_prompt()

    mock_read_project_version.assert_called_once_with(
        'extra_library',
        '/path/to/extra_library/extra_library/version.txt',
    )
    task_bootstrap.source.get_branch_name.assert_called_once_with()
    assert task_bootstrap.source.stash_changes.call_count == 0
    task_bootstrap.source.get_last_commit_identifier.assert_called_once_with()
    task_bootstrap.source.get_commit_title.assert_called_once_with('def5678')
    assert task_bootstrap.source.unstash_changes.call_count == 0

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Release tag {} will be deleted locally and remotely (if applicable).', '4.5.1'),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == 'Do you want to proceed with deleting this tag? (y/N):'
    assert prompt.args == ()
    assert prompt.kwargs == {}

    task_bootstrap.source.tag_exists_locally.return_value = True
    task_bootstrap.source.tag_exists_remotely.return_value = True

    tester.respond_to_prompt('y')

    prompt = tester.wait_for_prompt()

    task_bootstrap.source.tag_exists_locally.assert_called_once_with('4.5.1')
    task_bootstrap.source.tag_exists_remotely.assert_called_once_with('4.5.1')
    task_bootstrap.source.delete_tag_locally.assert_called_once_with('4.5.1')
    task_bootstrap.source.delete_tag_remotely.assert_called_once_with('4.5.1')

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('The release tag has been deleted from local and remote (if applicable).'),
        mock.call('The release commit is present on the remote origin.'),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == 'Do you want to revert the commit and immediately push it to the remote origin? (y/N):'
    assert prompt.args == ()
    assert prompt.kwargs == {}

    mock_read_project_version.return_value = '4.5.1'

    tester.respond_to_prompt('n')

    tester.wait_for_finish()

    assert task_bootstrap.source.revert_commit.call_count == 0
    assert task_bootstrap.source.delete_last_local_commit.call_count == 0
    mock_read_project_version.assert_called_once_with(
        'extra_library',
        '/path/to/extra_library/extra_library/version.txt',
        reload=True,
    )
    assert task_bootstrap.source.unstash_changes.call_count == 0
    assert mock_post_rollback.call_count == 1
    assert mock_post_rollback.call_args[0][1] == '4.5.1'
    assert mock_post_rollback.call_args[0][2] == '4.5.1'
