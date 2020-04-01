Using Invoke Release in your Project
====================================

Invoke Release is simple to configure and use in libraries, services, or any other Python projects that are versioned.
This documentation covers the configuration and execution of Invoke Release commands. This page does not cover
configuring and using plugins. For that, see :doc:`plugins`.

.. contents:: Contents
    :local:
    :depth: 3
    :backlinks: none

Installation
------------

Invoke Release does not need to be listed in your project's dependencies (``setup.py``, ``requirements.txt``,
``Pipfile``, etc.). It only needs to be installed on the system or systems on which you will be running release
commands. It is available in PyPi and can be installed directly on your system via Pip:

.. code-block:: bash

    pip install invoke-release

Invoke Release supports any Python 2.7 or Python 3.x project, but in order to run release commands, you must install
Invoke Release on Python 3.7, 3.8, or newer. It will not run on Python 2 or older versions of Python 3.

Configuring Invoke Release
--------------------------

There are two components to configuring Invoke Release: Establishing the proper file structure and configuring
``tasks.py``.

Establishing a Version File and a Changelog
+++++++++++++++++++++++++++++++++++++++++++

Your project must have two files: A file for containing the version information and a changelog for holding release
notes. The version file must reside within the top-level Python package for your project and may be named either
``version.py`` (recommended) or ``version.txt``. The changelog must reside within the root project directory and may be
named either ``CHANGELOG.rst`` (recommended), ``CHANGELOG.md``, or ``CHANGELOG.txt``.

``version.py``
~~~~~~~~~~~~~~

If you use ``version.py``, it need only initially contain the following code:

.. code-block:: python

    __version__ = '1.2.3'

Where ``__version__`` is your project's current version. When you next create a release with ``invoke release``, the
version file will be rewritten to contain more data. The version file may also contain other attributes, such as
``__author__``, ``__license__``, etc. These attributes will remain unchanged during releases.

``version.txt``
~~~~~~~~~~~~~~~

If you use ``version.txt``, the version file should contain only your version string and nothing else:

.. code-block:: text

    1.2.3

``version.txt`` is useful for when ``version.py`` cannot be imported without your project dependencies' being
installed. Invoke Release will interact only with ``version.txt`` in this case. However, in order for your project to
use the value stored in ``version.txt``, you'll need to setup ``version.py`` and the project-root ``setup.py`` as
follows.

For ``setup.py`` if your project supports only Python 3:

.. code-block:: python

    import codecs
    import os

    from setuptools import setup

    with codecs.open(
        os.path.join(os.path.dirname(__file__), 'my_module', 'version.txt'),
        mode='rb',
        encoding='utf8',
    ) as _version_file:
        __version__ = _version_file.read().strip()

    setup(
        ...
        version=__version__,
        package_data={str('my_module'): [str('version.txt')]},
        zip_safe=False,
        ...
    )

For ``setup.py`` if your project supports both Python 2 and 3:

.. code-block:: python

    import os

    from setuptools import setup

    with open(
        os.path.join(os.path.dirname(__file__), 'my_module', 'version.txt'),
        mode='rt',
        encoding='utf8',
    ) as _version_file:
        __version__ = _version_file.read().strip()

    setup(
        ...
        version=__version__,
        package_data={str('my_module'): [str('version.txt')]},
        zip_safe=False,
        ...
    )

For ``version.py`` if your project supports only Python 3:

.. code-block:: python

    import os


    __all__ = ('__version__', '__version_info__')

    _version_file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'version.txt')
    with open(_version_file_path, mode='rt', encoding='utf8') as _version_file:
        __version__ = _version_file.read().strip()
    __version_info__ = tuple(map(int, __version__.split('-', 1)[0].split('.', 2))) + tuple(__version__.split('-', 1)[1:])

For ``version.py`` if your project supports both Python 2 and Python 3:

.. code-block:: python

    from __future__ import absolute_import, unicode_literals

    import codecs
    import os


    __all__ = ('__version__', '__version_info__')

    _version_file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'version.txt')
    with codecs.open(_version_file_path, mode='rb', encoding='utf8') as _version_file:
        __version__ = _version_file.read().strip()
    __version_info__ = tuple(map(int, __version__.split('-', 1)[0].split('.', 2))) + tuple(__version__.split('-', 1)[1:])

