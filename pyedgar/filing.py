# -*- coding: utf-8 -*-
"""
Base class for EDGAR filing.

Meant to be easily overridden. For example, to create a filing class that allows for easy extraction of
BeautifulSoup documents and local caching (e.g. if reading from edgar website):

```python
import os
from bs4 import BeautifulSoup
from IPython.display import display_html
import pyedgar
from pyedgar.utilities import htmlparse

class Filing(pyedgar.Filing):
    # caches filings in a directory next to this file called data/cache
    DATA_ROOT = "data"

    @property
    def cache_path(self):
        return os.path.join(self.DATA_ROOT, 'cache', self.accession.split('-')[1], f"{self.accession}.txt")

    def _cache_local(self, doc_to_cache):
        try:
            with open(self.cache_path, 'w') as fh:
                fh.write(doc_to_cache)
        except FileNotFoundError:
            # ## directory doesn't exists, make it and recall. If the parent doesn't exist either
            #  (the cache folder) then it'll error out below, so no infinite recursion.
            os.mkdir(os.path.dirname(self.cache_path))
            return self._cache_local(doc_to_cache)
        except Exception:
            # I guess caching didn't work...
            return doc_to_cache

    def _post_init_hook(self, **kwargs):
        self._local_cache = True
        if os.path.exists(self.cache_path):
            self._filing_local_path = self.cache_path

        for k,v in kwargs.items():
            if k not in self.__dict__:
                setattr(self, k, v)

    def _set_full_text(self):
        _txt = super()._set_full_text()

        try:
            if not os.path.exists(self.cache_path):
                self._cache_local(_txt)
        except Exception:
            pass

        return _txt

    def is_html(self, docnum=0, *args, **kwargs):
        return htmlparse.is_html(self.documents[docnum]['full_text'], *args, **kwargs)

    def soup(self, docnum=0, *args, **kwargs):
        return BeautifulSoup(self.documents[docnum]['full_text'], *args, **kwargs)

    def print(self, docnum=0):
        '''jupyter notebook aware print function'''
        if self.is_html(docnum):
            display_html(self.documents[docnum]['full_text'], raw=True)
        else:
            print(self.documents[docnum]['full_text'])
```

:copyright: © 2025 by Mac Gaulin
:license: MIT, see LICENSE for more details.
"""

# import os
import re
import logging

try:
    from bs4 import BeautifulSoup
except ImportError:
    pass

from pyedgar import config
from pyedgar.utilities import get_cik_acc, edgarweb, forms, localstore, htmlparse
from pyedgar.utilities.forms import FORMS


