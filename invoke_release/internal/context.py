import dataclasses
from typing import Optional

from invoke_release.config import Configuration
from invoke_release.internal.io import IOUtils


__all__ = (
    'TaskContext',
)


@dataclasses.dataclass
class TaskContext:
    config: Configuration
    io: IOUtils
    use_gpg: bool = False
    gpg_alternate_id: Optional[str] = None
