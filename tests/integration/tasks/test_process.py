"""
This module tests multiple releases, a rollback, a branch, and a release from the branch using actual Git repositories
and mocking only stdout/stderr/stdin (for the purpose of interacting with the tasks using the test infrastructure). Its
tests must be run serially, in order, in one process.
"""
import datetime
import importlib
import os
import sys
import time
from typing import (
    Any,
    Dict,
    Generator,
    NamedTuple,
    cast,
)
from unittest import mock

from invoke import __version__ as invoke_version
import pytest

from invoke_release.config import Configuration
from invoke_release.internal.context import TaskContext
from invoke_release.internal.io import (
    Color,
    IOUtils,
)
from invoke_release.internal.source_control.git import Git
from invoke_release.internal.versions import read_project_version
from invoke_release.plugins.replace import PatternReplaceVersionInFilesPlugin
from invoke_release.tasks import (
    branch,
    release,
    rollback_release,
    version,
)
from invoke_release.version import __version__

from tests import (
    InteractiveEditor,
    InteractiveTester,
    patch_popen_args,
    read_file,
    write_file,
)


TaskBootstrap = NamedTuple(
    'TaskBootstrap',
    (
        ('config', Configuration),
        ('io', mock.MagicMock),
        ('io_constructor', mock.MagicMock),
    ),
)


def _reset_modules():
    time.sleep(1)
    importlib.reload(importlib.import_module('special_library.version'))
    importlib.reload(importlib.import_module('special_library'))


@pytest.fixture(scope='module')
def task_bootstrap(local_git_repo: str) -> Generator[TaskBootstrap, None, None]:
    # This context and the helper functions ensure singleton Config override and singleton IO mock
    context: Dict[str, Any] = {'config': None, 'io_constructor': None}

    def get_config() -> Configuration:
        if not context['config']:
            context['config'] = Configuration()
        return cast(Configuration, context['config'])

    def get_mock_io_constructor() -> mock.MagicMock:
        if not context['io_constructor']:
            context['io_constructor'] = mock.MagicMock()
        return cast(mock.MagicMock, context['io_constructor'])

    with mock.patch('invoke_release.tasks.branch_task.config', new=get_config()), \
            mock.patch('invoke_release.tasks.release_task.config', new=get_config()), \
            mock.patch('invoke_release.tasks.rollback_release_task.config', new=get_config()), \
            mock.patch('invoke_release.tasks.version_task.config', new=get_config()), \
            mock.patch('invoke_release.tasks.branch_task.IOUtils', new=get_mock_io_constructor()), \
            mock.patch('invoke_release.tasks.release_task.IOUtils', new=get_mock_io_constructor()), \
            mock.patch('invoke_release.tasks.rollback_release_task.IOUtils', new=get_mock_io_constructor()), \
            mock.patch('invoke_release.tasks.version_task.IOUtils', new=get_mock_io_constructor()), \
            patch_popen_args(local_git_repo):
        config = get_config()
        config.configure(
            module_name='special_library',
            display_name='Dog Daycare',
            plugins=[PatternReplaceVersionInFilesPlugin('.version')],
        )
        config._gpg_command = None

        mock_io_constructor = get_mock_io_constructor()

        yield TaskBootstrap(
            get_config(),
            mock_io_constructor.return_value,
            mock_io_constructor,
        )


@pytest.fixture(scope='module')
def git(task_bootstrap: TaskBootstrap) -> Git:
    return Git(TaskContext(task_bootstrap.config, cast(IOUtils, task_bootstrap.io)))


def test_invoke_version(task_bootstrap: TaskBootstrap, git: Git, local_git_repo: str) -> None:
    tester = InteractiveTester(task_bootstrap.io, version)

    tester.start()

    tester.wait_for_finish()

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Python: {}', sys.version.split('\n')[0].strip()),
        mock.call('Source control: {}', git.get_version()),
        mock.call('Invoke: {}', invoke_version),
        mock.call('Invoke Release: {}', __version__),
        mock.call('Detected Project: {} {}', 'Dog Daycare', '1.2.3'),
        mock.call('Detected Git branch: {}', 'master'),
        mock.call('Detected version file: {}', os.path.join(local_git_repo, 'special_library/version.py')),
        mock.call('Detected changelog file: {}', os.path.join(local_git_repo, 'CHANGELOG.rst')),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()


