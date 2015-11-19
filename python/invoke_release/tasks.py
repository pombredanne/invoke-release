import datetime
import os
import re
import subprocess
import sys
import tempfile
from distutils.version import LooseVersion

from invoke import task

VERSION_RE = r'^\d+\.\d+\.\d+$'
VERSION_VARIABLE_RE = '^__version__ = \d+\.\d+\.\d+$'

VERSION_INFO_VARIABLE_TEMPLATE = '__version_info__ = {}'
VERSION_VARIABLE_TEMPLATE = "__version__ = '.'.join(map(str, __version_info__))"
RELEASE_MESSAGE_TEMPLATE = 'Released [unknown] version {}.'

MODULE_NAME = 'unknown'
MODULE_DISPLAY_NAME = '[unknown]'

RELEASE_PLUGINS = []

ROOT_DIRECTORY = ''
VERSION_FILENAME = 'python/unknown/version.py'
CHANGELOG_FILENAME = 'CHANGELOG.txt'
CHANGELOG_RC_FILENAME = '.gitchangelog.rc'
CHANGELOG_COMMENT_FIRST_CHAR = '#'

PARAMETERS_CONFIGURED = False

__POST_APPLY = False

__all__ = [
    'configure_release_parameters',
    'version',
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

BRANCH_MASTER = 'master'

INSTRUCTION_NO = 'n'
INSTRUCTION_YES = 'y'
INSTRUCTION_NEW = 'new'
INSTRUCTION_EDIT = 'edit'
INSTRUCTION_ACCEPT = 'accept'
INSTRUCTION_DELETE = 'delete'
INSTRUCTION_EXIT = 'exit'
INSTRUCTION_ROLLBACK = 'rollback'


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
        print message.format(*args, **kwargs)


def _standard_output(message, *args, **kwargs):
    _print_output(COLOR_GREEN_BOLD, message + "\n", *args, **kwargs)


def _prompt(message, *args, **kwargs):
    _print_output(COLOR_WHITE, message + ' ', *args, **kwargs)
    response = raw_input()
    if response:
        return response.strip()
    return ''


def _error_output(message, *args, **kwargs):
    _print_output(COLOR_RED_BOLD, ''.join(('ERROR: ', message, "\n")), *args, **kwargs)


def _error_output_exit(message, *args, **kwargs):
    _error_output(message, *args, **kwargs)
    sys.exit(1)


def _verbose_output(verbose, message, *args, **kwargs):
    if verbose:
        _print_output(COLOR_GRAY_LIGHT, ''.join(('DEBUG: ', message, "\n")), *args, **kwargs)


def _get_root_directory():
    root_directory = subprocess.check_output(
        ['git', 'rev-parse', '--show-toplevel'],
        stderr=sys.stderr,
    ).strip()

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
        )
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


def _write_to_version_file(release_version, verbose):
    _verbose_output(verbose, 'Writing version to {}...', VERSION_FILENAME)

    if not os.path.exists(VERSION_FILENAME):
        raise ReleaseFailure(
            'Failed to find version file: {}'.format(VERSION_FILENAME),
        )

    with open(VERSION_FILENAME, 'rb') as version_read:
        output = []
        version_info_written = False
        version_info = VERSION_INFO_VARIABLE_TEMPLATE.format(tuple([int(v) for v in release_version.split('.')]))
        for line in version_read:
            if line.startswith('__version_info__'):
                output.append(version_info)
                version_info_written = True
            elif line.startswith('__version__'):
                if not version_info_written:
                    output.append(version_info)
                output.append(VERSION_VARIABLE_TEMPLATE)
            else:
                output.append(line.rstrip())

    with open(VERSION_FILENAME, 'wb') as version_write:
        for line in output:
            version_write.write(line)
            version_write.write('\n')

    _verbose_output(verbose, 'Finished writing to {}.version.', MODULE_NAME)


