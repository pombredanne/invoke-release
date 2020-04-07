import subprocess

from invoke import task

from invoke_release.config import config
from invoke_release.errors import (
    ReleaseExit,
    ReleaseFailure,
    SourceControlError,
)
from invoke_release.internal.constants import INSTRUCTION_YES
from invoke_release.internal.context import TaskContext
from invoke_release.internal.io import IOUtils
from invoke_release.internal.plugins import (
    post_rollback,
    pre_rollback,
)
from invoke_release.internal.versions import read_project_version
from invoke_release.version import __version__


__all__ = (
    'rollback_release',
)


@task(help={
    'verbose': 'Specify this switch to include verbose debug information in the command output.',
    'no-stash': 'Specify this switch to disable stashing any uncommitted changes (by default, changes that have '
                'not been committed are stashed before the release is rolled back).',
})
def rollback_release(_, verbose=False, no_stash=False):  # type: (str, bool, bool) -> None
    """
    If the last commit is the commit for the current release, this command deletes the release tag and deletes
    (if local only) or reverts (if remote) the last commit. This is fairly safe to do if the release has not
    yet been pushed to remote, but extreme caution should be exercised when invoking this after the release has
    been pushed to remote.
    """
    io = IOUtils(verbose)
    if not config.is_configured:
        io.error_output_exit(
            'Cannot `invoke rollback_release` before calling `invoke_release.config.config.configure`.',
        )

    context = TaskContext(config, io)
    source = config.source_control_class(context)

    io.standard_output('Invoke Release {}', __version__)

    source.pull_if_tracking_remote()

    project_version = read_project_version(f'{config.module_name}.version', config.version_file_name)

    branch_name = source.get_branch_name()
    if branch_name != config.master_branch:
        instruction = io.prompt(
            'You are currently on branch "{branch}" instead of "{master}." Rolling back on a branch other than '
            '{master} can be dangerous.\nAre you sure you want to continue rolling back on "{branch}?" (y/N):',
            branch=branch_name,
            master=config.master_branch,
        ).lower()

        if instruction != INSTRUCTION_YES:
            io.standard_output('Canceling release rollback!')
            return

    try:
        pre_rollback(context, project_version)
    except ReleaseFailure as e:
        io.error_output_exit(e.args[0])

    stashed = False
    if not no_stash:
        stashed = source.stash_changes()
    try:
        commit_id = source.get_last_commit_identifier()
        message = source.get_commit_title(commit_id)
        if message.rstrip('.') != config.release_message_template.format(project_version):
            raise ReleaseFailure('Cannot roll back because last commit is not the release commit.')

        on_remote = source.get_remote_branches_with_commit(commit_id)
        is_on_remote = False
        if len(on_remote) == 1:
            is_on_remote = on_remote[0] == 'origin/{}'.format(branch_name)
        elif len(on_remote) > 1:
            raise ReleaseFailure(
                'Cannot roll back because release commit is on multiple remote branches: {}'.format(on_remote),
            )

        io.standard_output('Release tag {} will be deleted locally and remotely (if applicable).', project_version)
        delete = io.prompt('Do you want to proceed with deleting this tag? (y/N):').lower()
        if delete == INSTRUCTION_YES:
            if source.tag_exists_locally(project_version):
                source.delete_tag_locally(project_version)

            if source.tag_exists_remotely(project_version):
                source.delete_tag_remotely(project_version)

            io.standard_output('The release tag has been deleted from local and remote (if applicable).')

            if is_on_remote:
                io.standard_output('The release commit is present on the remote origin.')
                prompt = 'Do you want to revert the commit and immediately push it to the remote origin? (y/N):'
            else:
                io.standard_output('The release commit is only present locally, not on the remote origin.')
                prompt = 'Are you ready to delete the commit like it never happened? (y/N):'

            revert = io.prompt(prompt).lower()
            if revert == INSTRUCTION_YES:
                if is_on_remote:
                    source.revert_commit(commit_id, branch_name)
                else:
                    source.delete_last_local_commit()
            else:
                io.standard_output('The commit was not {}.', 'reverted' if is_on_remote else 'deleted')

            new_version = read_project_version(f'{config.module_name}.version', config.version_file_name, reload=True)
            post_rollback(context, project_version, new_version)

            io.standard_output('Release rollback is complete.')
        else:
            raise ReleaseExit()
    except (ReleaseFailure, SourceControlError) as e:
        io.error_output(e.args[0])
    except subprocess.CalledProcessError as e:
        io.error_output(
            'Command {command} failed with error code {error_code}. Command output:\n{output}',
            command=e.cmd,
            error_code=e.returncode,
            output=e.output.decode('utf8'),
        )
    except (ReleaseExit, KeyboardInterrupt):
        io.standard_output('Canceling release rollback!')
    finally:
        if stashed:
            source.unstash_changes()
