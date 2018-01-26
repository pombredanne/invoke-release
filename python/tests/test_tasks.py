from __future__ import absolute_import, unicode_literals

from unittest import TestCase

from invoke_release import tasks


class TestTasks(TestCase):
    """
    At a later point, we will write some actual tests. This project is difficult to test with automated tests, and
    we largely rely on manual tests.
    """

    def test_case_sensitive_regular_file_exists(self):
        self.assertTrue(tasks._case_sensitive_regular_file_exists(__file__))
        self.assertFalse(tasks._case_sensitive_regular_file_exists(__file__.upper()))
        self.assertFalse(tasks._case_sensitive_regular_file_exists(__file__ + '.bogus'))
