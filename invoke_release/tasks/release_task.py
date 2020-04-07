import codecs
import datetime
import os
import re
import shlex
import subprocess
import sys
import tempfile
from typing import (
    Any,
    Callable,
    Dict,
    List,
    NamedTuple,
    Optional,
)

from invoke import task

from invoke_release.config import config
from invoke_release.errors import (
    ReleaseExit,
    ReleaseFailure,
    SourceControlError,
    VersionError,
)
from invoke_release.internal.constants import (
    INSTRUCTION_ACCEPT,
    INSTRUCTION_DELETE,
    INSTRUCTION_EDIT,
    INSTRUCTION_EXIT,
    INSTRUCTION_NEW,
    INSTRUCTION_NO,
    INSTRUCTION_ROLLBACK,
    INSTRUCTION_YES,
)
from invoke_release.internal.context import TaskContext
from invoke_release.internal.io import (
    Color,
    IOUtils,
)
from invoke_release.internal.plugins import (
    get_extra_files_to_commit,
    post_release,
    pre_commit,
    pre_push,
    pre_release,
)
from invoke_release.internal.source_control.base import (
    ItemType,
    SourceControl,
)
from invoke_release.internal.versions import (
    ReleaseCategory,
    read_project_version,
    suggest_version,
    update_version_file,
    validate_and_normalize_version,
)
from invoke_release.plugins.base import ReleaseStatus
from invoke_release.version import __version__


__all__ = (
    'release',
)


RE_VERSION = re.compile(r'^\d+\.\d+\.\d+([a-zA-Z\d.+-]*[a-zA-Z\d]+)?$')
RE_VERSION_BRANCH_MAJOR = re.compile(r'^\d+\.x\.x$')
RE_VERSION_BRANCH_MINOR = re.compile(r'^\d+\.\d+\.x$')
RE_CHANGELOG_FILE_HEADER = re.compile(r'^=+$')
RE_CHANGELOG_VERSION_HEADER = re.compile(r'^-+$')

CHANGELOG_COMMENT_FIRST_CHAR = '#'


Changelog = NamedTuple(
    'Changelog',
    (
        ('header', List[str]),
        ('message', List[str]),
        ('footer', List[str]),
    )
)


def check_branch(
    context: TaskContext,
    branch_name: str,
) -> None:
    if branch_name != context.config.master_branch:
        if not RE_VERSION_BRANCH_MAJOR.match(branch_name) and not RE_VERSION_BRANCH_MINOR.match(branch_name):
            context.io.error_output(
                'You are currently on branch "{branch}" instead of "{master}." You must release only from {master} '
                'or version branches, and this does not appear to be a version branch (must match '
                '\\d+\\.x\\.x or \\d+.\\d+\\.x).\nCanceling release!',
                branch=branch_name,
                master=context.config.master_branch,
            )
            raise ReleaseExit()

        instruction = context.io.prompt(
            'You are currently on branch "{branch}" instead of "{master}." Are you sure you want to continue releasing '
            'from "{branch}?" You must do this only from version branches, and only when higher versions have been '
            'released from the parent branch. (y/N):',
            branch=branch_name,
            master=context.config.master_branch,
        ).lower()

        if instruction != INSTRUCTION_YES:
            raise ReleaseExit()


