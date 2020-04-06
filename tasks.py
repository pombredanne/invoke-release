from invoke_release.config import config
from invoke_release.plugins.replace import PatternReplaceVersionInFilesPlugin
from invoke_release.tasks import *  # noqa: F401,F403


config.configure(
    module_name='invoke_release',
    display_name='Invoke Release',
    plugins=[
        PatternReplaceVersionInFilesPlugin('README.rst'),
    ],
)
