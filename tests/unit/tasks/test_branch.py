from unittest import mock

import pytest

from invoke_release.errors import SourceControlError
from invoke_release.internal.source_control.base import ItemType
from invoke_release.tasks import branch
from invoke_release.version import __version__

from tests import InteractiveTester
from tests.unit import TaskBootstrap


@pytest.fixture(scope='function')
def module_being_tested() -> str:
    return 'invoke_release.tasks.branch_task'


def test_not_configured(task_bootstrap: TaskBootstrap) -> None:
    task_bootstrap.config.is_configured = False
    task_bootstrap.io.error_output_exit.side_effect = SystemExit

    with pytest.raises(SystemExit):
        branch.body('', verbose=True, no_stash=False)

    task_bootstrap.io_constructor.assert_called_once_with(True)
    task_bootstrap.io.error_output_exit.assert_called_once_with(
        'Cannot `invoke branch` before calling `invoke_release.config.config.configure`.',
    )


def test_exit_at_first_prompt(task_bootstrap: TaskBootstrap) -> None:
    task_bootstrap.config.is_configured = True

    tester = InteractiveTester(task_bootstrap.io, branch, [task_bootstrap.source], verbose=False, no_stash=False)

    task_bootstrap.source.stash_changes.return_value = False

    tester.start()

    prompt = tester.wait_for_prompt()

    task_bootstrap.io_constructor.assert_called_once_with(False)
    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Invoke Release {}', __version__),
    ], any_order=False)

    task_bootstrap.source.stash_changes.assert_called_once_with()

    assert prompt.message == 'Enter a version tag from which to create a new branch (or "exit"):'
    assert prompt.args == ()
    assert prompt.kwargs == {}

    tester.respond_to_prompt('exit')

    tester.wait_for_finish()

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Canceling branch!'),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()


def test_tag_does_not_exist(task_bootstrap: TaskBootstrap) -> None:
    task_bootstrap.config.is_configured = True

    tester = InteractiveTester(task_bootstrap.io, branch, [task_bootstrap.source], verbose=False, no_stash=False)

    task_bootstrap.source.stash_changes.return_value = False

    tester.start()

    prompt = tester.wait_for_prompt()

    task_bootstrap.io_constructor.assert_called_once_with(False)
    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Invoke Release {}', __version__),
    ], any_order=False)

    task_bootstrap.source.stash_changes.assert_called_once_with()

    assert prompt.message == 'Enter a version tag from which to create a new branch (or "exit"):'
    assert prompt.args == ()
    assert prompt.kwargs == {}

    task_bootstrap.source.list_tags.return_value = ['1.3.5', '1.3.6', '1.3.7']

    tester.respond_to_prompt('1.3.8')

    tester.wait_for_finish()

    task_bootstrap.io.standard_output.assert_not_called()
    task_bootstrap.io.error_output.assert_has_calls([
        mock.call('Version number 1.3.8 not in the list of available tags.'),
    ], any_order=False)

    task_bootstrap.source.fetch_remote_tags.assert_called_once_with()
    task_bootstrap.source.list_tags.assert_called_once_with()


def test_exit_at_second_prompt(task_bootstrap: TaskBootstrap) -> None:
    task_bootstrap.config.is_configured = True

    tester = InteractiveTester(task_bootstrap.io, branch, [task_bootstrap.source], verbose=False, no_stash=False)

    task_bootstrap.source.stash_changes.return_value = False

    tester.start()

    prompt = tester.wait_for_prompt()

    task_bootstrap.io_constructor.assert_called_once_with(False)
    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Invoke Release {}', __version__),
    ], any_order=False)

    task_bootstrap.source.stash_changes.assert_called_once_with()

    assert prompt.message == 'Enter a version tag from which to create a new branch (or "exit"):'
    assert prompt.args == ()
    assert prompt.kwargs == {}

    task_bootstrap.source.list_tags.return_value = ['1.3.5', '1.3.6', '1.3.7']

    tester.respond_to_prompt('1.3.7')

    prompt = tester.wait_for_prompt()

    task_bootstrap.io.standard_output.assert_not_called()
    task_bootstrap.io.error_output.assert_not_called()

    task_bootstrap.source.fetch_remote_tags.assert_called_once_with()
    task_bootstrap.source.list_tags.assert_called_once_with()

    assert prompt.message == (
        'Using tag {tag}, would you like to create a minor branch for patch versions (branch name {minor}, '
        'recommended), or a major branch for minor versions (branch name {major})? (MINOR/major/exit):'
    )
    assert prompt.args == ()
    assert prompt.kwargs == {'tag': '1.3.7', 'minor': '1.3.x', 'major': '1.x.x'}

    tester.respond_to_prompt('exit')

    tester.wait_for_finish()

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Canceling branch!'),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()


