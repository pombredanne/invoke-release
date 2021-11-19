from __future__ import absolute_import, unicode_literals

import codecs
from contextlib import closing
import datetime
from distutils.version import LooseVersion
import json
import os
from pkg_resources import parse_version
import re
import shlex
import subprocess
import sys
import tempfile

from invoke import task
import six
from six import moves
from six.moves import urllib
from wheel import archive

RE_CHANGELOG_FILE_HEADER = re.compile(r'^=+$')
RE_CHANGELOG_VERSION_HEADER = re.compile(r'^-+$')
RE_FILE_EXTENSION = re.compile(r'\.\w+$')
RE_VERSION = re.compile(r'^\d+\.\d+\.\d+([a-zA-Z\d.+-]*[a-zA-Z\d]+)?$')
RE_VERSION_BRANCH_MAJOR = re.compile(r'^\d+\.x\.x$')
RE_VERSION_BRANCH_MINOR = re.compile(r'^\d+\.\d+\.x$')
RE_SPLIT_AFTER_DIGITS = re.compile(r'(\d+)')

VERSION_INFO_VARIABLE_TEMPLATE = '__version_info__ = {}'
VERSION_VARIABLE_TEMPLATE = (
    "__version__ = '{}'.join(filter(None, ['.'.join(map(str, __version_info__[:3])), "
    "(__version_info__[3:] or [None])[0]]))"
)
RELEASE_MESSAGE_TEMPLATE = 'Released [unknown] version {}'

MODULE_NAME = 'unknown'
MODULE_DISPLAY_NAME = '[unknown]'
USE_PULL_REQUEST = False
USE_TAG = True

RELEASE_PLUGINS = []

ROOT_DIRECTORY = ''
VERSION_FILENAME = 'python/unknown/version.py'
VERSION_FILE_IS_TXT = False
CHANGELOG_FILENAME = 'CHANGELOG.txt'
CHANGELOG_COMMENT_FIRST_CHAR = '#'

PARAMETERS_CONFIGURED = False

__POST_APPLY = False

__all__ = [
    'configure_release_parameters',
    'version',
    'branch',
    'wheel',
    'release',
    'rollback_release',
]

_output = sys.stdout
_output_is_tty = _output.isatty()

COLOR_GREEN_BOLD = '32;1'
COLOR_RED_STANDARD = '31'
COLOR_RED_BOLD = '31;1'
COLOR_GRAY_LIGHT = '38;5;242'
COLOR_WHITE = '37;1'

PUSH_RESULT_NO_ACTION = 0
PUSH_RESULT_PUSHED = 1
PUSH_RESULT_ROLLBACK = 2

HEAD_BRANCH = 'HEAD branch: '

INSTRUCTION_NO = 'n'
INSTRUCTION_YES = 'y'
INSTRUCTION_NEW = 'new'
INSTRUCTION_EDIT = 'edit'
INSTRUCTION_ACCEPT = 'accept'
INSTRUCTION_DELETE = 'delete'
INSTRUCTION_EXIT = 'exit'
INSTRUCTION_ROLLBACK = 'rollback'
INSTRUCTION_MAJOR = 'major'

MAJOR_VERSION_PREFIX = '- [MAJOR]'
MINOR_VERSION_PREFIX = '- [MINOR]'
PATCH_VERSION_PREFIX = '- [PATCH]'


class ErrorStreamWrapper(object):
    def __init__(self, wrapped):
        self.wrapped = wrapped

    def write(self, err):
        self.wrapped.write('\x1b[{color}m{err}\x1b[0m'.format(color=COLOR_RED_STANDARD, err=err))

    def writelines(self, lines):
        self.wrapped.write('\x1b[{}m'.format(COLOR_RED_STANDARD))
        self.wrapped.writelines(lines)
        self.wrapped.write('\x1b[0m')

    def __getattribute__(self, item):
        try:
            return super(ErrorStreamWrapper, self).__getattribute__(item)
        except AttributeError:
            return self.wrapped.__getattribute__(item)


sys.stderr = ErrorStreamWrapper(sys.stderr)


class ReleaseFailure(Exception):
    """
    Exception raised when something caused the release to fail, and cleanup is required.
    """


class ReleaseExit(Exception):
    """
    Control-flow exception raised to cancel a release before changes are made.
    """


def _print_output(color, message, *args, **kwargs):
    if _output_is_tty:
        _output.write(
            '\x1b[{color}m{message}\x1b[0m'.format(
                color=color,
                message=message.format(*args, **kwargs),
            ),
        )
        _output.flush()
    else:
        print(message.format(*args, **kwargs))


def _standard_output(message, *args, **kwargs):
    _print_output(COLOR_GREEN_BOLD, message + '\n', *args, **kwargs)


def _prompt(message, *args, **kwargs):
    _print_output(COLOR_WHITE, message + ' ', *args, **kwargs)
    # noinspection PyCompatibility
    response = moves.input()
    if response:
        if not isinstance(response, six.text_type):
            # Input returns a bytestring in Python 2 and a unicode string in Python 3
            return response.decode('utf8').strip()
        return response.strip()
    return ''


def _error_output(message, *args, **kwargs):
    _print_output(COLOR_RED_BOLD, ''.join(('ERROR: ', message, '\n')), *args, **kwargs)


def _error_output_exit(message, *args, **kwargs):
    _error_output(message, *args, **kwargs)
    sys.exit(1)


def _verbose_output(verbose, message, *args, **kwargs):
    if verbose:
        _print_output(COLOR_GRAY_LIGHT, ''.join(('DEBUG: ', message, '\n')), *args, **kwargs)


def _case_sensitive_regular_file_exists(filename):
    if not os.path.isfile(filename):
        # Short circuit
        return False
    directory, filename = os.path.split(filename)
    return filename in os.listdir(directory)


def _get_root_directory():
    root_directory = subprocess.check_output(
        ['git', 'rev-parse', '--show-toplevel'],
        stderr=sys.stderr,
    ).decode('utf8').strip()

    if not root_directory:
        _error_output_exit('Failed to find Git root directory.')
    return root_directory


def _setup_task(no_stash, verbose):
    if not no_stash:
        global __POST_APPLY
        # stash changes before we execute task
        _verbose_output(verbose, 'Stashing changes...')

        result = subprocess.check_output(
            ['git', 'stash'],
            stderr=sys.stderr,
        ).decode('utf8')
        if result.startswith('Saved'):
            __POST_APPLY = True

        _verbose_output(verbose, 'Finished stashing changes.')


def _cleanup_task(verbose):
    if __POST_APPLY:
        _verbose_output(verbose, 'Un-stashing changes...')

        subprocess.check_output(
            ['git', 'stash', 'pop'],
            stderr=sys.stderr,
        )

        _verbose_output(verbose, 'Finished un-stashing changes.')


