Contributing
============

Contributions are welcome, and they are greatly appreciated! Every little bit helps, and credit will always be given.

You can contribute in many ways:

Types of Contributions
----------------------

Report Bugs
~~~~~~~~~~~

Report bugs at https://github.com/eventbrite/invoke-release/issues.

If you are reporting a bug, please include:

* Your operating system name and version.
* Your Python interpreter type and version.
* Any details about your local setup that might be helpful in troubleshooting.
* Detailed steps to reproduce the bug.

Fix Bugs
~~~~~~~~

Look through the GitHub issues for bugs. Anything tagged with "bug" is open to whoever wants to fix it.

Implement Features
~~~~~~~~~~~~~~~~~~

Look through the GitHub issues for features. Anything tagged with "feature" is open to whoever wants to implement it.

Write Documentation
~~~~~~~~~~~~~~~~~~~

Invoke Release could probably use more documentation, whether as part of the official Invoke Release docs, in
docstrings, or even on the web in blog posts, articles, and more.

Submit Feedback
~~~~~~~~~~~~~~~

The best way to send feedback is to file an issue at https://github.com/eventbrite/invoke-release/issues.

If you are proposing a feature:

* Explain in detail how it would work.
* Keep the scope as narrow as possible, to make it easier to implement.
* Remember that contributions are welcome. :)

Get Started
-----------

Ready to contribute? Here's how to set up Invoke Release for local development.

1. Ensure that GnuPG is installed on your system. Invoke Release does not require GnuPG to use (it's optional, though
   recommended), but it does require GnuPG to run integration tests, which you should run whenever you make changes.
   Install at least GnuPGv1 or GnuPGv2, but we recommend installing both, so that integration tests will run against
   both. ::

        $ brew install gnupg@1.4 gnupg              # macOS (see https://brew.sh/); installs both v1 and v2
        $ apt-get install gnupg gnupg2              # Ubuntu 16.04; installs both v1 and v2
        $ apt-get install gnupg1 gnupg              # Ubuntu 18.04, 19.04, and 20.04; installs both v1 and v2
        $ yum install gnupg gnupg2                  # CentOS; installs both v1 and v2

2. Fork the ``invoke-release`` repository on GitHub.
3. Clone your fork locally::

       $ git clone git@github.com:your_name_here/invoke-release.git

4. Create Python 3.7 and 3.8 virtualenvs (you should ``pip install virtualenvwrapper`` on your system if you have not
   already) for installing Invoke Release dependencies::

       $ mkvirtualenv "--python=/path/to/python3.7" invoke-release37
       (invoke-release37) $ pip install -e .[testing]
       (invoke-release37) $ deactivate
       $ mkvirtualenv "--python=/path/to/python3.8" invoke-release38
       (invoke-release38) $ pip install -e .[testing]
       (invoke-release38) $ deactivate

5. Make sure the tests pass on master before making any changes; otherwise, you might have an environment issue::

       (invoke-release37) $ ./test.sh
       (invoke-release38) $ ./test.sh

6. Create a branch for local development::

       $ git checkout -b name-of-your-bugfix-or-feature

   Now you can make your changes locally.

7. As you make changes, and when you are done making changes, regularly check that Flake8 and MyPy analysis and all of
   the tests pass. You should also include new tests or assertions to validate your new or changed code::

       # this command runs unit and integration tests
       (invoke-release37) $ pytest -v
       (invoke-release38) $ pytest -v

       # to run just unit tests or just integration tests
       (invoke-release37) $ pytest -v tests/unit
       (invoke-release37) $ pytest -v tests/integration

       # to verify Flake8 and MyPy compliance
       (invoke-release37) $ flake8
       (invoke-release37) $ mypy .

8. When you think you're ready to commit, run ``isort`` to organize your imports::

       $ isort

9. Commit your changes and push your branch to GitHub::

       $ git add -A
       $ git commit -m "[PATCH] Your detailed description of your changes"
       $ git push origin name-of-your-bugfix-or-feature

   Commit messages should start with ``[PATCH]`` for bug fixes that don't impact the *public* interface of the library
   or any of its command-line utilities, ``[MINOR]`` for changes that add new feature or alter the *public* interface
   of the library or its command-line utilities in non-breaking ways, or ``[MAJOR]`` for any changes that break
   backwards compatibility. This project strictly adheres to SemVer, so these commit prefixes help guide whether a
   patch, minor, or major release will be tagged. You should strive to avoid ``[MAJOR]`` changes, as they will not be
   released until the next major milestone, which could be a year or more away.

10. Submit a pull request through the GitHub website.

Pull Request Guidelines
-----------------------

Before you submit a pull request, check that it meets these guidelines:

1. The pull request should include new or augmented tests.
2. If the pull request adds functionality, the documentation should be updated. Put your new functionality into a
   class or function with a docstring, and add the feature to the appropriate location in ``docs/``.
3. The pull request should work for Python 3.7 and 3.8. Check
   https://travis-ci.org/eventbrite/invoke-release/pull_requests and make sure that the tests pass for all supported
   Python versions.
