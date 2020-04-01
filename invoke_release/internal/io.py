from enum import Enum
import os
import sys
from typing import (
    IO,
    Any,
    List,
    NoReturn,
)


__all__ = (
    'Color',
    'ErrorStreamWrapper',
    'IOUtils',
)


class Color(Enum):
    GREEN_BOLD = '\x1b[32;1m'
    RED_STANDARD = '\x1b[31m'
    RED_BOLD = '\x1b[31;1m'
    GRAY_LIGHT = '\x1b[38;5;242m'
    WHITE = '\x1b[37;1m'
    DEFAULT = '\x1b[0m'


class ErrorStreamWrapper:
    def __init__(self, wrapped: IO[str]) -> None:
        self._wrapped = wrapped

    def write(self, err: str) -> None:
        self._wrapped.write(f'{Color.RED_STANDARD.value}{err}{Color.DEFAULT.value}')

    def writelines(self, lines: List[str]) -> None:
        self._wrapped.write(Color.RED_STANDARD.value)
        self._wrapped.writelines(lines)
        self._wrapped.write(Color.DEFAULT.value)

    def __getattribute__(self, item: str) -> Any:
        try:
            return super().__getattribute__(item)
        except AttributeError:
            return getattr(self._wrapped, item)

    @classmethod
    def wrap_globally(cls) -> None:
        if not isinstance(sys.stderr, cls):
            # Do not double-wrap
            sys.stderr = cls(sys.stderr)  # type: ignore

    @classmethod
    def unwrap_globally(cls) -> None:
        if isinstance(sys.stderr, cls):
            sys.stderr = sys.stderr._wrapped  # type: ignore


class IOUtils:
    def __init__(self, verbose: bool = False, output: IO[str] = sys.stdout) -> None:
        self._output = output
        self._output_is_tty = self._output.isatty()
        self._verbose = verbose

    def print_output(self, color: Color, message: str, *args: Any, **kwargs: Any) -> None:
        if self._output_is_tty:
            self._output.write(f'{color.value}{message.format(*args, **kwargs)}{Color.DEFAULT.value}')
        else:
            self._output.write(message.format(*args, **kwargs))
        self._output.flush()

    def standard_output(self, message: str, *args: Any, **kwargs: Any) -> None:
        self.print_output(Color.GREEN_BOLD, message + '\n', *args, **kwargs)

    def prompt(self, message: str, *args: Any, **kwargs: Any) -> str:
        self.print_output(Color.WHITE, message + ' ', *args, **kwargs)
        # noinspection PyCompatibility
        response = input()
        if response:
            return response.strip()
        return ''

    def error_output(self, message: str, *args: Any, **kwargs: Any) -> None:
        self.print_output(Color.RED_BOLD, ''.join(('ERROR: ', message, '\n')), *args, **kwargs)

    def error_output_exit(self, message: str, *args: Any, **kwargs: Any) -> NoReturn:
        self.error_output(message, *args, **kwargs)
        sys.exit(1)

    def verbose_output(self, message: str, *args: Any, **kwargs: Any) -> None:
        if self._verbose:
            self.print_output(Color.GRAY_LIGHT, ''.join(('DEBUG: ', message, '\n')), *args, **kwargs)

    @staticmethod
    def case_sensitive_regular_file_exists(filename: str) -> bool:
        if not os.path.isfile(filename):
            # Short circuit
            return False
        directory, filename = os.path.split(filename)
        return filename in os.listdir(directory)
