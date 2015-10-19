# Eventbrite Command Line Release Tools ("Invoke Release")

The Invoke Release tools are a set of command line tools that help Eventbrite engineers release services and libraries
quickly, easily, and in a consistent manner. It ensures that the version standards for our projects are the same
across all projects, and minimizes the possible errors that can occur during a release. This documentation is broken
down into two sections:

* [Using Invoke Release on Existing Projects](#using-invoke-release-on-existing-projects)
* [Integrating Invoke Release into Your Project](#integrating-invoke-release-into-your-project)

## Using Invoke Release on Existing Projects

If a project already has support for Invoke Release, using it is easy. If you've never run Invoke Release before,
you first need to install it. To do so, run the following command _on your development machine_ (**not** within Vagrant
or a Docker container).

```
$ sudo pip install -U git+ssh://git@github.com/eventbrite/invoke-release.git
```

If you need to specify an exact version, you can use a tag (replacing the tag name as necessary):

```
$ sudo pip install -U git+ssh://git@github.com/eventbrite/invoke-release.git@0.7.0
```

You can confirm that the project and its requirements were successfully installed by checking the version (this
must be executed from the home directory of the project that already has Invoke Release support):

```
$ invoke --version
Invoke 0.11.1
$ invoke version
Eventbrite Command Line Release Tools ("Invoke Release") 0.7.0
EB Common 1.8.2
```

Once installed, all you have to do is execute it from the project's home directory and follow
the on-screen instructions:

```
$ invoke release
```

It's that easy! You can also view a list of commands or view help for a command as follows:

```
$ invoke --list
$ invoke --help release
```

## Integrating Invoke Release into Your Project

If you have created a new Eventbrite service or library, or you're improving an old one without Invoke Release support,
integrating Invoke Release is easy.

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
Eventbrite Command Line Release Tools ("Invoke Release") 0.7.0
EB Common 1.8.2
```

Finally, commit these changes to your project and push to remote master. You are now ready to run Invoke Release using
the steps in [the previous section](#using-invoke-release-on-existing-projects).