def _write_to_version_file(release_version, version_info, version_separator, verbose):
    _verbose_output(verbose, 'Writing version to {}...', VERSION_FILENAME)

    if not _case_sensitive_regular_file_exists(VERSION_FILENAME):
        raise ReleaseFailure(
            'Failed to find version file: {}. File names are case sensitive!'.format(VERSION_FILENAME),
        )

    if VERSION_FILE_IS_TXT:
        with codecs.open(VERSION_FILENAME, 'wb', encoding='utf8') as version_write:
            version_write.write(release_version)
    else:
        with codecs.open(VERSION_FILENAME, 'rb', encoding='utf8') as version_read:
            output = []
            version_info_written = False
            # We replace u' with ' in this, because Py2 projects should use unicode_literals in their version file
            version_info = VERSION_INFO_VARIABLE_TEMPLATE.format(tuple(version_info)).replace(", u'", ", '")
            for line in version_read:
                if line.startswith('__version_info__'):
                    output.append(version_info)
                    version_info_written = True
                elif line.startswith('__version__'):
                    if not version_info_written:
                        output.append(version_info)
                    output.append(VERSION_VARIABLE_TEMPLATE.format(version_separator))
                else:
                    output.append(line.rstrip())

        with codecs.open(VERSION_FILENAME, 'wb', encoding='utf8') as version_write:
            for line in output:
                version_write.write(line + '\n')

    _verbose_output(verbose, 'Finished writing to {}.version.', MODULE_NAME)


def _gather_commit_messages(verbose):
    _verbose_output(verbose, 'Gathering commit messages since last release commit.')

    command = [
        'git',
        'log',
        '-1',
        '--format=%H',
        '--grep={}'.format(RELEASE_MESSAGE_TEMPLATE.replace(' {}', '').replace('"', '\\"'))
    ]
    _verbose_output(verbose, 'Running command: "{}"', '" "'.join(command))
    commit_hash = subprocess.check_output(command, stderr=sys.stderr).decode('utf8').strip()

    if not commit_hash:
        _verbose_output(verbose, 'No previous release commit was found. Not gathering messages.')
        return []

    command = [
        'git',
        'log',
        '--format=%s',
        '{}..HEAD'.format(commit_hash)
    ]
    _verbose_output(verbose, 'Running command: "{}"', '" "'.join(command))
    output = subprocess.check_output(command, stderr=sys.stderr).decode('utf8')

    messages = []
    for message in output.splitlines():
        if not message.strip().startswith('Merge pull request #'):
            messages.append('- {}'.format(message))

    _verbose_output(
        verbose,
        'Returning {number} commit messages gathered since last release commit:\n{messages}',
        number=len(messages),
        messages=messages,
    )

    return messages


def _prompt_for_changelog(verbose):
    built_up_changelog = []
    changelog_header = []
    changelog_message = []
    changelog_footer = []

    _verbose_output(verbose, 'Reading changelog file {} looking for built-up changes...', CHANGELOG_FILENAME)
    with codecs.open(CHANGELOG_FILENAME, 'rb', encoding='utf8') as changelog_read:
        previous_line = ''
        passed_header = passed_changelog = False
        for line_number, line in enumerate(changelog_read):
            if not passed_header:
                changelog_header.append(line)
                # .txt and .md changelog files start like this:
                #     Changelog
                #     =========
                # .rst changelog files start like this
                #     =========
                #     Changelog
                #     =========
                if line_number > 0 and RE_CHANGELOG_FILE_HEADER.search(line):
                    passed_header = True
                continue

            if not passed_changelog and RE_CHANGELOG_VERSION_HEADER.search(line):
                changelog_footer.append(previous_line)
                passed_changelog = True

            if passed_changelog:
                changelog_footer.append(line)
            else:
                if previous_line.strip():
                    built_up_changelog.append(previous_line)

                previous_line = line

    if len(built_up_changelog) > 0:
        _verbose_output(verbose, 'Read {} lines of built-up changelog text:', len(built_up_changelog))
        if verbose:
            _verbose_output(verbose, six.text_type(built_up_changelog))
        _standard_output('There are existing changelog details for this release. You can "edit" the changes, '
                         '"accept" them as-is, delete them and create a "new" changelog message, or "delete" '
                         'them and enter no changelog.')
        instruction = _prompt('How would you like to proceed? (EDIT/new/accept/delete/exit):').lower()

        if instruction in (INSTRUCTION_NEW, INSTRUCTION_DELETE):
            built_up_changelog = []
        if instruction == INSTRUCTION_ACCEPT:
            changelog_message = built_up_changelog
        if not instruction or instruction in (INSTRUCTION_EDIT, INSTRUCTION_NEW):
            instruction = INSTRUCTION_YES
    else:
        _verbose_output(verbose, 'No existing lines of built-up changelog text were read.')
        instruction = _prompt(
            'Would you like to enter changelog details for this release? (Y/n/exit):',
        ).lower() or INSTRUCTION_YES

    if instruction == INSTRUCTION_EXIT:
        raise ReleaseExit()

    if instruction == INSTRUCTION_YES:
        gather = _prompt(
            'Would you like to{also} gather commit messages from recent commits and add them to the '
            'changelog? ({y_n}/exit):',
            **({'also': ' also', 'y_n': 'y/N'} if built_up_changelog else {'also': '', 'y_n': 'Y/n'})
        ).lower() or (INSTRUCTION_NO if built_up_changelog else INSTRUCTION_YES)

        commit_messages = []
        if gather == INSTRUCTION_YES:
            commit_messages = _gather_commit_messages(verbose)
        elif gather == INSTRUCTION_EXIT:
            raise ReleaseExit()

        tf_o = tempfile.NamedTemporaryFile(mode='wb')
        codec = codecs.lookup('utf8')
        with codecs.StreamReaderWriter(tf_o, codec.streamreader, codec.streamwriter, 'strict') as tf:
            _verbose_output(verbose, 'Opened temporary file {} for editing changelog.', tf.name)
            if commit_messages:
                tf.write('\n'.join(commit_messages) + '\n')
            if built_up_changelog:
                tf.writelines(built_up_changelog)
            tf.writelines([
                '\n',
                '# Enter your changelog message above this comment, then save and close editor when finished.\n',
                '# Any existing contents were pulled from changes to CHANGELOG.txt since the last release.\n',
                '# Leave it blank (delete all existing contents) to release with no changelog details.\n',
                '# All lines starting with "#" are comments and ignored.\n',
                '# As a best practice, if you are entering multiple items as a list, prefix each item with a "-".'
            ])
            tf.flush()
            _verbose_output(verbose, 'Wrote existing changelog contents and instructions to temporary file.')

            editor = os.environ.get('INVOKE_RELEASE_EDITOR', os.environ.get('EDITOR', 'vim'))
            _verbose_output(verbose, 'Opening editor {} to edit changelog.', editor)
            try:
                subprocess.check_call(
                    shlex.split(editor) + [tf.name],
                    stdout=sys.stdout,
                    stderr=sys.stderr,
                )
            except (subprocess.CalledProcessError, OSError) as e:
                args = {'editor': editor}
                if isinstance(e, OSError):
                    message = 'Failed to open changelog editor `{editor}` due to error: {error} (err {error_code}).'
                    args.update(error=e.strerror, error_code=e.errno)
                else:
                    message = 'Failed to open changelog editor `{editor}` due to return code: {return_code}.'
                    args.update(return_code=e.returncode)

                message += (
                    ' Try setting $INVOKE_RELEASE_EDITOR or $EDITOR in your shell profile to the full path to '
                    'Vim or another editor.'
                )

                raise ReleaseFailure(message.format(**args))
            _verbose_output(verbose, 'User has closed editor')

            with codecs.open(tf.name, 'rb', encoding='utf8') as read:
                first_line = True
                last_line_blank = False
                for line in read:
                    line_blank = not line.strip()
                    if (first_line or last_line_blank) and line_blank:
                        # Suppress leading blank lines and compress multiple blank lines into one
                        continue
                    if line.startswith(CHANGELOG_COMMENT_FIRST_CHAR):
                        # Suppress comments
                        continue
                    changelog_message.append(line)
                    last_line_blank = line_blank
                    first_line = False
                if last_line_blank:
                    # Suppress trailing blank lines
                    changelog_message.pop()
            _verbose_output(verbose, 'Changelog message read from temporary file:\n{}', changelog_message)

    return changelog_header, changelog_message, changelog_footer


