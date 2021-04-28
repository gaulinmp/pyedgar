#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Download script to download and cache feeds and indices.

:copyright: © 2020 by Mac Gaulin
:license: MIT, see LICENSE for more details.
"""

# Stdlib imports
import os
import re
# import tarfile
import logging
import datetime as dt
from time import sleep
from subprocess import Popen

# 3rd party imports

# Module Imports
from pyedgar import config
from pyedgar.utilities import edgarcache
# from pyedgar.utilities import edgarweb
# from pyedgar.utilities import forms
from pyedgar.utilities import indices
# from pyedgar.utilities import localstore

# Local logger
_logger = logging.getLogger(__name__)


def main(start_date=None, last_n_days=None, get_indices=True, download_feeds=True, extract_feeds=True):
    """
    Download feeds and indices.

    Examples:
        This will download/extract last 30 days of forms and all indices:

            ```python -m pyedgar.downloader -i -d -e --last-n-days 30```

        This will just extract the already downloaded last 30 days of forms and ignore indices:

            ```python -m pyedgar.downloader -e --last-n-days 30```

    Args:
        start_date (datetime): Date to start extraction of feeds from. When empty, defaults to today() - last_n_days
        last_n_days (int): If start_date is missing, extract this number days before today. Default: 30
        get_indices (bool): Flag to download and extract index files. Default: True
        download_feeds (bool): Flag to download daily feed files since `start_date` or for `last_n_days`. Default: True
        extract_feeds (bool): Flag to extract daily feed files since `start_date` or for `last_n_days`. Default: True
    """
    rgx = re.compile(config.KEEP_REGEX, re.I) if not config.KEEP_ALL else None
    _logger.info("From Config: keep regex: %r", rgx)
    cacher = edgarcache.EDGARCacher(keep_form_type_regex=rgx, check_cik='cik' in config.FILING_PATH_FORMAT)

    if start_date is None:
        start_date = dt.date.fromordinal(dt.date.today().toordinal() - (last_n_days or 30))

    if download_feeds:
        _logger.info("Downloading since {:%Y-%m-%d}...".format(start_date))
        for _ in cacher.download_many_feeds(start_date):
            pass

    if extract_feeds:
        _logger.info("Extracting since {:%Y-%m-%d}...".format(start_date))
        for _ in cacher.extract_daily_feeds(start_date, download_first=False):
            pass

    if get_indices:
        _logger.info("Downloading and extracting indices")
        index_maker = indices.IndexMaker()
        index_maker.extract_indexes()

    _logger.info("Done")



def download_feed(date, overwrite=True):
    """Download edgar daily feed compressed file.

    Args:
        date (datetime, str): Date of feed file to download. Can be datetime
            or string (YYYYMMDD format with optional spacing).
        overwrite (bool): Flag for whether to overwrite any existing file.
    """
    if isinstance(date, str):
        date, date_input = re.sub('[^0-9]', '', date), date
        if len(date) != 8:
            _logger.error("Date must be in YYYYMMDD format (spacing ignored). You passed: %r", date_input)
            return
        date = dt.datetime(date[:4], date[4:6], date[6:])

    feed_path = config.get_feed_cache_path(date)


    if os.path.exists(feed_path):
        if not overwrite:
            _logger.warning('Skipping existing cache file at: %r', feed_path)
            return

        _logger.warning('Removing existing file at %r', feed_path)
        os.remove(feed_path)

    year, month, day = date.year, date.month, date.day
    qtr = (month-1)//3+1
    url = f"https://www.sec.gov/Archives/edgar/Feed/{year}/QTR{qtr}/{year}{month:02d}{day:02d}.nc.tar.gz"

    _logger.info("curl %s -o %s", url, feed_path)
    return Popen(['curl', url, '-o', feed_path])


if __name__ == '__main__':
    from argparse import ArgumentParser

    argp = ArgumentParser(description='Downloader for pyedgar, downloads past'
                                      ' 30 days (or since DATE or last_n_days) of forms and'
                                      ' all indices (unless -f or -i flags'
                                      ' respectively are set).')

    argp.add_argument('-s', '--start-date', default=None,
                      dest='start_date', metavar='YYYY-MM-DD',
                      type=lambda s: dt.datetime.strptime(s, "%Y-%m-%d"),
                      help='An optional date of form YYYY-MM-DD to start '
                           'downloading indices from')

    argp.add_argument('-n', '--last-n-days', default=30, dest='last_n_days', type=int,
                      help='An optional integer for the last number of days '
                           'to start downloading indices from')

    argp.add_argument('-i', '--indices', action='store_true', dest='get_indices',
                      help='Download and update indices.')
    argp.add_argument('-d', '--download-feeds', action='store_true', dest='download_feeds',
                      help='Do not download or extract daily feed feeds.')
    argp.add_argument('-e', '--extract-feeds', action='store_true', dest='extract_feeds',
                      help='Do not extract daily feed feeds.')

    argp.add_argument('--log-level', dest='log_level', default='error',
                      help='Set the log-level to display more/less output. '
                           'Choose from: error (default), warning, info, debug.')

    cl_args = argp.parse_args()

    _log_level = {
        'w': logging.WARNING,
        'i': logging.INFO,
        'd': logging.DEBUG,
        }.get(cl_args.log_level[0].lower(), logging.ERROR)

    logging.basicConfig(level=_log_level)

    main(start_date=cl_args.start_date,
         last_n_days=cl_args.last_n_days,
         get_indices=cl_args.get_indices,
         download_feeds=cl_args.download_feeds,
         extract_feeds=cl_args.extract_feeds)


if __name__ == 'NOT __main__':
    from argparse import ArgumentParser

    argp = ArgumentParser(description='Redownload daily feed file.')

    argp.add_argument('-d', '--date', default=None,
                      dest='date', metavar='YYYY-MM-DD',
                      type=lambda s: dt.datetime.strptime(s, "%Y-%m-%d"),
                      help='The date to download in form YYYY-MM-DD')

    argp.add_argument('-r', '--recursive', default=False, action="store_true",
                      dest='recursive',
                      help='Recursively download from date till today.')

    argp.add_argument('-t', '--today', default=False, action="store_true",
                      dest='get_today',
                      help='Get the last 2 days of downloads (if missing)')

    cl_args = argp.parse_args()
    _logger.info(cl_args)
    _logger.warning("Downloading to %r", config.FEED_CACHE_ROOT)

    if cl_args.get_today:
        for i_date in range(dt.date.today().toordinal()-2, dt.date.today().toordinal()):
            i_date = dt.date.fromordinal(i_date)
            print(f"Downloading {i_date:%Y-%m-%d}")
            subp = download_feed(i_date, overwrite=False)
            if subp is not None:
                subp.wait()
            sleep(1)

    elif cl_args.date is None:
        argp.print_help()

    else:
        if cl_args.recursive:
            for i_date in range(cl_args.date.toordinal(), dt.date.today().toordinal()):
                i_date = dt.date.fromordinal(i_date)
                print(f"Downloading {i_date:%Y-%m-%d}")
                subp = download_feed(i_date)
                if subp is not None:
                    subp.wait()
                sleep(1)
        else:
            subp = download_feed(cl_args.date)
            if subp is not None:
                subp.wait()

    print()