def test_invoke_release_1_3_0(
    task_bootstrap: TaskBootstrap,
    interactive_editor: InteractiveEditor,
    git: Git,
    local_git_repo: str,
) -> None:
    tester = InteractiveTester(task_bootstrap.io, release)

    tester.start()

    prompt = tester.wait_for_prompt()

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Invoke Release {}', __version__),
        mock.call('Releasing {}...', 'Dog Daycare'),
        mock.call('Current version: {}', '1.2.3'),
        mock.call("First let's compile the changelog, and then we'll select a version to release."),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == 'Would you like to enter changelog details for this release? (Y/n/exit):'
    assert prompt.args == ()
    assert prompt.kwargs == {}

    tester.respond_to_prompt('')

    prompt = tester.wait_for_prompt()

    task_bootstrap.io.standard_output.assert_not_called()
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == (
        'Would you like to{also} gather commit messages from recent commits and add them to the '
        'changelog? ({y_n}/exit):'
    )
    assert prompt.args == ()
    assert prompt.kwargs == {'also': '', 'y_n': 'Y/n'}

    tester.respond_to_prompt('')

    contents = interactive_editor.wait_for_editor_open()

    assert contents == """
# Enter your changelog message above this comment, then save and close editor when finished.
# Any existing contents were pulled from changes to CHANGELOG.txt since the last release.
# Leave it blank (delete all existing contents) to release with no changelog details.
# All lines starting with "#" are comments and ignored.
# As a best practice, if you are entering multiple items as a list, prefix each item with a "-".
"""

    interactive_editor.close_editor('- [MINOR] Initial release\n')

    prompt = tester.wait_for_prompt()

    task_bootstrap.io.standard_output.assert_not_called()
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == (
        'According to the changelog message, the next version should be `{}`. '
        'Do you want to proceed with the suggested version? (Y/n)'
    )
    assert prompt.args == ('1.3.0', )
    assert prompt.kwargs == {}

    tester.respond_to_prompt('')

    prompt = tester.wait_for_prompt()

    task_bootstrap.io.standard_output.assert_not_called()
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == (
        'The changes to release files have not yet been committed. Are you ready to commit them? (Y/n):'
    )
    assert prompt.args == ()
    assert prompt.kwargs == {}

    tester.respond_to_prompt('')

    prompt = tester.wait_for_prompt()

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Releasing {module} version: {version}', module='Dog Daycare', version='1.3.0'),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == 'Push release changes and tag to remote origin (branch "{}")? (y/N/rollback):'
    assert prompt.args == ('master', )
    assert prompt.kwargs == {}

    tester.respond_to_prompt('y')

    tester.wait_for_finish()

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Release process is complete.'),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert read_file(local_git_repo, '.version').strip() == '1.3.0'
    assert '(1, 3, 0)' in read_file(local_git_repo, 'special_library/version.py')
    assert read_file(local_git_repo, 'CHANGELOG.rst') == f"""Changelog
=========

1.3.0 ({datetime.datetime.now().strftime('%Y-%m-%d')})
------------------
- [MINOR] Initial release

"""

    _reset_modules()

    assert read_project_version('special_library.version', 'special_library/version.py', reload=True) == '1.3.0'

    assert git.get_remote_branches_with_commit(git.get_last_commit_identifier())
    assert git.tag_exists_locally('1.3.0') is True
    assert git.tag_exists_remotely('1.3.0') is True


