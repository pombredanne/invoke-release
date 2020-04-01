import os
from typing import (
    List,
    Optional,
)

from invoke_release.plugins.base import AbstractInvokeReleasePlugin


__all__ = (
    'PatternReplaceVersionInFilesPlugin',
)


class PatternReplaceVersionInFilesPlugin(AbstractInvokeReleasePlugin):
    def __init__(self, *files_to_search: str) -> None:
        super().__init__(*files_to_search)

    def error_check(self, root_directory: str) -> Optional[List[str]]:
        file_errors = []
        for file_name in self.get_extra_files_to_commit(root_directory):
            if not os.path.exists(file_name):
                file_errors.append(
                    f'The file {file_name} was not found! {self.__class__.__name__} is not configured correctly!',
                )
        return file_errors

    def pre_commit(self, root_directory: str, old_version: str, new_version: str) -> None:
        for file_name in self.get_extra_files_to_commit(root_directory):
            contents = []
            with open(file_name, 'rt', encoding='utf8') as file_read:
                for line in file_read:
                    contents.append(line.rstrip().replace(old_version, new_version))
            with open(file_name, 'wt', encoding='utf8') as file_write:
                for line in contents:
                    file_write.write(line)
                    file_write.write('\n')
