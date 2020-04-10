import datetime
import os
import subprocess
import sys
import tempfile
from typing import (
    Generator,
    cast,
)
from unittest import mock

import pytest

from invoke_release.config import Configuration
from invoke_release.errors import (
    ReleaseFailure,
    SourceControlError,
)
from invoke_release.internal.context import TaskContext
from invoke_release.internal.io import (
    Color,
    IOUtils,
)
from invoke_release.internal.source_control.base import ItemType
from invoke_release.plugins.base import ReleaseStatus
# noinspection PyProtectedMember
from invoke_release.tasks.release_task import (
    Changelog,
    open_editor,
    prompt_for_changelog,
    release,
    write_to_changelog_file,
)
from invoke_release.version import __version__

from tests import (
    InteractiveEditor,
    InteractiveTester,
)
from tests.unit import TaskBootstrap


@pytest.fixture(scope='function')
def module_being_tested() -> str:
    return 'invoke_release.tasks.release_task'


@pytest.fixture(scope='function')
def mock_read_project_version() -> Generator[mock.MagicMock, None, None]:
    with mock.patch('invoke_release.tasks.release_task.read_project_version') as m:
        yield m


@pytest.fixture(scope='function')
def mock_pre_release() -> Generator[mock.MagicMock, None, None]:
    with mock.patch('invoke_release.tasks.release_task.pre_release') as m:
        yield m


@pytest.fixture(scope='function')
def mock_pre_commit() -> Generator[mock.MagicMock, None, None]:
    with mock.patch('invoke_release.tasks.release_task.pre_commit') as m:
        yield m


@pytest.fixture(scope='function')
def mock_pre_push() -> Generator[mock.MagicMock, None, None]:
    with mock.patch('invoke_release.tasks.release_task.pre_push') as m:
        yield m


@pytest.fixture(scope='function')
def mock_post_release() -> Generator[mock.MagicMock, None, None]:
    with mock.patch('invoke_release.tasks.release_task.post_release') as m:
        yield m


@pytest.fixture(scope='function')
def mock_update_version_file() -> Generator[mock.MagicMock, None, None]:
    with mock.patch('invoke_release.tasks.release_task.update_version_file') as m:
        yield m


@pytest.fixture(scope='function')
def mock_get_extra_files_to_commit() -> Generator[mock.MagicMock, None, None]:
    with mock.patch('invoke_release.tasks.release_task.get_extra_files_to_commit') as m:
        yield m


@pytest.fixture(scope='function')
def mock_prompt_for_changelog() -> Generator[mock.MagicMock, None, None]:
    with mock.patch('invoke_release.tasks.release_task.prompt_for_changelog') as m:
        yield m


@pytest.fixture(scope='function')
def mock_write_to_changelog_file() -> Generator[mock.MagicMock, None, None]:
    with mock.patch('invoke_release.tasks.release_task.write_to_changelog_file') as m:
        yield m


