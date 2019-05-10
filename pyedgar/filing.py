# -*- coding: utf-8 -*-
"""
Base class for EDGAR filing.

:copyright: © 2019 by Mac Gaulin
:license: MIT, see LICENSE for more details.
"""

# import os
import re
import logging

from pyedgar.utilities import edgarweb
from pyedgar.utilities import forms
from pyedgar.utilities.forms import FORMS
from pyedgar.utilities import localstore

class Filing(object):
    """
    Base class for EDGAR filing, with format aware parsing
    to provide access to filing documents as objects.
    """
    # Every form has a CIK and accession.
    _cik = None
    _accession = None
    # Set the form type, with some family hierarchy: 10s, Def 14s, etc.
    _type = None
    _type_exact = None
    # Paths to local and remote filing. Set lazily.
    _filing_local_path = None
    _filing_url = None
    # Form Data (main headers)
    _headers = {}
    _full_text = None
    _documents = None
    # Object logger for logging things and stuff.
    __log = None
    # Read-filing arguments
    read_args = None

    def __init__(self, cik=None, accession=None, **kwargs):
        """
        Initialization sets CIK, Accession, and optionally
        loads filing from disk.

        Args:
            cik: Numeric CIK for firm.
            accession: Accession for filing, filed under CIK.
                Expected format: 0123456789-01-012345, or 012345678901012345.

        Returns:
            Filing object.

        Raises:
            None. Loading done lazily.
        """
        self.__log = logging.getLogger('pyedgar.filing.Filing')

        self._set_cik(cik)
        self._set_accession(accession)

        self.read_args = kwargs

    def __repr__(self):
        return ("<EDGAR filing ({}/{}) Headers:{}, Text:{}, Documents:{}>"
                .format(self.cik, self.accession,
                        bool(self._headers),
                        bool(self._full_text),
                        bool(self._documents),))

    def __str__(self):
        return self.__repr__()

    def _set_cik(self, cik=None):
        """
        Set cik on object, verifying format is CIK-like.

        Args:
            cik: Numeric CIK for firm, either as int or string.

        Returns:
            CIK as an int.

        Raises:
            ValueError: if cik is not numerical (or castable to int).
        """
        try:
            if cik is not None:
                self._cik = int(cik)
        except ValueError:
            # They didn't pass in a CIK that looked like a number
            raise ValueError("CIKs must be numeric variables,"
                             " you passed in {}".format(cik))

        return self._cik

    def _set_accession(self, accession=None):
        """
        Set accession on object, verifying format is accession-like.
        Expected format: 0123456789-01-012345, or 012345678901012345.
        Function converts the latter to the former.

        Args:
            accession: Accession number as a string, with format
                0123456789-01-012345, or 012345678901012345.
        Returns:
            The formatted Accession as a string of 20 characters.

        Raises:
            ValueError: if accession is not expected format.
        """
        try:
            if accession and localstore.ACCESSION_RE.search(accession):
                if len(accession) == 18:
                    self._accession = '{}-{}-{}'.format(accession[:10],
                                                        accession[10:12],
                                                        accession[12:])
                else:
                    self._accession = accession
        except TypeError:
            # They didn't pass in an accession that was a string.
            raise ValueError("Accessions must be 18/20 character strings of format"
                             " ##########-##-######, you passed in {}"
                             .format(accession))

        return self.accession

    def _set_full_text(self):
        """
        Full text of the filing at cik/accession.
        Lazily load the full text of the filing into memory.

        Args: None

        Returns:
            String representing the full text of the EDGAR filing.

        Raises:
            FileNotFoundError: The file wasn't found in the local cache.
        """
        if not self._full_text:
            try:
                self._full_text = forms.get_full_filing(self.path, **self.read_args)
            except FileNotFoundError:
                msg = ("Filing not found for CIK:{} / Accession:{}"
                       .format(self._cik, self._accession))
                self.__log.debug(msg)
                raise FileNotFoundError(msg)

        return self._full_text

    def _set_headers(self, set_flat=True, set_hierarchical=True):
        """
        Load the full set of headers of the filing at cik/accession into memory.
        """
        if not self.full_text:
            self.__log.debug("Full filing text missing or not found!")
            return None
        if set_flat:
            self._headers = forms.get_all_headers_flat(self.full_text)
        if set_hierarchical:
            self._headers.update(forms.get_all_headers_dict(self.full_text))

        return self._headers

    def _set_type(self):
        """
        Full text of the filing at cik/accession.
        Lazily load the full text of the filing into memory.

        Args: None

        Returns:
            String representing the full text of the EDGAR filing.

        Raises:
            FileNotFoundError: The file wasn't found in the local cache.
        """
        _t = self.headers.get('type', 'OTHER')
        self._type_exact = _t

        self._type = 'other'
        if _t in ('3', '3/A'):
            self._type = FORMS.FORM_3
        elif _t in ('4', '4/A'):
            self._type = FORMS.FORM_4
        elif _t in ('8-K', '8-K/A'):
            self._type = FORMS.FORM_8K
        elif _t[:4] in ('10-Q' '10QS'):
            self._type = FORMS.FORM_10Q
        elif _t[:4] in ('10-K' '10KS'):
            self._type = FORMS.FORM_10K
        elif _t.endswith('14A'):
            self._type = FORMS.FORM_DEF14A
        elif 'SC 13G' in _t:
            self._type = FORMS.FORM_13G
        elif 'SC 13D' in _t:
            self._type = FORMS.FORM_13D
        elif '13F-' in _t:
            self._type = FORMS.FORM_13F

        return self._type

    def _set_documents(self):
        """
        Parse the full text of the filing and split it into the
        documents/exhibits with associated meta data.
        Full text of the documents resides at documents[i]['full_text'].
        """
        if not self.full_text:
            self.__log.debug("Full filing text missing or not found!")
            return None
        self._documents = forms.chunk_filing(self.full_text)

        return self._documents

    cik = property(fget=lambda self: self._cik, fset=_set_cik)
    accession = property(fget=lambda self: self._accession, fset=_set_accession)

    @property
    def path(self):
        """
        Get the filing path internal variable.
        Sets it lazily the first time it is used.
        """
        if not self._filing_local_path:
            self._filing_local_path = localstore.get_filing_path(cik=self._cik, accession=self._accession)

        return self._filing_local_path

    @property
    def urls(self):
        """
        Get the URLs to the filing path.
        Return is tuple with (url to raw filing, url to index on EDGAR)
        """
        if not self._filing_url:
            self._filing_url = edgarweb.get_edgar_urls(self._cik, self._accession)

        return self._filing_url

    @property
    def full_text(self):
        """
        Full text of the filing at cik/accession.
        Lazily load the full text of the filing into memory.
        """
        return self._full_text or self._set_full_text()

    @property
    def headers(self):
        """
        Full set of headers of the filing at cik/accession.
        Lazily load the headers of the filing into memory.
        """
        return self._headers or self._set_headers()

    @property
    def type(self):
        """
        Generic type of the filing at cik/accession, from:
        3, 4, 8-K, 10-K, 10-Q, DEF14A, 13G, 13D, 13F
        Lazily load the headers of the filing into memory.
        """
        return self._type or self._set_type()

    @property
    def type_exact(self):
        """
        Exact TYPE header of the filing at cik/accession.
        Lazily load the headers of the filing into memory.
        """
        return self._type or self._set_type()

    @property
    def documents(self):
        """
        Full set of documents/exhibits of the filing at cik/accession.
        Lazily load the documents of the filing into memory.
        Full text of the documents resides at documents[i]['full_text'].
        """
        return self._documents or self._set_documents()

    def get_sequence_number(self, sequence_number):
        """
        Access exhibits (or main filing) by sequence number (1-indexed).

        Args:
            sequence_number: 1-indexed int representing the sequence
                of the document in the EDGAR filing. Identified using
                the 'sequence' tag in each <DOCUMENT> element.

        Returns:
            Array of document dictionaries in the form:
            [{search_key: search_string, 'full_text':...}, ...]
            or None, if no document is available or sequence is not found.

        Raises:
            None
        """
        if not self.documents:
            return None

        for doc in self.documents:
            try:
                i_seq = int(doc.get('sequence', -1337))
                if sequence_number == i_seq:
                    return doc
            except ValueError:
                # then try matching sequences as strings.
                i_seq = doc.get('sequence', '').strip()
                if str(sequence_number) == i_seq:
                    return doc

    def get_documents_by_tag(self, tag_name, search_string, regex=False, flags=0):
        """
        Search document dictionaries for `tag_name` that matches `search_string`.
        Returns array of document dictionaries that match the requirement:
        search_string == document[tag_name], or using `regex=True`,
        search_string.search(document['filename'])

        Args:
            tag_name: dictionary key in document dicts to match against.
            search_string: string to search for in document[tag_name]
            regex: Boolean signifying that search_string should use a regular
                expression match. If search_string isn't a compiled regex
                pattern, then compile it using flags=flags.
            flags: Optional flags to use when compiling search_string,
                if it isn't a re.Pattern already.

        Returns:
            Array of document dictionaries in the form:
            [{tag_name: search_string, 'full_text':...}, ...]
            or None, if no document is available or string is not found.

        Raises:
            None
        """
        if not self.documents or not search_string or not tag_name:
            return None

        if regex:
            search_re = search_string
            if not hasattr(search_re, 'search'):
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
