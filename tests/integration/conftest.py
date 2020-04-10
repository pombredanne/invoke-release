import os
import pathlib
import re
import subprocess
import sys
import tempfile
from typing import (
    Generator,
    List,
    Optional,
)

import pytest

from tests import (
    mkdir,
    write_file,
)
from tests.integration import GpgSetup


@pytest.fixture(scope='module')
def remote_git_repo() -> Generator[str, None, None]:
    with tempfile.TemporaryDirectory(suffix='remote') as directory:
        directory = str(pathlib.Path(directory).resolve().absolute())  # get rid of symlinks, if applicable

        mkdir(directory, 'special_library.git')
        directory = os.path.join(directory, 'special_library.git')

        subprocess.check_call(['git', 'init', '--bare'], cwd=directory, stdout=sys.stdout, stderr=sys.stderr)

        yield directory

        sys.stderr.write("Cleaning up 'remote' repository\n")
        sys.stderr.flush()


@pytest.fixture(scope='module')
def local_git_repo(remote_git_repo: str) -> Generator[str, None, None]:
    with tempfile.TemporaryDirectory(suffix='local') as directory:
        directory = str(pathlib.Path(directory).resolve().absolute())  # get rid of symlinks, if applicable

        subprocess.check_call(
            ['git', 'clone', f'file://{remote_git_repo}'],
            cwd=directory,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )

        directory = os.path.join(directory, 'special_library')

        subprocess.check_call(
            ['git', 'config', '--local', 'user.email', 'nicholas@example.com'],
            cwd=directory,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )

        subprocess.check_call(
            ['git', 'config', '--local', 'user.name', 'Nick Sample'],
            cwd=directory,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )

        mkdir(directory, 'special_library')
        write_file(directory, 'CHANGELOG.rst', 'Changelog\n=========\n')
        write_file(directory, 'special_library/__init__.py', 'from special_library.version import __version__\n')
        write_file(directory, 'special_library/version.py', "__version__ = '1.2.3'")

        subprocess.check_call(['git', 'add', '-A'], cwd=directory, stdout=sys.stdout, stderr=sys.stderr)
        subprocess.check_call(
            ['git', 'commit', '-m', 'Initial commit'],
            cwd=directory,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
        subprocess.check_call(
            ['git', 'push', 'origin', 'master:master'],
            cwd=directory,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )

        yield directory

        sys.stderr.write('Cleaning up local repository clone\n')
        sys.stderr.flush()


GPG_RE = re.compile('gpg: key (?P<key_id>[0-9A-F]{8,32}) ')


gpg1: Optional[str] = None
gpg2: Optional[str] = None
try:
    gpg1 = subprocess.check_output(['which', 'gpg1']).decode('utf8').strip()
except subprocess.CalledProcessError:
    try:
        gpg1 = subprocess.check_output(['which', 'gpg']).decode('utf8').strip()
    except subprocess.CalledProcessError:
        pass
try:
    gpg2 = subprocess.check_output(['which', 'gpg2']).decode('utf8').strip()
except subprocess.CalledProcessError:
    try:
        gpg2 = subprocess.check_output(['which', 'gpg']).decode('utf8').strip()
    except subprocess.CalledProcessError:
        pass

if not gpg1 and not gpg2:
    raise AssertionError(
        'Invoke Release integration tests cannot run unless the system has GnuPG installed. Please install either '
        'GnuPGv1 or GnuPGv2 or, for better test coverage, both. To skip integration tests, run `pytest tests/unit`.'
    )

if gpg1 and gpg2:
    gpg1_version = subprocess.check_output(
        [gpg1, '--version'],
        stderr=subprocess.STDOUT,
    ).decode('utf-8').split('\n')[0].strip()
    gpg2_version = subprocess.check_output(
        [gpg2, '--version'],
        stderr=subprocess.STDOUT,
    ).decode('utf-8').split('\n')[0].strip()
    if gpg1_version == gpg2_version:  # gpg and gpg2 are aliases, so we only need one of them
        gpg2 = None

gpg_commands: List[str] = []
if gpg1:
    gpg_commands.append(gpg1)
if gpg2:
    gpg_commands.append(gpg2)


@pytest.fixture(scope='module', params=gpg_commands)
def gpg_setup(request) -> Generator[GpgSetup, None, None]:
    """
    Creates two GPG keys, one matching the Git committer email for the local repo above, and yields a tuple containing
    the temporary GNUPGHOME directory and the key ID for the key not matching the committer email.
    """
    with tempfile.TemporaryDirectory(suffix='gpg_home') as directory:
        directory = str(pathlib.Path(directory).resolve().absolute())  # get rid of symlinks, if applicable

        gpg: str = request.param

        subprocess.check_call(
            [gpg, '--version'],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )

        write_file(directory, 'gen-key1.instruct', """%echo Generating first key
Key-Type: rsa
Key-Usage: sign
Subkey-Type: rsa
Subkey-Usage: encrypt
Key-Length: 2048
Name-Real: Nick Sample
Name-Email: nicholas@example.com
Expire-Date: 1d
%no-protection
%no-ask-passphrase
%commit
%echo Done
""")
        write_file(directory, 'gen-key2.instruct', """%echo Generating second key
Key-Type: rsa
Key-Usage: sign
Subkey-Type: rsa
Subkey-Usage: encrypt
Key-Length: 2048
Name-Real: Seth Sample
Name-Email: seth@example.net
Expire-Date: 1d
%no-protection
%no-ask-passphrase
%commit
%echo Done""")

        try:
            output = subprocess.check_output(
                [gpg, '--gen-key', '--batch', os.path.join(directory, 'gen-key1.instruct')],
                stderr=subprocess.STDOUT,
                env=dict(os.environ, GNUPGHOME=directory),
            ).decode('utf-8')
        except subprocess.CalledProcessError as e:
            raise AssertionError(f'Failed to generate GPG key, exit code {e.returncode}, output: {e.output}')

        assert output, 'No output was captured from the GPG task'
        sys.stdout.write(output)
        sys.stdout.flush()

        key_created = GPG_RE.search(output)
        assert key_created, 'No key ID pattern match in the output'
        implicit_key = key_created.group('key_id')
        assert implicit_key, 'The spare key ID was not found in the output'

        try:
            output = subprocess.check_output(
                [gpg, '--gen-key', '--batch', os.path.join(directory, 'gen-key2.instruct')],
                stderr=subprocess.STDOUT,
                env=dict(os.environ, GNUPGHOME=directory),
            ).decode('utf-8')
        except subprocess.CalledProcessError as e:
            raise AssertionError(f'Failed to generate GPG key, exit code {e.returncode}, output: {e.output}')

        assert output, 'No output was captured from the GPG task'
        sys.stdout.write(output)
        sys.stdout.flush()

        key_created = GPG_RE.search(output)
        assert key_created, 'No key ID pattern match in the output'
        explicit_key = key_created.group('key_id')
        assert explicit_key, 'The spare key ID was not found in the output'

        subprocess.check_call(
            [gpg, '--list-keys'],
            stderr=subprocess.STDOUT,
            env=dict(os.environ, GNUPGHOME=directory),
        )

        yield GpgSetup(gpg, directory, implicit_key, explicit_key)

        sys.stderr.write('Cleaning up GPG keys\n')
        sys.stderr.flush()
