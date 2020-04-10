Changelog
=========

5.0.0-beta1 (2020-04-07)
------------------------
- [MAJOR] Invoke Release now runs only on Python 3.7+. It can still release projects that use Python 2, but the ``invoke release`` commands must run on Python 3.7+.
- [MAJOR] Removed ``invoke wheel`` command.
- [MAJOR] Renamed plugin method ``version_error_check`` to ``error_check`` because it had nothing to do with versions.
- [MINOR] ``configure_release_parameters`` is deprecated. Please use ``invoke_release.config.config.configure``, instead.
- [MINOR] Performed a major refactor and re-organization of all internal code.
- [MINOR] Added Python type annotations.
- [MINOR] Added the option of supporting other source control providers in the future.
- [MINOR] Converted to a proper configuration system instead of saving config variables to individual global variables.
- [PATCH] Added considerable test coverage (>96% lines covered now)
- [PATCH] ReadTheDocs documentation.
- [MINOR] Fix #37

4.5.2 (2020-03-31)
------------------
- [PATCH] Properly handle + separator added in previous commit

4.5.1 (2020-03-31)
------------------
- [PATCH] Permit a + in the release version specifier

4.5.0 (2020-01-15)
------------------
- [PATCH] Fix GitHub PRs workflow when not pushing branch  (#33)
- [MINOR] Use parse_version instead of LooseVersion to properly compare versions

4.4.3 (2019-12-02)
------------------
- [PATCH] Fix title on PR creation (#31)

4.4.2 (2019-10-22)
------------------
- Fix open pr (#29)

4.4.1 (2019-10-21)
------------------
- [PATCH] Undo branch name changes
- [PATCH] Avoid re-checking out to the original branch if that branch is ``master``

4.4.0 (2019-10-17)
------------------
- Ensure the local ``invoke-release-{}-{}`` branch is deleted after pushhing it to ``origin``
- over idented
- addressed comments
- code refactor && fetching repo owner and name
- code refactor && fetching repo owner and name
- code refactor && fetching repo owner and name
- better error handling
- refactoring to avoid adding a new dependency
- comments addressed
- add requests dep
- check env token
- fixxes
- open PR
- WIP

4.3.0 (2019-10-02)
------------------
- Improve ``invoke release`` workflow by suggesting a version to bump to. (#18)
- Fix: When using PRs it should go back to the current_branch instead of master.
- [PATCH] Fix typo in cherry-pick prompt message (#17)

4.2.0 (2019-09-12)
------------------
- [MINOR] Automate creation of branch for cherry-picks/fixes.
- [PATCH] Exit with error message if creating a local tracking branch fails.
- [MINOR] Add support to invoke branch for pull request workflow
- [PATCH] Add Python 3.7 testing to CI

4.1.0 (2019-07-18)
------------------
- [MINOR] Add support for pushing to a branch and not tag
  Some projects don't support pushing directly to master without going through a pull request. This new flow, if configured (the existing flow is unchanged), will:
  - Create a branch named ``invoke-release-<base branch>-<new_version>``
  - Push the branch to origin
  - Not create a tag
  A future change will add support for automatically creating the pull request. Users of this flow will typically create some kind of build bot that will verify the pull request, automatically merge it, and create and push a tag.

4.0.5 (2018-11-07)
------------------
- [PATCH] Peg wheel to 0.31.1 due to breaking change with archive module (#6)

4.0.4 (2018-03-02)
------------------
- Preserve changelog blank lines smartly

4.0.3 (2018-01-26)
------------------
- Fix another problem in setup

4.0.2 (2018-01-26)
------------------
- Improve how Travis deploys new releases
- Fix setup details so that it installs correctly and displays correctly on PyPi
- Ignore pull requests merged in changelogs

4.0.1 (2018-01-26)
------------------
- Add entire changelog to annotated release tag message
- Fix problems that caused build to fail

4.0.0 (2018-01-26)
------------------
- Complete Python 3 compatibility, ensuring end-to-end unicode
- Add ability to sign release tags for increased security
- Relax requirements for versions to permit alphanumeric qualifier suffixes after the patch version
- Relax requirements for version branches, rigidify requirements for version numbers released from version branches
- Support ``CHANGELOG.md`` and ``CHANGELOG.rst`` in addition to ``CHANGELOG.txt``
- Improve wording of some prompts and messages to reduce confusion
- Prepare for open sourcing so that it can be used with our open source projects, like Conformity and PySOA
- Ensure we use colons consistently at the end of all prompts
- Ensure we can roll back partial releases that failed before completing
- Add Travis build and Travis secret for automatically deploying new releases to PyPi

3.0.0 (2017-03-17)
------------------
- Made Python 3 compatible
- Fixed bug in ``rollback_release`` preventing it from working
- Fixed bug in ``setup.py`` preventing it from installing
- Added a ``build_wheel`` task

2.0.0 (2016-10-18)
------------------
- Adding support for storing version in plain text version.txt

1.4.0 (2016-08-17)
------------------
- Add new task for creating patching branches from release tags

1.3.2 (2016-08-15)
------------------
- Make ``invoke release`` work with $EDITOR with params

1.3.1 (2016-06-17)
------------------
- Fixed the install requires that does not work on all machines

1.3.0 (2016-06-17)
------------------
- Support the latest version of Invoke, which requires context arguments for tasks

1.2.1 (2016-01-22)
------------------
- Fixed a bug Senna discovered: If path to Vim doesn't exist, a different error is thrown.

1.2.0 (2016-01-21)
------------------
- Fixed issue with release tool using vi instead of vim by default and vi being linked differently in path
  - Changed the default from ``vi`` to ``vim``, because it has been established that a ``vi`` command linked to a non-``vim`` executable doesn't work.
  - Added the ability to specify an Invoke Release-specific editor environmental variable that doesn't conflict with other applications' use of ``$EDITOR``.
  - Added exception checking to suggest using the environmental variable if an editor fails to launch.
  - Improved error messages for other command error messages, because ``CalledProcessError`` never has a value for ``e.message``.

1.1.1 (2015-12-09)
------------------
- Made file exist checks case-sensitive, because Git is always case sensitive, even though Mac OS X's file system isn't. As a result, if the file was named ``CHANGELOG.TXT``, and the release tool called ``git add CHANGELOG.txt``, Git would silently fail to add the file without any error codes, and the release tool would incorrectly succeed with a partial release.
- Fixed a typo in the changelog editor comments.

1.1.0 (2015-11-19)
------------------
- Add changelog details to commit release message
- Updated release tool to work with branches other than master
- Refactored to use ``{}`` / ``format`` instead of ``%s`` / ``%`` and fixed a bug with the new changelog feature
- Improved changelog feature to accept built-up changelog, gather commit messages, edit message in advanced editor
- Added support for plugins that can execute hooks at various stages of the release lifecycle
- Updated tool to fail more cleanly instead of erroring out on problems, check if tag already exists before releasing

1.0.3 (2015-10-22)
------------------
- Fixed errors that appeared if called from subdirectory.

1.0.2 (2015-10-23)
------------------
No release version exits nicely instead of erroring.

1.0.1 (2015-10-22)
------------------
- Improved the main documentation.
- Added flake8 ignore instructions.
- Changed the version and changelog writers to not strip whitespace on the beginning of lines.

1.0.0 (2015-10-19)
------------------
- Added support for rolling back between commit and push stages when executing release.
- Added support for executing rollback_release.
- Improved output formatting.
- Included color support for different output message types.
- Added check to ensure that new version number is greater than existing version number during release.

0.7.0 (2015-10-19)
------------------
- Fixed a bug in ``python_directory`` customization.

0.6.0 (2015-10-13)
------------------
- Added missing install requirement.

0.5.0 (2015-10-13)
------------------
- Added a version command to the available commands.
- Made significant improvements to documentation.

0.4.0 (2015-10-13)
------------------
- Added requirements and documentation.

0.3.0 (2015-10-13)
------------------
- Back-added old changelog message.
- Improved changelog output format.

0.2.0 (2015-10-13)
------------------
- Created new reusable command-line release tool for Eventbrite libraries and services.
- Improved language, spelling, and grammar on output messages.
- Added support for additional exit points and multi-line changelog messages.
- Fixed bugs from version 0.1.0.

0.1.0 (2015-10-13)
------------------
- Initial test release.
