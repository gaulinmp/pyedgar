# -*- coding: utf-8 -*-
"""
General utilities for interacting with plaintext documents.

EDGAR document specification details: https://www.sec.gov/info/edgar/pdsdissemspec051310.pdf

:copyright: © 2025 by Mac Gaulin
:license: MIT, see LICENSE for more details.
"""

import re
import logging
from collections import Counter

__logger = logging.getLogger(__name__)

_re_space = re.compile(r'\s')
_re_spaces = re.compile(r'\s+')
_re_spaces_2plus = re.compile(r'\s\s+')
_re_nl = re.compile(r'[\n\r]')
_re_nls = re.compile(r'[\n\r]+')
_re_number = re.compile(r'\b[\'"$-]*[\d.][\d.,]*\b')

def find_newlines(text, pos=0, endpos=-1):
    """
    Returns the list of the position of the _last_ set of newlines in a
    consecutive group. Includes the character at endposition.
    """
    if endpos <= pos:
        endpos = len(text)
    return list(x.end() for x in _re_nls.finditer(text, pos=pos, endpos=endpos))


def get_linestats(line, expected_line_length):
    r = {'line': line.rstrip()}
    r['line_strip'] = r['line'].lstrip()

    r['linelen'] = len(r['line'])
    r['textlen'] = len(r['line_strip'])
    r['space_left'] = r['linelen'] - r['textlen']
    r['space_right'] = expected_line_length - r['linelen']

    r['num_internal_spaces'] = len(_re_space.findall(r['line_strip']))
    r['num_internal_spacing'] = len(_re_spaces_2plus.findall(r['line_strip']))
    r['len_internal_spacing'] = sum(len(s) for s in
                                    _re_spaces_2plus.findall(r['line_strip']))
    r['num_tokens'] = len(r['line_strip'].split())
    r['num_numbers'] = sum(1 for _ in _re_number.finditer(r['line']))
    r['tok_sp_ratio'] = r['num_tokens'] / r['num_internal_spaces'] \
                        if r['num_internal_spaces'] else 0
    r['length_right_ratio'] = r['linelen'] / expected_line_length

    return r

def unwrap_plaintext(text, expected_line_length=None):
    splitlines = text.split('\n')

    if expected_line_length is None:
        aggline = Counter([len(l) for l in splitlines if l.strip()])

        if len(aggline) <= 1:
            return text

        mode_linelen = aggline.most_common(1)[0][0]
        max_linelen = max(aggline.keys())
        if mode_linelen / max_linelen < .95:
            __logger.debug("Poor line length format, mode: {} max: {} ({:.1f}%)"
                           .format(mode_linelen, max_linelen,
                                   100*mode_linelen/max_linelen))

        expected_line_length = mode_linelen

    joinlines = []
    stnext = get_linestats('', expected_line_length)

    for i,line in enumerate(splitlines):
        # get next line (which is stnext), and this loop's st is last's stnext
        stnext, st = get_linestats(line, expected_line_length), stnext

        newline = ((st['tok_sp_ratio'] < .9) |
                   # ^ Lots of space between tokens. Not normal text line.
                   (stnext['tok_sp_ratio'] < .75) |
                   # ^ Next line isn't normal line either
                   (st['length_right_ratio'] < .85))
                   # ^ Text doesn't go all the way to the end

        # If this line continues on next, remove left space from next line.
        if not newline:
            stnext['line'] = stnext['line_strip']

        # Remember, we're operating one line behind.
        joinlines.append(st['line'])
        joinlines.append('\n' if newline else ' ')
    # add last line.
    joinlines.append(stnext['line'])

    return ''.join(joinlines)

def get_para_bounds(text, position):
    r"""Gets location of nearest newlines surrounding `position` in `text`.

    :param text: Text to search for paragraphs in.
    :param position: Index of point around which newlines are searched.
    :return: Tuple containing (start, end) indexes of surrounding paragraph.
    :rtype: tuple

    >>> get_para_bounds('123\n567\n90', -1)
    (0, 3)
    >>> get_para_bounds('123\n567\n90', 5)
    (4, 7)
    >>> get_para_bounds('123\n567\n90', 100)
    (8, 10)
    >>> get_para_bounds('123\n567\n90', {})
    (0, 3)
    """
    start, end = None, None
    try:
        position = min(len(text), max(0, position))
    except TypeError:
        position = 0
    for i in range(2,10): # search 'backwards'
        for start in _re_nl.finditer(text, position-4**i, position):
            pass
        if start:
            break
    end = _re_nl.search(text, position)
    return start.end() if start else 0, end.start() if end else len(text)

if __name__ == '__main__':
    import doctest
    doctest.testmod()