def _gather_commit_messages(verbose):
    _verbose_output(verbose, 'Gathering commit messages since last release commit.')

    command = [
        'git',
        'log',
        '-1',
        '--format=%H',
        '--grep={}'.format(RELEASE_MESSAGE_TEMPLATE.replace(' {}.', '').replace('"', '\\"'))
    ]
    _verbose_output(verbose, 'Running command: "{}"', '" "'.join(command))
    commit_hash = subprocess.check_output(command, stderr=sys.stderr)
    commit_hash = commit_hash.strip()

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
    output = subprocess.check_output(command, stderr=sys.stderr)

    messages = []
    for message in output.splitlines():
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
    with open(CHANGELOG_FILENAME, 'rb') as changelog_read:
        previous_line = ''
        passed_header = passed_changelog = False
        for line_number, line in enumerate(changelog_read):
            if not passed_header:
                changelog_header.append(line)
                if re.search('^=+$', line):
                    passed_header = True
                continue

            if not passed_changelog and re.search('^-+$', line):
                changelog_footer.append(previous_line)
                passed_changelog = True

            if passed_changelog:
                changelog_footer.append(line)
            else:
                if previous_line.strip():
                    built_up_changelog.append(previous_line)

                previous_line = line

    if len(built_up_changelog) > 0:
        _verbose_output(verbose, 'Read {} lines of built-up changelog text.', len(built_up_changelog))
        _standard_output('There are existing changelog details for this release. You can "edit" the changes, '
                         '"accept" them as-is, delete them and create a "new" changelog message, or "delete" '
                         'them and enter no changelog.')
        instruction = _prompt('How would you like to proceed? (EDIT/new/accept/delete/exit)').lower()

        if instruction in (INSTRUCTION_NEW, INSTRUCTION_DELETE):
            built_up_changelog = []
        if instruction == INSTRUCTION_ACCEPT:
            changelog_message = built_up_changelog
        if not instruction or instruction in (INSTRUCTION_EDIT, INSTRUCTION_NEW):
            instruction = INSTRUCTION_YES
    else:
        _verbose_output(verbose, 'No existing lines of built-up changelog text were read.')
        instruction = _prompt(
            'Would you like to enter changelog details for this release? (Y/n/exit)',
        ).lower() or INSTRUCTION_YES

    if instruction == INSTRUCTION_EXIT:
        raise ReleaseExit()

    if instruction == INSTRUCTION_YES:
        gather = _prompt(
            'Would you like to{also} gather commit messages from recent commits and add them to the '
            'changelog? ({y_n}/exit)',
            **({'also': ' also', 'y_n': 'y/N'} if built_up_changelog else {'also': '', 'y_n': 'Y/n'})
        ).lower() or (INSTRUCTION_NO if built_up_changelog else INSTRUCTION_YES)

        commit_messages = []
        if gather == INSTRUCTION_YES:
            commit_messages = _gather_commit_messages(verbose)
        elif gather == INSTRUCTION_EXIT:
            raise ReleaseExit()

        with tempfile.NamedTemporaryFile() as tf:
            _verbose_output(verbose, 'Opened temporary file {} for editing changelog.', tf.name)
            if commit_messages:
                tf.write('\n'.join(commit_messages))
                tf.write('\n')
            if built_up_changelog:
                tf.writelines(built_up_changelog)
            tf.writelines([
                '\n',
                '# Enter your changelog message above this comment, then save and close editor when finished.\n',
                '# Any existing contents were pulled from changes to CHANGELOG.txt since the last release.\n',
                '# Leave it blank (delete all existing contents) to release with no changelog details.\n',
                '# All lines starting with "#" are comments and ignored.',
                '# As a best practice, if you are entering multiple items as a list, prefix each item with a "-".'
            ])
            tf.flush()
            _verbose_output(verbose, 'Wrote existing changelog contents and instructions to temporary file.')

            editor = os.environ.get('EDITOR', 'vi')
            _verbose_output(verbose, 'Opening editor {} to edit changelog.', editor)
            subprocess.check_call(
                [editor, tf.name],
                stdout=sys.stdout,
                stderr=sys.stderr,
            )
            _verbose_output(verbose, 'User has closed editor')

            with open(tf.name, 'rb') as read:
                for line in read:
                    if line and line.strip() and not line.startswith(CHANGELOG_COMMENT_FIRST_CHAR):
                        changelog_message.append(line)
            _verbose_output(verbose, 'Changelog message read from temporary file:\n{}', changelog_message)

    return changelog_header, changelog_message, changelog_footer


