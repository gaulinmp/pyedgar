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

RE_HTML_TAGS = re.compile(r"</?(?:html|head|title|body|div|font|style|[apb]\b|tr|td|h\d)", re.I)


def is_html(maybe_html, num_tags_for_yes=5, max_length_to_check=100_000):
    """
    Returns boolean flag for whether text is likely HTML or not. Based on finding HTML tags.

    Note: iXBRL has a WHOLE bunch of noise up front with <ix: tags, so this sometimes fails that.
        You could add checking for xbrl explicitly, or just increase max_length_to_check or setting it to None for all.

    Args:
        maybe_html (str): HTML or text input to check
        num_tags_for_yes (int, optional): Number of tags to find to consider this string HTML. Defaults to 5.
        max_length_to_check (int, optional): Maximum number of bytes to search for HTML tags in. Defaults to 100_000.
    """
    for i, _ in enumerate(RE_HTML_TAGS.finditer(maybe_html, 0, max_length_to_check or len(maybe_html))):
        if i >= num_tags_for_yes:
            return True
    return False


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
    if not force and (not html_string or not is_html(html_string)):
        if unwrap:
            return plaintext.unwrap_plaintext(html_string, 80)  # SGML is 80 chars wide
        return html_string

    text = html_ent_re_sub(html_string)

    p1 = Popen(f"w3m -T text/html -dump -cols {document_width} -no-graph".split(), stdin=PIPE, stdout=PIPE)
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
