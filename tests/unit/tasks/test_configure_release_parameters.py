from unittest import mock
import warnings

# noinspection PyProtectedMember
from invoke_release.tasks import configure_release_parameters


def test_configure_release_parameters() -> None:
    with mock.patch('invoke_release.tasks.config') as mock_config, warnings.catch_warnings(record=True) as w:
        # noinspection PyDeprecation
        configure_release_parameters(module_name='pysoa', display_name='PySOA')

    mock_config.configure.assert_called_once_with(module_name='pysoa', display_name='PySOA')

    assert len(w) == 1
    issubclass(w[0].category, DeprecationWarning)
    assert '`configure_release_parameters` is deprecated' in str(w[0].message)