``CHANGELOG.rst``, ``CHANGELOG.md``, or ``CHANGELOG.txt``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Much simpler than the version file instructions, the initial changelog contents are minimal:

.. code-block:: rst

    Changelog
    =========

    0.1.0 (2018-01-24)
    ------------------
    - Initial beta release

Configuring ``tasks.py``
++++++++++++++++++++++++

Once your version and changelog file structure is complete, you must configure the Invoke tasks that make up the
operation of Invoke Release. Invoke tasks are always configured in a file named ``tasks.py`` in the root directory of
your project. (For more information about using Invoke, see the
`Invoke documentation <http://docs.pyinvoke.org/en/stable/>`_.

The simplest possible ``tasks.py`` looks like this:

.. code-block:: python

    from invoke_release.config import config
    from invoke_release.tasks import *  # noqa: F401,F403


    config.configure(
        module_name='my_package',
        display_name='My Python Project',
    )

This configuration assumes that your Python project's top-level Python package is named ``my_package``, and that the
package directory lives within the project root directory. In this example, the version file would be found at
``./my_package/version.py`` or ``./my_package/version.txt`` relative to the project root directory. If the package
directory actually lives within a sub-directory, such as ``python`` or ``source`` or ``source/python``, you must
specify the ``python_directory`` argument to detail this sub-directory:

.. code-block:: python

    config.configure(
        module_name='my_package',
        display_name='My Python Project',
        python_directory='source/python',
    )

In this example, the version file would be found at ``./source/python/my_package/version.py`` or
``./source/python/my_package/version.txt`` relative to the project root directory.

There are several other possible arguments to ``config.configure`` to customize Invoke Release's behavior. These
arguments are described below:

* ``use_pull_request``: This ``bool`` defaults to ``False``. If set to ``True``, Invoke Release will not commit to
  ``master`` or version branches directly. Instead, it will create release branches from which you can create
  pull requests for merging release changes.
* ``use_tag``: This ``bool`` defaults to ``True``. If set to ``False``, Invoke Release will not create and push release
  tags. Setting this to ``False`` is usually associated with setting ``use_pull_request`` to ``True``.
* ``master_branch``: If you use a master branch name other than ``master``, set this argument's string value to that
  branch.
* ``plugins``: See :doc:`plugins`.
* ``source_control``: Too specify an ``invoke_release.config.SourceControlType`` value other than
  ``SourceControlType.GIT``. Currently, ``GIT`` is the only supported value.

Using Commands
--------------

Once you have configured Invoke Release as described above and committed that configuration to your master branch, you
can begin using Invoke Release to manage your project's releases. You can list available commands and see their
documentation with the following commands:

.. code-block:: bash

    ~/projects/pysoa $ invoke --list
    Available tasks:

      branch             Creates a branch from a release tag for creating a new patch or minor release from that
                         branch.
      release            Increases the version, adds a changelog message, and tags a new version of this project.
      rollback-release   If the last commit is the commit for the current release, this command deletes the release tag
                         and deletes
      version            Prints the "Invoke Release" version and the version of the current project.

    ~/projects/pysoa $ invoke release --help
    Usage: inv[oke] [--core-opts] release [--options] [other tasks here ...]

    Docstring:
      Increases the version, adds a changelog message, and tags a new version of this project.

    Options:
      -n, --no-stash   Specify this switch to disable stashing any uncommitted changes (by default, changes that have
                       not been committed are stashed before the release is executed).
      -v, --verbose    Specify this switch to include verbose debug information in the command output.


``invoke version``
++++++++++++++++++

This command is a helpful troubleshooting or verification command for ensuring your project is configured correctly:

.. code-block:: bash

    ~/projects/pysoa $ invoke version
    Python: 3.7.6 (default, Feb 19 2020, 15:23:51)
    Source control: git version 2.15.1
    Invoke: 1.4.1
    Invoke Release: 5.0.0
    Detected Project: PySOA 1.1.3
    Detected Git branch: master
    Detected version file: /Users/nwilliams/projects/pysoa/pysoa/version.py
    Detected changelog file: /Users/nwilliams/projects/pysoa/CHANGELOG.rst

Like all the commands you will see below, it supports a ``--verbose`` argument for getting more diagnostic output:

.. code-block:: bash

    ~/projects/pysoa $ invoke version --verbose
    Python: 3.7.6 (default, Feb 19 2020, 15:23:51)
    Source control: git version 2.15.1
    DEBUG: GPG (/usr/local/bin/gpg): gpg (GnuPG) 2.2.4
    DEBUG: TTY: /dev/ttys001
    Invoke: 1.4.1
    Invoke Release: 5.0.0
    Detected Project: PySOA 1.1.3
    DEBUG: Determining current Git branch name.
    DEBUG: Current Git branch name is master.
    Detected Git branch: master
    Detected version file: /Users/nwilliams/projects/pysoa/pysoa/version.py
    Detected changelog file: /Users/nwilliams/projects/pysoa/CHANGELOG.rst
    DEBUG: Release commit message template: "Released PySOA version {}"

If you see any errors or unexpected messages in this output, you should adjust your project configuration accordingly.

``invoke release``
++++++++++++++++++

This command is the prime reason that Invoke Release exists, and was the only command in the very early stages. When
you execute this command, Invoke Release will walk you through a series of prompts and steps that vary based on your
configuration and responses to prompt. At the end, unless you cancel, you'll have a new version of your project that
you can then push to PyPi, Devpi, or whatever other release publication tooling you have available.

At each prompt, you'll be presented with a two or more options from which to choose. The option in ALL CAPS is the
default option and will be chosen for you if you press enter without typing anything. At all prompts, you can either
type ``exit`` or ``rollback`` or press Ctrl+C to abort the process.

.. code-block:: bash

    ~/projects/pysoa $ invoke release
    <example coming soon>

``invoke branch``
+++++++++++++++++

This command makes it easy to create branches from previous versions so that you can make changes and release patches
or minor releases from those branches, even if you've made other changes in the interim that you don't want to include
in your release.

.. code-block:: bash

    ~/projects/pysoa $ invoke branch
    <example coming soon>

``invoke rollback_release``
+++++++++++++++++++++++++++

Mistakes happen. Whether you locally made a release and, before pushing that release to the remote repository, realized
you missed something, or you completed a release but need to recall it because it is badly broken, Invoke Release is
here to help.

.. code-block:: bash

    ~/projects/pysoa $ invoke rollback_release
    <example coming soon>

Cryptographically Signing Releases
----------------------------------

There's releasing with Invoke Release, and *then* there's releasing with Invoke Release + GnuPG so that your release
commits and tags can be cryptographically verified by your consumers. Want that little green "Verified" seal next to
your release commit in the GitHub commits list or in the details on the GitHub releases page? This is how you get that.

This extra process is completely optional but highly recommended.

Install GnuPG
+++++++++++++

You first need to make sure you have GnuPG installed on your system. Invoke Release supports both GnuPG 1.4+ and GnuPG
2.1+, but we recommend you install GnuPG 2.1+ for the best experience. If you already have GnuPG on your system, you
can skip this step.

.. code-block:: bash

    $ brew install gnupg              # macOS (see https://brew.sh/); installs v2
    $ apt-get install gnupg2          # Ubuntu 16.04; installs v2
    $ apt-get install gnupg           # Ubuntu 18.04, 19.04, and 20.04; installs v2
    $ yum install gnupg2              # CentOS; installs v2

Setup your Key(s)
+++++++++++++++++

The easiest way to setup a GnuPG key for Invoke Release + Git to use is to have a key that exactly matches your Git
committer name and email address. For example, given this output:

.. code-block:: bash

    $ git config --global user.name
    Nick Williams
    $ git config --global user.email
    nicholas@example.com

You would create a GnuPG signing key with the "Real name" value "Nick Williams" and the "Email address" value
"nicholas@example.com":

.. code-block:: bash

    $ gpg --gen-key
    gpg (GnuPG) 2.2.4; Copyright (C) 2017 Free Software Foundation, Inc.
    This is free software: you are free to change and redistribute it.
    There is NO WARRANTY, to the extent permitted by law.

    Note: Use "gpg --full-generate-key" for a full featured key generation dialog.

    GnuPG needs to construct a user ID to identify your key.

    Real name: Nick Williams
    Email address: nicholas@example.com
    You selected this USER-ID:
        "Nick Williams <nicholas@example.com>"

    Change (N)ame, (E)mail, or (O)kay/(Q)uit? O
    We need to generate a lot of random bytes. It is a good idea to perform
    some other action (type on the keyboard, move the mouse, utilize the
    disks) during the prime generation; this gives the random number
    generator a better chance to gain enough entropy.

    <at this point, GnuPG prompts you twice for a password>

    We need to generate a lot of random bytes. It is a good idea to perform
    some other action (type on the keyboard, move the mouse, utilize the
    disks) during the prime generation; this gives the random number
    generator a better chance to gain enough entropy.
    gpg: /Users/nwilliams/.gnupg/trustdb.gpg: trustdb created
    gpg: key 0039B9A39E8240E3 marked as ultimately trusted
    gpg: directory '/Users/nwilliams/.gnupg/openpgp-revocs.d' created
    gpg: revocation certificate stored as '/Users/nwilliams/.gnupg/openpgp-revocs.d/75F0E9929B658171C0DA07130039B9A39E8240E3.rev'
    public and secret key created and signed.

    pub   rsa2048 2020-04-06 [SC] [expires: 2022-04-06]
          75F0E9929B658171C0DA07130039B9A39E8240E3
    uid                      Nick Williams <nicholas@example.com>
    sub   rsa2048 2020-04-06 [E] [expires: 2022-04-06]

Because this real name and email address exactly match the Git configuration ``user.name`` and ``user.email``,
Invoke Release and Git can use it automatically.

However, suppose you already have an existing signing key you wish to use that does not match these details. This is
still possible, it just requires a little extra work:

.. code-block:: bash

    $ gpg --list-keys
    gpg: checking the trustdb
    gpg: marginals needed: 3  completes needed: 1  trust model: pgp
    gpg: depth: 0  valid:   1  signed:   0  trust: 0-, 0q, 0n, 0m, 0f, 1u
    gpg: next trustdb check due at 2022-04-06
    /Users/nwilliams/.gnupg/pubring.kbx
    ------------------------------
    pub   rsa2048 2020-04-06 [SC] [expires: 2022-04-06]
          75F0E9929B658171C0DA07130039B9A39E8240E3
    uid           [ultimate] Nick Williams <nicholas@example.com>
    sub   rsa2048 2020-04-06 [E] [expires: 2022-04-06]

In the output above, notice the key ID ``75F0E9929B658171C0DA07130039B9A39E8240E3``. Only the last 16 characters of
that, ``0039B9A39E8240E3``, are important. In the next section, you'll learn about the prompt for signing a release.
You'll need to respond to that prompt with this shortened key ID (``0039B9A39E8240E3``), so keep it handy.

Once you have a key with which to sign your releases, you need to tell GitHub about that key. First, publish your
signing key publicly:

.. code-block:: bash

    $ gpg --keyserver pgp.mit.edu --send-keys 0039B9A39E8240E3

Next, export your key for GitHub:

.. code-block:: bash

    $ gpg --armor --export 0039B9A39E8240E3

Copy the entire armored output of this command, including the ``-----BEGIN PGP PUBLIC KEY BLOCK-----`` header and
``-----END PGP PUBLIC KEY BLOCK-----`` footer. Go to GitHub and click on your profile icon in the upper right-hand
corner, then click "Settings." Click "SSH and GPG Keys" from the settings page, click "New GPG key," paste in your
armored key, and submit. You are now ready to use your GPG key to cryptographically sign release commits and tags.

*Note: You can also use your GPG key to sign all commits you make to Git repositories, but that is beyond the scope of*
*this project or this documentation. If you are interested in this, we recommend you view the GitHub documentation*
`Signing commits using GPG <https://help.github.com/articles/signing-commits-using-gpg/>`_.

Respond to the Prompt
+++++++++++++++++++++

When you run ``invoke release``, it will detect the presence of GnuPG and prompt you to sign your release commit and
tag. Respond affirmatively to use a key matching your configured Git name and email address, or respond with the
16-digit shortened key ID to use a different key.

.. code-block:: bash

    ~/projects/pysoa $ invoke release
    <example coming soon>
