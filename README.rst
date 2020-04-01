Invoke Release - Easy Python Releases
=====================================

.. image:: https://readthedocs.org/projects/invoke-release/badge/
    :target: https://invoke-release.readthedocs.io

.. image:: https://pepy.tech/badge/invoke-release
    :target: https://pepy.tech/project/invoke-release

.. image:: https://img.shields.io/pypi/l/invoke-release.svg
    :target: https://pypi.python.org/pypi/invoke-release

.. image:: https://api.travis-ci.org/eventbrite/invoke-release.svg
    :target: https://travis-ci.org/eventbrite/invoke-release

.. image:: https://img.shields.io/pypi/v/invoke-release.svg
    :target: https://pypi.python.org/pypi/invoke-release

.. image:: https://img.shields.io/pypi/wheel/invoke-release.svg
    :target: https://pypi.python.org/pypi/invoke-release

.. image:: https://img.shields.io/pypi/pyversions/invoke-release.svg
    :target: https://pypi.python.org/pypi/invoke-release

**Invoke Release** is a set of command line tools that help software engineers release Python projects quickly, easily,
and in a consistent manner. It helps ensure that the version standards for your projects are the same across all of
your organization's projects, and minimizes the possible errors that can occur during a release. It uses Git for
committing release changes and creating release tags for your project.

Built atop the popular open source Python tool `Invoke <http://www.pyinvoke.org/>`_, Invoke Release exists as a
collection of standard Invoke tasks that you can easily include in all of your projects with just a few lines of Python
code per project.

License
-------

Invoke Release is licensed under the `Apache License, version 2.0 <LICENSE>`_.

Installation
------------

Invoke Release does not need to be listed in your project's dependencies (``setup.py``, ``requirements.txt``,
``Pipfile``, etc.). It only needs to be installed on the system or systems on which you will be running release
commands. It is available in PyPi and can be installed directly on your system via Pip:

.. code-block:: bash

    pip install invoke-release

Invoke Release supports any Python 2.7 or Python 3.x project, but in order to run release commands, you must install
Invoke Release on Python 3.7, 3.8, or newer. It will not run on Python 2 or older versions of Python 3.

Documentation
-------------

The complete Invoke Release documentation is available on `Read the Docs <https://invoke-release.readthedocs.io>`_!
