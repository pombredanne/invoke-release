from __future__ import absolute_import, unicode_literals

import codecs
import os

from invoke_release.tasks import ReleaseFailure


class AbstractInvokeReleasePlugin(object):
    def __init__(self, *extra_files_to_commit):
        self.__extra_files_to_commit = extra_files_to_commit or []

    def get_extra_files_to_commit(self, root_directory):
        """
        Yields an iterator of all the files this plugin has modified (if any) that should be committed (or rolled back,
        as the case may be). This method can (and should) also be used by hook methods in the plugin when iterating
        over the files and modifying them (if applicable). The file names this method returns are absolute file names,
        created by comining the provided relative file names with the `root_directory` argument.

        :param root_directory: The root project directory to combine with the provided relative file names.
        :type root_directory: str | unicode

        :return: An iterator of all the files modified by this plugin.
        :rtype: types.GeneratorType
        """
        for file_name in self.__extra_files_to_commit:
            yield os.path.join(root_directory, file_name)

    def version_error_check(self, root_directory):
        """
        Invokes a hook for checking error states during `invoke version` calls. Commonly used to warn the user about
        incorrectly configured plugins. Returns a list of error strings, each to be printed as a separate error on
        a new line.

        :param root_directory: The root project directory
        :type root_directory: str | unicode
        :return: A list of error messages, or None or [] if no error messages.
        :rtype: list
        """
        pass

    def pre_release(self, root_directory, old_version):
        """
        Invokes a pre-release hook to execute tasks before the user is prompted for a new version or changelog message.
        Commonly used to run pre-release checks and fail the release if some condition is met or not met.

        :param root_directory: The root project directory
        :type root_directory: str | unicode
        :param old_version: The version of the project before release
        :type old_version: str | unicode
        :raise: ReleaseFailure
        """
        errors = self.version_error_check(root_directory)
        if errors:
            import pprint
            raise ReleaseFailure(
                'The {plugin_class} plugin generated the following errors:\n{errors}'.format(
                    plugin_class=self.__class__.__name__,
                    errors=pprint.pformat(errors),
                )
            )

    def pre_commit(self, root_directory, old_version, new_version):
        """
        Invokes a post-commit hook to execute tasks after a user has entered a new version and changelog message, but
        before any changes are committed. Commonly used to modify files to be included in the release commit.

        :param root_directory: The root project directory
        :type root_directory: str | unicode
        :param old_version: The version of the project before release
        :type old_version: str | unicode
        :param new_version: The version of the project after release
        :type new_version: str | unicode
        :raise: ReleaseFailure
        """
        pass

    def pre_push(self, root_directory, old_version, new_version):
        """
        Invokes a pre-push hook to execute tasks after the release commit has been completed but before the tag is
        created or the changes pushed.

        :param root_directory: The root project directory
        :type root_directory: str | unicode
        :param old_version: The version of the project before release
        :type old_version: str | unicode
        :param new_version: The version of the project after release
        :type new_version: str | unicode
        :raise: ReleaseFailure
        """
        pass

    def post_release(self, root_directory, old_version, new_version, pushed_or_rolled_back):
        """
        Invokes a post-release hook to execute tasks after the release has completed or rolled back. Will not be called
        if the release is halted due to a `ReleaseFailure` or premature exit.

        :param root_directory: The root project directory
        :type root_directory: str | unicode
        :param old_version: The version of the project before release
        :type old_version: str | unicode
        :param new_version: The version of the project after release
        :type new_version: str | unicode
        :param pushed_or_rolled_back: A flag indicating whether the release was pushed, rolled back, or not pushed.
                                      Valid return values are integer constants PUSH_RESULT_NO_ACTION,
                                      PUSH_RESULT_PUSHED, and PUSH_RESULT_ROLLBACK.
        :type pushed_or_rolled_back: int
        """
        pass

    def pre_rollback(self, root_directory, current_version):
        """
        Invokes a pre-rollback hook to execute tasks before a call to `rollback-release` proceeds. Can be used to run
        pre-rollback checks and cancel the rollback if some condition is met or not met.

        :param root_directory: The root project directory
        :type root_directory: str | unicode
        :param current_version: The version of the project before rollback
        :type current_version: str | unicode
        :raise: ReleaseFailure
        """
        pass

    def post_rollback(self, root_directory, current_version, rollback_to_version):
        """
        Invokes a post-rollback hook to execute tasks after a call to `rollback-release` has succeeded. Will not be
        called if the task fails or is canceled for any reason.

        :param root_directory: The root project directory
        :type root_directory: str | unicode
        :param current_version: The version of the project before rollback
        :type current_version: str | unicode
        :param rollback_to_version: The version of the project after rollback
        :type rollback_to_version: str | unicode
        """
        pass


class PatternReplaceVersionInFilesPlugin(AbstractInvokeReleasePlugin):
    def __init__(self, *files_to_search):
        super(PatternReplaceVersionInFilesPlugin, self).__init__(*files_to_search)

    def version_error_check(self, root_directory):
        file_errors = []
        for file_name in self.get_extra_files_to_commit(root_directory):
            if not os.path.exists(file_name):
                file_errors.append(
                    'The file {file_name} was not found! {plugin_class} is not configured correctly!'.format(
                        file_name=file_name,
                        plugin_class=self.__class__.__name__,
                    )
                )
        return file_errors

    def pre_commit(self, root_directory, old_version, new_version):
        for file_name in self.get_extra_files_to_commit(root_directory):
            contents = []
            with codecs.open(file_name, 'rb', encoding='utf8') as file_read:
                for line in file_read:
                    contents.append(line.rstrip().replace(old_version, new_version))
            with codecs.open(file_name, 'wb', encoding='utf8') as file_write:
                for line in contents:
                    file_write.write(line)
                    file_write.write('\n')
