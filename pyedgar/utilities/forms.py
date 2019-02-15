# -*- coding: utf-8 -*-
"""
Utilities for interacting with edgar forms.

:copyright: © 2018 by Mac Gaulin
:license: MIT, see LICENSE for more details.
"""

import re
import os
import logging

# from . import plaintext
from .htmlparse import convert_html_to_text
from ..exceptions import WrongFormType, EDGARFilingFormatError

__logger = logging.getLogger(__name__)

# Obviously encoding is not uniform. Because internet.
# ENCODING_INPUT = 'latin-1'
ENCODING_INPUT = 'utf-8'
ENCODING_OUTPUT = 'utf-8'

RE_DOC_TAG = re.compile('</?DOCUMENT>')
RE_DOC_TAG_OPEN = re.compile('<DOCUMENT>')
RE_DOC_TAG_CLOSE = re.compile('</DOCUMENT>')
RE_TEXT_TAG = re.compile('</?TEXT>')
RE_TEXT_TAG_OPEN = re.compile('<TEXT>')
RE_TEXT_TAG_CLOSE = re.compile('</TEXT>')
# Only matches <KEY>VALUE, no </KEY> nor <KEY>\n
RE_HEADER_TAG = re.compile(r'^<(?P<key>[^/][^>]*)>[ \t]*(?P<value>.+)$', re.M)
# Matches anything like <*>*\n
RE_HEADER_TAG_OC = re.compile(r'^<(?P<key>/?[^>]*)>(?P<value>.*)$', re.M)


def get_full_filing(file_path, encoding=None, errors=None, buffering=None):
    """
    Returns full text of filing.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError("File {} does not exist.".format(file_path))

    with open(file_path, encoding=encoding or ENCODING_INPUT,
              errors=errors or 'ignore') as fh:
        return fh.read()

def get_form_with_header(file_path, form_type=None, buff_size=(2<<16) + 8,
                         encoding=None, errors=None):
    """
    Reads file or string, returns:
    {'cik', 'form_type', 'filing_date', 'text':[]}
    or None on failure.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError("File {} does not exist.".format(file_path))

    with open(file_path, encoding=encoding or ENCODING_INPUT, errors=errors or 'ignore',
              buffering=buff_size) as fh:
        text = fh.read(buff_size)

        found_form = get_header(text, "TYPE")
        if form_type is not None:
            if not found_form or form_type.upper() != found_form.upper():
                raise WrongFormType

        # Now find where the header stops (where first document starts)
        doc_start = RE_DOC_TAG_OPEN.search(text)

        # If no DOCUMENT tag found, this isn't an EDGAR form. ABORT!
        if not doc_start:
            raise EDGARFilingFormatError
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
    text = "".join(chunks)
    st = RE_DOC_TAG_OPEN.search(text)
    if not st:
        ret_dict['text'] = text
        return ret_dict
    en = RE_DOC_TAG_CLOSE.search(text, st.end()) # start searching after start
    if not en:
        ret_dict['text'] = text[st.end()]
        return ret_dict

    ret_dict['text'] = text[st.end():en.start()]

    return ret_dict

def get_form(file_path, encoding=None, errors=None):
    """
    Reads file at file_path and returns form between <TEXT> and </TEXT> tags.
    """
    form_dict = get_form_with_header(file_path, encoding=encoding, errors=errors)
    if not form_dict or 'text' not in form_dict:
        return ''
    text = form_dict['text']

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


def get_all_headers(text, pos=0, endpos=None, flat=False, **kwargs):
    """
    <KEY>VALUE formatted headers in EDGAR documents.
    Dictionary is either iterative (`flat=False`, default) where open/close
    SGML tags are nested dictionaries, or flat, where multiple keys
    are either ignored, renamed, or put in a list (see `get_all_headers_flat`).

    Note: this requires the daily feed version of the EDGAR files.
    Dictionary keys are lowercase (`.lower()` is called), and stripped.

    `pos` and `endpos` can be used to get headers for specific exhibits.
    """
    if flat:
        return get_all_headers_flat(text, pos=pos, endpos=endpos, **kwargs)
    return get_all_headers_dict(text, pos=pos, endpos=endpos, **kwargs)


def get_all_headers_flat(text, pos=0, endpos=None,
                         omit_duplicates=True,
                         add_int_to_name=True, **kwargs):
    """
    Return dictionary of all <KEY>VALUE formatted headers in EDGAR documents.
    Note this requires the daily feed version of the EDGAR files.
    Dictionary keys are lowercase (`.lower()` is called), and stripped.

    `pos` and `endpos` can be used to get headers for specific exhibits.

    Keys with the same name can either be ignored (`omit_duplicates=True`),
    or subsequent keys with names already in dictionary can be renamed
    by adding a count to the end (filer, filer1, etc.) if
    `add_int_to_name=True`, or added to a list if `add_int_to_name=False`.

    Returns dictionary of headers.
    """
    if pos == 0 and endpos is None:
        doc_tag_open = RE_DOC_TAG_OPEN.search(text)
        if doc_tag_open:
            endpos = doc_tag_open.start()
    if endpos is None:
        endpos = len(text)

    ret = {}
    for rx in RE_HEADER_TAG.finditer(text, pos, endpos):
        key, val = rx.groups()
        key, val = key.lower().strip(), val.strip()

        if not val:
            continue

        if key not in ret:
            ret[key] = val
            continue

        if omit_duplicates:
            continue

        if add_int_to_name:
            for i in range(1, 10000):
                newkey = '{}{}'.format(key, i)
                if newkey not in ret:
                    key = newkey
                    break
            ret[key] = val
            continue

        if type(ret[key]) != list:
            ret[key] = [ret[key],]

        ret[key].append(val)

    return ret

