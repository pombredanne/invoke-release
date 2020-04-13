# Invoke Release

Invoke Release is a set of command line tools that help software engineers release Python projects quickly, easily, and
in a consistent manner. It helps ensure that the version standards for your projects are the same across all of your
organization's projects, and minimizes the possible errors that can occur during a release. It uses Git for committing
release changes and creating release tags for your project.

Built atop the popular open source Python tool [Invoke](http://www.pyinvoke.org/), Invoke Release exists as a
collection of standard Invoke tasks that you can easily include in all of your projects with just a few lines of Python
code per project.

This documentation is broken down into five main sections:

* [Installing Invoke Release](#installing-invoke-release)
* [Using Invoke Release on Existing Projects](#using-invoke-release-on-existing-projects)
* [Integrating Invoke Release into Your Project](#integrating-invoke-release-into-your-project)
  - [Using the Alternative `version.txt` Pattern](#using-the-alternative-versiontxt-pattern)
* [Cryptographically Signing Releases](#cryptographically-signing-releases)
  - [Setting up Release Signing](#setting-up-release-signing)
  - [Signing a Release Tag](#signing-a-release-tag)
* [Creating and Using Invoke Release Plugins](#creating-and-using-invoke-release-plugins)
  - [`PatternReplaceVersionInFilesPlugin`](#patternreplaceversioninfilesplugin)

Invoke Release has been tested on Python 2.7 and 3.5 and on Mac OS X and Ubuntu. It has not been tested on Windows at
this time, but pull requests are welcome if issues are found with Windows. It would require a shell-like environment,
such as [Cygwin](https://www.cygwin.com/), to properly run on Windows operating systems.

**NOTE:** If you have previously installed Invoke, this, alone, is not enough to use Invoke Release. Be sure to read
the first section below on installing Invoke Release.

## Installing Invoke Release

Before you can integrate Invoke Release into your project **or** use it on a project into which it has already been
integrated, you need to install the tools. Installation is easy. It can be installed on most systems by simply running
the following command:

```
$ pip install invoke-release
```

Unfortunately, the facts on the ground are not always that simple. Invoke Release depends on installing Invoke, which
must itself place a binary `invoke` command on your execution path. On Cygwin or a Linux system, this is not normally
an issue. On Mac OS X, this will not work with the built-in Python program bundled with Mac OS X; the installation will
cause "permission denied" errors.

Strictly speaking, it would be possible to `sudo pip` to install Invoke Release on your system, but we do not recommend
doing that. Instead, you should use a virtualenv or, even better, ditch the bundled Python and install a better Python
using [Homebrew](https://brew.sh/):

```
$ brew install python
...
$ which python
/usr/local/bin/python  <- This means Brew Python; /usr/bin/python means bundled Python
$ pip install invoke-release
```

## Using Invoke Release on Existing Projects

If a project already has support for Invoke Release, using it is easy. First, check that the integration is working
properly and that the tools are installed on your machine:

```
$ invoke version
Python 2.7.11 (default, Jun 17 2016, 09:29:41)
Invoke 0.22.0
Invoke Release 4.5.2
My Project 2.1.0
Detected Git branch: master
Detected version file: /path/to/my/project/module/version.py
Detected changelog file: /path/to/my/project/CHANGELOG.txt
```

If the `invoke` command is not working, or you get module errors about `invoke_release.tasks`, see
[Installing Invoke Release](#installing-invoke-release).

Once you have confirmed that the tools are working properly, all you have to do is execute it from the project's root
directory and follow the on-screen instructions:

```
$ invoke release
Invoke Release 4.5.2
Releasing My Project...
Current version: 2.1.0
Enter a new version (or "exit"): 2.2.0
...
```

It's that easy! Well, you should also carefully read the prompts and select your responses to those prompts.

You can also use Invoke Release to create version branches. Let's say, for example, that you released version 2.0.0 of
your project some time ago, and since then have released 2.1.0 and 2.2.0. However, a critical bug is found in 2.0.0
that requires a patch release. Invoke Release can help you create a new branch from that 2.0.0 tag, to which you can
then commit (or cherry-pick, as the case may be) your fix, and from which you can subsequently release 2.0.1:

```
$ invoke branch
Invoke Release 4.5.2
Enter a version tag from which to create a new branch (or "exit"): 2.0.0
...
```

The prompts will further help you determine whether to create a major version branch (for releasing minor versions) or
a minor version branch (for releasing patch versions), and then create the branch for you. Then all you need to do is
land your commits and call `invoke release` from that branch to release a new minor or patch version, as the case may
be.

One of the available commands is `rollback-release`:

```
$ invoke rollback-release
...
```

This command is extremely useful if a release fails partway through for some reason, such as if you encounter problems
while [signing a release tag](#signing-a-release-tag). Otherwise, it should be used with extreme caution. Releases that
have only been committed and/or tagged locally, and not pushed, are safe to revert at any time (such as those that
failed). On the other hand, release commits and tags that have been pushed to the remote origin repository should only
be rolled back in the direst of circumstances. If _any_ commits have occurred since the release, this command cannot be
used. If the release tag has already been uploaded to a public Python repo like PyPi, rolling back the release will not
be able to undo that, and the release will be on that public repo until you remove it manually (if that is even
possible).

Finally, there is the wheel task:

```
$ invoke wheel
...
```

This builds a wheel archive of the project as currently checked out. At the moment, it is experimental. Use it at your
own discretion.

For more information, you can view a list of commands or view help for a command as follows (again, in your project's
root directory):

```
$ invoke --list
$ invoke --help release
```

## Integrating Invoke Release into Your Project

If you have created a new Python library, or you're improving an old one without existing Invoke Release support,
integrating Invoke Release is easy. Be sure to read [Installing Invoke Release](#installing-invoke-release) if you have
not yet installed Invoke Release or if the `invoke` command is not working.

As a prerequisite, your project's Python root module _must_ have a module named `version.py` with, at least, a
`__version__` variable defined. This variable must also be imported in the `__init__.py` file of the home module. For
an example of this, see [`python/invoke_release/version.py`](python/invoke_release/version.py) and
[`python/invoke_release/__init__.py`](python/invoke_release/__init__.py). If your project is a Python 2 or universal
project, we _strongly_ recommend putting `from __future__ import unicode_literals` at the top of your `version.py`
file. For Python 3-only projects, this is not necessary.

Your project must also contain a file named `CHANGELOG.txt`, `CHANGELOG.md`, or `CHANGELOG.rst`. If more than one of
those files are present, Invoke Release will use the first one found, in that order. In order to work properly, the
existing changelog file must match the following format (and `CHANGELOG.rst` files must have an additional leading
`=========` line before the `Changelog` header.)

```text
Changelog
=========

0.1.0 (2018-01-24)
------------------
- Initial beta release
```

The changelog, shown here with just one "initial release," may have any number of existing releases listed, as long as
they all match that syntax, making it easy to integrate Invoke Release with existing Python projects.

Once you have configured the version, init, and changelog files, create a file named `tasks.py` in the root directory
of your project and give it the following contents:

```python
from invoke_release.tasks import *  # noqa: F403


configure_release_parameters(  # noqa: F405
    module_name='my_project_python_home_module',
    display_name='My Project Display Name'
)
```

If you would like `invoke-release` to push a release branch instead of pushing a commit to `master`,
add `use_pull_request=True` to `tasks.py`.
If you do not want to push a tag to your remote repository, add `use_tag=False` to `tasks.py`.

This assumes that the default Python source directory in your project is the same as the `module_name`, relative to the
project root directory. This is true for many Python projects, but not all of them. For some projects, you may need to
use the optional `python_directory` function argument to customize this. Using the above naming, if your module
directory is `python/my_project_python_home_module`, you'd pass "my_project_python_home_module" as the
`module_name` and "python" as the `python_directory`.

For example, compare the contents of `tasks.py` for Eventbrite's PySOA service library, whose `pysoa` module directory
is in the root of the project:

```python
configure_release_parameters(  # noqa: F405
    module_name='pysoa',
    display_name='PySOA',
)
```

With the contents of this project's own `tasks.py`, whose `invoke_release` module directory is within a `python`
directory in the root of this project:

```python
...
configure_release_parameters(  # noqa: F405
    module_name='invoke_release',
    display_name='Invoke Release',
    python_directory='python',
...
```

Once you've completed the necessary integration step, execute the following command (from the project root directory)
and verify the output. Address any errors that you see.

```
$ invoke version
Python 2.7.11 (default, Jun 17 2016, 09:29:41)
Invoke 0.22.0
Invoke Release 4.5.2
PySOA 0.26.1
Detected Git branch: master
Detected version file: /path/to/pysoa-project/pysoa/version.py
Detected changelog file: /path/to/pysoa-project/CHANGELOG.txt
```

Finally, commit these changes to your project and push to remote master. You are now ready to run Invoke Release using
the steps in [the previous section](#using-invoke-release-on-existing-projects).

### Using the Alternative `version.txt` Pattern

Normally, the version tuple and string is stored directly in the `version.py` file, and Invoke Release will update this
file with each release; however, there is an alternative approach you may take. You can, instead, create a
`version.txt` file that contains the raw version string and no other contents. Invoke Release will, instead, update
the version in that file. This is particularly useful if you have tools that need to read the project version without
importing the `version` module. If you take this approach, your `version.py` file should have the following exact
contents (excluding `__future__` for Python 3-only projects):

```python
from __future__ import unicode_literals

import codecs
import os


__all__ = ['__version__', '__version_info__']

_version_file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'version.txt')
with codecs.open(_version_file_path, mode='rb', encoding='utf8') as _version_file:
    __version__ = _version_file.read().strip()
__version_info__ = tuple(map(int, __version__.split('-', 1)[0].split('.', 2))) + tuple(__version__.split('-', 1)[1:])
```

Currently, Invoke Release will not update `version.py` with these contents, so it is your responsibility to do so. In
the future, the ability to update `version.py` with these contents may be added.

The final step to using this pattern is to update your project's `setup.py` to ensure that the `version.txt` file gets
included with your packaged project:

```python
...
setup(
   ...
   package_data={'my_root_module': ['version.txt']},
   ...
)
```

## Cryptographically Signing Releases

Starting with version 4.0, Invoke Release now supports cryptographically signing your release tags as part of the
release process before pushing them to a remote origin. This requires some additional setup before you can use this
feature. As a new feature, it is still somewhat experimental, and there may be bugs. We encourage bug reports and
pull requests to report and resolve any issues you may find.

### Setting up Release Signing

First, you must ensure that `gpg` or `gpg2` is installed on your system. Git does not currently support any other
crypto program that operates differently than one of these. There are many ways to install these, depending on your
operating system:

```
$ apt-get install gnupg
$ zypper install gpg2
$ yum install gpg2
$ brew install gpg
```

Then, you need to create a signing key. This is done with `gpg --gen-key` if you're using the older GPG 1 or
`gpg --full-gen-key` if you're using the newer GPG 2.0, 2.1, or 2.2. Follow the prompts for creating your key, and be
sure to use 4096 bits (anything below that will soon be insecure; anything above that may not be supported on all
systems yet) and "RSA and RSA" as the key type, using the following guidance regarding the name and email:

**IMPORTANT NOTE:** When signing releases, Git can either auto-find the key that matches your committer name and email
(the easiest approach), or you can manually specify the key's unique ID to use at the signing prompt. To auto-find the
key, it is important that name and email in your key are identical to the name and email configured as your Git
committer information for that repository (or globally, if there is no local configuration). For example, if your
Git config `user.name` is "Jane Smith" and your Git config `user.email` is "jane@example.org," then you'll need to
supply "Jane Smith" (and nothing else) at the GPG "Full name" prompt and "jane@example.org" (and nothing else) at the
GPG "Email" prompt, _and provide no answers_ to any of the other "Comment" or "Extra details" prompts.

Once your key is created, you can publish it to public servers using a command like the following, replacing
`9F3A6F3F1D46A033` with your key's unique ID (which you can find with `gpg --list-keys`):

```
gpg --keyserver pgp.mit.edu --send-keys 9F3A6F3F1D46A033
```

You should also add the GPG key to your GitHub account. Doing this is easy. First, use the following command to
generate an armored public key block:

```
gpg --armor --export 9F3A6F3F1D46A033
```

Copy the entire output, including the `-----BEGIN PGP PUBLIC KEY BLOCK-----` header and
`-----END PGP PUBLIC KEY BLOCK-----` footer. Go to GitHub and click on your profile icon in the upper right-hand
corner, then click "Settings." Click "SSH and GPG Keys" from the settings page, click "New GPG key," paste in your
armored key, and submit. You are now ready to use your GPG key to cryptographically sign release tags.

_Note: You can also use your GPG key to sign all commits you make to Git repositories, but that is beyond the scope
of this project or this documentation. If you are interested in this, we recommend you view the GitHub documenation
[Signing commits using GPG](https://help.github.com/articles/signing-commits-using-gpg/)._

### Signing a Release Tag

During the standard `invoke release` process, Invoke Release will detect the presence of GPG installed on your system
and prompt you to add a signature to the release tag:

```
$ invoke release
...
GPG is installed on your system. Would you like to sign the release tag with your GitHub
committer email GPG key? (y/N/[alternative key ID]) 9F3A6F3F1D46A033
...
```

When you get this prompt, you should respond `y` if you want to auto-find the key matching your committer details or,
if you want to use a different key, you should respond with the full key ID, as in the example above. The release
output will include details about the generated signature and a test verification. If anything fails, you can roll back
the release to either try again after correcting the problem or release without a signature if you cannot correct the
problem.

## Creating and Using Invoke Release Plugins

In most cases, the default Invoke Release behavior (increment version, update changelog, commit, tag, push) is
complete and sufficient for releasing a new project version. However, sometimes you need more advanced
behavior. For those times, the Invoke Release tools support plugins that can add behavior during the version check,
during the pre-release check, between file changes and commit, between commit and tag/push, and after push.

You specify one or more plugins by using the `plugins` argument to `configure_release_parameters`:

```python
from invoke_release.tasks import *  # noqa: F403


configure_release_parameters(  # noqa: F405
    module_name='my_project',
    display_name='My Test Project',
    plugins=[
        Plugin1(),
        Plugin2(),
    ],
)
```

A plugin must be an instance of a class that extends `invoke_release.plugins:AbstractInvokeReleasePlugin`. You can
read the [docstring documentation for this class](python/invoke_release/plugins.py) to learn about the available hooks
and how to implement them. Chances are, though, you can just use one of the built-in plugins, documented below. If you
do create a new plugin, we encourage you to submit a pull request for adding it to this library so that other projects
can enjoy it.

### `PatternReplaceVersionInFilesPlugin`

The name of this plugin should be pretty self-explanatory. Using this plugin, you can tell Invoke Release about other
files that contain the version string pattern that should be updated on release. For example, as a proof-of-concept,
[this library uses the plugin to update the version strings in this documentation](tasks.py).

To use this plugin, just import it, instantiate it, and pass it a list of relative file names whose contents should be
searched and updated:

```python
from invoke_release.tasks import *  # noqa: F403
from invoke_release.plugins import PatternReplaceVersionInFilesPlugin


configure_release_parameters(  # noqa: F405
    module_name='my_project',
    display_name='My Test Project',
    plugins=[
        PatternReplaceVersionInFilesPlugin('.version', 'README.md'),
    ],
)
```
