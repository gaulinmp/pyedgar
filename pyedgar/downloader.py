#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
High level downloading functionality, using lower-level download routines from `pyedgar.utilities`


:copyright: © 2025 by Mac Gaulin
:license: MIT, see LICENSE for more details.
"""

# Stdlib imports
import re
import os
import logging
import datetime as dt

# 3rd party imports
try:
    from tqdm import tqdm
except ImportError:
    # If tqdm isn't available, just pass through first argument
    def tqdm(_iterable, *args, **kwargs):
        return _iterable


# Module Imports
from pyedgar import config
from pyedgar import utilities
from pyedgar.utilities import edgarcache
from pyedgar.utilities import edgarweb
from pyedgar.utilities import indices

# from pyedgar.utilities import localstore

# Local logger
_logger = logging.getLogger(__name__)


def download_extract_feeds(
    start_date=None,
    end_date=None,
    last_n_days=30,
    download_feeds=True,
    extract=True,
    overwrite=False,
    use_curl_to_download=None,
):
    """
    Download feeds. Feeds will be downloaded for `start_date` through `end_date` (or yesterday),
    or for the past `last_n_days` days.

    Args:
        start_date (date): Date to start extraction of feeds from. When empty, defaults to today() - last_n_days
        end_date (date): Date to end extraction of feeds. When empty, defaults to today() - 1.
        last_n_days (int): If start_date is missing, extract this number days before today. Default: 30
        download_feeds (bool): Flag to download daily feed files from `start_date` to `end_date` or for `last_n_days`. Default: True
        extract (bool): Flag to extract filings. Default: True
        overwrite (bool): Flag to overwrite existing files. Default: False
        use_curl_to_download (bool, None): Flag to use cURL subprocess instead of `requests` library. If None,
            will check for and use cURL if it exists. Default: None
    """
    if not download_feeds and not extract:
        _logger.warning("No action to perform. Set download_feeds or extract to True.")
        return

    if use_curl_to_download is None:
        use_curl_to_download = edgarweb.has_curl()

    if start_date is None:
        start_date = dt.date.fromordinal(dt.date.today().toordinal() - last_n_days)
    else:
        start_date = utilities.parse_date_input(start_date)

    if end_date is None:
        end_date = dt.date.fromordinal(dt.date.today().toordinal() - 1)
    else:
        end_date = utilities.parse_date_input(end_date)

    _doingstr = {
        1: "Extracting",
        2: "Downloading",
        3: "Downloading and Extracting",
    }[2 * bool(download_feeds) + bool(extract)]

    cacher = edgarcache.EDGARCacher(
        keep_form_type_regex=re.compile(config.KEEP_REGEX, re.I) if not config.KEEP_ALL else None,
        check_cik="cik" in config.FILING_PATH_FORMAT,
        use_requests=not use_curl_to_download,
    )
    _logger.info(f"{_doingstr} {start_date:%Y-%m-%d} --  {end_date:%Y-%m-%d}.")

    if extract:
        cacher.extract_daily_feeds(start_date, to_date=end_date, download_first=download_feeds, overwrite=overwrite)
    else:
        # Then we're just downloading, no extract, so can't use the cacher's method
        for i_date in cacher.iterate_over_days(start_date, end_date, message="Downloading"):
            edgarweb.download_feed(i_date, overwrite=overwrite, use_requests=not use_curl_to_download)

    _logger.info(f"Done {_doingstr.lower()} feeds")


def download_indices(start_date=1995, end_date=None, overwrite=False, use_curl_to_download=None):
    """
    Download feeds and indices. Feeds will be downloaded for `start_date` through yesterday,
    or for the past `last_n_days` days.

    Args:
        start_date (date): Date to start extraction of feeds from. Default: 1995
        end_date (date): Date to end extraction of feeds. Default: today() - 1
        overwrite (bool): Flag to overwrite existing files. Default: False
        use_curl_to_download (bool, None): Flag to use cURL subprocess instead of `requests` library. If None,
            will check for and use cURL if it exists. Default: None
    """
    if use_curl_to_download is None:
        use_curl_to_download = edgarweb.has_curl()

    start_date = utilities.parse_date_input(start_date or 1995)

    if end_date is None:
        end_date = dt.date.fromordinal(dt.date.today().toordinal() - 1)
    else:
        end_date = utilities.parse_date_input(end_date)

    _logger.info(f"Downloading and extracting indices from {start_date:%Y-%m-%d} -- {end_date:%Y-%m-%d}.")
    # the last index file we find is probably not 'complete' because it was downloaded during the month maybe.
    # Let's make sure that isn't the case
    last_index = None
    for i_date in utilities.iterate_dates(start_date, end_date, period="quarterly"):
        _idx = config.get_index_cache_path(i_date)
        if os.path.exists(_idx):
            last_index = _idx
    if last_index is not None:
        _logger.info("Removing last of the old index caches: %s", last_index)
        os.remove(last_index)

    index_maker = indices.IndexMaker(use_tqdm=True, use_requests=not use_curl_to_download)
    index_maker.extract_indexes(start_date=start_date, end_date=end_date, download_first=True, overwrite=overwrite)
    _logger.info("Done downloading and extracting indices")

def print_cache_status():
    """Prints out the last found cache files for feeds and indices."""
    for i_date in reversed(list(utilities.iterate_dates(1995))):
        _feedfile = config.get_feed_cache_path(i_date)
        if os.path.exists(_feedfile):
            break
    else:
        _feedfile = None

    for i_date in reversed(list(utilities.iterate_dates(1995, period='quarterly'))):
        _idxfile = config.get_index_cache_path(i_date)
        if os.path.exists(_idxfile):
            break
    else:
        _idxfile = None

    print("Last downloaded feed cache: ", _feedfile)
    print("Last downloaded index cache:", _idxfile)

def print_config():
    """Prints out config file"""
    clean_user = lambda s: s.replace(os.path.expanduser("~"), "~") if isinstance(s, str) else s
    _cfloc = config.get_config_file()

    print("pyEDGAR Config File:")
    if _cfloc is None:
        print("No config file found in:")
        for x in config.PREFERRED_CONFIG_DIRECTORIES:
            if x == os.path.abspath("."):
                print("\t[current directory]:", end="")
            print("\t{}/".format(clean_user(x).replace("\\", "/")))
    else:
        print("Location: {}".format(clean_user(_cfloc)))

    print("-" * 80)
    _config = {c: getattr(config, c) for c in dir(config) if c.isupper()}
    for c in "PREFERRED_CONFIG_DIRECTORIES CONFIG_OBJECT".split():
        if c in _config:
            del _config[c]

    _maxlen = max(len(k) for k in _config.keys())
    for k, v in _config.items():
        print("{1:>{0}s}: {2}".format(_maxlen, k, clean_user(v)))
    print("-" * 80)