def test_invoke_release_2_0_0_but_do_not_push(
    task_bootstrap: TaskBootstrap,
    interactive_editor: InteractiveEditor,
    git: Git,
    local_git_repo: str,
) -> None:
    write_file(local_git_repo, 'special_library/play.py', 'print("It\'s a dog\'s life for sure")\n')
    git.commit(['special_library/play.py'], '[MAJOR] Added a play module')
    git.push('master')

    tester = InteractiveTester(task_bootstrap.io, release)

    tester.start()

    prompt = tester.wait_for_prompt()

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Invoke Release {}', __version__),
        mock.call('Releasing {}...', 'Dog Daycare'),
        mock.call('Current version: {}', '1.3.0'),
        mock.call("First let's compile the changelog, and then we'll select a version to release."),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == 'Would you like to enter changelog details for this release? (Y/n/exit):'
    assert prompt.args == ()
    assert prompt.kwargs == {}

    tester.respond_to_prompt('')

    prompt = tester.wait_for_prompt()

    task_bootstrap.io.standard_output.assert_not_called()
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == (
        'Would you like to{also} gather commit messages from recent commits and add them to the '
        'changelog? ({y_n}/exit):'
    )
    assert prompt.args == ()
    assert prompt.kwargs == {'also': '', 'y_n': 'Y/n'}

    tester.respond_to_prompt('')

    contents = interactive_editor.wait_for_editor_open()

    assert contents == """- [MAJOR] Added a play module

# Enter your changelog message above this comment, then save and close editor when finished.
# Any existing contents were pulled from changes to CHANGELOG.txt since the last release.
# Leave it blank (delete all existing contents) to release with no changelog details.
# All lines starting with "#" are comments and ignored.
# As a best practice, if you are entering multiple items as a list, prefix each item with a "-".
"""

    interactive_editor.close_editor('- [MAJOR] Added a play module\n- [MINOR] Something else minor\n')

    prompt = tester.wait_for_prompt()

    task_bootstrap.io.standard_output.assert_not_called()
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == (
        'According to the changelog message, the next version should be `{}`. '
        'Do you want to proceed with the suggested version? (Y/n)'
    )
    assert prompt.args == ('2.0.0', )
    assert prompt.kwargs == {}

    tester.respond_to_prompt('')

    prompt = tester.wait_for_prompt()

    task_bootstrap.io.standard_output.assert_not_called()
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == (
        'The changes to release files have not yet been committed. Are you ready to commit them? (Y/n):'
    )
    assert prompt.args == ()
    assert prompt.kwargs == {}

    tester.respond_to_prompt('')

    prompt = tester.wait_for_prompt()

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Releasing {module} version: {version}', module='Dog Daycare', version='2.0.0'),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == 'Push release changes and tag to remote origin (branch "{}")? (y/N/rollback):'
    assert prompt.args == ('master', )
    assert prompt.kwargs == {}

    tester.respond_to_prompt('')

    tester.wait_for_finish()

    task_bootstrap.io.print_output.assert_has_calls([
        mock.call(
            Color.RED_BOLD,
            'Make sure you remember to explicitly push {branch} and the tag (or revert your local changes if '
            'you are trying to cancel)! You can push with the following commands:\n'
            '    git push origin {branch}:{branch}\n'
            '    git push origin "refs/tags/{tag}:refs/tags/{tag}"\n',
            branch='master',
            tag='2.0.0',
        )
    ], any_order=False)
    task_bootstrap.io.standard_output.assert_not_called()
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert read_file(local_git_repo, '.version').strip() == '2.0.0'
    assert '(2, 0, 0)' in read_file(local_git_repo, 'special_library/version.py')
    assert read_file(local_git_repo, 'CHANGELOG.rst') == f"""Changelog
=========

2.0.0 ({datetime.datetime.now().strftime('%Y-%m-%d')})
------------------
- [MAJOR] Added a play module
- [MINOR] Something else minor

1.3.0 ({datetime.datetime.now().strftime('%Y-%m-%d')})
------------------
- [MINOR] Initial release

"""

    _reset_modules()

    assert read_project_version('special_library.version', 'special_library/version.py', reload=True) == '2.0.0'

    assert git.get_remote_branches_with_commit(git.get_last_commit_identifier()) == []
    assert git.tag_exists_locally('2.0.0') is True
    assert git.tag_exists_remotely('2.0.0') is False


