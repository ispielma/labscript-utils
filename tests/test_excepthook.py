"""Tests for the graphical error dialog's opt-out.

The opt-out is a fork addition and had no coverage at all. It is worth some,
because it is the switch every test run in the suite depends on to stay silent,
and because getting it wrong is invisible: the failure mode is a dialog that
does not appear when someone asked for one, or windows appearing during a test
run that was supposed to be quiet.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import labscript_utils.excepthook as excepthook


class TestEnvironmentFlag(object):
    """``LABSCRIPT_NO_ERROR_DIALOG`` says whether to suppress the dialog."""

    def test_unset_leaves_the_dialog_enabled(self):
        assert excepthook._no_error_dialog_from_env({}) is False

    def test_values_that_read_as_false_leave_the_dialog_enabled(self):
        # '0' is the one that matters: it used to suppress the dialog, which is
        # the opposite of what anyone writing it intends.
        for value in ['', '0', 'false', 'no', 'off']:
            environ = {'LABSCRIPT_NO_ERROR_DIALOG': value}
            assert excepthook._no_error_dialog_from_env(environ) is False, value

    def test_values_that_read_as_true_suppress_the_dialog(self):
        for value in ['1', 'true', 'yes', 'on']:
            environ = {'LABSCRIPT_NO_ERROR_DIALOG': value}
            assert excepthook._no_error_dialog_from_env(environ) is True, value

    def test_case_and_surrounding_whitespace_do_not_matter(self):
        for value in [' FALSE ', 'No', 'Off', '\t0\n']:
            environ = {'LABSCRIPT_NO_ERROR_DIALOG': value}
            assert excepthook._no_error_dialog_from_env(environ) is False, value

    def test_an_unrecognised_value_suppresses_the_dialog(self):
        # Erring towards silence: an unparseable value in a CI environment
        # should not start spawning windows.
        environ = {'LABSCRIPT_NO_ERROR_DIALOG': 'quiet please'}
        assert excepthook._no_error_dialog_from_env(environ) is True

    def test_the_conftest_setting_used_across_the_suite_suppresses_it(self):
        # Every tests/conftest.py in the suite, and .claude/settings.json, set
        # '1'. If that ever stopped suppressing, every test run would start
        # putting windows on screen.
        environ = {'LABSCRIPT_NO_ERROR_DIALOG': '1'}
        assert excepthook._no_error_dialog_from_env(environ) is True


class TestTheFlagIsReadWhenUsed(object):
    """The documented escape hatch is assigning to the module attribute."""

    def test_tkhandler_consults_the_attribute_rather_than_a_captured_value(self):
        """A test *of* the dialog sets NO_ERROR_DIALOG and gets a dialog.

        This is the case the environment variable deliberately cannot express,
        so it has to keep working. If someone captures the flag at import, or
        hoists the read out of ``tkhandler``, this fails.

        ``reraise=False`` keeps sys.__excepthook__ from printing the traceback,
        and the whole subprocess module is stood in for rather than its Popen
        attribute patched, so nothing here can spawn a window.
        """
        spawned = []

        class FakePopen(object):
            def __init__(self, *args, **kwargs):
                spawned.append(args)

            def poll(self):
                return None

        class FakeSubprocess(object):
            Popen = FakePopen

        saved_flag = excepthook.NO_ERROR_DIALOG
        saved_subprocess = excepthook.subprocess
        saved_children = list(excepthook.child_processes)
        saved_logger = excepthook.l.logger
        excepthook.subprocess = FakeSubprocess
        excepthook.l.logger = None
        try:
            excepthook.NO_ERROR_DIALOG = True
            excepthook.tkhandler(ValueError, ValueError('quiet'), None, reraise=False)
            assert spawned == [], 'suppressed, so nothing should be spawned'

            excepthook.NO_ERROR_DIALOG = False
            excepthook.tkhandler(ValueError, ValueError('loud'), None, reraise=False)
            assert len(spawned) == 1, 'the dialog was asked for and not shown'
        finally:
            excepthook.subprocess = saved_subprocess
            excepthook.NO_ERROR_DIALOG = saved_flag
            excepthook.child_processes[:] = saved_children
            excepthook.l.logger = saved_logger