def test_open_editor(task_context: TaskContext) -> None:
    with mock.patch('invoke_release.tasks.release_task.subprocess.check_call') as mock_check_call, \
            mock.patch.dict(os.environ, clear=True):
        open_editor(task_context, '/foo/bar.txt')

    mock_check_call.assert_called_once_with(['vim', '/foo/bar.txt'], stdout=sys.stdout, stderr=sys.stderr)

    with mock.patch('invoke_release.tasks.release_task.subprocess.check_call') as mock_check_call, \
            mock.patch.dict(os.environ, EDITOR='/bin/tiny --mode=dark', clear=True):
        open_editor(task_context, '/baz/qux.txt')

    mock_check_call.assert_called_once_with(
        ['/bin/tiny', '--mode=dark', '/baz/qux.txt'],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    with mock.patch('invoke_release.tasks.release_task.subprocess.check_call') as mock_check_call, \
            mock.patch.dict(
                os.environ,
                INVOKE_RELEASE_EDITOR='/custom/editor "-m light"',
                EDITOR='/bin/tiny --mode=dark',
                clear=True,
            ):
        open_editor(task_context, '/foo/qux.txt')

    mock_check_call.assert_called_once_with(
        ['/custom/editor', '-m light', '/foo/qux.txt'],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    with mock.patch('invoke_release.tasks.release_task.subprocess.check_call') as mock_check_call, \
            mock.patch.dict(os.environ, clear=True):
        mock_check_call.side_effect = OSError(12, 'Some strange problem')

        with pytest.raises(ReleaseFailure) as context:
            open_editor(task_context, '/foo/bar.txt')

    mock_check_call.assert_called_once_with(['vim', '/foo/bar.txt'], stdout=sys.stdout, stderr=sys.stderr)
    assert isinstance(context.value, ReleaseFailure)
    assert 'due to error: Some strange problem (err 12)' in context.value.args[0]
    assert context.value.args[0].endswith(
        ' Try setting $INVOKE_RELEASE_EDITOR or $EDITOR in your shell profile to the full path to '
        'Vim or another editor.'
    )

    with mock.patch('invoke_release.tasks.release_task.subprocess.check_call') as mock_check_call, \
            mock.patch.dict(os.environ, clear=True):
        mock_check_call.side_effect = subprocess.CalledProcessError(57, ['foo'])

        with pytest.raises(ReleaseFailure) as context:
            open_editor(task_context, '/foo/bar.txt')

    mock_check_call.assert_called_once_with(['vim', '/foo/bar.txt'], stdout=sys.stdout, stderr=sys.stderr)
    assert isinstance(context.value, ReleaseFailure)
    assert 'due to return code: 57' in context.value.args[0]
    assert context.value.args[0].endswith(
        ' Try setting $INVOKE_RELEASE_EDITOR or $EDITOR in your shell profile to the full path to '
        'Vim or another editor.'
    )


def test_write_to_changelog_file(task_context: TaskContext, mock_config: mock.MagicMock) -> None:
    mock_config.changelog_file_name = '/path/to/non/existent/CHANGELOG.rst'
    with pytest.raises(ReleaseFailure):
        write_to_changelog_file(task_context, '4.17.2', Changelog(
            ['header contents'],
            ['message contents'],
            ['footer contents'],
        ))

    with tempfile.NamedTemporaryFile('rt', encoding='utf-8', suffix='CHANGELOG.rst') as changelog:
        mock_config.changelog_file_name = changelog.name
        write_to_changelog_file(task_context, '4.17.2', Changelog(
            ['header contents line 1\n', 'header contents line 2\n'],
            ['message contents line 1\n', 'message contents line 2\n'],
            ['footer contents line 1\n', 'footer contents line 2\n'],
        ))

        with open(changelog.name, 'rt', encoding='utf-8') as f:
            assert f.read() == f"""header contents line 1
header contents line 2

4.17.2 ({datetime.datetime.now().strftime('%Y-%m-%d')})
-------------------
message contents line 1
message contents line 2

footer contents line 1
footer contents line 2
"""

    with tempfile.NamedTemporaryFile('rt', encoding='utf-8', suffix='CHANGELOG.rst') as changelog:
        mock_config.changelog_file_name = changelog.name
        write_to_changelog_file(task_context, '4.17.2', Changelog(
            ['header contents line 1\n', 'header contents line 2\n'],
            [],
            ['footer contents line 1\n', 'footer contents line 2\n'],
        ))

        with open(changelog.name, 'rt', encoding='utf-8') as f:
            assert f.read() == f"""header contents line 1
header contents line 2

4.17.2 ({datetime.datetime.now().strftime('%Y-%m-%d')})
-------------------
(No changelog details)

footer contents line 1
footer contents line 2
"""


def test_prompt_for_changelog_contains_built_up_exit_first_prompt(task_bootstrap: TaskBootstrap) -> None:
    with tempfile.NamedTemporaryFile('wt', encoding='utf-8', suffix='CHANGELOG.rst') as tmp_file:
        tmp_file.write("""
Changelog
=========

- Some existing change
- Another built-up change
- Include all the changes

4.17.2 (2020-04-02)
-------------------
- An older change
- Another version's change

4.17.1 (2020-04-02)
-------------------
- Something else
- Something more
""")
        tmp_file.flush()

        task_bootstrap.config.changelog_file_name = tmp_file.name

        context = TaskContext(cast(Configuration, task_bootstrap.config), cast(IOUtils, task_bootstrap.io))

        tester = InteractiveTester(
            task_bootstrap.io,
            prompt_for_changelog,
            context=context,
            source=task_bootstrap.source
        )

        tester.start()

        prompt = tester.wait_for_prompt()

        task_bootstrap.io.standard_output.assert_has_calls([
            mock.call(
                'There are existing changelog details for this release:\n'
                '    - Some existing change\n'
                '    - Another built-up change\n'
                '    - Include all the changes\n'
            ),
            mock.call(
                'You can "edit" the changes, "accept" them as-is, delete them and create a "new" changelog message, '
                'or "delete" them and enter no changelog.'
            )
        ], any_order=False)
        task_bootstrap.io.error_output.assert_not_called()
        task_bootstrap.io.error_output_exit.assert_not_called()

        assert prompt.message == 'How would you like to proceed? (EDIT/new/accept/delete/exit):'
        assert prompt.args == ()
        assert prompt.kwargs == {}

        tester.respond_to_prompt('exit')

        tester.wait_for_finish()

        assert tester.release_exit is True


def test_prompt_for_changelog_contains_built_up_proceed_with_just_that(task_bootstrap: TaskBootstrap) -> None:
    with tempfile.NamedTemporaryFile('wt', encoding='utf-8', suffix='CHANGELOG.rst') as tmp_file:
        tmp_file.write("""Changelog
=========

- Some existing change
- Another built-up change
- Include all the changes

4.17.2 (2020-04-02)
-------------------
- An older change
- Another version's change

4.17.1 (2020-04-02)
-------------------
- Something else
- Something more
""")
        tmp_file.flush()

        task_bootstrap.config.changelog_file_name = tmp_file.name

        context = TaskContext(cast(Configuration, task_bootstrap.config), cast(IOUtils, task_bootstrap.io))

        tester = InteractiveTester(
            task_bootstrap.io,
            prompt_for_changelog,
            context=context,
            source=task_bootstrap.source
        )

        tester.start()

        prompt = tester.wait_for_prompt()

        task_bootstrap.io.standard_output.assert_has_calls([
            mock.call(
                'There are existing changelog details for this release:\n'
                '    - Some existing change\n'
                '    - Another built-up change\n'
                '    - Include all the changes\n'
            ),
            mock.call(
                'You can "edit" the changes, "accept" them as-is, delete them and create a "new" changelog message, '
                'or "delete" them and enter no changelog.'
            )
        ], any_order=False)
        task_bootstrap.io.error_output.assert_not_called()
        task_bootstrap.io.error_output_exit.assert_not_called()

        assert prompt.message == 'How would you like to proceed? (EDIT/new/accept/delete/exit):'
        assert prompt.args == ()
        assert prompt.kwargs == {}

        tester.respond_to_prompt('accept')

        tester.wait_for_finish()

        changelog = tester.return_value
        assert isinstance(changelog, Changelog)
        assert changelog.header == ['Changelog\n', '=========\n']
        assert changelog.message == [
            '- Some existing change\n', '- Another built-up change\n', '- Include all the changes\n',
        ]
        assert changelog.footer == [
            '4.17.2 (2020-04-02)\n', '-------------------\n', '- An older change\n', "- Another version's change\n",
            '\n',
            '4.17.1 (2020-04-02)\n', '-------------------\n', '- Something else\n', '- Something more\n',
        ]


def test_prompt_for_changelog_contains_built_up_delete(task_bootstrap: TaskBootstrap) -> None:
    with tempfile.NamedTemporaryFile('wt', encoding='utf-8', suffix='CHANGELOG.rst') as tmp_file:
        tmp_file.write("""Changelog
=========

- Some existing change
- Another built-up change
- Include all the changes

4.17.2 (2020-04-02)
-------------------
- An older change
- Another version's change

4.17.1 (2020-04-02)
-------------------
- Something else
- Something more
""")
        tmp_file.flush()

        task_bootstrap.config.changelog_file_name = tmp_file.name

        context = TaskContext(cast(Configuration, task_bootstrap.config), cast(IOUtils, task_bootstrap.io))

        tester = InteractiveTester(
            task_bootstrap.io,
            prompt_for_changelog,
            context=context,
            source=task_bootstrap.source
        )

        tester.start()

        prompt = tester.wait_for_prompt()

        task_bootstrap.io.standard_output.assert_has_calls([
            mock.call(
                'There are existing changelog details for this release:\n'
                '    - Some existing change\n'
                '    - Another built-up change\n'
                '    - Include all the changes\n'
            ),
            mock.call(
                'You can "edit" the changes, "accept" them as-is, delete them and create a "new" changelog message, '
                'or "delete" them and enter no changelog.'
            )
        ], any_order=False)
        task_bootstrap.io.error_output.assert_not_called()
        task_bootstrap.io.error_output_exit.assert_not_called()

        assert prompt.message == 'How would you like to proceed? (EDIT/new/accept/delete/exit):'
        assert prompt.args == ()
        assert prompt.kwargs == {}

        tester.respond_to_prompt('delete')

        tester.wait_for_finish()

        changelog = tester.return_value
        assert isinstance(changelog, Changelog)
        assert changelog.header == ['Changelog\n', '=========\n']
        assert changelog.message == []
        assert changelog.footer == [
            '4.17.2 (2020-04-02)\n', '-------------------\n', '- An older change\n', "- Another version's change\n",
            '\n',
            '4.17.1 (2020-04-02)\n', '-------------------\n', '- Something else\n', '- Something more\n',
        ]


def test_prompt_for_changelog_contains_built_up_edit_then_exit(task_bootstrap: TaskBootstrap) -> None:
    with tempfile.NamedTemporaryFile('wt', encoding='utf-8', suffix='CHANGELOG.rst') as tmp_file:
        tmp_file.write("""Changelog
=========

- Some existing change
- Another built-up change
- Include all the changes

4.17.2 (2020-04-02)
-------------------
- An older change
- Another version's change

4.17.1 (2020-04-02)
-------------------
- Something else
- Something more
""")
        tmp_file.flush()

        task_bootstrap.config.changelog_file_name = tmp_file.name

        context = TaskContext(cast(Configuration, task_bootstrap.config), cast(IOUtils, task_bootstrap.io))

        tester = InteractiveTester(
            task_bootstrap.io,
            prompt_for_changelog,
            context=context,
            source=task_bootstrap.source
        )

        tester.start()

        prompt = tester.wait_for_prompt()

        task_bootstrap.io.standard_output.assert_has_calls([
            mock.call(
                'There are existing changelog details for this release:\n'
                '    - Some existing change\n'
                '    - Another built-up change\n'
                '    - Include all the changes\n'
            ),
            mock.call(
                'You can "edit" the changes, "accept" them as-is, delete them and create a "new" changelog message, '
                'or "delete" them and enter no changelog.'
            )
        ], any_order=False)
        task_bootstrap.io.error_output.assert_not_called()
        task_bootstrap.io.error_output_exit.assert_not_called()

        assert prompt.message == 'How would you like to proceed? (EDIT/new/accept/delete/exit):'
        assert prompt.args == ()
        assert prompt.kwargs == {}

        tester.respond_to_prompt('edit')

        prompt = tester.wait_for_prompt()

        assert prompt.message == (
            'Would you like to{also} gather commit messages from recent commits and add them to the '
            'changelog? ({y_n}/exit):'
        )
        assert prompt.args == ()
        assert prompt.kwargs == {'also': ' also', 'y_n': 'y/N'}

        tester.respond_to_prompt('exit')

        tester.wait_for_finish()

        assert tester.release_exit is True


def test_prompt_for_changelog_contains_built_up_edit_then_continue(
    task_bootstrap: TaskBootstrap,
    interactive_editor: InteractiveEditor,
) -> None:
    with tempfile.NamedTemporaryFile('wt', encoding='utf-8', suffix='CHANGELOG.rst') as tmp_file:
        tmp_file.write("""Changelog
=========

- Some existing change
- Another built-up change
- Include all the changes

4.17.2 (2020-04-02)
-------------------
- An older change
- Another version's change

4.17.1 (2020-04-02)
-------------------
- Something else
- Something more
""")
        tmp_file.flush()

        task_bootstrap.config.changelog_file_name = tmp_file.name

        context = TaskContext(cast(Configuration, task_bootstrap.config), cast(IOUtils, task_bootstrap.io))

        tester = InteractiveTester(
            task_bootstrap.io,
            prompt_for_changelog,
            context=context,
            source=task_bootstrap.source
        )

        tester.start()

        prompt = tester.wait_for_prompt()

        task_bootstrap.io.standard_output.assert_has_calls([
            mock.call(
                'There are existing changelog details for this release:\n'
                '    - Some existing change\n'
                '    - Another built-up change\n'
                '    - Include all the changes\n'
            ),
            mock.call(
                'You can "edit" the changes, "accept" them as-is, delete them and create a "new" changelog message, '
                'or "delete" them and enter no changelog.'
            )
        ], any_order=False)
        task_bootstrap.io.error_output.assert_not_called()
        task_bootstrap.io.error_output_exit.assert_not_called()

        assert prompt.message == 'How would you like to proceed? (EDIT/new/accept/delete/exit):'
        assert prompt.args == ()
        assert prompt.kwargs == {}

        tester.respond_to_prompt('edit')

        prompt = tester.wait_for_prompt()

        assert prompt.message == (
            'Would you like to{also} gather commit messages from recent commits and add them to the '
            'changelog? ({y_n}/exit):'
        )
        assert prompt.args == ()
        assert prompt.kwargs == {'also': ' also', 'y_n': 'y/N'}

        tester.respond_to_prompt('')

        contents = interactive_editor.wait_for_editor_open()

        assert task_bootstrap.source.gather_commit_messages_since_last_release.call_count == 0
        assert contents == """- Some existing change
- Another built-up change
- Include all the changes

# Enter your changelog message above this comment, then save and close editor when finished.
# Any existing contents were pulled from changes to CHANGELOG.txt since the last release.
# Leave it blank (delete all existing contents) to release with no changelog details.
# All lines starting with "#" are comments and ignored.
# As a best practice, if you are entering multiple items as a list, prefix each item with a "-".
"""

        interactive_editor.close_editor("""- Some existing change
- Another built-up change
- Include all the changes
- An added item
- [MINOR] One more added item

# Enter your changelog message above this comment, then save and close editor when finished.
# Any existing contents were pulled from changes to CHANGELOG.txt since the last release.
# Leave it blank (delete all existing contents) to release with no changelog details.
# All lines starting with "#" are comments and ignored.
# As a best practice, if you are entering multiple items as a list, prefix each item with a "-".
""")

        tester.wait_for_finish()

        changelog = tester.return_value
        assert isinstance(changelog, Changelog)
        assert changelog.header == ['Changelog\n', '=========\n']
        assert changelog.message == [
            '- Some existing change\n', '- Another built-up change\n', '- Include all the changes\n',
            '- An added item\n', '- [MINOR] One more added item\n'
        ]
        assert changelog.footer == [
            '4.17.2 (2020-04-02)\n', '-------------------\n', '- An older change\n', "- Another version's change\n",
            '\n',
            '4.17.1 (2020-04-02)\n', '-------------------\n', '- Something else\n', '- Something more\n',
        ]


def test_prompt_for_changelog_contains_built_up_edit_then_gather_and_continue(
    task_bootstrap: TaskBootstrap,
    interactive_editor: InteractiveEditor,
) -> None:
    with tempfile.NamedTemporaryFile('wt', encoding='utf-8', suffix='CHANGELOG.rst') as tmp_file:
        tmp_file.write("""Changelog
=========

- Some existing change
- Another built-up change
- Include all the changes

4.17.2 (2020-04-02)
-------------------
- An older change
- Another version's change

4.17.1 (2020-04-02)
-------------------
- Something else
- Something more
""")
        tmp_file.flush()

        task_bootstrap.config.changelog_file_name = tmp_file.name

        context = TaskContext(cast(Configuration, task_bootstrap.config), cast(IOUtils, task_bootstrap.io))

        tester = InteractiveTester(
            task_bootstrap.io,
            prompt_for_changelog,
            context=context,
            source=task_bootstrap.source
        )

        tester.start()

        prompt = tester.wait_for_prompt()

        task_bootstrap.io.standard_output.assert_has_calls([
            mock.call(
                'There are existing changelog details for this release:\n'
                '    - Some existing change\n'
                '    - Another built-up change\n'
                '    - Include all the changes\n'
            ),
            mock.call(
                'You can "edit" the changes, "accept" them as-is, delete them and create a "new" changelog message, '
                'or "delete" them and enter no changelog.'
            )
        ], any_order=False)
        task_bootstrap.io.error_output.assert_not_called()
        task_bootstrap.io.error_output_exit.assert_not_called()

        assert prompt.message == 'How would you like to proceed? (EDIT/new/accept/delete/exit):'
        assert prompt.args == ()
        assert prompt.kwargs == {}

        tester.respond_to_prompt('edit')

        prompt = tester.wait_for_prompt()

        assert prompt.message == (
            'Would you like to{also} gather commit messages from recent commits and add them to the '
            'changelog? ({y_n}/exit):'
        )
        assert prompt.args == ()
        assert prompt.kwargs == {'also': ' also', 'y_n': 'y/N'}

        task_bootstrap.source.gather_commit_messages_since_last_release.return_value = [
            '[PATCH] This is a commit message',
            '[MAJOR] This is another gathered commit message',
        ]

        tester.respond_to_prompt('y')

        contents = interactive_editor.wait_for_editor_open()

        task_bootstrap.source.gather_commit_messages_since_last_release.assert_called_once_with()
        assert contents == """- [PATCH] This is a commit message
- [MAJOR] This is another gathered commit message
- Some existing change
- Another built-up change
- Include all the changes

# Enter your changelog message above this comment, then save and close editor when finished.
# Any existing contents were pulled from changes to CHANGELOG.txt since the last release.
# Leave it blank (delete all existing contents) to release with no changelog details.
# All lines starting with "#" are comments and ignored.
# As a best practice, if you are entering multiple items as a list, prefix each item with a "-".
"""

        interactive_editor.close_editor("""- [PATCH] This is a commit message
- [MAJOR] This is another gathered commit message
- Some existing change
- Another built-up change
- Include all the changes
- An added item
- [MINOR] One more added item

# Enter your changelog message above this comment, then save and close editor when finished.
# Any existing contents were pulled from changes to CHANGELOG.txt since the last release.
# Leave it blank (delete all existing contents) to release with no changelog details.
# All lines starting with "#" are comments and ignored.
# As a best practice, if you are entering multiple items as a list, prefix each item with a "-".
""")

        tester.wait_for_finish()

        changelog = tester.return_value
        assert isinstance(changelog, Changelog)
        assert changelog.header == ['Changelog\n', '=========\n']
        assert changelog.message == [
            '- [PATCH] This is a commit message\n', '- [MAJOR] This is another gathered commit message\n',
            '- Some existing change\n', '- Another built-up change\n', '- Include all the changes\n',
            '- An added item\n', '- [MINOR] One more added item\n'
        ]
        assert changelog.footer == [
            '4.17.2 (2020-04-02)\n', '-------------------\n', '- An older change\n', "- Another version's change\n",
            '\n',
            '4.17.1 (2020-04-02)\n', '-------------------\n', '- Something else\n', '- Something more\n',
        ]


def test_prompt_for_changelog_contains_built_up_new_then_continue(
    task_bootstrap: TaskBootstrap,
    interactive_editor: InteractiveEditor,
) -> None:
    with tempfile.NamedTemporaryFile('wt', encoding='utf-8', suffix='CHANGELOG.rst') as tmp_file:
        tmp_file.write("""=========
Changelog
=========

- Some existing change
- Another built-up change
- Include all the changes

4.17.2 (2020-04-02)
-------------------
- An older change
- Another version's change

4.17.1 (2020-04-02)
-------------------
- Something else
- Something more
""")
        tmp_file.flush()

        task_bootstrap.config.changelog_file_name = tmp_file.name

        context = TaskContext(cast(Configuration, task_bootstrap.config), cast(IOUtils, task_bootstrap.io))

        tester = InteractiveTester(
            task_bootstrap.io,
            prompt_for_changelog,
            context=context,
            source=task_bootstrap.source
        )

        tester.start()

        prompt = tester.wait_for_prompt()

        task_bootstrap.io.standard_output.assert_has_calls([
            mock.call(
                'There are existing changelog details for this release:\n'
                '    - Some existing change\n'
                '    - Another built-up change\n'
                '    - Include all the changes\n'
            ),
            mock.call(
                'You can "edit" the changes, "accept" them as-is, delete them and create a "new" changelog message, '
                'or "delete" them and enter no changelog.'
            )
        ], any_order=False)
        task_bootstrap.io.error_output.assert_not_called()
        task_bootstrap.io.error_output_exit.assert_not_called()

        assert prompt.message == 'How would you like to proceed? (EDIT/new/accept/delete/exit):'
        assert prompt.args == ()
        assert prompt.kwargs == {}

        tester.respond_to_prompt('new')

        prompt = tester.wait_for_prompt()

        assert prompt.message == (
            'Would you like to{also} gather commit messages from recent commits and add them to the '
            'changelog? ({y_n}/exit):'
        )
        assert prompt.args == ()
        assert prompt.kwargs == {'also': '', 'y_n': 'Y/n'}

        tester.respond_to_prompt('n')

        contents = interactive_editor.wait_for_editor_open()

        assert task_bootstrap.source.gather_commit_messages_since_last_release.call_count == 0
        assert contents == """
# Enter your changelog message above this comment, then save and close editor when finished.
# Any existing contents were pulled from changes to CHANGELOG.txt since the last release.
# Leave it blank (delete all existing contents) to release with no changelog details.
# All lines starting with "#" are comments and ignored.
# As a best practice, if you are entering multiple items as a list, prefix each item with a "-".
"""

        interactive_editor.close_editor("""- An added item
- [MINOR] One more added item

# Enter your changelog message above this comment, then save and close editor when finished.
# Any existing contents were pulled from changes to CHANGELOG.txt since the last release.
# Leave it blank (delete all existing contents) to release with no changelog details.
# All lines starting with "#" are comments and ignored.
# As a best practice, if you are entering multiple items as a list, prefix each item with a "-".
""")

        tester.wait_for_finish()

        changelog = tester.return_value
        assert isinstance(changelog, Changelog)
        assert changelog.header == ['=========\n', 'Changelog\n', '=========\n']
        assert changelog.message == [
            '- An added item\n', '- [MINOR] One more added item\n'
        ]
        assert changelog.footer == [
            '4.17.2 (2020-04-02)\n', '-------------------\n', '- An older change\n', "- Another version's change\n",
            '\n',
            '4.17.1 (2020-04-02)\n', '-------------------\n', '- Something else\n', '- Something more\n',
        ]


def test_prompt_for_changelog_contains_built_up_new_then_gather_and_continue(
    task_bootstrap: TaskBootstrap,
    interactive_editor: InteractiveEditor,
) -> None:
    with tempfile.NamedTemporaryFile('wt', encoding='utf-8', suffix='CHANGELOG.rst') as tmp_file:
        tmp_file.write("""Changelog
=========

- Some existing change
- Another built-up change
- Include all the changes

4.17.2 (2020-04-02)
-------------------
- An older change
- Another version's change

4.17.1 (2020-04-02)
-------------------
- Something else
- Something more
""")
        tmp_file.flush()

        task_bootstrap.config.changelog_file_name = tmp_file.name

        context = TaskContext(cast(Configuration, task_bootstrap.config), cast(IOUtils, task_bootstrap.io))

        tester = InteractiveTester(
            task_bootstrap.io,
            prompt_for_changelog,
            context=context,
            source=task_bootstrap.source
        )

        tester.start()

        prompt = tester.wait_for_prompt()

        task_bootstrap.io.standard_output.assert_has_calls([
            mock.call(
                'There are existing changelog details for this release:\n'
                '    - Some existing change\n'
                '    - Another built-up change\n'
                '    - Include all the changes\n'
            ),
            mock.call(
                'You can "edit" the changes, "accept" them as-is, delete them and create a "new" changelog message, '
                'or "delete" them and enter no changelog.'
            )
        ], any_order=False)
        task_bootstrap.io.error_output.assert_not_called()
        task_bootstrap.io.error_output_exit.assert_not_called()

        assert prompt.message == 'How would you like to proceed? (EDIT/new/accept/delete/exit):'
        assert prompt.args == ()
        assert prompt.kwargs == {}

        tester.respond_to_prompt('new')

        prompt = tester.wait_for_prompt()

        assert prompt.message == (
            'Would you like to{also} gather commit messages from recent commits and add them to the '
            'changelog? ({y_n}/exit):'
        )
        assert prompt.args == ()
        assert prompt.kwargs == {'also': '', 'y_n': 'Y/n'}

        task_bootstrap.source.gather_commit_messages_since_last_release.return_value = [
            '[PATCH] This is a commit message',
            '[MAJOR] This is another gathered commit message',
        ]

        tester.respond_to_prompt('')

        contents = interactive_editor.wait_for_editor_open()

        task_bootstrap.source.gather_commit_messages_since_last_release.assert_called_once_with()
        assert contents == """- [PATCH] This is a commit message
- [MAJOR] This is another gathered commit message

# Enter your changelog message above this comment, then save and close editor when finished.
# Any existing contents were pulled from changes to CHANGELOG.txt since the last release.
# Leave it blank (delete all existing contents) to release with no changelog details.
# All lines starting with "#" are comments and ignored.
# As a best practice, if you are entering multiple items as a list, prefix each item with a "-".
"""

        interactive_editor.close_editor("""- [PATCH] This is a commit message
- [MAJOR] This is another gathered commit message
- An added item
- [MINOR] One more added item
# Enter your changelog message above this comment, then save and close editor when finished.
# Any existing contents were pulled from changes to CHANGELOG.txt since the last release.
# Leave it blank (delete all existing contents) to release with no changelog details.
# All lines starting with "#" are comments and ignored.
# As a best practice, if you are entering multiple items as a list, prefix each item with a "-".
""")

        tester.wait_for_finish()

        changelog = tester.return_value
        assert isinstance(changelog, Changelog)
        assert changelog.header == ['Changelog\n', '=========\n']
        assert changelog.message == [
            '- [PATCH] This is a commit message\n', '- [MAJOR] This is another gathered commit message\n',
            '- An added item\n', '- [MINOR] One more added item\n'
        ]
        assert changelog.footer == [
            '4.17.2 (2020-04-02)\n', '-------------------\n', '- An older change\n', "- Another version's change\n",
            '\n',
            '4.17.1 (2020-04-02)\n', '-------------------\n', '- Something else\n', '- Something more\n',
        ]


def test_prompt_for_changelog_no_built_up_new_then_gather_and_continue(
    task_bootstrap: TaskBootstrap,
    interactive_editor: InteractiveEditor,
) -> None:
    with tempfile.NamedTemporaryFile('wt', encoding='utf-8', suffix='CHANGELOG.rst') as tmp_file:
        tmp_file.write("""Changelog
=========

4.17.2 (2020-04-02)
-------------------
- An older change
- Another version's change

4.17.1 (2020-04-02)
-------------------
- Something else
- Something more
""")
        tmp_file.flush()

        task_bootstrap.config.changelog_file_name = tmp_file.name

        context = TaskContext(cast(Configuration, task_bootstrap.config), cast(IOUtils, task_bootstrap.io))

        tester = InteractiveTester(
            task_bootstrap.io,
            prompt_for_changelog,
            context=context,
            source=task_bootstrap.source
        )

        tester.start()

        prompt = tester.wait_for_prompt()

        task_bootstrap.io.standard_output.assert_not_called()
        task_bootstrap.io.error_output.assert_not_called()
        task_bootstrap.io.error_output_exit.assert_not_called()

        assert prompt.message == 'Would you like to enter changelog details for this release? (Y/n/exit):'
        assert prompt.args == ()
        assert prompt.kwargs == {}

        tester.respond_to_prompt('y')

        prompt = tester.wait_for_prompt()

        assert prompt.message == (
            'Would you like to{also} gather commit messages from recent commits and add them to the '
            'changelog? ({y_n}/exit):'
        )
        assert prompt.args == ()
        assert prompt.kwargs == {'also': '', 'y_n': 'Y/n'}

        task_bootstrap.source.gather_commit_messages_since_last_release.return_value = [
            '[PATCH] This is a commit message',
            '[MAJOR] This is another gathered commit message',
        ]

        tester.respond_to_prompt('')

        contents = interactive_editor.wait_for_editor_open()

        task_bootstrap.source.gather_commit_messages_since_last_release.assert_called_once_with()
        assert contents == """- [PATCH] This is a commit message
- [MAJOR] This is another gathered commit message

# Enter your changelog message above this comment, then save and close editor when finished.
# Any existing contents were pulled from changes to CHANGELOG.txt since the last release.
# Leave it blank (delete all existing contents) to release with no changelog details.
# All lines starting with "#" are comments and ignored.
# As a best practice, if you are entering multiple items as a list, prefix each item with a "-".
"""

        interactive_editor.close_editor("""
- [PATCH] This is a commit message
- [MAJOR] This is another gathered commit message
- An added item
- [MINOR] One more added item

# Enter your changelog message above this comment, then save and close editor when finished.
# Any existing contents were pulled from changes to CHANGELOG.txt since the last release.
# Leave it blank (delete all existing contents) to release with no changelog details.
# All lines starting with "#" are comments and ignored.
# As a best practice, if you are entering multiple items as a list, prefix each item with a "-".
""")

        tester.wait_for_finish()

        changelog = tester.return_value
        assert isinstance(changelog, Changelog)
        assert changelog.header == ['Changelog\n', '=========\n']
        assert changelog.message == [
            '- [PATCH] This is a commit message\n', '- [MAJOR] This is another gathered commit message\n',
            '- An added item\n', '- [MINOR] One more added item\n'
        ]
        assert changelog.footer == [
            '4.17.2 (2020-04-02)\n', '-------------------\n', '- An older change\n', "- Another version's change\n",
            '\n',
            '4.17.1 (2020-04-02)\n', '-------------------\n', '- Something else\n', '- Something more\n',
        ]


def test_not_configured(task_bootstrap: TaskBootstrap, mock_read_project_version: mock.MagicMock) -> None:
    task_bootstrap.config.is_configured = False
    task_bootstrap.io.error_output_exit.side_effect = SystemExit

    with pytest.raises(SystemExit):
        release.body('', verbose=True, no_stash=False)

    task_bootstrap.io_constructor.assert_called_once_with(True)
    task_bootstrap.io.error_output_exit.assert_called_once_with(
        'Cannot `invoke release` before calling `invoke_release.config.config.configure`.',
    )

    assert mock_read_project_version.call_count == 0


def test_master_pre_release_failed(
    task_bootstrap: TaskBootstrap,
    mock_read_project_version: mock.MagicMock,
    mock_pre_release: mock.MagicMock,
) -> None:
    task_bootstrap.config.is_configured = True
    task_bootstrap.config.module_name = 'extra_library'
    task_bootstrap.config.display_name = 'My Extra Library'
    task_bootstrap.config.release_message_template = 'Released My Extra Library version {}'
    task_bootstrap.config.version_file_name = '/path/to/extra_library/extra_library/version.txt'
    task_bootstrap.config.changelog_file_name = '/path/to/extra_library/CHANGELOG.rst'
    task_bootstrap.config.master_branch = 'development'

    tester = InteractiveTester(
        task_bootstrap.io,
        release,
        [task_bootstrap.source, mock_read_project_version],
        verbose=True,
        no_stash=False,
    )

    mock_read_project_version.return_value = '4.5.1'
    mock_pre_release.side_effect = ReleaseFailure('No worky!')
    task_bootstrap.source.get_branch_name.return_value = 'development'
    task_bootstrap.io.error_output_exit.side_effect = SystemExit

    tester.start()

    tester.wait_for_finish()

    task_bootstrap.source.pull_if_tracking_remote.assert_called_once_with()
    mock_read_project_version.assert_called_once_with(
        'extra_library.version',
        '/path/to/extra_library/extra_library/version.txt',
    )
    assert mock_pre_release.call_count == 1
    assert mock_pre_release.call_args[0][1] == '4.5.1'
    task_bootstrap.source.get_branch_name.assert_called_once_with()

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Invoke Release {}', __version__),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_has_calls([
        mock.call('No worky!')
    ], any_order=False)


