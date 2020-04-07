from typing import (
    Generator,
    cast,
)
from unittest import mock

import pytest

from invoke_release.config import Configuration
from invoke_release.internal.context import TaskContext
from invoke_release.internal.io import IOUtils
from invoke_release.internal.source_control.git import Git

from tests import InteractiveEditor


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


@pytest.fixture(scope='function')
def interactive_editor() -> Generator[InteractiveEditor, None, None]:
    with mock.patch('invoke_release.tasks.release_task.open_editor') as mock_open_editor:
        editor = InteractiveEditor()

        mock_open_editor.side_effect = editor.open_editor

        yield editor
