#####################################################################
#                                                                   #
# plugins.py                                                        #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of the labscript suite (see                     #
# http://labscriptsuite.org) and is licensed under the Simplified   #
# BSD License. See the license.txt file in the root of the project  #
# for the full license.                                             #
#                                                                   #
#####################################################################
import importlib
import logging
import os
from types import MethodType


DEFAULT_PRIORITY = 10

__all__ = [
    'DEFAULT_PRIORITY',
    'Callback',
    'callback',
    'BasePlugin',
    'MenuBuilder',
    'PluginManager',
]


class Callback(object):
    """Class wrapping a callable. At present only differs from a regular
    function in that it has a "priority" attribute - lower numbers means
    higher priority. If there are multiple callbacks triggered by the same
    event, they will be returned in order of priority by get_callbacks"""
    def __init__(self, func, priority=DEFAULT_PRIORITY):
        self.priority = priority
        self.func = func

    def __get__(self, instance, class_):
        """Make sure our callable binds like an instance method. Otherwise
        __call__ doesn't get the instance argument."""
        if instance is None:
            return self
        else:
            return MethodType(self, instance)

    def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)


class callback(object):
    """Decorator to turn a function into a Callback object. Presently
    optional, and only required if the callback needs to have a non-default
    priority set"""
    # Instantiate the decorator:
    def __init__(self, priority=DEFAULT_PRIORITY):
        self.priority = priority

    # Call the decorator
    def __call__(self, func):
        return Callback(func, self.priority)


class BasePlugin(object):
    """Default no-op implementation of the existing plugin interface."""
    def __init__(self, initial_settings):
        self.initial_settings = initial_settings
        self.menu = None
        self.notifications = {}

    def get_menu_class(self):
        return None

    def get_notification_classes(self):
        return []

    def get_setting_classes(self):
        return []

    def get_callbacks(self):
        return None

    def get_tab_classes(self):
        return {}

    def tabs_created(self, tabs):
        pass

    def set_menu_instance(self, menu):
        self.menu = menu

    def set_notification_instances(self, notifications):
        self.notifications = notifications

    def plugin_setup_complete(self, data=None):
        pass

    def get_save_data(self):
        return {}

    def close(self):
        pass


class MenuBuilder(object):
    """Build menus from the nested dictionary format used by BLACS plugins."""
    def __init__(self, icon_factory=None):
        self.icon_factory = icon_factory

    def create_menu(self, parent, menu_parameters):
        if 'name' in menu_parameters:
            if 'menu_items' in menu_parameters:
                child = parent.addMenu(menu_parameters['name'])
                for child_menu_params in menu_parameters['menu_items']:
                    self.create_menu(child, child_menu_params)
            else:
                if 'icon' in menu_parameters and self.icon_factory is not None:
                    child = parent.addAction(
                        self.icon_factory(menu_parameters['icon']),
                        menu_parameters['name'],
                    )
                else:
                    child = parent.addAction(menu_parameters['name'])

            if 'action' in menu_parameters:
                child.triggered.connect(menu_parameters['action'])

        elif 'separator' in menu_parameters:
            parent.addSeparator()


