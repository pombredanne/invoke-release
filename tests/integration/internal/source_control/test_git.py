import json
import os
import subprocess
import sys
from typing import (
    Generator,
    Optional,
)
from unittest import mock
import urllib.request

import pytest

from invoke_release.errors import SourceControlError
from invoke_release.internal.context import TaskContext
from invoke_release.internal.source_control.base import ItemType
from invoke_release.internal.source_control.git import Git
from invoke_release.internal.utils import get_tty

from tests import (
    file_exists,
    patch_popen_args,
    read_file,
    write_file,
)
from tests.integration import GpgSetup


@pytest.fixture(scope='module')
def remote_repo(remote_git_repo) -> Generator[str, None, None]:
    # an alias for brevity
    yield remote_git_repo


@pytest.fixture(scope='module')
def local_repo(local_git_repo) -> Generator[str, None, None]:
    # an alias for brevity
    yield local_git_repo


class TestGit:
    @pytest.mark.skip('Un-skip and run with pytest -v to check the output of this sanity check.')
    def test_sanity_check(self, local_repo: str) -> None:
        subprocess.check_call(['ls', '-al'], cwd=local_repo, stdout=sys.stdout, stderr=sys.stderr)
        subprocess.check_call(['ls', '-al', 'special_library'], cwd=local_repo, stdout=sys.stdout, stderr=sys.stderr)
        subprocess.check_call(['git', 'remote', '-v'], cwd=local_repo, stdout=sys.stdout, stderr=sys.stderr)

    def test_get_version(self, git: Git) -> None:
        assert git.get_version().startswith('git version ')

    def test_get_root_directory(self, git: Git, local_repo: str):
        with patch_popen_args(local_repo):
            assert git.get_root_directory() == local_repo
        with patch_popen_args(os.path.join(local_repo, 'special_library')):
            assert git.get_root_directory() == local_repo

    def test_branches(self, git: Git, local_repo: str, remote_repo: str):
        with patch_popen_args(remote_repo):
            assert git.get_branch_name() == 'master'
            subprocess.check_call(
                ['git', 'update-ref', 'refs/heads/test_branches_create_remote_branch', 'refs/heads/master'],
                stdout=sys.stdout,
                stderr=sys.stderr,
            )

        with patch_popen_args(local_repo):
            assert git.get_branch_name() == 'master'
            commit_hash = git.get_last_commit_identifier()
            assert git.pull_if_tracking_remote() is True

            git.create_branch('test_branches_create_local_branch')
            assert git.get_branch_name() == 'test_branches_create_local_branch'
            assert git.pull_if_tracking_remote() is False

            assert git.branch_exists_remotely('test_branches_create_remote_branch') is True
            assert git.branch_exists_remotely('test_branches_create_local_branch') is False

            git.checkout_remote_branch('test_branches_create_remote_branch')
            assert git.pull_if_tracking_remote() is True

            assert set(git.get_remote_branches_with_commit(commit_hash)) == {
                'origin/master',
                'origin/test_branches_create_remote_branch',
            }

            git.push('test_branches_create_local_branch', set_tracking=True)
            assert git.branch_exists_remotely('test_branches_create_local_branch') is True
            assert set(git.get_remote_branches_with_commit(commit_hash)) == {
                'origin/master',
                'origin/test_branches_create_remote_branch',
                'origin/test_branches_create_local_branch',
            }
            assert git.pull_if_tracking_remote() is True

            git.checkout_item('master')

            git.checkout_item('test_branches_create_local_branch')
            git.checkout_item('master')
            git.delete_branch('test_branches_create_local_branch')

            git.checkout_item('test_branches_create_remote_branch')
            git.checkout_item('master')
            git.delete_branch('test_branches_create_remote_branch')

            with pytest.raises(SourceControlError):
                git.checkout_item('non_existent_branch')

    def test_tags(self, git: Git, local_repo: str, remote_repo: str):
        with patch_popen_args(remote_repo):
            git.create_tag('test_tags_create_remote_tag', 'This is a message for the tag')

        with patch_popen_args(local_repo):
            git.checkout_item('master')
            git.create_tag('test_tags_create_local_tag', 'This is a message for the tag')

            assert git.tag_exists_remotely('test_tags_create_remote_tag') is True
            assert git.tag_exists_locally('test_tags_create_remote_tag') is False
            assert git.tag_exists_remotely('test_tags_create_local_tag') is False
            assert git.tag_exists_locally('test_tags_create_local_tag') is True

            assert set(git.list_tags()) == {'test_tags_create_local_tag'}

            git.fetch_remote_tags()

            assert git.tag_exists_remotely('test_tags_create_remote_tag') is True
            assert git.tag_exists_locally('test_tags_create_remote_tag') is True
            assert git.tag_exists_remotely('test_tags_create_local_tag') is False
            assert git.tag_exists_locally('test_tags_create_local_tag') is True

            assert set(git.list_tags()) == {'test_tags_create_local_tag', 'test_tags_create_remote_tag'}

            git.push('test_tags_create_local_tag', ItemType.TAG)

            assert git.tag_exists_remotely('test_tags_create_remote_tag') is True
            assert git.tag_exists_locally('test_tags_create_remote_tag') is True
            assert git.tag_exists_remotely('test_tags_create_local_tag') is True
            assert git.tag_exists_locally('test_tags_create_local_tag') is True

            git.delete_tag_locally('test_tags_create_local_tag')

            assert git.tag_exists_remotely('test_tags_create_remote_tag') is True
            assert git.tag_exists_locally('test_tags_create_remote_tag') is True
            assert git.tag_exists_remotely('test_tags_create_local_tag') is True
            assert git.tag_exists_locally('test_tags_create_local_tag') is False

            git.delete_tag_remotely('test_tags_create_local_tag')

            assert git.tag_exists_remotely('test_tags_create_remote_tag') is True
            assert git.tag_exists_locally('test_tags_create_remote_tag') is True
            assert git.tag_exists_remotely('test_tags_create_local_tag') is False
            assert git.tag_exists_locally('test_tags_create_local_tag') is False

            try:
                git.create_tag('test_create_branch_from_tag_tag', 'This is a message for the tag')
                git.create_branch('test_create_branch_from_tag_branch', 'test_create_branch_from_tag_tag', ItemType.TAG)
            finally:
                try:
                    git.delete_branch('test_create_branch_from_tag_branch')
                except SourceControlError:
                    pass

    def test_sign_tag(
        self,
        git: Git,
        local_repo: str,
        gpg_setup: GpgSetup,
        task_context: TaskContext,
        mock_config: mock.MagicMock,
    ):
        task_context.use_gpg = True
        mock_config.gpg_command = gpg_setup.command
        mock_config.tty = get_tty()

        with patch_popen_args(cwd=local_repo, env={'GNUPGHOME': gpg_setup.directory}):
            git.checkout_item('master')
            git.create_tag(f'test_sign_tag_auto_key.{gpg_setup.command}', 'This tag was signed with the default key')

            output = subprocess.check_output(
                ['git', 'verify-tag', f'test_sign_tag_auto_key.{gpg_setup.command}'],
                stderr=subprocess.STDOUT,
            ).decode('utf-8')
            assert gpg_setup.implicit_key in output, 'The implicit key SHOULD have been used for this.'
            assert gpg_setup.explicit_key not in output, 'The explicit key should NOT have been used for this.'

            task_context.gpg_alternate_id = gpg_setup.explicit_key
            git.create_tag(
                f'test_sign_tag_explicit_key.{gpg_setup.command}',
                'This tag was signed with an explicit key',
            )

            output = subprocess.check_output(
                ['git', 'verify-tag', f'test_sign_tag_explicit_key.{gpg_setup.command}'],
                stderr=subprocess.STDOUT,
            ).decode('utf-8')
            assert gpg_setup.implicit_key not in output, 'The implicit key should NOT have been used for this.'
            assert gpg_setup.explicit_key in output, 'The explicit key SHOULD have been used for this.'

            task_context.gpg_alternate_id = 'ABC1234567890DEF'

            with pytest.raises(SourceControlError) as context:
                git.create_tag('test_sign_tag_fake_key', 'This tag was signed with an fake key')

            assert isinstance(context.value, SourceControlError)
            assert 'Failed tagging release due to error signing with GPG.' in context.value.args[0]

    def test_stashing(self, git: Git, local_repo: str):
        with patch_popen_args(local_repo):
            git.checkout_item('master')

            try:
                write_file(local_repo, 'README.rst', 'This is a test new file\n')
                write_file(local_repo, 'CHANGELOG.rst', 'This is the replaced file contents\n')

                assert file_exists(local_repo, 'README.rst') is True
                assert read_file(local_repo, 'CHANGELOG.rst') == 'This is the replaced file contents\n'

                assert git.stash_changes() is True

                assert file_exists(local_repo, 'README.rst') is False
                assert read_file(local_repo, 'CHANGELOG.rst') == 'Changelog\n=========\n'

                git.unstash_changes()

                assert file_exists(local_repo, 'README.rst') is True
                assert read_file(local_repo, 'README.rst') == 'This is a test new file\n'
                assert read_file(local_repo, 'CHANGELOG.rst') == 'This is the replaced file contents\n'
            finally:
                write_file(local_repo, 'CHANGELOG.rst', 'Changelog\n=========\n')
                os.unlink(os.path.join(local_repo, 'README.rst'))

            assert git.stash_changes() is False

    def test_delete_commit(self, git: Git, local_repo: str):
        with patch_popen_args(local_repo):
            git.checkout_item('master')

            error: Optional[Exception] = None
            try:
                first_commit_hash = git.get_last_commit_identifier()

                write_file(local_repo, 'README.rst', 'This is a test new file\n')
                write_file(local_repo, 'CHANGELOG.rst', 'This is the replaced file contents\n')

                git.commit(['README.rst', 'CHANGELOG.rst'], 'Adding/updating some files\n\nThis is just a test')

                second_commit_hash = git.get_last_commit_identifier()
                assert second_commit_hash != first_commit_hash

                assert git.get_commit_title(second_commit_hash) == 'Adding/updating some files'

                assert git.get_remote_branches_with_commit(second_commit_hash) == []

                git.delete_last_local_commit()
                assert git.get_last_commit_identifier() == first_commit_hash
            except Exception as e:
                error = e
                raise
            finally:
                write_file(local_repo, 'CHANGELOG.rst', 'Changelog\n=========\n')
                try:
                    os.unlink(os.path.join(local_repo, 'README.rst'))
                    if not error:
                        raise AssertionError("Failed: DID NOT RAISE <class 'FileNotFoundError'>")
                except FileNotFoundError:
                    pass

    def test_revert_commit(self, git: Git, local_repo: str, remote_repo: str):
        with patch_popen_args(local_repo):
            git.checkout_item('master')
            git.create_branch('test_revert_commit')

            error: Optional[Exception] = None
            try:
                first_commit_hash = git.get_last_commit_identifier()

                write_file(local_repo, 'README.rst', 'This is a test new file\n')
                write_file(local_repo, 'CHANGELOG.rst', 'This is the replaced file contents\n')

                git.commit(['README.rst', 'CHANGELOG.rst'], 'Adding/updating some files')

                second_commit_hash = git.get_last_commit_identifier()
                assert second_commit_hash != first_commit_hash

                git.push('test_revert_commit')

                assert git.get_remote_branches_with_commit(second_commit_hash) == ['origin/test_revert_commit']

                git.revert_commit(second_commit_hash, 'test_revert_commit')

                third_commit_hash = git.get_last_commit_identifier()
                assert third_commit_hash != first_commit_hash
                assert third_commit_hash != second_commit_hash

                git.push('test_revert_commit')

                assert git.get_remote_branches_with_commit(second_commit_hash) == ['origin/test_revert_commit']
                assert git.get_remote_branches_with_commit(third_commit_hash) == ['origin/test_revert_commit']
            except Exception as e:
                error = e
                raise
            finally:
                write_file(local_repo, 'CHANGELOG.rst', 'Changelog\n=========\n')
                try:
                    os.unlink(os.path.join(local_repo, 'README.rst'))
                    if not error:
                        raise AssertionError("Failed: DID NOT RAISE <class 'FileNotFoundError'>")
                except FileNotFoundError:
                    pass
                git.checkout_item('master')
                git.delete_branch('test_revert_commit')

        with patch_popen_args(remote_repo):
            git.delete_branch('test_revert_commit')

    def test_sign_commit(
        self,
        git: Git,
        local_repo: str,
        gpg_setup: GpgSetup,
        task_context: TaskContext,
        mock_config: mock.MagicMock,
    ):
        task_context.use_gpg = True
        mock_config.gpg_command = gpg_setup.command
        mock_config.tty = get_tty()

        with patch_popen_args(cwd=local_repo, env={'GNUPGHOME': gpg_setup.directory}):
            git.checkout_item('master')
            git.create_branch('test_sign_commit_auto_key')

            try:
                write_file(local_repo, 'CHANGELOG.rst', 'Change 1\n')
                git.commit(['CHANGELOG.rst'], "This was signed with the committer's default key\n\nDetailed message")

                commit_hash = git.get_last_commit_identifier()
                assert git.get_commit_title(commit_hash) == "This was signed with the committer's default key"

                output = subprocess.check_output(
                    ['git', 'verify-commit', commit_hash],
                    stderr=subprocess.STDOUT,
                ).decode('utf-8')
                assert gpg_setup.implicit_key in output, 'The implicit key SHOULD have been used for this.'
                assert gpg_setup.explicit_key not in output, 'The explicit key should NOT have been used for this.'
            finally:
                git.checkout_item('master')
                git.delete_branch('test_sign_commit_auto_key')

            task_context.gpg_alternate_id = gpg_setup.explicit_key
            git.create_branch('test_sign_commit_explicit_key')

            try:
                write_file(local_repo, 'CHANGELOG.rst', 'Change 2\n')
                git.commit(['CHANGELOG.rst'], 'This was signed with the explicit key\n\nDetailed message')

                commit_hash = git.get_last_commit_identifier()
                assert git.get_commit_title(commit_hash) == 'This was signed with the explicit key'

                output = subprocess.check_output(
                    ['git', 'verify-commit', commit_hash],
                    stderr=subprocess.STDOUT,
                ).decode('utf-8')
                assert gpg_setup.implicit_key not in output, 'The implicit key should NOT have been used for this.'
                assert gpg_setup.explicit_key in output, 'The explicit key SHOULD have been used for this.'
            finally:
                git.checkout_item('master')
                git.delete_branch('test_sign_commit_explicit_key')

            task_context.gpg_alternate_id = 'ABC1234567890DEF'
            git.create_branch('test_sign_commit_fake_key')

            try:
                write_file(local_repo, 'CHANGELOG.rst', 'Change 3\n')

                with pytest.raises(SourceControlError) as context:
                    git.commit(['CHANGELOG.rst'], 'This was signed with a flake key\n\nDetailed message')

                assert isinstance(context.value, SourceControlError)
                assert 'Failed to commit changes due to error signing with GPG' in context.value.args[0]
            finally:
                write_file(local_repo, 'CHANGELOG.rst', 'Changelog\n=========\n')
                git.checkout_item('master')
                git.delete_branch('test_sign_commit_fake_key')

    def test_gather_commit_messages_since_last_release(self, git: Git, local_repo: str, mock_config: mock.MagicMock):
        mock_config.release_message_template = 'Released My Cool Project version {}'
        with patch_popen_args(local_repo):
            git.checkout_item('master')
            git.create_branch('test_gather_commit_messages_since_last_release')

            try:
                assert git.gather_commit_messages_since_last_release() == []

                write_file(local_repo, 'CHANGELOG.rst', 'Change 1\n')
                git.commit(['CHANGELOG.rst'], 'This is the first commit title\n\nThis commit will not be included.')

                write_file(local_repo, 'CHANGELOG.rst', 'Change 2\n')
                git.commit(['CHANGELOG.rst'], 'Released My Cool Project version 1.3.0')

                write_file(local_repo, 'CHANGELOG.rst', 'Change 3\n')
                git.commit(['CHANGELOG.rst'], 'This is the third commit title\n\nThis message will not be included.')

                write_file(local_repo, 'CHANGELOG.rst', 'Change 4\n')
                git.commit(['CHANGELOG.rst'], 'Merge pull request #1\n\nThis whole commit will be ignored')

                write_file(local_repo, 'CHANGELOG.rst', 'Change 5\n')
                git.commit(['CHANGELOG.rst'], '[MINOR] Another cool commit\n\nOnly titles are returned, not messages.')

                assert git.gather_commit_messages_since_last_release() == [
                    'This is the third commit title',
                    '[MINOR] Another cool commit',
                ]
            finally:
                git.checkout_item('master')
                git.delete_branch('test_gather_commit_messages_since_last_release')
                write_file(local_repo, 'CHANGELOG.rst', 'Changelog\n=========\n')

    def test_reset_pending_changes(self, git: Git, local_repo: str):
        with patch_popen_args(local_repo):
            git.checkout_item('master')

            try:
                write_file(local_repo, 'CHANGELOG.rst', "This is a change that we're going to reset")
                assert read_file(local_repo, 'CHANGELOG.rst') == "This is a change that we're going to reset"

                git.reset_pending_changes()

                assert read_file(local_repo, 'CHANGELOG.rst') == 'Changelog\n=========\n'
            finally:
                write_file(local_repo, 'CHANGELOG.rst', 'Changelog\n=========\n')

    def test_open_pull_request(self, git: Git, local_repo: str, remote_repo: str):
        previous_token = os.environ.pop('GITHUB_TOKEN', None)

        remote_extract = f"{remote_repo.split('/')[-2]}/{remote_repo.split('/')[-1]}".replace('.git', '')

        try:
            assert git.open_pull_request('Test Pull Request', 'master', 'branch_for_pull_request') is None

            os.environ['GITHUB_TOKEN'] = 'cao81o84to94g1tu78tu8'

            with patch_popen_args(local_repo):
                with mock.patch('invoke_release.internal.source_control.git.urllib.request.urlopen') as mock_url_open:
                    mock_url_open.side_effect = OSError('Bah humbug!')

                    with pytest.raises(SourceControlError) as context:
                        git.open_pull_request('Test Pull Request', 'master', 'branch_for_pull_request')

                    assert isinstance(context.value, SourceControlError)
                    assert context.value.args[0] == "Could not open Github PR due to error: OSError('Bah humbug!')"

                with mock.patch('invoke_release.internal.source_control.git.urllib.request.urlopen') as mock_url_open:
                    mock_url_open.return_value.__enter__.return_value.getcode.return_value = 404

                    assert git.open_pull_request('Test Pull Request', 'master', 'branch_for_pull_request') is None

                    assert mock_url_open.call_count == 1
                    assert mock_url_open.call_args[1]['timeout'] == 15
                    request = mock_url_open.call_args[0][0]

                    assert isinstance(request, urllib.request.Request)
                    assert request.data
                    assert request.full_url == f'https://api.github.com/repos/{remote_extract}/pulls'
                    assert request.headers == {
                        'Content-type': 'application/json',
                        'Authorization': 'token {}'.format('cao81o84to94g1tu78tu8'),
                        'Accept': 'application/vnd.github.v3+json',
                        'Content-length': str(len(request.data)),
                    }
                    assert json.loads(request.data.decode('utf-8')) == {
                        'title': 'Test Pull Request',
                        'base': 'master',
                        'head': 'branch_for_pull_request',
                    }

                with mock.patch('invoke_release.internal.source_control.git.urllib.request.urlopen') as mock_url_open:
                    mock_url_open.return_value.__enter__.return_value.getcode.return_value = 201
                    mock_url_open.return_value.__enter__.return_value.read.return_value = json.dumps({
                        'html_url': 'https://github.com/test/project/pull/1039',
                    }).encode('utf-8')

                    assert git.open_pull_request('Another Release PR', '1.3.x', 'invoke-release-1.3.x-1.3.7') == (
                        'https://github.com/test/project/pull/1039'
                    )

                    assert mock_url_open.call_count == 1
                    assert mock_url_open.call_args[1]['timeout'] == 15
                    request = mock_url_open.call_args[0][0]

                    assert isinstance(request, urllib.request.Request)
                    assert request.data
                    assert request.full_url == f'https://api.github.com/repos/{remote_extract}/pulls'
                    assert request.headers == {
                        'Content-type': 'application/json',
                        'Authorization': 'token {}'.format('cao81o84to94g1tu78tu8'),
                        'Accept': 'application/vnd.github.v3+json',
                        'Content-length': str(len(request.data)),
                    }
                    assert json.loads(request.data.decode('utf-8')) == {
                        'title': 'Another Release PR',
                        'base': '1.3.x',
                        'head': 'invoke-release-1.3.x-1.3.7',
                    }
        finally:
            os.environ.pop('GITHUB_TOKEN', None)
            if previous_token:
                os.environ['GITHUB_TOKEN'] = previous_token
