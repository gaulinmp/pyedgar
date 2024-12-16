#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Download and cache a local copy of EDGAR.
Allows for caching of downloaded daily zips and index files.

EDGAR HTML specification: https://www.sec.gov/info/edgar/ednews/edhtml.htm
EDGAR FTP specification: https://www.sec.gov/edgar/searchedgar/ftpusers.htm

URL Change in 2016:
  <2016 ftp URL: ftp://ftp.sec.gov/edgar/data/2098/0000002098-96-000003.txt
  >2016 http URL: https://www.sec.gov/Archives/edgar/data/2098/0000002098-96-000003.txt

:copyright: © 2025 by Mac Gaulin
:license: MIT, see LICENSE for more details.
"""

# Stdlib imports
import os
import re
import tarfile
import logging

# 3rd party imports

# Module Imports
from pyedgar.exceptions import InputTypeError, WrongFormType, NoFormTypeFound, NoCIKFound
from pyedgar import config
from pyedgar import utilities
from pyedgar.utilities import localstore
from pyedgar.utilities import forms
from pyedgar.utilities import edgarweb


class EDGARCacher(object):
    """
    Class that downloads EDGAR to your very own computer.
    Everyone should have a local copy after all!
    I have just enough flexibility here for my computer. It works on Linux, YWindowsMMV.
    """

    # These should work for everypeople.
    EDGAR_ENCODING = "latin-1"  # The SEC documentation says it uses latin-1
    # EDGAR_ENCODING = 'utf-8' # Alternatively one could use utf-8.

    # These should be changed for you. Either in source, or more better at runtime.
    keep_regex = None
    check_cik = False

    # Class local vars
    _path_formatter = None
    _use_requests = False

    # Local versions of file path lookups, for overriding if you like
    _get_filing_path = None
    _get_feed_cache_path = None
    _get_index_cache_path = None

    # May as well share this across instances (instead of setting in __init__)
    _logger = logging.getLogger(__name__)

    def __init__(self, keep_form_type_regex=None, check_cik=False, use_tqdm=True, use_requests=False):
        """
        Initialize the downloader object.

        keep_form_type_regex: regular expression object which will match to form-types you wish to keep, default to config file if None. Pass '.' for all filings.
        check_cik: flag for whether to extract the CIK from the nc file for passing into the path formatter.
        use_tqdm: flag for whether or not to wrap downloads in tqdm for progress monitoring
        """
        self.check_cik = check_cik
        self._use_requests = use_requests

        self.keep_regex = keep_form_type_regex
        if keep_form_type_regex is None and config.KEEP_REGEX:
            self.keep_regex = re.compile(config.KEEP_REGEX)

        self._get_filing_path = localstore.get_filing_path
        self._get_feed_cache_path = config.get_feed_cache_path
        self._get_index_cache_path = config.get_index_cache_path

        self._logger.debug("Feed cache: %r | %r", config.FEED_CACHE_ROOT, config.FEED_CACHE_PATH_FORMAT)
        self._logger.debug("Filing root: %r | %r", config.FILING_ROOT, config.FILING_PATH_FORMAT)
        self._logger.debug("Index cache: %r | %r", config.INDEX_CACHE_ROOT, config.INDEX_CACHE_PATH_FORMAT)
        self._logger.debug("Index root: %r | form_*.%s", config.INDEX_ROOT, config.INDEX_EXTENSION)
        self._logger.debug("Extract regex: %r", self.keep_regex.pattern if self.keep_regex else "ALL")

    def _handle_nc(self, file_or_str):
        """
        Reads file or string, returns dictionary based on flags or None on failure.
        At a minimum, it returns: {'doc'}

        If keep_regex is set (not None), it adds 'form_type'.
            (Raises WrongFormType if FORM-TYPE SGML tag doesn't match `keep_regex`.)

        If check_cik is True, it extracts and adds 'cik'.
        """
        try:
            txt = file_or_str.read()
        except AttributeError:
            txt = file_or_str

        if not txt:
            raise InputTypeError("No text of file object found")

        for _decode_type, _errors in zip((self.EDGAR_ENCODING, "utf-8", "latin-1"), ("strict", "strict", "ignore")):
            try:
                txt = txt.decode(_decode_type, errors=_errors)
                break
            except (UnicodeDecodeError, ValueError):
                pass

        ret_val = {"doc": txt, "encoding": _decode_type, "decode_errors": _errors}

        if self.keep_regex is not None:
            ret_val["form_type"] = forms.get_header(txt, "FORM-TYPE")

            if not ret_val["form_type"]:
                raise NoFormTypeFound(ret_val["form_type"])

            if not self.keep_regex.search(ret_val["form_type"]):
                raise WrongFormType(ret_val["form_type"])

        if self.check_cik:
            ret_val["cik"] = forms.get_header(txt, "CIK")
            ret_val["accession"] = forms.get_header(txt, "ACCESSION-NUMBER")

            if not ret_val["cik"]:
                raise NoCIKFound("No CIK found in {}".format(txt[:250]))

        return ret_val

    def extract_from_feed_cache(self, cache_path, overwrite=False):
        """
        Extract all filings from a daily feed compressed cache file.
        Uses `self._get_filing_path` to determine location for extracted filings.

        Extracts filings based on regular expression match of form type if `self.keep_regex` is not None.
        """
        i_done, i_tot = 0, 0

        with tarfile.open(cache_path, "r") as tar:
            for tarinfo in tar:
                if len(tarinfo.name) < 3 or ".corr" in tarinfo.name:
                    continue
                i_tot += 1

                # tarinfo.name of form ./ACCESSION.nc
                nc_acc = tarinfo.name.split("/")[-1][:-3]
                if len(nc_acc) != 20:
                    self._logger.warning("\tAccession in filename seems suspect. %r", nc_acc)

                try:
                    nc_file = tar.extractfile(tarinfo)
                except IOError:
                    continue

                # At this point, we have a file, and we have an accession.
                # This should be all we need to save it off.
                try:
                    nc_dict = self._handle_nc(nc_file)
                except InputTypeError:
                    self._logger.warning("\tNot a file or string at %r (%r/%r extracted)", tarinfo.name, i_done, i_tot)
                    continue
                except NoCIKFound:
                    # This only triggers if self.check_cik is set.
                    self._logger.warning("\tNo CIK found at %r (%r/%r extracted)", tarinfo.name, i_done, i_tot)
                    continue
                except NoFormTypeFound:
                    # This only triggers if self.keep_regex is set.
                    self._logger.warning("\tNo FormType found at %r (%r/%r extracted)", tarinfo.name, i_done, i_tot)
                    continue
                except WrongFormType:
                    # This only triggers if self.keep_regex is set.
                    continue

                try:
                    nc_text = nc_dict.pop("doc")
                    if "accession" not in nc_dict:
                        nc_dict["accession"] = nc_acc
                except AttributeError:
                    # None type has no pop
                    self._logger.warning(
                        "\tHandling nc file %r passed exceptions (%r/%r extracted)", tarinfo.name, i_done, i_tot
                    )
                    continue
                except KeyError:
                    # This triggers upon nc_dict.pop not having 'doc' in it. Shouldn't happen.
                    self._logger.warning(
                        "\tNo document item extracted from %r (%r/%r extracted)", tarinfo.name, i_done, i_tot
                    )
                    continue

                # Get local nc file path. Accession is nc file filename.
                nc_out_path = self._get_filing_path(**nc_dict)
                i_done += 1
                if not overwrite and os.path.exists(nc_out_path):
                    continue

                # Sometimes the containing dir (cik or year) doesn't exist. Make it so.
                if not os.path.exists(os.path.dirname(nc_out_path)):
                    os.makedirs(os.path.dirname(nc_out_path))

                with open(nc_out_path, "w", encoding=nc_dict["encoding"], errors=nc_dict["decode_errors"]) as fh:
                    fh.write(nc_text)

        return i_done, i_tot

    def extract_daily_feeds(self, from_date, to_date=None, download_first=False, overwrite=False):
        """
        Loop through daily feed compressed files and extract them to local cache.
        Uses the object's path formatter to determine file paths.

        Args:
            from_date (datetime): Day to start extracting on.
            to_date (datetime): Optional day to finish extracting on. Default: datetime.date.today()
            download_first (bool): Flag for whether to try and download daily feed cache files from
                EDGAR if they don't exist, or just use the already downloaded files. Default: False.
            overwrite (bool): Flag for whether to overwrite filings if they have already been extracted. Default: False.
        """
        num_extracted, num_total, num_parsed, i_extracted, i_searched = 0, 0, 0, 0, 0

        for i_date in utilities.iterate_dates(from_date, to_date=to_date, period="daily"):
            if download_first:
                feed_path = edgarweb.download_feed(i_date, overwrite=overwrite, use_requests=self._use_requests)
            else:
                feed_path = self._get_feed_cache_path(i_date)

            if feed_path is None or not os.path.exists(feed_path):
                self._logger.info("Cache file does not exist for %s at %s.", i_date, feed_path)
                continue

            self._logger.info(
                "%s feed file %s: %4.2f MB",
                "Downloaded" if download_first else "Parsing",
                i_date,
                os.path.getsize(feed_path) / 1024 ** 2,
            )

            try:
                i_extracted, i_searched = self.extract_from_feed_cache(feed_path, overwrite=overwrite)
            except tarfile.ReadError:
                self._logger.error("Handling nc file on %s at %s raised Read Error", i_date, feed_path)

            # Log progress after each tar file is done
            self._logger.info("Extracted %d out of %d filings from %s", i_extracted, i_searched, feed_path)

            num_extracted += i_extracted
            num_total += i_searched
            num_parsed += 1

        return num_extracted, num_total, num_parsed
