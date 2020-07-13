from __future__ import absolute_import, unicode_literals

import os
import sys

# Let's eat our own dog food and make sure the local version works for releasing itself
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'python')))
from invoke_release.tasks import *  # noqa: F403,E402
from invoke_release.plugins import (  # noqa: E402
    PatternReplaceVersionInFilesPlugin
)

configure_release_parameters(  # noqa: F405
    module_name='invoke_release',
    display_name='Invoke Release',
    python_directory='python',
    plugins=[
        PatternReplaceVersionInFilesPlugin('README.md')
    ]
)
