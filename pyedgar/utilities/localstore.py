# -*- coding: utf-8 -*-
"""
Utilities for general EDGAR website tasks.

:copyright: © 2025 by Mac Gaulin
:license: MIT, see LICENSE for more details.
"""
import os
import re
import logging

from pyedgar import config
#  import FEED_ROOT, FEED_CACHE_ROOT, INDEX_ROOT, INDEX_CACHE_ROOT

__logger = logging.getLogger(__name__)

ACCESSION_RE = re.compile(r'(?P<accession>\d{10}-?\d\d-?\d{6})', re.I)

def get_filing_path(*args, **kwargs):
    """
    Return filepath to local copy of EDGAR filing.
    Filing document is .nc file with full submission, including main filing and exhibits/attachments.
    Does some sanity checking on top of config.get_filing_path

    :param args: Tries to guess cik/accession in the args passed in. cik/accession passed in by kwargs overrides these args.
    :param kwargs: dictionary to be passed to config.format_filing_path.

    :return: Full path to local filing document. Equal to ``join(FILING_ROOT, format_filing_path(**kwargs))``
    :rtype: string
    """
    cik = kwargs.get('cik', None)
    accession = kwargs.get('accession', None)

    if args:
        if accession is None:
            accession = [arg for arg in args if ACCESSION_RE.match(str(arg))]
            if accession:
                accession = accession[0]
            else:
                accession = None

        if cik is None:
            for arg in args:
                if len(str(arg)) <= 10:
                    try:
                        cik = int(arg)
                    except (ValueError, TypeError):
                        continue
                    break

    if cik is None and accession is None:
        raise ValueError("Requires non-missing CIK({}) or Accession({}). Got: args:{}, kwargs:{}"
                         .format(cik, accession, args, kwargs))

    try:
        clean_ac = ACCESSION_RE.search(accession).group('accession')
        if len(clean_ac) == 18: # no dashes found. Add dashes.
            clean_ac = clean_ac[:10] + '-' + clean_ac[10:12] + '-' + clean_ac[12:]
    except AttributeError: # no .group found.
        clean_ac = accession

    if cik is not None:
        kwargs['cik'] = cik
    if accession is not None:
        kwargs['accession'] = accession

    formatted_filename = config.format_filing_path(**kwargs)

    return os.path.join(config.FILING_ROOT, formatted_filename)

def walk_files(root_dir, filename_regex=None, return_dirs=False):
    """
    Iteratively walk directories and files, returning full paths.

    :param str root_dir: The root directory at which to start searching.
    :param re filename_regex: Regular expression (or string pattern) to which
              files or directories must match.
    :param bool return_dirs: Return directories as well as files.

    :return: Full path to filename or directory that matches optional regex.
    :rtype: string
    """
    if filename_regex is not None:
        try:
            # One can chain re.compile calls. This obviates checking type.
            filename_regex = re.compile(filename_regex)
        except (re.error, TypeError) as e:
            __logger.error("Regular expression provided is invalid!")
            raise(e)
    for r,ds,fs in os.walk(root_dir):
        if return_dirs:
            for d in ds:
                if filename_regex is not None and not filename_regex.search(d):
                    continue
                yield os.path.join(r,d)
        for f in fs:
            if filename_regex is not None and not filename_regex.search(f):
                continue
            yield os.path.join(r,f)
