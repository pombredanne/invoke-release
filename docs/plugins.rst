Creating and Using Invoke Release Plugins
=========================================

In most cases, the default Invoke Release behavior (increment version, update changelog, commit, tag, push) is
complete and sufficient for releasing a new project version. However, sometimes you need more advanced
behavior. For those times, the Invoke Release tools support plugins that can add behavior during the version check,
during the pre-release check, between file changes and commit, between commit and tag/push, and after push.

.. contents:: Contents
    :local:
    :depth: 3
    :backlinks: none

Configuring Plugins
-------------------

You specify one or more plugins by using the ``plugins`` argument to ``config.configure``:

.. code-block:: python

    from invoke_release.config import config
    from invoke_release.tasks import *  # noqa: F401,F403

    from my_plugins import (
        Plugin1,
        Plugin2,
    )

    config.configure(
        module_name='my_library',
        display_name='My Library',
        plugins=[
            Plugin1(),
            Plugin2(),
        ],
    )

A plugin must be an instance of a class that extends ``invoke_release.plugins:AbstractInvokeReleasePlugin``. You can
read the documentation for this class `below <#abstractinvokereleaseplugin-pydoc>`_ to learn about the available hooks
and how to implement them. Chances are, though, you can just use one of the built-in plugins, documented below. If you
do create a new plugin, we encourage you to submit a pull request for adding it to this library so that other projects
can enjoy it.

``PatternReplaceVersionInFilesPlugin``
--------------------------------------

The name of this plugin should be pretty self-explanatory. Using this plugin, you can tell Invoke Release about other
files that contain the version string pattern that should be updated on release. For example, as a proof-of-concept,
`Invoke Releases uses the plugin in its own tasks.py file <https://github.com/eventbrite/invoke-release/blob/master/tasks.py>`_.

To use this plugin, import it, instantiate it, and pass it a list of relative file names whose contents should be
searched and updated:

.. code-block:: python

    from invoke_release.config import config
    from invoke_release.plugins.replace import PatternReplaceVersionInFilesPlugin
    from invoke_release.tasks import *  # noqa: F401,F403

    config.configure(
        module_name='another_library',
        display_name='Another Library',
        plugins=[
            PatternReplaceVersionInFilesPlugin('.version', 'README.md'),
        ],
    )

``AbstractInvokeReleasePlugin`` PyDoc
-------------------------------------

.. autoclass:: invoke_release.plugins.base.AbstractInvokeReleasePlugin

.. autoclass:: invoke_release.plugins.base.ReleaseStatus
