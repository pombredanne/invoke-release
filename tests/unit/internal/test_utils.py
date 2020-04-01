import subprocess
from unittest import mock

from invoke_release.internal.utils import (
    get_gpg_command,
    get_tty,
    set_map,
)


def test_set_map() -> None:
    s = set_map(
        lambda x: x if x in (1, 2, 3) else (None if x == 6 else [x, x, x]),
        [1, 2, 3, 4, 5, 6]
    )
    assert isinstance(s, set)
    assert s == {1, 2, 3, 4, 5}


def test_get_gpg_command() -> None:
    with mock.patch('invoke_release.internal.utils.subprocess.check_output') as mock_check_output:
        mock_check_output.return_value = b'/path/to/gpg2'
        assert get_gpg_command() == '/path/to/gpg2'
        mock_check_output.assert_called_once_with(['which', 'gpg2'])

    with mock.patch('invoke_release.internal.utils.subprocess.check_output') as mock_check_output:
        mock_check_output.side_effect = (
            subprocess.CalledProcessError(1, ['which', 'gpg2']),
            b'/other/path/to/gpg1',
        )
        assert get_gpg_command() == '/other/path/to/gpg1'
        mock_check_output.assert_has_calls([mock.call(['which', 'gpg2']), mock.call(['which', 'gpg'])], any_order=False)

    with mock.patch('invoke_release.internal.utils.subprocess.check_output') as mock_check_output:
        mock_check_output.side_effect = (
            subprocess.CalledProcessError(1, ['which', 'gpg2']),
            subprocess.CalledProcessError(1, ['which', 'gpg']),
            b'/final/path/to/gpg1',
        )
        assert get_gpg_command() == '/final/path/to/gpg1'
        mock_check_output.assert_has_calls([
            mock.call(['which', 'gpg2']),
            mock.call(['which', 'gpg']),
            mock.call(['which', 'gpg1']),
        ], any_order=False)

    with mock.patch('invoke_release.internal.utils.subprocess.check_output') as mock_check_output:
        mock_check_output.side_effect = (
            subprocess.CalledProcessError(1, ['which', 'gpg2']),
            subprocess.CalledProcessError(1, ['which', 'gpg']),
            subprocess.CalledProcessError(1, ['which', 'gpg1']),
        )
        assert get_gpg_command() is None
        mock_check_output.assert_has_calls([
            mock.call(['which', 'gpg2']),
            mock.call(['which', 'gpg']),
            mock.call(['which', 'gpg1']),
        ], any_order=False)


def test_get_tty() -> None:
    with mock.patch('invoke_release.internal.utils.subprocess.check_output') as mock_check_output:
        mock_check_output.return_value = b'/dev/ttys0001'
        assert get_tty() == '/dev/ttys0001'
        mock_check_output.assert_called_once_with(['tty'])

    with mock.patch('invoke_release.internal.utils.subprocess.check_output') as mock_check_output:
        mock_check_output.side_effect = subprocess.CalledProcessError(1, ['tty'])
        assert get_tty() is None
        mock_check_output.assert_called_once_with(['tty'])
