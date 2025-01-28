#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Download and extract indices from EDGAR index files.

:copyright: © 2025 by Mac Gaulin
:license: MIT, see LICENSE for more details.
"""

# Stdlib imports
import os
import logging

# 3rd party imports
import pandas as pd

# Module Imports
from pyedgar import config
from pyedgar import utilities
from pyedgar.utilities import edgarweb


# progress logging
try:
    def no_tqdm(iterable, *args, **kwargs):
        return iterable
    from tqdm import tqdm
except ImportError:
    tqdm = no_tqdm


class IndexMaker:
    """
    Class that downloads EDGAR to your very own computer.
    Everyone should have a local copy after all!
    I have just enough flexibility here for my computer. It works on Linux, YWindowsMMV.
    """

    edgar_index_args = {"sep": "|", "encoding": "latin-1", "skiprows": [0, 1, 2, 3, 4, 5, 6, 7, 8, 10]}

    _use_requests = False
    _tq = None
    _get_index_cache_path = None

    # May as well share this across instances (instead of setting in __init__)
    _logger = logging.getLogger(__name__)

    def __init__(self, use_tqdm=False, use_requests=False):
        """
        Initialize the index making object.

        Arguments:
            use_tqdm (bool): flag for whether or not to wrap downloads in tqdm for progress monitoring
        """
        self._use_requests = use_requests
        self._get_index_cache_path = config.get_index_cache_path

        self._tqdm = tqdm if use_tqdm else no_tqdm

    def download_indexes(self, start_date=1995, end_date=None, overwrite=False):
        """Download multiple edgar quarterly index compressed files.

        Args:
            start_date (int, datetime, None): Starting datetime (from which we'll extract year/quarter) or year. Default to 1995.
            end_date (int, datetime, None): Ending datetime (from which we'll extract year/quarter) or year. Default to today's year.
            overwrite (bool): Flag for whether to overwrite any existing file (default False).

        Returns:
            tuple: output file path, return code
        """
        _num = len([0 for _ in utilities.iterate_dates(start_date, end_date, period="quarterly")])

        # The download recursively works as it sounds, but we want progress bar, so do it date by date
        for i_date in self._tqdm(
            utilities.iterate_dates(start_date, end_date, period="quarterly"), total=_num, desc="Downloading Indices"
        ):
            edgarweb.download_indexes_recursively(
                i_date, end_date=i_date, overwrite=overwrite, use_requests=self._use_requests
            )

    def extract_indexes(self, start_date=1995, end_date=None, save_forms=None, download_first=True, overwrite=False):
        if download_first:
            self._logger.info("Downloading the quarterly indices...")
            self.download_indexes(start_date=start_date, end_date=end_date, overwrite=overwrite)
            self._logger.info("Done downloading quarterly indices.")

        df = []

        _num = len([0 for _ in utilities.iterate_dates(start_date, end_date, period="quarterly")])

        for i_date in self._tqdm(
            utilities.iterate_dates(start_date, to_date=end_date, period="quarterly"),
            total=_num,
            desc="Extracting Indices",
        ):
            idx_cache_file = self._get_index_cache_path(i_date)

            try:
                self._logger.info("\tLoading index for %rQ%r", i_date.year, utilities.get_quarter(i_date))
                dfi = pd.read_csv(idx_cache_file, **self.edgar_index_args)
            except FileNotFoundError:
                self._logger.warning(
                    "No Index cache file at %r (for %rQ%r)", idx_cache_file, i_date.year, utilities.get_quarter(i_date)
                )
                continue
            except Exception:
                self._logger.warning(
                    "Reading %r failed at %rQ%r", idx_cache_file, i_date.year, utilities.get_quarter(i_date)
                )
                # File reading didn't work, try overwriting with new download
                continue

            dfi["Accession"] = dfi.Filename.str.slice(start=-24, stop=-4)
            del dfi["Filename"]

            df.append(dfi)

            self._logger.info("Added %r(%r) to list(%r)", idx_cache_file, len(dfi), len(df))

        # Solve Issue #8
        if not df:
            self._logger.warning("No indices found!")
            return None

        df = pd.concat(df)
        df["Date Filed"] = pd.to_datetime(df["Date Filed"])

        all_forms = df["Form Type"].unique()
        if save_forms is None:
            save_forms = {
                "all": all_forms,
                "10-K": [x for x in all_forms if x[:4] in ("10-K", "10KS")],
                "10-Q": [x for x in all_forms if x[:4] in ("10-Q", "10QS")],
                "DEF14A": [x for x in all_forms if x.endswith("14A")],
                "8-K": ("8-K", "8-K/A"),
            }

        for form, formlist in self._tqdm(save_forms.items(), total=len(save_forms), desc="Exporting Indices"):
            outpath = os.path.join(config.INDEX_ROOT, "form_{}.{}".format(form, config.INDEX_EXTENSION))

            self._logger.info("Saving %r to %r", form, outpath)
            self._logger.debug("Saving %s to %s with form-types: %r", form, outpath, formlist)

            (
                df[df["Form Type"].isin(formlist)]
                .sort_values(["CIK", "Date Filed"])
                .to_csv(outpath, sep=config.INDEX_DELIMITER, index=False)
            )
        self._logger.info("Done extracting indices!")