def test_rollback_release(
    task_bootstrap: TaskBootstrap,
    git: Git,
    local_git_repo: str,
) -> None:
    tester = InteractiveTester(task_bootstrap.io, rollback_release)

    tester.start()

    prompt = tester.wait_for_prompt()

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Invoke Release {}', __version__),
        mock.call('Release tag {} will be deleted locally and remotely (if applicable).', '2.0.0'),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == 'Do you want to proceed with deleting this tag? (y/N):'
    assert prompt.args == ()
    assert prompt.kwargs == {}

    tester.respond_to_prompt('y')

    prompt = tester.wait_for_prompt()

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('The release tag has been deleted from local and remote (if applicable).'),
        mock.call('The release commit is only present locally, not on the remote origin.'),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == 'Are you ready to delete the commit like it never happened? (y/N):'
    assert prompt.args == ()
    assert prompt.kwargs == {}

    tester.respond_to_prompt('y')

    tester.wait_for_finish()

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Release rollback is complete.'),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert read_file(local_git_repo, '.version').strip() == '1.3.0'
    assert '(1, 3, 0)' in read_file(local_git_repo, 'special_library/version.py')
    assert '(2, 0, 0)' not in read_file(local_git_repo, 'special_library/version.py')
    assert read_file(local_git_repo, 'CHANGELOG.rst') == f"""Changelog
=========

1.3.0 ({datetime.datetime.now().strftime('%Y-%m-%d')})
------------------
- [MINOR] Initial release

"""

    _reset_modules()

    assert read_project_version('special_library.version', 'special_library/version.py', reload=True) == '1.3.0'

    assert git.tag_exists_locally('2.0.0') is False
    assert git.tag_exists_remotely('2.0.0') is False


def test_invoke_release_2_0_0_try_again(
    task_bootstrap: TaskBootstrap,
    interactive_editor: InteractiveEditor,
    git: Git,
    local_git_repo: str,
) -> None:
    write_file(local_git_repo, 'special_library/eat.py', 'print("This food is delicious")\n')
    git.commit(['special_library/eat.py'], '[MINOR] Added an eat module')
    git.push('master')

    tester = InteractiveTester(task_bootstrap.io, release)

    tester.start()

    prompt = tester.wait_for_prompt()

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Invoke Release {}', __version__),
        mock.call('Releasing {}...', 'Dog Daycare'),
        mock.call('Current version: {}', '1.3.0'),
        mock.call("First let's compile the changelog, and then we'll select a version to release."),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == 'Would you like to enter changelog details for this release? (Y/n/exit):'
    assert prompt.args == ()
    assert prompt.kwargs == {}

    tester.respond_to_prompt('')

    prompt = tester.wait_for_prompt()

    task_bootstrap.io.standard_output.assert_not_called()
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == (
        'Would you like to{also} gather commit messages from recent commits and add them to the '
        'changelog? ({y_n}/exit):'
    )
    assert prompt.args == ()
    assert prompt.kwargs == {'also': '', 'y_n': 'Y/n'}

    tester.respond_to_prompt('')

    contents = interactive_editor.wait_for_editor_open()

    assert contents == """- [MAJOR] Added a play module
- [MINOR] Added an eat module

# Enter your changelog message above this comment, then save and close editor when finished.
# Any existing contents were pulled from changes to CHANGELOG.txt since the last release.
# Leave it blank (delete all existing contents) to release with no changelog details.
# All lines starting with "#" are comments and ignored.
# As a best practice, if you are entering multiple items as a list, prefix each item with a "-".
"""

    interactive_editor.close_editor("""- [MAJOR] Added a play module
- [MINOR] Added an eat module
- [MINOR] Something else minor

# Enter your changelog message above this comment, then save and close editor when finished.
# Any existing contents were pulled from changes to CHANGELOG.txt since the last release.
# Leave it blank (delete all existing contents) to release with no changelog details.
# All lines starting with "#" are comments and ignored.
# As a best practice, if you are entering multiple items as a list, prefix each item with a "-".
""")

    prompt = tester.wait_for_prompt()

    task_bootstrap.io.standard_output.assert_not_called()
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == (
        'According to the changelog message, the next version should be `{}`. '
        'Do you want to proceed with the suggested version? (Y/n)'
    )
    assert prompt.args == ('2.0.0', )
    assert prompt.kwargs == {}

    tester.respond_to_prompt('')

    prompt = tester.wait_for_prompt()

    task_bootstrap.io.standard_output.assert_not_called()
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == (
        'The changes to release files have not yet been committed. Are you ready to commit them? (Y/n):'
    )
    assert prompt.args == ()
    assert prompt.kwargs == {}

    tester.respond_to_prompt('')

    prompt = tester.wait_for_prompt()

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Releasing {module} version: {version}', module='Dog Daycare', version='2.0.0'),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == 'Push release changes and tag to remote origin (branch "{}")? (y/N/rollback):'
    assert prompt.args == ('master',)
    assert prompt.kwargs == {}

    tester.respond_to_prompt('y')

    tester.wait_for_finish()

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Release process is complete.'),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert read_file(local_git_repo, '.version').strip() == '2.0.0'
    assert '(2, 0, 0)' in read_file(local_git_repo, 'special_library/version.py')
    assert read_file(local_git_repo, 'CHANGELOG.rst') == f"""Changelog
=========

2.0.0 ({datetime.datetime.now().strftime('%Y-%m-%d')})
------------------
- [MAJOR] Added a play module
- [MINOR] Added an eat module
- [MINOR] Something else minor

1.3.0 ({datetime.datetime.now().strftime('%Y-%m-%d')})
------------------
- [MINOR] Initial release

"""

    _reset_modules()

    assert read_project_version('special_library.version', 'special_library/version.py', reload=True) == '2.0.0'

    assert git.get_remote_branches_with_commit(git.get_last_commit_identifier())
    assert git.tag_exists_locally('2.0.0') is True
    assert git.tag_exists_remotely('2.0.0') is True


