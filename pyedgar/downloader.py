#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
High level downloading functionality, using lower-level download routines from `pyedgar.utilities`


:copyright: © 2020 by Mac Gaulin
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


def main(start_date=None, last_n_days=30, get_indices=False, get_feeds=False, use_curl_to_download=None):
    """
    Download feeds and indices. Feeds will be downloaded for `start_date` through yesterday,
    or for the past `last_n_days` days.

    Examples:
        This will download/extract last 30 days of forms and all indices:

            ```python -m pyedgar.downloader -i -d -e --last-n-days 30```

        This will just extract the already downloaded last 30 days of forms and ignore indices:

            ```python -m pyedgar.downloader -e --last-n-days 30```

    Args:
        start_date (date): Date to start extraction of feeds from. When empty, defaults to today() - last_n_days
        last_n_days (int): If start_date is missing, extract this number days before today. Default: 30
        get_indices (bool): Flag to download and extract index files. Default: False
        get_feeds (bool): Flag to download daily feed files since `start_date` or for `last_n_days`. Default: False
        use_curl_to_download (bool, None): Flag to use cURL subprocess instead of `requests` library. If None,
            will check for and use cURL if it exists. Default: None
    """
    if use_curl_to_download is None:
        use_curl_to_download = edgarweb.has_curl()

    if start_date is None:
        start_date = dt.date.fromordinal(dt.date.today().toordinal() - last_n_days)
    else:
        start_date = utilities.parse_date_input(start_date)

    if get_feeds:
        cacher = edgarcache.EDGARCacher(
            keep_form_type_regex=re.compile(config.KEEP_REGEX, re.I) if not config.KEEP_ALL else None,
            check_cik="cik" in config.FILING_PATH_FORMAT,
            use_requests=not use_curl_to_download,
        )
        _logger.info("Downloading since {:%Y-%m-%d}...".format(start_date))

        num_dates = len([1 for _ in utilities.iterate_dates(start_date)])
        for i_date in tqdm(utilities.iterate_dates(start_date), total=num_dates, desc="Downloading Feeds"):
            # download one date, so we can track progress with TQDM
            cacher.extract_daily_feeds(i_date, to_date=i_date, download_first=True, overwrite=False)

        _logger.info("Done downloading feeds on {:%Y-%m-%d}...".format(i_date))

    if get_indices:
        _logger.info("Downloading and extracting indices")
        # the last index file we find is probably not 'complete' because it was downloaded during the month maybe.
        # Let's make sure that isn't the case
        max_date, last_index = dt.date(1995, 1, 1), None
        for i_date in utilities.iterate_dates(1995, period="quarterly"):
            _idx = config.get_index_cache_path(i_date)
            if os.path.exists(_idx) and i_date > max_date:
                max_date, last_index = i_date, _idx
        if last_index is not None:
            _logger.info("Removing last of the old index caches: %s", last_index)
            os.remove(last_index)

        index_maker = indices.IndexMaker(use_tqdm=True, use_requests=not use_curl_to_download)
        index_maker.extract_indexes()
        _logger.info("Done downloading and extracting indices")


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


if __name__ == "__main__":
    from argparse import ArgumentParser

    argp = ArgumentParser(
        description="Downloader for pyedgar. Has functionality for downloading indexes and filings.\n"
        "Indexes: downloads quarterly index files from EDGAR, then combines them all into one big master index file.\n"
        "Filings: downloads compressed filing 'feed files' from EDGAR, then extracts the specified form types."
    )

    argp.add_argument(
        "-s",
        "--start-date",
        default=None,
        dest="start_date",
        metavar="YYYY-MM-DD",
        type=utilities.parse_date_input,
        help="An optional date to start downloading feeds/indices from (of form YYYY-MM-DD).",
    )

    argp.add_argument(
        "-n",
        "--last-n-days",
        default=30,
        dest="last_n_days",
        type=int,
        help="An number of days before today to start downloading feeds/indices from.",
    )

    argp.add_argument("-i", "--indices", action="store_true", dest="get_indices", help="Download and update indices.")

    argp.add_argument(
        "-d", "--download-feeds", action="store_true", dest="get_feeds", help="Download and extract daily feed feeds.",
    )

    argp.add_argument("--config", action="store_true", dest="print_config", help="Print config file settings.")

    argp.add_argument(
        "--log",
        "--log-level",
        dest="log_level",
        default="error",
        help="Set the log-level to display more/less output. Choose from: error (default), warning, info, debug.",
    )

    cl_args = argp.parse_args()

    _log_level = {"w": logging.WARNING, "i": logging.INFO, "d": logging.DEBUG,}.get(
        cl_args.log_level[0].lower(), logging.ERROR
    )

    logging.basicConfig(level=_log_level)

    _logger.debug("Running with args: %r", cl_args)

    if cl_args.print_config:
        print_config()

    main(
        start_date=cl_args.start_date,
        last_n_days=cl_args.last_n_days,
        get_indices=cl_args.get_indices,
        get_feeds=cl_args.get_feeds,
    )
