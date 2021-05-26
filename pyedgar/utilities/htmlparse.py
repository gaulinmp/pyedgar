# -*- coding: utf-8 -*-

"""
Module for parsing HTML files.

:copyright: © 2021 by Mac Gaulin
:license: MIT, see LICENSE for more details.
"""

import re
import logging
from subprocess import Popen, PIPE

from . import plaintext
from ._html_encoding_lookup import html_ent_re_sub

__logger = logging.getLogger(__name__)

RE_HTML_TAGS = re.compile(r'</?(?:html|head|title|body|div|font|style|[apb]\b|tr|td|h\d)', re.I)

def convert_html_to_text(html_string, unwrap=True, document_width=150, force=False):
    """
    Get the plaintext version of an HTML string.
    If HTML, uses w3m linux program to parse into plain text.
    If `unwrap`, also unwraps paragraphs so each paragraph is on one line.
    TODO: come up with better unwrapping algorithm.

    :param string html_string: HTML or text document in a string
    :param bool unwrap: If True (default) call `plaintext.unwrap_plaintext` on text
    :param document_width: Expected width of lines in text (used for unwrapping, default=150).
    :param bool force: Skip checking whether text is HTML (# of valid HTML
        tags >= 3, default=False).

    :return: Plain text representation of file.
    :rtype: string
    """
    # If not an HTML file, just return the text.
    if (not force and
        (not html_string or len(RE_HTML_TAGS.findall(html_string, 0, 2000)) <= 3)):
        if unwrap:
            return plaintext.unwrap_plaintext(html_string, 80) # SGML is 80 chars wide
        return html_string

    text = html_ent_re_sub(html_string)

    p1 = Popen('w3m -T text/html -dump -cols {0} -no-graph'
                .format(document_width).split(),
                stdin=PIPE, stdout=PIPE)
    # Now send it the text on STDIN (like cat file.html | w3m)
    output = p1.communicate(input=text.encode())

    p1.stdout.close()  # Allow p1 to receive a SIGPIPE if p2 exits.
    try:
        p1.terminate()
    except ProcessLookupError:
        pass

    if output[-1]:
        __logger.warning(output[-1])

    if unwrap:
        return plaintext.unwrap_plaintext(output[0].decode(), document_width)

    return output[0].decode()
