#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Download and extract indices from EDGAR index files.

:copyright: © 2019 by Mac Gaulin
:license: MIT, see LICENSE for more details.
"""

# Stdlib imports
import os
import logging
import datetime as dt
from itertools import product

# 3rd party imports
import pandas as _pd

# TQDM is a simple progress bar. If it doesn't exist, pass through arguments.
try:
    def _faketqdm(x, *args, **kwargs):
        return x
    from tqdm import tqdm as _tqdm
except ModuleNotFoundError:
    _tqdm = _faketqdm


# Module Imports
from pyedgar import config
from pyedgar.utilities import edgarweb
from pyedgar.utilities import edgarcache
from pyedgar.utilities import forms
from pyedgar.utilities import localstore


class IndexMaker():
    """
    Class that downloads EDGAR to your very own computer.
    Everyone should have a local copy after all!
    I have just enough flexibility here for my computer. It works on Linux, YWindowsMMV.
    """
    # These should work for everypeople.
    EDGAR_ENCODING = 'latin-1' # The SEC documentation says it uses latin-1
    # EDGAR_ENCODING = 'utf-8' # Alternatively one could use utf-8.

    edgar_index_args = {
        'sep': '|',
        'encoding': 'latin-1',
        'skiprows': [0, 1, 2, 3, 4, 5, 6, 7, 8, 10]
    }

    # Local versions of file path lookups, for overriding if you like
    _tq = None
    _get_filing_path = None
    _get_feed_cache_path = None
    _get_index_cache_path = None

    # May as well share this across instances (instead of setting in __init__)
    _logger = logging.getLogger(__name__)

    def __init__(self, use_tqdm=True):
        """
        Initialize the index making object.

        use_tqdm: flag for whether or not to wrap downloads in tqdm for progress monitoring
        """
        # Use the following to default to 10s, 20s, 8s, 13s, and Def 14As.
        # if keep_form_type_regex is None:
        #    re.compile(r'10-[KQ]|10[KQ]SB|20-F|8-K|13[FDG]|(?:14A$)')

        self._downloader = edgarcache.EDGARCacher(use_tqdm=use_tqdm)

        self._get_filing_path = localstore.get_filing_path
        self._get_feed_cache_path = config.get_feed_cache_path
        self._get_index_cache_path = config.get_index_cache_path

        self._tq = _tqdm if use_tqdm else _faketqdm

    def extract_indexes(self):
        self._logger.warning("Downloading the quarterly indices...")
        df = _pd.DataFrame()
        idx_num = (dt.date.today().year - 1994)*4

        for year, qtr in self._tq(product(range(1995, dt.date.today().year + 1),
                                         range(1, 5)), total=idx_num):
            qtr_dt = dt.date(year, qtr*3, 1)

            self._logger.info("\n\tFor %rQ%r (%r) downloading...",
                              year, qtr, qtr_dt)

            idx_cache_file = self._downloader.download_quarterly_index(
                qtr_dt, compressed=True, resume=False)

            self._logger.info("For date %r downloaded %r",
                              qtr_dt, idx_cache_file)

            if idx_cache_file is None:
                # Then we didn't get an index file, try the next one (but we're probably done)
                continue

            try:
                dfi = _pd.read_csv(idx_cache_file, **self.edgar_index_args)
            except NotImplementedError:
                self._logger.warning("Reading %r failed at %r Q%r",
                                     idx_cache_file, year, qtr)
                # File reading didn't work, try overwriting with new download
                continue

            dfi['Accession'] = dfi.Filename.str.slice(start=-24, stop=-4)
            del dfi['Filename']

            df = _pd.concat([df, dfi], copy=False)

            self._logger.info("Added %r(%r) to df(%r)",
                              idx_cache_file, len(dfi), len(df))

        df['Date Filed'] = _pd.to_datetime(df['Date Filed'])

        self._logger.warning("Done downloading, extracting...")

        all_forms = df['Form Type'].unique()
        save_forms = {
            'all':    all_forms,
            '10-K':   [x for x in all_forms if x[:4] in ('10-K', '10KS')],
            '10-Q':   [x for x in all_forms if x[:4] in ('10-Q', '10QS')],
            'DEF14A': [x for x in all_forms if x.endswith('14A')],
            '13s':    [x for x in all_forms if 'SC 13' in x or '13F-' in x],
            '8-K': ('8-K', '8-K/A'),
        }

        for form, formlist in self._tq(save_forms.items(), total=len(save_forms)):
            outpath = os.path.join(config.INDEX_ROOT,
                                   'form_{}.{}'.format(form, config.INDEX_EXTENSION))

            self._logger.info("Saving %r: %r", outpath, formlist)

            (df[df['Form Type'].isin(formlist)]
               .sort_values(['CIK','Date Filed'])
               .to_csv(outpath, sep=config.INDEX_DELIMITER, index=False))
        self._logger.warning("Done!")
