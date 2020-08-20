# -*- coding: utf-8 -*-
"""
Utilities for interacting with edgar forms.

:copyright: © 2020 by Mac Gaulin
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
ENCODING_INPUT = "utf-8"
ENCODING_OUTPUT = "utf-8"

RE_DOC_TAG = re.compile("</?DOCUMENT>")
RE_DOC_TAG_OPEN = re.compile("<DOCUMENT>")
RE_DOC_TAG_CLOSE = re.compile("</DOCUMENT>")
RE_TEXT_TAG = re.compile("</?TEXT>")
RE_TEXT_TAG_OPEN = re.compile("<TEXT>")
RE_TEXT_TAG_CLOSE = re.compile("</TEXT>")
# Only matches <KEY>VALUE, no </KEY> nor <KEY>\n
RE_HEADER_TAG = re.compile(r"^<(?P<key>[^/][^>]*)>[ \t]*(?P<value>.+)$", re.M)
# Matches anything like <*>*\n
RE_HEADER_TAG_OC = re.compile(r"^<(?P<key>/?[^>]*)>(?P<value>.*)$", re.M)
# Matches KEY: value
RE_HEADER_TAG_PLAINTEXT = re.compile(r"^(?P<indent>[ \t]*)(?P<key>[^\n\r:]+):[ \t]*(?P<value>[^\n\r]+)?$", re.M)


def get_full_filing(file_path, encoding=None, errors="ignore"):
    """
    Returns full text of filing.
    Calls: `open(file_path, encoding=encoding or ENCODING_INPUT, errors=errors)`

    Args:
        file_path (str or Path): path to the filing to be loaded.
        encoding (str): encoding to use in reading file. Default: `ENCODING_INPUT` (utf-8)
        errors (str): how to handle errors, passed to `open`. Default: `'ignore'`.

    Returns:
        str: Full text of the filing

    Raises:
        FileNotFoundError: Raised if file doesn't exist.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError("File {} does not exist.".format(file_path))

    with open(file_path, encoding=encoding or ENCODING_INPUT, errors=errors or "ignore") as fh:
        return fh.read()


