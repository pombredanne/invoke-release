from typing import NamedTuple


GpgSetup = NamedTuple(
    'GpgSetup',
    (
        ('command', str),
        ('directory', str),
        ('implicit_key', str),
        ('explicit_key', str),
    ),
)