def _write_to_changelog_file(release_version, changelog_header, changelog_message, changelog_footer, verbose):
    _verbose_output(verbose, 'Writing changelog contents to {}.', CHANGELOG_FILENAME)
    with open(CHANGELOG_FILENAME, 'wb') as changelog_write:
        header_line = '{version} ({date})'.format(
            version=release_version,
            date=datetime.datetime.now().strftime('%Y-%m-%d'),
        )

        changelog_write.writelines(changelog_header)
        changelog_write.write('\n')
        if changelog_message:
            changelog_write.writelines([
                header_line, '\n',
                '-' * len(header_line), '\n',
            ])
            changelog_write.writelines(changelog_message)
            changelog_write.write('\n')
        changelog_write.writelines(changelog_footer)

    _verbose_output(verbose, 'Finished writing to changelog.')


def _tag_branch(release_version, verbose, overwrite=False):
    _verbose_output(verbose, 'Tagging branch...')

    release_message = RELEASE_MESSAGE_TEMPLATE.format(release_version)
    cmd = ['git', 'tag', '-a', release_version, '-m', release_message]
    if overwrite:
        cmd.append('-f')

    try:
        result = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        result = '`git` command exit code {code} - {output}'.format(code=e.returncode, output=e.output)

    if result:
        raise ReleaseFailure('Failed tagging branch: {}'.format(result))

    _verbose_output(verbose, 'Finished tagging branch.')