def test_invoke_branch_1_2_3_does_not_exist(task_bootstrap: TaskBootstrap) -> None:
    tester = InteractiveTester(task_bootstrap.io, branch)

    tester.start()

    prompt = tester.wait_for_prompt()

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Invoke Release {}', __version__),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == 'Enter a version tag from which to create a new branch (or "exit"):'
    assert prompt.args == ()
    assert prompt.kwargs == {}

    tester.respond_to_prompt('1.2.3')

    tester.wait_for_finish()

    task_bootstrap.io.standard_output.assert_not_called()
    task_bootstrap.io.error_output.assert_has_calls([
        mock.call('Version number 1.2.3 not in the list of available tags.'),
    ], any_order=False)
    task_bootstrap.io.error_output_exit.assert_not_called()


def test_invoke_branch_1_3_0(task_bootstrap: TaskBootstrap, git: Git) -> None:
    tester = InteractiveTester(task_bootstrap.io, branch)

    tester.start()

    prompt = tester.wait_for_prompt()

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Invoke Release {}', __version__),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == 'Enter a version tag from which to create a new branch (or "exit"):'
    assert prompt.args == ()
    assert prompt.kwargs == {}

    tester.respond_to_prompt('1.3.0')

    prompt = tester.wait_for_prompt()

    task_bootstrap.io.standard_output.assert_not_called()
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == (
        'Using tag {tag}, would you like to create a minor branch for patch versions (branch name {minor}, '
        'recommended), or a major branch for minor versions (branch name {major})? (MINOR/major/exit):'
    )
    assert prompt.args == ()
    assert prompt.kwargs == {'tag': '1.3.0', 'minor': '1.3.x', 'major': '1.x.x'}

    tester.respond_to_prompt('')

    prompt = tester.wait_for_prompt()

    task_bootstrap.io.standard_output.assert_not_called()
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == 'Branch {} created. Would you like to go ahead and push it to remote? (y/N):'
    assert prompt.args == ('1.3.x', )
    assert prompt.kwargs == {}

    tester.respond_to_prompt('y')

    tester.wait_for_finish()

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Branch process is complete.'),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert git.get_branch_name() == '1.3.x'
    assert git.branch_exists_remotely('1.3.x') is True

    _reset_modules()

    assert read_project_version('special_library.version', 'special_library/version.py', reload=True) == '1.3.0'


