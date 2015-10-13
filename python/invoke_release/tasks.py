import datetime
import os
import re
import subprocess
import sys

from invoke import task

VERSION_RE = r'^\d+\.\d+\.\d+$'
VERSION_VARIABLE_RE = '^__version__ = \d+\.\d+\.\d+$'

VERSION_INFO_VARIABLE_TEMPLATE = '__version_info__ = %s'
VERSION_VARIABLE_TEMPLATE = "__version__ = '.'.join(map(str, __version_info__))"
RELEASE_MESSAGE_TEMPLATE = 'Releasing [unknown] version %s'

MODULE_NAME = 'unknown'
MODULE_DISPLAY_NAME = '[unknown]'

PYTHON_DIRECTORY = 'python'
VERSION_FILE = 'python/unknown/version.py'
CHANGELOG_FILENAME = 'CHANGELOG.txt'
CHANGELOG_RC_FILENAME = '.gitchangelog.rc'

PARAMETERS_CONFIGURED = False


__POST_APPLY = False


__all__ = [
    'configure_release_parameters',
    'release',
    'rollback_release',
]


class ReleaseFailure(Exception):
    """Exception raised when something caused the release to fail"""


def configure_release_parameters(module_name, display_name, python_directory=None):
    global MODULE_NAME, MODULE_DISPLAY_NAME, RELEASE_MESSAGE_TEMPLATE, PYTHON_DIRECTORY, VERSION_FILE
    global PARAMETERS_CONFIGURED

    if PARAMETERS_CONFIGURED:
        raise ReleaseFailure('Cannot call configure_release_parameters more than once.')

    if not module_name:
        raise ValueError('module_name is required')
    if not display_name:
        raise ValueError('display_name is required')

    MODULE_NAME = module_name
    MODULE_DISPLAY_NAME = display_name
    RELEASE_MESSAGE_TEMPLATE = 'Releasing %s version %%s' % (MODULE_DISPLAY_NAME, )

    if python_directory:
        PYTHON_DIRECTORY = python_directory

    VERSION_FILE = '%s/%s/version.py' % (PYTHON_DIRECTORY, MODULE_NAME, )

    PARAMETERS_CONFIGURED = True


def _get_root_directory():
    root_directory = subprocess.check_output(
        ['git', 'rev-parse', '--show-toplevel']
    ).strip()

    if not root_directory:
        raise ReleaseFailure('Failed to find git root directory')
    return root_directory


def _setup_task(nostash, verbose):
    if not nostash:
        global __POST_APPLY
        # stash changes before we execute task
        if verbose:
            print 'Stashing changes...'
        result = subprocess.check_output(['git', 'stash'])
        if result.startswith('Saved'):
            __POST_APPLY = True
        if verbose:
            print '...Finished stashing changes.'


def _cleanup_task(verbose):
    if __POST_APPLY:
        if verbose:
            print 'Un-stashing changes...'
        subprocess.call(['git', 'stash', 'apply'])
        if verbose:
            print '...Finished un-stashing changes.'


def _write_to_version_file(root_directory, release_version, verbose):
    if verbose:
        print 'Writing version to %s...' % (VERSION_FILE, )

    version_file = os.path.join(root_directory, VERSION_FILE)
    if not os.path.exists(version_file):
        raise ReleaseFailure(
            'Failed to find version file: %s' % (version_file, )
        )

    with open(version_file, 'r') as version_read:
        output = []
        version_info_written = False
        version_info = VERSION_INFO_VARIABLE_TEMPLATE % (tuple(release_version.split('.')), )
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
                output.append(line.strip())

    with open(version_file, 'w') as version_write:
        for line in output:
            version_write.write(line)
            version_write.write('\n')

    if verbose:
        print '...Finished writing to %s.version.' % (MODULE_NAME, )


def _write_to_changelog(root_directory, release_version, message, verbose):
    if verbose:
        print 'Writing changelog to %s...' % (CHANGELOG_FILENAME, )

    changelog_file = os.path.join(root_directory, CHANGELOG_FILENAME)
    if not os.path.exists(changelog_file):
        raise ReleaseFailure(
            'Failed to find changelog file: %s' % (changelog_file, )
        )

    with open(changelog_file, 'r') as changelog_read:
        output = []
        for line in changelog_read:
            # Find the title underline
            if re.search('^=+$', line):
                output.append(line.strip())
                output.append('')
                output.append('%s (%s)' % (release_version, datetime.datetime.now().strftime('%Y-%m-%d'), ))
                output.append('------------------')
                output.append(message)
            else:
                output.append(line.strip())

    with open(changelog_file, 'w') as changelog_write:
        for line in output:
            changelog_write.write(line)
            changelog_write.write('\n')

    if verbose:
        print '...Finished writing to changelog.'


