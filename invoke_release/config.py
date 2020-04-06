from enum import Enum
import os
import re
import sys
from typing import (
    List,
    Optional,
    Type,
    cast,
)

from invoke_release.errors import ConfigError
from invoke_release.internal.io import (
    ErrorStreamWrapper,
    IOUtils,
)
from invoke_release.internal.source_control.base import SourceControl
from invoke_release.internal.source_control.git import Git
from invoke_release.internal.utils import (
    get_gpg_command,
    get_tty,
)
from invoke_release.plugins.base import AbstractInvokeReleasePlugin


__all__ = (
    'config',
    'Configuration',
    'SourceControlType',
)


RE_FILE_EXTENSION = re.compile(r'\.\w+$')


class SourceControlType(Enum):
    GIT = Git


class Configuration:
    def __init__(self):
        self._configured = False
        self._module_name: str = ''
        self._display_name: str = ''
        self._release_message_template: str = ''
        self._root_directory: str = ''
        self._changelog_file_name: str = ''
        self._use_version_text = False
        self._version_file_name: str = ''
        self._use_pull_request = False
        self._use_tag = True
        self._master_branch = 'master'
        self._plugins: List[AbstractInvokeReleasePlugin] = []
        self._source_control_class: Type[SourceControl] = Git
        self._gpg_command: Optional[str] = None
        self._tty: Optional[str] = None

    @property
    def is_configured(self):
        return self._configured

    def get_file_existence_errors(self) -> List[str]:
        errors: List[str] = []

        if not IOUtils.case_sensitive_regular_file_exists(self._version_file_name):
            errors.append(f"Version file {RE_FILE_EXTENSION.sub('.(py|txt)', self._version_file_name)} was not found!")

        if not IOUtils.case_sensitive_regular_file_exists(self._changelog_file_name):
            errors.append(
                f"Changelog file {RE_FILE_EXTENSION.sub('.(txt|md|rst)', self._changelog_file_name)} was not found!"
            )

        return errors

    def ensure_configured(self, command: str) -> None:
        if not self._configured:
            raise ConfigError(
                f'Cannot call `invoke {command}` before calling `invoke_release.config.config.configure`.',
            )

        errors = self.get_file_existence_errors()
        if errors:
            raise ConfigError(
                f'This project is not correctly configured to use `invoke {command}`! '
                f"(File names are case sensitive!) {' '.join(errors)}",
            )

    @property
    def module_name(self) -> str:
        return self._module_name

    @property
    def display_name(self) -> str:
        return self._display_name

    @property
    def release_message_template(self) -> str:
        return self._release_message_template

    @property
    def root_directory(self) -> str:
        return self._root_directory

    @property
    def changelog_file_name(self) -> str:
        return self._changelog_file_name

    @property
    def use_version_text(self) -> bool:
        return self._use_version_text

    @property
    def version_file_name(self) -> str:
        return self._version_file_name

    @property
    def use_pull_request(self) -> bool:
        return self._use_pull_request

    @property
    def use_tag(self) -> bool:
        return self._use_tag

    @property
    def master_branch(self) -> str:
        return self._master_branch

    @property
    def plugins(self) -> List[AbstractInvokeReleasePlugin]:
        return self._plugins

    @property
    def source_control_class(self) -> Type[SourceControl]:
        return self._source_control_class

    @property
    def gpg_command(self) -> Optional[str]:
        return self._gpg_command

    @property
    def tty(self) -> Optional[str]:
        return self._tty

    def configure(
        self,
        *,
        module_name: str,
        display_name: str,
        python_directory: Optional[str] = None,
        use_pull_request: bool = False,
        use_tag: bool = True,
        master_branch: str = 'master',
        plugins: Optional[List[AbstractInvokeReleasePlugin]] = None,
        source_control: SourceControlType = SourceControlType.GIT,
    ) -> None:
        ErrorStreamWrapper.wrap_globally()

        if self._configured:
            raise ConfigError('Cannot call `invoke_release.config.config.configure` more than once.')

        if module_name:
            module_name = module_name.strip()
        if not module_name:
            raise ConfigError('module_name is a required config parameter')

        if display_name:
            display_name = display_name.strip()
        if not display_name:
            raise ConfigError('display_name is a required config parameter')

        self._module_name = module_name
        self._display_name = display_name
        self._release_message_template = f'Released {self._display_name} version {{}}'
        self._use_pull_request = use_pull_request
        self._use_tag = use_tag
        self._master_branch = master_branch

        if plugins:
            self._plugins = plugins

        if source_control != SourceControlType.GIT:
            self._source_control_class = cast(Type[SourceControl], source_control.value)

        self._root_directory = os.path.normpath(self._source_control_class.get_root_directory())

        if python_directory:
            import_directory = os.path.normpath(os.path.join(self._root_directory, python_directory))
            version_file_prefix = os.path.join(self._root_directory, f'{python_directory}/{self._module_name}/version')
        else:
            import_directory = self._root_directory
            version_file_prefix = os.path.join(self._root_directory, f'{self._module_name}/version')

        changelog_file_prefix = os.path.join(self._root_directory, 'CHANGELOG')
        for extension in ('txt', 'rst', 'md'):
            file = f'{changelog_file_prefix}.{extension}'
            if IOUtils.case_sensitive_regular_file_exists(file):
                self._changelog_file_name = file
                break
        else:
            self._changelog_file_name = f'{changelog_file_prefix}.txt'

        if IOUtils.case_sensitive_regular_file_exists(f'{version_file_prefix}.txt'):
            self._use_version_text = True
            self._version_file_name = f'{version_file_prefix}.txt'
        else:
            self._version_file_name = f'{version_file_prefix}.py'

        if import_directory not in sys.path:
            sys.path.insert(0, import_directory)

        self._gpg_command = get_gpg_command()
        self._tty = get_tty()

        self._configured = True


config = Configuration()
