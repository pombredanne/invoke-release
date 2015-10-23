import datetime
import os
import re
import subprocess
import sys
from distutils.version import LooseVersion

from invoke import task

VERSION_RE = r'^\d+\.\d+\.\d+$'
VERSION_VARIABLE_RE = '^__version__ = \d+\.\d+\.\d+$'

VERSION_INFO_VARIABLE_TEMPLATE = '__version_info__ = %s'
VERSION_VARIABLE_TEMPLATE = "__version__ = '.'.join(map(str, __version_info__))"
RELEASE_MESSAGE_TEMPLATE = 'Released [unknown] version %s.'

MODULE_NAME = 'unknown'
MODULE_DISPLAY_NAME = '[unknown]'

VERSION_FILENAME = 'python/unknown/version.py'
CHANGELOG_FILENAME = 'CHANGELOG.txt'
CHANGELOG_RC_FILENAME = '.gitchangelog.rc'

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
COLOR_RED_BOLD = '31;1'
COLOR_GRAY_LIGHT = '38;5;242'
COLOR_WHITE = '37;1'


class ReleaseFailure(Exception):
    """
    Exception raised when something caused the release to fail, and cleanup is required.
    """


def _print_output(color, message, *args):
    if _output_is_tty:
        _output.write('\x1b[%sm%s\x1b[0m' % (color, message % tuple(args), ))
        _output.flush()
    else:
        print message % args


def _standard_output(message, *args):
    _print_output(COLOR_GREEN_BOLD, message + "\n", *args)


def _prompt(message, *args):
    _print_output(COLOR_WHITE, message + ' ', *args)
    return raw_input()


def _error_output(message, *args):
    _print_output(COLOR_RED_BOLD, ''.join(('ERROR: ', message, "\n")), *args)


def _error_output_exit(message, *args):
    _error_output(message, *args)
    sys.exit(1)


def _verbose_output(verbose, message, *args):
    if verbose:
        _print_output(COLOR_GRAY_LIGHT, ''.join(('DEBUG: ', message, "\n")), *args)


def _get_root_directory():
    root_directory = subprocess.check_output(
        ['git', 'rev-parse', '--show-toplevel']
    ).strip()

    if not root_directory:
        _error_output_exit('Failed to find git root directory')
    return root_directory


def _setup_task(no_stash, verbose):
    if not no_stash:
        global __POST_APPLY
        # stash changes before we execute task
        _verbose_output(verbose, 'Stashing changes...')

        result = subprocess.check_output(['git', 'stash'])
        if result.startswith('Saved'):
            __POST_APPLY = True

        _verbose_output(verbose, 'Finished stashing changes.')


def _cleanup_task(verbose):
    if __POST_APPLY:
        _verbose_output(verbose, 'Un-stashing changes...')

        subprocess.call(['git', 'stash', 'apply'])

        _verbose_output(verbose, 'Finished un-stashing changes.')


def _write_to_version_file(release_version, verbose):
    _verbose_output(verbose, 'Writing version to %s...', VERSION_FILENAME)

    if not os.path.exists(VERSION_FILENAME):
        raise ReleaseFailure(
            'Failed to find version file: %s' % (VERSION_FILENAME, )
        )

    with open(VERSION_FILENAME, 'r') as version_read:
        output = []
        version_info_written = False
        version_info = VERSION_INFO_VARIABLE_TEMPLATE % (tuple([int(v) for v in release_version.split('.')]), )
        for line in version_read:
            if line.startswith('__version_info__'):
                output.append(version_info)
                version_info_written = True
            elif line.startswith('__version__'):
                if not version_info_written:
                    output.append(version_info)
                # This old version code isn't used anymore, but is kept around for troubleshooting/testing purposes
                # new_version = re.sub(
                #     line,
                #     VERSION_VARIABLE_RE,
                #     VERSION_VARIABLE_TEMPLATE % (release_version, ),
                # )
                # output.append(new_version)
                output.append(VERSION_VARIABLE_TEMPLATE)
            else:
                output.append(line.rstrip())

    with open(VERSION_FILENAME, 'w') as version_write:
        for line in output:
            version_write.write(line)
            version_write.write('\n')

    _verbose_output(verbose, 'Finished writing to %s.version.', MODULE_NAME)


