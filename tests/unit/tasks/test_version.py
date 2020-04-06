import subprocess
import sys
from unittest import mock

from invoke import __version__ as invoke_version
import pytest

from invoke_release.tasks import version
from invoke_release.version import __version__

from tests.unit import TaskBootstrap


@pytest.fixture(scope='function')
def module_being_tested() -> str:
    return 'invoke_release.tasks.version_task'


def test_not_configured(task_bootstrap: TaskBootstrap) -> None:
    task_bootstrap.config.is_configured = False
    task_bootstrap.io.error_output_exit.side_effect = SystemExit

    with pytest.raises(SystemExit):
        version.body('', verbose=True)

    task_bootstrap.io_constructor.assert_called_once_with(True)
    task_bootstrap.io.error_output_exit.assert_called_once_with(
        'Cannot `invoke version` before calling `invoke_release.config.config.configure`.',
    )


def test_no_gpg_no_errors(task_bootstrap: TaskBootstrap) -> None:
    task_bootstrap.config.is_configured = True
    task_bootstrap.config.module_name = 'special_library'
    task_bootstrap.config.display_name = 'Our Special Library'
    task_bootstrap.config.release_message_template = 'Released Our Special Library version {}'
    task_bootstrap.config.root_directory = '/path/to/special_library'
    task_bootstrap.config.version_file_name = '/path/to/special_library/special_library/version.py'
    task_bootstrap.config.changelog_file_name = '/path/to/special_library/CHANGELOG.txt'
    task_bootstrap.config.gpg_command = None
    task_bootstrap.config.tty = None
    task_bootstrap.config.get_file_existence_errors.return_value = []
    task_bootstrap.config.plugins = [mock.MagicMock()]
    task_bootstrap.config.plugins[0].error_check.return_value = []

    task_bootstrap.source.get_version.return_value = '8.9.3'
    task_bootstrap.source.get_branch_name.return_value = '7.x.x'

    with mock.patch('invoke_release.tasks.version_task.read_project_version') as mock_read_project_version:
        mock_read_project_version.return_value = '7.1.3'
        version.body('', verbose=False)

    task_bootstrap.io_constructor.assert_called_once_with(False)
    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Python: {}', sys.version.split('\n')[0].strip()),
        mock.call('Source control: {}', '8.9.3'),
        mock.call('Invoke: {}', invoke_version),
        mock.call('Invoke Release: {}', __version__),
        mock.call('Detected Project: {} {}', 'Our Special Library', '7.1.3'),
        mock.call('Detected Git branch: {}', '7.x.x'),
        mock.call('Detected version file: {}', '/path/to/special_library/special_library/version.py'),
        mock.call('Detected changelog file: {}', '/path/to/special_library/CHANGELOG.txt'),
    ], any_order=False)
    task_bootstrap.io.verbose_output.assert_has_calls([
        mock.call("GPG: Not installed (won't be used)"),
        mock.call('TTY: None detected'),
        mock.call('Release commit message template: "{}"', 'Released Our Special Library version {}')
    ], any_order=False)


def test_with_gpg_and_errors(task_bootstrap: TaskBootstrap) -> None:
    task_bootstrap.config.is_configured = True
    task_bootstrap.config.module_name = 'special_library'
    task_bootstrap.config.display_name = 'Our Special Library'
    task_bootstrap.config.release_message_template = 'Released Our Special Library version {}'
    task_bootstrap.config.root_directory = '/path/to/special_library'
    task_bootstrap.config.version_file_name = '/path/to/special_library/special_library/version.py'
    task_bootstrap.config.changelog_file_name = '/path/to/special_library/CHANGELOG.txt'
    task_bootstrap.config.gpg_command = '/usr/sbin/gpg'
    task_bootstrap.config.tty = '/dev/ttys0006'
    task_bootstrap.config.get_file_existence_errors.return_value = [
        'Version file does not exist',
        'The changelog file is also broken',
    ]
    task_bootstrap.config.plugins = [mock.MagicMock()]
    task_bootstrap.config.plugins[0].error_check.return_value = ['A plugin error', 'Another plugin error']

    task_bootstrap.source.get_version.return_value = '8.9.3'
    task_bootstrap.source.get_branch_name.return_value = '7.x.x'

    with mock.patch('invoke_release.tasks.version_task.read_project_version') as mock_read_project_version, \
            mock.patch('invoke_release.tasks.version_task.subprocess.check_output') as mock_check_output:
        mock_read_project_version.side_effect = OSError("It's broke")
        mock_check_output.return_value = b"""gpg (GnuPG) 2.2.1
libgcrypt 1.8.2
Copyright (C) 2017 Free Software Foundation, Inc."""
        version.body('', verbose=True)

    task_bootstrap.io_constructor.assert_called_once_with(True)
    task_bootstrap.io.standard_output.assert_has_calls([
        mock.call('Python: {}', sys.version.split('\n')[0].strip()),
        mock.call('Source control: {}', '8.9.3'),
        mock.call('Invoke: {}', invoke_version),
        mock.call('Invoke Release: {}', __version__),
        mock.call(
            'Detected Project: {} {}',
            'Our Special Library',
            '[Error: Could not read version: OSError("It\'s broke")]',
        ),
        mock.call('Detected Git branch: {}', '7.x.x'),
        mock.call('Detected version file: {}', '/path/to/special_library/special_library/version.py'),
        mock.call('Detected changelog file: {}', '/path/to/special_library/CHANGELOG.txt'),
    ], any_order=False)
    task_bootstrap.io.verbose_output.assert_has_calls([
        mock.call("GPG ({}): {}", '/usr/sbin/gpg', 'gpg (GnuPG) 2.2.1'),
        mock.call('TTY: {}', '/dev/ttys0006'),
        mock.call('Release commit message template: "{}"', 'Released Our Special Library version {}')
    ], any_order=False)
    task_bootstrap.io.error_output.assert_has_calls([
        mock.call('Version file does not exist\nThe changelog file is also broken'),
        mock.call('A plugin error'),
        mock.call('Another plugin error'),
    ], any_order=True)

    mock_check_output.assert_called_once_with(['/usr/sbin/gpg', '--version'], stderr=subprocess.STDOUT)
