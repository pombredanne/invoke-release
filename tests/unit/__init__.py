from typing import NamedTuple
from unittest import mock


TaskBootstrap = NamedTuple(
    'TaskBootstrap',
    (
        ('config', mock.MagicMock),
        ('io', mock.MagicMock),
        ('source', mock.MagicMock),
        ('io_constructor', mock.MagicMock),
        ('source_constructor', mock.MagicMock),
    ),
)
