#####################################################################
#                                                                   #
# lookup_format.py                                                  #
#                                                                   #
# Copyright 2026, Monash University                                 #
#                                                                   #
# This file is part of the labscript suite (see                     #
# http://labscriptsuite.org) and is licensed under the Simplified   #
# BSD License. See the license.txt file in the root of the project  #
# for the full license.                                             #
#                                                                   #
#####################################################################
import ast
import string


class InvalidLookupFormatField(ValueError):
    """Raised when a lookup-format field is not valid lookup-only syntax."""


def format_lookup_string(template, context, dt=None, preserve_unresolved=False):
    """Format a template using optional ``strftime`` plus lookup-only fields.

    Args:
        template (str): Format template.
        context (dict): Top-level lookup context.
        dt (datetime, optional): Datetime used for a first ``strftime`` pass.
        preserve_unresolved (bool): If True, unresolved lookups are left intact.
    """
    if dt is not None:
        template = dt.strftime(template)
    formatter = _LookupFormatter(context, preserve_unresolved=preserve_unresolved)
    return formatter.format(template)


class _LookupFormatter(object):
    def __init__(self, context, preserve_unresolved=False):
        self.context = context
        self.preserve_unresolved = preserve_unresolved
        self.formatter = string.Formatter()

    def format(self, template):
        parts = []
        for literal_text, field_name, format_spec, conversion in self.formatter.parse(template):
            parts.append(literal_text)
            if field_name is None:
                continue
            placeholder = self._reconstruct_placeholder(
                field_name, conversion, format_spec
            )
            try:
                value = self._resolve_field(field_name)
                if conversion:
                    value = self.formatter.convert_field(value, conversion)
                if format_spec:
                    format_spec = self.format(format_spec)
                parts.append(self.formatter.format_field(value, format_spec))
            except KeyError:
                if self.preserve_unresolved:
                    parts.append(placeholder)
                else:
                    raise
        return ''.join(parts)

    def _resolve_field(self, field_name):
        root_name, lookups = _parse_lookup_field(field_name)
        try:
            value = self.context[root_name]
        except KeyError:
            raise KeyError(root_name)
        for lookup in lookups:
            try:
                value = value[lookup]
            except KeyError:
                raise
        return value

    @staticmethod
    def _reconstruct_placeholder(field_name, conversion, format_spec):
        placeholder = '{' + field_name
        if conversion:
            placeholder += '!' + conversion
        if format_spec:
            placeholder += ':' + format_spec
        placeholder += '}'
        return placeholder


def _parse_lookup_field(field_name):
    field_name = str(field_name)
    length = len(field_name)
    index = 0

    root_name, index = _parse_identifier(field_name, index)
    lookups = []

    while index < length:
        if field_name[index] != '[':
            msg = "Invalid lookup-format field %r" % field_name
            raise InvalidLookupFormatField(msg)
        closing_index = field_name.find(']', index + 1)
        if closing_index == -1:
            msg = "Invalid lookup-format field %r" % field_name
            raise InvalidLookupFormatField(msg)
        lookup_text = field_name[index + 1 : closing_index].strip()
        if not lookup_text:
            msg = "Invalid lookup-format field %r" % field_name
            raise InvalidLookupFormatField(msg)
        lookups.append(_parse_lookup_key(lookup_text))
        index = closing_index + 1

    return root_name, lookups


def _parse_identifier(field_name, index):
    if index >= len(field_name):
        msg = "Invalid lookup-format field %r" % field_name
        raise InvalidLookupFormatField(msg)

    start = index
    first = field_name[index]
    if not (first.isalpha() or first == '_'):
        msg = "Invalid lookup-format field %r" % field_name
        raise InvalidLookupFormatField(msg)
    index += 1

    while index < len(field_name):
        char = field_name[index]
        if char.isalnum() or char == '_':
            index += 1
            continue
        break

    return field_name[start:index], index


def _parse_lookup_key(lookup_text):
    if lookup_text[0] in ('"', "'"):
        try:
            return ast.literal_eval(lookup_text)
        except (SyntaxError, ValueError) as exc:
            msg = "Invalid lookup-format key %r" % lookup_text
            raise InvalidLookupFormatField(msg) from exc
    try:
        return int(lookup_text)
    except ValueError:
        return lookup_text