def test_not_master_not_version_branch(
    task_bootstrap: TaskBootstrap,
    mock_read_project_version: mock.MagicMock,
    mock_pre_release: mock.MagicMock,
) -> None:
    task_bootstrap.config.is_configured = True
    task_bootstrap.config.module_name = 'extra_library'
    task_bootstrap.config.display_name = 'My Extra Library'
    task_bootstrap.config.release_message_template = 'Released My Extra Library version {}'
    task_bootstrap.config.version_file_name = '/path/to/extra_library/extra_library/version.txt'
    task_bootstrap.config.changelog_file_name = '/path/to/extra_library/CHANGELOG.rst'
    task_bootstrap.config.master_branch = 'root'

    tester = InteractiveTester(
        task_bootstrap.io,
        release,
        [task_bootstrap.source, mock_read_project_version],
        verbose=True,
        no_stash=False,
    )

    mock_read_project_version.return_value = '4.5.1'
    task_bootstrap.source.get_branch_name.return_value = 'development'

    tester.start()

    tester.wait_for_finish()

    task_bootstrap.source.pull_if_tracking_remote.assert_called_once_with()
    mock_read_project_version.assert_called_once_with(
        'extra_library.version',
        '/path/to/extra_library/extra_library/version.txt',
    )
    assert mock_pre_release.call_count == 0
    task_bootstrap.source.get_branch_name.assert_called_once_with()

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Invoke Release {}', __version__),
        mock.call('Canceling release!'),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_has_calls([
        mock.call(
            'You are currently on branch "{branch}" instead of "{master}." You must release only from {master} '
            'or version branches, and this does not appear to be a version branch (must match '
            '\\d+\\.x\\.x or \\d+.\\d+\\.x).\nCanceling release!',
            branch='development',
            master='root',
        )
    ], any_order=False)
    task_bootstrap.io.error_output_exit.assert_not_called()


def test_not_master_but_is_version_branch_cancel(
    task_bootstrap: TaskBootstrap,
    mock_read_project_version: mock.MagicMock,
    mock_pre_release: mock.MagicMock,
) -> None:
    task_bootstrap.config.is_configured = True
    task_bootstrap.config.module_name = 'extra_library'
    task_bootstrap.config.display_name = 'My Extra Library'
    task_bootstrap.config.release_message_template = 'Released My Extra Library version {}'
    task_bootstrap.config.version_file_name = '/path/to/extra_library/extra_library/version.txt'
    task_bootstrap.config.changelog_file_name = '/path/to/extra_library/CHANGELOG.rst'
    task_bootstrap.config.master_branch = 'master'

    tester = InteractiveTester(
        task_bootstrap.io,
        release,
        [task_bootstrap.source, mock_read_project_version],
        verbose=True,
        no_stash=False,
    )

    mock_read_project_version.return_value = '4.5.1'
    task_bootstrap.source.get_branch_name.return_value = '4.5.x'

    tester.start()

    prompt = tester.wait_for_prompt()

    task_bootstrap.source.pull_if_tracking_remote.assert_called_once_with()
    mock_read_project_version.assert_called_once_with(
        'extra_library.version',
        '/path/to/extra_library/extra_library/version.txt',
    )
    assert mock_pre_release.call_count == 0
    task_bootstrap.source.get_branch_name.assert_called_once_with()

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
    assert prompt.kwargs == {'branch': '4.5.x', 'master': 'master'}

    tester.respond_to_prompt('n')

    tester.wait_for_finish()

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Canceling release!'),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()


def test_not_master_but_is_version_branch_accept_but_error_during_prompt(
    task_bootstrap: TaskBootstrap,
    mock_read_project_version: mock.MagicMock,
    mock_pre_release: mock.MagicMock,
    mock_prompt_for_changelog: mock.MagicMock,
) -> None:
    task_bootstrap.config.is_configured = True
    task_bootstrap.config.module_name = 'extra_library'
    task_bootstrap.config.display_name = 'My Extra Library'
    task_bootstrap.config.release_message_template = 'Released My Extra Library version {}'
    task_bootstrap.config.version_file_name = '/path/to/extra_library/extra_library/version.txt'
    task_bootstrap.config.changelog_file_name = '/path/to/extra_library/CHANGELOG.rst'
    task_bootstrap.config.master_branch = 'master'

    tester = InteractiveTester(
        task_bootstrap.io,
        release,
        [task_bootstrap.source, mock_read_project_version],
        verbose=True,
        no_stash=False,
    )

    mock_read_project_version.return_value = '4.5.1'
    task_bootstrap.source.get_branch_name.return_value = '4.5.x'

    tester.start()

    prompt = tester.wait_for_prompt()

    task_bootstrap.source.pull_if_tracking_remote.assert_called_once_with()
    mock_read_project_version.assert_called_once_with(
        'extra_library.version',
        '/path/to/extra_library/extra_library/version.txt',
    )
    assert mock_pre_release.call_count == 0
    task_bootstrap.source.get_branch_name.assert_called_once_with()

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
    assert prompt.kwargs == {'branch': '4.5.x', 'master': 'master'}

    task_bootstrap.source.stash_changes.return_value = False
    mock_prompt_for_changelog.side_effect = ReleaseFailure('Prompting the user failed')

    tester.respond_to_prompt('y')

    tester.wait_for_finish()

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Releasing {}...', 'My Extra Library'),
        mock.call('Current version: {}', '4.5.1'),
        mock.call("First let's compile the changelog, and then we'll select a version to release."),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_has_calls([
        mock.call('Prompting the user failed'),
    ], any_order=False)
    task_bootstrap.io.error_output_exit.assert_not_called()

    task_bootstrap.source.stash_changes.assert_called_once_with()
    assert task_bootstrap.source.unstash_changes.call_count == 0


