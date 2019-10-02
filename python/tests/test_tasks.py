from __future__ import absolute_import, unicode_literals

from unittest import TestCase

from invoke_release import tasks


class TestTasks(TestCase):
    """
    At a later point, we will write some actual tests. This project is difficult to test with automated tests, and
    we largely rely on manual tests.
    """

    def test_case_sensitive_regular_file_exists(self):
        assert tasks._case_sensitive_regular_file_exists(__file__) is True
        assert tasks._case_sensitive_regular_file_exists(__file__.upper()) is False
        assert tasks._case_sensitive_regular_file_exists(__file__ + '.bogus') is False

    def test_get_version_element_to_bump_if_any_chooses_major_version_if_a_major_commit_is_present(self):

        changelog_message = [
            '- [PATCH] A patch-commit message.\n',
            '- [MINOR] A minor-commit message.\n',
            '- [MAJOR] A major-commit message.\n',
        ]

        version_element_to_bump = tasks._get_version_element_to_bump_if_any(changelog_message)

        assert version_element_to_bump == tasks.MAJOR_VERSION_PREFIX

    def test_get_version_element_to_bump_if_any_chooses_minor_if_only_a_minor_commit_is_present(self):

        changelog_message = [
            '- [MINOR] A minor-commit message.\n',
        ]

        version_element_to_bump = tasks._get_version_element_to_bump_if_any(changelog_message)

        assert version_element_to_bump == tasks.MINOR_VERSION_PREFIX

    def test_get_version_element_to_bump_if_any_returns_none_if_a_commit_doesnt_have_tag_and_there_is_no_major(self):

        changelog_message = [
            '- [MINOR] A minor-commit message.\n',
            'A commit message [PATCH] with a tag in between.\n',
        ]

        version_element_to_bump = tasks._get_version_element_to_bump_if_any(changelog_message)

        assert version_element_to_bump is None

    def test_get_version_element_to_bump_if_any_returns_major_if_commit_does_not_have_tag_but_there_is_a_major(self):

        changelog_message = [
            'A commit message with no tag.\n',
            '- [MAJOR] A minor-commit message.\n',
        ]

        version_element_to_bump = tasks._get_version_element_to_bump_if_any(changelog_message)

        assert version_element_to_bump == tasks.MAJOR_VERSION_PREFIX

    def test_suggest_version_suggests_a_patch_bump_for_patch_tag(self):

        current_version = '1.2.3'

        suggested_version = tasks._suggest_version(current_version, tasks.PATCH_VERSION_PREFIX)

        assert suggested_version == '1.2.4'

    def test_suggest_version_suggests_a_minor_bump_successfully_if_metadata_is_present_for_minor_tag(self):

        current_version = '1.2.3+meta.data'

        suggested_version = tasks._suggest_version(current_version, tasks.MINOR_VERSION_PREFIX)

        assert suggested_version == '1.3.0'

    def test_suggest_version_suggests_a_major_bump_if_metadata_and_prerelease_info_is_present_for_major_Tag(self):

        current_version = '1.2.3-pre.release+meta.data'

        suggested_version = tasks._suggest_version(current_version, tasks.MAJOR_VERSION_PREFIX)

        assert suggested_version == '2.0.0'

    def test_suggest_version_suggests_minor_bump_for_major_version_zero_and_major_tag(self):

        current_version = '0.50.1'

        suggested_version = tasks._suggest_version(current_version, tasks.MAJOR_VERSION_PREFIX)

        assert suggested_version == '0.51.0'

    def test_suggest_version_suggests_patch_bump_for_major_version_zero_and_patch_bump(self):

        current_version = '0.50.1'

        suggested_version = tasks._suggest_version(current_version, tasks.PATCH_VERSION_PREFIX)

        assert suggested_version == '0.50.2'

    def test_suggest_version_returns_none_if_no_version_to_bump_is_provided(self):

        current_version = '2.50.1'

        suggested_version = tasks._suggest_version(current_version, None)

        assert suggested_version is None
