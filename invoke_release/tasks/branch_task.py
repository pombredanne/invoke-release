from distutils.version import LooseVersion
import subprocess

from invoke import task

from invoke_release.config import config
from invoke_release.errors import (
    ReleaseExit,
    ReleaseFailure,
    SourceControlError,
)
from invoke_release.internal.constants import (
    INSTRUCTION_EXIT,
    INSTRUCTION_MAJOR,
    INSTRUCTION_SKIP,
    INSTRUCTION_YES,
)
from invoke_release.internal.context import TaskContext
from invoke_release.internal.io import IOUtils
from invoke_release.internal.source_control.base import ItemType
from invoke_release.version import __version__


__all__ = (
    'branch',
)


@task(help={
    'verbose': 'Specify this switch to include verbose debug information in the command output.',
    'no-stash': 'Specify this switch to disable stashing any uncommitted changes (by default, changes that have '
                'not been committed are stashed before the branch is created).',
})
def branch(_, verbose=False, no_stash=False):  # type: (str, bool, bool) -> None
    """
    Creates a branch from a release tag for creating a new patch or minor release from that branch.
    """
    io = IOUtils(verbose)
    if not config.is_configured:
        io.error_output_exit('Cannot `invoke branch` before calling `invoke_release.config.config.configure`.')

    context = TaskContext(config, io)
    source = config.source_control_class(context)

    io.standard_output('Invoke Release {}', __version__)

    stashed = False
    if not no_stash:
        stashed = source.stash_changes()
    try:
        branch_version = io.prompt('Enter a version tag from which to create a new branch (or "exit"):').lower()
        if not branch_version or branch_version == INSTRUCTION_EXIT:
            raise ReleaseExit()

        source.fetch_remote_tags()
        tags = source.list_tags()
        if branch_version not in tags:
            raise ReleaseFailure('Version number {} not in the list of available tags.'.format(branch_version))

        parsed_version = LooseVersion(branch_version)
        minor_branch = '.'.join(list(map(str, parsed_version.version[:2])) + ['x'])
        major_branch = '.'.join(list(map(str, parsed_version.version[:1])) + ['x', 'x'])

        proceed_instruction = io.prompt(
            'Using tag {tag}, would you like to create a minor branch for patch versions (branch name {minor}, '
            'recommended), or a major branch for minor versions (branch name {major})? (MINOR/major/exit):',
            tag=branch_version,
            minor=minor_branch,
            major=major_branch,
        )

        if proceed_instruction == INSTRUCTION_EXIT:
            raise ReleaseExit()

        new_branch = major_branch if proceed_instruction == INSTRUCTION_MAJOR else minor_branch

        if config.use_pull_request:
            if source.branch_exists_remotely(new_branch):
                io.standard_output(
                    'Branch {branch} exists on remote. Checking it out into a local tracking branch.',
                    branch=new_branch,
                )
                try:
                    source.checkout_remote_branch(new_branch)
                except SourceControlError:
                    raise ReleaseFailure(
                        f'Could not check out a local branch tracking remote branch {new_branch}. Does a local branch '
                        f'named {new_branch} already exist?\nDelete or rename your local branch {new_branch} and try '
                        f'again, or just pull your local branch to manually work against it.',
                    )
            else:
                io.standard_output(
                    'Branch {branch} does not yet exist on remote. Creating new branch and pushing to remote.',
                    branch=new_branch,
                )
                source.create_branch(new_branch, branch_version, from_item_type=ItemType.TAG)
                source.push(new_branch, set_tracking=True)

            cherry_pick_branch_suffix = io.prompt(
                'Now you should create the branch where you will apply your changes. You need a token to uniquely\n'
                'identify your feature branch, such as a GitHub or JIRA issue.\n'
                f'Enter it here to create a branch named `cherry-pick-{new_branch}-<entered_token>` '
                f'(or SKIP to skip this step):'
            )
            if cherry_pick_branch_suffix and cherry_pick_branch_suffix.lower() != INSTRUCTION_SKIP:
                source.create_branch(f'cherry-pick-{new_branch}-{cherry_pick_branch_suffix}')
        else:
            source.create_branch(new_branch, branch_version, from_item_type=ItemType.TAG)

            push_instruction = io.prompt(
                'Branch {} created. Would you like to go ahead and push it to remote? (y/N):',
                new_branch,
            ).lower()
            if push_instruction and push_instruction == INSTRUCTION_YES:
                source.push(new_branch, set_tracking=True)

        io.standard_output('Branch process is complete.')
    except (SourceControlError, ReleaseFailure) as e:
        io.error_output(e.args[0])
    except subprocess.CalledProcessError as e:
        io.error_output(
            'Command {command} failed with error code {error_code}. Command output:\n{output}',
            command=e.cmd,
            error_code=e.returncode,
            output=e.output.decode('utf8'),
        )
    except (ReleaseExit, KeyboardInterrupt):
        io.standard_output('Canceling branch!')
    finally:
        if stashed:
            source.unstash_changes()
