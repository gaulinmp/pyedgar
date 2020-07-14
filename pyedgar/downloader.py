#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Download script to download and cache feeds and indices.

:copyright: © 2020 by Mac Gaulin
:license: MIT, see LICENSE for more details.
"""

# Stdlib imports
# import os
import re
# import tarfile
import logging
import datetime as dt

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
        }.get(str(cl_args.log_level)[0].lower(),
              logging.ERROR)

    logging.basicConfig(level=_log_level)

    main(start_date=cl_args.start_date,
         last_n_days=cl_args.last_n_days,
         get_indices=cl_args.get_indices,
         download_feeds=cl_args.download_feeds,
         extract_feeds=cl_args.extract_feeds)
