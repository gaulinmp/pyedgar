#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Download script to download and cache feeds and indices.

:copyright: © 2019 by Mac Gaulin
:license: MIT, see LICENSE for more details.
"""

# Stdlib imports
import os
# import tarfile
import logging
import datetime as dt

# 3rd party imports

# Module Imports
from pyedgar import config
from pyedgar.utilities import edgarcache
from pyedgar.utilities import edgarweb
from pyedgar.utilities import forms
from pyedgar.utilities import indices
from pyedgar.utilities import localstore

# Local logger
_logger = logging.getLogger(__name__)


# Example running script. This will download past 30 days of forms and all indices.
# run with ```python -m pyedgar.downloader --help```
def main(start_date=None, get_indices=True, get_feeds=True, extract_feeds=True):
    cacher = edgarcache.EDGARCacher()

    if start_date is None:
        start_date = dt.date.fromordinal(dt.date.today().toordinal()-30)

    if get_feeds:
        print("Downloading and extracting since {:%Y-%m-%d}...".format(start_date))
        if extract_feeds:
            cacher.extract_daily_feeds(start_date)
        else:
            for i_date, feed_path in cacher.download_many_feeds(start_date):
                if not feed_path:
                    # This day doesn't exist on EDGAR.
                    # Not sure why servers can't work on weekends.
                    continue

                if not os.path.exists(feed_path):
                    _logger.error("Failed to download %r file to %r.",
                                  i_date, feed_path)
                    continue
                print("Done downloading {}".format(feed_path))

        print(" Done!")

    if get_indices:
        print("Downloading and extracting indices")
        index_maker = indices.IndexMaker()
        index_maker.extract_indexes()
        print("Done")


if __name__ == '__main__':
    from argparse import ArgumentParser

    argp = ArgumentParser(description='Downloader for pyedgar, downloads past'
                                      ' 30 days (or since DATE) of forms and'
                                      ' all indices (unless -f or -i flags'
                                      ' respectively are set).')

    argp.add_argument('-d', '--start-date', default=None,
                      dest='start_date', metavar='YYYY-MM-DD',
                      type=lambda s: dt.datetime.strptime(s, "%Y-%m-%d"),
                      help='An optional date of form YYYY-MM-DD to start '
                           'downloading indices from')

    argp.add_argument('-i', '--no-indices', action='store_false', dest='get_indices',
                      help='Do not download and update indices.')
    argp.add_argument('-f', '--no-feeds', action='store_false', dest='get_feeds',
                      help='Do not download or extract daily feed feeds.')
    argp.add_argument('-e', '--no-extract', action='store_false', dest='extract_feeds',
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
         get_indices=cl_args.get_indices,
         get_feeds=cl_args.get_feeds,
         extract_feeds=cl_args.extract_feeds)
