from setuptools import setup, find_packages
import os
import sys

sys.path.insert(0, 'python')

from invoke_release import __version__

packages = [x for x in find_packages('python') if '.tests' not in x]

# No dependencies to keep the library lightweight
install_requires = [
    'invoke>=0.13.0,<0.14.0',
    'wheel',
]

test_requirements = [
]

if sys.argv[-1] == 'tag':
    os.system("git tag -a {version} -m 'version {version}'".format(version=__version__))
    os.system('git push --tags')
    sys.exit()


setup(
    name='invoke_release',
    version=__version__,
    description='Reusable command-line release tasks for Eventbrite libraries and services.',
    packages=packages,
    package_dir={
        '': 'python',
    },
    install_requires=install_requires,
    author='Nick Williams',
    author_email='nwilliams@eventbrite.com',
    url='https://github.com/eventbrite/invoke-release',
    # Invalid classifier prevents accidental upload to PyPI
    classifiers=['Private :: Do Not Upload'],
    test_suite='tests',
    tests_require=test_requirements
)
