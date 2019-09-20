#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Use indices from EDGAR index files.

:copyright: © 2019 by Mac Gaulin
:license: MIT, see LICENSE for more details.
"""

# Stdlib imports
import os
import re
import logging
# import datetime as dt

# 3rd party imports
import pandas as pd
try:
    def faketqdm(x, *args, **kwargs):
        return x
    from tqdm import tqdm
except ModuleNotFoundError:
    tqdm = faketqdm


# Module Imports
from pyedgar import config
# from pyedgar.utilities import edgarweb
# from pyedgar.utilities import edgarcache
# from pyedgar.utilities import forms
# from pyedgar.utilities import localstore


class EDGARIndex():
    """
    Class that opens EDGAR indices.
    Indices are always a pandas dataframe.
    """

    # Class variables
    simplify_col_names = None

    # Private class variables
    _tq = None
    _logger = logging.getLogger(__name__)
    _simple_col_names = ('cik', 'name', 'form', 'filedate', 'accession')
    _raw_col_names = ('CIK', 'Company Name', 'Form Type', 'Date Filed', 'Accession')

    def __init__(self, simplify_col_names=True, use_tqdm=True):
        """
        Initialize the index making object.

        use_tqdm: flag for whether or not to wrap downloads in tqdm for progress monitoring
        """
        self._tq = tqdm if use_tqdm else faketqdm
        self.simplify_col_names = simplify_col_names


    @property
    def indices(self):
        """
        Search for all indices, return dict of all found.
        """
        return self.search_for_indices()

    def search_for_indices(self, fname_regex=None):
        """
        Search `config.INDEX_ROOT` for all index files, identified by
        `config.INDEX_EXTENSION`.

        Args:
            fname_regex (re): Regex to use to match against file names to find
                index files.

        Returns:
            dict: Dictionary of all found index files, as `{filename:fullpath,}`
        """
        idx_root = config.INDEX_ROOT
        indices = dict()

        if fname_regex is None:
            fname_regex = re.compile('\.{}$'.format(config.INDEX_EXTENSION), re.I)

        for _file in os.listdir(idx_root):
            matches = fname_regex.search(_file)
            self._logger.info("Found %r which %r an index file.",
                              _file, 'matches' if matches else 'does not match')
            if matches:
                indices[_file] = os.path.join(idx_root, _file)

        return indices

    def get_index(self, index_name_or_path, shorten_col_names=True):
        # Assume they passed in the filing name, which is a key in self.indices
        try:
            return self.load_index(self.indices[index_name_or_path])
        except KeyError:
            pass

        # Next try to see if they omitted the extension
        try:
            try_lookup = '{}.{}'.format(index_name_or_path, config.INDEX_EXTENSION)
            return self.load_index(self.indices[try_lookup])
        except KeyError:
            pass

        # Last try to see if they omitted 'form' and the extension
        try:
            try_lookup = 'form_{}.{}'.format(index_name_or_path, config.INDEX_EXTENSION)
            return self.load_index(self.indices[try_lookup])
        except KeyError:
            pass

        # Then maybe they asked for a path
        return self.load_index(index_name_or_path)

    def load_index(self, index_path, override_sep=None):
        sep = config.INDEX_DELIMITER if override_sep is None else override_sep

        df = pd.read_csv(index_path, sep=sep)

        if self.simplify_col_names:
            df.rename(columns={k: v for k, v in
                               zip(self._raw_col_names, self._simple_col_names)},
                      index=str, inplace=True)
        if 'filedate' in df:
            df['filedate'] = pd.to_datetime(df['filedate'])

        return df

    def __getitem__(self, key):
        """
        Allow for dict-type lookup of indexes::

            idx = EDGARIndex()
            idx['10-K']
        """
        try:
            return self.get_index(key)
        except FileNotFoundError:
            raise KeyError("No index found at key {}. Indices found: {}",
                           key, list(self.indices.keys()))
