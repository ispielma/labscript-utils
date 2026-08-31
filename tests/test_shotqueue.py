import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qtutils.qt.QtCore import Qt
from qtutils.qt.QtGui import QColor
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
