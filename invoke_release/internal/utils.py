import subprocess
from typing import (
    Any,
    Callable,
    Iterable,
    Optional,
    Set,
    TypeVar,
)


__all__ = (
    'get_gpg_command',
    'get_tty',
    'set_map',
)


_A = TypeVar('_A')


def set_map(map_function: Callable[[_A], Any], iterable: Iterable[_A]) -> Set[Any]:
    ret: Set[Any] = set()
    for i in iterable:
        r = map_function(i)
        if r:
            if getattr(r, '__iter__', None):
                ret.update(r)
            else:
                ret.add(r)
    return ret


def get_gpg_command() -> Optional[str]:
    try:
        return subprocess.check_output(['which', 'gpg2']).decode('utf8').strip()
    except subprocess.CalledProcessError:
        try:
            return subprocess.check_output(['which', 'gpg']).decode('utf8').strip()
        except subprocess.CalledProcessError:
            try:
                return subprocess.check_output(['which', 'gpg1']).decode('utf8').strip()
            except subprocess.CalledProcessError:
                return None


def get_tty() -> Optional[str]:
    try:
        return subprocess.check_output(['tty']).decode('utf8').strip()
    except subprocess.CalledProcessError:
        return None
