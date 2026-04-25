import logging
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labscript_utils.plugins import (
    BasePlugin,
    Callback,
    MenuBuilder,
    PluginManager,
    callback,
)


class FakeConfig(object):
    def __init__(self):
        self.sections = {}

    def has_section(self, name):
        return name in self.sections

    def add_section(self, name):
        self.sections[name] = {}

    def items(self, name):
        return list(self.sections[name].items())

    def set(self, section, option, value):
        self.sections[section][option] = value

    def getboolean(self, section, option):
        return self.sections[section][option].lower() == 'true'


def test_callback_binds_as_method_and_keeps_priority():
    class Example(object):
        @callback(priority=5)
        def method(self, value):
            return self, value

    example = Example()

    assert isinstance(Example.__dict__['method'], Callback)
    assert Example.__dict__['method'].priority == 5
    assert example.method('value') == (example, 'value')


def test_base_plugin_defaults_are_no_ops():
    plugin = BasePlugin({'x': 1})

    assert plugin.initial_settings == {'x': 1}
    assert plugin.get_menu_class() is None
    assert plugin.get_notification_classes() == []
    assert plugin.get_setting_classes() == []
    assert plugin.get_callbacks() is None
    assert plugin.get_tab_classes() == {}
    assert plugin.get_save_data() == {}


def make_plugin_package(tmp_path, modules):
    package = 'plugin_test_' + uuid.uuid4().hex
    package_dir = tmp_path / package
    plugins_dir = package_dir / 'plugins'
    plugins_dir.mkdir(parents=True)
    (package_dir / '__init__.py').write_text('')
    (plugins_dir / '__init__.py').write_text('')
    for name, source in modules.items():
        module_dir = plugins_dir / name
        module_dir.mkdir()
        (module_dir / '__init__.py').write_text(source)
    sys.path.insert(0, str(tmp_path))
    return package + '.plugins', plugins_dir


def test_discovery_defaults_config_and_imports_only_enabled_plugins(tmp_path):
    plugin_package, plugins_dir = make_plugin_package(
        tmp_path,
        {
            'enabled': 'class Plugin(object):\n    pass\n',
            'disabled': 'raise RuntimeError("should not import")\n',
        },
    )
    config = FakeConfig()
    manager = PluginManager(
        plugin_package,
        str(plugins_dir),
        config,
        'app/plugins',
        ['enabled'],
    )

    modules = manager.discover_modules()

    assert set(modules) == {'enabled'}
    assert config.sections['app/plugins']['enabled'] == 'True'
    assert config.sections['app/plugins']['disabled'] == 'False'


def test_instantiate_plugins_uses_saved_settings():
    class Plugin(object):
        def __init__(self, initial_settings):
            self.initial_settings = initial_settings

    manager = PluginManager(
        'package.plugins',
        'plugins',
        FakeConfig(),
        'app/plugins',
    )
    manager.modules = {'plugin': SimpleNamespace(Plugin=Plugin)}

    plugins = manager.instantiate_plugins({'plugin': {'answer': 42}})

    assert plugins['plugin'].initial_settings == {'answer': 42}


def test_get_callbacks_sorts_by_priority_and_logs_errors(caplog):
    class Slow(object):
        def get_callbacks(self):
            return {'event': self.on_event}

        @callback(priority=20)
        def on_event(self):
            pass

    class Fast(object):
        def get_callbacks(self):
            return {'event': self.on_event}

        @callback(priority=5)
        def on_event(self):
            pass

    class Broken(object):
        def get_callbacks(self):
            raise RuntimeError('broken')

    logger = logging.getLogger('test.plugins')
    manager = PluginManager(
        'package.plugins',
        'plugins',
        FakeConfig(),
        'app/plugins',
        logger=logger,
    )
    manager.plugins = {
        'slow': Slow(),
        'broken': Broken(),
        'fast': Fast(),
    }

    with caplog.at_level(logging.ERROR, logger='test.plugins'):
        callbacks = manager.get_callbacks('event')

    assert [callback.priority for callback in callbacks] == [5, 20]
    assert 'Error getting callbacks from' in caplog.text


class FakeSignal(object):
    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)


class FakeAction(object):
    def __init__(self, name, icon=None):
        self.name = name
        self.icon = icon
        self.triggered = FakeSignal()


class FakeMenu(object):
    def __init__(self, name='root'):
        self.name = name
        self.items = []

    def addMenu(self, name):
        menu = FakeMenu(name)
        self.items.append(('menu', menu))
        return menu

    def addAction(self, *args):
        if len(args) == 1:
            action = FakeAction(args[0])
        else:
            action = FakeAction(args[1], icon=args[0])
        self.items.append(('action', action))
        return action

    def addSeparator(self):
        self.items.append(('separator', None))


def test_menu_builder_creates_nested_menus_icons_actions_and_separators():
    root = FakeMenu()
    called = []

    def action():
        called.append(True)

    MenuBuilder(icon_factory=lambda name: 'icon:' + name).create_menu(
        root,
        {
            'name': 'Top',
            'menu_items': [
                {'name': 'Plain', 'action': action},
                {'separator': True},
                {'name': 'Icon', 'icon': 'resource', 'action': action},
            ],
        },
    )

    top = root.items[0][1]
    plain = top.items[0][1]
    icon = top.items[2][1]

    assert root.items[0][0] == 'menu'
    assert plain.name == 'Plain'
    assert plain.triggered.callbacks == [action]
    assert top.items[1] == ('separator', None)
    assert icon.name == 'Icon'
    assert icon.icon == 'icon:resource'
    assert icon.triggered.callbacks == [action]
