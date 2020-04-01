from typing import cast
from unittest import mock

import pytest

from invoke_release.config import Configuration
from invoke_release.internal.context import TaskContext
from invoke_release.internal.io import IOUtils
from invoke_release.internal.source_control.git import Git


@pytest.fixture(scope='function')
def mock_config() -> mock.MagicMock:
    return mock.MagicMock()


@pytest.fixture(scope='function')
def mock_io() -> mock.MagicMock:
    return mock.MagicMock()


@pytest.fixture(scope='function')
def task_context(mock_config: mock.MagicMock, mock_io: mock.MagicMock) -> TaskContext:
    return TaskContext(cast(Configuration, mock_config), cast(IOUtils, mock_io))


@pytest.fixture(scope='function')
def git(task_context: TaskContext) -> Git:
    return Git(task_context)