def test_master_reject_suggested_version_then_exit(
    task_bootstrap: TaskBootstrap,
    mock_read_project_version: mock.MagicMock,
    mock_pre_release: mock.MagicMock,
    mock_prompt_for_changelog: mock.MagicMock,
) -> None:
    task_bootstrap.config.is_configured = True
    task_bootstrap.config.module_name = 'extra_library'
    task_bootstrap.config.display_name = 'My Extra Library'
    task_bootstrap.config.release_message_template = 'Released My Extra Library version {}'
    task_bootstrap.config.version_file_name = '/path/to/extra_library/extra_library/version.txt'
    task_bootstrap.config.changelog_file_name = '/path/to/extra_library/CHANGELOG.rst'
    task_bootstrap.config.master_branch = 'master'

    tester = InteractiveTester(
        task_bootstrap.io,
        release,
        [task_bootstrap.source, mock_read_project_version],
        verbose=True,
        no_stash=False,
    )

    mock_read_project_version.return_value = '4.5.1'
    task_bootstrap.source.get_branch_name.return_value = 'master'

    task_bootstrap.source.stash_changes.return_value = True
    mock_prompt_for_changelog.return_value = Changelog(
        ['header1\n', 'header2\n'],
        ['- [PATCH] Message 1\n', '- [PATCH] Message 2\n'],
        ['footer1\n', 'footer2\n'],
    )

    tester.start()

    prompt = tester.wait_for_prompt()

    task_bootstrap.source.pull_if_tracking_remote.assert_called_once_with()
    mock_read_project_version.assert_called_once_with(
        'extra_library.version',
        '/path/to/extra_library/extra_library/version.txt',
    )
    assert mock_pre_release.call_count == 1
    assert mock_pre_release.call_args[0][1] == '4.5.1'
    task_bootstrap.source.get_branch_name.assert_called_once_with()
    assert mock_prompt_for_changelog.call_count == 1

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Invoke Release {}', __version__),
        mock.call('Releasing {}...', 'My Extra Library'),
        mock.call('Current version: {}', '4.5.1'),
        mock.call("First let's compile the changelog, and then we'll select a version to release."),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == (
        'According to the changelog message, the next version should be `{}`. '
        'Do you want to proceed with the suggested version? (Y/n)'
    )
    assert prompt.args == ('4.5.2', )
    assert prompt.kwargs == {}

    task_bootstrap.source.stash_changes.assert_called_once_with()
    assert task_bootstrap.source.unstash_changes.call_count == 0

    tester.respond_to_prompt('n')

    prompt = tester.wait_for_prompt()

    task_bootstrap.io.standard_output.assert_not_called()
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == 'Enter a new version (or "exit"):'
    assert prompt.args == ()
    assert prompt.kwargs == {}

    tester.respond_to_prompt('exit')

    tester.wait_for_finish()

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Canceling release!'),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    task_bootstrap.source.unstash_changes.assert_called_once_with()


def test_master_no_suggested_version_then_exit(
    task_bootstrap: TaskBootstrap,
    mock_read_project_version: mock.MagicMock,
    mock_pre_release: mock.MagicMock,
    mock_prompt_for_changelog: mock.MagicMock,
) -> None:
    task_bootstrap.config.is_configured = True
    task_bootstrap.config.module_name = 'extra_library'
    task_bootstrap.config.display_name = 'My Extra Library'
    task_bootstrap.config.release_message_template = 'Released My Extra Library version {}'
    task_bootstrap.config.version_file_name = '/path/to/extra_library/extra_library/version.txt'
    task_bootstrap.config.changelog_file_name = '/path/to/extra_library/CHANGELOG.rst'
    task_bootstrap.config.master_branch = 'master'

    tester = InteractiveTester(
        task_bootstrap.io,
        release,
        [task_bootstrap.source, mock_read_project_version],
        verbose=True,
        no_stash=True,
    )

    mock_read_project_version.return_value = '4.5.1'
    task_bootstrap.source.get_branch_name.return_value = 'master'

    mock_prompt_for_changelog.return_value = Changelog(
        ['header1\n', 'header2\n'],
        ['- Message 1\n', '- Message 2\n'],
        ['footer1\n', 'footer2\n'],
    )

    tester.start()

    prompt = tester.wait_for_prompt()

    task_bootstrap.source.pull_if_tracking_remote.assert_called_once_with()
    mock_read_project_version.assert_called_once_with(
        'extra_library.version',
        '/path/to/extra_library/extra_library/version.txt',
    )
    assert mock_pre_release.call_count == 1
    assert mock_pre_release.call_args[0][1] == '4.5.1'
    task_bootstrap.source.get_branch_name.assert_called_once_with()
    assert mock_prompt_for_changelog.call_count == 1

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Invoke Release {}', __version__),
        mock.call('Releasing {}...', 'My Extra Library'),
        mock.call('Current version: {}', '4.5.1'),
        mock.call("First let's compile the changelog, and then we'll select a version to release."),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == 'Enter a new version (or "exit"):'
    assert prompt.args == ()
    assert prompt.kwargs == {}

    assert task_bootstrap.source.stash_changes.call_count == 0

    tester.respond_to_prompt('exit')

    tester.wait_for_finish()

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Canceling release!'),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert task_bootstrap.source.unstash_changes.call_count == 0


def test_master_accept_suggested_version_but_conflicts(
    task_bootstrap: TaskBootstrap,
    mock_read_project_version: mock.MagicMock,
    mock_pre_release: mock.MagicMock,
    mock_prompt_for_changelog: mock.MagicMock,
) -> None:
    task_bootstrap.config.is_configured = True
    task_bootstrap.config.module_name = 'extra_library'
    task_bootstrap.config.display_name = 'My Extra Library'
    task_bootstrap.config.release_message_template = 'Released My Extra Library version {}'
    task_bootstrap.config.version_file_name = '/path/to/extra_library/extra_library/version.txt'
    task_bootstrap.config.changelog_file_name = '/path/to/extra_library/CHANGELOG.rst'
    task_bootstrap.config.master_branch = 'master'

    tester = InteractiveTester(
        task_bootstrap.io,
        release,
        [task_bootstrap.source, mock_read_project_version],
        verbose=True,
        no_stash=False,
    )

    mock_read_project_version.return_value = '4.5.1'
    task_bootstrap.source.get_branch_name.return_value = 'master'

    mock_prompt_for_changelog.return_value = Changelog(
        ['header1\n', 'header2\n'],
        ['- [PATCH] Message 1\n', '- [MINOR] Message 2\n'],
        ['footer1\n', 'footer2\n'],
    )

    tester.start()

    prompt = tester.wait_for_prompt()

    task_bootstrap.source.pull_if_tracking_remote.assert_called_once_with()
    mock_read_project_version.assert_called_once_with(
        'extra_library.version',
        '/path/to/extra_library/extra_library/version.txt',
    )
    assert mock_pre_release.call_count == 1
    assert mock_pre_release.call_args[0][1] == '4.5.1'
    task_bootstrap.source.get_branch_name.assert_called_once_with()
    assert mock_prompt_for_changelog.call_count == 1

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Invoke Release {}', __version__),
        mock.call('Releasing {}...', 'My Extra Library'),
        mock.call('Current version: {}', '4.5.1'),
        mock.call("First let's compile the changelog, and then we'll select a version to release."),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == (
        'According to the changelog message, the next version should be `{}`. '
        'Do you want to proceed with the suggested version? (Y/n)'
    )
    assert prompt.args == ('4.6.0', )
    assert prompt.kwargs == {}

    task_bootstrap.source.tag_exists_locally.return_value = True
    task_bootstrap.source.tag_exists_remotely.return_value = False

    tester.respond_to_prompt('y')

    tester.wait_for_finish()

    task_bootstrap.io.standard_output.assert_not_called()
    task_bootstrap.io.error_output.assert_has_calls([
        mock.call('Tag 4.6.0 already exists locally or remotely (or both). Cannot create version.'),
    ], any_order=False)
    task_bootstrap.io.error_output_exit.assert_not_called()


def test_master_no_suggested_version_enter_version_but_conflicts(
    task_bootstrap: TaskBootstrap,
    mock_read_project_version: mock.MagicMock,
    mock_pre_release: mock.MagicMock,
    mock_prompt_for_changelog: mock.MagicMock,
) -> None:
    task_bootstrap.config.is_configured = True
    task_bootstrap.config.module_name = 'extra_library'
    task_bootstrap.config.display_name = 'My Extra Library'
    task_bootstrap.config.release_message_template = 'Released My Extra Library version {}'
    task_bootstrap.config.version_file_name = '/path/to/extra_library/extra_library/version.txt'
    task_bootstrap.config.changelog_file_name = '/path/to/extra_library/CHANGELOG.rst'
    task_bootstrap.config.master_branch = 'master'

    tester = InteractiveTester(
        task_bootstrap.io,
        release,
        [task_bootstrap.source, mock_read_project_version],
        verbose=True,
        no_stash=False,
    )

    mock_read_project_version.return_value = '4.5.1'
    task_bootstrap.source.get_branch_name.return_value = 'master'

    mock_prompt_for_changelog.return_value = Changelog(
        ['header1\n', 'header2\n'],
        ['- Message 1\n', '- Message 2\n'],
        ['footer1\n', 'footer2\n'],
    )

    tester.start()

    prompt = tester.wait_for_prompt()

    task_bootstrap.source.pull_if_tracking_remote.assert_called_once_with()
    mock_read_project_version.assert_called_once_with(
        'extra_library.version',
        '/path/to/extra_library/extra_library/version.txt',
    )
    assert mock_pre_release.call_count == 1
    assert mock_pre_release.call_args[0][1] == '4.5.1'
    task_bootstrap.source.get_branch_name.assert_called_once_with()
    assert mock_prompt_for_changelog.call_count == 1

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Invoke Release {}', __version__),
        mock.call('Releasing {}...', 'My Extra Library'),
        mock.call('Current version: {}', '4.5.1'),
        mock.call("First let's compile the changelog, and then we'll select a version to release."),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == 'Enter a new version (or "exit"):'
    assert prompt.args == ()
    assert prompt.kwargs == {}

    task_bootstrap.source.tag_exists_locally.return_value = False
    task_bootstrap.source.tag_exists_remotely.return_value = True

    tester.respond_to_prompt('4.6.1')

    tester.wait_for_finish()

    task_bootstrap.io.standard_output.assert_not_called()
    task_bootstrap.io.error_output.assert_has_calls([
        mock.call('Tag 4.6.1 already exists locally or remotely (or both). Cannot create version.'),
    ], any_order=False)
    task_bootstrap.io.error_output_exit.assert_not_called()


def test_master_cancel_on_prompt_to_commit_changes(
    task_bootstrap: TaskBootstrap,
    mock_read_project_version: mock.MagicMock,
    mock_pre_release: mock.MagicMock,
    mock_prompt_for_changelog: mock.MagicMock,
) -> None:
    task_bootstrap.config.is_configured = True
    task_bootstrap.config.module_name = 'extra_library'
    task_bootstrap.config.display_name = 'My Extra Library'
    task_bootstrap.config.release_message_template = 'Released My Extra Library version {}'
    task_bootstrap.config.version_file_name = '/path/to/extra_library/extra_library/version.txt'
    task_bootstrap.config.changelog_file_name = '/path/to/extra_library/CHANGELOG.rst'
    task_bootstrap.config.master_branch = 'master'
    task_bootstrap.config.gpg_command = None
    task_bootstrap.config.use_pull_request = False
    task_bootstrap.config.use_tag = True

    tester = InteractiveTester(
        task_bootstrap.io,
        release,
        [task_bootstrap.source, mock_read_project_version],
        verbose=True,
        no_stash=False,
    )

    mock_read_project_version.return_value = '4.5.1'
    task_bootstrap.source.get_branch_name.return_value = 'master'

    mock_prompt_for_changelog.return_value = Changelog(
        ['header1\n', 'header2\n'],
        ['- Message 1\n', '- Message 2\n'],
        ['footer1\n', 'footer2\n'],
    )

    tester.start()

    prompt = tester.wait_for_prompt()

    task_bootstrap.source.pull_if_tracking_remote.assert_called_once_with()
    mock_read_project_version.assert_called_once_with(
        'extra_library.version',
        '/path/to/extra_library/extra_library/version.txt',
    )
    assert mock_pre_release.call_count == 1
    assert mock_pre_release.call_args[0][1] == '4.5.1'
    task_bootstrap.source.get_branch_name.assert_called_once_with()
    assert mock_prompt_for_changelog.call_count == 1

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Invoke Release {}', __version__),
        mock.call('Releasing {}...', 'My Extra Library'),
        mock.call('Current version: {}', '4.5.1'),
        mock.call("First let's compile the changelog, and then we'll select a version to release."),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == 'Enter a new version (or "exit"):'
    assert prompt.args == ()
    assert prompt.kwargs == {}

    task_bootstrap.source.tag_exists_locally.return_value = False
    task_bootstrap.source.tag_exists_remotely.return_value = False

    tester.respond_to_prompt('4.6.0')

    prompt = tester.wait_for_prompt()

    assert prompt.message == (
        'The changes to release files have not yet been committed. Are you ready to commit them? (Y/n):'
    )
    assert prompt.args == ()
    assert prompt.kwargs == {}

    tester.respond_to_prompt('n')

    tester.wait_for_finish()

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Canceling release!'),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()


def test_master_pre_commit_hook_failure(
    task_bootstrap: TaskBootstrap,
    mock_read_project_version: mock.MagicMock,
    mock_prompt_for_changelog: mock.MagicMock,
    mock_pre_commit: mock.MagicMock,
    mock_update_version_file: mock.MagicMock,
    mock_write_to_changelog_file: mock.MagicMock,
) -> None:
    task_bootstrap.config.is_configured = True
    task_bootstrap.config.module_name = 'extra_library'
    task_bootstrap.config.display_name = 'My Extra Library'
    task_bootstrap.config.release_message_template = 'Released My Extra Library version {}'
    task_bootstrap.config.version_file_name = '/path/to/extra_library/extra_library/version.txt'
    task_bootstrap.config.changelog_file_name = '/path/to/extra_library/CHANGELOG.rst'
    task_bootstrap.config.master_branch = 'master'
    task_bootstrap.config.gpg_command = None
    task_bootstrap.config.use_pull_request = False
    task_bootstrap.config.use_tag = True

    tester = InteractiveTester(
        task_bootstrap.io,
        release,
        [task_bootstrap.source, mock_read_project_version],
        verbose=True,
        no_stash=False,
    )

    mock_read_project_version.return_value = '4.5.1'
    task_bootstrap.source.get_branch_name.return_value = 'master'

    changelog = Changelog(
        ['header1\n', 'header2\n'],
        ['- Message 1\n', '- Message 2\n'],
        ['footer1\n', 'footer2\n'],
    )
    mock_prompt_for_changelog.return_value = changelog

    tester.start()

    prompt = tester.wait_for_prompt()

    task_bootstrap.source.pull_if_tracking_remote.assert_called_once_with()
    mock_read_project_version.assert_called_once_with(
        'extra_library.version',
        '/path/to/extra_library/extra_library/version.txt',
    )
    task_bootstrap.source.get_branch_name.assert_called_once_with()
    assert mock_prompt_for_changelog.call_count == 1

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Invoke Release {}', __version__),
        mock.call('Releasing {}...', 'My Extra Library'),
        mock.call('Current version: {}', '4.5.1'),
        mock.call("First let's compile the changelog, and then we'll select a version to release."),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == 'Enter a new version (or "exit"):'
    assert prompt.args == ()
    assert prompt.kwargs == {}

    task_bootstrap.source.tag_exists_locally.return_value = False
    task_bootstrap.source.tag_exists_remotely.return_value = False

    tester.respond_to_prompt('4.6.0')

    prompt = tester.wait_for_prompt()

    assert prompt.message == (
        'The changes to release files have not yet been committed. Are you ready to commit them? (Y/n):'
    )
    assert prompt.args == ()
    assert prompt.kwargs == {}

    mock_pre_commit.side_effect = ReleaseFailure('Yikes!')

    tester.respond_to_prompt('y')

    tester.wait_for_finish()

    assert mock_update_version_file.call_count == 1
    assert mock_update_version_file.call_args[0][1:] == ('4.6.0', [4, 6, 0], '-')
    assert mock_write_to_changelog_file.call_count == 1
    assert mock_write_to_changelog_file.call_args[0][1:] == ('4.6.0', changelog)

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Releasing {module} version: {version}', module='My Extra Library', version='4.6.0'),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_has_calls([
        mock.call('Yikes!'),
    ], any_order=False)
    task_bootstrap.io.error_output_exit.assert_not_called()

    task_bootstrap.source.reset_pending_changes.assert_called_once_with()


