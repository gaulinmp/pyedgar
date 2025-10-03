#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Main point of entry, mostly a wrapper around downloader.

Examples:

This will show the config file settings:

    ```python -m pyedgar --status --config```

This will download and extract the indices (you can use -s and -e to specify years/dates to download):

    ```python -m pyedgar -i```

This will download and extract the last 30 days of forms:

    ```python -m pyedgar -d -x --last-n-days 30```

This will only download the daily feed files in 1998:

    ```python -m pyedgar -d -s 1998 -e 1999```

This will only extract all daily feed files:

    ```python -m pyedgar -x -s 1994```


:copyright: © 2025 by Mac Gaulin
:license: MIT, see LICENSE for more details.
"""

# Stdlib imports
import logging
from argparse import ArgumentParser

# Module Imports
from pyedgar import config
from pyedgar import downloader
from pyedgar import utilities

# Local logger
_logger = logging.getLogger(__name__)


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
    "-e",
    "--end-date",
    default=None,
    dest="end_date",
    metavar="YYYY-MM-DD",
    type=utilities.parse_date_input,
    help="An optional date to end downloading feeds/indices on (of form YYYY-MM-DD).",
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
    "-d",
    "--download-feeds",
    action="store_true",
    dest="get_feeds",
    help="Download daily feeds.",
)

argp.add_argument(
    "-x",
    "--extract-feeds",
    action="store_true",
    dest="extract_feeds",
    help="Extract filings from daily feeds.",
)

argp.add_argument(
    "-o",
    "--overwrite",
    action="store_true",
    dest="overwrite",
    help="Overwrite existing filings when extracting from feeds. Defaults to config file setting.",
)

argp.add_argument("--config", action="store_true", dest="print_config", help="Print config file settings.")

argp.add_argument(
    "--status", action="store_true", dest="print_status", help="Show last downloaded feed and index cache files."
)

argp.add_argument(
    "--log",
    "--log-level",
    dest="log_level",
    default="error",
    help="Set the log-level to display more/less output. Choose from: error (default), warning, info, debug.",
)

# Parse the command line arguments, run the main functions
cl_args = argp.parse_args()

_log_level = {
    "w": logging.WARNING,
    "i": logging.INFO,
    "d": logging.DEBUG,
}.get(cl_args.log_level[0].lower(), logging.ERROR)

logging.basicConfig(level=_log_level)

_logger.debug("Running with args: %r", cl_args)

if cl_args.print_status:
    downloader.print_cache_status()

if cl_args.print_config:
    downloader.print_config()

if cl_args.get_indices:
    downloader.download_indices(
        start_date=cl_args.start_date,
        end_date=cl_args.end_date,
    )

if cl_args.get_feeds or cl_args.extract_feeds:
    # Use CLI flag if provided, otherwise fall back to config setting
    overwrite = cl_args.overwrite if cl_args.overwrite else config.OVERWRITE_ON_EXTRACT
    downloader.download_extract_feeds(
        start_date=cl_args.start_date,
        end_date=cl_args.end_date,
        last_n_days=cl_args.last_n_days,
        download_feeds=cl_args.get_feeds,
        extract=cl_args.extract_feeds,
        overwrite=overwrite,
    )