class Filing(object):
    """
    Base class for EDGAR filing, with format aware parsing
    to provide access to filing documents as objects.
    """

    #: Firm CIK
    _cik = None
    #: Filing Accession
    _accession = None
    #: Whether filings are cached locally, or to get them from EDGAR
    _local_cache = False
    #: If filing is not found, fallback to downloading from the web.
    _web_fallback = True
    #: The 'loose' form type, with some family hierarchy: 10s, Def 14s, etc.
    _type = None
    #: The exact form type, extracted from the main <TYPE> tag.
    _type_exact = None
    #: Paths to local filing. Set lazily.
    _filing_local_path = None
    #: Paths to remote filing. Set lazily.
    _filing_url = None
    #: Form Data (main headers)
    _headers = {}
    #: Full text of the document, loaded lazily.
    _full_text = None
    #: Array of filed exhibits, parsed lazily.
    _documents = None
    #: Object logger for logging things and stuff.
    __log = None
    #: Read-filing arguments
    read_args = None
    #: get_header arguments
    header_args = None

    def __init__(
        self,
        cik=None,
        accession=None,
        use_cache=None,
        web_fallback=True,
        flat_headers=True,
        omit_duplicate_headers=False,
        duplicate_headers_as_list=True,
        read_kwargs=None,
        **kwargs,
    ):
        """
        Initialization sets CIK, Accession, and optionally
        loads filing from disk.

        Args:
            cik (int,str): Numeric CIK for firm.
            accession (str): Accession for filing, filed under CIK.
                Expected format: 0123456789-01-012345, or 012345678901012345.
            use_cache (bool): Use the local cache at `config.FEED_CACHE_ROOT`,
                default to `config.CACHE_FEED`.
            web_fallback (bool): When FileNotFoundError is raised, try
                `edgarweb.download_form_from_web` instead.
            flat_headers (bool): Set the style of loading headers. If True,
                all headers will be loaded in one dictionary. If False, headers
                will be loaded as a hierarchical set of dictionaries, matching
                the hierarchy in the filing's headers. Default: True.
            omit_duplicate_headers (bool): Passed to `get_all_headers()`, if True
                will ignore duplicate headers (e.g. 8-K items) keeping the first.
                Default: False.
            duplicate_headers_as_list (bool): Passed to `get_all_headers()`,
                if True will return the header values as a list (e.g. ['5.02',
                '5.07', '9.01']). If False will add _# to duplicate header names.
                Default: True.
            read_kwargs (dict, None): Dictionary passed as read args. Defaults to None.

        Returns:
            Filing object.

        Raises:
            None. Loading done lazily.
        """
        self.__log = logging.getLogger("pyedgar.filing.Filing")

        if accession is None:
            try:
                _ac = get_cik_acc(cik)
                cik, accession = _ac['cik'], _ac['accession']
            except TypeError as exc:
                raise ValueError(f"CIK/Accession input not formatted as expected. Got: {cik}/{accession}") from exc

        self._set_cik(cik)
        self._set_accession(accession)

        self._local_cache = use_cache if use_cache is not None else config.CACHE_FEED
        self._web_fallback = web_fallback

        self.read_args = read_kwargs or {}
        self.header_args = {
            "flat": flat_headers,
            "omit_duplicates": omit_duplicate_headers,
            "add_int_to_name": not duplicate_headers_as_list,
        }

        self._post_init_hook(**kwargs)

    def _post_init_hook(self, **kwargs):
        """
        Post init hook, called at the end of init. Used for hooking into initialization and gets
        all extra keyword arguments passed to init.

        Empty by default, but used to do things like store data, handle local caching, etc. Example::

        ```python
        def gvkeyFiling(pyedgar.filing.Filing):
            def _post_init_hook(self, **kwargs):
                self.gvkey = kwargs.get('gvkey', -1)
        ```
        """
        return self

    def __repr__(self):
        return (
            f"<EDGAR filing ({self.cik}/{self.accession}) Loaded Headers:{bool(self._headers)}, "
            f"Text:{bool(self._full_text)}, Documents:{bool(self._documents)}>"
        )

    def __str__(self):
        return self.__repr__()

    #===================================================================================================================
    #             Helper functions
    #===================================================================================================================
    def _set_cik(self, cik=None):
        """
        Set cik on object, verifying format is CIK-like.

        Args:
            cik (int,str): Numeric CIK for firm, either as int or string.

        Returns:
            int: CIK of the filing.

        Raises:
            ValueError: if cik is not numerical (or castable to int).
        """
        try:
            if cik is not None:
                self._cik = int(cik)
        except ValueError as exc:
            # They didn't pass in a CIK that looked like a number
            raise ValueError(f"CIKs must be numeric variables, you passed in {cik}") from exc

        return self._cik

    def _set_accession(self, accession=None):
        """
        Set accession on object, verifying format is accession-like.
        Expected format: 0123456789-01-012345, or 012345678901012345.
        Function converts the latter to the former.

        Args:
            accession (str): Accession number as a string, with format
                0123456789-01-012345, or 012345678901012345.

        Returns:
            The formatted Accession as a string of 20 characters.

        Raises:
            ValueError: if accession is not expected format.
        """
        try:
            if accession and localstore.ACCESSION_RE.search(accession):
                if len(accession) == 18:
                    self._accession = f"{accession[:10]}-{accession[10:12]}-{accession[12:]}"
                else:
                    self._accession = accession
        except TypeError as exc:
            # They didn't pass in an accession that was a string.
            raise ValueError(
                f"Accessions must be 18/20 character strings of format ##########-##-######, you passed in {accession}"
            ) from exc

        return self.accession

    def _set_full_text(self):
        """
        Full text of the filing at cik/accession.
        Lazily load the full text of the filing into memory.
        Use cache if `self._local_cache`, and fall back to EDGAR website
        if `self._web_fallback`.

        Returns:
            String representing the full text of the EDGAR filing.

        Raises:
            FileNotFoundError: The file wasn't found in the local cache if
                `self._local_cache`.
        """
        if not self._full_text:
            self.__log.debug("Local cache: %r", self._local_cache)
            if self._local_cache:
                self.__log.debug("Local cache if: %r", self._local_cache)
                try:
                    self._full_text = forms.get_full_filing(self.path, **self.read_args)
                    return self._full_text
                except FileNotFoundError as exc:
                    msg = f"Filing not found for CIK:{self.cik} / Accession:{self.accession}"
                    self.__log.debug(msg)
                    if not self._web_fallback:
                        raise FileNotFoundError(msg) from exc

            if self._web_fallback:
                self.__log.debug("Downloading from EDGAR web: %d/%s", self.cik, self.accession)
                self._full_text = edgarweb.download_form_from_web(self.cik, self.accession)

        return self._full_text

    def _set_headers(self, **load_kwargs):
        """
        Load the full set of headers of the filing at cik/accession into memory.

        Args:
            Optional load arguments passed to `forms.get_all_headers()`

        Returns:
            dict: Dictionary of headers, with either flat, hierarchical, both,
                or neither, depending on `self._flat_headers`.
        """
        if not self.full_text:
            self.__log.debug("Full filing text missing or not found!")
            return None

        self._headers = forms.get_all_headers(self.full_text, **{**self.header_args, **load_kwargs})

        return self._headers

    def _set_type(self):
        """
        Full text of the filing at cik/accession.
        Lazily load the full text of the filing into memory.

        Returns:
            String representing the full text of the EDGAR filing.

        Raises
            ileNotFoundError: The file wasn't found in the local cache.
        """
        _t = self.headers.get("type", self.headers.get("conformed-submission-type", "OTHER"))
        self._type_exact = _t

        self._type = "other"
        if _t in ("3", "3/A"):
            self._type = FORMS.FORM_3
        elif _t in ("4", "4/A"):
            self._type = FORMS.FORM_4
        elif _t in ("8-K", "8-K/A"):
            self._type = FORMS.FORM_8K
        elif _t[:4] in ("10-Q" "10QS"):
            self._type = FORMS.FORM_10Q
        elif _t[:4] in ("10-K" "10KS"):
            self._type = FORMS.FORM_10K
        elif _t.endswith("14A"):
            self._type = FORMS.FORM_DEF14A
        elif "SC 13G" in _t:
            self._type = FORMS.FORM_13G
        elif "SC 13D" in _t:
            self._type = FORMS.FORM_13D
        elif "13F-" in _t:
            self._type = FORMS.FORM_13F

        return self._type

    def _set_documents(self):
        """
        Parse the full text of the filing and split it into the
        documents/exhibits with associated meta data.
        Full text of the documents resides at documents[i]['full_text'].

        Returns:
            list: List of document objects. ['full_text'] contains the document
                text.
        """
        if not self.full_text:
            self.__log.debug("Full filing text missing or not found!")
            return None
        self._documents = forms.chunk_filing(self.full_text)

        return self._documents

    #===================================================================================================================
    #             Properties
    #===================================================================================================================
    cik = property(fget=lambda self: self._cik, fset=_set_cik)
    accession = property(fget=lambda self: self._accession, fset=_set_accession)

    @property
    def path(self):
        """
        Get the filing path internal variable.
        Sets it lazily the first time it is used.

        Returns:
            str: The full path of the local cache.
        """
        if not self._filing_local_path:
            self._filing_local_path = localstore.get_filing_path(cik=self.cik, accession=self.accession)

        return self._filing_local_path

    @property
    def urls(self):
        """
        Get the URLs to the filing path.

        Returns:
            tuple: (url to raw filing, url to index on EDGAR)
        """
        if not self._filing_url:
            self._filing_url = edgarweb.get_edgar_urls(self.cik, self.accession)

        return self._filing_url

    @property
    def full_text(self):
        """
        Full text of the filing at cik/accession.
        Lazily load the full text of the filing into memory.

        Returns:
            str: Full document of the filing, equivalent to viewing raw file.
        """
        return self._full_text or self._set_full_text()

    @property
    def headers(self):
        """
        Full set of headers of the filing at cik/accession.
        Lazily load the headers of the filing into memory.

        Returns:
            dict: Dictionary of the headers, either flat or hierarchical
                depending on the filing object attributes.
        """
        return self._headers or self._set_headers()

    @property
    def type(self):
        """
        Generic type of the filing at cik/accession, from:
        3, 4, 8-K, 10-K, 10-Q, DEF14A, 13G, 13D, 13F
        Lazily load the headers of the filing into memory.

        Returns:
            str: Type string of the document, simplified.
        """
        return self._type or self._set_type()

    @property
    def type_exact(self):
        """
        Exact TYPE header of the filing at cik/accession.
        Lazily load the headers of the filing into memory.

        Returns:
            str: Full type string of the document from the header.
        """
        self.type
        return self._type_exact

    @property
    def documents(self):
        """
        Full set of documents/exhibits of the filing at cik/accession.
        Lazily load the documents of the filing into memory.
        Full text of the documents resides at documents[i]['full_text'].

        Returns:
            list: List of all documents in the filing.
        """
        return self._documents or self._set_documents()


    #===================================================================================================================
    #             Method functions
    #===================================================================================================================
    def get_sequence_number(self, sequence_number):
        """
        Access exhibits (or main filing) by sequence number (1-indexed).

        Args:
            sequence_number (int): 1-indexed int representing the sequence
                of the document in the EDGAR filing. Identified using
                the 'sequence' tag in each <DOCUMENT> element.

        Returns:
            Array of document dictionaries in the form:
            ``[{search_key: search_string, 'full_text':...}, ...]``
            or ``None``, if no document is available or sequence is not found.
        """
        if not self.documents:
            return None

        for doc in self.documents:
            try:
                i_seq = int(doc.get("sequence", -1337))
                if sequence_number == i_seq:
                    return doc
            except ValueError:
                # then try matching sequences as strings.
                i_seq = doc.get("sequence", "").strip()
                if str(sequence_number) == i_seq:
                    return doc

    def get_documents_by_tag(self, tag_name, search_string, regex=False, flags=0):
        """
        Search document dictionaries for `tag_name` that matches `search_string`.
        Returns array of document dictionaries that match the requirement:
        ``search_string == document[tag_name]``, or using `regex=True`,
        ``search_string.search(document['filename'])``
\
        Args:
            tag_name (str): dictionary key in document dicts to match against.
            search_string (str): string to search for in ``document[tag_name]``
            regex (str): Boolean signifying that search_string should use a regular
                expression match. If search_string isn't a compiled regex
                pattern, then compile it using flags=flags.
            flags (str): Optional flags to use when compiling search_string,
                if it isn't a ``re.Pattern`` already.

        Returns:
            Array of document dictionaries in the form:
            ``[{tag_name: search_string, 'full_text':...}, ...]``
            or ``None``, if no document is available or string is not found.
        """
        if not self.documents or not search_string or not tag_name:
            return None

        if regex:
            search_re = search_string
            if not hasattr(search_re, "search"):
                search_re = re.compile(search_re, flags=flags)

        ret = []
        for doc in self.documents:
            if tag_name not in doc:
                continue
            match_against = doc.get(tag_name)
            if not regex and search_string == match_against:
                ret.append(doc)
            elif regex and search_re.search(match_against):
                ret.append(doc)

        return ret


class HTMLFiling(Filing):
    """
    Filing with convenience functions for dealing with HTML documents. Adds the classes:

    * `is_html()`: Boolean flag for whether specified document (`docnum=X`) is HTML format
    * `soup()`: Returns a BeautifulSoup object of specified document (note: does not check is_html)
    """
    def is_html(self, docnum=0, **kwargs):
        return htmlparse.is_html(self.documents[docnum]['full_text'], **kwargs)

    def soup(self,  *args, docnum=0, **kwargs):
        """
        Returns the document at `docnum` as a BeautifulSoup object.
        Args/Kwargs are passed along to BeautifulSoup, so docnum must be specified as a keyword argument,
         e.g.: `filing.soup('lxml', docnum=1)`
        """
        return BeautifulSoup(self.documents[docnum]['full_text'], *args, **kwargs)