def test_master_pre_push_hook_failure(
    task_bootstrap: TaskBootstrap,
    mock_read_project_version: mock.MagicMock,
    mock_prompt_for_changelog: mock.MagicMock,
    mock_pre_push: mock.MagicMock,
    mock_update_version_file: mock.MagicMock,
    mock_write_to_changelog_file: mock.MagicMock,
    mock_get_extra_files_to_commit: mock.MagicMock,
) -> None:
    task_bootstrap.config.is_configured = True
    task_bootstrap.config.module_name = 'extra_library'
    task_bootstrap.config.display_name = 'My Extra Library'
    task_bootstrap.config.release_message_template = 'Released My Extra Library version {}'
    task_bootstrap.config.version_file_name = '/path/to/extra_library/extra_library/version.txt'
    task_bootstrap.config.changelog_file_name = '/path/to/extra_library/CHANGELOG.rst'
    task_bootstrap.config.master_branch = 'master'
    task_bootstrap.config.gpg_command = None
    task_bootstrap.config.use_pull_request = False
    task_bootstrap.config.use_tag = True

    tester = InteractiveTester(
        task_bootstrap.io,
        release,
        [task_bootstrap.source, mock_read_project_version],
        verbose=True,
        no_stash=False,
    )

    mock_read_project_version.return_value = '4.5.1'
    task_bootstrap.source.get_branch_name.return_value = 'master'

    changelog = Changelog(
        ['header1\n', 'header2\n'],
        ['- Message 1\n', '- Message 2\n'],
        ['footer1\n', 'footer2\n'],
    )
    mock_prompt_for_changelog.return_value = changelog

    tester.start()

    prompt = tester.wait_for_prompt()

    task_bootstrap.source.pull_if_tracking_remote.assert_called_once_with()
    mock_read_project_version.assert_called_once_with(
        'extra_library.version',
        '/path/to/extra_library/extra_library/version.txt',
    )
    task_bootstrap.source.get_branch_name.assert_called_once_with()
    assert mock_prompt_for_changelog.call_count == 1

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Invoke Release {}', __version__),
        mock.call('Releasing {}...', 'My Extra Library'),
        mock.call('Current version: {}', '4.5.1'),
        mock.call("First let's compile the changelog, and then we'll select a version to release."),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == 'Enter a new version (or "exit"):'
    assert prompt.args == ()
    assert prompt.kwargs == {}

    task_bootstrap.source.tag_exists_locally.return_value = False
    task_bootstrap.source.tag_exists_remotely.return_value = False

    tester.respond_to_prompt('4.6.0')

    prompt = tester.wait_for_prompt()

    assert prompt.message == (
        'The changes to release files have not yet been committed. Are you ready to commit them? (Y/n):'
    )
    assert prompt.args == ()
    assert prompt.kwargs == {}

    mock_get_extra_files_to_commit.return_value = []
    mock_pre_push.side_effect = ReleaseFailure('Yikes 2!')

    tester.respond_to_prompt('y')

    tester.wait_for_finish()

    assert mock_update_version_file.call_count == 1
    assert mock_update_version_file.call_args[0][1:] == ('4.6.0', [4, 6, 0], '-')
    assert mock_write_to_changelog_file.call_count == 1
    assert mock_write_to_changelog_file.call_args[0][1:] == ('4.6.0', changelog)

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Releasing {module} version: {version}', module='My Extra Library', version='4.6.0'),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_has_calls([
        mock.call('Yikes 2!'),
    ], any_order=False)
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert task_bootstrap.source.create_branch.call_count == 0
    task_bootstrap.source.commit.assert_called_once_with(
        ['/path/to/extra_library/extra_library/version.txt', '/path/to/extra_library/CHANGELOG.rst'],
        """Released My Extra Library version 4.6.0

Changelog Details:
- Message 1
- Message 2
""",
    )
    assert task_bootstrap.source.create_tag.call_count == 0
    assert task_bootstrap.source.reset_pending_changes.call_count == 0
    task_bootstrap.source.delete_last_local_commit.assert_called_once_with()
    assert task_bootstrap.source.checkout_item.call_count == 0
    assert task_bootstrap.source.delete_branch.call_count == 0


def test_master_use_pull_request_pre_push_hook_failure(
    task_bootstrap: TaskBootstrap,
    mock_read_project_version: mock.MagicMock,
    mock_prompt_for_changelog: mock.MagicMock,
    mock_pre_push: mock.MagicMock,
    mock_update_version_file: mock.MagicMock,
    mock_write_to_changelog_file: mock.MagicMock,
    mock_get_extra_files_to_commit: mock.MagicMock,
) -> None:
    task_bootstrap.config.is_configured = True
    task_bootstrap.config.module_name = 'extra_library'
    task_bootstrap.config.display_name = 'My Extra Library'
    task_bootstrap.config.release_message_template = 'Released My Extra Library version {}'
    task_bootstrap.config.version_file_name = '/path/to/extra_library/extra_library/version.txt'
    task_bootstrap.config.changelog_file_name = '/path/to/extra_library/CHANGELOG.rst'
    task_bootstrap.config.master_branch = 'master'
    task_bootstrap.config.gpg_command = None
    task_bootstrap.config.use_pull_request = True
    task_bootstrap.config.use_tag = True

    tester = InteractiveTester(
        task_bootstrap.io,
        release,
        [task_bootstrap.source, mock_read_project_version],
        verbose=True,
        no_stash=False,
    )

    mock_read_project_version.return_value = '4.5.1'
    task_bootstrap.source.get_branch_name.return_value = 'master'

    changelog = Changelog(
        ['header1\n', 'header2\n'],
        ['- Message 1\n', '- Message 2\n'],
        ['footer1\n', 'footer2\n'],
    )
    mock_prompt_for_changelog.return_value = changelog

    tester.start()

    prompt = tester.wait_for_prompt()

    task_bootstrap.source.pull_if_tracking_remote.assert_called_once_with()
    mock_read_project_version.assert_called_once_with(
        'extra_library.version',
        '/path/to/extra_library/extra_library/version.txt',
    )
    task_bootstrap.source.get_branch_name.assert_called_once_with()
    assert mock_prompt_for_changelog.call_count == 1

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Invoke Release {}', __version__),
        mock.call('Releasing {}...', 'My Extra Library'),
        mock.call('Current version: {}', '4.5.1'),
        mock.call("First let's compile the changelog, and then we'll select a version to release."),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == 'Enter a new version (or "exit"):'
    assert prompt.args == ()
    assert prompt.kwargs == {}

    task_bootstrap.source.tag_exists_locally.return_value = False
    task_bootstrap.source.tag_exists_remotely.return_value = False

    tester.respond_to_prompt('4.6.0')

    prompt = tester.wait_for_prompt()

    assert prompt.message == (
        'The changes to release files have not yet been committed. Are you ready to commit them? (Y/n):'
    )
    assert prompt.args == ()
    assert prompt.kwargs == {}

    mock_get_extra_files_to_commit.return_value = []
    mock_pre_push.side_effect = ReleaseFailure('Yikes 2!')

    tester.respond_to_prompt('y')

    tester.wait_for_finish()

    assert mock_update_version_file.call_count == 1
    assert mock_update_version_file.call_args[0][1:] == ('4.6.0', [4, 6, 0], '-')
    assert mock_write_to_changelog_file.call_count == 1
    assert mock_write_to_changelog_file.call_args[0][1:] == ('4.6.0', changelog)

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Releasing {module} version: {version}', module='My Extra Library', version='4.6.0'),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_has_calls([
        mock.call('Yikes 2!'),
    ], any_order=False)
    task_bootstrap.io.error_output_exit.assert_not_called()

    task_bootstrap.source.create_branch.assert_called_once_with('invoke-release-master-4.6.0')
    task_bootstrap.source.commit.assert_called_once_with(
        ['/path/to/extra_library/extra_library/version.txt', '/path/to/extra_library/CHANGELOG.rst'],
        """Released My Extra Library version 4.6.0

Changelog Details:
- Message 1
- Message 2
""",
    )
    assert task_bootstrap.source.create_tag.call_count == 0
    assert task_bootstrap.source.reset_pending_changes.call_count == 0
    task_bootstrap.source.delete_last_local_commit.assert_called_once_with()
    task_bootstrap.source.checkout_item.assert_called_once_with('master')
    task_bootstrap.source.delete_branch.assert_called_once_with('invoke-release-master-4.6.0')


def test_master_prompt_to_push_roll_back(
    task_bootstrap: TaskBootstrap,
    mock_read_project_version: mock.MagicMock,
    mock_prompt_for_changelog: mock.MagicMock,
    mock_update_version_file: mock.MagicMock,
    mock_write_to_changelog_file: mock.MagicMock,
    mock_get_extra_files_to_commit: mock.MagicMock,
    mock_post_release: mock.MagicMock,
) -> None:
    task_bootstrap.config.is_configured = True
    task_bootstrap.config.module_name = 'extra_library'
    task_bootstrap.config.display_name = 'My Extra Library'
    task_bootstrap.config.release_message_template = 'Released My Extra Library version {}'
    task_bootstrap.config.version_file_name = '/path/to/extra_library/extra_library/version.txt'
    task_bootstrap.config.changelog_file_name = '/path/to/extra_library/CHANGELOG.rst'
    task_bootstrap.config.master_branch = 'master'
    task_bootstrap.config.gpg_command = None
    task_bootstrap.config.use_pull_request = False
    task_bootstrap.config.use_tag = True

    tester = InteractiveTester(
        task_bootstrap.io,
        release,
        [task_bootstrap.source, mock_read_project_version],
        verbose=True,
        no_stash=False,
    )

    mock_read_project_version.return_value = '4.5.1'
    task_bootstrap.source.get_branch_name.return_value = 'master'

    changelog = Changelog(
        ['header1\n', 'header2\n'],
        ['- Message 1\n', '- Message 2\n'],
        ['footer1\n', 'footer2\n'],
    )
    mock_prompt_for_changelog.return_value = changelog

    tester.start()

    prompt = tester.wait_for_prompt()

    task_bootstrap.source.pull_if_tracking_remote.assert_called_once_with()
    mock_read_project_version.assert_called_once_with(
        'extra_library.version',
        '/path/to/extra_library/extra_library/version.txt',
    )
    task_bootstrap.source.get_branch_name.assert_called_once_with()
    assert mock_prompt_for_changelog.call_count == 1

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Invoke Release {}', __version__),
        mock.call('Releasing {}...', 'My Extra Library'),
        mock.call('Current version: {}', '4.5.1'),
        mock.call("First let's compile the changelog, and then we'll select a version to release."),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == 'Enter a new version (or "exit"):'
    assert prompt.args == ()
    assert prompt.kwargs == {}

    task_bootstrap.source.tag_exists_locally.return_value = False
    task_bootstrap.source.tag_exists_remotely.return_value = False

    tester.respond_to_prompt('4.6.0')

    prompt = tester.wait_for_prompt()

    assert prompt.message == (
        'The changes to release files have not yet been committed. Are you ready to commit them? (Y/n):'
    )
    assert prompt.args == ()
    assert prompt.kwargs == {}

    mock_get_extra_files_to_commit.return_value = []

    tester.respond_to_prompt('y')

    prompt = tester.wait_for_prompt()

    assert mock_update_version_file.call_count == 1
    assert mock_update_version_file.call_args[0][1:] == ('4.6.0', [4, 6, 0], '-')
    assert mock_write_to_changelog_file.call_count == 1
    assert mock_write_to_changelog_file.call_args[0][1:] == ('4.6.0', changelog)

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Releasing {module} version: {version}', module='My Extra Library', version='4.6.0'),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert task_bootstrap.source.create_branch.call_count == 0
    task_bootstrap.source.commit.assert_called_once_with(
        ['/path/to/extra_library/extra_library/version.txt', '/path/to/extra_library/CHANGELOG.rst'],
        """Released My Extra Library version 4.6.0

Changelog Details:
- Message 1
- Message 2
""",
    )
    task_bootstrap.source.create_tag.assert_called_once_with(
        '4.6.0',
        """Released My Extra Library version 4.6.0

Changelog Details:
- Message 1
- Message 2
""",
    )
    assert task_bootstrap.source.reset_pending_changes.call_count == 0
    assert task_bootstrap.source.delete_last_local_commit.call_count == 0
    assert task_bootstrap.source.checkout_item.call_count == 0
    assert task_bootstrap.source.delete_branch.call_count == 0
    assert task_bootstrap.source.delete_tag_locally.call_count == 0

    assert prompt.message == 'Push release changes and tag to remote origin (branch "{}")? (y/N/rollback):'
    assert prompt.args == ('master', )
    assert prompt.kwargs == {}

    tester.respond_to_prompt('rollback')

    tester.wait_for_finish()

    assert task_bootstrap.source.push.call_count == 0
    task_bootstrap.source.delete_last_local_commit.assert_called_once_with()
    assert task_bootstrap.source.checkout_item.call_count == 0
    assert task_bootstrap.source.delete_branch.call_count == 0
    task_bootstrap.source.delete_tag_locally.assert_called_once_with('4.6.0')

    assert mock_post_release.call_count == 1
    assert mock_post_release.call_args[0][1:] == ('4.5.1', '4.6.0', ReleaseStatus.ROLLED_BACK)

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Canceling release!'),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()


