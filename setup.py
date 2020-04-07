import sys

from setuptools import (
    find_packages,
    setup,
)

from invoke_release.version import __version__


def readme() -> str:
    with open('README.rst', 'rt', encoding='utf8') as f:
        return f.read()


tests_require = [
    'flake8~=3.7',
    'mypy~=0.770',
    'pytest~=5.4',
    'pytest-cov~=2.8',
]


setup(
    name='invoke-release',
    version=__version__,
    author='Eventbrite, Inc.',
    author_email='opensource@eventbrite.com',
    description='Easy Python Releases',
    long_description=readme(),
    url='https://github.com/eventbrite/invoke-release',
    packages=list(map(str, find_packages(include=['invoke_release', 'invoke_release.*']))),
    package_data={
        str('invoke_release'): [str('py.typed')],  # PEP 561,
    },
    zip_safe=False,  # PEP 561
    include_package_data=True,
    python_requires='>=3.7',
    install_requires=[
        'invoke~=1.4',
        'setuptools>=46.1.3',
    ],
    setup_requires=['pytest-runner'] if {'pytest', 'test', 'ptr'}.intersection(sys.argv) else [],
    tests_require=tests_require,
    extras_require={
        'testing': tests_require,
        'docs': ['sphinx~=2.2'],
    },
    test_suite='tests',
    license='Apache 2.0',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Topic :: Software Development',
        'Topic :: Software Development :: User Interfaces',
        'Topic :: Software Development :: Version Control',
        'Topic :: Software Development :: Version Control :: Git',
        'Topic :: Security :: Cryptography',
        'Topic :: Utilities',
    ],
    project_urls={
        'Documentation': 'https://invoke-release.readthedocs.io',
        'Issues': 'https://github.com/eventbrite/invoke-release/issues',
        'CI': 'https://travis-ci.org/eventbrite/invoke-release/',
    },
)