def open_editor(context: TaskContext, edit_file_name: str) -> None:
    editor = os.environ.get('INVOKE_RELEASE_EDITOR', os.environ.get('EDITOR', 'vim'))
    context.io.verbose_output('Opening editor {} to edit changelog.', editor)
    try:
        subprocess.check_call(
            shlex.split(editor) + [edit_file_name],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
    except (subprocess.CalledProcessError, OSError) as e:
        args: Dict[str, Any] = {'editor': editor}
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
    context.io.verbose_output('User has closed editor')


def prompt_for_changelog(context: TaskContext, source: SourceControl) -> Changelog:
    built_up_changelog = []
    changelog_header = []
    changelog_message = []
    changelog_footer = []

    context.io.verbose_output(
        'Reading changelog file {} looking for built-up changes...',
        context.config.changelog_file_name,
    )
    with open(context.config.changelog_file_name, 'rt', encoding='utf8') as changelog_read:
        previous_line = ''
        passed_header = passed_changelog = False
        for line_number, line in enumerate(changelog_read):
            if not passed_header:
                changelog_header.append(line)
                # .txt, .md, and .rst (sometimes) changelog files start like this:
                #     Changelog
                #     =========
                # .rst changelog files sometimes start like this
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
        context.io.standard_output(
            f"There are existing changelog details for this release:\n    {'    '.join(built_up_changelog)}",
        )
        context.io.standard_output(
            'You can "edit" the changes, "accept" them as-is, delete them and create a "new" changelog message, or '
            '"delete" them and enter no changelog.',
        )
        instruction = context.io.prompt('How would you like to proceed? (EDIT/new/accept/delete/exit):').lower()

        if instruction in (INSTRUCTION_NEW, INSTRUCTION_DELETE):
            built_up_changelog = []
        if instruction == INSTRUCTION_ACCEPT:
            changelog_message = built_up_changelog
        if not instruction or instruction in (INSTRUCTION_EDIT, INSTRUCTION_NEW):
            instruction = INSTRUCTION_YES
    else:
        context.io.verbose_output('No existing lines of built-up changelog text were read.')
        instruction = context.io.prompt(
            'Would you like to enter changelog details for this release? (Y/n/exit):',
        ).lower() or INSTRUCTION_YES

    if instruction == INSTRUCTION_EXIT:
        raise ReleaseExit()

    if instruction == INSTRUCTION_YES:
        gather = context.io.prompt(
            'Would you like to{also} gather commit messages from recent commits and add them to the '
            'changelog? ({y_n}/exit):',
            **({'also': ' also', 'y_n': 'y/N'} if built_up_changelog else {'also': '', 'y_n': 'Y/n'})
        ).lower() or (INSTRUCTION_NO if built_up_changelog else INSTRUCTION_YES)

        commit_messages = []
        if gather == INSTRUCTION_YES:
            commit_messages = [f'- {m}' for m in source.gather_commit_messages_since_last_release()]
        elif gather == INSTRUCTION_EXIT:
            raise ReleaseExit()

        tf_o = tempfile.NamedTemporaryFile(mode='wb')
        codec = codecs.lookup('utf8')
        with codecs.StreamReaderWriter(tf_o, codec.streamreader, codec.streamwriter, 'strict') as tf:
            context.io.verbose_output('Opened temporary file {} for editing changelog.', tf.name)
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
                '# As a best practice, if you are entering multiple items as a list, prefix each item with a "-".\n'
            ])
            tf.flush()
            context.io.verbose_output('Wrote existing changelog contents and instructions to temporary file.')

            open_editor(context, tf.name)

            with open(tf.name, 'rt', encoding='utf8') as read:
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
            context.io.verbose_output('Changelog message read from temporary file:\n{}', changelog_message)

    return Changelog(changelog_header, changelog_message, changelog_footer)


def write_to_changelog_file(context: TaskContext, version: str, changelog: Changelog):
    context.io.verbose_output('Writing changelog contents to {}.', context.config.changelog_file_name)

    if not IOUtils.case_sensitive_regular_file_exists(context.config.changelog_file_name):
        raise ReleaseFailure(
            f'Failed to find changelog file: {context.config.changelog_file_name}. File names are case sensitive!',
        )

    with open(context.config.changelog_file_name, 'wt', encoding='utf8') as changelog_write:
        header_line = f"{version} ({datetime.datetime.now().strftime('%Y-%m-%d')})"

        changelog_write.writelines(changelog.header + ['\n'])
        changelog_write.writelines([
            header_line, '\n', '-' * len(header_line), '\n',
        ])
        if changelog.message:
            changelog_write.writelines(changelog.message + ['\n'])
        else:
            changelog_write.write('(No changelog details)\n\n')
        changelog_write.writelines(changelog.footer)

    context.io.verbose_output('Finished writing to changelog.')


