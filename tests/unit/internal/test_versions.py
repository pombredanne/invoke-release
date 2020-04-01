import os
import tempfile
from typing import cast
from unittest import mock

import pytest

from invoke_release.config import Configuration
from invoke_release.errors import VersionError
from invoke_release.internal.context import TaskContext
from invoke_release.internal.io import IOUtils
from invoke_release.internal.versions import (
    ReleaseCategory,
    read_project_version,
    suggest_version,
    update_version_file,
    validate_and_normalize_version,
)


def test_release_category_detect_from_changelog() -> None:
    assert ReleaseCategory.detect_from_changelog([
        '- [MINOR] Hello',
        '\t-[MAJOR] Goodbye',
        '[PATCH] Sweet',
    ]) == ReleaseCategory.MAJOR

    assert ReleaseCategory.detect_from_changelog([
        '- [PATCH] Hello',
        '\t-[MINOR] Goodbye',
        '[PATCH] Sweet',
    ]) == ReleaseCategory.MINOR

    assert ReleaseCategory.detect_from_changelog([
        '- [PATCH] Hello',
        '\t-[PATCH] Goodbye',
        '[MINOR] Sweet',
    ]) == ReleaseCategory.MINOR

    assert ReleaseCategory.detect_from_changelog([
        '- [PATCH] Hello',
        '\t-[PATCH] Goodbye',
        '[PATCH] Sweet',
    ]) == ReleaseCategory.PATCH

    assert ReleaseCategory.detect_from_changelog([
        '- [PATCH] Hello',
        '\t-[PATCH] Goodbye',
        '- Sweet',
    ]) is None


def test_suggest_version() -> None:
    assert suggest_version('1.0.2', ReleaseCategory.PATCH) == '1.0.3'
    assert suggest_version('3.4.0', ReleaseCategory.PATCH) == '3.4.1'
    assert suggest_version('3.4.5', ReleaseCategory.MINOR) == '3.5.0'
    assert suggest_version('1.9.1', ReleaseCategory.MINOR) == '1.10.0'
    assert suggest_version('3.4.5', ReleaseCategory.MAJOR) == '4.0.0'
    assert suggest_version('2.0.3', ReleaseCategory.MAJOR) == '3.0.0'


def test_validate_and_normalize_version() -> None:
    with pytest.raises(VersionError):
        validate_and_normalize_version('1.7.9', '1.9-not-valid', None)

    with pytest.raises(VersionError):
        validate_and_normalize_version('1.7.9', '1.8.0', '1.7.x')

    with pytest.raises(VersionError):
        validate_and_normalize_version('1.7.9', '2.0.0', '1.x.x')

    with pytest.raises(VersionError):
        validate_and_normalize_version('1.7.9', '1.7.8', None)

    with pytest.raises(VersionError):
        validate_and_normalize_version('2.0.1', '1.9.0', None)

    assert validate_and_normalize_version('1.7.9', '1.7.10', None) == ('1.7.10', [1, 7, 10], '-')
    assert validate_and_normalize_version('2.0.1', '2.1.0', '2.x.x') == ('2.1.0', [2, 1, 0], '-')
    assert validate_and_normalize_version('1.7.9', '1.7.10-b1', '1.7.x') == ('1.7.10-b1', [1, 7, 10, 'b1'], '-')
    assert validate_and_normalize_version(
        '1.7.9',
        '1.7.10.post2',
        '1.7.x',
    ) == ('1.7.10.post2', [1, 7, 10, 'post2'], '.')
    assert validate_and_normalize_version(
        '1.7.9',
        '1.7.10post2',
        '1.7.x',
    ) == ('1.7.10-post2', [1, 7, 10, 'post2'], '-')
    assert validate_and_normalize_version(
        '2.1.3',
        '2.2.0+eventbrite-0',
        None,
    ) == ('2.2.0+eventbrite-0', [2, 2, 0, 'eventbrite-0'], '+')


