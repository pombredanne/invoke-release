import os
import subprocess
import sys
from unittest import mock

import pytest

from invoke_release.errors import SourceControlError
from invoke_release.internal.context import TaskContext
from invoke_release.internal.source_control.git import Git


class TestGit:
    def test_supports_gpg_signing(self, git: Git):
        assert git.supports_gpg_signing is True

    def test_get_root_directory_failure_points(self, git: Git):
        with mock.patch('invoke_release.internal.source_control.git.subprocess.check_output') as mock_check_output:
            mock_check_output.return_value = b''

            with pytest.raises(SourceControlError) as context:
                git.get_root_directory()

            assert isinstance(context.value, SourceControlError)
            assert context.value.args[0] == 'Failed to find Git root directory.'

            mock_check_output.assert_called_once_with(['git', 'rev-parse', '--show-toplevel'], stderr=sys.stderr)

        with mock.patch('invoke_release.internal.source_control.git.subprocess.check_output') as mock_check_output:
            mock_check_output.side_effect = subprocess.CalledProcessError(
                cmd=['git', 'sample', 'cmd'],
                returncode=152,
                output=b'This is some output',
            )

            with pytest.raises(SourceControlError) as context:
                git.get_root_directory()

            assert isinstance(context.value, SourceControlError)
            assert context.value.args[0] == (
                "Failed to run Git command ['git', 'sample', 'cmd'].\n152: This is some output"
            )

            mock_check_output.assert_called_once_with(['git', 'rev-parse', '--show-toplevel'], stderr=sys.stderr)

        with mock.patch('invoke_release.internal.source_control.git.subprocess.check_output') as mock_check_output:
            mock_check_output.side_effect = subprocess.CalledProcessError(
                cmd=['git', 'other', 'thing'],
                returncode=13,
                output=None,
            )

            with pytest.raises(SourceControlError) as context:
                git.get_root_directory()

            assert isinstance(context.value, SourceControlError)
            assert context.value.args[0] == (
                "Failed to run Git command ['git', 'other', 'thing'].\n13: [No captured output, see stderr above]"
            )

            mock_check_output.assert_called_once_with(['git', 'rev-parse', '--show-toplevel'], stderr=sys.stderr)

    def test_commit_failure_points(self, git: Git, task_context: TaskContext, mock_config: mock.MagicMock):
        with mock.patch('invoke_release.internal.source_control.git.subprocess.check_output') as mock_check_output:
            mock_check_output.return_value = b'Could not stage change to file CHANGELOG.rst'

            with pytest.raises(SourceControlError) as context:
                git.commit(['CHANGELOG.rst', 'special_library/version.py'], 'This is a commit, yo')

            assert isinstance(context.value, SourceControlError)
            assert context.value.args[0] == (
                'Failed staging release files for commit: Could not stage change to file CHANGELOG.rst'
            )

            mock_check_output.assert_called_once_with(
                ['git', 'add', 'CHANGELOG.rst', 'special_library/version.py'],
                stderr=subprocess.STDOUT,
            )

        task_context.use_gpg = True
        mock_config.gpg_command = '/path/to/gpg'
        mock_config.tty = '/dev/ttys0003'

        patcher = mock.patch.object(git, '_configure_gpg')
        patcher.start()

        with mock.patch('invoke_release.internal.source_control.git.subprocess.check_output') as mock_check_output:
            mock_check_output.side_effect = (
                b'',
                subprocess.CalledProcessError(12, ['foo'], output=b'Some weird error unrelated to signing'),
            )

            with pytest.raises(SourceControlError) as context:
                git.commit(['CHANGELOG.rst', 'special_library/version.py'], 'This is a commit, yo')

            assert isinstance(context.value, SourceControlError)
            assert 'Failed to run Git command' in context.value.args[0]

            mock_check_output.assert_has_calls([
                mock.call(
                    ['git', 'add', 'CHANGELOG.rst', 'special_library/version.py'],
                    stderr=subprocess.STDOUT,
                ),
                mock.call(
                    ['git', 'commit', '--gpg-sign', '-m', 'This is a commit, yo'],
                    stderr=subprocess.STDOUT,
                    env=dict(os.environ, GPG_TTY='/dev/ttys0003'),
                ),
            ], any_order=False)

        patcher = mock.patch.object(git, 'get_last_commit_identifier')
        patcher.start().return_value = '8et28oec8c3717'

        with mock.patch('invoke_release.internal.source_control.git.subprocess.check_output') as mock_check_output, \
                mock.patch('invoke_release.internal.source_control.git.subprocess.check_call') as mock_check_call:
            mock_check_output.side_effect = (
                b'',
                b'Sample commit output',
            )
            mock_check_call.side_effect = subprocess.CalledProcessError(12, ['foo'])

            with pytest.raises(SourceControlError) as context:
                git.commit(['CHANGELOG.rst', 'special_library/version.py'], 'This is a commit, yo')

            assert isinstance(context.value, SourceControlError)
            assert 'failed to verify the commit signature' in context.value.args[0]

            mock_check_output.assert_has_calls([
                mock.call(
                    ['git', 'add', 'CHANGELOG.rst', 'special_library/version.py'],
                    stderr=subprocess.STDOUT,
                ),
                mock.call(
                    ['git', 'commit', '--gpg-sign', '-m', 'This is a commit, yo'],
                    stderr=subprocess.STDOUT,
                    env=dict(os.environ, GPG_TTY='/dev/ttys0003'),
                ),
            ], any_order=False)
            mock_check_call.assert_has_calls([
                mock.call(
                    ['git', 'verify-commit', '8et28oec8c3717'],
                    stdout=sys.stdout,
                    stderr=sys.stderr,
                ),
            ], any_order=False)

    def test_create_tag_failure_points(self, git: Git, task_context: TaskContext, mock_config: mock.MagicMock):
        task_context.use_gpg = True
        mock_config.gpg_command = '/path/to/gpg'
        mock_config.tty = '/dev/ttys0004'

        patcher = mock.patch.object(git, '_configure_gpg')
        patcher.start()

        with mock.patch('invoke_release.internal.source_control.git.subprocess.check_output') as mock_check_output:
            mock_check_output.side_effect = subprocess.CalledProcessError(12, ['foo'], output=b'Some other error')

            with pytest.raises(SourceControlError) as context:
                git.create_tag('tag1', 'This is the first message')

            assert isinstance(context.value, SourceControlError)
            assert 'Failed to run Git command' in context.value.args[0]

            mock_check_output.assert_called_once_with(
                ['git', 'tag', '-a', 'tag1', '-m', 'This is the first message', '-s'],
                stderr=subprocess.STDOUT,
                env=dict(os.environ, GPG_TTY='/dev/ttys0004'),
            )

        with mock.patch('invoke_release.internal.source_control.git.subprocess.check_output') as mock_check_output:
            mock_check_output.return_value = b'unable to sign the tag'

            with pytest.raises(SourceControlError) as context:
                git.create_tag('tag1', 'This is the first message')

            assert isinstance(context.value, SourceControlError)
            assert 'Failed tagging release due to error signing with GPG' in context.value.args[0]

            mock_check_output.assert_called_once_with(
                ['git', 'tag', '-a', 'tag1', '-m', 'This is the first message', '-s'],
                stderr=subprocess.STDOUT,
                env=dict(os.environ, GPG_TTY='/dev/ttys0004'),
            )

        with mock.patch('invoke_release.internal.source_control.git.subprocess.check_output') as mock_check_output:
            mock_check_output.return_value = b'unable to create the tag for some other reason'
            task_context.gpg_alternate_id = 'ABC1234567890DEF'

            with pytest.raises(SourceControlError) as context:
                git.create_tag('tag2', 'This is the second message')

            assert isinstance(context.value, SourceControlError)
            assert 'unable to create the tag for some other reason' in context.value.args[0]

            mock_check_output.assert_called_once_with(
                ['git', 'tag', '-a', 'tag2', '-m', 'This is the second message', '-u', 'ABC1234567890DEF'],
                stderr=subprocess.STDOUT,
                env=dict(os.environ, GPG_TTY='/dev/ttys0004'),
            )

        with mock.patch('invoke_release.internal.source_control.git.subprocess.check_output') as mock_check_output, \
                mock.patch('invoke_release.internal.source_control.git.subprocess.check_call') as mock_check_call:
            mock_check_output.return_value = b''
            mock_check_call.side_effect = subprocess.CalledProcessError(12, ['foo'])
            task_context.gpg_alternate_id = ''

            with pytest.raises(SourceControlError) as context:
                git.create_tag('tag3', 'This is the third message')

            assert isinstance(context.value, SourceControlError)
            assert 'failed to verify its signature' in context.value.args[0]

            mock_check_output.assert_called_once_with(
                ['git', 'tag', '-a', 'tag3', '-m', 'This is the third message', '-s'],
                stderr=subprocess.STDOUT,
                env=dict(os.environ, GPG_TTY='/dev/ttys0004'),
            )

    def test_remote_url_to_github_account_and_repo(self):
        assert Git.remote_url_to_github_account_and_repo('https://github.com/eventbrite/invoke-release.git') == (
            'eventbrite/invoke-release'
        )
        assert Git.remote_url_to_github_account_and_repo('git@github.com:eventbrite/invoke_release.git') == (
            'eventbrite/invoke_release'
        )
        assert Git.remote_url_to_github_account_and_repo('file:///path/to/local/repo/') == (
            'local/repo'
        )
        assert Git.remote_url_to_github_account_and_repo('file:///Path/To/Local/Repo/.git') == (
            'Local/Repo'
        )

        with pytest.raises(SourceControlError):
            Git.remote_url_to_github_account_and_repo('not a remote path')