def test_invoke_release_1_3_1(
    task_bootstrap: TaskBootstrap,
    interactive_editor: InteractiveEditor,
    git: Git,
    local_git_repo: str,
) -> None:
    write_file(local_git_repo, 'special_library/bark.py', 'print("Woof! Woof woof!")\n')
    git.commit(['special_library/bark.py'], '[PATCH] Added the ability to bark, which was missing (a bug)')
    git.push('master')

    tester = InteractiveTester(task_bootstrap.io, release)

    tester.start()

    prompt = tester.wait_for_prompt()

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Invoke Release {}', __version__),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == (
        'You are currently on branch "{branch}" instead of "{master}." Are you sure you want to continue releasing '
        'from "{branch}?" You must do this only from version branches, and only when higher versions have been '
        'released from the parent branch. (y/N):'
    )
    assert prompt.args == ()
    assert prompt.kwargs == {'branch': '1.3.x', 'master': 'master'}

    tester.respond_to_prompt('y')

    prompt = tester.wait_for_prompt()

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Releasing {}...', 'Dog Daycare'),
        mock.call('Current version: {}', '1.3.0'),
        mock.call("First let's compile the changelog, and then we'll select a version to release."),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == 'Would you like to enter changelog details for this release? (Y/n/exit):'
    assert prompt.args == ()
    assert prompt.kwargs == {}

    tester.respond_to_prompt('')

    prompt = tester.wait_for_prompt()

    task_bootstrap.io.standard_output.assert_not_called()
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == (
        'Would you like to{also} gather commit messages from recent commits and add them to the '
        'changelog? ({y_n}/exit):'
    )
    assert prompt.args == ()
    assert prompt.kwargs == {'also': '', 'y_n': 'Y/n'}

    tester.respond_to_prompt('')

    contents = interactive_editor.wait_for_editor_open()

    assert contents == """- [PATCH] Added the ability to bark, which was missing (a bug)

# Enter your changelog message above this comment, then save and close editor when finished.
# Any existing contents were pulled from changes to CHANGELOG.txt since the last release.
# Leave it blank (delete all existing contents) to release with no changelog details.
# All lines starting with "#" are comments and ignored.
# As a best practice, if you are entering multiple items as a list, prefix each item with a "-".
"""

    interactive_editor.close_editor('- [PATCH] Added the ability to bark, which was missing (a bug)\n')

    prompt = tester.wait_for_prompt()

    task_bootstrap.io.standard_output.assert_not_called()
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == (
        'According to the changelog message, the next version should be `{}`. '
        'Do you want to proceed with the suggested version? (Y/n)'
    )
    assert prompt.args == ('1.3.1', )
    assert prompt.kwargs == {}

    tester.respond_to_prompt('')

    prompt = tester.wait_for_prompt()

    task_bootstrap.io.standard_output.assert_not_called()
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == (
        'The changes to release files have not yet been committed. Are you ready to commit them? (Y/n):'
    )
    assert prompt.args == ()
    assert prompt.kwargs == {}

    tester.respond_to_prompt('')

    prompt = tester.wait_for_prompt()

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Releasing {module} version: {version}', module='Dog Daycare', version='1.3.1'),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == 'Push release changes and tag to remote origin (branch "{}")? (y/N/rollback):'
    assert prompt.args == ('1.3.x',)
    assert prompt.kwargs == {}

    tester.respond_to_prompt('y')

    tester.wait_for_finish()

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Release process is complete.'),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert read_file(local_git_repo, '.version').strip() == '1.3.1'
    assert '(1, 3, 1)' in read_file(local_git_repo, 'special_library/version.py')
    assert read_file(local_git_repo, 'CHANGELOG.rst') == f"""Changelog
=========

1.3.1 ({datetime.datetime.now().strftime('%Y-%m-%d')})
------------------
- [PATCH] Added the ability to bark, which was missing (a bug)

1.3.0 ({datetime.datetime.now().strftime('%Y-%m-%d')})
------------------
- [MINOR] Initial release

"""

    _reset_modules()

    assert read_project_version('special_library.version', 'special_library/version.py', reload=True) == '1.3.1'

    assert git.get_remote_branches_with_commit(git.get_last_commit_identifier())
    assert git.tag_exists_locally('1.3.1') is True
    assert git.tag_exists_remotely('1.3.1') is True