def _write_to_changelog_file(release_version, changelog_header, changelog_message, changelog_footer, verbose):
    _verbose_output(verbose, 'Writing changelog contents to {}.', CHANGELOG_FILENAME)

    if not _case_sensitive_regular_file_exists(CHANGELOG_FILENAME):
        raise ReleaseFailure(
            'Failed to find changelog file: {}. File names are case sensitive!'.format(CHANGELOG_FILENAME),
        )

    with codecs.open(CHANGELOG_FILENAME, 'wb', encoding='utf8') as changelog_write:
        header_line = '{version} ({date})'.format(
            version=release_version,
            date=datetime.datetime.now().strftime('%Y-%m-%d'),
        )

        changelog_write.writelines(changelog_header + ['\n'])
        if changelog_message:
            changelog_write.writelines([
                header_line, '\n', '-' * len(header_line), '\n',
            ])
            changelog_write.writelines(changelog_message + ['\n'])
        changelog_write.writelines(changelog_footer)

    _verbose_output(verbose, 'Finished writing to changelog.')


def _tag_branch(release_version, changelog_lines, verbose, overwrite=False):
    _verbose_output(verbose, 'Tagging branch...')

    try:
        gpg = subprocess.check_output(['which', 'gpg']).decode('utf8').strip()
        _verbose_output(verbose, 'Found location of `gpg` to be {}'.format(gpg))
    except subprocess.CalledProcessError:
        gpg = None
    if not gpg:
        try:
            gpg = subprocess.check_output(['which', 'gpg2']).decode('utf8').strip()
            _verbose_output(verbose, 'Found location of `gpg2` to be {}'.format(gpg))
        except subprocess.CalledProcessError:
            gpg = None

    try:
        tty = subprocess.check_output(['tty']).decode('utf8').strip()
        _verbose_output(verbose, 'Found location of `tty` to be {}'.format(tty))
    except subprocess.CalledProcessError:
        _verbose_output(verbose, 'Could not get tty path ... Maybe a problem? Maybe not.')
        tty = ''

    release_message = RELEASE_MESSAGE_TEMPLATE.format(release_version)
    if changelog_lines:
        release_message += '\n\nChangelog Details:'
        for line in changelog_lines:
            release_message += '\n' + line.strip()

    cmd = ['git', 'tag', '-a', release_version, '-m', release_message]
    if overwrite:
        cmd.append('-f')

    signed = False
    if gpg:
        sign_with_key = _prompt(
            'GPG is installed on your system. Would you like to sign the release tag with your GitHub committer email '
            'GPG key? (y/N/[alternative key ID]):',
        ).lower() or INSTRUCTION_NO

        if sign_with_key == INSTRUCTION_YES:
            cmd.append('-s')
        elif sign_with_key != INSTRUCTION_NO:
            cmd.extend(['-u', sign_with_key])

        if sign_with_key != INSTRUCTION_NO:
            signed = True
            try:
                subprocess.check_output(
                    ['git', 'config', '--global', 'gpg.program', gpg],
                )
            except subprocess.CalledProcessError as e:
                raise ReleaseFailure(
                    'Failed to configure Git+GPG. Something is not right. Aborting.\n{code}: {output}'.format(
                        code=e.returncode,
                        output=e.output.decode('utf8'),
                    )
                )
    else:
        _standard_output('GPG is not installed on your system. Will not sign the release tag.')

    try:
        result = subprocess.check_output(
            cmd,
            stderr=subprocess.STDOUT,
            env=dict(os.environ, GPG_TTY=tty),
        ).decode('utf8')
    except subprocess.CalledProcessError as e:
        result = '`git` command exit code {code} - {output}'.format(code=e.returncode, output=e.output.decode('utf8'))

    if result:
        if 'unable to sign the tag' in result:
            raise ReleaseFailure(
                'Failed tagging branch due to error signing the tag. Perhaps you need to create a code-signing key, or '
                'the alternate key ID you specified was incorrect?\n\n'
                'Suggestions:\n'
                ' - Generate a key with `{gpg} --get-key` (GPG v1) or `{gpg} --full-gen-key` (GPG v2) (and use 4096)\n'
                ' - It is not enough for the key email to match your committer email; the full display name must '
                'match, too (e.g. "First Last <email@example.org>")\n'
                ' - If the key display name does not match the committer display name, use the alternate key ID\n'
                'Error output: {output}'.format(gpg=gpg, output=result)
            )
        raise ReleaseFailure('Failed tagging branch: {}'.format(result))

    if signed:
        try:
            subprocess.check_call(
                ['git', 'tag', '-v', release_version],
                stdout=sys.stdout,
                stderr=sys.stderr,
            )
        except subprocess.CalledProcessError:
            raise ReleaseFailure(
                'Successfully created a signed release tag, but failed to verify its signature. Something is not right.'
            )

    _verbose_output(verbose, 'Finished tagging branch.')