@task(help={
    'verbose': 'Specify this switch to include verbose debug information in the command output.',
    'no-stash': 'Specify this switch to disable stashing any uncommitted changes (by default, changes that have '
                'not been committed are stashed before the release is executed).',
})
def release(_, verbose=False, no_stash=False):
    """
    Increases the version, adds a changelog message, and tags a new version of this project.
    """
    io = IOUtils(verbose)
    if not config.is_configured:
        io.error_output_exit('Cannot `invoke release` before calling `invoke_release.config.config.configure`.')

    context = TaskContext(config, io)
    source = config.source_control_class(context)

    io.standard_output('Invoke Release {}', __version__)

    source.pull_if_tracking_remote()

    project_version = read_project_version(f'{config.module_name}.version', config.version_file_name)

    branch_name = source.get_branch_name()

    try:
        check_branch(context, branch_name)
    except ReleaseExit:
        context.io.standard_output('Canceling release!')
        return

    try:
        pre_release(context, project_version)
    except ReleaseFailure as e:
        io.error_output_exit(e.args[0])

    stashed = False
    if not no_stash:
        stashed = source.stash_changes()

    rollback_actions: List[Callable[[], Any]] = []

    def do_rollback():
        for action in rollback_actions:
            action()

    try:
        io.standard_output('Releasing {}...', config.display_name)
        io.standard_output('Current version: {}', project_version)
        io.standard_output("First let's compile the changelog, and then we'll select a version to release.")

        changelog = prompt_for_changelog(context, source)
        release_category = ReleaseCategory.detect_from_changelog(changelog.message)
        suggested_version: Optional[str] = None
        if release_category:
            suggested_version = suggest_version(project_version, release_category)

        instruction = None
        if suggested_version:
            instruction = io.prompt(
                'According to the changelog message, the next version should be `{}`. '
                'Do you want to proceed with the suggested version? (Y/n)',
                suggested_version,
            ).lower() or INSTRUCTION_YES

        if suggested_version and instruction == INSTRUCTION_YES:
            release_version = suggested_version
        else:
            release_version = io.prompt('Enter a new version (or "exit"):').lower()

        if not release_version or release_version == INSTRUCTION_EXIT:
            raise ReleaseExit()

        release_version, version_info, version_separator = validate_and_normalize_version(
            project_version,
            release_version,
            branch_name if branch_name != config.master_branch else None,
        )

        if source.tag_exists_locally(release_version) or source.tag_exists_remotely(release_version):
            raise ReleaseFailure(
                f'Tag {release_version} already exists locally or remotely (or both). Cannot create version.',
            )

        instruction = io.prompt(
            'The changes to release files have not yet been committed. Are you ready to commit them? (Y/n):',
        ).lower()
        if instruction and instruction != INSTRUCTION_YES:
            raise ReleaseExit()

        io.standard_output('Releasing {module} version: {version}', module=config.display_name, version=release_version)

        context.use_gpg = False
        context.gpg_alternate_id = None
        if config.gpg_command and source.supports_gpg_signing:
            sign_with_key = io.prompt(
                'You have GPG installed on your system and your source control supports signing commits and tags.\n'
                'Would you like to use GPG to sign this release with the key matching your committer email? '
                '(y/N/[alternative key ID]):'
            )
            sign_with_key_lowered = sign_with_key.lower()
            if sign_with_key_lowered != INSTRUCTION_NO:
                context.use_gpg = True
                if sign_with_key_lowered != INSTRUCTION_YES:
                    context.gpg_alternate_id = sign_with_key

        rollback_actions = [source.reset_pending_changes]

        update_version_file(context, release_version, version_info, version_separator)
        write_to_changelog_file(context, release_version, changelog)

        pre_commit(context, project_version, release_version)

        current_branch_name = branch_name
        if config.use_pull_request:
            branch_name = f'invoke-release-{current_branch_name}-{release_version}'
            source.create_branch(branch_name)
            rollback_actions.extend([
                lambda: source.checkout_item(current_branch_name),
                lambda: source.delete_branch(branch_name),
            ])

        commit_title = config.release_message_template.format(release_version)
        commit_message = (
            f"{commit_title}\n\nChangelog Details:\n{''.join(changelog.message)}"
        )
        source.commit(
            [config.version_file_name, config.changelog_file_name] + get_extra_files_to_commit(context),
            commit_message,
        )

        rollback_actions[0] = source.delete_last_local_commit  # we no longer need to reset, now we need to delete

        pre_push(context, project_version, release_version)

        if config.use_tag:
            source.create_tag(release_version, commit_message)
            rollback_actions.insert(0, lambda: source.delete_tag_locally(release_version))

            message = 'Push release changes and tag to remote origin (branch "{}")? (y/N/rollback):'
        else:
            message = 'Push release changes to remote origin (branch "{}")? (y/N/rollback):'

        push = io.prompt(message, branch_name).lower()
        if push == INSTRUCTION_ROLLBACK:
            do_rollback()
            rollback_actions = []
            post_release(context, project_version, release_version, ReleaseStatus.ROLLED_BACK)
            raise ReleaseExit()

        elif push == INSTRUCTION_YES:
            source.push(branch_name)
            if config.use_tag:
                source.push(release_version, ItemType.TAG)

            if config.use_pull_request:
                source.checkout_item(current_branch_name)
                source.delete_branch(branch_name)
                try:
                    pr_opened = source.open_pull_request(
                        title=commit_title,
                        base=current_branch_name,
                        head=branch_name,
                    )
                except SourceControlError as e:
                    io.error_output(e.args[0])
                    pr_opened = None
                if pr_opened:
                    io.standard_output(f'GitHub PR created successfully. URL: {pr_opened}')
                else:
                    io.standard_output(
                        "You're almost done! The release process will be complete when you manually create a pull "
                        "request and it is merged."
                    )

            post_release(context, project_version, release_version, ReleaseStatus.PUSHED)

            if not config.use_pull_request:
                io.standard_output('Release process is complete.')

        else:
            rollback_actions = []
            if config.use_tag:
                io.print_output(
                    Color.RED_BOLD,
                    'Make sure you remember to explicitly push {branch} and the tag (or revert your local changes if '
                    'you are trying to cancel)! You can push with the following commands:\n'
                    '    git push origin {branch}:{branch}\n'
                    '    git push origin "refs/tags/{tag}:refs/tags/{tag}"\n',
                    branch=branch_name,
                    tag=release_version,
                )
            else:
                io.print_output(
                    Color.RED_BOLD,
                    'Make sure you remember to explicitly push {branch} (or revert your local changes if you are '
                    'trying to cancel)! You can push with the following command:\n'
                    '    git push origin {branch}:{branch}\n',
                    branch=branch_name,
                )
            post_release(context, project_version, release_version, ReleaseStatus.NOT_PUSHED)

    except (ReleaseFailure, SourceControlError, VersionError) as e:
        io.error_output(e.args[0])
        do_rollback()
    except subprocess.CalledProcessError as e:
        io.error_output(
            'Command {command} failed with error code {error_code}. Command output:\n{output}',
            command=e.cmd,
            error_code=e.returncode,
            output=e.output.decode('utf8'),
        )
        do_rollback()
    except (ReleaseExit, KeyboardInterrupt):
        io.standard_output('Canceling release!')
        do_rollback()
    except Exception:
        do_rollback()
        raise
    finally:
        if stashed:
            source.unstash_changes()
