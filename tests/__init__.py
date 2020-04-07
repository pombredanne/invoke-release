import contextlib
import functools
import os
import subprocess
import threading
from typing import (
    Any,
    Callable,
    Dict,
    Generator,
    List,
    NamedTuple,
    Optional,
    Tuple,
    TypeVar,
    Union,
    cast,
)
from unittest import mock

from invoke.tasks import (
    Context,
    Task,
)

from invoke_release.errors import ReleaseExit


__all__ = (
    'InteractiveEditor',
    'InteractiveTester',
    'file_exists',
    'mkdir',
    'patch_popen_args',
    'popen_wrapper',
    'read_file',
    'write_file',
)


def write_file(directory: str, file: str, contents: str) -> None:
    with open(os.path.join(directory, file), 'wt', encoding='utf-8') as f:
        f.write(contents)


def read_file(directory: str, file: str) -> str:
    with open(os.path.join(directory, file), 'rt', encoding='utf-8') as f:
        return f.read()


def file_exists(directory: str, file: str) -> bool:
    return os.path.exists(os.path.join(directory, file))


def mkdir(directory: str, sub_directory: str) -> None:
    os.mkdir(os.path.join(directory, sub_directory))


_Popen = TypeVar('_Popen', bound=Callable[..., None])


def popen_wrapper(original_popen_init: _Popen, directory: str, environ: Optional[Dict[str, str]] = None) -> _Popen:
    # noinspection PyUnusedLocal
    @functools.wraps(original_popen_init)
    def wrapper(*args, cwd=None, env=None, **kwargs):
        if environ:
            env = env or dict(os.environ)
            env.update(environ)
        return original_popen_init(*args, cwd=directory, env=env, **kwargs)

    return cast(_Popen, wrapper)


@contextlib.contextmanager
def patch_popen_args(cwd: str, env: Optional[Dict[str, str]] = None) -> Generator[None, None, None]:
    original_popen_init = subprocess.Popen.__init__
    try:
        subprocess.Popen.__init__ = popen_wrapper(subprocess.Popen.__init__, cwd, env)  # type: ignore
        yield
    finally:
        subprocess.Popen.__init__ = original_popen_init  # type: ignore


class InteractiveEditor:
    def __init__(self):
        self._open_event = threading.Event()
        self._close_event = threading.Event()

        self._file_name: str = ''

    def open_editor(self, _, edit_file_name) -> None:
        self._file_name = edit_file_name
        self._open_event.set()
        self._close_event.wait()

    def wait_for_editor_open(self) -> str:
        self._open_event.wait(timeout=3)

        with open(self._file_name, 'rt', encoding='utf-8') as f:
            return f.read()

    def close_editor(self, save_contents: str) -> None:
        with open(self._file_name, 'wt', encoding='utf-8') as f:
            f.write(save_contents)

        self._close_event.set()


Prompt = NamedTuple(
    'Prompt',
    (
        ('message', str),
        ('args', Tuple[Any, ...]),
        ('kwargs', Dict[str, Any]),
    )
)


class InteractiveTester(threading.Thread):
    def __init__(
        self,
        io: mock.MagicMock,
        task: Union[Callable[..., Any], Task],
        other_mocks: Optional[List[mock.MagicMock]] = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        self.io = io
        self.task = task
        self.args = args
        self.kwargs = kwargs
        self.release_exit = False
        self.return_value: Any = None

        self._caller_flag = threading.Event()
        self._runner_flag = threading.Event()
        self._finished_flag = threading.Event()
        self._current_prompt: Optional[Prompt] = None
        self._current_response: Optional[str] = None

        self._other_mocks: List[mock.MagicMock] = other_mocks or []
        self._reset_mocks()

        super().__init__(daemon=True)

    def _reset_mocks(self) -> None:
        for other_mock in self._other_mocks:
            other_mock.reset_mock()
        self.io.reset_mock()
        self.io.prompt.side_effect = self._prompt

    def run(self) -> None:
        try:
            if isinstance(self.task, Task):
                self.task.body(cast(Context, mock.MagicMock()), *self.args, **self.kwargs)
            else:
                self.return_value = self.task(**self.kwargs)
        except ReleaseExit:
            self.release_exit = True
        except SystemExit:
            pass  # just exit the thread
        self._caller_flag.set()
        self._finished_flag.set()

    def _prompt(self, message: str, *args: Any, **kwargs: Any) -> str:
        self._current_prompt = Prompt(message, args, kwargs)
        self._runner_flag.clear()
        self._caller_flag.set()
        self._runner_flag.wait()
        assert self._current_response is not None
        try:
            return self._current_response
        finally:
            self._current_response = None

    def wait_for_prompt(self) -> Prompt:
        self._caller_flag.wait(timeout=3)
        assert self._current_prompt is not None
        try:
            return self._current_prompt
        finally:
            self._current_prompt = None

    def respond_to_prompt(self, response: str) -> None:
        self._reset_mocks()

        self._current_response = response
        self._caller_flag.clear()
        self._runner_flag.set()

    def wait_for_finish(self) -> None:
        self._finished_flag.wait(timeout=3)
