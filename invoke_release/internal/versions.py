from __future__ import annotations

from enum import Enum
import importlib
import re
from typing import (
    List,
    Optional,
    Tuple,
    Union,
    cast,
)

from pkg_resources import parse_version

from invoke_release.errors import VersionError
from invoke_release.internal.context import TaskContext
from invoke_release.internal.io import IOUtils


__all__ = (
    'ReleaseCategory',
    'read_project_version',
    'suggest_version',
    'update_version_file',
    'validate_and_normalize_version',
)


RE_VERSION_SUFFIX_RAW = r'([a-zA-Z\d.+-]*[a-zA-Z\d]+)?$'
RE_STANDARD_VERSION = re.compile(r'^\d+\.\d+\.\d+' + RE_VERSION_SUFFIX_RAW)
RE_SPLIT_AFTER_DIGITS = re.compile(r'(\d+)')

VERSION_INFO_VARIABLE_TEMPLATE = '__version_info__ = {}'
VERSION_VARIABLE_TEMPLATE = (
    "__version__ = '{}'.join(filter(None, ['.'.join(map(str, __version_info__[:3])), "
    "(__version_info__[3:] or [None])[0]]))"
)


class ReleaseCategory(Enum):
    MAJOR = 'MAJOR'
    MINOR = 'MINOR'
    PATCH = 'PATCH'

    @staticmethod
    def detect_from_changelog(changelog: List[str]) -> Optional[ReleaseCategory]:
        untagged_commit_present = False
        patch_commit_present = False
        minor_commit_present = False

        for line in changelog:
            line = line.strip(' \t\n-[]')
            if line.startswith(ReleaseCategory.MAJOR.value):
                return ReleaseCategory.MAJOR
            if line.startswith(ReleaseCategory.MINOR.value):
                minor_commit_present = True
            elif line.startswith(ReleaseCategory.PATCH.value):
                patch_commit_present = True
            else:
                untagged_commit_present = True

        version: Optional[ReleaseCategory] = ReleaseCategory.PATCH if patch_commit_present else None
        version = ReleaseCategory.MINOR if minor_commit_present else version

        return version if not untagged_commit_present else None


def suggest_version(current_version: str, release_category: ReleaseCategory) -> str:
    version_info: Tuple[int, int, int] = cast(
        Tuple[int, int, int],
        tuple(map(int, current_version.split('-')[0].split('+')[0].split('.')[:3])),
    )

    if release_category is ReleaseCategory.PATCH:
        # If this is a patch release, recommend the next patch version
        version_info = (version_info[0], version_info[1], version_info[2] + 1)
    elif release_category is ReleaseCategory.MINOR or version_info[0] == 0:
        # If this is a minor release, or if the major version is 0 and this is a major release, recommend the next
        # minor version
        version_info = (version_info[0], version_info[1] + 1, 0)
    else:
        version_info = (version_info[0] + 1, 0, 0)

    return '.'.join(map(str, version_info))


def validate_and_normalize_version(
    current_version: str,
    new_version: str,
    branch: Optional[str],
) -> Tuple[str, List[Union[str, int]], str]:
    if branch:
        version_re = re.compile(
            r'^' + branch.replace('.x', r'.\d+').replace('.', r'\.') + RE_VERSION_SUFFIX_RAW,
        )
    else:
        version_re = RE_STANDARD_VERSION

    if not version_re.match(new_version):
        raise VersionError(
            'Invalid version specified: {version}. Must match "{regex}".'.format(
                version=new_version,
                regex=version_re.pattern,
            ),
        )

    # Deconstruct and reconstruct the version, to make sure it is consistent everywhere
    version_parts = new_version.split('.', 2)
    end_parts = list(filter(None, RE_SPLIT_AFTER_DIGITS.split(version_parts[2], 1)))
    version_separator = '-'
    if len(end_parts) > 1:
        version_info: List[Union[str, int]] = [
            int(version_parts[0]),
            int(version_parts[1]),
            int(end_parts[0]),
            end_parts[1].strip(' .-_+'),
        ]
        if end_parts[1][0] in ('-', '+', '.'):
            version_separator = end_parts[1][0]
    else:
        version_info = list(map(int, version_parts))
    new_version = version_separator.join(
        filter(None, ['.'.join(map(str, version_info[:3])), (version_info[3:] or [None])[0]])  # type: ignore
    )  # This must match the code in VERSION_VARIABLE_TEMPLATE at the top of this file

    if not (parse_version(new_version) > parse_version(current_version)):
        raise VersionError(
            'New version number {new_version} is not greater than current version {current_version}.'.format(
                new_version=new_version,
                current_version=current_version,
            ),
        )

    return new_version, version_info, version_separator


def update_version_file(
    context: TaskContext,
    version: str,
    version_info: List[Union[str, int]],
    version_separator: str,
) -> None:
    context.io.verbose_output('Writing version to {}...', context.config.version_file_name)

    if not IOUtils.case_sensitive_regular_file_exists(context.config.version_file_name):
        raise VersionError(
            'Failed to find version file: {}. File names are case sensitive!'.format(context.config.version_file_name),
        )

    if context.config.use_version_text:
        with open(context.config.version_file_name, 'wt', encoding='utf8') as version_write:
            version_write.write(version)

        context.io.verbose_output('Finished writing to {}.', context.config.version_file_name)
    else:
        version_info_line = VERSION_INFO_VARIABLE_TEMPLATE.format(tuple(version_info))
        version_line = VERSION_VARIABLE_TEMPLATE.format(version_separator)

        with open(context.config.version_file_name, 'rt', encoding='utf8') as version_read:
            output = []
            version_info_written = False
            for line in version_read:
                if line.startswith('__version_info__'):
                    if not version_info_written:
                        output.append(version_info_line)
                    version_info_written = True
                elif line.startswith('__version__'):
                    if not version_info_written:
                        output.append(version_info_line)
                        version_info_written = True
                    output.append(version_line)
                else:
                    output.append(line.rstrip())

        with open(context.config.version_file_name, 'wt', encoding='utf8') as version_write:
            for line in output:
                version_write.write(line + '\n')

        context.io.verbose_output('Finished writing to {}.version.', context.config.module_name)


def read_project_version(module_name: str, version_file_name: str, reload: bool = False) -> str:
    if version_file_name.endswith('.txt'):
        with open(version_file_name, 'rt', encoding='utf8') as version_txt:
            return version_txt.read().strip()

    module = importlib.import_module(module_name)
    if reload:
        module = importlib.reload(module)
    return module.__version__  # type: ignore