def _commit_release_changes(release_version, changelog_lines, verbose):
    _verbose_output(verbose, 'Committing release changes...')

    files_to_commit = [VERSION_FILENAME, CHANGELOG_FILENAME] + _get_extra_files_to_commit()
    _verbose_output(verbose, 'Staging changes for files {}.'.format(files_to_commit))

    try:
        result = subprocess.check_output(
            ['git', 'add'] + files_to_commit,
            stderr=subprocess.STDOUT,
        )
    except subprocess.CalledProcessError as e:
        result = '`git` command exit code {code} - {output}'.format(code=e.returncode, output=e.output.decode('utf8'))

    if result:
        raise ReleaseFailure('Failed staging release files for commit: {}'.format(result))

    release_message = [RELEASE_MESSAGE_TEMPLATE.format(release_version)]
    if changelog_lines:
        release_message.append('\nChangelog Details:')
        for line in changelog_lines:
            release_message.append(line.strip())

    subprocess.check_call(
        ['git', 'commit', '-m', '\n'.join(release_message)],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    _verbose_output(verbose, 'Finished releasing changes.')


def _push_release_changes(release_version, branch_name, default_branch, verbose):
    try:
        if USE_TAG:
            message = 'Push release changes and tag to remote origin (branch "{}")? (y/N/rollback):'
        else:
            message = 'Push release changes to remote origin (branch "{}")? (y/N/rollback):'
        push = _prompt(message, branch_name).lower()
    except KeyboardInterrupt:
        push = INSTRUCTION_ROLLBACK

    if push == INSTRUCTION_YES:
        _verbose_output(verbose, 'Pushing changes to remote origin...')

        subprocess.check_call(
            ['git', 'push', 'origin', '{0}:{0}'.format(branch_name)],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
        if USE_TAG:
            # push the release tag
            subprocess.check_call(
                ['git', 'push', 'origin', release_version],
                stdout=sys.stdout,
                stderr=sys.stderr,
            )

        if USE_PULL_REQUEST:
            _checkout_branch(verbose, default_branch)
            _delete_branch(verbose, branch_name)

        _verbose_output(verbose, 'Finished pushing changes to remote origin.')

        return PUSH_RESULT_PUSHED
    elif push == INSTRUCTION_ROLLBACK:
        _standard_output('Rolling back local release commit and tag...')

        if USE_PULL_REQUEST:
            _checkout_branch(verbose, default_branch)
            _delete_branch(verbose, branch_name)
        else:
            _delete_last_commit(verbose)

        if USE_TAG:
            _delete_local_tag(release_version, verbose)

        _verbose_output(verbose, 'Finished rolling back local release commit.')

        return PUSH_RESULT_ROLLBACK
    else:
        _standard_output('Not pushing changes to remote origin!')
        if USE_TAG:
            _print_output(
                COLOR_RED_BOLD,
                'Make sure you remember to explicitly push {branch} and the tag '
                '(or revert your local changes if you are trying to cancel)! '
                'You can push with the following commands:\n'
                '    git push origin {branch}:{branch}\n'
                '    git push origin "{tag}"\n',
                branch=branch_name,
                tag=release_version,
            )
        else:
            _print_output(
                COLOR_RED_BOLD,
                'Make sure you remember to explicitly push {branch} (or revert your local changes if you are '
                'trying to cancel)! You can push with the following command:\n'
                '    git push origin {branch}:{branch}\n',
                branch=branch_name,
            )

        return PUSH_RESULT_NO_ACTION


def _get_last_commit_hash(verbose):
    _verbose_output(verbose, 'Getting last commit hash...')

    commit_hash = subprocess.check_output(
        ['git', 'log', '-n', '1', '--pretty=format:%H'],
        stderr=sys.stderr,
    ).decode('utf8').strip()

    _verbose_output(verbose, 'Last commit hash is {}.', commit_hash)

    return commit_hash


def _get_commit_subject(commit_hash, verbose):
    _verbose_output(verbose, 'Getting commit message for hash {}...', commit_hash)

    message = subprocess.check_output(
        ['git', 'log', '-n', '1', '--pretty=format:%s', commit_hash],
        stderr=sys.stderr,
    ).decode('utf8').strip()

    _verbose_output(verbose, 'Commit message for hash {hash} is "{value}".', hash=commit_hash, value=message)

    return message


def _get_branch_name(verbose):
    _verbose_output(verbose, 'Determining current Git branch name.')

    branch_name = subprocess.check_output(
        ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
        stderr=sys.stderr,
    ).decode('utf8').strip()

    _verbose_output(verbose, 'Current Git branch name is {}.', branch_name)

    return branch_name


def _get_default_branch(verbose):
    _verbose_output(verbose, 'Determining current Git default branch.')

    remote_info = subprocess.check_output(
        ['git', 'remote', 'show', 'origin'],
        stderr=sys.stderr,
    ).decode('utf8').strip()
    for line in iter(remote_info.splitlines()):
        if HEAD_BRANCH in line:
            default_branch = line.strip().replace(HEAD_BRANCH, '')

    _verbose_output(verbose, 'Current Git default branch is {}.', default_branch)

    return default_branch


def _create_branch(verbose, branch_name):
    _verbose_output(verbose, 'Creating branch {branch}...', branch=branch_name)

    subprocess.check_call(
        ['git', 'checkout', '-b', branch_name],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    _verbose_output(verbose, 'Done creating branch {}.', branch_name)


def _create_local_tracking_branch(verbose, branch_name):
    """Create a local tracking branch of origin/<branch_name>.

    Returns True if successful, False otherwise.

    """
    _verbose_output(
        verbose,
        'Creating local branch {branch} set up to track remote branch {branch} from \'origin\'...',
        branch=branch_name
    )

    success = True

    try:
        subprocess.check_call(
            ['git', 'checkout', '--track', 'origin/{}'.format(branch_name)],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
        _verbose_output(verbose, 'Done creating branch {}.', branch_name)
    except subprocess.CalledProcessError:
        _verbose_output(verbose, 'Creating branch {} failed.', branch_name)
        success = False

    return success


def _checkout_branch(verbose, branch_name):
    _verbose_output(verbose, 'Checking out branch {branch}...', branch=branch_name)

    subprocess.check_call(
        ['git', 'checkout', branch_name],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    _verbose_output(verbose, 'Done checking out branch {}.', branch_name)


def _delete_branch(verbose, branch_name):
    _verbose_output(verbose, 'Deleting branch {branch}...', branch=branch_name)

    subprocess.check_call(
        ['git', 'branch', '-D', branch_name],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    _verbose_output(verbose, 'Done deleting branch {}.', branch_name)


def _is_branch_on_remote(verbose, branch_name):
    _verbose_output(verbose, 'Checking if branch {} exists on remote...', branch_name)

    result = subprocess.check_output(
        ['git', 'ls-remote', '--heads', 'origin', branch_name],
        stderr=sys.stderr,
    ).decode('utf8').strip()

    on_remote = branch_name in result

    _verbose_output(
        verbose,
        'Result of on-remote check for branch {branch_name} is {result}.',
        branch_name=branch_name,
        result=on_remote,
    )

    return on_remote


def _create_branch_from_tag(verbose, tag_name, branch_name):
    _verbose_output(verbose, 'Creating branch {branch} from tag {tag}...', branch=branch_name, tag=tag_name)

    subprocess.check_call(
        ['git', 'checkout', 'tags/{}'.format(tag_name), '-b', branch_name],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    _verbose_output(verbose, 'Done creating branch {}.', branch_name)


def _push_branch(verbose, branch_name):
    _verbose_output(verbose, 'Pushing branch {} to remote.', branch_name)

    subprocess.check_call(
        ['git', 'push', 'origin', '{0}:{0}'.format(branch_name)],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    _verbose_output(verbose, 'Done pushing branch {}.', branch_name)


def _fetch_tags(verbose):
    _verbose_output(verbose, 'Fetching all remote tags...')

    subprocess.check_call(
        ['git', 'fetch', '--tags'],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    _verbose_output(verbose, 'Done fetching tags.')


def _get_tag_list(verbose):
    _verbose_output(verbose, 'Parsing list of local tags...')

    result = subprocess.check_output(
        ['git', 'tag', '--list'],
        stderr=sys.stderr,
    ).decode('utf8').strip().split()

    _verbose_output(verbose, 'Result of tag list parsing is {}.', result)

    return result


def _does_tag_exist_locally(release_version, verbose):
    _verbose_output(verbose, 'Checking if tag {} exists locally...', release_version)

    result = subprocess.check_output(
        ['git', 'tag', '--list', release_version],
        stderr=sys.stderr,
    ).decode('utf8').strip()

    exists = release_version in result

    _verbose_output(verbose, 'Result of exists check for tag {tag} is {result}.', tag=release_version, result=exists)

    return exists


def _is_tag_on_remote(release_version, verbose):
    _verbose_output(verbose, 'Checking if tag {} was pushed to remote...', release_version)

    result = subprocess.check_output(
        ['git', 'ls-remote', '--tags', 'origin', release_version],
        stderr=sys.stderr,
    ).decode('utf8').strip()

    on_remote = release_version in result

    _verbose_output(
        verbose,
        'Result of on-remote check for tag {tag} is {result}.',
        tag=release_version,
        result=on_remote,
    )

    return on_remote


def _get_remote_branches_with_commit(commit_hash, verbose):
    _verbose_output(verbose, 'Checking if commit {} was pushed to any remote branches...', commit_hash)

    result = subprocess.check_output(
        ['git', 'branch', '-r', '--contains', commit_hash],
        stderr=sys.stderr,
    ).decode('utf8').strip()

    on_remote = []
    for line in result.splitlines():
        line = line.strip()
        if line.startswith('origin/') and not line.startswith('origin/HEAD'):
            on_remote.append(line)

    _verbose_output(
        verbose,
        'Result of on-remote check for commit {hash} is {remote}.',
        hash=commit_hash,
        remote=on_remote,
    )

    return on_remote


def _delete_local_tag(tag_name, verbose):
    _verbose_output(verbose, 'Deleting local tag {}...', tag_name)

    subprocess.check_call(
        ['git', 'tag', '-d', tag_name],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    _verbose_output(verbose, 'Finished deleting local tag {}.', tag_name)


def _delete_remote_tag(tag_name, verbose):
    _verbose_output(verbose, 'Deleting remote tag {}...', tag_name)

    subprocess.check_call(
        ['git', 'push', 'origin', ':refs/tags/{}'.format(tag_name)],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    _verbose_output(verbose, 'Finished deleting remote tag {}.', tag_name)


def _delete_last_commit(verbose):
    _verbose_output(verbose, 'Deleting last commit, assumed to be for version and changelog files...')

    extra_files = _get_extra_files_to_commit()

    subprocess.check_call(
        ['git', 'reset', '--soft', 'HEAD~1'],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    subprocess.check_call(
        ['git', 'reset', 'HEAD', VERSION_FILENAME, CHANGELOG_FILENAME] + extra_files,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    subprocess.check_call(
        ['git', 'checkout', '--', VERSION_FILENAME, CHANGELOG_FILENAME] + extra_files,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    _verbose_output(verbose, 'Finished deleting last commit.')


def _revert_remote_commit(release_version, commit_hash, branch_name, verbose):
    _verbose_output(verbose, 'Rolling back release commit on remote branch "{}"...', branch_name)

    subprocess.check_call(
        ['git', 'revert', '--no-edit', '--no-commit', commit_hash],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    release_message = 'REVERT: {}'.format(RELEASE_MESSAGE_TEMPLATE.format(release_version))
    subprocess.check_call(
        ['git', 'commit', '-m', release_message],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    _verbose_output(verbose, 'Pushing changes to remote branch "{}"...', branch_name)
    subprocess.check_call(
        ['git', 'push', 'origin', '{0}:{0}'.format(branch_name)],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    _verbose_output(verbose, 'Finished rolling back release commit.')


def _import_version_or_exit():
    if VERSION_FILE_IS_TXT:
        # if there is version.txt, use that
        with codecs.open(VERSION_FILENAME, 'rb', encoding='utf8') as version_txt:
            return version_txt.read()
    try:
        return __import__('{}.version'.format(MODULE_NAME), fromlist=[str('__version__')]).__version__
    except ImportError as e:
        import pprint
        _error_output_exit(
            'Could not import `__version__` from `{module}.version`. Error was "ImportError: {err}." Path is:\n{path}',
            module=MODULE_NAME,
            err=e.args[0],
            path=pprint.pformat(sys.path),
        )
    except AttributeError as e:
        _error_output_exit('Could not retrieve `__version__` from imported module. Error was "{}."', e.args[0])


def _ensure_files_exist(exit_on_failure):
    failure = False

    if not _case_sensitive_regular_file_exists(VERSION_FILENAME):
        _error_output('Version file {} was not found!', RE_FILE_EXTENSION.sub('.(py|txt)', VERSION_FILENAME))
        failure = True

    if not _case_sensitive_regular_file_exists(CHANGELOG_FILENAME):
        _error_output('Changelog file {} was not found!', RE_FILE_EXTENSION.sub('.(txt|md|rst)', CHANGELOG_FILENAME))
        failure = True

    if failure:
        _error_output(
            'This project is not correctly configured to use `invoke release`! (File names are case sensitive!)'
        )
        if exit_on_failure:
            sys.exit(1)


def _ensure_configured(command):
    if not PARAMETERS_CONFIGURED:
        _error_output_exit('Cannot `invoke {}` before calling `configure_release_parameters`.', command)

    _ensure_files_exist(True)


def _set_map(map_function, iterable):
    ret = set()
    for i in iterable:
        r = map_function(i)
        if r:
            if getattr(r, '__iter__', None):
                ret.update(r)
            else:
                ret.add(r)
    return ret


def _get_extra_files_to_commit():
    return list(_set_map(lambda plugin: plugin.get_extra_files_to_commit(ROOT_DIRECTORY), RELEASE_PLUGINS))


def _get_version_errors():
    return _set_map(lambda plugin: plugin.version_error_check(ROOT_DIRECTORY), RELEASE_PLUGINS)


def _pre_release(old_version):
    for plugin in RELEASE_PLUGINS:
        plugin.pre_release(ROOT_DIRECTORY, old_version)


def _pre_commit(old_version, new_version):
    for plugin in RELEASE_PLUGINS:
        plugin.pre_commit(ROOT_DIRECTORY, old_version, new_version)


def _pre_push(old_version, new_version):
    for plugin in RELEASE_PLUGINS:
        plugin.pre_push(ROOT_DIRECTORY, old_version, new_version)


def _post_release(old_version, new_version, pushed):
    for plugin in RELEASE_PLUGINS:
        plugin.post_release(ROOT_DIRECTORY, old_version, new_version, pushed)


def _pre_rollback(current_version):
    for plugin in RELEASE_PLUGINS:
        plugin.pre_rollback(ROOT_DIRECTORY, current_version)


def _post_rollback(current_version, rollback_to_version):
    for plugin in RELEASE_PLUGINS:
        plugin.post_rollback(ROOT_DIRECTORY, current_version, rollback_to_version)


def _get_version_element_to_bump_if_any(changelog_message):
    untagged_commit_present = False
    patch_commit_present = False
    minor_commit_present = False

    for line in changelog_message:
        if line.startswith(MAJOR_VERSION_PREFIX):
            return MAJOR_VERSION_PREFIX
        if line.startswith(MINOR_VERSION_PREFIX):
            minor_commit_present = True
        elif line.startswith(PATCH_VERSION_PREFIX):
            patch_commit_present = True
        else:
            untagged_commit_present = True

    version = PATCH_VERSION_PREFIX if patch_commit_present else None
    version = MINOR_VERSION_PREFIX if minor_commit_present else version

    return version if not untagged_commit_present else None


def _bump_version_according_to_tag(current_version, version_element_to_bump):

    if version_element_to_bump == PATCH_VERSION_PREFIX:
        return (current_version[0], current_version[1], current_version[2] + 1)
    if version_element_to_bump == MINOR_VERSION_PREFIX:
        return (current_version[0], current_version[1] + 1, 0)
    if version_element_to_bump == MAJOR_VERSION_PREFIX:
        if current_version[0] == 0:
            # For MAJOR version zero, recommend to bump a MINOR version instead since going for version 1.x.x should be
            # a conscious decision and suggestion wouldn't be necessary.
            return (current_version[0], current_version[1] + 1, 0)
        else:
            return (current_version[0] + 1, 0, 0)

    return ''


def _suggest_version(current_version, version_element_to_bump):
    current_version = tuple(
        map(
            int,
            current_version.split('-')[0].split('+')[0].split('.')[:3]
        )
    )

    return '.'.join(
        map(
            str,
            _bump_version_according_to_tag(current_version, version_element_to_bump)
        )
    ) or None


def configure_release_parameters(module_name, display_name, python_directory=None, plugins=None,
                                 use_pull_request=False, use_tag=True):
    global MODULE_NAME, MODULE_DISPLAY_NAME, RELEASE_MESSAGE_TEMPLATE, VERSION_FILENAME, CHANGELOG_FILENAME
    global ROOT_DIRECTORY, RELEASE_PLUGINS, PARAMETERS_CONFIGURED, VERSION_FILE_IS_TXT
    global USE_PULL_REQUEST, USE_TAG

    if PARAMETERS_CONFIGURED:
        _error_output_exit('Cannot call configure_release_parameters more than once.')

    if not module_name:
        _error_output_exit('module_name is required')
    if not display_name:
        _error_output_exit('display_name is required')

    MODULE_NAME = module_name
    MODULE_DISPLAY_NAME = display_name
    RELEASE_MESSAGE_TEMPLATE = 'Released {} version {{}}'.format(MODULE_DISPLAY_NAME)

    ROOT_DIRECTORY = os.path.normpath(_get_root_directory())

    if python_directory:
        import_directory = os.path.normpath(os.path.join(ROOT_DIRECTORY, python_directory))
        version_file_prefix = os.path.join(
            ROOT_DIRECTORY,
            '{python}/{module}/version'.format(python=python_directory, module=MODULE_NAME)
        )
    else:
        import_directory = ROOT_DIRECTORY
        version_file_prefix = os.path.join(
            ROOT_DIRECTORY,
            '{module}/version'.format(module=MODULE_NAME)
        )

    changelog_file_prefix = os.path.join(ROOT_DIRECTORY, 'CHANGELOG')

    if _case_sensitive_regular_file_exists('{}.txt'.format(version_file_prefix)):
        VERSION_FILE_IS_TXT = True
        VERSION_FILENAME = '{}.txt'.format(version_file_prefix)
    else:
        VERSION_FILE_IS_TXT = False
        VERSION_FILENAME = '{}.py'.format(version_file_prefix)

    CHANGELOG_FILENAME = '{}.txt'.format(changelog_file_prefix)
    if not _case_sensitive_regular_file_exists('{}.txt'.format(changelog_file_prefix)):
        if _case_sensitive_regular_file_exists('{}.md'.format(changelog_file_prefix)):
            CHANGELOG_FILENAME = '{}.md'.format(changelog_file_prefix)
        elif _case_sensitive_regular_file_exists('{}.rst'.format(changelog_file_prefix)):
            CHANGELOG_FILENAME = '{}.rst'.format(changelog_file_prefix)

    if import_directory not in sys.path:
        sys.path.insert(0, import_directory)

    if getattr(plugins, '__iter__', None):
        RELEASE_PLUGINS = plugins

    USE_PULL_REQUEST = use_pull_request
    USE_TAG = use_tag

    PARAMETERS_CONFIGURED = True


@task
def version(_):
    """
    Prints the "Invoke Release" version and the version of the current project.
    """
    if not PARAMETERS_CONFIGURED:
        _error_output_exit('Cannot `invoke version` before calling `configure_release_parameters`.')

    _standard_output('Python {}', sys.version.split('\n')[0].strip())

    from invoke import __version__ as invoke_version
    _standard_output('Invoke {}', invoke_version)

    from invoke_release.version import __version__
    _standard_output('Invoke Release {}', __version__)

    _ensure_files_exist(False)

    for error in _get_version_errors():
        _error_output(error)

    _standard_output('{module} {version}', module=MODULE_DISPLAY_NAME, version=_import_version_or_exit())
    _standard_output('Detected Git branch: {}', _get_branch_name(False))
    _standard_output('Detected version file: {}', VERSION_FILENAME)
    _standard_output('Detected changelog file: {}', CHANGELOG_FILENAME)


@task(help={
    'verbose': 'Specify this switch to include verbose debug information in the command output.',
    'no-stash': 'Specify this switch to disable stashing any uncommitted changes (by default, changes that have '
                'not been committed are stashed before the branch is created).',
})
def branch(_, verbose=False, no_stash=False):
    """
    Creates a branch from a release tag for creating a new patch or minor release from that branch.
    """
    _ensure_configured('release')

    from invoke_release.version import __version__
    _standard_output('Invoke Release {}', __version__)

    _setup_task(no_stash, verbose)
    try:
        _fetch_tags(verbose)

        tags = _get_tag_list(verbose)

        branch_version = _prompt('Enter a version tag from which to create a new branch (or "exit"):').lower()
        if not branch_version or branch_version == INSTRUCTION_EXIT:
            raise ReleaseExit()

        if branch_version not in tags:
            raise ReleaseFailure('Version number {} not in the list of available tags.'.format(branch_version))

        _v = LooseVersion(branch_version)
        minor_branch = '.'.join(list(map(six.text_type, _v.version[:2])) + ['x'])
        major_branch = '.'.join(list(map(six.text_type, _v.version[:1])) + ['x', 'x'])

        proceed_instruction = _prompt(
            'Using tag {tag}, would you like to create a minor branch for patch versions (branch {minor}, '
            'recommended), or a major branch for minor versions (branch {major})? (MINOR/major/exit):',
            tag=branch_version,
            minor=minor_branch,
            major=major_branch,
        )

        if proceed_instruction == INSTRUCTION_EXIT:
            raise ReleaseExit()

        new_branch = major_branch if proceed_instruction == INSTRUCTION_MAJOR else minor_branch

        if USE_PULL_REQUEST:
            if _is_branch_on_remote(verbose, new_branch):
                _standard_output(
                    'Branch {branch} exists on remote. Creating local tracking branch.',
                    branch=new_branch,
                )
                created = _create_local_tracking_branch(verbose, new_branch)
                if not created:
                    raise ReleaseFailure(
                        'Could not create local tracking branch {branch}.\n'
                        'Does a local branch named {branch} already exists?\n'
                        'Delete or rename your local branch {branch} and try again.'.format(branch=new_branch),
                    )
            else:
                _standard_output(
                    'Branch {branch} does not exist on remote.\n'
                    'Creating branch, and pushing to remote.',
                    branch=new_branch,
                )
                _create_branch_from_tag(verbose, branch_version, new_branch)
                _push_branch(verbose, new_branch)

            cherry_pick_branch_suffix = _prompt(
                'Now we will create the branch where you will apply your fixes. We\n'
                'need a name to uniquely identify your feature branch. I suggest using\n'
                'the JIRA ticket id, e.g. EB-120106, of the issue you are working on:'
            )
            if not cherry_pick_branch_suffix:
                raise ReleaseFailure('You must enter a name to identify your feature branch.')
            _create_branch(
                verbose,
                'cherry-pick-{hotfix_branch_name}-{suffix}'.format(
                    hotfix_branch_name=new_branch,
                    suffix=cherry_pick_branch_suffix,
                )
            )
        else:
            _create_branch_from_tag(verbose, branch_version, new_branch)

            push_instruction = _prompt(
                'Branch {} created. Would you like to go ahead and push it to remote? (y/N):',
                new_branch,
            ).lower()
            if push_instruction and push_instruction == INSTRUCTION_YES:
                _push_branch(verbose, new_branch)

        _standard_output('Branch process is complete.')
    except ReleaseFailure as e:
        _error_output(e.args[0])
    except subprocess.CalledProcessError as e:
        _error_output(
            'Command {command} failed with error code {error_code}. Command output:\n{output}',
            command=e.cmd,
            error_code=e.returncode,
            output=e.output.decode('utf8'),
        )
    except (ReleaseExit, KeyboardInterrupt):
        _standard_output('Canceling branch!')
    finally:
        _cleanup_task(verbose)


@task(help={
    'verbose': 'Specify this switch to include verbose debug information in the command output.',
    'no-stash': 'Specify this switch to disable stashing any uncommitted changes (by default, changes that have '
                'not been committed are stashed before the release is executed).',
})
def release(_, verbose=False, no_stash=False):
    """
    Increases the version, adds a changelog message, and tags a new version of this project.
    """
    _ensure_configured('release')

    from invoke_release.version import __version__
    _standard_output('Invoke Release {}', __version__)

    __version__ = _import_version_or_exit()

    version_regular_expression = RE_VERSION

    default_branch = _get_default_branch(verbose)

    branch_name = _get_branch_name(verbose)
    if branch_name != default_branch:
        if not RE_VERSION_BRANCH_MAJOR.match(branch_name) and not RE_VERSION_BRANCH_MINOR.match(branch_name):
            _error_output(
                'You are currently on branch "{}" instead of "{}". You should only release from default or version '
                'branches, and this does not appear to be a version branch (must match \\d+\\.x\\.x or \\d+.\\d+\\.x). '
                '\nCanceling release!',
                branch_name,
                default_branch,
            )
            return

        instruction = _prompt(
            'You are currently on branch "{branch}" instead of "{db}". Are you sure you want to continue releasing '
            'from "{branch}?" You should only do this from version branches, and only when higher versions have been '
            'released from the parent branch. (y/N):',
            branch=branch_name,
            db=default_branch,
        ).lower()

        if instruction != INSTRUCTION_YES:
            _standard_output('Canceling release!')
            return

        version_regular_expression = re.compile(
            r'^' + branch_name.replace('.x', r'.\d+').replace('.', r'\.') + r'([a-zA-Z\d.-]*[a-zA-Z\d]+)?$',
        )

    try:
        _pre_release(__version__)
    except ReleaseFailure as e:
        _error_output_exit(e.args[0])

    _setup_task(no_stash, verbose)
    try:
        _standard_output('Releasing {}...', MODULE_DISPLAY_NAME)
        _standard_output('Current version: {}', __version__)

        cl_header, cl_message, cl_footer = _prompt_for_changelog(verbose)
        suggested_version = _suggest_version(__version__, _get_version_element_to_bump_if_any(cl_message))

        instruction = None
        if suggested_version:
            instruction = _prompt(
               'According to the changelog message the next version should be `{}`. '
               'Do you want to proceed with the suggested version? (Y/n)'.format(suggested_version)
            ).lower() or INSTRUCTION_YES

        if instruction == INSTRUCTION_YES:
            release_version = suggested_version
        else:
            release_version = _prompt('Enter a new version (or "exit"):').lower()

        if not release_version or release_version == INSTRUCTION_EXIT:
            raise ReleaseExit()

        if not version_regular_expression.match(release_version):
            raise ReleaseFailure(
                'Invalid version specified: {version}. Must match "{regex}".'.format(
                    version=release_version,
                    regex=version_regular_expression.pattern,
                ),
            )

        # Deconstruct and reconstruct the version, to make sure it is consistent everywhere
        version_info = release_version.split('.', 2)
        end_parts = list(filter(None, RE_SPLIT_AFTER_DIGITS.split(version_info[2], 1)))
        version_separator = '-'
        if len(end_parts) > 1:
            version_info[0] = int(version_info[0])
            version_info[1] = int(version_info[1])
            version_info[2] = int(end_parts[0])
            version_info.append(end_parts[1].strip(' .-_+'))
            if end_parts[1][0] in ('-', '+', '.'):
                version_separator = end_parts[1][0]
        else:
            version_info = list(map(int, version_info))
        release_version = version_separator.join(
            filter(None, ['.'.join(map(six.text_type, version_info[:3])), (version_info[3:] or [None])[0]])
        )  # This must match the code in VERSION_VARIABLE_TEMPLATE at the top of this file

        if not (parse_version(release_version) > parse_version(__version__)):
            raise ReleaseFailure(
                'New version number {new_version} is not greater than current version {old_version}.'.format(
                    new_version=release_version,
                    old_version=__version__,
                ),
            )

        if _does_tag_exist_locally(release_version, verbose) or _is_tag_on_remote(release_version, verbose):
            raise ReleaseFailure(
                'Tag {} already exists locally or remotely (or both). Cannot create version.'.format(release_version),
            )

        instruction = _prompt('The release has not yet been committed. Are you ready to commit it? (Y/n):').lower()
        if instruction and instruction != INSTRUCTION_YES:
            raise ReleaseExit()

        _standard_output('Releasing {module} version: {version}', module=MODULE_DISPLAY_NAME, version=release_version)

        _write_to_version_file(release_version, version_info, version_separator, verbose)
        _write_to_changelog_file(release_version, cl_header, cl_message, cl_footer, verbose)

        _pre_commit(__version__, release_version)

        if USE_PULL_REQUEST:
            current_branch_name = _get_branch_name(verbose)
            branch_name = 'invoke-release-{}-{}'.format(current_branch_name, release_version)
            _create_branch(verbose, branch_name)
        _commit_release_changes(release_version, cl_message, verbose)

        _pre_push(__version__, release_version)

        if USE_TAG:
            _tag_branch(release_version, cl_message, verbose)
        pushed_or_rolled_back = _push_release_changes(release_version, branch_name, default_branch, verbose)

        uses_prs_and_branch_is_pushed = USE_PULL_REQUEST and pushed_or_rolled_back == PUSH_RESULT_PUSHED

        if uses_prs_and_branch_is_pushed:
            if current_branch_name != default_branch:
                _checkout_branch(verbose, current_branch_name)
            try:
                github_token = os.environ['GITHUB_TOKEN']
            except KeyError:
                pr_opened = False
                _standard_output('Then environment variable `GITHUB_TOKEN` is not set. Will not open GitHub PR.')
            else:
                pr_opened = open_pull_request(
                    branch_name,
                    current_branch_name,
                    MODULE_DISPLAY_NAME,
                    release_version,
                    github_token,
                )
        _post_release(__version__, release_version, pushed_or_rolled_back)

        if uses_prs_and_branch_is_pushed:
            if pr_opened:
                _standard_output('GitHub PR created successfully. URL: {}'.format(pr_opened))
            else:
                _standard_output(
                    "You're almost done! The release process will be complete when you create "
                    "a pull request and it is merged."
                )
        else:
            _standard_output('Release process is complete.')
    except ReleaseFailure as e:
        _error_output(e.args[0])
    except subprocess.CalledProcessError as e:
        _error_output(
            'Command {command} failed with error code {error_code}. Command output:\n{output}',
            command=e.cmd,
            error_code=e.returncode,
            output=e.output.decode('utf8'),
        )
    except (ReleaseExit, KeyboardInterrupt):
        _standard_output('Canceling release!')
    finally:
        _cleanup_task(verbose)


@task(help={
    'verbose': 'Specify this switch to include verbose debug information in the command output.',
    'no-stash': 'Specify this switch to disable stashing any uncommitted changes (by default, changes that have '
                'not been committed are stashed before the release is rolled back).',
})
def rollback_release(_, verbose=False, no_stash=False):
    """
    If the last commit is the commit for the current release, this command deletes the release tag and deletes
    (if local only) or reverts (if remote) the last commit. This is fairly safe to do if the release has not
    yet been pushed to remote, but extreme caution should be exercised when invoking this after the release has
    been pushed to remote.
    """
    _ensure_configured('rollback-release')

    from invoke_release.version import __version__
    _standard_output('Invoke Release {}', __version__)

    __version__ = _import_version_or_exit()

    default_branch = _get_default_branch(verbose)

    branch_name = _get_branch_name(verbose)
    if branch_name != default_branch:
        instruction = _prompt(
            'You are currently on branch "{branch}" instead of "{db}". Rolling back on a branch other than {db} '
            'can be dangerous.\nAre you sure you want to continue rolling back on "{branch}?" (y/N):',
            branch=branch_name,
            db=default_branch,
        ).lower()

        if instruction != INSTRUCTION_YES:
            _standard_output('Canceling release rollback!')
            return

    try:
        _pre_rollback(__version__)
    except ReleaseFailure as e:
        _error_output_exit(e.args[0])

    _setup_task(no_stash, verbose)
    try:
        commit_hash = _get_last_commit_hash(verbose)
        message = _get_commit_subject(commit_hash, verbose)
        if message.rstrip('.') != RELEASE_MESSAGE_TEMPLATE.format(__version__):
            raise ReleaseFailure('Cannot roll back because last commit is not the release commit.')

        on_remote = _get_remote_branches_with_commit(commit_hash, verbose)
        is_on_remote = False
        if len(on_remote) == 1:
            is_on_remote = on_remote[0] == 'origin/{}'.format(branch_name)
        elif len(on_remote) > 1:
            raise ReleaseFailure(
                'Cannot roll back because release commit is on multiple remote branches: {}'.format(on_remote),
            )

        _standard_output('Release tag {} will be deleted locally and remotely (if applicable).', __version__)
        delete = _prompt('Do you want to proceed with deleting this tag? (y/N):').lower()
        if delete == INSTRUCTION_YES:
            if _does_tag_exist_locally(__version__, verbose):
                _delete_local_tag(__version__, verbose)

            if _is_tag_on_remote(__version__, verbose):
                _delete_remote_tag(__version__, verbose)

            _standard_output('The release tag has been deleted from local and remote (if applicable).')

            if is_on_remote:
                _standard_output('The release commit is present on the remote origin.')
                prompt = 'Do you want to revert the commit and immediately push it to the remote origin? (y/N):'
            else:
                _standard_output('The release commit is only present locally, not on the remote origin.')
                prompt = 'Are you ready to delete the commit like it never happened? (y/N):'

            revert = _prompt(prompt).lower()
            if revert == INSTRUCTION_YES:
                if is_on_remote:
                    _revert_remote_commit(__version__, commit_hash, branch_name, verbose)
                else:
                    _delete_last_commit(verbose)
            else:
                _standard_output('The commit was not reverted.')

            version_module = __import__('{}.version'.format(MODULE_NAME), fromlist=[str('__version__')])
            # noinspection PyCompatibility
            moves.reload_module(version_module)
            _post_rollback(__version__, version_module.__version__)

            _standard_output('Release rollback is complete.')
        else:
            raise ReleaseExit()
    except ReleaseFailure as e:
        _error_output(e.args[0])
    except subprocess.CalledProcessError as e:
        _error_output(
            'Command {command} failed with error code {error_code}. Command output:\n{output}',
            command=e.cmd,
            error_code=e.returncode,
            output=e.output.decode('utf8'),
        )
    except (ReleaseExit, KeyboardInterrupt):
        _standard_output('Canceling release rollback!')
    finally:
        _cleanup_task(verbose)


@task
def wheel(_):
    """
    Builds a wheel archive of all files in the Git root directory.

    Future possible changes: Upload to the wheel server.
    """
    build_instruction = _prompt('Build a wheel archive of {}? (Y/n):'.format(MODULE_DISPLAY_NAME)).lower()

    if build_instruction == INSTRUCTION_NO:
        _standard_output('Aborting!')
        return

    base_dir = _get_root_directory()
    archive_name = archive.make_wheelfile_inner(MODULE_NAME, _get_root_directory())
    _standard_output('Successfully built the wheel archive {archive_name} at {base_dir}'.format(
        archive_name=archive_name,
        base_dir=base_dir
    ))


def open_pull_request(branch_name, current_branch_name, display_name, version_to_release, github_token):
    remote = six.text_type(
        subprocess.check_output(
            ['git', 'remote', 'get-url', 'origin'],
            stderr=subprocess.STDOUT,
        )
    )
    repo = (remote.split(':')[1].split('.')[0])
    url = 'https://api.github.com/repos/{}/pulls'.format(repo)

    values = {
        'title': 'Released {} version {}'.format(display_name, version_to_release),
        'base': current_branch_name,
        'head': branch_name,
    }

    body = json.dumps(values).encode('utf-8')
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'token {}'.format(github_token),
        'Accept': 'application/vnd.github.v3+json',
        'Content-Length': len(body),
    }

    try:
        req = urllib.request.Request(url, body, headers)
        with closing(urllib.request.urlopen(req)) as f:
            # GitHub will always answer with 201 if the PR was `CREATED`.
            return f.getcode() == 201 and json.loads(f.read().decode('utf-8'))['html_url']
    except Exception:
        _error_output('Could not open Github PR')
