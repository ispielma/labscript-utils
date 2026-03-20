#####################################################################
#                                                                   #
# labconfig.py                                                      #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of the labscript suite (see                     #
# http://labscriptsuite.org) and is licensed under the Simplified   #
# BSD License. See the license.txt file in the root of the project  #
# for the full license.                                             #
#                                                                   #
#####################################################################
import configparser
import os
import shlex
import subprocess
import warnings
from ast import literal_eval
from pathlib import Path

from labscript_utils import dedent
from labscript_profile import (
    LABSCRIPT_SUITE_PROFILE,
    default_labconfig_path,
    ensure_labconfig,
)
from labscript_profile.toml_config import (
    TomlBasicInterpolation,
    TomlConfigParser,
    dump_toml_file,
    load_toml_file,
)


default_config_path = default_labconfig_path()


class EnvInterpolation(TomlBasicInterpolation):
    """Interpolation that expands environment variables after TOML/basic interpolation."""

    def before_get(self, *args):
        value = super(EnvInterpolation, self).before_get(*args)
        if isinstance(value, str):
            return os.path.expandvars(value)
        return value


class LabConfig(TomlConfigParser):
    """TOML labconfig reader with the small ConfigParser-like API used by the suite."""

    NoOptionError = configparser.NoOptionError
    NoSectionError = configparser.NoSectionError
    DuplicateSectionError = configparser.DuplicateSectionError

    def __init__(
        self, config_path=default_config_path, required_params=None, defaults=None,
    ):
        if required_params is None:
            required_params = {}
        if defaults is None:
            defaults = {}
        else:
            defaults = dict(defaults)
        defaults['labscript_suite'] = str(LABSCRIPT_SUITE_PROFILE)
        if isinstance(config_path, list):
            config_paths = list(config_path)
            if config_paths:
                if config_paths[0] == default_config_path:
                    config_paths[0] = ensure_labconfig()
                self.config_path = config_paths[0]
            else:
                self.config_path = None
        else:
            self.config_path = ensure_labconfig() if config_path == default_config_path else config_path
            config_paths = [self.config_path]

        self.file_format = ""
        for section, options in required_params.items():
            self.file_format += "[%s]\n" % section
            for option in options:
                self.file_format += "%s = <value>\n" % option

        TomlConfigParser.__init__(
            self,
            defaults=defaults,
            interpolation=EnvInterpolation(),
        )
        for path in config_paths:
            self._read_path(path)

        experiment_name = self.get("default", "experiment_name", fallback=None)
        if experiment_name:
            msg = """The experiment_name keyword has been renamed apparatus_name in
                labscript_utils 3.0, and will be removed in a future version. Please
                update your labconfig to use the apparatus_name keyword."""
            warnings.warn(dedent(msg), FutureWarning)
            if self.get("default", "apparatus_name", fallback=None):
                msg = """You have defined both experiment_name and apparatus_name in
                    your labconfig. Please omit the deprecate experiment_name
                    keyword."""
                raise Exception(dedent(msg))
            self.set("default", "apparatus_name", experiment_name)

        try:
            for section, options in required_params.items():
                section = self._canonical_section_name(section)
                for option in options:
                    self.get(section, option)
        except (configparser.NoOptionError, configparser.NoSectionError):
            msg = f"""The experiment configuration file located at {config_path} does
                not have the required keys. Make sure the config file contains the
                following structure:\n{self.file_format}"""
            raise Exception(dedent(msg))

    def _read_path(self, path):
        """Read a TOML labconfig, or temporarily fall back to legacy INI."""
        if path is None:
            return
        path = Path(path)
        if not path.exists():
            return
        if path.suffix.lower() == '.toml':
            self.read_toml(path)
            return
        if path.suffix.lower() == '.ini':
            msg = """INI labconfig support is deprecated and slated for removal soon.
                Convert this file to TOML."""
            warnings.warn(dedent(msg), FutureWarning)
            self.read(path)
            return
        msg = f"Unsupported labconfig format for {path}. Expected a .toml or .ini file."
        raise RuntimeError(msg)


