#####################################################################
#                                                                   #
# file_utils.py                                                     #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of the labscript suite (see                     #
# http://labscriptsuite.org) and is licensed under the Simplified   #
# BSD License. See the license.txt file in the root of the project  #
# for the full license.                                             #
#                                                                   #
#####################################################################

import os
import re


def next_available_indexed_filepath(filepath, suffix_format, start=0):
    """Return the first non-existent filepath created by appending a formatted suffix.

    ``suffix_format`` is formatted with a single ``index`` keyword argument and is
    inserted between the filepath stem and its extension. If filepath already ends
    with a suffix matching the pattern, that suffix is stripped and the search begins
    at the next higher index."""
    basename, ext = os.path.splitext(filepath)
    suffix_pattern = re.escape(suffix_format)
    suffix_pattern = re.sub(
        r'\\\{index(?::[^}]*)?\\\}',
        lambda match: r'(?P<index>\d+)',
        suffix_pattern,
    )
    match = re.search(suffix_pattern + r'$', basename)
    if match is not None:
        basename = basename[:match.start()]
        start = max(start, int(match.group('index')) + 1)
    index = start
    while True:
        candidate = basename + suffix_format.format(index=index) + ext
        if not os.path.exists(candidate):
            return candidate, index
        index += 1
