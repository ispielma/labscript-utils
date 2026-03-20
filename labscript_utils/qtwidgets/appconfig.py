#####################################################################
#                                                                   #
# appconfig.py                                                      #
#                                                                   #
# Copyright 2026, The labscript suite contributors                  #
#                                                                   #
# This file is part of the labscript suite (see                     #
# http://labscriptsuite.org) and is licensed under the Simplified   #
# BSD License. See the license.txt file in the root of the project  #
# for the full license.                                             #
#                                                                   #
#####################################################################
"""Small Qt helpers for app-specific configuration save/load actions."""
import os
from pathlib import Path
from qtutils import inmain_decorator
from qtutils.qt import QtWidgets


def normalize_dialog_path(selection, suffix=None):
    """Return an absolute path from a QFileDialog result, or ``None`` on cancel."""
    if isinstance(selection, tuple):
        selection, _ = selection
    if not selection:
        return None
    path = os.path.abspath(selection)
    if suffix:
        current_path = Path(path)
        if current_path.suffix.lower() != suffix.lower():
            path = str(current_path.with_suffix(suffix))
    return path


def normalize_dialog_paths(selection):
    """Return absolute paths from a multi-file dialog result."""
    if isinstance(selection, tuple):
        selection, _ = selection
    return [os.path.abspath(path) for path in selection]


def select_open_file(parent, title, directory, file_filter):
    """Open a file-selection dialog and return an absolute path or ``None``."""
    return normalize_dialog_path(
        QtWidgets.QFileDialog.getOpenFileName(parent, title, directory, file_filter)
    )


def select_open_files(parent, title, directory, file_filter):
    """Open a multi-file dialog and return absolute paths."""
    return normalize_dialog_paths(
        QtWidgets.QFileDialog.getOpenFileNames(parent, title, directory, file_filter)
    )


def select_save_file(parent, title, directory, file_filter, suffix=None):
    """Open a save-file dialog and return an absolute path or ``None``."""
    return normalize_dialog_path(
        QtWidgets.QFileDialog.getSaveFileName(parent, title, directory, file_filter),
        suffix=suffix,
    )


def select_directory(parent, title, directory):
    """Open a directory-selection dialog and return an absolute path or ``None``."""
    return normalize_dialog_path(
        QtWidgets.QFileDialog.getExistingDirectory(parent, title, directory)
    )


@inmain_decorator()
def error_dialog(parent, title, message):
    """Show a modal warning dialog in the main GUI thread."""
    QtWidgets.QMessageBox.warning(parent, title, message)


@inmain_decorator()
def question_dialog(parent, title, message):
    """Ask a yes/no question in the main GUI thread and return ``True`` on yes."""
    reply = QtWidgets.QMessageBox.question(
        parent,
        title,
        message,
        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
    )
    return reply == QtWidgets.QMessageBox.Yes


def select_config_file(parent, title, default, file_filter, save):
    """Return an absolute path chosen through a Qt open/save file dialog."""
    chooser = select_save_file if save else select_open_file
    return chooser(parent, title, default, file_filter)

class AppConfigActions:
    """Shared QAction plumbing for app-specific save/load configuration code."""
    def __init__(self, parent, config_name, default_save_path_getter, save_action,
                 save_as_action, load_action, revert_action, get_save_data,
                 save_configuration, load_configuration, error_dialog,
                 default_load_path_getter=None):
        self.parent = parent
        self.config_name = config_name
        self.default_save_path_getter = default_save_path_getter
        self.default_load_path_getter = default_load_path_getter or default_save_path_getter
        self.save_action = save_action
        self.save_as_action = save_as_action
        self.revert_action = revert_action
        self.get_save_data = get_save_data
        self.save_configuration = save_configuration
        self.load_configuration = load_configuration
        self.error_dialog = error_dialog
        self.last_save_config_file = None
        self.last_save_data = None
        self.save_as_action.setEnabled(True)
        save_action.triggered.connect(self.on_save_configuration_triggered)
        save_as_action.triggered.connect(self.on_save_configuration_as_triggered)
        load_action.triggered.connect(self.on_load_configuration_triggered)
        revert_action.triggered.connect(self.on_revert_configuration_triggered)

    def mark_clean(self, save_file, save_data):
        """Record the last saved configuration path and data."""
        self.last_save_config_file = save_file
        self.last_save_data = save_data
        self.save_action.setText('Save configuration %s' % save_file)
        self.save_as_action.setEnabled(True)
        self.revert_action.setEnabled(True)

    def prompt_to_save_if_dirty(self, title, message):
        """Return whether a pending action should continue after a save prompt."""
        save_data = self.get_save_data()
        if self.last_save_data is None or save_data == self.last_save_data:
            return True
        reply = QtWidgets.QMessageBox.question(self.parent, title, message,
                                               QtWidgets.QMessageBox.Yes
                                               | QtWidgets.QMessageBox.No
                                               | QtWidgets.QMessageBox.Cancel)
        if reply == QtWidgets.QMessageBox.Cancel:
            return False
        if reply == QtWidgets.QMessageBox.Yes:
            self.save_configuration(self.last_save_config_file)
        return True

    def on_save_configuration_triggered(self):
        """Save to the current target or fall back to Save As."""
        if self.last_save_config_file is None:
            self.on_save_configuration_as_triggered()
        else:
            self.save_configuration(self.last_save_config_file)

    def on_save_configuration_as_triggered(self):
        """Prompt for a save target and save the current configuration."""
        save_file = select_config_file(self.parent,
                                       'Select  file to save current %s' % self.config_name,
                                       self.last_save_config_file or self.default_save_path_getter(),
                                       "Config files (*.toml)", save=True)
        if save_file is not None:
            self.save_configuration(save_file)

    def on_load_configuration_triggered(self):
        """Prompt for a configuration file and load it."""
        if not self.prompt_to_save_if_dirty(
            'Load configuration',
            "Current configuration has changed: save config file '%s'?"
            % self.last_save_config_file):
            return
        filename = select_config_file(self.parent,
                                      'Select %s file to load' % self.config_name,
                                      self.last_save_config_file or self.default_load_path_getter(),
                                      "Config files (*.toml *.ini)", save=False)
        if filename is not None:
            self.load_configuration(filename)

    def on_revert_configuration_triggered(self):
        """Prompt to revert to the last saved configuration."""
        save_data = self.get_save_data()
        if self.last_save_data is None or save_data == self.last_save_data:
            self.error_dialog('no changes to revert')
            return
        reply = QtWidgets.QMessageBox.question(self.parent, 'Load configuration',
                                               "Revert configuration to the last saved state in '%s'?"
                                               % self.last_save_config_file,
                                               QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.Cancel)
        if reply == QtWidgets.QMessageBox.Yes:
            self.load_configuration(self.last_save_config_file)