def _resolve_appconfig_load_path(filename):
    path = Path(filename)
    suffix = path.suffix.lower()
    if suffix == '.ini':
        if path.exists():
            return path
        toml_path = path.with_suffix('.toml')
        if toml_path.exists():
            return toml_path
        return path
    if suffix == '.toml':
        if path.exists():
            return path
        legacy_path = path.with_suffix('.ini')
        if legacy_path.exists():
            return legacy_path
        return path
    toml_path = path.with_suffix('.toml')
    if toml_path.exists():
        return toml_path
    legacy_path = path.with_suffix('.ini')
    if legacy_path.exists():
        return legacy_path
    return toml_path


def _resolve_appconfig_save_path(filename):
    return Path(filename).with_suffix('.toml')


def _to_toml_compatible(value, location='value'):
    if isinstance(value, dict):
        converted = {}
        for key, child in value.items():
            if not isinstance(key, str):
                msg = f"{location} contains a non-string dict key {key!r}"
                raise TypeError(msg)
            converted[key] = _to_toml_compatible(child, f"{location}.{key}")
        return converted
    if isinstance(value, (list, tuple)):
        return [
            _to_toml_compatible(child, f"{location}[{index}]")
            for index, child in enumerate(value)
        ]
    if isinstance(value, (str, bool, int, float)):
        return value
    msg = f"{location} value {value!r} is not representable in TOML app config"
    raise TypeError(msg)


def _load_legacy_appconfig_value(value):
    """Temporary legacy INI app-config decoder. Slated for removal soon."""
    if not isinstance(value, str):
        return value
    try:
        return literal_eval(value)
    except (ValueError, SyntaxError):
        return value


def save_appconfig(filename, data):
    """Save a dictionary as a TOML app config."""
    data = {
        section_name: {
            name: _to_toml_compatible(value, f"{section_name}/{name}")
            for name, value in section.items()
        }
        for section_name, section in data.items()
    }
    filename = _resolve_appconfig_save_path(filename)
    filename.parent.mkdir(parents=True, exist_ok=True)
    dump_toml_file(filename, data)
    return str(filename)


def load_appconfig(filename, return_save_path=False):
    """Load a TOML app config, or a legacy INI app config if required.

    If a legacy INI file is loaded, a sibling TOML file is immediately written and can be
    returned as the canonical save path via ``return_save_path=True``. Legacy INI support
    here is temporary and slated for removal soon.
    """
    requested_path = Path(filename)
    filename = _resolve_appconfig_load_path(filename)
    save_path = _resolve_appconfig_save_path(requested_path)
    if filename.suffix.lower() == '.ini':
        c = configparser.ConfigParser(interpolation=None)
        c.optionxform = str
        if filename.exists():
            c.read(filename)
        data = {
            section_name: {
                name: _load_legacy_appconfig_value(value)
                for name, value in c.items(section_name, raw=True)
            }
            for section_name in c.sections()
        }
        if filename.exists():
            save_path = Path(save_appconfig(save_path, data))
    else:
        raw = load_toml_file(filename) if filename.exists() else {}
        data = {
            section_name: dict(section.items())
            for section_name, section in raw.items()
            if section_name != 'default' and isinstance(section, dict)
        }
        if filename.suffix.lower() == '.toml':
            save_path = filename
    if return_save_path:
        return data, str(save_path)
    return data


def get_app_saved_configs_dir(exp_config, app_name):
    """Return the application-specific directory within ``default.app_saved_configs``."""
    try:
        base_path = exp_config.get('default', 'app_saved_configs')
    except LabConfig.NoOptionError:
        exp_config.set(
            'default',
            'app_saved_configs',
            os.path.join(
                '%(labscript_suite)s',
                'userlib',
                'app_saved_configs',
                '%(apparatus_name)s',
            ),
        )
        base_path = exp_config.get('default', 'app_saved_configs')
    path = os.path.join(base_path, app_name)
    if not os.path.exists(path):
        os.makedirs(path)
    return path

def launch_from_config(config, filepath, program_key, arguments_key,
                       missing_program_message, launch_failed_message,
                       error_dialog):
    """Launch a configured external program on a file path."""
    program_path = config.get('programs', program_key)
    if not program_path:
        error_dialog(missing_program_message)
        return False
    arguments = config.get('programs', arguments_key)
    has_filepath_placeholder = '{file}' in arguments
    arguments = shlex.split(arguments.replace('{file}', filepath))
    if not has_filepath_placeholder:
        arguments.insert(0, filepath)
    try:
        subprocess.Popen([program_path] + arguments)
    except Exception as exc:
        error_dialog(launch_failed_message % (config.config_path, str(exc)))
        return False
    return True
