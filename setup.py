from __future__ import absolute_import, unicode_literals

from setuptools import (
    find_packages,
    setup,
)
import sys

sys.path.insert(0, 'python')

from invoke_release.version import __version__  # noqa: E402


# No dependencies to keep the library lightweight
install_requires = [
    'invoke~=0.22.0',
    'six~=1.11.0',
    'wheel~=0.31.1'
]

tests_require = [
    'pytest'
]


setup(
    name='invoke-release',
    version=__version__,
    author='Eventbrite, Inc.',
    author_email='opensource@eventbrite.com',
    description='Reusable Invoke-based command-line release tasks for libraries and services',
    long_description='''This provides some stock tasks built atop Invoke (http://www.pyinvoke.org/) to make releasing
your libraries and services, using Git tags, easier and more streamlined. Simply configure your project with a
`task.py` file per the instructions at https://github.com/eventbrite/invoke-release, and you can then perform robust
releases like so:

.. code-block:: bash

    $ invoke version
    $ invoke release
    $ invoke wheel
    $ invoke branch
    $ invoke rollback-release''',
    url='https://github.com/eventbrite/invoke-release',
    packages=list(map(str, find_packages(where='python', exclude=['*.tests', '*.tests.*', 'tests.*', 'tests']))),
    package_dir={
        str(''): str('python'),  # In Python 2, these can't be unicode; in Python 3, they must be
    },
    install_requires=install_requires,
    # Invalid classifier prevents accidental upload to PyPI
    setup_requires=['pytest-runner'],
    tests_require=tests_require,
    extras_require={
        'testing': tests_require,
    },
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Topic :: Software Development',
    ],
)
