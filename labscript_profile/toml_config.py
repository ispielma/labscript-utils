import configparser

try:
    import tomllib
except ImportError:
    import tomli as tomllib

import tomli_w


def load_toml_file(filename):
    with open(filename, 'rb') as f:
        return tomllib.load(f)


def dump_toml_file(filename, data):
    with open(filename, 'wb') as f:
        tomli_w.dump(data, f)


class TomlBasicInterpolation(configparser.BasicInterpolation):
    """Basic interpolation that leaves non-string TOML values alone."""

    def before_get(self, parser, section, option, value, defaults):
        if not isinstance(value, str):
            return value
        return super().before_get(parser, section, option, value, defaults)


class TomlConfigParser(configparser.ConfigParser):
    """ConfigParser variant that preserves native TOML values."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('interpolation', TomlBasicInterpolation())
        super().__init__(*args, **kwargs)

    def set(self, section, option, value=None):
        if not section or section == self.default_section:
            sectdict = self._defaults
        else:
            try:
                sectdict = self._sections[section]
            except KeyError:
                raise configparser.NoSectionError(section) from None
        sectdict[self.optionxform(option)] = value

    def getboolean(
        self, section, option, *, raw=False, vars=None, fallback=configparser._UNSET
    ):
        value = self.get(section, option, raw=raw, vars=vars, fallback=fallback)
        if value is fallback:
            return value
        if isinstance(value, bool):
            return value
        return self._convert_to_boolean(value)

    def read_toml(self, filename):
        data = load_toml_file(filename)
        if not isinstance(data, dict):
            raise TypeError("Top-level TOML document must be a mapping of sections")
        for section_name, section in data.items():
            if not isinstance(section, dict):
                raise TypeError(f"Section {section_name!r} must contain key/value pairs")
            section_name = str(section_name)
            if section_name != self.default_section and not self.has_section(section_name):
                self.add_section(section_name)
            for option, value in section.items():
                self.set(section_name, str(option), value)
        return [str(filename)]

    def to_toml_dict(self):
        data = {}
        if self.defaults():
            data[self.default_section] = dict(self.defaults())
        for section in self.sections():
            data[section] = dict(self._sections[section])
        return data

    def write_toml(self, filename):
        dump_toml_file(filename, self.to_toml_dict())
