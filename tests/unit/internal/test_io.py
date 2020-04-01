from io import StringIO
import sys
import tempfile
from unittest import mock

import pytest

from invoke_release.internal.io import (
    Color,
    ErrorStreamWrapper,
    IOUtils,
)


def test_error_stream_wrapper_wrap_globally() -> None:
    original_stdout = sys.stdout
    original_stderr = sys.stderr

    ErrorStreamWrapper.wrap_globally()

    assert sys.stdout is original_stdout
    assert sys.stderr is not original_stderr
    assert isinstance(sys.stderr, ErrorStreamWrapper)
    assert sys.stderr._wrapped == original_stderr

    ErrorStreamWrapper.wrap_globally()

    assert sys.stdout is original_stdout
    assert sys.stderr is not original_stderr
    assert isinstance(sys.stderr, ErrorStreamWrapper)
    # noinspection PyProtectedMember
    assert sys.stderr._wrapped == original_stderr

    sys.stderr.write('Test a single line\n')
    sys.stderr.writelines(['Test multiple lines\n', 'Yes, multiple lines\n'])
    sys.stderr.flush()

    ErrorStreamWrapper.unwrap_globally()

    assert sys.stdout is original_stdout
    assert sys.stderr is original_stderr

    ErrorStreamWrapper.unwrap_globally()

    assert sys.stdout is original_stdout
    assert sys.stderr is original_stderr


def test_error_stream_wrapper_behavior() -> None:
    string = StringIO()
    wrapper = ErrorStreamWrapper(string)

    assert string.getvalue() == ''

    wrapper.write('Hello, world!\n')
    wrapper.flush()
    assert string.getvalue() == f'{Color.RED_STANDARD.value}Hello, world!\n{Color.DEFAULT.value}'

    wrapper.writelines(['Goodnight, moon.\n', 'Goodnight, Mars.\n'])
    assert string.getvalue() == f"""{Color.RED_STANDARD.value}Hello, world!
{Color.DEFAULT.value}{Color.RED_STANDARD.value}Goodnight, moon.
Goodnight, Mars.
{Color.DEFAULT.value}"""


def test_io_utils_not_a_tty() -> None:
    string = StringIO()
    io = IOUtils(False, string)

    assert string.getvalue() == ''

    io.standard_output('This is a standard output message with green color.')
    assert string.getvalue() == 'This is a standard output message with green color.\n'
    string.truncate(0)
    string.seek(0)
    assert string.getvalue() == ''

    io.error_output('This is error output, which will be red and bold.')
    assert string.getvalue() == 'ERROR: This is error output, which will be red and bold.\n'
    string.truncate(0)
    string.seek(0)
    assert string.getvalue() == ''

    with pytest.raises(SystemExit) as context:
        io.error_output_exit('This is red, bold error output that also results in an exit.')
    assert string.getvalue() == 'ERROR: This is red, bold error output that also results in an exit.\n'
    assert isinstance(context.value, SystemExit)
    assert context.value.code == 1
    string.truncate(0)
    string.seek(0)
    assert string.getvalue() == ''

    io.verbose_output('This will not appear because verbosity is disabled.')
    assert string.getvalue() == ''

    with mock.patch('invoke_release.internal.io.input') as mock_input:
        mock_input.return_value = None
        assert io.prompt('This is the first prompt, which should be white and will not be answered:') == ''
        assert string.getvalue() == 'This is the first prompt, which should be white and will not be answered: '
        mock_input.assert_called_once_with()
        string.truncate(0)
        string.seek(0)

    with mock.patch('invoke_release.internal.io.input') as mock_input:
        mock_input.return_value = 'Hello world \n'
        assert io.prompt('This second prompt will be answered:') == 'Hello world'
        assert string.getvalue() == 'This second prompt will be answered: '
        mock_input.assert_called_once_with()
        string.truncate(0)
        string.seek(0)

    io = IOUtils(True, string)

    assert string.getvalue() == ''

    io.verbose_output('Now the verbose output should appear, light and gray.')
    assert string.getvalue() == 'DEBUG: Now the verbose output should appear, light and gray.\n'


def test_io_utils_is_a_tty() -> None:
    string = StringIO()
    string.isatty = lambda: True  # type: ignore

    io = IOUtils(False, string)

    assert string.getvalue() == ''

    io.standard_output('This is a standard output message with green color.')
    assert string.getvalue() == (
        f'{Color.GREEN_BOLD.value}This is a standard output message with green color.\n{Color.DEFAULT.value}'
    )
    string.truncate(0)
    string.seek(0)
    assert string.getvalue() == ''

    io.error_output('This is error output, which will be red and bold.')
    assert string.getvalue() == (
        f'{Color.RED_BOLD.value}ERROR: This is error output, which will be red and bold.\n{Color.DEFAULT.value}'
    )
    string.truncate(0)
    string.seek(0)
    assert string.getvalue() == ''

    with pytest.raises(SystemExit) as context:
        io.error_output_exit('This is red, bold error output that also results in an exit.')
    assert string.getvalue() == (
        f'{Color.RED_BOLD.value}ERROR: This is red, bold error output that also results in an '
        f'exit.\n{Color.DEFAULT.value}'
    )
    assert isinstance(context.value, SystemExit)
    assert context.value.code == 1
    string.truncate(0)
    string.seek(0)
    assert string.getvalue() == ''

    io.verbose_output('This will not appear because verbosity is disabled.')
    assert string.getvalue() == ''

    with mock.patch('invoke_release.internal.io.input') as mock_input:
        mock_input.return_value = None
        assert io.prompt('This is the first prompt, which should be white and will not be answered:') == ''
        assert string.getvalue() == (
            f'{Color.WHITE.value}This is the first prompt, which should be white and will not be '
            f'answered: {Color.DEFAULT.value}'
        )
        mock_input.assert_called_once_with()
        string.truncate(0)
        string.seek(0)

    with mock.patch('invoke_release.internal.io.input') as mock_input:
        mock_input.return_value = 'Hello world \n'
        assert io.prompt('This second prompt will be answered:') == 'Hello world'
        assert string.getvalue() == f'{Color.WHITE.value}This second prompt will be answered: {Color.DEFAULT.value}'
        mock_input.assert_called_once_with()
        string.truncate(0)
        string.seek(0)

    io = IOUtils(True, string)

    assert string.getvalue() == ''

    io.verbose_output('Now the verbose output should appear, light and gray.')
    assert string.getvalue() == (
        f'{Color.GRAY_LIGHT.value}DEBUG: Now the verbose output should appear, light and gray.\n{Color.DEFAULT.value}'
    )


def test_case_sensitive_regular_file_exists() -> None:
    assert IOUtils.case_sensitive_regular_file_exists('/path/to/non-existent/file.txt') is False

    with tempfile.NamedTemporaryFile('wt', encoding='utf-8', suffix='test_case_sensitive_regular_file_exists.txt') as f:
        f.write('foo')
        f.flush()

        assert IOUtils.case_sensitive_regular_file_exists(f.name) is True
        assert IOUtils.case_sensitive_regular_file_exists(f.name.replace(
            'test_case_sensitive_regular_file_exists.txt',
            'Test_Case_Sensitive_Regular_File_Exists.Txt',
        )) is False
