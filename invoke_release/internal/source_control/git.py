import functools
import json
import os
import re
import subprocess
import sys
from typing import (
    List,
    NoReturn,
    Optional,
)
import urllib.request

from invoke_release.errors import SourceControlError
from invoke_release.internal.source_control.base import (
    ItemType,
    SourceControl,
)


__all__ = (
    'Git',
)


RE_ACCOUNT_REPO = re.compile(
    r'(?:https?://|git@|file:///)(?:[a-z0-9_./-]+)[:/](?P<repo>[a-z0-9_-]+/[a-z0-9_-]+)(?:.git)?/?(?:.git)?/?$',
    re.IGNORECASE
)


def handle_subprocess_errors(method):
    @functools.wraps(method)
    def wrapper(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except subprocess.CalledProcessError as e:
            output = e.output
            if not output:
                output = b'[No captured output, see stderr above]'
            raise SourceControlError(
                f"Failed to run Git command {e.cmd}.\n{e.returncode}: {output.decode('utf-8')}",
            )

    return wrapper


class Git(SourceControl):
    @property
    def supports_gpg_signing(self):
        return True

    @handle_subprocess_errors
    def get_version(self) -> str:
        return subprocess.check_output(
            ['git', '--version'],
            stderr=sys.stderr,
        ).decode('utf-8').strip()

    @staticmethod
    @handle_subprocess_errors
    def get_root_directory() -> str:
        root_directory = subprocess.check_output(
            ['git', 'rev-parse', '--show-toplevel'],
            stderr=sys.stderr,
        ).decode('utf8').strip()

        if not root_directory:
            raise SourceControlError('Failed to find Git root directory.')
        return root_directory

    @handle_subprocess_errors
    def get_branch_name(self) -> str:
        self._context.io.verbose_output('Determining current Git branch name.')

        branch_name = subprocess.check_output(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            stderr=sys.stderr,
        ).decode('utf8').strip()

        self._context.io.verbose_output('Current Git branch name is {}.', branch_name)

        return branch_name

    @handle_subprocess_errors
    def create_branch(
        self,
        branch_name: str,
        from_item: Optional[str] = None,
        from_item_type: ItemType = ItemType.BRANCH
    ) -> None:
        self._context.io.verbose_output('Creating branch {}...', branch_name)

        cmd = ['git', 'checkout']
        if from_item:
            cmd.append(f'tags/{from_item}' if from_item_type is ItemType.TAG else from_item)
        cmd.extend(['-b', branch_name])

        subprocess.check_call(
            cmd,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )

        self._context.io.verbose_output('Done creating branch {}.', branch_name)

    @handle_subprocess_errors
    def checkout_remote_branch(self, branch_name: str) -> None:
        self._context.io.verbose_output(
            'Creating local branch {branch} set up to track remote branch {branch} from origin...',
            branch=branch_name
        )

        subprocess.check_call(['git', 'fetch', 'origin'], stdout=sys.stdout, stderr=sys.stderr)

        subprocess.check_call(
            ['git', 'checkout', '--track', f'origin/{branch_name}'],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )

        self._context.io.verbose_output('Done checking out branch {}.', branch_name)

    @handle_subprocess_errors
    def delete_branch(self, branch_name: str) -> None:
        self._context.io.verbose_output('Deleting branch {}...', branch_name)

        subprocess.check_call(
            ['git', 'branch', '-D', branch_name],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )

        self._context.io.verbose_output('Done deleting branch {}.', branch_name)

    @handle_subprocess_errors
    def branch_exists_remotely(self, branch_name: str) -> bool:
        self._context.io.verbose_output('Checking if branch {} exists on remote...', branch_name)

        result = subprocess.check_output(
            ['git', 'ls-remote', '--heads', 'origin', branch_name],
            stderr=sys.stderr,
        ).decode('utf8').strip()

        on_remote = branch_name in result

        self._context.io.verbose_output(
            'Result of on-remote check for branch {branch_name} is {result}.',
            branch_name=branch_name,
            result=on_remote,
        )

        return on_remote

    @handle_subprocess_errors
    def get_remote_branches_with_commit(self, commit_id: str) -> List[str]:
        self._context.io.verbose_output('Checking if commit {} was pushed to any remote branches...', commit_id)

        result = subprocess.check_output(
            ['git', 'branch', '-r', '--contains', commit_id],
            stderr=sys.stderr,
        ).decode('utf8').strip()

        on_remote: List[str] = []
        for line in result.splitlines():
            line = line.strip()
            if line.startswith('origin/') and not line.startswith('origin/HEAD'):
                on_remote.append(line)

        self._context.io.verbose_output(
            'Result of on-remote check for commit {hash} is {remote}.',
            hash=commit_id,
            remote=on_remote,
        )

        return on_remote

    @handle_subprocess_errors
    def create_tag(self, tag_name: str, tag_message: str) -> None:
        self._context.io.verbose_output('Tagging branch {}...', tag_name)

        cmd = ['git', 'tag', '-a', tag_name, '-m', tag_message]

        if self._context.use_gpg:
            self._configure_gpg()
            if self._context.gpg_alternate_id:
                cmd.extend(['-u', self._context.gpg_alternate_id])
            else:
                cmd.append('-s')

        env = dict(os.environ)
        if self._context.use_gpg and self._context.config.tty:
            env['GPG_TTY'] = self._context.config.tty

        try:
            result = subprocess.check_output(
                cmd,
                stderr=subprocess.STDOUT,
                env=env,
            ).decode('utf8')
        except subprocess.CalledProcessError as e:
            error = e.output.decode('utf-8') if e.output else None
            if error and ('unable to sign' in error or 'failed to sign' in error):
                self._raise_gpg_error('tagging release', error)
            raise

        if result:
            if 'unable to sign' in result or 'failed to sign' in result:
                self._raise_gpg_error('tagging release', result)
            raise SourceControlError(f'Failed tagging release: {result}')

        if self._context.use_gpg:
            try:
                subprocess.check_call(
                    ['git', 'tag', '-v', tag_name],
                    stdout=sys.stdout,
                    stderr=sys.stderr,
                )
            except subprocess.CalledProcessError:
                raise SourceControlError(
                    'Successfully created a signed release tag, but failed to verify its signature. '
                    'Something is not right.'
                )

        self._context.io.verbose_output('Finished tagging branch.')

    @handle_subprocess_errors
    def delete_tag_locally(self, tag_name: str) -> None:
        self._context.io.verbose_output('Deleting local tag {}...', tag_name)

        subprocess.check_call(
            ['git', 'tag', '-d', tag_name],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )

        self._context.io.verbose_output('Finished deleting local tag {}.', tag_name)

    @handle_subprocess_errors
    def delete_tag_remotely(self, tag_name: str) -> None:
        self._context.io.verbose_output('Deleting remote tag {}...', tag_name)

        subprocess.check_call(
            ['git', 'push', 'origin', f':refs/tags/{tag_name}'],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )

        self._context.io.verbose_output('Finished deleting remote tag {}.', tag_name)

    @handle_subprocess_errors
    def fetch_remote_tags(self) -> None:
        self._context.io.verbose_output('Fetching all remote tags...')

        subprocess.check_call(
            ['git', 'fetch', '--tags'],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )

        self._context.io.verbose_output('Done fetching tags.')

    @handle_subprocess_errors
    def list_tags(self) -> List[str]:
        self._context.io.verbose_output('Parsing list of local tags...')

        result = subprocess.check_output(
            ['git', 'tag', '--list'],
            stderr=sys.stderr,
        ).decode('utf8').strip().split()

        self._context.io.verbose_output('Result of tag list parsing is {}.', result)

        return result

    @handle_subprocess_errors
    def tag_exists_remotely(self, tag_name: str) -> bool:
        self._context.io.verbose_output('Checking if tag {} was pushed to remote...', tag_name)

        result = subprocess.check_output(
            ['git', 'ls-remote', '--tags', 'origin', tag_name],
            stderr=sys.stderr,
        ).decode('utf8').strip()

        on_remote = tag_name in result

        self._context.io.verbose_output(
            'Result of on-remote check for tag {tag} is {result}.',
            tag=tag_name,
            result=on_remote,
        )

        return on_remote

    @handle_subprocess_errors
    def tag_exists_locally(self, tag_name: str) -> bool:
        self._context.io.verbose_output('Checking if tag {} exists locally...', tag_name)

        result = subprocess.check_output(
            ['git', 'tag', '--list', tag_name],
            stderr=sys.stderr,
        ).decode('utf8').strip()

        exists = tag_name in result

        self._context.io.verbose_output(
            'Result of exists check for tag {tag} is {result}.',
            tag=tag_name,
            result=exists,
        )

        return exists

    @handle_subprocess_errors
    def checkout_item(self, item_name: str) -> None:
        self._context.io.verbose_output('Checking out item {}...', item_name)

        subprocess.check_call(
            ['git', 'checkout', item_name],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )

        self._context.io.verbose_output('Done checking out item {}.', item_name)

    @handle_subprocess_errors
    def delete_last_local_commit(self) -> None:
        self._context.io.verbose_output('Deleting last commit, assumed to be for version and changelog files...')

        subprocess.check_call(
            ['git', 'reset', '--hard', 'HEAD~1'],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )

        self._context.io.verbose_output('Finished deleting last commit.')

    @handle_subprocess_errors
    def revert_commit(self, commit_id: str, branch_name: str) -> None:
        self._context.io.verbose_output('Rolling back release commit on remote branch "{}"...', branch_name)

        subprocess.check_call(
            ['git', 'revert', '--no-edit', commit_id],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )

        self._context.io.verbose_output('Pushing revert to remote branch "{}"...', branch_name)
        subprocess.check_call(
            ['git', 'push', 'origin', f'{branch_name}:{branch_name}'],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )

        self._context.io.verbose_output('Finished rolling back release commit.')

    @handle_subprocess_errors
    def stash_changes(self) -> bool:
        self._context.io.verbose_output('Stashing changes...')

        result = subprocess.check_output(
            ['git', 'stash', '--include-untracked'],
            stderr=sys.stderr,
        ).decode('utf8')
        if result.startswith('Saved'):
            self._context.io.verbose_output('Finished stashing changes.')
            return True

        self._context.io.verbose_output('No changes were stashed.')
        return False

    @handle_subprocess_errors
    def unstash_changes(self) -> None:
        self._context.io.verbose_output('Un-stashing changes...')

        subprocess.check_output(
            ['git', 'stash', 'pop'],
            stderr=sys.stderr,
        )

        self._context.io.verbose_output('Finished un-stashing changes.')

    @handle_subprocess_errors
    def gather_commit_messages_since_last_release(self) -> List[str]:
        self._context.io.verbose_output('Gathering commit messages since last release commit.')

        command = [
            'git',
            'log',
            '-1',
            '--format=%H',
            '--grep={}'.format(self._context.config.release_message_template.replace(' {}', '').replace('"', '\\"'))
        ]
        self._context.io.verbose_output('Running command: "{}"', '" "'.join(command))
        commit_hash = subprocess.check_output(command, stderr=sys.stderr).decode('utf8').strip()

        if not commit_hash:
            self._context.io.verbose_output('No previous release commit was found. Not gathering messages.')
            return []

        command = [
            'git',
            'log',
            '--format=%s',
            f'{commit_hash}..HEAD',
        ]
        self._context.io.verbose_output('Running command: "{}"', '" "'.join(command))
        output = subprocess.check_output(command, stderr=sys.stderr).decode('utf8')

        messages = []
        for message in reversed(output.splitlines()):
            if not message.strip().startswith('Merge pull request #'):
                messages.append(message.strip())

        self._context.io.verbose_output(
            'Returning {number} commit messages gathered since last release commit:\n{messages}',
            number=len(messages),
            messages=messages,
        )

        return messages

    @handle_subprocess_errors
    def reset_pending_changes(self) -> None:
        self._context.io.verbose_output('Resetting all un-staged changes...')

        subprocess.check_call(
            ['git', 'reset', '--hard'],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )

        self._context.io.verbose_output('Done resetting changes.')

    @handle_subprocess_errors
    def commit(self, files: List[str], message: str) -> None:
        self._context.io.verbose_output('Committing release changes...')

        result = subprocess.check_output(['git', 'add'] + files, stderr=subprocess.STDOUT)
        if result:
            raise SourceControlError(f"Failed staging release files for commit: {result.decode('utf-8').strip()}")

        cmd = ['git', 'commit']
        env = dict(os.environ)

        if self._context.use_gpg:
            self._configure_gpg()
            if self._context.gpg_alternate_id:
                cmd.append(f'--gpg-sign={self._context.gpg_alternate_id}')
            else:
                cmd.append('--gpg-sign')

            if self._context.config.tty:
                env['GPG_TTY'] = self._context.config.tty

        cmd.extend(['-m', message])

        try:
            output = subprocess.check_output(
                cmd,
                stderr=subprocess.STDOUT,
                env=env,
            )
        except subprocess.CalledProcessError as e:
            error = e.output.decode('utf-8') if e.output else None
            if error and ('unable to sign' in error or 'failed to sign' in error):
                self._raise_gpg_error('to commit changes', error)
            raise

        sys.stdout.write(output.decode('utf-8'))
        sys.stdout.flush()

        if self._context.use_gpg:
            try:
                subprocess.check_call(
                    ['git', 'verify-commit', self.get_last_commit_identifier()],
                    stdout=sys.stdout,
                    stderr=sys.stderr,
                )
            except subprocess.CalledProcessError:
                raise SourceControlError(
                    'Successfully committed the changes, but failed to verify the commit signature. '
                    'Something is not right.'
                )

        self._context.io.verbose_output('Finished releasing changes.')

    @handle_subprocess_errors
    def push(self, item: str, item_type: ItemType = ItemType.BRANCH, set_tracking: bool = False) -> None:
        self._context.io.verbose_output('Pushing item {} to remote.', item)

        if item_type is ItemType.BRANCH:
            ref_spec = f'{item}:{item}'
        else:
            ref_spec = f'refs/tags/{item}:refs/tags/{item}'

        subprocess.check_call(
            ['git', 'push', 'origin', ref_spec],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )

        self._context.io.verbose_output('Done pushing item {} to remote.', item)

        if item_type is ItemType.BRANCH and set_tracking:
            self._context.io.verbose_output('Setting local branch {} to track remote branch origin/{}')

            subprocess.check_call(
                ['git', 'branch', f'--set-upstream-to=origin/{item}', item],
                stdout=sys.stdout,
                stderr=sys.stderr,
            )

            self._context.io.verbose_output('Done setting branch tracking.')

    @handle_subprocess_errors
    def pull_if_tracking_remote(self) -> bool:
        result = subprocess.check_output(
            ['git', 'status', '-sb'],
            stderr=subprocess.STDOUT,
        ).decode('utf-8').strip().split('\n')[0].strip(' #\n\t').split('...')
        assert len(result) in (1, 2)

        if len(result) == 2 and result[1].strip().startswith('origin/'):
            self._context.io.verbose_output(
                'Local branch {} tracks remote {}, so pulling changes',
                result[0],
                result[1],
            )

            subprocess.check_call(['git', 'pull'], stdout=sys.stdout, stderr=sys.stderr)

            self._context.io.verbose_output('Done pulling changes')

            return True

        return False

    @handle_subprocess_errors
    def get_last_commit_identifier(self) -> str:
        self._context.io.verbose_output('Getting last commit hash...')

        commit_hash = subprocess.check_output(
            ['git', 'log', '-n', '1', '--pretty=format:%H'],
            stderr=sys.stderr,
        ).decode('utf8').strip()

        self._context.io.verbose_output('Last commit hash is {}.', commit_hash)

        return commit_hash

    @handle_subprocess_errors
    def get_commit_title(self, commit_id: str) -> str:
        self._context.io.verbose_output('Getting commit message for hash {}...', commit_id)

        message = subprocess.check_output(
            ['git', 'log', '-n', '1', '--pretty=format:%s', commit_id],
            stderr=sys.stderr,
        ).decode('utf8').strip()

        self._context.io.verbose_output('Commit message for hash {hash} is "{value}".', hash=commit_id, value=message)

        return message

    @staticmethod
    def remote_url_to_github_account_and_repo(remote: str) -> str:
        match = RE_ACCOUNT_REPO.match(remote)
        if not match:
            raise SourceControlError(f"Could not detect GitHub account and repo from remote '{remote}'")

        return match.group('repo')

    @handle_subprocess_errors
    def open_pull_request(self, title: str, base: str, head: str) -> Optional[str]:
        github_api_token = os.environ.get('GITHUB_TOKEN')
        if github_api_token:
            remote = subprocess.check_output(
                ['git', 'remote', 'get-url', 'origin'],
                stderr=subprocess.STDOUT,
            ).decode('utf-8').strip()
            repo = self.remote_url_to_github_account_and_repo(remote)
            url = 'https://api.github.com/repos/{}/pulls'.format(repo)
            body = json.dumps({
                'title': title,
                'base': base,
                'head': head,
            }).encode('utf-8')
            headers = {
                'Content-type': 'application/json',
                'Authorization': 'token {}'.format(github_api_token),
                'Accept': 'application/vnd.github.v3+json',
                'Content-length': str(len(body)),
            }

            try:
                req = urllib.request.Request(url, body, headers)
                with urllib.request.urlopen(req, timeout=15) as f:
                    # GitHub will always answer with 201 if the PR was `CREATED`.
                    if f.getcode() != 201:
                        return None
                    return json.loads(f.read().decode('utf-8'))['html_url']
            except Exception as e:
                raise SourceControlError(f'Could not open Github PR due to error: {e!r}')
        else:
            self._context.io.standard_output(
                'Then environment variable `GITHUB_TOKEN` is not set. Will not open GitHub PR.'
            )
            return None

    def _configure_gpg(self) -> None:
        try:
            assert self._context.config.gpg_command
            subprocess.check_output(
                ['git', 'config', '--global', 'gpg.program', self._context.config.gpg_command],
            )
        except subprocess.CalledProcessError as e:
            raise SourceControlError(
                'Failed to configure Git+GPG. Something is not right. Aborting.\n'
                f"{e.returncode}: {e.output.decode('utf8')}"
            )

    def _raise_gpg_error(self, what: str, output: str) -> NoReturn:
        gpg = self._context.config.gpg_command
        raise SourceControlError(
            f'Failed {what} due to error signing with GPG. Perhaps you need to create a code-signing key, or '
            'the alternate key ID you specified was incorrect?\n\n'
            'Suggestions:\n'
            f' - Generate a key with `{gpg} --get-key` (GPG v1) or `{gpg} --full-gen-key` (GPG v2) (and use 4096)\n'
            ' - It is not enough for the key email to match your committer email; the full display name must '
            'match, too (e.g. "First Last <email@example.org>")\n'
            ' - If the key display name does not match the committer display name, use the alternate key ID\n'
            f'Error output: {output}'
        )