def test_no_pull_request_minor_branch_do_not_push(task_bootstrap: TaskBootstrap) -> None:
    task_bootstrap.config.is_configured = True
    task_bootstrap.config.use_pull_request = False

    tester = InteractiveTester(task_bootstrap.io, branch, [task_bootstrap.source], verbose=False, no_stash=False)

    task_bootstrap.source.stash_changes.return_value = True

    tester.start()

    prompt = tester.wait_for_prompt()

    task_bootstrap.io_constructor.assert_called_once_with(False)
    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Invoke Release {}', __version__),
    ], any_order=False)

    task_bootstrap.source.stash_changes.assert_called_once_with()

    assert prompt.message == 'Enter a version tag from which to create a new branch (or "exit"):'
    assert prompt.args == ()
    assert prompt.kwargs == {}

    task_bootstrap.source.list_tags.return_value = ['1.3.5', '1.3.6', '1.3.7']

    tester.respond_to_prompt('1.3.7')

    prompt = tester.wait_for_prompt()

    task_bootstrap.io.standard_output.assert_not_called()
    task_bootstrap.io.error_output.assert_not_called()

    task_bootstrap.source.fetch_remote_tags.assert_called_once_with()
    task_bootstrap.source.list_tags.assert_called_once_with()

    assert prompt.message == (
        'Using tag {tag}, would you like to create a minor branch for patch versions (branch name {minor}, '
        'recommended), or a major branch for minor versions (branch name {major})? (MINOR/major/exit):'
    )
    assert prompt.args == ()
    assert prompt.kwargs == {'tag': '1.3.7', 'minor': '1.3.x', 'major': '1.x.x'}

    tester.respond_to_prompt('minor')

    prompt = tester.wait_for_prompt()

    task_bootstrap.source.create_branch.assert_called_once_with('1.3.x', '1.3.7', from_item_type=ItemType.TAG)

    assert prompt.message == 'Branch {} created. Would you like to go ahead and push it to remote? (y/N):'
    assert prompt.args == ('1.3.x', )
    assert prompt.kwargs == {}

    tester.respond_to_prompt('')

    tester.wait_for_finish()

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Branch process is complete.'),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()

    task_bootstrap.source.unstash_changes.assert_called_once_with()
    assert task_bootstrap.source.push.call_count == 0


def test_no_pull_request_major_branch_do_push(task_bootstrap: TaskBootstrap) -> None:
    task_bootstrap.config.is_configured = True
    task_bootstrap.config.use_pull_request = False

    tester = InteractiveTester(task_bootstrap.io, branch, [task_bootstrap.source], verbose=False, no_stash=False)

    task_bootstrap.source.stash_changes.return_value = False

    tester.start()

    prompt = tester.wait_for_prompt()

    task_bootstrap.io_constructor.assert_called_once_with(False)
    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Invoke Release {}', __version__),
    ], any_order=False)

    task_bootstrap.source.stash_changes.assert_called_once_with()

    assert prompt.message == 'Enter a version tag from which to create a new branch (or "exit"):'
    assert prompt.args == ()
    assert prompt.kwargs == {}

    task_bootstrap.source.list_tags.return_value = ['1.3.5', '1.3.6', '1.3.7']

    tester.respond_to_prompt('1.3.7')

    prompt = tester.wait_for_prompt()

    task_bootstrap.io.standard_output.assert_not_called()
    task_bootstrap.io.error_output.assert_not_called()

    task_bootstrap.source.fetch_remote_tags.assert_called_once_with()
    task_bootstrap.source.list_tags.assert_called_once_with()

    assert prompt.message == (
        'Using tag {tag}, would you like to create a minor branch for patch versions (branch name {minor}, '
        'recommended), or a major branch for minor versions (branch name {major})? (MINOR/major/exit):'
    )
    assert prompt.args == ()
    assert prompt.kwargs == {'tag': '1.3.7', 'minor': '1.3.x', 'major': '1.x.x'}

    tester.respond_to_prompt('major')

    prompt = tester.wait_for_prompt()

    task_bootstrap.source.create_branch.assert_called_once_with('1.x.x', '1.3.7', from_item_type=ItemType.TAG)

    assert prompt.message == 'Branch {} created. Would you like to go ahead and push it to remote? (y/N):'
    assert prompt.args == ('1.x.x', )
    assert prompt.kwargs == {}

    tester.respond_to_prompt('y')

    tester.wait_for_finish()

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Branch process is complete.'),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()

    assert task_bootstrap.source.unstash_changes.call_count == 0
    task_bootstrap.source.push.assert_called_once_with('1.x.x', set_tracking=True)