class PluginManager(object):
    """Manage discovery and setup of plugins using the existing plugin API."""
    def __init__(
        self,
        plugin_package,
        plugins_dir,
        config,
        config_section,
        default_plugins=(),
        logger=None,
    ):
        self.plugin_package = plugin_package
        self.plugins_dir = plugins_dir
        self.config = config
        self.config_section = config_section
        self.default_plugins = set(default_plugins)
        self.logger = logger or logging.getLogger(__name__)
        self.modules = {}
        self.plugins = {}

    def discover_modules(self):
        if not self.config.has_section(self.config_section):
            self.config.add_section(self.config_section)

        configured_plugins = set(
            name for name, val in self.config.items(self.config_section)
        )

        modules = {}
        for module_name in os.listdir(self.plugins_dir):
            module_path = os.path.join(self.plugins_dir, module_name)
            if not os.path.isdir(module_path) or module_name == '__pycache__':
                continue

            # If this is a new plugin, add it to the config.
            if module_name not in configured_plugins:
                self.config.set(
                    self.config_section,
                    module_name,
                    str(module_name in self.default_plugins),
                )
                configured_plugins.add(module_name)

            # Only load activated plugins.
            if self.config.getboolean(self.config_section, module_name):
                try:
                    module = importlib.import_module(
                        self.plugin_package + '.' + module_name
                    )
                except Exception:
                    self.logger.exception(
                        "Could not import plugin '%s'. Skipping." % module_name
                    )
                else:
                    modules[module_name] = module

        self.modules = modules
        return modules

    def instantiate_plugins(self, plugin_settings=None):
        if plugin_settings is None:
            plugin_settings = {}

        plugins = {}
        for module_name, module in self.modules.items():
            try:
                plugins[module_name] = module.Plugin(
                    plugin_settings[module_name]
                    if module_name in plugin_settings else {}
                )
            except Exception:
                self.logger.exception(
                    "Could not instantiate plugin '%s'. Skipping" % module_name
                )

        self.plugins = plugins
        return plugins

    def create_tabs(self, tab_widget, settings_dict, tablist, settings, tab_data):
        for module_name, plugin in self.plugins.items():
            try:
                if hasattr(plugin, 'get_tab_classes'):
                    tab_dict = {}

                    for tab_name, TabClass in plugin.get_tab_classes().items():
                        settings_key = "{}: {}".format(module_name, tab_name)
                        settings_dict.setdefault(settings_key, {"tab_name": tab_name})
                        settings_dict[settings_key]["front_panel_settings"] = (
                            settings[settings_key] if settings_key in settings else {}
                        )
                        settings_dict[settings_key]["saved_data"] = (
                            tab_data[settings_key]['data']
                            if settings_key in tab_data else {}
                        )

                        tablist[settings_key] = TabClass(
                            tab_widget,
                            settings_dict[settings_key],
                        )
                        tab_dict[tab_name] = tablist[settings_key]

                    if hasattr(plugin, 'tabs_created'):
                        plugin.tabs_created(tab_dict)

            except Exception:
                self.logger.exception(
                    "Could not instantiate tab for plugin '%s'. Skipping"
                    % module_name
                )

    def setup_plugins(self, data, notifications, menu_builder, menubar):
        settings_pages = []
        settings_callbacks = []

        for module_name, plugin in self.plugins.items():
            try:
                # Setup settings page.
                settings_pages.extend(plugin.get_setting_classes())

                # Setup menu.
                if plugin.get_menu_class():
                    # Must store a reference or else the methods called when
                    # the menu actions are triggered will be garbage collected.
                    menu = plugin.get_menu_class()(data)
                    menu_builder.create_menu(menubar, menu.get_menu_items())
                    plugin.set_menu_instance(menu)

                # Setup notifications.
                plugin_notifications = {}
                for notification_class in plugin.get_notification_classes():
                    notifications.add_notification(notification_class)
                    plugin_notifications[notification_class] = (
                        notifications.get_instance(notification_class)
                    )
                plugin.set_notification_instances(plugin_notifications)

                # Register callbacks.
                callbacks = plugin.get_callbacks()
                # Save the settings_changed callback in a separate list for
                # setting up later.
                if isinstance(callbacks, dict) and 'settings_changed' in callbacks:
                    settings_callbacks.append(callbacks['settings_changed'])

            except Exception:
                self.logger.exception(
                    "Plugin '%s' error. Plugin may not be functional." % module_name
                )

        return settings_pages, settings_callbacks

    def setup_complete(self, data):
        for module_name, plugin in self.plugins.items():
            try:
                plugin.plugin_setup_complete(data)
            except Exception:
                self.logger.exception(
                    "Error in plugin_setup_complete() for plugin '%s'. "
                    "Trying again with old call signature..." % module_name
                )
                # Backwards compatibility for old plugins.
                try:
                    plugin.plugin_setup_complete()
                    self.logger.warning(
                        "Plugin '%s' using old API. Please update "
                        "Plugin.plugin_setup_complete method to accept a "
                        "dictionary of blacs_data as the only argument."
                        % module_name
                    )
                except Exception:
                    self.logger.exception(
                        "Plugin '%s' error. Plugin may not be functional."
                        % module_name
                    )

    def get_callbacks(self, name):
        """Return all callbacks for a particular name, in priority order."""
        callbacks = []

        for plugin in self.plugins.values():
            try:
                plugin_callbacks = plugin.get_callbacks()
                if plugin_callbacks is not None:
                    if name in plugin_callbacks:
                        callbacks.append(plugin_callbacks[name])
            except Exception:
                self.logger.exception('Error getting callbacks from %s.' % str(plugin))

        callbacks.sort(
            key=lambda callback: getattr(callback, 'priority', DEFAULT_PRIORITY)
        )
        return callbacks

    def close_plugins(self):
        for module_name, plugin in self.plugins.items():
            try:
                plugin.close()
            except Exception as e:
                self.logger.error(
                    'Could not close plugin %s. Error was: %s'
                    % (module_name, str(e))
                )
