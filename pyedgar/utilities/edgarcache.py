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

:copyright: © 2020 by Mac Gaulin
:license: MIT, see LICENSE for more details.
"""

# Stdlib imports
import os
import tarfile
import logging
import datetime as dt

# 3rd party imports

# Module Imports
from pyedgar.exceptions import (InputTypeError, WrongFormType,
                                NoFormTypeFound, NoCIKFound)
from pyedgar import config
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
    EDGAR_ENCODING = 'latin-1' # The SEC documentation says it uses latin-1
    # EDGAR_ENCODING = 'utf-8' # Alternatively one could use utf-8.

    # These should be changed for you. Either in source, or more better at runtime.
    keep_regex = None
    check_cik = False

    # Class local vars
    _path_formatter = None
    _downloader = None

    # Local versions of file path lookups, for overriding if you like
    _get_filing_path = None
    _get_feed_cache_path = None
    _get_index_cache_path = None

    # May as well share this across instances (instead of setting in __init__)
    _logger = logging.getLogger(__name__)

    def __init__(self,
                 keep_form_type_regex=None,
                 check_cik=False,
                 use_tqdm=True):
        """
        Initialize the downloader object.

        keep_form_type_regex: regular expression object which will match to form-types you wish to keep
        check_cik: flag for whether to extract the CIK from the nc file for passing into the path formatter.
        use_tqdm: flag for whether or not to wrap downloads in tqdm for progress monitoring
        """
        self.check_cik = check_cik

        self.keep_regex = keep_form_type_regex
        # Use the following to default to 10s, 20s, 8s, 13s, and Def 14As.
        # if keep_form_type_regex is None:
        #    re.compile(r'10-[KQ]|10[KQ]SB|20-F|8-K|13[FDG]|(?:14A$)')

        self._downloader = edgarweb.EDGARDownloader(use_tqdm=use_tqdm)

        self._get_filing_path = localstore.get_filing_path
        self._get_feed_cache_path = config.get_feed_cache_path
        self._get_index_cache_path = config.get_index_cache_path

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

        for _decode_type, _errors in zip((self.EDGAR_ENCODING, 'utf-8', 'latin-1'),
                                         ('strict', 'strict', 'ignore')):
            try:
                txt = txt.decode(_decode_type, errors=_errors)
            except (UnicodeDecodeError, ValueError):
                continue
            break

        ret_val = {'doc': txt, 'encoding':_decode_type, 'decode_errors':_errors}

        if self.keep_regex is not None:
            ret_val['form_type'] = forms.get_header(txt, "FORM-TYPE")

            if not ret_val['form_type']:
                raise NoFormTypeFound(ret_val['form_type'])

            if not self.keep_regex.search(ret_val['form_type']):
                raise WrongFormType(ret_val['form_type'])

        if self.check_cik:
            ret_val['cik'] = forms.get_header(txt, "CIK")
            ret_val['accession'] = forms.get_header(txt, 'ACCESSION-NUMBER')

            if not ret_val['cik']:
                raise NoCIKFound("No CIK found in {}".format(txt[:250]))

        return ret_val

    def extract_from_feed_cache(self, cache_path, overwrite=True):
        """
        Loop through daily feed compressed files and extract them to local cache.
        Uses the object's path formatter to determine file paths.
        """
        i_done, i_tot = 0, 0

        with tarfile.open(cache_path, 'r') as tar:
            for tarinfo in tar:
                if len(tarinfo.name) < 3 or '.corr' in tarinfo.name:
                    continue
                i_tot += 1

                # tarinfo.name of form ./ACCESSION.nc
                nc_acc = tarinfo.name.split('/')[-1][:-3]
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
                    self._logger.warning("\tNot a file or string at %r (%r/%r extracted)",
                                         tarinfo.name, i_done, i_tot)
                    continue
                except NoCIKFound:
                    # This only triggers if self.check_cik is set.
                    self._logger.warning("\tNo CIK found at %r (%r/%r extracted)",
                                         tarinfo.name, i_done, i_tot)
                    continue
                except NoFormTypeFound:
                    # This only triggers if self.keep_regex is set.
                    self._logger.warning("\tNo FormType found at %r (%r/%r extracted)",
                                         tarinfo.name, i_done, i_tot)
                    continue
                except WrongFormType:
                    # This only triggers if self.keep_regex is set.
                    continue

                try:
                    nc_text = nc_dict.pop('doc')
                    if 'accession' not in nc_dict:
                        nc_dict['accession'] = nc_acc
                except AttributeError:
                    # None type has no pop
                    self._logger.warning("\tHandling nc file %r passed exceptions (%r/%r extracted)",
                                         tarinfo.name, i_done, i_tot)
                    continue
                except KeyError:
                    # This triggers upon nc_dict.pop not having 'doc' in it. Shouldn't happen.
                    self._logger.warning("\tNo document item extracted from %r (%r/%r extracted)",
                                         tarinfo.name, i_done, i_tot)
                    continue

                # Get local nc file path. Accession is nc file filename.
                nc_out_path = self._get_filing_path(**nc_dict)
                i_done += 1
                if not overwrite and os.path.exists(nc_out_path):
                    continue

                # Sometimes the containing dir (cik or year) doesn't exist. Make it so.
                if not os.path.exists(os.path.dirname(nc_out_path)):
                    os.makedirs(os.path.dirname(nc_out_path))

                with open(nc_out_path, 'w', encoding=nc_dict['encoding'], errors=nc_dict['decode_errors']) as fh:
                    fh.write(nc_text)

        return i_done, i_tot


    def iterate_daily_feeds(self, from_date, to_date=None):
        """
        Generator that yields (dt.date, daily feed tar file path)
        """
        if to_date is None:
            to_date = dt.date.today()

        for i_date in range(from_date.toordinal(), to_date.toordinal()):
            # i_date is ordinal number, so cast it to date
            yield dt.date.fromordinal(i_date), self._get_feed_cache_path(i_date)

    def download_daily_feed(self, dl_date, overwrite=False, resume=True):
        """Download a daily feed tar given a datetime input."""
        sec_path = edgarweb.get_feed_path(dl_date)
        local_path = self._get_feed_cache_path(dl_date)

        if overwrite:
            try:
                os.remove(local_path)
            except Exception:
                pass

        return self._downloader.download_tar(sec_path, local_path, resume=resume)

    def download_quarterly_index(self, dl_date, compressed=True, overwrite=False, resume=True):
        """Download a quarterly index given a datetime input."""
        # For now, get the IDX file, not the zipped file. Because laziness and edu internet.
        sec_path = edgarweb.get_idx_path(dl_date, compressed=compressed)
        local_path = self._get_index_cache_path(dl_date)

        if overwrite:
            try:
                os.remove(local_path)
            except Exception:
                pass

        if compressed:
            return self._downloader.download_tar(sec_path, local_path, resume=resume)

        return self._downloader.download_plaintext(sec_path, local_path)

    def download_many_feeds(self, from_date, to_date=None):
        """
        Generator that yields (dt.date, downloaded daily feed tar file path)
        """
        for i_date, _ in self.iterate_daily_feeds(from_date, to_date=to_date):
            # Actually get the file. This downloads it, or passes the filepath to the cached file.
            yield i_date, self.download_daily_feed(i_date)


    def extract_daily_feeds(self, from_date, to_date=None, download_first=True):
        """
        Loop through daily feed compressed files and extract them to local cache.
        Uses the object's path formatter to determine file paths.

        Args:
            from_date (datetime): Day to start extracting on.
            to_date (datetime): Optional day to finish extracting on. Default: datetime.date.today()
            download_first (bool): Flag for whether to try and download daily feed cache files from
                EDGAR if they don't exist, or just use the already downloaded files. Default: False.
        """
        num_extracted, num_total, num_parsed = 0, 0, 0

        iter_func = self.download_many_feeds if download_first else self.iterate_daily_feeds

        for i_date, feed_path in iter_func(from_date, to_date=to_date):
            if not feed_path:
                # This day doesn't exist on EDGAR.
                # Not sure why servers can't work on weekends.
                continue

            if not os.path.exists(feed_path):
                self._logger.warning("Cache file does not exist for %s at %s.",
                                   i_date, feed_path)
                continue

            self._logger.info("Daily feed cache %s: %4.2f MB",
                              i_date, os.path.getsize(feed_path)/1024**2)

            try:
                i_extracted, i_searched = self.extract_from_feed_cache(feed_path)
            except tarfile.ReadError:
                self._logger.error("Handling nc file on %s at %s raised Read Error",
                                   i_date, feed_path)

            # Log progress after each tar file is done
            self._logger.info("Finished adding %d out of %d from %s\n",
                              i_extracted, i_searched, feed_path)

            num_extracted += i_extracted
            num_total += i_searched
            num_parsed += 1

        num_extracted, num_total, num_parsed