def test_with_pull_request_minor_branch_fail_to_pull_branch(task_bootstrap: TaskBootstrap) -> None:
    task_bootstrap.config.is_configured = True
    task_bootstrap.config.use_pull_request = True

    tester = InteractiveTester(task_bootstrap.io, branch, [task_bootstrap.source], verbose=False, no_stash=True)

    task_bootstrap.source.stash_changes.return_value = False

    tester.start()

    prompt = tester.wait_for_prompt()

    task_bootstrap.io_constructor.assert_called_once_with(False)
    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Invoke Release {}', __version__),
    ], any_order=False)

    assert task_bootstrap.source.stash_changes.call_count == 0

    assert prompt.message == 'Enter a version tag from which to create a new branch (or "exit"):'
    assert prompt.args == ()
    assert prompt.kwargs == {}

    task_bootstrap.source.list_tags.return_value = ['1.3.5', '1.3.6', '1.3.7']

    tester.respond_to_prompt('1.3.7')

    prompt = tester.wait_for_prompt()

    task_bootstrap.io.standard_output.assert_not_called()
    task_bootstrap.io.error_output.assert_not_called()

    task_bootstrap.source.fetch_remote_tags.assert_called_once_with()
    task_bootstrap.source.list_tags.assert_called_once_with()

    assert prompt.message == (
        'Using tag {tag}, would you like to create a minor branch for patch versions (branch name {minor}, '
        'recommended), or a major branch for minor versions (branch name {major})? (MINOR/major/exit):'
    )
    assert prompt.args == ()
    assert prompt.kwargs == {'tag': '1.3.7', 'minor': '1.3.x', 'major': '1.x.x'}

    task_bootstrap.source.branch_exists_remotely.return_value = True
    task_bootstrap.source.checkout_remote_branch.side_effect = SourceControlError('No worky')

    tester.respond_to_prompt('minor')

    tester.wait_for_finish()

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Branch {branch} exists on remote. Checking it out into a local tracking branch.', branch='1.3.x'),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_has_calls([
        mock.call(
            f'Could not check out a local branch tracking remote branch 1.3.x. Does a local branch '
            f'named 1.3.x already exist?\nDelete or rename your local branch 1.3.x and try '
            f'again, or just pull your local branch to manually work against it.'
        ),
    ], any_order=False)

    task_bootstrap.source.branch_exists_remotely.assert_called_once_with('1.3.x')
    task_bootstrap.source.checkout_remote_branch.assert_called_once_with('1.3.x')
    assert task_bootstrap.source.unstash_changes.call_count == 0


