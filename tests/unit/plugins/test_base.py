from typing import (
    List,
    Optional,
)

import pytest

from invoke_release.errors import ReleaseFailure
from invoke_release.plugins.base import (
    AbstractInvokeReleasePlugin,
    ReleaseStatus,
)


class SamplePlugin(AbstractInvokeReleasePlugin):
    def error_check(self, root_directory: str) -> Optional[List[str]]:
        return ['This is a really bad release', 'You really should not do this']


class TestAbstractInvokeReleasePlugin:
    def test_get_extra_files_to_commit(self) -> None:
        plugin = AbstractInvokeReleasePlugin('README.rst', 'docs/about.rst', 'docs/header.rst')
        assert list(plugin.get_extra_files_to_commit('/path/root')) == [
            '/path/root/README.rst',
            '/path/root/docs/about.rst',
            '/path/root/docs/header.rst',
        ]

    def test_error_check(self) -> None:
        plugin = AbstractInvokeReleasePlugin()
        assert plugin.error_check('/path/root') is None

    def test_pre_release(self) -> None:
        plugin = AbstractInvokeReleasePlugin()
        plugin.pre_release('/path/root', '1.2.3')

        plugin = SamplePlugin()
        with pytest.raises(ReleaseFailure) as context:
            plugin.pre_release('/path/root', '1.2.3')

        assert isinstance(context.value, ReleaseFailure)
        assert context.value.args[0].startswith('The SamplePlugin plugin generated the following errors:\n')
        assert 'This is a really bad release' in context.value.args[0]
        assert 'You really should not do this' in context.value.args[0]

    def test_pre_commit(self) -> None:
        plugin = AbstractInvokeReleasePlugin()
        plugin.pre_commit('/path/root', '1.2.3', '1.3.0')

    def test_pre_push(self) -> None:
        plugin = AbstractInvokeReleasePlugin()
        plugin.pre_push('/path/root', '1.2.3', '1.3.0')

    def test_post_release(self) -> None:
        plugin = AbstractInvokeReleasePlugin()
        plugin.post_release('/path/root', '1.2.3', '1.3.0', ReleaseStatus.NOT_PUSHED)

    def test_pre_rollback(self) -> None:
        plugin = AbstractInvokeReleasePlugin()
        plugin.pre_rollback('/path/root', '1.3.0')

    def test_post_rollback(self) -> None:
        plugin = AbstractInvokeReleasePlugin()
        plugin.post_rollback('/path/root', '1.3.0', '1.2.3')
