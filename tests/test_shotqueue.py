import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qtutils.qt.QtCore import Qt
from qtutils.qt.QtGui import QColor, QPalette
from qtutils.qt.QtWidgets import QApplication

from labscript_utils.qtwidgets.shotqueue import ShotQueueWidget


_qapplication = None


def make_widget():
    global _qapplication
    if QApplication.instance() is None:
        # Held for the life of the process: a QApplication that is garbage
        # collected takes every widget built under it down with it.
        _qapplication = QApplication([])
    return ShotQueueWidget(column_titles=['Mode', 'Shot file'], path_column=1)


def row_backgrounds(widget, row):
    model = widget.queue_model
    return [
        model.item(row, column).data(Qt.BackgroundRole)
        for column in range(model.columnCount())
    ]


def test_row_background_colours_every_column_of_that_row():
    widget = make_widget()
    widget.set_row_infos(
        [
            {'path': '/tmp/shot_a.h5', 'background': QColor('#ccffcc')},
            {'path': '/tmp/shot_b.h5'},
        ]
    )
    coloured = row_backgrounds(widget, 0)
    assert all(brush is not None for brush in coloured)
    assert all(brush.color() == QColor('#ccffcc') for brush in coloured)
    assert all(brush is None for brush in row_backgrounds(widget, 1))


def row_fonts(widget, row):
    return [
        widget.queue_model.item(row, column).font()
        for column in range(widget.queue_model.columnCount())
    ]


def test_a_struck_out_row_is_struck_out_in_every_column():
    # A row the operator has asked to be rid of, which cannot simply be removed
    # because something else may still be using its file. Struck through says
    # both halves at once: it is still here, and it is finished with.
    widget = make_widget()
    widget.set_row_infos(
        [
            {'path': '/tmp/shot_a.h5', 'strikeout': True},
            {'path': '/tmp/shot_b.h5'},
        ]
    )
    assert all(font.strikeOut() for font in row_fonts(widget, 0))
    assert not any(font.strikeOut() for font in row_fonts(widget, 1))


def luminance(colour):
    return (
        0.2126 * colour.redF() + 0.7152 * colour.greenF() + 0.0722 * colour.blueF()
    )


DARK_THEME = {
    'Base': '#232323',
    'Text': '#dddddd',
    'Window': '#2b2b2b',
    'WindowText': '#dddddd',
    # Below Base, which is where a dark theme puts it and the whole point of
    # this test: a rule drawn in Dark is then invisible on the list.
    'Dark': '#191919',
    'Mid': '#3a3a3a',
    'Shadow': '#000000',
}


def test_the_rule_under_a_row_is_visible_on_a_dark_theme():
    # It marks a row off from those below it, so a rule nobody can see is the
    # same as no rule. It has to hold up whichever way round the theme is, and
    # the frame roles do not: Dark is defined relative to Window and a dark
    # theme puts it below Base, four hundredths of a luminance apart from the
    # list it would be drawn on.
    widget = make_widget()
    application = QApplication.instance()
    saved = application.palette()
    palette = QPalette(saved)
    for role, value in DARK_THEME.items():
        palette.setColor(getattr(QPalette.ColorRole, role), QColor(value))
    application.setPalette(palette)
    try:
        widget.set_row_infos(
            [
                {'path': '/tmp/shot_a.h5', 'rule_below': True},
                {'path': '/tmp/shot_b.h5'},
            ]
        )
        widget.resize(400, 80)
        widget.show()
        application.processEvents()

        view = widget.queue_view
        image = view.viewport().grab().toImage()
        # grab() returns device pixels while visualRect returns logical ones,
        # and on a retina screen those differ by a factor of two. Reading the
        # image at logical coordinates sampled a row well above the rule, found
        # two identical pixels and reported a contrast of exactly zero -- so
        # the test passed or failed according to which display the window
        # happened to open on, which is no test at all.
        scale = image.devicePixelRatio() or 1
        first = view.visualRect(widget.queue_model.index(0, widget.path_column))
        second = view.visualRect(widget.queue_model.index(1, widget.path_column))
        x = int(first.center().x() * scale)
        background = QColor(image.pixel(x, int(second.center().y() * scale)))
        contrast = max(
            abs(luminance(QColor(image.pixel(x, int(y * scale)))) - luminance(background))
            for y in range(first.bottom() - 1, first.bottom() + 2)
        )
    finally:
        application.setPalette(saved)

    assert contrast > 0.15, (
        'the rule is %.3f in luminance from the rows it separates, which is '
        'not a line anybody can see' % contrast
    )
