import subprocess
import sys

from invoke import task

from invoke_release.config import config
from invoke_release.internal.context import TaskContext
from invoke_release.internal.io import IOUtils
from invoke_release.internal.utils import set_map
from invoke_release.internal.versions import read_project_version


__all__ = (
    'version',
)


@task(help={
    'verbose': 'Specify this switch to include verbose debug information in the command output.',
})
def version(_, verbose=False):  # type: (str, bool) -> None
    """
    Prints the "Invoke Release" version and the version of the current project.
    """
    io = IOUtils(verbose)
    if not config.is_configured:
        io.error_output_exit('Cannot `invoke version` before calling `invoke_release.config.config.configure`.')

    context = TaskContext(config, io)
    source = config.source_control_class(context)

    io.standard_output('Python: {}', sys.version.split('\n')[0].strip())
    io.standard_output('Source control: {}', source.get_version())

    if config.gpg_command:
        if verbose:
            gpg_version = subprocess.check_output(
                [config.gpg_command, '--version'],
                stderr=subprocess.STDOUT,
            ).decode('utf-8').strip().split('\n')[0]
            io.verbose_output('GPG ({}): {}', config.gpg_command, gpg_version)
    else:
        io.verbose_output("GPG: Not installed (won't be used)")

    if config.tty:
        io.verbose_output('TTY: {}', config.tty)
    else:
        io.verbose_output('TTY: None detected')

    from invoke import __version__ as invoke_version
    io.standard_output('Invoke: {}', invoke_version)

    from invoke_release.version import __version__
    io.standard_output('Invoke Release: {}', __version__)

    errors = config.get_file_existence_errors()
    if errors:
        io.error_output('\n'.join(errors))

    for error in set_map(lambda plugin: plugin.error_check(config.root_directory), config.plugins):
        io.error_output(error)

    try:
        project_version = read_project_version(f'{config.module_name}.version', config.version_file_name)
    except Exception as e:
        project_version = f'[Error: Could not read version: {e!r}]'

    io.standard_output('Detected Project: {} {}', config.display_name, project_version)
    io.standard_output('Detected Git branch: {}', source.get_branch_name())
    io.standard_output('Detected version file: {}', config.version_file_name)
    io.standard_output('Detected changelog file: {}', config.changelog_file_name)
    io.verbose_output('Release commit message template: "{}"', config.release_message_template)