def test_master_prompt_to_push_do_not_push(
    task_bootstrap: TaskBootstrap,
    mock_read_project_version: mock.MagicMock,
    mock_prompt_for_changelog: mock.MagicMock,
    mock_update_version_file: mock.MagicMock,
    mock_write_to_changelog_file: mock.MagicMock,
    mock_get_extra_files_to_commit: mock.MagicMock,
    mock_post_release: mock.MagicMock,
) -> None:
    task_bootstrap.config.is_configured = True
    task_bootstrap.config.module_name = 'extra_library'
    task_bootstrap.config.display_name = 'My Extra Library'
    task_bootstrap.config.release_message_template = 'Released My Extra Library version {}'
    task_bootstrap.config.version_file_name = '/path/to/extra_library/extra_library/version.txt'
    task_bootstrap.config.changelog_file_name = '/path/to/extra_library/CHANGELOG.rst'
    task_bootstrap.config.master_branch = 'master'
    task_bootstrap.config.gpg_command = None
    task_bootstrap.config.use_pull_request = False
    task_bootstrap.config.use_tag = True

    tester = InteractiveTester(
        task_bootstrap.io,
        release,
        [task_bootstrap.source, mock_read_project_version],
        verbose=True,
        no_stash=False,
    )

    mock_read_project_version.return_value = '4.5.1'
    task_bootstrap.source.get_branch_name.return_value = 'master'

    changelog = Changelog(
        ['header1\n', 'header2\n'],
        ['- Message 1\n', '- Message 2\n'],
        ['footer1\n', 'footer2\n'],
    )
    mock_prompt_for_changelog.return_value = changelog

    tester.start()

    prompt = tester.wait_for_prompt()

    task_bootstrap.source.pull_if_tracking_remote.assert_called_once_with()
    mock_read_project_version.assert_called_once_with(
        'extra_library.version',
        '/path/to/extra_library/extra_library/version.txt',
    )
    task_bootstrap.source.get_branch_name.assert_called_once_with()
    assert mock_prompt_for_changelog.call_count == 1

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Invoke Release {}', __version__),
        mock.call('Releasing {}...', 'My Extra Library'),
        mock.call('Current version: {}', '4.5.1'),
        mock.call("First let's compile the changelog, and then we'll select a version to release."),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == 'Enter a new version (or "exit"):'
    assert prompt.args == ()
    assert prompt.kwargs == {}

    task_bootstrap.source.tag_exists_locally.return_value = False
    task_bootstrap.source.tag_exists_remotely.return_value = False

    tester.respond_to_prompt('4.6.0')

    prompt = tester.wait_for_prompt()

    assert prompt.message == (
        'The changes to release files have not yet been committed. Are you ready to commit them? (Y/n):'
    )
    assert prompt.args == ()
    assert prompt.kwargs == {}

    mock_get_extra_files_to_commit.return_value = []

    tester.respond_to_prompt('y')

    prompt = tester.wait_for_prompt()

    assert mock_update_version_file.call_count == 1
    assert mock_update_version_file.call_args[0][1:] == ('4.6.0', [4, 6, 0], '-')
    assert mock_write_to_changelog_file.call_count == 1
    assert mock_write_to_changelog_file.call_args[0][1:] == ('4.6.0', changelog)

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Releasing {module} version: {version}', module='My Extra Library', version='4.6.0'),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert task_bootstrap.source.create_branch.call_count == 0
    task_bootstrap.source.commit.assert_called_once_with(
        ['/path/to/extra_library/extra_library/version.txt', '/path/to/extra_library/CHANGELOG.rst'],
        """Released My Extra Library version 4.6.0

Changelog Details:
- Message 1
- Message 2
""",
    )
    task_bootstrap.source.create_tag.assert_called_once_with(
        '4.6.0',
        """Released My Extra Library version 4.6.0

Changelog Details:
- Message 1
- Message 2
""",
    )
    assert task_bootstrap.source.reset_pending_changes.call_count == 0
    assert task_bootstrap.source.delete_last_local_commit.call_count == 0
    assert task_bootstrap.source.checkout_item.call_count == 0
    assert task_bootstrap.source.delete_branch.call_count == 0
    assert task_bootstrap.source.delete_tag_locally.call_count == 0

    assert prompt.message == 'Push release changes and tag to remote origin (branch "{}")? (y/N/rollback):'
    assert prompt.args == ('master', )
    assert prompt.kwargs == {}

    tester.respond_to_prompt('n')

    tester.wait_for_finish()

    assert task_bootstrap.source.push.call_count == 0
    assert task_bootstrap.source.delete_last_local_commit.call_count == 0
    assert task_bootstrap.source.checkout_item.call_count == 0
    assert task_bootstrap.source.delete_branch.call_count == 0
    assert task_bootstrap.source.delete_tag_locally.call_count == 0

    assert mock_post_release.call_count == 1
    assert mock_post_release.call_args[0][1:] == ('4.5.1', '4.6.0', ReleaseStatus.NOT_PUSHED)

    task_bootstrap.io.print_output.assert_has_calls([
        mock.call(
            Color.RED_BOLD,
            'Make sure you remember to explicitly push {branch} and the tag (or revert your local changes if '
            'you are trying to cancel)! You can push with the following commands:\n'
            '    git push origin {branch}:{branch}\n'
            '    git push origin "refs/tags/{tag}:refs/tags/{tag}"\n',
            branch='master',
            tag='4.6.0',
        ),
    ], any_order=False)
    task_bootstrap.io.standard_output.assert_not_called()
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()


def test_master_prompt_to_push_do_not_push_no_tag(
    task_bootstrap: TaskBootstrap,
    mock_read_project_version: mock.MagicMock,
    mock_prompt_for_changelog: mock.MagicMock,
    mock_update_version_file: mock.MagicMock,
    mock_write_to_changelog_file: mock.MagicMock,
    mock_get_extra_files_to_commit: mock.MagicMock,
    mock_post_release: mock.MagicMock,
) -> None:
    task_bootstrap.config.is_configured = True
    task_bootstrap.config.module_name = 'extra_library'
    task_bootstrap.config.display_name = 'My Extra Library'
    task_bootstrap.config.release_message_template = 'Released My Extra Library version {}'
    task_bootstrap.config.version_file_name = '/path/to/extra_library/extra_library/version.txt'
    task_bootstrap.config.changelog_file_name = '/path/to/extra_library/CHANGELOG.rst'
    task_bootstrap.config.master_branch = 'master'
    task_bootstrap.config.gpg_command = None
    task_bootstrap.config.use_pull_request = False
    task_bootstrap.config.use_tag = False

    tester = InteractiveTester(
        task_bootstrap.io,
        release,
        [task_bootstrap.source, mock_read_project_version],
        verbose=True,
        no_stash=False,
    )

    mock_read_project_version.return_value = '4.5.1'
    task_bootstrap.source.get_branch_name.return_value = 'master'

    changelog = Changelog(
        ['header1\n', 'header2\n'],
        ['- Message 1\n', '- Message 2\n'],
        ['footer1\n', 'footer2\n'],
    )
    mock_prompt_for_changelog.return_value = changelog

    tester.start()

    prompt = tester.wait_for_prompt()

    task_bootstrap.source.pull_if_tracking_remote.assert_called_once_with()
    mock_read_project_version.assert_called_once_with(
        'extra_library.version',
        '/path/to/extra_library/extra_library/version.txt',
    )
    task_bootstrap.source.get_branch_name.assert_called_once_with()
    assert mock_prompt_for_changelog.call_count == 1

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Invoke Release {}', __version__),
        mock.call('Releasing {}...', 'My Extra Library'),
        mock.call('Current version: {}', '4.5.1'),
        mock.call("First let's compile the changelog, and then we'll select a version to release."),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == 'Enter a new version (or "exit"):'
    assert prompt.args == ()
    assert prompt.kwargs == {}

    task_bootstrap.source.tag_exists_locally.return_value = False
    task_bootstrap.source.tag_exists_remotely.return_value = False

    tester.respond_to_prompt('4.6.0')

    prompt = tester.wait_for_prompt()

    assert prompt.message == (
        'The changes to release files have not yet been committed. Are you ready to commit them? (Y/n):'
    )
    assert prompt.args == ()
    assert prompt.kwargs == {}

    mock_get_extra_files_to_commit.return_value = []

    tester.respond_to_prompt('y')

    prompt = tester.wait_for_prompt()

    assert mock_update_version_file.call_count == 1
    assert mock_update_version_file.call_args[0][1:] == ('4.6.0', [4, 6, 0], '-')
    assert mock_write_to_changelog_file.call_count == 1
    assert mock_write_to_changelog_file.call_args[0][1:] == ('4.6.0', changelog)

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Releasing {module} version: {version}', module='My Extra Library', version='4.6.0'),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert task_bootstrap.source.create_branch.call_count == 0
    task_bootstrap.source.commit.assert_called_once_with(
        ['/path/to/extra_library/extra_library/version.txt', '/path/to/extra_library/CHANGELOG.rst'],
        """Released My Extra Library version 4.6.0

Changelog Details:
- Message 1
- Message 2
""",
    )
    assert task_bootstrap.source.create_tag.call_count == 0
    assert task_bootstrap.source.reset_pending_changes.call_count == 0
    assert task_bootstrap.source.delete_last_local_commit.call_count == 0
    assert task_bootstrap.source.checkout_item.call_count == 0
    assert task_bootstrap.source.delete_branch.call_count == 0
    assert task_bootstrap.source.delete_tag_locally.call_count == 0

    assert prompt.message == 'Push release changes to remote origin (branch "{}")? (y/N/rollback):'
    assert prompt.args == ('master', )
    assert prompt.kwargs == {}

    tester.respond_to_prompt('n')

    tester.wait_for_finish()

    assert task_bootstrap.source.push.call_count == 0
    assert task_bootstrap.source.delete_last_local_commit.call_count == 0
    assert task_bootstrap.source.checkout_item.call_count == 0
    assert task_bootstrap.source.delete_branch.call_count == 0
    assert task_bootstrap.source.delete_tag_locally.call_count == 0

    assert mock_post_release.call_count == 1
    assert mock_post_release.call_args[0][1:] == ('4.5.1', '4.6.0', ReleaseStatus.NOT_PUSHED)

    task_bootstrap.io.print_output.assert_has_calls([
        mock.call(
            Color.RED_BOLD,
            'Make sure you remember to explicitly push {branch} (or revert your local changes if you are '
            'trying to cancel)! You can push with the following command:\n'
            '    git push origin {branch}:{branch}\n',
            branch='master',
        ),
    ], any_order=False)
    task_bootstrap.io.standard_output.assert_not_called()
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()


def test_master_prompt_to_push_accept(
    task_bootstrap: TaskBootstrap,
    mock_read_project_version: mock.MagicMock,
    mock_prompt_for_changelog: mock.MagicMock,
    mock_update_version_file: mock.MagicMock,
    mock_write_to_changelog_file: mock.MagicMock,
    mock_get_extra_files_to_commit: mock.MagicMock,
    mock_post_release: mock.MagicMock,
) -> None:
    task_bootstrap.config.is_configured = True
    task_bootstrap.config.module_name = 'extra_library'
    task_bootstrap.config.display_name = 'My Extra Library'
    task_bootstrap.config.release_message_template = 'Released My Extra Library version {}'
    task_bootstrap.config.version_file_name = '/path/to/extra_library/extra_library/version.txt'
    task_bootstrap.config.changelog_file_name = '/path/to/extra_library/CHANGELOG.rst'
    task_bootstrap.config.master_branch = 'master'
    task_bootstrap.config.gpg_command = None
    task_bootstrap.config.use_pull_request = False
    task_bootstrap.config.use_tag = True

    tester = InteractiveTester(
        task_bootstrap.io,
        release,
        [task_bootstrap.source, mock_read_project_version],
        verbose=True,
        no_stash=False,
    )

    mock_read_project_version.return_value = '4.5.1'
    task_bootstrap.source.get_branch_name.return_value = 'master'

    changelog = Changelog(
        ['header1\n', 'header2\n'],
        ['- Message 1\n', '- Message 2\n'],
        ['footer1\n', 'footer2\n'],
    )
    mock_prompt_for_changelog.return_value = changelog

    tester.start()

    prompt = tester.wait_for_prompt()

    assert task_bootstrap.source_constructor.call_count == 1
    context: TaskContext = task_bootstrap.source_constructor.call_args[0][0]

    task_bootstrap.source.pull_if_tracking_remote.assert_called_once_with()
    mock_read_project_version.assert_called_once_with(
        'extra_library.version',
        '/path/to/extra_library/extra_library/version.txt',
    )
    task_bootstrap.source.get_branch_name.assert_called_once_with()
    assert mock_prompt_for_changelog.call_count == 1

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Invoke Release {}', __version__),
        mock.call('Releasing {}...', 'My Extra Library'),
        mock.call('Current version: {}', '4.5.1'),
        mock.call("First let's compile the changelog, and then we'll select a version to release."),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == 'Enter a new version (or "exit"):'
    assert prompt.args == ()
    assert prompt.kwargs == {}

    task_bootstrap.source.tag_exists_locally.return_value = False
    task_bootstrap.source.tag_exists_remotely.return_value = False

    tester.respond_to_prompt('4.6.0')

    prompt = tester.wait_for_prompt()

    assert prompt.message == (
        'The changes to release files have not yet been committed. Are you ready to commit them? (Y/n):'
    )
    assert prompt.args == ()
    assert prompt.kwargs == {}

    mock_get_extra_files_to_commit.return_value = []

    tester.respond_to_prompt('y')

    prompt = tester.wait_for_prompt()

    assert mock_update_version_file.call_count == 1
    assert mock_update_version_file.call_args[0][1:] == ('4.6.0', [4, 6, 0], '-')
    assert mock_write_to_changelog_file.call_count == 1
    assert mock_write_to_changelog_file.call_args[0][1:] == ('4.6.0', changelog)

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Releasing {module} version: {version}', module='My Extra Library', version='4.6.0'),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert context.use_gpg is False
    assert context.gpg_alternate_id is None

    assert task_bootstrap.source.create_branch.call_count == 0
    task_bootstrap.source.commit.assert_called_once_with(
        ['/path/to/extra_library/extra_library/version.txt', '/path/to/extra_library/CHANGELOG.rst'],
        """Released My Extra Library version 4.6.0

Changelog Details:
- Message 1
- Message 2
""",
    )
    task_bootstrap.source.create_tag.assert_called_once_with(
        '4.6.0',
        """Released My Extra Library version 4.6.0

Changelog Details:
- Message 1
- Message 2
""",
    )
    assert task_bootstrap.source.reset_pending_changes.call_count == 0
    assert task_bootstrap.source.delete_last_local_commit.call_count == 0
    assert task_bootstrap.source.checkout_item.call_count == 0
    assert task_bootstrap.source.delete_branch.call_count == 0
    assert task_bootstrap.source.delete_tag_locally.call_count == 0

    assert prompt.message == 'Push release changes and tag to remote origin (branch "{}")? (y/N/rollback):'
    assert prompt.args == ('master', )
    assert prompt.kwargs == {}

    tester.respond_to_prompt('y')

    tester.wait_for_finish()

    task_bootstrap.source.push.assert_has_calls([
        mock.call('master'),
        mock.call('4.6.0', ItemType.TAG)
    ], any_order=False)
    assert task_bootstrap.source.delete_last_local_commit.call_count == 0
    assert task_bootstrap.source.checkout_item.call_count == 0
    assert task_bootstrap.source.delete_branch.call_count == 0
    assert task_bootstrap.source.delete_tag_locally.call_count == 0

    assert mock_post_release.call_count == 1
    assert mock_post_release.call_args[0][1:] == ('4.5.1', '4.6.0', ReleaseStatus.PUSHED)

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Release process is complete.'),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()