def get_all_headers_dict(text, pos=0, endpos=None, starter_dict=None, **kwargs):
    """
    Return dictionary of all <KEY>VALUE formatted headers in EDGAR documents.
    Note this requires the daily feed version of the EDGAR files.
    Dictionary keys are lowercase (`.lower()` is called), and stripped.

    `pos` and `endpos` can be used to get headers for specific exhibits.
    """
    if pos == 0 and endpos is None:
        doc_tag_open = RE_DOC_TAG_OPEN.search(text)
        if doc_tag_open:
            endpos = doc_tag_open.start()
    if endpos is None:  # No <DOCUMENT> found, parse to end.
        endpos = len(text)

    retdict = {}
    if starter_dict is not None:
        retdict.update(starter_dict)
    # push and pop 'current' dictionary from stack because pointers.
    stack = [retdict, ]

    for imatch in RE_HEADER_TAG_OC.finditer(text, pos, endpos):
        tmp = imatch.groupdict()
        # if 'key' not in tmp or 'value' not in tmp:
        #     continue
        key,val = tmp['key'].lower(), tmp['value'].strip()

        if '/' in key:
            # Then it's a closing tag. pop the last dict off the stack
            if len(stack) > 1:
                stack.pop()
            # If there's a value... we don't care. That's bad formatting.
            continue
        elif val:
            # Then just a normal key. Add to the dict at the end of the stack
            stack[-1][key] = val.strip()
            continue

        # Otherwise this might be a sub-group. Look for the </KEY> tag.
        re_end = re.compile('</{}>'.format(key), re.I)
        if re_end.search(text, imatch.end(), endpos):
            # Then we found the end tag. Create dict at KEY if KEY doesn't exist
            if key in stack[-1]:
                # Then try key_X for X from 0 to 200 I guess.
                for key_i in range(200):
                    newkey = '{}_{}'.format(key, key_i)
                    if newkey not in stack[-1]:
                        key = newkey
                        break
            # make a new dict at KEY
            stack[-1][key] = {}
            stack.append(stack[-1][key])

    return retdict

def get_header(text, header, pos=0, endpos=None, return_match=False):
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

def chunk_filing(text):
    """
    Separates EDGAR filing into constituent documents and
    their associated metadata.

    Args:
        text: Full text of the EDGAR filing, separated by <DOCUMENT> tags.

    Returns:
        List of dictionaries containins:
            {'full_text': full text of document or exhibit, between <TEXT> tags,
             'meta_data': meta data associated with document
                          (between <DOCUMENT> and <TEXT> tags)}

    Raises:
        ValueError: No text provided (empty).
        EDGARFilingFormatError: Document is not in proper EDGAR SGML format
    """
    if not text.strip():
        raise ValueError("Input text is empty.")

    doc_tags = RE_DOC_TAG.findall(text)

    if len(doc_tags) % 2:
        raise EDGARFilingFormatError('Uneven number of <DOCUMENT> tags found.'
                                     'Found: {}'.format(doc_tags))

    for i, tag in enumerate(doc_tags):
        if (i % 2) ^ ('/' in tag):
            raise EDGARFilingFormatError('<DOCUMENT> tags do not alternate open/close.'
                                         'Found: {}'.format(doc_tags))

    docs = []
    for _start, _end in zip(RE_DOC_TAG_OPEN.finditer(text),
                            RE_DOC_TAG_CLOSE.finditer(text)):

        text_start = RE_TEXT_TAG_OPEN.search(text, _start.end(), _end.start())
        if text_start:
            text_end = RE_TEXT_TAG_CLOSE.search(text, _start.end(), _end.start()) or _end
        else:
            # Document with no text? Whatevs.
            text_start = _end
            text_end = _end

        doc = get_all_headers_dict(text, pos=_start.end(), endpos=text_start.start())

        # Slicing that doesn't make sense (i.e. string[5:3]) returns ''
        # Thus if there's no text tag, full_text will be ''
        # because from above, text_start/end are both _end
        doc['full_text'] = text[text_start.end():text_end.start()]

        docs.append(doc)

    return docs

class CIKS(object):
    GOOGLE = 1288776
    AMAZON = 1018724
    FACEBOOK = 1326801
    APPLE = 320193
    GE = 40545
    NIKE = 320187
    FORD = 37996
    WALMART = 104169

class FORMS(object):
    FORM_3 = "3"
    FORM_4 = "4"
    FORM_8K = "8-K"
    FORM_10K = "10-K"
    FORM_10Q = "10-Q"
    FORM_DEF14A = "DEF14A"
    FORM_13G = "13G"
    FORM_13D = "13D"
    FORM_13F = "13F"
