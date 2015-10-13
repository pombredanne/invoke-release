# Eventbrite Command Line Release Tools ("Invoke Release")

## Using Invoke Release on Existing Projects

If a project already has support for Invoke Release, using it is easy. If you've never run Invoke Release before,
you first need to install it. To do so, run the following command _on your development machine_ (**not** within Vagrant
or a Docker container).

```
$ pip install -U git+ssh://git@github.com/eventbrite/invoke-release.git
```

If you need to specify an exact version, you can use a tag (replacing the tag name as necessary):

```
$ pip install -U git+ssh://git@github.com/eventbrite/invoke-release.git@0.4.0
```

Then, once installed, all you have to do is execute it from the project's home directory and follow
the on-screen instructions:

```
$ invoke release
```

It's that easy!

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

This assumes that the default Python source directory in your project is `python/` relative to the
project root directory. This is often true only for libraries. For services or other projects not meeting this
pattern, you can use the optional `python_directory` function argument to customize this.

For example, here are the contents of this file for EB Common and Geo Service, respectively:

```
from invoke_release.tasks import *
configure_release_parameters(
    module_name='ebcommon',
    display_name='EB Common'
)
```

```
from invoke_release.tasks import *
configure_release_parameters(
    module_name='geo_service',
    display_name='Geo Service',
    python_directory='geo_service'
)
```

Commit these changes to your project and push to remote master. You are now ready to run Invoke Release using
the steps in the previous section.