def test_update_version_file() -> None:
    mock_config = mock.MagicMock()
    mock_io = mock.MagicMock()
    context = TaskContext(cast(Configuration, mock_config), cast(IOUtils, mock_io))

    mock_config.use_version_text = True
    mock_config.version_file_name = '/foo/does/not/exist.txt'
    with pytest.raises(VersionError):
        update_version_file(context, '1.2.3', [1, 2, 3], '-')

    with tempfile.NamedTemporaryFile('wt', encoding='utf-8', suffix='version.txt') as tmp_file:
        mock_config.use_version_text = True
        mock_config.version_file_name = tmp_file.name
        update_version_file(context, '1.0.7', [1, 0, 7], '-')

        with open(tmp_file.name, 'rt', encoding='utf-8') as read:
            assert read.read() == '1.0.7'

    with tempfile.NamedTemporaryFile('wt', encoding='utf-8', suffix='1-version.py') as tmp_file:
        mock_config.use_version_text = False
        mock_config.version_file_name = tmp_file.name

        tmp_file.write('from __future__ import absolute_import, unicode_literals\n\n')
        tmp_file.write("__author__ = 'Nick Williams'\n")
        tmp_file.write("__license__ = 'Apache 2.0'\n")
        tmp_file.write("__version__ = '1.0.6'\n")
        tmp_file.flush()

        update_version_file(context, '1.0.7', [1, 0, 7], '-')

        with open(tmp_file.name, 'rt', encoding='utf-8') as read:
            assert read.read() == """from __future__ import absolute_import, unicode_literals

__author__ = 'Nick Williams'
__license__ = 'Apache 2.0'
__version_info__ = (1, 0, 7)
__version__ = '-'.join(filter(None, ['.'.join(map(str, __version_info__[:3])), (__version_info__[3:] or [None])[0]]))
"""

    with tempfile.NamedTemporaryFile('wt', encoding='utf-8', suffix='2-version.py') as tmp_file:
        mock_config.use_version_text = False
        mock_config.version_file_name = tmp_file.name

        tmp_file.write('from __future__ import absolute_import, unicode_literals\n\n')
        tmp_file.write("__author__ = 'Seth Elliott'\n")
        tmp_file.write("__license__ = 'MIT'\n")
        tmp_file.write("__version_info__ = (1, 0, 7)\n")
        tmp_file.write(
            "__version__ = '-'.join(filter(None, ['.'.join(map(str, __version_info__[:3])), "
            "(__version_info__[3:] or [None])[0]]))\n"
        )
        tmp_file.flush()

        update_version_file(context, '1.1.0+eventbrite-3', [1, 1, 0, 'eventbrite-3'], '+')

        with open(tmp_file.name, 'rt', encoding='utf-8') as read:
            assert read.read() == """from __future__ import absolute_import, unicode_literals

__author__ = 'Seth Elliott'
__license__ = 'MIT'
__version_info__ = (1, 1, 0, 'eventbrite-3')
__version__ = '+'.join(filter(None, ['.'.join(map(str, __version_info__[:3])), (__version_info__[3:] or [None])[0]]))
"""

    with tempfile.NamedTemporaryFile('wt', encoding='utf-8', suffix='3-version.py') as tmp_file:
        mock_config.use_version_text = False
        mock_config.version_file_name = tmp_file.name

        tmp_file.write('from __future__ import absolute_import, unicode_literals\n\n')
        tmp_file.write("__author__ = 'Seth Elliott'\n")
        tmp_file.write("__license__ = 'MIT'\n")
        tmp_file.write(
            "__version__ = '-'.join(filter(None, ['.'.join(map(str, __version_info__[:3])), "
            "(__version_info__[3:] or [None])[0]]))\n"
        )
        tmp_file.write("__version_info__ = (1, 0, 7)\n")
        tmp_file.flush()

        update_version_file(context, '1.1.0+eventbrite-3', [1, 1, 0, 'eventbrite-3'], '+')

        with open(tmp_file.name, 'rt', encoding='utf-8') as read:
            assert read.read() == """from __future__ import absolute_import, unicode_literals

__author__ = 'Seth Elliott'
__license__ = 'MIT'
__version_info__ = (1, 1, 0, 'eventbrite-3')
__version__ = '+'.join(filter(None, ['.'.join(map(str, __version_info__[:3])), (__version_info__[3:] or [None])[0]]))
"""


def test_read_project_version() -> None:
    with tempfile.NamedTemporaryFile('wt', encoding='utf-8', suffix='version.txt') as f:
        f.write('1.7.3\n')
        f.flush()

        assert read_project_version('tests.unit.internal.tmp_version', f.name, False) == '1.7.3'

        f.seek(0)
        f.write('4.7.10+eventbrite-0')
        f.flush()

        assert read_project_version('tests.unit.internal.tmp_version', f.name, False) == '4.7.10+eventbrite-0'

    directory = os.path.dirname(__file__)
    tmp_version = os.path.join(directory, 'tmp_version.py')

    try:
        with open(tmp_version, 'wt', encoding='utf-8') as f:
            f.write("__version__ = '1.5.4'\n")
            f.flush()

            assert read_project_version('tests.unit.internal.tmp_version', tmp_version, False) == '1.5.4'

            f.seek(0)
            f.write("__version__ = '3.10.7+eventbrite-1'")
            f.flush()

            assert read_project_version('tests.unit.internal.tmp_version', tmp_version, False) == '1.5.4'
            assert read_project_version('tests.unit.internal.tmp_version', tmp_version, True) == '3.10.7+eventbrite-1'
    finally:
        os.unlink(tmp_version)
