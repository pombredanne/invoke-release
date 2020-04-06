import os
import sys
import tempfile
from typing import (
    List,
    Optional,
    Type,
    cast,
)
from unittest import mock

import pytest

from invoke_release.config import (
    Configuration,
    SourceControlType,
)
from invoke_release.errors import ConfigError
from invoke_release.internal.io import ErrorStreamWrapper
from invoke_release.internal.source_control.base import SourceControl
from invoke_release.plugins.base import AbstractInvokeReleasePlugin


def _mkdir(directory: str, sub_directory: str) -> None:
    os.mkdir(os.path.join(directory, sub_directory))


def _write(directory: str, file: str, contents: str) -> None:
    with open(os.path.join(directory, file), 'wt', encoding='utf-8') as f:
        f.write(contents)


class TestConfiguration:
    # noinspection PyAttributeOutsideInit
    def setup_method(self) -> None:
        self._tmp_dir: Optional[str] = None

    # noinspection PyMethodMayBeStatic
    def teardown_method(self) -> None:
        ErrorStreamWrapper.unwrap_globally()
        if self._tmp_dir and self._tmp_dir == sys.path[0]:
            sys.path.pop(0)

    def test_invalid_module_name(self) -> None:
        config = Configuration()

        with pytest.raises(ConfigError):
            config.configure(
                module_name='',
                display_name='My Cool Project',
            )

    def test_invalid_display_name(self) -> None:
        config = Configuration()

        with pytest.raises(ConfigError):
            config.configure(
                module_name='my_project',
                display_name='',
            )

    def test_standard_layout(self) -> None:
        mock_source_class = mock.MagicMock()

        config = Configuration()
        config._source_control_class = cast(Type[SourceControl], mock_source_class)

        with tempfile.TemporaryDirectory('test_standard_prefix') as directory:
            self._tmp_dir = directory

            _mkdir(directory, 'project_one')
            _write(directory, 'project_one/version.py', "__version__ = '1.3.7'\n")
            _write(directory, 'CHANGELOG.txt', 'Changelog\n=========\n')

            mock_source_class.get_root_directory.return_value = directory

            with mock.patch('invoke_release.config.get_gpg_command') as mock_get_gpg_command, \
                    mock.patch('invoke_release.config.get_tty') as mock_get_tty:
                mock_get_gpg_command.return_value = None
                mock_get_tty.return_value = None

                config.configure(
                    module_name='project_one',
                    display_name='Cool Project One',
                )

            assert config.is_configured is True
            assert config.module_name == 'project_one'
            assert config.display_name == 'Cool Project One'
            assert config.release_message_template == 'Released Cool Project One version {}'
            assert config.root_directory == directory
            assert config.use_pull_request is False
            assert config.use_tag is True
            assert config.master_branch == 'master'
            assert config.plugins == []
            assert config.changelog_file_name == os.path.join(directory, 'CHANGELOG.txt')
            assert config.use_version_text is False
            assert config.version_file_name == os.path.join(directory, 'project_one/version.py')
            assert config.gpg_command is None
            assert config.tty is None

            with pytest.raises(ConfigError):
                config.configure(
                    module_name='project_one',
                    display_name='Cool Project One',
                )

    def test_custom_layout(self) -> None:
        config = Configuration()

        with tempfile.TemporaryDirectory('test_standard_prefix') as directory:
            self._tmp_dir = os.path.join(directory, 'source/python')

            _mkdir(directory, 'source')
            _mkdir(directory, 'source/python')
            _mkdir(directory, 'source/python/other_two')
            _write(directory, 'source/python/other_two/version.txt', '3.1.5\n')
            _write(directory, 'CHANGELOG.rst', 'Changelog\n=========\n')

            mock_source_enum = mock.MagicMock()
            mock_source_enum.value.get_root_directory.return_value = directory

            plugins = [mock.MagicMock(), mock.MagicMock()]

            with mock.patch('invoke_release.config.get_gpg_command') as mock_get_gpg_command, \
                    mock.patch('invoke_release.config.get_tty') as mock_get_tty:
                mock_get_gpg_command.return_value = '/bin/gpg'
                mock_get_tty.return_value = '/dev/ttys0003'

                config.configure(
                    module_name='other_two',
                    display_name='Neat Project Two',
                    python_directory='source/python',
                    use_pull_request=True,
                    use_tag=False,
                    master_branch='development',
                    plugins=cast(List[AbstractInvokeReleasePlugin], plugins),
                    source_control=cast(SourceControlType, mock_source_enum),
                )

            assert config.is_configured is True
            assert config.module_name == 'other_two'
            assert config.display_name == 'Neat Project Two'
            assert config.release_message_template == 'Released Neat Project Two version {}'
            assert config.root_directory == directory
            assert config.use_pull_request is True
            assert config.use_tag is False
            assert config.master_branch == 'development'
            assert config.plugins == plugins
            assert config.changelog_file_name == os.path.join(directory, 'CHANGELOG.rst')
            assert config.use_version_text is True
            assert config.version_file_name == os.path.join(directory, 'source/python/other_two/version.txt')
            assert config.gpg_command == '/bin/gpg'
            assert config.tty == '/dev/ttys0003'
            assert config.source_control_class == mock_source_enum.value

            with pytest.raises(ConfigError):
                config.configure(
                    module_name='other_two',
                    display_name='Neat Project Two',
                    python_directory='source/python',
                    use_pull_request=True,
                    use_tag=False,
                    master_branch='development',
                    plugins=[],
                    source_control=cast(SourceControlType, mock_source_enum),
                )

    def test_other_changelog(self) -> None:
        mock_source_class = mock.MagicMock()

        config = Configuration()
        config._source_control_class = cast(Type[SourceControl], mock_source_class)
        with pytest.raises(ConfigError):
            config.ensure_configured('release')

        with tempfile.TemporaryDirectory('test_standard_prefix') as directory:
            self._tmp_dir = directory

            _mkdir(directory, 'project_one')
            _write(directory, 'project_one/version.py', "__version__ = '1.3.7'\n")
            _write(directory, 'CHANGELOG.md', 'Changelog\n=========\n')

            mock_source_class.get_root_directory.return_value = directory

            with mock.patch('invoke_release.config.get_gpg_command') as mock_get_gpg_command, \
                    mock.patch('invoke_release.config.get_tty') as mock_get_tty:
                mock_get_gpg_command.return_value = None
                mock_get_tty.return_value = None

                config.configure(
                    module_name='project_one',
                    display_name='Cool Project One',
                )

            assert config.is_configured is True
            assert config.module_name == 'project_one'
            assert config.display_name == 'Cool Project One'
            assert config.release_message_template == 'Released Cool Project One version {}'
            assert config.root_directory == directory
            assert config.use_pull_request is False
            assert config.use_tag is True
            assert config.master_branch == 'master'
            assert config.plugins == []
            assert config.changelog_file_name == os.path.join(directory, 'CHANGELOG.md')
            assert config.use_version_text is False
            assert config.version_file_name == os.path.join(directory, 'project_one/version.py')
            assert config.gpg_command is None
            assert config.tty is None

            assert config.get_file_existence_errors() == []
            config.ensure_configured('release')

            with pytest.raises(ConfigError):
                config.configure(
                    module_name='project_one',
                    display_name='Cool Project One',
                )

            os.unlink(os.path.join(directory, 'project_one/version.py'))

            errors = config.get_file_existence_errors()
            assert 'version.(py|txt)' in errors[0]
            assert len(errors) == 1
            with pytest.raises(ConfigError):
                config.ensure_configured('release')

    def test_no_changelog(self) -> None:
        mock_source_class = mock.MagicMock()

        config = Configuration()
        config._source_control_class = cast(Type[SourceControl], mock_source_class)

        with tempfile.TemporaryDirectory('test_standard_prefix') as directory:
            self._tmp_dir = directory

            _mkdir(directory, 'project_one')
            _write(directory, 'project_one/version.py', "__version__ = '1.3.7'\n")

            mock_source_class.get_root_directory.return_value = directory

            with mock.patch('invoke_release.config.get_gpg_command') as mock_get_gpg_command, \
                    mock.patch('invoke_release.config.get_tty') as mock_get_tty:
                mock_get_gpg_command.return_value = None
                mock_get_tty.return_value = None

                config.configure(
                    module_name='project_one',
                    display_name='Cool Project One',
                )

            assert config.is_configured is True
            assert config.module_name == 'project_one'
            assert config.display_name == 'Cool Project One'
            assert config.release_message_template == 'Released Cool Project One version {}'
            assert config.root_directory == directory
            assert config.use_pull_request is False
            assert config.use_tag is True
            assert config.master_branch == 'master'
            assert config.plugins == []
            assert config.changelog_file_name == os.path.join(directory, 'CHANGELOG.txt')
            assert config.use_version_text is False
            assert config.version_file_name == os.path.join(directory, 'project_one/version.py')
            assert config.gpg_command is None
            assert config.tty is None

            with pytest.raises(ConfigError):
                config.configure(
                    module_name='project_one',
                    display_name='Cool Project One',
                )

            config = Configuration()
            config._source_control_class = cast(Type[SourceControl], mock_source_class)
            config.configure(
                module_name='project_one',
                display_name='Cool Project One',
            )

            errors = config.get_file_existence_errors()
            assert 'CHANGELOG.(txt|md|rst)' in errors[0]
            assert len(errors) == 1
            with pytest.raises(ConfigError):
                config.ensure_configured('release')