def get_form_with_header(file_path, form_type=None, buff_size=(2 << 16) + 8, encoding=None, errors="ignore"):
    """
    Reads in filing located at `file_path` and returns dictionary of its
    contents and some header information.

    Args:
        file_path (str or Path): path to the filing to be loaded.
        form_type (str): Verify filings TYPE header matches `form_type` or raise `WrongFormType`.
        buff_size (int): Buffer size to read in filings. Default: (2<<16) + 8
        encoding (str): encoding to use in reading file. Default: `ENCODING_INPUT` (utf-8)
        errors (str): how to handle errors, passed to `open`. Default: `'ignore'`.

    Returns:
        dict: Filing and information of the form: {'cik', 'form_type', 'filing_date', 'text':[]}

    Raises:
        FileNotFoundError: Raised if file doesn't exist.
        WrongFormType: Raised if form TYPE header doesn't match `form_type`
        EDGARFilingFormatError: Raised if filing is misformatted (no starting `<DOCUMENT>` tag)
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError("File {} does not exist.".format(file_path))

    with open(file_path, encoding=encoding or ENCODING_INPUT, errors=errors or "ignore", buffering=buff_size) as fh:
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
        ret_dict = {
            "form_type": found_form.upper(),
            "name": get_header(text, "CONFORMED-NAME", endpos=doc_start.start()),
            "sic": get_header(text, "ASSIGNED-SIC", endpos=doc_start.start()),
            "fye": get_header(text, "FISCAL-YEAR-END", endpos=doc_start.start()),
            "filing_date": get_header(text, "FILING-DATE", endpos=doc_start.start()),
            "filing_date_period": get_header(text, "PERIOD", endpos=doc_start.start()),
            "filing_date_change": get_header(text, "DATE-OF-FILING-DATE-CHANGE", endpos=doc_start.start()),
        }
        # Iteratively loop through open file buffer, reading buff_size chunks
        # until </DOCUMENT> tag is found. There is a chance that the tag could
        # be split across chunks, but it's a cost I'm willing to accept.
        chunks = [text]
        while not RE_DOC_TAG_CLOSE.search(chunks[-1]):
            text = fh.read(buff_size)
            if not text:  # prevent infinite loop, text is null when EOF reached
                break
            chunks.append(text)

    # Now put all those chunks together.
    text = "".join(chunks)
    st = RE_DOC_TAG_OPEN.search(text)
    if not st:
        ret_dict["text"] = text
        return ret_dict
    en = RE_DOC_TAG_CLOSE.search(text, st.end())  # start searching after start
    if not en:
        ret_dict["text"] = text[st.end()]
        return ret_dict

    ret_dict["text"] = text[st.end() : en.start()]

    return ret_dict


def get_form(file_path, encoding=None, errors="ignore", chunk_size=1024 ** 2):
    """
    Reads file at file_path and returns form between <TEXT> and </TEXT> tags.
    Default is to chunk the file being read, because sometimes 225MB files have
    only 1MB of text in the first document. So speed that up.
    Set chunk_size=None to disable chunking.

    Args:
        file_path (str or Path): path to the filing to be loaded.
        encoding (str): encoding to use in reading file. Default: `ENCODING_INPUT` (utf-8)
        errors (str): how to handle errors, passed to `open`. Default: `'ignore'`.
        chunk_size (int): Size of chunks to read of file, until end of first document
            is found. Disable with `chunk_size=None`. Default: 1MB

    Returns:
        str: Text of the first document.

    Raises:
        FileNotFoundError: Raised if file doesn't exist.
        EDGARFilingFormatError: Raised if filing is misformatted (no starting `<DOCUMENT>` tag)
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError("File {} does not exist.".format(file_path))

    if chunk_size is not None and os.stat(file_path).st_size < 2 * chunk_size:
        chunk_size = None

    with open(file_path, encoding=encoding or ENCODING_INPUT, errors=errors, buffering=chunk_size or -1) as fh:
        if chunk_size is None:
            text = fh.read()
        else:
            chunks = []
            # Avoid while True, so set range to 10GB / buffer size
            for i in range(int(10 * 1024 ** 3 // chunk_size) + 1):
                chunks.append(fh.read(chunk_size))

                _doc_match = RE_DOC_TAG_CLOSE.search(chunks[-1])
                _txt_match = RE_TEXT_TAG_CLOSE.search(chunks[-1])

                # Look for doc or text end if neither found, continue
                if not _doc_match and not _txt_match:
                    continue

                # If we're here, one or both were found. So we're done.
                break

            text = "".join(chunks)

    en = RE_TEXT_TAG_CLOSE.search(text)  # start searching after start
    if not en:
        raise EDGARFilingFormatError("No ending TEXT tag found, despite ending DOCUMENT found.")

    st = RE_TEXT_TAG_OPEN.search(text, endpos=en.start())
    if not st:
        raise EDGARFilingFormatError("No starting TEXT tag found, despite ending TEXT found.")

    return text[st.end() : en.start()].strip()


def get_plaintext(path, unwrap=True, document_width=150, just_first=True):
    """
    Get the plaintext version of an edgar filing.
    Assumes the first exhibit in the full filing text document.
    If HTML, uses w3m linux program to parse into plain text.
    If `unwrap`, also unwraps paragraphs so each paragraph is on one line.

    Args:
        path (str or Path): Full path to form.
        unwrap (bool): Whether to call `plaintext.unwrap_plaintext` on document.
        document_width (int): How wide the plaintext will be. Used in unwrapping.

    Returns:
        str: Plain text representation of file.
    """
    text = get_form(path)

    return convert_html_to_text(text, unwrap=unwrap, document_width=document_width)


def get_all_headers(text, flat=False, force_sgml=False, **kwargs):
    """
    <KEY>VALUE formatted headers in EDGAR documents.
    Dictionary is either iterative (`flat=False`, default) where open/close
    SGML tags are nested dictionaries, or flat, where multiple keys
    are either ignored, renamed, or put in a list (see `get_all_headers_flat`).

    Note: this works on either SGML headers or formatted, web version headers,
    but SGML parsing can be forced with `force_sgml`.

    Dictionary keys are lowercase (`.lower()` is called), and stripped.
    """
    if "ACCESSION NUMBER:" in text[:2000] and not force_sgml:
        if flat:
            return get_all_headers_flat_nosgml(text, **kwargs)
        return get_all_headers_dict_nosgml(text, **kwargs)
    if flat:
        return get_all_headers_flat(text, **kwargs)
    return get_all_headers_dict(text, **kwargs)


def get_all_headers_flat(text, pos=0, endpos=None, omit_duplicates=False, add_int_to_name=False, **kwargs):
    """
    Return dictionary of all <KEY>VALUE formatted headers in EDGAR documents.
    Note this requires the daily feed version of the EDGAR files.
    Dictionary keys are lowercase (`.lower()` is called), and stripped.

    `pos` and `endpos` can be used to get headers for specific exhibits.

    Keys with the same name can either be ignored (`omit_duplicates=True`),
    or subsequent keys with names already in dictionary can be renamed
    by adding a count to the end (filer, filer_1, etc.) if
    `add_int_to_name=True`, or added to a list if `add_int_to_name=False`.

    Returns dictionary of headers.
    """
    if endpos is None:
        _, endpos = _get_header_bounds(text, pos=pos)

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
                newkey = "{}_{}".format(key, i)
                if newkey not in ret:
                    key = newkey
                    break
            ret[key] = val
            continue

        if not isinstance(ret[key], list):
            ret[key] = [
                ret[key],
            ]

        ret[key].append(val)

    return ret


def get_all_headers_flat_nosgml(text, pos=0, endpos=None, omit_duplicates=False, add_int_to_name=False, **kwargs):
    """
    Return dictionary of all <KEY>VALUE formatted headers in EDGAR documents.
    Note this requires the daily feed version of the EDGAR files.
    Dictionary keys are lowercase (`.lower()` is called), and stripped.

    `pos` and `endpos` can be used to get headers for specific exhibits.

    Keys with the same name can either be ignored (`omit_duplicates=True`),
    or subsequent keys with names already in dictionary can be renamed
    by adding a count to the end (filer, filer_1, etc.) if
    `add_int_to_name=True`, or added to a list if `add_int_to_name=False`.

    Returns:
        dict: Dictionary of headers.
    """
    if endpos is None:
        _, endpos = _get_header_bounds(text, pos=pos)

    ret = {}
    for rx in RE_HEADER_TAG_PLAINTEXT.finditer(text, pos, endpos):
        _, key, val = rx.groups()
        try:
            key, val = _clean_plaintext_header_key(key.lower()), val.strip()
        except AttributeError:
            # val.strip() breaks if val is None.
            continue

        if not val:
            continue

        if key not in ret:
            ret[key] = val
            continue

        if omit_duplicates:
            continue

        if add_int_to_name:
            for i in range(1, 10000):
                newkey = "{}_{}".format(key, i)
                if newkey not in ret:
                    key = newkey
                    break
            ret[key] = val
            continue

        if not isinstance(ret[key], list):
            ret[key] = [
                ret[key],
            ]

        ret[key].append(val)

    return ret


def get_all_headers_dict(
    text, pos=0, endpos=None, starter_dict=None, omit_duplicates=False, add_int_to_name=False, **kwargs
):
    """
    Return dictionary of all <KEY>VALUE formatted headers in EDGAR documents.
    Note this requires the daily feed version of the EDGAR files.
    Dictionary keys are lowercase (`.lower()` is called), and stripped.

    `pos` and `endpos` can be used to get headers for specific exhibits.

    Keys with the same name can either be ignored (`omit_duplicates=True`),
    or subsequent keys with names already in dictionary can be renamed
    by adding a count to the end (filer, filer_1, etc.) if
    `add_int_to_name=True`, or added to a list if `add_int_to_name=False`.
    """
    if endpos is None:
        _, endpos = _get_header_bounds(text, pos=pos)

    retdict = {}
    if starter_dict is not None:
        retdict.update(starter_dict)
    # push and pop 'current' dictionary from stack, which works because pointers.
    stack = [
        retdict,
    ]

    for imatch in RE_HEADER_TAG_OC.finditer(text, pos, endpos):
        tmp = imatch.groupdict()
        # if 'key' not in tmp or 'value' not in tmp:
        #     continue
        key, val = tmp["key"].lower(), tmp["value"].strip()

        if "/" in key:
            # Then it's a closing tag. pop the last dict off the stack
            if len(stack) > 1:
                stack.pop()
            # If there's a value... we don't care. That's bad formatting.
            continue
        elif val:
            # Then just a normal key.
            # Add to the dict at the end of the stack, checking for dups
            if key not in stack[-1]:
                stack[-1][key] = val
                continue

            if omit_duplicates:
                continue

            if add_int_to_name:
                for i in range(1, 10000):
                    newkey = "{}_{}".format(key, i)
                    if newkey not in stack[-1]:
                        key = newkey
                        break
                stack[-1][key] = val
                continue

            if not isinstance(stack[-1][key], list):
                stack[-1][key] = [
                    stack[-1][key],
                ]

            stack[-1][key].append(val)
            continue

        # Otherwise this might be a sub-group. Look for the </KEY> tag.
        re_end = re.compile("</{}>".format(key), re.I)
        if re_end.search(text, imatch.end(), endpos):
            # Then we found the end tag. Create dict at KEY if KEY doesn't exist
            if key in stack[-1]:
                # Then try key_X for X from 0 to 200 I guess.
                for key_i in range(200):
                    newkey = "{}_{}".format(key, key_i)
                    if newkey not in stack[-1]:
                        key = newkey
                        break
            # make a new dict at KEY
            stack[-1][key] = {}
            stack.append(stack[-1][key])

    return retdict


def get_all_headers_dict_nosgml(text, pos=0, endpos=None, starter_dict=None, **kwargs):
    """
    Return dictionary of all KEY: VALUE formatted headers in EDGAR documents.
    Note this requires the EDGAR website version of the EDGAR files.
    Dictionary keys are lowercase (`.lower()` is called), and stripped.

    `pos` and `endpos` can be used to get headers for specific exhibits.
    """

    def newkey(key):
        if key in stack[-1]:
            # Then try key_X for X from 0 to 2000 I guess.
            for key_i in range(2000):
                newkey = "{}_{}".format(key, key_i)
                if newkey not in stack[-1]:
                    return newkey
        return key

    if endpos is None:
        _, endpos = _get_header_bounds(text, pos=pos)

    retdict = {}
    if starter_dict is not None:
        retdict.update(starter_dict)
    # push and pop 'current' dictionary from stack, which works because pointers.
    stack = [
        retdict,
    ]

    for imatch in RE_HEADER_TAG_PLAINTEXT.finditer(text, pos, endpos):
        tmp = imatch.groupdict()
        # print(f"\nStarting with {tmp}")
        # print(f"Stack length: {len(stack)}")

        indent = tmp["indent"]  # empty for level 0, 1 \t for each level
        key = _clean_plaintext_header_key(tmp["key"].lower())
        try:
            val = tmp["value"].strip()
        except AttributeError:
            val = None

        if len(indent) + 1 < len(stack) and key:
            # We've found an out-dent, drop off a level.
            # Remove last dict from stack and make a new one if val missing
            # print(f"Found new outdent ({key}): len({len(indent)}) + 1 < {len(stack)}")

            while len(stack) > len(indent) + 1:
                stack.pop()
                # print(f"Stack pop, new len: {len(stack)}")

        if not val:
            # We've found the start of a new indent level.
            # Add key to the dict and push new level to stack
            # print(f"Found new indent ({key}): val is {val}")
            key = newkey(key)
            stack[-1][key] = {}
            stack.append(stack[-1][key])
            continue

        # print(f"Adding key/val {key}:{val}")
        stack[-1][newkey(key)] = val

    return retdict


def get_header(text, header, pos=0, endpos=None, return_match=False, return_multiple=False):
    """
    Searches `text` for header formatted <`header`>VALUE\\n and returns VALUE.strip()
    Note this requires the daily feed version of the EDGAR files.

    `pos` and `endpos` can be used to get headers for specific exhibits.
    """
    if endpos is None:
        _, endpos = _get_header_bounds(text, pos=pos)

    re_tag = re.compile(r"^<{}>(.+)$".format(header), re.M | re.I)

    match = re_tag.search(text, pos, endpos)
    value = match.group(1).strip() if match else ""

    if return_match:
        return value, match
    return value


def _get_header_bounds(text, pos=0, endpos=None, **kwargs):
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
    if endpos is None:
        doc_tag_open = RE_DOC_TAG_OPEN.search(text, pos=pos)
        if doc_tag_open:
            endpos = doc_tag_open.start()
    if endpos is None:
        endpos = len(text)

    return pos, endpos


def _clean_plaintext_header_key(
    key, replace_with_dash=re.compile(r" (?![1-9])"), replace_with_empty=re.compile(r" (?=[1-9])")
):
    return replace_with_dash.sub("-", replace_with_empty.sub("", key.strip()))


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
        raise EDGARFilingFormatError("Uneven number of <DOCUMENT> tags found." "Found: {}".format(doc_tags))

    for i, tag in enumerate(doc_tags):
        if (i % 2) ^ ("/" in tag):
            raise EDGARFilingFormatError("<DOCUMENT> tags do not alternate open/close." "Found: {}".format(doc_tags))

    docs = []
    for _start, _end in zip(RE_DOC_TAG_OPEN.finditer(text), RE_DOC_TAG_CLOSE.finditer(text)):

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
        doc["full_text"] = text[text_start.end() : text_end.start()]

        docs.append(doc)

    return docs


class CIKS(object):
    GOOGLE = 1288776
    ALPHABET = 1652044
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