def _write_to_changelog(release_version, message, verbose):
    _verbose_output(verbose, 'Writing changelog to %s...', CHANGELOG_FILENAME)

    if not os.path.exists(CHANGELOG_FILENAME):
        raise ReleaseFailure(
            'Failed to find changelog file: %s' % (CHANGELOG_FILENAME, )
        )

    with open(CHANGELOG_FILENAME, 'r') as changelog_read:
        output = []
        wrote_new_message = False
        for line in changelog_read:
            # Find the title underline
            if not wrote_new_message and re.search('^=+$', line):
                output.append(line.strip())
                output.append('')

                header_line = '%s (%s)' % (release_version, datetime.datetime.now().strftime('%Y-%m-%d'), )
                output.append(header_line)
                output.append('-' * len(header_line))
                output.append(message)

                wrote_new_message = True
            else:
                output.append(line.rstrip())

    with open(CHANGELOG_FILENAME, 'w') as changelog_write:
        for line in output:
            changelog_write.write(line)
            changelog_write.write('\n')

    _verbose_output(verbose, 'Finished writing to changelog.')


def _tag_branch(release_version, verbose, overwrite=False):
    _verbose_output(verbose, 'Tagging branch...')

    release_message = RELEASE_MESSAGE_TEMPLATE % (release_version, )
    cmd = ['git', 'tag', '-a', release_version, '-m', release_message]
    if overwrite:
        cmd.append('-f')
    result = subprocess.check_output(cmd)
    if result:
        raise ReleaseFailure('Failed tagging branch: %s' % (result, ))

    _verbose_output(verbose, 'Finished tagging branch.')


def _commit_release_changes(release_version, verbose):
    _verbose_output(verbose, 'Committing release changes...')

    result = subprocess.check_output(
        ['git', 'add', VERSION_FILENAME, CHANGELOG_FILENAME],
    )
    if result:
        raise ReleaseFailure(
            'Failed staging release files for commit: %s' % (result, )
        )

    release_message = RELEASE_MESSAGE_TEMPLATE % (release_version, )
    print subprocess.check_output(
        ['git', 'commit', '-m', release_message]
    )

    _verbose_output(verbose, 'Finished releasing changes.')


def _push_release_changes(release_version, verbose):
    try:
        push = raw_input('Push release changes and tag to master? (y/N/rollback): ').strip().lower()
    except KeyboardInterrupt:
        push = 'rollback'

    if push == 'y':
        _verbose_output(verbose, 'Pushing changes to master...')

        print subprocess.check_output(
            ['git', 'push', 'origin', 'master']
        )
        # push the release tag
        print subprocess.check_output(
            ['git', 'push', 'origin', release_version]
        )

        _verbose_output(verbose, 'Finished pushing changes to master.')
    elif push == 'rollback':
        _standard_output('Rolling back local release commit and tag...')

        _delete_last_commit(verbose)
        _delete_local_tag(release_version, verbose)

        _verbose_output(verbose, 'Finished rolling back local release commit.')
    else:
        _standard_output('Not pushing changes to master!')
        _standard_output('Make sure you remember to explicitly push the tag, or '
                         'revert your local changes if you are trying to cancel!')


def _get_last_commit_hash(verbose):
    _verbose_output(verbose, 'Getting last commit hash...')

    commit_hash = subprocess.check_output(
        ['git', 'log', '-n', '1', '--pretty=format:%H']
    ).strip()

    _verbose_output(verbose, 'Last commit hash is %s.', commit_hash)

    return commit_hash


def _get_commit_subject(commit_hash, verbose):
    _verbose_output(verbose, 'Getting commit message for hash %s...', commit_hash)

    message = subprocess.check_output(
        ['git', 'log', '-n', '1', '--pretty=format:%B', commit_hash]
    ).strip()

    _verbose_output(verbose, 'Commit message for hash %s is "%s".', commit_hash, message)

    return message


def _is_tag_on_remote(release_version, verbose):
    _verbose_output(verbose, 'Checking if tag %s was pushed to remote...', release_version)

    result = subprocess.check_output(
        ['git', 'ls-remote', '--tags', 'origin', release_version]
    ).strip()

    on_remote = release_version in result

    _verbose_output(verbose, 'Result of on-remote check for tag %s is %s.', release_version, on_remote)

    return on_remote