def _commit_release_changes(release_version, verbose):
    _verbose_output(verbose, 'Committing release changes...')

    files_to_commit = [VERSION_FILENAME, CHANGELOG_FILENAME] + _get_extra_files_to_commit()
    _verbose_output(verbose, 'Staging changes for files {}.'.format(files_to_commit))

    try:
        result = subprocess.check_output(
            ['git', 'add'] + files_to_commit,
            stderr=subprocess.STDOUT,
        )
    except subprocess.CalledProcessError as e:
        result = '`git` command exit code {code} - {output}'.format(code=e.returncode, output=e.output)

    if result:
        raise ReleaseFailure('Failed staging release files for commit: {}'.format(result))

    release_message = RELEASE_MESSAGE_TEMPLATE.format(release_version)
    subprocess.check_call(
        ['git', 'commit', '-m', release_message],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    _verbose_output(verbose, 'Finished releasing changes.')


def _push_release_changes(release_version, branch_name, verbose):
    try:
        push = _prompt(
            'Push release changes and tag to remote origin (branch "{}")? (y/N/rollback)',
            branch_name,
        ).lower()
    except KeyboardInterrupt:
        push = INSTRUCTION_ROLLBACK

    if push == INSTRUCTION_YES:
        _verbose_output(verbose, 'Pushing changes to remote origin...')

        subprocess.check_call(
            ['git', 'push', 'origin', '{0}:{0}'.format(branch_name)],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
        # push the release tag
        subprocess.check_call(
            ['git', 'push', 'origin', release_version],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )

        _verbose_output(verbose, 'Finished pushing changes to remote origin.')

        return PUSH_RESULT_PUSHED
    elif push == INSTRUCTION_ROLLBACK:
        _standard_output('Rolling back local release commit and tag...')

        _delete_last_commit(verbose)
        _delete_local_tag(release_version, verbose)

        _verbose_output(verbose, 'Finished rolling back local release commit.')

        return PUSH_RESULT_ROLLBACK
    else:
        _standard_output('Not pushing changes to remote origin!')
        _standard_output('Make sure you remember to explicitly push the tag, or '
                         'revert your local changes if you are trying to cancel!')

        return PUSH_RESULT_NO_ACTION


def _get_last_commit_hash(verbose):
    _verbose_output(verbose, 'Getting last commit hash...')

    commit_hash = subprocess.check_output(
        ['git', 'log', '-n', '1', '--pretty=format:%H'],
        stderr=sys.stderr,
    ).strip()

    _verbose_output(verbose, 'Last commit hash is {}.', commit_hash)

    return commit_hash


def _get_commit_subject(commit_hash, verbose):
    _verbose_output(verbose, 'Getting commit message for hash {}...', commit_hash)

    message = subprocess.check_output(
        ['git', 'log', '-n', '1', '--pretty=format:%B', commit_hash],
        stderr=sys.stderr,
    ).strip()

    _verbose_output(verbose, 'Commit message for hash {hash} is "{message}".', hash=commit_hash, message=message)

    return message


def _get_branch_name(verbose):
    _verbose_output(verbose, 'Determining current Git branch name.')

    branch_name = subprocess.check_output(
        ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
        stderr=sys.stderr,
    ).strip()

    _verbose_output(verbose, 'Current Git branch name is {}.', branch_name)

    return branch_name


def _does_tag_exist_locally(release_version, verbose):
    _verbose_output(verbose, 'Checking if tag {} exists locally...', release_version)

    result = subprocess.check_output(
        ['git', 'tag', '--list', release_version],
        stderr=sys.stderr,
    ).strip()

    exists = release_version in result

    _verbose_output(verbose, 'Result of exists check for tag {tag} is {result}.', tag=release_version, result=exists)

    return exists


def _is_tag_on_remote(release_version, verbose):
    _verbose_output(verbose, 'Checking if tag {} was pushed to remote...', release_version)

    result = subprocess.check_output(
        ['git', 'ls-remote', '--tags', 'origin', release_version],
        stderr=sys.stderr,
    ).strip()

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
    ).strip()

    on_remote = []
    for line in result.splitlines():
        line = line.strip()
        if line.startswith('origin/'):
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
    try:
        return __import__('{}.version'.format(MODULE_NAME), fromlist=['__version__']).__version__
    except ImportError, e:
        import pprint
        _error_output_exit(
            'Could not import `__version__` from `{module}.version`. Error was "ImportError: {err}." Path is:\n{path}',
            module=MODULE_NAME,
            err=e.message,
            path=pprint.pformat(sys.path),
        )
    except AttributeError, e:
        _error_output_exit('Could not retrieve `__version__` from imported module. Error was "{}."', e.message)


def _ensure_files_exist(exit_on_failure):
    failure = False

    if not os.path.isfile(VERSION_FILENAME):
        _error_output(
            'Version file {} was not found! This project is not correctly configured to use `invoke release`!',
            VERSION_FILENAME,
        )
        failure = True

    if not os.path.isfile(CHANGELOG_FILENAME):
        _error_output(
            'Changelog file {} was not found! This project is not correctly configured to use `invoke release`!',
            CHANGELOG_FILENAME,
        )
        failure = True

    if exit_on_failure and failure:
        sys.exit(1)


def _ensure_configured(command):
    if not PARAMETERS_CONFIGURED:
        _error_output_exit('Cannot `invoke {}` before calling `configure_release_parameters`.', command)

    _ensure_files_exist(True)


def _set_map(function, iterable):
    ret = set()
    for i in iterable:
        r = function(i)
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


def configure_release_parameters(module_name, display_name, python_directory=None, plugins=None):
    global MODULE_NAME, MODULE_DISPLAY_NAME, RELEASE_MESSAGE_TEMPLATE, VERSION_FILENAME, CHANGELOG_FILENAME
    global ROOT_DIRECTORY, RELEASE_PLUGINS, PARAMETERS_CONFIGURED

    if PARAMETERS_CONFIGURED:
        _error_output_exit('Cannot call configure_release_parameters more than once.')

    if not module_name:
        _error_output_exit('module_name is required')
    if not display_name:
        _error_output_exit('display_name is required')

    MODULE_NAME = module_name
    MODULE_DISPLAY_NAME = display_name
    RELEASE_MESSAGE_TEMPLATE = 'Released {} version {{}}.'.format(MODULE_DISPLAY_NAME)

    ROOT_DIRECTORY = os.path.normpath(_get_root_directory())
    CHANGELOG_FILENAME = os.path.join(ROOT_DIRECTORY, 'CHANGELOG.txt')

    if python_directory:
        import_directory = os.path.normpath(os.path.join(ROOT_DIRECTORY, python_directory))
        VERSION_FILENAME = os.path.join(
            ROOT_DIRECTORY,
            '{python}/{module}/version.py'.format(python=python_directory, module=MODULE_NAME),
        )
    else:
        import_directory = ROOT_DIRECTORY
        VERSION_FILENAME = os.path.join(ROOT_DIRECTORY, '{}/version.py'.format(MODULE_NAME))

    if import_directory not in sys.path:
        sys.path.insert(0, import_directory)

    if getattr(plugins, '__iter__', None):
        RELEASE_PLUGINS = plugins

    PARAMETERS_CONFIGURED = True


@task
def version():
    """
    Prints the "Invoke Release" version and the version of the current project.
    """
    if not PARAMETERS_CONFIGURED:
        _error_output_exit('Cannot `invoke version` before calling `configure_release_parameters`.')

    from invoke_release.version import __version__
    _standard_output('Eventbrite Command Line Release Tools ("Invoke Release") {}', __version__)

    _ensure_files_exist(False)

    for error in _get_version_errors():
        _error_output(error)

    _standard_output('{module} {version}', module=MODULE_DISPLAY_NAME, version=_import_version_or_exit())

    _standard_output('Detected Git branch: {}', _get_branch_name(False))


@task(help={
    'verbose': 'Specify this switch to include verbose debug information in the command output.',
    'no-stash': 'Specify this switch to disable stashing any uncommitted changes (by default, changes that have '
                'not been committed are stashed before the release is executed).',
})
def release(verbose=False, no_stash=False):
    """
    Increases the version, adds a changelog message, and tags a new version of this project.

    :param verbose: See @task help above.
    :param no_stash: See @task help above.
    """
    _ensure_configured('release')

    from invoke_release.version import __version__
    _standard_output('Eventbrite Command Line Release Tools ("Invoke Release") {}', __version__)

    __version__ = _import_version_or_exit()

    branch_name = _get_branch_name(verbose)
    if branch_name != BRANCH_MASTER:
        instruction = _prompt(
            'You are currently on branch "{branch}" instead of "master." You should release ONLY patch versions '
            'from branches other than master.\nAre you sure you want to continue releasing from "{branch}?" (y/N)',
            branch=branch_name,
        ).lower()

        if instruction != INSTRUCTION_YES:
            _standard_output('Canceling release!')
            return

    try:
        _pre_release(__version__)
    except ReleaseFailure, e:
        _error_output_exit(e.message)

    _setup_task(no_stash, verbose)
    try:
        _standard_output('Releasing {}...', MODULE_DISPLAY_NAME)
        _standard_output('Current version: {}', __version__)

        release_version = _prompt('Enter a new version (or "exit"):').lower()
        if not release_version or release_version == INSTRUCTION_EXIT:
            raise ReleaseExit()
        if not re.match(VERSION_RE, release_version):
            raise ReleaseFailure(
                'Invalid version specified: {version}. Must match "{regex}".'.format(
                    version=release_version,
                    regex=VERSION_RE,
                ),
            )
        if not (LooseVersion(release_version) > LooseVersion(__version__)):
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

        cl_header, cl_message, cl_footer = _prompt_for_changelog(verbose)

        instruction = _prompt('No changes have been committed yet. Are you ready to commit the release? (Y/n)').lower()
        if instruction and instruction != INSTRUCTION_YES:
            raise ReleaseExit()

        _standard_output('Releasing {module} version: {version}', module=MODULE_DISPLAY_NAME, version=release_version)

        _write_to_version_file(release_version, verbose)
        _write_to_changelog_file(release_version, cl_header, cl_message, cl_footer, verbose)

        _pre_commit(__version__, release_version)

        _commit_release_changes(release_version, verbose)

        _pre_push(__version__, release_version)

        _tag_branch(release_version, verbose)
        pushed_or_rolled_back = _push_release_changes(release_version, branch_name, verbose)

        _post_release(__version__, release_version, pushed_or_rolled_back)

        _standard_output('Release process is complete.')
    except (ReleaseFailure, subprocess.CalledProcessError) as e:
        _error_output(e.message)
    except (ReleaseExit, KeyboardInterrupt):
        _standard_output('Canceling release!')
    finally:
        _cleanup_task(verbose)


@task(help={
    'verbose': 'Specify this switch to include verbose debug information in the command output.',
    'no-stash': 'Specify this switch to disable stashing any uncommitted changes (by default, changes that have '
                'not been committed are stashed before the release is rolled back).',
})
def rollback_release(verbose=False, no_stash=False):
    """
    If the last commit is the commit for the current release, this command deletes the release tag and deletes
    (if local only) or reverts (if remote) the last commit. This is fairly safe to do if the release has not
    yet been pushed to remote, but extreme caution should be exercised when invoking this after the release has
    been pushed to remote.

    :param verbose:  See @task help above.
    :param no_stash:  See @task help above.
    """
    _ensure_configured('rollback_release')

    from invoke_release.version import __version__
    _standard_output('Eventbrite Command Line Release Tools ("Invoke Release") {}', __version__)

    __version__ = _import_version_or_exit()

    branch_name = _get_branch_name(verbose)
    if branch_name != BRANCH_MASTER:
        instruction = _prompt(
            'You are currently on branch "{branch}" instead of "master." Rolling back on a branch other than master '
            'can be dangerous.\nAre you sure you want to continue rolling back on "{branch}?" (y/N)',
            branch=branch_name,
        ).lower()

        if instruction != INSTRUCTION_YES:
            _standard_output('Canceling release rollback!')
            return

    try:
        _pre_rollback(__version__)
    except ReleaseFailure, e:
        _error_output_exit(e.message)

    _setup_task(no_stash, verbose)
    try:
        commit_hash = _get_last_commit_hash(verbose)
        message = _get_commit_subject(commit_hash, verbose)
        if message != RELEASE_MESSAGE_TEMPLATE.format(__version__):
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
        delete = _prompt('Do you want to proceed with deleting this tag? (y/N)').lower()
        if delete == INSTRUCTION_YES:
            tag_on_remote = _is_tag_on_remote(__version__, verbose)
            _delete_local_tag(__version__, verbose)
            if tag_on_remote:
                _delete_remote_tag(__version__, verbose)

            _standard_output('The release tag has been deleted from local and remote (if applicable).')
            revert = _prompt('Do you also want to revert the commit? (y/N)').lower()
            if revert == INSTRUCTION_YES:
                if is_on_remote:
                    _standard_output('The commit is present on the remote origin.')
                    revert = _prompt(
                        'Are you sure you want to revert the commit and immediately push to remote origin? (y/N)',
                    ).lower()
                    if revert == INSTRUCTION_YES:
                        _revert_remote_commit(__version__, commit_hash, branch_name, verbose)
                else:
                    _delete_last_commit(verbose)
            else:
                _standard_output('The commit was not reverted.')

            module = __import__('{}.version'.format(MODULE_NAME), fromlist=['__version__'])
            reload(module)
            _post_rollback(__version__, module.__version__)

            _standard_output('Release rollback is complete.')
        else:
            raise ReleaseExit()
    except (ReleaseFailure, subprocess.CalledProcessError) as e:
        _error_output(e.message)
    except (ReleaseExit, KeyboardInterrupt):
        _standard_output('Canceling release rollback!')
    finally:
        _cleanup_task(verbose)
