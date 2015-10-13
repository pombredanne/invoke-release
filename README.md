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

In the root directory of your project, create a file named `tasks.py` and give it the following contents:

```
from invoke_release.tasks import *
configure_release_parameters(module_name='my_project_python_home_module', display_name='My Project Display Name')
```

For example, here are the contents of this file for EB Common and Geo Service, respectively:

```
from invoke_release.tasks import *
configure_release_parameters(module_name='ebcommon', display_name='EB Common')
```

```
from invoke_release.tasks import *
configure_release_parameters(module_name='geo_service', display_name='Geo Service')
```

Commit these changes to your project and push to remote master. You are now ready to run Invoke Release using
the steps in the previous section.
