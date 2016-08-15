# Eventbrite Command Line Release Tools ("Invoke Release")

The Invoke Release tools are a set of command line tools that help Eventbrite engineers release services and libraries
quickly, easily, and in a consistent manner. It ensures that the version standards for our projects are the same
across all projects, and minimizes the possible errors that can occur during a release. This documentation is broken
down into four sections:

* [Installing Invoke Release Tools](#installing-invoke-release-tools)
* [Using Invoke Release on Existing Projects](#using-invoke-release-on-existing-projects)
* [Integrating Invoke Release into Your Project](#integrating-invoke-release-into-your-project)
* [Creating and Using Invoke Release Plugins](#creating-and-using-invoke-release-plugins)

**NOTE:** If you have previously installed `invoke`, this, alone, is not enough to use the Eventbrite Command Line
Release Tools. Be sure to read the first section below on installing these tools.

## Installing Invoke Release Tools

Before you can integrate Invoke Release into your project **or** use it on a project into which it has already been
integrated, you need to install the tools. Installation is easy. Just running `devtools_update` _on your development
machine_ (**not** within Vagrant or a Docker container) will ensure that you have the latest version of the release
tools installed. (If you haven't run `devtools_update` since 2015-10-22, you may need to run this command twice—once to
get the latest devtools helpers, and a second time to actually install the release tools.)

If, for some reason, you need to manually install the release tools (for example, to use master instead of the latest
tag, or to use the release tools within Vagrant/Docker instead of on your local machine), that's easy, too. Just run
the following command (if you are using Python on a Mac not installed with Homebrew, you need to run this as `sudo`):

```
$ pip install -U git+ssh://git@github.com/eventbrite/invoke-release.git
```

This will install the Eventbrite Command Line Release Tools and their only dependency, `invoke`. (You do not need to
manually/separately install `invoke`.) If you need to specify an exact version of the tools, you can use a tag
(replacing the tag name as necessary, and using `sudo` as necessary as described above):

```
$ pip install -U git+ssh://git@github.com/eventbrite/invoke-release.git@1.3.2
```

You can confirm that the project and its requirements were successfully installed by checking the version:

```
$ invoke --version
Invoke 0.13.0
```

## Using Invoke Release on Existing Projects

If a project already has support for Invoke Release, using it is easy. First, check that the integration is working
properly and that the tools are installed on your machine:

```
$ invoke --version
Invoke 0.13.0
$ invoke version
Eventbrite Command Line Release Tools ("Invoke Release") 1.3.2
EB Common 1.8.2
```

If the `invoke` command is not working, or you get module errors about `invoke_release.tasks`, see
[Installing Invoke Release Tools](#installing-invoke-release-tools). Once you have confirmed that the tools are
working properly, all you have to do is execute it from the project's home directory and follow the on-screen
instructions:

```
$ invoke release
```

It's that easy! You can also view a list of commands or view help for a command as follows:

```
$ invoke --list
$ invoke --help release
```

One of the available commands is `rollback_release`:

```
$ invoke rollback_release
```

However, this command should be used with extreme caution. Releases that have only been committed and tagged locally,
and not pushed, are safe to revert at any time. On the other hand, release commits and tags that have been pushed to
origin should only be rolled back in the direst of circumstances. If any commits have occurred since the release, this
command cannot be used.

## Integrating Invoke Release into Your Project

If you have created a new Eventbrite service or library, or you're improving an old one without Invoke Release support,
integrating Invoke Release is easy. Be sure to read [Installing Invoke Release Tools](#installing-invoke-release-tools)
if you have not yet installed the Eventbrite Command Line Release Tools or if the `invoke` command is not working.

As a prerequisite, your Python home module _must_ have a module named `version.py` with, at least, a `__version__`
variable defined. This variable must also be imported in the `__init__.py` file of the home module. For an example
of this, see [`python/invoke_release/version.py`](python/invoke_release/version.py) and
[`python/invoke_release/__init__.py`](python/invoke_release/__init__.py).

In the root directory of your project, create a file named `tasks.py` and give it the following contents:

```
from invoke_release.tasks import *
configure_release_parameters(
    module_name='my_project_python_home_module',
    display_name='My Project Display Name'
)
```

This assumes that the default Python source directory in your project is the same as the `module_name`, relative to the
project root directory. This is true for most Eventbrite services and some libraries. For most libraries, and some
services not meeting this pattern, you must use the optional `python_directory` function argument to customize this.
If your module directory is `python/my_project_python_home_module`, you'd pass "my_project_python_home_module" as the
`module_name` and "python" as the `python_directory`.

For example, here are the contents of this file for EB Common and Geo Service, respectively:

```
from invoke_release.tasks import *
configure_release_parameters(
    module_name='ebcommon',
    display_name='EB Common',
    python_directory='python'
)
```

```
from invoke_release.tasks import *
configure_release_parameters(
    module_name='geo_service',
    display_name='Geo Service',
)
```

Once you've completed the necessary integration step, execute the following command (from the project root directory)
and verify the output. Address any errors that you see.

```
$ invoke version
Eventbrite Command Line Release Tools ("Invoke Release") 1.3.2
EB Common 1.8.2
```

Finally, commit these changes to your project and push to remote master. You are now ready to run Invoke Release using
the steps in [the previous section](#using-invoke-release-on-existing-projects).

## Creating and Using Invoke Release Plugins

In most cases, the default Invoke Release behavior (increment version, update changelog, commit, tag, push) is
complete and sufficient for releasing a new service or library version. However, sometimes you need more advanced
behavior. For those times, the Invoke Release tools support plugins that can add behavior during the version check,
during the pre-release check, between file changes and commit, between commit and tag/push, and after push.

You specify one or more plugins by using the `plugins` argument to `configure_release_parameters`:

```
from invoke_release.tasks import *
configure_release_parameters(
    module_name='my_service',
    display_name='My Test Service',
    plugins=[
        Plugin1(),
        Plugin2(),
        etc...
    ]
)
```

A plugin must be an instance of a `class` that extends `invoke_release.plugins:AbstractInvokeReleasePlugin`. You can
read the [docstring documentation for this class](python/invoke_release/plugins.py) to learn about the available hooks
and how to implement them. Chances are, though, you can just use one of the built-in plugins, documented below. If you
do create a new plugin, please submit a code review for adding it to this library so that other projects can enjoy it.

### PatternReplaceVersionInFilesPlugin

The name of this plugin should be pretty self-explanatory. Using this plugin, you can tell Invoke Release about other
files that contain the version string pattern that should be updated on release. For example, as a proof-of-concept,
[this library uses the plugin to update the version strings in this documentation](tasks.py).

To use this plugin, just import it, instantiate it, and pass it a list of relative file names whose contents should be
searched and updated:

```
from invoke_release.tasks import *
from invoke_release.plugins import (
    PatternReplaceVersionInFilesPlugin
)
configure_release_parameters(
    module_name='my_service',
    display_name='My Test Service',
    plugins=[
        PatternReplaceVersionInFilesPlugin('.version', 'README.md')
    ]
)
```