def test_master_prompt_to_push_accept_with_gpg(
    task_bootstrap: TaskBootstrap,
    mock_read_project_version: mock.MagicMock,
    mock_prompt_for_changelog: mock.MagicMock,
    mock_update_version_file: mock.MagicMock,
    mock_write_to_changelog_file: mock.MagicMock,
    mock_get_extra_files_to_commit: mock.MagicMock,
    mock_post_release: mock.MagicMock,
) -> None:
    task_bootstrap.config.is_configured = True
    task_bootstrap.config.module_name = 'extra_library'
    task_bootstrap.config.display_name = 'My Extra Library'
    task_bootstrap.config.release_message_template = 'Released My Extra Library version {}'
    task_bootstrap.config.version_file_name = '/path/to/extra_library/extra_library/version.txt'
    task_bootstrap.config.changelog_file_name = '/path/to/extra_library/CHANGELOG.rst'
    task_bootstrap.config.master_branch = 'master'
    task_bootstrap.config.gpg_command = '/usr/bin/gpg2'
    task_bootstrap.config.use_pull_request = False
    task_bootstrap.config.use_tag = True

    tester = InteractiveTester(
        task_bootstrap.io,
        release,
        [task_bootstrap.source, mock_read_project_version],
        verbose=True,
        no_stash=False,
    )

    mock_read_project_version.return_value = '4.5.1'
    task_bootstrap.source.get_branch_name.return_value = 'master'

    changelog = Changelog(
        ['header1\n', 'header2\n'],
        ['- Message 1\n', '- Message 2\n'],
        ['footer1\n', 'footer2\n'],
    )
    mock_prompt_for_changelog.return_value = changelog

    tester.start()

    prompt = tester.wait_for_prompt()

    assert task_bootstrap.source_constructor.call_count == 1
    context: TaskContext = task_bootstrap.source_constructor.call_args[0][0]

    task_bootstrap.source.pull_if_tracking_remote.assert_called_once_with()
    mock_read_project_version.assert_called_once_with(
        'extra_library.version',
        '/path/to/extra_library/extra_library/version.txt',
    )
    task_bootstrap.source.get_branch_name.assert_called_once_with()
    assert mock_prompt_for_changelog.call_count == 1

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Invoke Release {}', __version__),
        mock.call('Releasing {}...', 'My Extra Library'),
        mock.call('Current version: {}', '4.5.1'),
        mock.call("First let's compile the changelog, and then we'll select a version to release."),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == 'Enter a new version (or "exit"):'
    assert prompt.args == ()
    assert prompt.kwargs == {}

    task_bootstrap.source.tag_exists_locally.return_value = False
    task_bootstrap.source.tag_exists_remotely.return_value = False

    tester.respond_to_prompt('4.6.0')

    prompt = tester.wait_for_prompt()

    assert prompt.message == (
        'The changes to release files have not yet been committed. Are you ready to commit them? (Y/n):'
    )
    assert prompt.args == ()
    assert prompt.kwargs == {}

    tester.respond_to_prompt('y')

    prompt = tester.wait_for_prompt()

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Releasing {module} version: {version}', module='My Extra Library', version='4.6.0'),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == (
        'You have GPG installed on your system and your source control supports signing commits and tags.\n'
        'Would you like to use GPG to sign this release with the key matching your committer email? '
        '(y/N/[alternative key ID]):'
    )
    assert prompt.args == ()
    assert prompt.kwargs == {}

    mock_get_extra_files_to_commit.return_value = ['README.rst']

    assert context.use_gpg is False
    assert context.gpg_alternate_id is None

    tester.respond_to_prompt('y')

    prompt = tester.wait_for_prompt()

    assert context.use_gpg is True
    assert context.gpg_alternate_id is None

    assert mock_update_version_file.call_count == 1
    assert mock_update_version_file.call_args[0][1:] == ('4.6.0', [4, 6, 0], '-')
    assert mock_write_to_changelog_file.call_count == 1
    assert mock_write_to_changelog_file.call_args[0][1:] == ('4.6.0', changelog)

    assert task_bootstrap.source.create_branch.call_count == 0
    task_bootstrap.source.commit.assert_called_once_with(
        ['/path/to/extra_library/extra_library/version.txt', '/path/to/extra_library/CHANGELOG.rst', 'README.rst'],
        """Released My Extra Library version 4.6.0

Changelog Details:
- Message 1
- Message 2
""",
    )
    task_bootstrap.source.create_tag.assert_called_once_with(
        '4.6.0',
        """Released My Extra Library version 4.6.0

Changelog Details:
- Message 1
- Message 2
""",
    )
    assert task_bootstrap.source.reset_pending_changes.call_count == 0
    assert task_bootstrap.source.delete_last_local_commit.call_count == 0
    assert task_bootstrap.source.checkout_item.call_count == 0
    assert task_bootstrap.source.delete_branch.call_count == 0
    assert task_bootstrap.source.delete_tag_locally.call_count == 0

    assert prompt.message == 'Push release changes and tag to remote origin (branch "{}")? (y/N/rollback):'
    assert prompt.args == ('master', )
    assert prompt.kwargs == {}

    tester.respond_to_prompt('y')

    tester.wait_for_finish()

    task_bootstrap.source.push.assert_has_calls([
        mock.call('master'),
        mock.call('4.6.0', ItemType.TAG)
    ], any_order=False)
    assert task_bootstrap.source.delete_last_local_commit.call_count == 0
    assert task_bootstrap.source.checkout_item.call_count == 0
    assert task_bootstrap.source.delete_branch.call_count == 0
    assert task_bootstrap.source.delete_tag_locally.call_count == 0

    assert mock_post_release.call_count == 1
    assert mock_post_release.call_args[0][1:] == ('4.5.1', '4.6.0', ReleaseStatus.PUSHED)

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Release process is complete.'),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()


def test_master_prompt_to_push_accept_with_gpg_alternate_id(
    task_bootstrap: TaskBootstrap,
    mock_read_project_version: mock.MagicMock,
    mock_prompt_for_changelog: mock.MagicMock,
    mock_update_version_file: mock.MagicMock,
    mock_write_to_changelog_file: mock.MagicMock,
    mock_get_extra_files_to_commit: mock.MagicMock,
    mock_post_release: mock.MagicMock,
) -> None:
    task_bootstrap.config.is_configured = True
    task_bootstrap.config.module_name = 'extra_library'
    task_bootstrap.config.display_name = 'My Extra Library'
    task_bootstrap.config.release_message_template = 'Released My Extra Library version {}'
    task_bootstrap.config.version_file_name = '/path/to/extra_library/extra_library/version.txt'
    task_bootstrap.config.changelog_file_name = '/path/to/extra_library/CHANGELOG.rst'
    task_bootstrap.config.master_branch = 'master'
    task_bootstrap.config.gpg_command = '/usr/bin/gpg2'
    task_bootstrap.config.use_pull_request = False
    task_bootstrap.config.use_tag = True

    tester = InteractiveTester(
        task_bootstrap.io,
        release,
        [task_bootstrap.source, mock_read_project_version],
        verbose=True,
        no_stash=False,
    )

    mock_read_project_version.return_value = '4.5.1'
    task_bootstrap.source.get_branch_name.return_value = 'master'

    changelog = Changelog(
        ['header1\n', 'header2\n'],
        ['- Message 1\n', '- Message 2\n'],
        ['footer1\n', 'footer2\n'],
    )
    mock_prompt_for_changelog.return_value = changelog

    tester.start()

    prompt = tester.wait_for_prompt()

    assert task_bootstrap.source_constructor.call_count == 1
    context: TaskContext = task_bootstrap.source_constructor.call_args[0][0]

    task_bootstrap.source.pull_if_tracking_remote.assert_called_once_with()
    mock_read_project_version.assert_called_once_with(
        'extra_library.version',
        '/path/to/extra_library/extra_library/version.txt',
    )
    task_bootstrap.source.get_branch_name.assert_called_once_with()
    assert mock_prompt_for_changelog.call_count == 1

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Invoke Release {}', __version__),
        mock.call('Releasing {}...', 'My Extra Library'),
        mock.call('Current version: {}', '4.5.1'),
        mock.call("First let's compile the changelog, and then we'll select a version to release."),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == 'Enter a new version (or "exit"):'
    assert prompt.args == ()
    assert prompt.kwargs == {}

    task_bootstrap.source.tag_exists_locally.return_value = False
    task_bootstrap.source.tag_exists_remotely.return_value = False

    tester.respond_to_prompt('4.6.0')

    prompt = tester.wait_for_prompt()

    assert prompt.message == (
        'The changes to release files have not yet been committed. Are you ready to commit them? (Y/n):'
    )
    assert prompt.args == ()
    assert prompt.kwargs == {}

    tester.respond_to_prompt('y')

    prompt = tester.wait_for_prompt()

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Releasing {module} version: {version}', module='My Extra Library', version='4.6.0'),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == (
        'You have GPG installed on your system and your source control supports signing commits and tags.\n'
        'Would you like to use GPG to sign this release with the key matching your committer email? '
        '(y/N/[alternative key ID]):'
    )
    assert prompt.args == ()
    assert prompt.kwargs == {}

    mock_get_extra_files_to_commit.return_value = ['README.rst']

    assert context.use_gpg is False
    assert context.gpg_alternate_id is None

    tester.respond_to_prompt('A8D72EF139CC0013')

    prompt = tester.wait_for_prompt()

    assert context.use_gpg is True
    assert context.gpg_alternate_id == 'A8D72EF139CC0013'

    assert mock_update_version_file.call_count == 1
    assert mock_update_version_file.call_args[0][1:] == ('4.6.0', [4, 6, 0], '-')
    assert mock_write_to_changelog_file.call_count == 1
    assert mock_write_to_changelog_file.call_args[0][1:] == ('4.6.0', changelog)

    assert task_bootstrap.source.create_branch.call_count == 0
    task_bootstrap.source.commit.assert_called_once_with(
        ['/path/to/extra_library/extra_library/version.txt', '/path/to/extra_library/CHANGELOG.rst', 'README.rst'],
        """Released My Extra Library version 4.6.0

Changelog Details:
- Message 1
- Message 2
""",
    )
    task_bootstrap.source.create_tag.assert_called_once_with(
        '4.6.0',
        """Released My Extra Library version 4.6.0

Changelog Details:
- Message 1
- Message 2
""",
    )
    assert task_bootstrap.source.reset_pending_changes.call_count == 0
    assert task_bootstrap.source.delete_last_local_commit.call_count == 0
    assert task_bootstrap.source.checkout_item.call_count == 0
    assert task_bootstrap.source.delete_branch.call_count == 0
    assert task_bootstrap.source.delete_tag_locally.call_count == 0

    assert prompt.message == 'Push release changes and tag to remote origin (branch "{}")? (y/N/rollback):'
    assert prompt.args == ('master', )
    assert prompt.kwargs == {}

    tester.respond_to_prompt('y')

    tester.wait_for_finish()

    task_bootstrap.source.push.assert_has_calls([
        mock.call('master'),
        mock.call('4.6.0', ItemType.TAG)
    ], any_order=False)
    assert task_bootstrap.source.delete_last_local_commit.call_count == 0
    assert task_bootstrap.source.checkout_item.call_count == 0
    assert task_bootstrap.source.delete_branch.call_count == 0
    assert task_bootstrap.source.delete_tag_locally.call_count == 0

    assert mock_post_release.call_count == 1
    assert mock_post_release.call_args[0][1:] == ('4.5.1', '4.6.0', ReleaseStatus.PUSHED)

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Release process is complete.'),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()