def _is_commit_on_remote(commit_hash, verbose):
    _verbose_output(verbose, 'Checking if commit %s was pushed to remote...', commit_hash)

    result = subprocess.check_output(
        ['git', 'branch', '-r', '--contains', commit_hash]
    ).strip()

    on_remote = 'origin/master' in result

    _verbose_output(verbose, 'Result of on-remote check for commit %s is %s.', commit_hash, on_remote)

    return on_remote


def _delete_local_tag(tag_name, verbose):
    _verbose_output(verbose, 'Deleting local tag %s...', tag_name)

    print subprocess.check_output(
        ['git', 'tag', '-d', tag_name]
    )

    _verbose_output(verbose, 'Finished deleting local tag %s.', tag_name)


def _delete_remote_tag(tag_name, verbose):
    _verbose_output(verbose, 'Deleting remote tag %s...', tag_name)

    print subprocess.check_output(
        ['git', 'push', 'origin', ':refs/tags/%s' % (tag_name, )]
    )

    _verbose_output(verbose, 'Finished deleting remote tag %s.', tag_name)


def _delete_last_commit(verbose):
    _verbose_output(verbose, 'Deleting last commit, assumed to be for version and changelog files...')

    print subprocess.check_output(
        ['git', 'reset', '--soft', 'HEAD~1']
    )
    print subprocess.check_output(
        ['git', 'reset', 'HEAD', VERSION_FILENAME, CHANGELOG_FILENAME],
    )
    print subprocess.check_output(
        ['git', 'checkout', '--', VERSION_FILENAME, CHANGELOG_FILENAME],
    )

    _verbose_output(verbose, 'Finished deleting last commit.')


def _revert_remote_commit(release_version, commit_hash, verbose):
    _verbose_output(verbose, 'Rolling back release commit...')

    print subprocess.check_output(
        ['git', 'revert', '--no-edit', '--no-commit', commit_hash]
    )

    release_message = 'REVERT: ' + RELEASE_MESSAGE_TEMPLATE % (release_version, )
    print subprocess.check_output(
        ['git', 'commit', '-m', release_message]
    )

    _verbose_output(verbose, 'Pushing changes to master...')
    print subprocess.check_output(
        ['git', 'push', 'origin', 'master']
    )

    _verbose_output(verbose, 'Finished rolling back release commit.')


def configure_release_parameters(module_name, display_name, python_directory=None):
    global MODULE_NAME, MODULE_DISPLAY_NAME, RELEASE_MESSAGE_TEMPLATE, VERSION_FILENAME, CHANGELOG_FILENAME
    global PARAMETERS_CONFIGURED

    if PARAMETERS_CONFIGURED:
        _error_output_exit('Cannot call configure_release_parameters more than once.')

    if not module_name:
        _error_output_exit('module_name is required')
    if not display_name:
        _error_output_exit('display_name is required')

    MODULE_NAME = module_name
    MODULE_DISPLAY_NAME = display_name
    RELEASE_MESSAGE_TEMPLATE = 'Released %s version %%s.' % (MODULE_DISPLAY_NAME, )

    root_directory = os.path.normpath(_get_root_directory())
    CHANGELOG_FILENAME = os.path.join(root_directory, 'CHANGELOG.txt')

    if python_directory:
        import_directory = os.path.normpath(os.path.join(root_directory, python_directory))
        VERSION_FILENAME = os.path.join(root_directory, '%s/%s/version.py' % (python_directory, MODULE_NAME, ))
    else:
        import_directory = root_directory
        VERSION_FILENAME = os.path.join(root_directory, '%s/version.py' % (MODULE_NAME, ))

    if import_directory not in sys.path:
        sys.path.insert(0, import_directory)

    PARAMETERS_CONFIGURED = True


@task
def version():
    """
    Prints the "Invoke Release" version and the version of the current project.
    """
    if not PARAMETERS_CONFIGURED:
        _error_output_exit('Cannot invoke version before calling configure_release_parameters.')

    from invoke_release.version import __version__
    _standard_output('Eventbrite Command Line Release Tools ("Invoke Release") %s', __version__)

    project_version = __import__('%s.version' % (MODULE_NAME, ), fromlist=['__version__']).__version__
    _standard_output('%s %s', MODULE_DISPLAY_NAME, project_version)

    if not os.path.isfile(VERSION_FILENAME):
        _error_output(('Version file %s was not found! This project is not correctly configured to use '
                       '`invoke release`!') % (VERSION_FILENAME, ))