def test_with_pull_request_minor_branch_pulled_existing_branch_skip_cp_branch(task_bootstrap: TaskBootstrap) -> None:
    task_bootstrap.config.is_configured = True
    task_bootstrap.config.use_pull_request = True

    tester = InteractiveTester(task_bootstrap.io, branch, [task_bootstrap.source], verbose=False, no_stash=False)

    task_bootstrap.source.stash_changes.return_value = False

    tester.start()

    prompt = tester.wait_for_prompt()

    task_bootstrap.io_constructor.assert_called_once_with(False)
    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Invoke Release {}', __version__),
    ], any_order=False)

    task_bootstrap.source.stash_changes.assert_called_once_with()

    assert prompt.message == 'Enter a version tag from which to create a new branch (or "exit"):'
    assert prompt.args == ()
    assert prompt.kwargs == {}

    task_bootstrap.source.list_tags.return_value = ['1.3.5', '1.3.6', '1.3.7']

    tester.respond_to_prompt('1.3.7')

    prompt = tester.wait_for_prompt()

    task_bootstrap.io.standard_output.assert_not_called()
    task_bootstrap.io.error_output.assert_not_called()

    task_bootstrap.source.fetch_remote_tags.assert_called_once_with()
    task_bootstrap.source.list_tags.assert_called_once_with()

    assert prompt.message == (
        'Using tag {tag}, would you like to create a minor branch for patch versions (branch name {minor}, '
        'recommended), or a major branch for minor versions (branch name {major})? (MINOR/major/exit):'
    )
    assert prompt.args == ()
    assert prompt.kwargs == {'tag': '1.3.7', 'minor': '1.3.x', 'major': '1.x.x'}

    task_bootstrap.source.branch_exists_remotely.return_value = True

    tester.respond_to_prompt('minor')

    prompt = tester.wait_for_prompt()

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Branch {branch} exists on remote. Checking it out into a local tracking branch.', branch='1.3.x'),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()

    task_bootstrap.source.branch_exists_remotely.assert_called_once_with('1.3.x')
    task_bootstrap.source.checkout_remote_branch.assert_called_once_with('1.3.x')

    assert prompt.message == (
        'Now you should create the branch where you will apply your changes. You need a token to uniquely\n'
        'identify your feature branch, such as a GitHub or JIRA issue.\n'
        f'Enter it here to create a branch named `cherry-pick-1.3.x-<entered_token>` (or SKIP to skip this step):'
    )

    tester.respond_to_prompt('skip')

    tester.wait_for_finish()

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Branch process is complete.'),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()

    assert task_bootstrap.source.create_branch.call_count == 0
    assert task_bootstrap.source.unstash_changes.call_count == 0


def test_with_pull_request_major_branch_create_two_branches(task_bootstrap: TaskBootstrap) -> None:
    task_bootstrap.config.is_configured = True
    task_bootstrap.config.use_pull_request = True

    tester = InteractiveTester(task_bootstrap.io, branch, [task_bootstrap.source], verbose=False, no_stash=False)

    task_bootstrap.source.stash_changes.return_value = False

    tester.start()

    prompt = tester.wait_for_prompt()

    task_bootstrap.io_constructor.assert_called_once_with(False)
    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Invoke Release {}', __version__),
    ], any_order=False)

    task_bootstrap.source.stash_changes.assert_called_once_with()

    assert prompt.message == 'Enter a version tag from which to create a new branch (or "exit"):'
    assert prompt.args == ()
    assert prompt.kwargs == {}

    task_bootstrap.source.list_tags.return_value = ['1.3.5', '1.3.6', '1.3.7']

    tester.respond_to_prompt('1.3.7')

    prompt = tester.wait_for_prompt()

    task_bootstrap.io.standard_output.assert_not_called()
    task_bootstrap.io.error_output.assert_not_called()

    task_bootstrap.source.fetch_remote_tags.assert_called_once_with()
    task_bootstrap.source.list_tags.assert_called_once_with()

    assert prompt.message == (
        'Using tag {tag}, would you like to create a minor branch for patch versions (branch name {minor}, '
        'recommended), or a major branch for minor versions (branch name {major})? (MINOR/major/exit):'
    )
    assert prompt.args == ()
    assert prompt.kwargs == {'tag': '1.3.7', 'minor': '1.3.x', 'major': '1.x.x'}

    task_bootstrap.source.branch_exists_remotely.return_value = False

    tester.respond_to_prompt('major')

    prompt = tester.wait_for_prompt()

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call(
            'Branch {branch} does not yet exist on remote. Creating new branch and pushing to remote.',
            branch='1.x.x',
        ),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()

    task_bootstrap.source.branch_exists_remotely.assert_called_once_with('1.x.x')
    task_bootstrap.source.create_branch.assert_called_once_with('1.x.x', '1.3.7', from_item_type=ItemType.TAG)
    task_bootstrap.source.push.assert_called_once_with('1.x.x', set_tracking=True)

    assert prompt.message == (
        'Now you should create the branch where you will apply your changes. You need a token to uniquely\n'
        'identify your feature branch, such as a GitHub or JIRA issue.\n'
        f'Enter it here to create a branch named `cherry-pick-1.x.x-<entered_token>` (or SKIP to skip this step):'
    )

    tester.respond_to_prompt('JIRA-1234')

    tester.wait_for_finish()

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Branch process is complete.'),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()

    task_bootstrap.source.create_branch.assert_called_once_with('cherry-pick-1.x.x-JIRA-1234')
    assert task_bootstrap.source.push.call_count == 0
    assert task_bootstrap.source.unstash_changes.call_count == 0
