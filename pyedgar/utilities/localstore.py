#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Utilities for general EDGAR website tasks.

COPYRIGHT: None. I don't get paid for this.
"""
import os
import re

# This is platform specific. Probably a better solution than hard coding...
FEED_ROOT = '/data/storage/edgar/feeds/'
FEED_CACHE_ROOT = '/data/backup/edgar/feeds/'
INDEX_ROOT = '/data/storage/edgar/indices/'
ACCESSION_RE = re.compile(r'(?P<accession>\d{10}-?\d\d-?\d{6})', re.I)

def get_filing_path(cik, accession):
    """Return filepath to local copy of EDGAR filing. Filing document is .txt
    file with full submission, including main filing and exhibits/attachments.

    :param cik: The root directory at which to start searching.
    :param string accession: 18 digit accession string (optionally with dashes).

    :return: Full path to local filing document.
    :rtype: string
    """
    try:
        cik_full = "{:010d}".format(int(cik))
    except ValueError:
        return None # CIK not in integer format.
    try:
        clean_ac = ACCESSION_RE.search(accession).group('accession')
        if len(clean_ac) == 18: # no dashes found. Add dashes.
            clean_ac = clean_ac[:10] + '-' + clean_ac[10:12] + '-' + clean_ac[12:]
    except AttributeError: # no .group found.
        clean_ac = accession

    path = os.path.join(FEED_ROOT, *[cik_full[i:i+2] for i in range(0,10,2)] )

    return os.path.join(path, clean_ac + '.txt')

def walk_files(root_dir, filename_regex=None, return_dirs=False):
    """Iteratively walk directories and files, returning full paths.

    :param str root_dir: The root directory at which to start searching.
    :param re filename_regex: Compiled regular expression on which `search` is
    called and passed the file or directory name.
    :param bool return_dirs: Return directories as well as files.

    :return: Full path to filename or directory that matches optional regex.
    :rtype: string
    """
    for r,ds,fs in os.walk(root_dir):
        if return_dirs:
            for d in ds:
                if not filename_regex or filename_regex.search(d):
                    yield os.path.join(r,d)
        for f in fs:
            if not filename_regex or filename_regex.search(f):
                yield os.path.join(r,f)