def _tag_branch(release_version, verbose, overwrite=False):
    if verbose:
        print 'Tagging branch...'

    release_message = RELEASE_MESSAGE_TEMPLATE % (release_version, )
    cmd = ['git', 'tag', '-a', release_version, '-m', release_message]
    if overwrite:
        cmd.append('-f')
    result = subprocess.check_output(cmd)
    if result:
        raise ReleaseFailure('Failed tagging branch: %s' % (result, ))

    if verbose:
        print '...Finished tagging branch.'


def _commit_release_changes(root_directory, release_version, verbose):
    """Commit changes to version file and changelog"""
    if verbose:
        print 'Committing release changes...'

    version_file = os.path.join(root_directory, VERSION_FILE)
    changelog_file = os.path.join(root_directory, CHANGELOG_FILENAME)
    result = subprocess.check_output(
        ['git', 'add', version_file, changelog_file],
    )
    if result:
        raise ReleaseFailure(
            'Failed staging release files for commit: %s' % (result, )
        )

    release_message = RELEASE_MESSAGE_TEMPLATE % (release_version, )
    print subprocess.check_output(
        ['git', 'commit', '-m', release_message]
    )

    if verbose:
        print '...Finished releasing changes.'


def _push_release_changes(release_version, verbose):
    push = raw_input('push release changes to master? (y/n): ')
    if push == 'y':
        if verbose:
            print 'Pushing changes to master...'

        print subprocess.check_output(
            ['git', 'push', 'origin', 'master']
        )
        # push the release tag
        print subprocess.check_output(
            ['git', 'push', 'origin', release_version]
        )
        if verbose:
            print '...Finished pushing changes to master.'
    else:
        print 'Not pushing changes to master!'
        print 'Make sure you remember to explicitly push the tag!'


@task
def release(verbose=False, nostash=False):
    if not PARAMETERS_CONFIGURED:
        raise ReleaseFailure('Cannot invoke release before calling configure_release_parameters.')

    root_directory = _get_root_directory()
    sys.path.insert(0, os.path.join(root_directory, PYTHON_DIRECTORY))
    __version__ = __import__('%s.version' % (MODULE_NAME, ), fromlist=['__version__']).__version__

    _setup_task(nostash, verbose)
    try:
        print 'Releasing %s...' % (MODULE_DISPLAY_NAME, )
        print 'Current version: %s' % (__version__, )
        release_version = raw_input('Enter a new version (or "exit"): ')
        if release_version.lower() == 'exit':
            print 'Cancelling release!'
            return
        if not re.match(VERSION_RE, release_version):
            raise ReleaseFailure(
                'Invalid version specified: %s. Must match "%s".'
                ' Exiting without releasing.' % (
                    release_version,
                    VERSION_RE,
                )
            )
        print('Enter a changelog message (or "exit" to exit, or just leave blank to skip; '
              'hit Enter for a new line, hit Enter twice to finish the changelog message):'),
        sentinel = ''
        changelog_text = '\n'.join(iter(raw_input, sentinel)).strip()
        if changelog_text and changelog_text.lower() == 'exit':
            print 'Cancelling release!'
            return
        print 'Releasing %s version: %s' % (MODULE_DISPLAY_NAME, release_version, )
        _write_to_version_file(root_directory, release_version, verbose)
        if changelog_text:
            _write_to_changelog(root_directory, release_version, changelog_text, verbose)
        _commit_release_changes(root_directory, release_version, verbose)
        _tag_branch(release_version, verbose)
        _push_release_changes(release_version, verbose)
    finally:
        _cleanup_task(verbose)


@task
def rollback_release():
    # undo release, not sure if we need this yet
    # if you want to rollback a release and haven't pushed to master:
    #   $ git reset --hard HEAD^
    #   $ git tag -d <whatever version number you entered>
    if not PARAMETERS_CONFIGURED:
        raise ReleaseFailure('Cannot invoke rollback_release before calling configure_release_parameters.')

    raise NotImplementedError('Rollback is not yet implemented.')
