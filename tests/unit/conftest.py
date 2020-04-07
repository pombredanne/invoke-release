from typing import Generator
from unittest import mock

import pytest

from tests.unit import TaskBootstrap


@pytest.fixture(scope='function')
def task_bootstrap(module_being_tested: str) -> Generator[TaskBootstrap, None, None]:
    with mock.patch(f'{module_being_tested}.config') as mock_config, \
            mock.patch(f'{module_being_tested}.IOUtils') as mock_io:
        yield TaskBootstrap(
            mock_config,
            mock_io.return_value,
            mock_config.source_control_class.return_value,
            mock_io,
            mock_config.source_control_class,
        )
