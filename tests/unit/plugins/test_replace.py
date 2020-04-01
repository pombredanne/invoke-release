import os
import tempfile

from invoke_release.plugins.replace import PatternReplaceVersionInFilesPlugin


class TestPatternReplaceVersionInFilesPlugin:
    def test_no_files(self):
        plugin = PatternReplaceVersionInFilesPlugin()
        assert plugin.error_check('/path/root') == []
        plugin.pre_commit('/path/root', '1.2.3', '1.3.0')

    def test_with_non_existent_files(self):
        plugin = PatternReplaceVersionInFilesPlugin('README.rst', 'docs/about.rst')
        assert plugin.error_check('/path/root') == [
            'The file /path/root/README.rst was not found! '
            'PatternReplaceVersionInFilesPlugin is not configured correctly!',
            'The file /path/root/docs/about.rst was not found! '
            'PatternReplaceVersionInFilesPlugin is not configured correctly!',
        ]

    def test_with_files(self):
        with tempfile.NamedTemporaryFile('wt', encoding='utf-8', suffix='README.rst') as f1, \
                tempfile.NamedTemporaryFile('wt', encoding='utf-8', suffix='docs-about.rst') as f2:
            directory = os.path.dirname(f1.name)
            name1 = f1.name.replace(f'{directory}/', '')
            name2 = f2.name.replace(f'{directory}/', '')

            f1.write('This is some info about the project whose version is 1.7.12. Comprehend?')
            f1.flush()
            f2.write('About this project\n==================\n\nProject Version: 1.7.12\n')
            f2.flush()

            plugin = PatternReplaceVersionInFilesPlugin(name1, name2)
            assert list(plugin.get_extra_files_to_commit(directory)) == [
                f1.name,
                f2.name,
            ]
            assert plugin.error_check(directory) == []

            plugin.pre_commit(directory, '1.7.12', '2.0.0')

            with open(f1.name, 'rt', encoding='utf-8') as f1b, \
                    open(f2.name, 'rt', encoding='utf-8') as f2b:
                assert f1b.read() == 'This is some info about the project whose version is 2.0.0. Comprehend?\n'
                assert f2b.read() == 'About this project\n==================\n\nProject Version: 2.0.0\n'
