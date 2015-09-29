#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Utilities for interacting with edgar forms.
"""

import os
import re
import logging
from subprocess import Popen, PIPE

from . import plaintext
from .htmlparse import RE_HTML_TAGS, convert_html_to_text, html_ent_re_sub
from .. import exceptions as EX

__logger = logging.getLogger(__name__)

RE_DOC_TAG_OPEN = re.compile('<DOCUMENT>')
RE_DOC_TAG_CLOSE = re.compile('</DOCUMENT>')
RE_TEXT_TAG_OPEN  = re.compile('<TEXT>')
RE_TEXT_TAG_CLOSE =  re.compile('</TEXT>')
RE_HEADER_TAG = re.compile(r'^<(?P<key>[^/][^>]*)>(?P<value>.+)$', re.M)

def get_all_headers(text, pos=0, endpos=None):
    """
    Return dictionary of all <KEY>VALUE formatted headers in EDGAR documents.
    Note this requires the daily feed version of the EDGAR files.
    Dictionary keys are lowercase (`.lower()` is called), and stripped.

    `pos` and `endpos` can be used to get headers for specific exhibits.
    """
    if endpos is None:
        endpos = len(text)
    return {x.group(1).lower():x.group(2).strip()
            for x in RE_HEADER_TAG.finditer(text, pos, endpos) if x}

def get_header(text, header, return_match=False, pos=0, endpos=None):
    """
    Searches `text` for header formatted <`header`>VALUE\\n and returns VALUE.strip()
    Note this requires the daily feed version of the EDGAR files.

    `pos` and `endpos` can be used to get headers for specific exhibits.
    """
    re_tag = re.compile(r'^<{}>(.+)$'.format(header), re.M | re.I)
    if endpos is None:
        endpos = len(text)

    match = re_tag.search(text, pos, endpos)
    value = match.group(1).strip() if match else ''

    if return_match:
        return value, match
    return value

def get_form_with_header(file_path, form_type=None, buff_size=(2<<16) + 8):
    """
    Reads file or string, returns:
        >>> {'cik', 'form_type', 'filing_date', 'text':[]}
    or None on failure.
    """
    if not os.path.exists(file_path):
        raise EX.FileNotFound

    with open(file_path, encoding='utf-8', errors='ignore',
              buffering=buff_size) as fh:
        text = fh.read(buff_size)

        found_form = get_header(text, "TYPE")
        if form_type is not None:
            if not found_form or form_type.upper() != found_form.upper():
                raise EX.WrongFormType

        # Now find where the header stops (where first document starts)
        doc_start = RE_DOC_TAG_OPEN.search(text)

        # If no DOCUMENT tag found, this isn't an EDGAR form. ABORT!
        if not doc_start:
            raise EX.EDGARFilingFormatError
        # This is what I care about now. Could be changed to `get_all_headers`
        ret_dict = {'form_type': found_form.upper(),
                   'name': get_header(text, "CONFORMED-NAME",
                                      endpos=doc_start.start()),
                   'sic': get_header(text, "ASSIGNED-SIC",
                                     endpos=doc_start.start()),
                   'fye': get_header(text, "FISCAL-YEAR-END",
                                     endpos=doc_start.start()),
                   'filing_date': get_header(text, "FILING-DATE",
                                             endpos=doc_start.start()),
                   'filing_date_period': get_header(text, "PERIOD",
                                                    endpos=doc_start.start()),
                   'filing_date_change': get_header(text, "DATE-OF-FILING-DATE-CHANGE",
                                                    endpos=doc_start.start()),}
        # Iteratively loop through open file buffer, reading buff_size chunks
        # until </DOCUMENT> tag is found. There is a chance that the tag could
        # be split across chunks, but it's a cost I'm willing to accept.
        chunks = [text]
        while not RE_DOC_TAG_CLOSE.search(chunks[-1]):
            text = fh.read(buff_size)
            if not text: # prevent infinite loop, text is null when EOF reached
                break
            chunks.append(text)

    # Now put all those chunks together.
    text =  "".join(chunks)
    st = RE_DOC_TAG_OPEN.search(text)
    if not st:
        return text
    en = RE_DOC_TAG_CLOSE.search(text, st.end()) # start searching after start
    if not en:
        return text[st.end()]
    return text[st.end():en.start()]

def get_form(file_path):
    """
    Reads file at file_path and returns form between <TEXT> and </TEXT> tags.
    """
    text = get_form_with_header(file_path)
    if not text:
        return ''

    st = RE_TEXT_TAG_OPEN.search(text)
    if not st:
        return text
    en = RE_TEXT_TAG_CLOSE.search(text, st.end())
    if not en:
        return text[st.end()]
    return text[st.end():en.start()]

def get_plaintext(path, unwrap=True, document_width=150):
    """
    Get the plaintext version of an edgar filing.
    Assumes the first exhibit in the full filing text document.
    If HTML, uses w3m linux program to parse into plain text.
    If `unwrap`, also unwraps paragraphs so each paragraph is on one line.

    :param string path: Full path to form.
    :param bool unwrap: Whether to call `plaintext.unwrap_plaintext` on document.
    :param int document_width: How wide the plaintext will be. Used in unwrapping.

    :return: Plain text representation of file.
    :rtype: string
    """
    text = get_form(path)

    return convert_html_to_text(text, unwrap=unwrap, document_width=document_width)