def test_master_prompt_to_push_accept_no_tag(
    task_bootstrap: TaskBootstrap,
    mock_read_project_version: mock.MagicMock,
    mock_prompt_for_changelog: mock.MagicMock,
    mock_update_version_file: mock.MagicMock,
    mock_write_to_changelog_file: mock.MagicMock,
    mock_get_extra_files_to_commit: mock.MagicMock,
    mock_post_release: mock.MagicMock,
) -> None:
    task_bootstrap.config.is_configured = True
    task_bootstrap.config.module_name = 'extra_library'
    task_bootstrap.config.display_name = 'My Extra Library'
    task_bootstrap.config.release_message_template = 'Released My Extra Library version {}'
    task_bootstrap.config.version_file_name = '/path/to/extra_library/extra_library/version.txt'
    task_bootstrap.config.changelog_file_name = '/path/to/extra_library/CHANGELOG.rst'
    task_bootstrap.config.master_branch = 'master'
    task_bootstrap.config.gpg_command = None
    task_bootstrap.config.use_pull_request = False
    task_bootstrap.config.use_tag = False

    tester = InteractiveTester(
        task_bootstrap.io,
        release,
        [task_bootstrap.source, mock_read_project_version],
        verbose=True,
        no_stash=False,
    )

    mock_read_project_version.return_value = '4.5.1'
    task_bootstrap.source.get_branch_name.return_value = 'master'

    changelog = Changelog(
        ['header1\n', 'header2\n'],
        ['- Message 1\n', '- Message 2\n'],
        ['footer1\n', 'footer2\n'],
    )
    mock_prompt_for_changelog.return_value = changelog

    tester.start()

    prompt = tester.wait_for_prompt()

    task_bootstrap.source.pull_if_tracking_remote.assert_called_once_with()
    mock_read_project_version.assert_called_once_with(
        'extra_library.version',
        '/path/to/extra_library/extra_library/version.txt',
    )
    task_bootstrap.source.get_branch_name.assert_called_once_with()
    assert mock_prompt_for_changelog.call_count == 1

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Invoke Release {}', __version__),
        mock.call('Releasing {}...', 'My Extra Library'),
        mock.call('Current version: {}', '4.5.1'),
        mock.call("First let's compile the changelog, and then we'll select a version to release."),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == 'Enter a new version (or "exit"):'
    assert prompt.args == ()
    assert prompt.kwargs == {}

    task_bootstrap.source.tag_exists_locally.return_value = False
    task_bootstrap.source.tag_exists_remotely.return_value = False

    tester.respond_to_prompt('4.6.0')

    prompt = tester.wait_for_prompt()

    assert prompt.message == (
        'The changes to release files have not yet been committed. Are you ready to commit them? (Y/n):'
    )
    assert prompt.args == ()
    assert prompt.kwargs == {}

    mock_get_extra_files_to_commit.return_value = []

    tester.respond_to_prompt('y')

    prompt = tester.wait_for_prompt()

    assert mock_update_version_file.call_count == 1
    assert mock_update_version_file.call_args[0][1:] == ('4.6.0', [4, 6, 0], '-')
    assert mock_write_to_changelog_file.call_count == 1
    assert mock_write_to_changelog_file.call_args[0][1:] == ('4.6.0', changelog)

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Releasing {module} version: {version}', module='My Extra Library', version='4.6.0'),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert task_bootstrap.source.create_branch.call_count == 0
    task_bootstrap.source.commit.assert_called_once_with(
        ['/path/to/extra_library/extra_library/version.txt', '/path/to/extra_library/CHANGELOG.rst'],
        """Released My Extra Library version 4.6.0

Changelog Details:
- Message 1
- Message 2
""",
    )
    assert task_bootstrap.source.create_tag.call_count == 0
    assert task_bootstrap.source.reset_pending_changes.call_count == 0
    assert task_bootstrap.source.delete_last_local_commit.call_count == 0
    assert task_bootstrap.source.checkout_item.call_count == 0
    assert task_bootstrap.source.delete_branch.call_count == 0
    assert task_bootstrap.source.delete_tag_locally.call_count == 0

    assert prompt.message == 'Push release changes to remote origin (branch "{}")? (y/N/rollback):'
    assert prompt.args == ('master', )
    assert prompt.kwargs == {}

    tester.respond_to_prompt('y')

    tester.wait_for_finish()

    task_bootstrap.source.push.assert_called_once_with('master')
    assert task_bootstrap.source.delete_last_local_commit.call_count == 0
    assert task_bootstrap.source.checkout_item.call_count == 0
    assert task_bootstrap.source.delete_branch.call_count == 0
    assert task_bootstrap.source.delete_tag_locally.call_count == 0

    assert mock_post_release.call_count == 1
    assert mock_post_release.call_args[0][1:] == ('4.5.1', '4.6.0', ReleaseStatus.PUSHED)

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Release process is complete.'),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()


def test_master_prompt_to_push_accept_no_tag_with_pull_request(
    task_bootstrap: TaskBootstrap,
    mock_read_project_version: mock.MagicMock,
    mock_prompt_for_changelog: mock.MagicMock,
    mock_update_version_file: mock.MagicMock,
    mock_write_to_changelog_file: mock.MagicMock,
    mock_get_extra_files_to_commit: mock.MagicMock,
    mock_post_release: mock.MagicMock,
) -> None:
    task_bootstrap.config.is_configured = True
    task_bootstrap.config.module_name = 'extra_library'
    task_bootstrap.config.display_name = 'My Extra Library'
    task_bootstrap.config.release_message_template = 'Released My Extra Library version {}'
    task_bootstrap.config.version_file_name = '/path/to/extra_library/extra_library/version.txt'
    task_bootstrap.config.changelog_file_name = '/path/to/extra_library/CHANGELOG.rst'
    task_bootstrap.config.master_branch = 'master'
    task_bootstrap.config.gpg_command = None
    task_bootstrap.config.use_pull_request = True
    task_bootstrap.config.use_tag = False

    tester = InteractiveTester(
        task_bootstrap.io,
        release,
        [task_bootstrap.source, mock_read_project_version],
        verbose=True,
        no_stash=False,
    )

    mock_read_project_version.return_value = '4.5.1'
    task_bootstrap.source.get_branch_name.return_value = 'master'

    changelog = Changelog(
        ['header1\n', 'header2\n'],
        ['- Message 1\n', '- Message 2\n'],
        ['footer1\n', 'footer2\n'],
    )
    mock_prompt_for_changelog.return_value = changelog

    tester.start()

    prompt = tester.wait_for_prompt()

    task_bootstrap.source.pull_if_tracking_remote.assert_called_once_with()
    mock_read_project_version.assert_called_once_with(
        'extra_library.version',
        '/path/to/extra_library/extra_library/version.txt',
    )
    task_bootstrap.source.get_branch_name.assert_called_once_with()
    assert mock_prompt_for_changelog.call_count == 1

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Invoke Release {}', __version__),
        mock.call('Releasing {}...', 'My Extra Library'),
        mock.call('Current version: {}', '4.5.1'),
        mock.call("First let's compile the changelog, and then we'll select a version to release."),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == 'Enter a new version (or "exit"):'
    assert prompt.args == ()
    assert prompt.kwargs == {}

    task_bootstrap.source.tag_exists_locally.return_value = False
    task_bootstrap.source.tag_exists_remotely.return_value = False

    tester.respond_to_prompt('4.6.0')

    prompt = tester.wait_for_prompt()

    assert prompt.message == (
        'The changes to release files have not yet been committed. Are you ready to commit them? (Y/n):'
    )
    assert prompt.args == ()
    assert prompt.kwargs == {}

    mock_get_extra_files_to_commit.return_value = []

    tester.respond_to_prompt('y')

    prompt = tester.wait_for_prompt()

    assert mock_update_version_file.call_count == 1
    assert mock_update_version_file.call_args[0][1:] == ('4.6.0', [4, 6, 0], '-')
    assert mock_write_to_changelog_file.call_count == 1
    assert mock_write_to_changelog_file.call_args[0][1:] == ('4.6.0', changelog)

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Releasing {module} version: {version}', module='My Extra Library', version='4.6.0'),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    task_bootstrap.source.create_branch.assert_called_once_with('invoke-release-master-4.6.0')
    task_bootstrap.source.commit.assert_called_once_with(
        ['/path/to/extra_library/extra_library/version.txt', '/path/to/extra_library/CHANGELOG.rst'],
        """Released My Extra Library version 4.6.0

Changelog Details:
- Message 1
- Message 2
""",
    )
    assert task_bootstrap.source.create_tag.call_count == 0
    assert task_bootstrap.source.reset_pending_changes.call_count == 0
    assert task_bootstrap.source.delete_last_local_commit.call_count == 0
    assert task_bootstrap.source.checkout_item.call_count == 0
    assert task_bootstrap.source.delete_branch.call_count == 0
    assert task_bootstrap.source.delete_tag_locally.call_count == 0

    assert prompt.message == 'Push release changes to remote origin (branch "{}")? (y/N/rollback):'
    assert prompt.args == ('invoke-release-master-4.6.0', )
    assert prompt.kwargs == {}

    task_bootstrap.source.open_pull_request.return_value = 'https://github.com/account/project/pull/12'

    tester.respond_to_prompt('y')

    tester.wait_for_finish()

    task_bootstrap.source.push.assert_called_once_with('invoke-release-master-4.6.0')
    assert task_bootstrap.source.delete_last_local_commit.call_count == 0
    task_bootstrap.source.checkout_item.assert_called_once_with('master')
    task_bootstrap.source.delete_branch.assert_called_once_with('invoke-release-master-4.6.0')
    assert task_bootstrap.source.delete_tag_locally.call_count == 0
    task_bootstrap.source.open_pull_request.assert_called_once_with(
        title='Released My Extra Library version 4.6.0',
        base='master',
        head='invoke-release-master-4.6.0',
    )

    assert mock_post_release.call_count == 1
    assert mock_post_release.call_args[0][1:] == ('4.5.1', '4.6.0', ReleaseStatus.PUSHED)

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('GitHub PR created successfully. URL: https://github.com/account/project/pull/12'),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()


def test_master_prompt_to_push_accept_no_tag_with_pull_request_which_failed(
    task_bootstrap: TaskBootstrap,
    mock_read_project_version: mock.MagicMock,
    mock_prompt_for_changelog: mock.MagicMock,
    mock_update_version_file: mock.MagicMock,
    mock_write_to_changelog_file: mock.MagicMock,
    mock_get_extra_files_to_commit: mock.MagicMock,
    mock_post_release: mock.MagicMock,
) -> None:
    task_bootstrap.config.is_configured = True
    task_bootstrap.config.module_name = 'extra_library'
    task_bootstrap.config.display_name = 'My Extra Library'
    task_bootstrap.config.release_message_template = 'Released My Extra Library version {}'
    task_bootstrap.config.version_file_name = '/path/to/extra_library/extra_library/version.txt'
    task_bootstrap.config.changelog_file_name = '/path/to/extra_library/CHANGELOG.rst'
    task_bootstrap.config.master_branch = 'master'
    task_bootstrap.config.gpg_command = None
    task_bootstrap.config.use_pull_request = True
    task_bootstrap.config.use_tag = False

    tester = InteractiveTester(
        task_bootstrap.io,
        release,
        [task_bootstrap.source, mock_read_project_version],
        verbose=True,
        no_stash=False,
    )

    mock_read_project_version.return_value = '4.5.1'
    task_bootstrap.source.get_branch_name.return_value = 'master'

    changelog = Changelog(
        ['header1\n', 'header2\n'],
        ['- Message 1\n', '- Message 2\n'],
        ['footer1\n', 'footer2\n'],
    )
    mock_prompt_for_changelog.return_value = changelog

    tester.start()

    prompt = tester.wait_for_prompt()

    task_bootstrap.source.pull_if_tracking_remote.assert_called_once_with()
    mock_read_project_version.assert_called_once_with(
        'extra_library.version',
        '/path/to/extra_library/extra_library/version.txt',
    )
    task_bootstrap.source.get_branch_name.assert_called_once_with()
    assert mock_prompt_for_changelog.call_count == 1

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Invoke Release {}', __version__),
        mock.call('Releasing {}...', 'My Extra Library'),
        mock.call('Current version: {}', '4.5.1'),
        mock.call("First let's compile the changelog, and then we'll select a version to release."),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    assert prompt.message == 'Enter a new version (or "exit"):'
    assert prompt.args == ()
    assert prompt.kwargs == {}

    task_bootstrap.source.tag_exists_locally.return_value = False
    task_bootstrap.source.tag_exists_remotely.return_value = False

    tester.respond_to_prompt('4.6.0')

    prompt = tester.wait_for_prompt()

    assert prompt.message == (
        'The changes to release files have not yet been committed. Are you ready to commit them? (Y/n):'
    )
    assert prompt.args == ()
    assert prompt.kwargs == {}

    mock_get_extra_files_to_commit.return_value = []

    tester.respond_to_prompt('y')

    prompt = tester.wait_for_prompt()

    assert mock_update_version_file.call_count == 1
    assert mock_update_version_file.call_args[0][1:] == ('4.6.0', [4, 6, 0], '-')
    assert mock_write_to_changelog_file.call_count == 1
    assert mock_write_to_changelog_file.call_args[0][1:] == ('4.6.0', changelog)

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Releasing {module} version: {version}', module='My Extra Library', version='4.6.0'),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_not_called()
    task_bootstrap.io.error_output_exit.assert_not_called()

    task_bootstrap.source.create_branch.assert_called_once_with('invoke-release-master-4.6.0')
    task_bootstrap.source.commit.assert_called_once_with(
        ['/path/to/extra_library/extra_library/version.txt', '/path/to/extra_library/CHANGELOG.rst'],
        """Released My Extra Library version 4.6.0

Changelog Details:
- Message 1
- Message 2
""",
    )
    assert task_bootstrap.source.create_tag.call_count == 0
    assert task_bootstrap.source.reset_pending_changes.call_count == 0
    assert task_bootstrap.source.delete_last_local_commit.call_count == 0
    assert task_bootstrap.source.checkout_item.call_count == 0
    assert task_bootstrap.source.delete_branch.call_count == 0
    assert task_bootstrap.source.delete_tag_locally.call_count == 0

    assert prompt.message == 'Push release changes to remote origin (branch "{}")? (y/N/rollback):'
    assert prompt.args == ('invoke-release-master-4.6.0', )
    assert prompt.kwargs == {}

    task_bootstrap.source.open_pull_request.side_effect = SourceControlError('PR request failed, dude')

    tester.respond_to_prompt('y')

    tester.wait_for_finish()

    task_bootstrap.source.push.assert_called_once_with('invoke-release-master-4.6.0')
    assert task_bootstrap.source.delete_last_local_commit.call_count == 0
    task_bootstrap.source.checkout_item.assert_called_once_with('master')
    task_bootstrap.source.delete_branch.assert_called_once_with('invoke-release-master-4.6.0')
    assert task_bootstrap.source.delete_tag_locally.call_count == 0
    task_bootstrap.source.open_pull_request.assert_called_once_with(
        title='Released My Extra Library version 4.6.0',
        base='master',
        head='invoke-release-master-4.6.0',
    )

    assert mock_post_release.call_count == 1
    assert mock_post_release.call_args[0][1:] == ('4.5.1', '4.6.0', ReleaseStatus.PUSHED)

    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call(
            "You're almost done! The release process will be complete when you manually create a pull "
            "request and it is merged."
        ),
    ], any_order=False)
    task_bootstrap.io.error_output.assert_has_calls([
        mock.call('PR request failed, dude'),
    ], any_order=False)
    task_bootstrap.io.error_output_exit.assert_not_called()
