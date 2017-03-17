import os
import sys

# Let's eat our own dog food and make sure this works.
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'python')))
from invoke_release.tasks import *  # noqa
from invoke_release.plugins import (
    PatternReplaceVersionInFilesPlugin
)

configure_release_parameters(
    module_name='invoke_release',
    display_name='Eventbrite Command Line Release Tools ("Invoke Release")',
    python_directory='python',
    plugins=[
        PatternReplaceVersionInFilesPlugin('README.md')
    ]
)
