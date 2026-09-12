"""Settings that have to be in place before the modules that read them import.

Running the tests is not supposed to put anything on the screen of whoever runs
them, from either of the two directions it can happen.

``QT_QPA_PLATFORM`` covers rendering. ``test_shotqueue.py`` builds a real
``QApplication`` and shows a widget, because Qt does not lay out or paint a
widget that was never shown, so the pixel measurements that guard the
running-shot rule read nothing without it. The fix for that is not to stop
showing the window. Rendering offscreen is what lets the test go on showing a
real one without it appearing.

``LABSCRIPT_NO_ERROR_DIALOG`` covers the other direction: it stops
``labscript_utils.excepthook`` spawning a tkinter window for every unhandled
exception. Exceptions are still logged and still reach stderr, which is what
you want from a test run anyway.

Both are set here rather than in a fixture because each has to be in place
before the module that reads it is imported -- Qt is imported by qtutils, and
``excepthook`` reads its variable at module scope -- and pytest imports conftest
before the test modules. A conftest is imported by pytest and nothing else, so a
real run of a real application still gets its error dialogs.

``setdefault`` leaves an explicit setting alone, so either can be overridden by
exporting it. Export ``QT_QPA_PLATFORM=cocoa`` to watch a test drive the window,
or ``LABSCRIPT_NO_ERROR_DIALOG=0`` to let the dialog through -- ``''``, ``'0'``,
``'false'``, ``'no'`` and ``'off'`` all mean "leave it enabled", in any case and
ignoring surrounding whitespace.

A test *of* the error dialog is better off setting the flag directly than
arranging the environment around itself. ``excepthook`` consults the environment
once, when it imports, and the handler then reads the module global -- so
assigning that takes effect immediately, while changing the environment
afterwards does nothing:

    import labscript_utils.excepthook as excepthook
    excepthook.NO_ERROR_DIALOG = False

``tests/test_excepthook.py`` covers both, and stubs the subprocess module so it
cannot spawn a window while checking that it would have.
"""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('LABSCRIPT_NO_ERROR_DIALOG', '1')