@task(help={
    'verbose': 'Specify this switch to include verbose debug information in the command output.',
    'no-stash': 'Specify this switch to disable stashing any uncommitted changes (by default, changes that have '
                'not been committed are stashed before the release is executed).',
})
def release(verbose=False, no_stash=False):
    """
    Increases the version, adds a changelog message, and tags a new version of this project.
    """
    if not PARAMETERS_CONFIGURED:
        _error_output_exit('Cannot invoke release before calling configure_release_parameters.')

    __version__ = __import__('%s.version' % (MODULE_NAME, ), fromlist=['__version__']).__version__

    _setup_task(no_stash, verbose)
    try:
        _standard_output('Releasing %s...', MODULE_DISPLAY_NAME)
        _standard_output('Current version: %s', __version__)
        release_version = _prompt('Enter a new version (or "exit"):')
        if not release_version or release_version.lower() == 'exit':
            _standard_output('Canceling release!')
            return
        if not re.match(VERSION_RE, release_version):
            raise ReleaseFailure(
                'Invalid version specified: %s. Must match "%s".' % (release_version, VERSION_RE, )
            )
        if not (LooseVersion(release_version) > LooseVersion(__version__)):
            raise ReleaseFailure(
                'New version number %s is not greater than current version %s.' % (release_version, __version__, )
            )
        _print_output(COLOR_WHITE, 'Enter a changelog message (or "exit" to exit, or just leave blank to skip; '
                                   'hit Enter for a new line, hit Enter twice to finish the changelog message):\n')
        sentinel = ''
        changelog_text = '\n'.join(iter(raw_input, sentinel)).strip()
        if changelog_text and changelog_text.lower() == 'exit':
            _standard_output('Canceling release!')
            return
        _standard_output('Releasing %s version: %s', MODULE_DISPLAY_NAME, release_version)
        _write_to_version_file(release_version, verbose)
        if changelog_text:
            _write_to_changelog(release_version, changelog_text, verbose)
        _commit_release_changes(release_version, verbose)
        _tag_branch(release_version, verbose)
        _push_release_changes(release_version, verbose)
        _standard_output('Release process is complete.')
    except ReleaseFailure, e:
        _error_output(e.message)
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
    """
    if not PARAMETERS_CONFIGURED:
        _error_output_exit('Cannot invoke rollback_release before calling configure_release_parameters.')

    __version__ = __import__('%s.version' % (MODULE_NAME, ), fromlist=['__version__']).__version__

    _setup_task(no_stash, verbose)
    try:
        commit_hash = _get_last_commit_hash(verbose)
        message = _get_commit_subject(commit_hash, verbose)
        if message != (RELEASE_MESSAGE_TEMPLATE % (__version__, )):
            raise ReleaseFailure('Cannot roll back because last commit is not the release commit.')

        _standard_output('Release tag %s will be deleted locally and remotely (if applicable).', __version__)
        delete = _prompt('Do you want to proceed with deleting this tag? (y/N):').lower()
        if delete == 'y':
            tag_on_remote = _is_tag_on_remote(__version__, verbose)
            _delete_local_tag(__version__, verbose)
            if tag_on_remote:
                _delete_remote_tag(__version__, verbose)

            _standard_output('The release tag has been deleted from local and remote (if applicable).')
            revert = _prompt('Do you also want to revert the commit? (y/N):').lower()
            if revert == 'y':
                if _is_commit_on_remote(commit_hash, verbose):
                    _standard_output('The commit is present on the remote master branch.')
                    revert = _prompt(
                        'Are you sure you want to revert the commit and immediately push to master? (y/N):'
                    ).lower()
                    if revert == 'y':
                        _revert_remote_commit(__version__, commit_hash, verbose)
                else:
                    _delete_last_commit(verbose)
            else:
                _standard_output('The commit was not reverted.')
            _standard_output('Release rollback is complete.')
        else:
            _standard_output('Canceling release rollback!')
    except ReleaseFailure, e:
        _error_output(e.message)
    finally:
        _cleanup_task(verbose)
