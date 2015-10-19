import sys

# Let's eat our own dog food and make sure this works.
sys.path.insert(0, 'python')
from invoke_release.tasks import *

configure_release_parameters(
    module_name='invoke_release',
    display_name='Eventbrite Command Line Release Tools ("Invoke Release")',
    python_directory='python'
)
