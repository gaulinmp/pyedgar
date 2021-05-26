#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
File for reading and setting configurations for the whole library.
I will not pretend this config file is a good way to do things.
But it is flexible, and works so far.
I make no guarantees that this will not destroy your computer.

Example config file:

``` ini
[Paths]
; Root directories, under which filings/cached tarballs will be found
; There is no % interpolation

; CACHE_FEED indicates whether the feed should be cached/searched locally
CACHE_FEED = True

; FILING_ROOT is the root of the extracted filings
FILING_ROOT=/data/bulk/data/edgar/filings/

; FEED_CACHE_ROOT is the root of the compressed daily feed files from EDGAR
FEED_CACHE_ROOT=/data/bulk/data/edgar/raw_from_edgar/compressed_daily_feeds/

; CACHE_INDEX indicates whether the index should be cached/searched locally
CACHE_INDEX = True

; INDEX_ROOT is the root of the extracted index tab-delimited files
INDEX_ROOT=/data/bulk/data/edgar/indices/

; INDEX_CACHE_ROOT is the root of the
INDEX_CACHE_ROOT=/data/bulk/data/edgar/raw_from_edgar/indices/

; FILING_PATH_FORMAT is the string to be .format-ed with the CIK and ACCESSION of the filing
; Don't put injection attacks here. That would be bad.
; Maximum length is 250 characters.
; Format string is formatted as an f-string (see docs), therefore slicing is possible.
; Available variables are:
;    cik (int)
;    cik_str (=f'{cik:010d}')
;    accession (20 character format with dashes)
;    and accession18 (18 characters of only digits with dashes removed)
; Examples:
; FILING_PATH_FORMAT={accession[11:13]}/{accession}.nc
;         Would result in --> FILING_ROOT/95/0001005463-95-000003.nc
;         This is useful for accession-only lookups (which is nice because multiple CIKs can file the same accession)
;
; FILING_PATH_FORMAT={cik_str[0:2]}/{cik_str[2:4]}/{cik_str[4:6]}/{cik_str[6:8]}/{cik_str[8:10]}/{accession}.txt
;         Would result in --> FILING_ROOT/00/01/00/54/63/0001005463-95-000003.txt
;         This uses CIK to break up filings, resulting in < 100 entries per directory. One problem is multiple CIKs
;           can file the same accession, meaning you have to either copy the same accession filing to multiple dirs
;
; FILING_PATH_FORMAT={accession[:4]}/{accession[4:7]}/{accession[7:10]}/{accession[11:13]}/{accession[14:17]}/{accession[17:]}/{accession}.nc
;         Would result in --> FILING_ROOT/1234/567/890/12/123/456/1234567890-12-123456.txt
;         This is useful for only accession lookups (no CIKs) but also < 1000 entries per directory
;
FILING_PATH_FORMAT={accession[11:13]}/{accession}.nc

; Filename format for caching FEED compressed files from EDGAR
; String is passed .format(date=datetime object) of the date of the feed
FEED_CACHE_PATH_FORMAT={date:%Y%m%d}.nc.tar.gz

; Filename format for caching INDEX compressed files from EDGAR
; Available data are: date (datetime object), year, and quarter (both ints)
INDEX_CACHE_PATH_FORMAT=full_index_{year}_Q{quarter}.gz

[Downloader]
; Downloader specific settings
KEEP_ALL=True
KEEP_REGEX=

; User Agent for downloading, to keep the SEC happy
USER_AGENT=pyedgar feed download by YOUREMAIL@example.com, from code at https://github.com/gaulinmp/pyedgar

[Index]
; Index file settings
INDEX_DELIMITER=\t
; Index file extension
; If you want to compress the index files, change INDEX_EXTENSION to tab.gz
INDEX_EXTENSION=tab.gz
```

:copyright: © 2020 by Mac Gaulin
:license: MIT, see LICENSE for more details.
"""


# STDlib imports
import os
import re
import logging
import tempfile
import configparser
import datetime as dt
from itertools import product, starmap

# 3rd party imports

_logger = logging.getLogger(__name__)


#  ██████╗ ██████╗ ███╗   ██╗███████╗██╗ ██████╗     ███████╗██╗██╗     ███████╗
# ██╔════╝██╔═══██╗████╗  ██║██╔════╝██║██╔════╝     ██╔════╝██║██║     ██╔════╝
# ██║     ██║   ██║██╔██╗ ██║█████╗  ██║██║  ███╗    █████╗  ██║██║     █████╗
# ██║     ██║   ██║██║╚██╗██║██╔══╝  ██║██║   ██║    ██╔══╝  ██║██║     ██╔══╝
# ╚██████╗╚██████╔╝██║ ╚████║██║     ██║╚██████╔╝    ██║     ██║███████╗███████╗
#  ╚═════╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝     ╚═╝ ╚═════╝     ╚═╝     ╚═╝╚══════╝╚══════╝

PREFERRED_CONFIG_DIRECTORIES = [
    os.path.abspath(os.curdir),
    os.path.expanduser("~/.config/pyedgar"),
    os.path.expanduser("~/AppData/Local/pyedgar"),
    os.path.expanduser("~/AppData/Roaming/pyedgar"),
    os.path.expanduser("~/Library/Preferences/pyedgar"),
    os.path.expanduser("~/.config"),
    os.path.expanduser("~"),
    os.path.expanduser("~/Documents"),
]


def get_config_file(extra_dirs=None):
    """Searches the expected config paths and names, returning the first found.

    First, try and load directory location from environmental variable `PYEDGAR_CONF`
    if it points to a specific file.

    Directories searched, in order:

    #. `os.environ['PYEDGAR_CONF']` (could be directory path as well)
    #. `.` (current dir)
    #. `~/.config/pyedgar/`
    #. `~/AppData/Local/pyedgar/`
    #. `~/AppData/Roaming/pyedgar/`
    #. `~/Library/Preferences/pyedgar/`
    #. `~/.config/`
    #. `~/`
    #. `~/Documents/`

    For each of those directories, the following file names are looked for:

    #. `pyedgar.conf`
    #. `.pyedgar`
    #. `pyedgar.ini`

    The first one of these combinations that is found is read and returned.
    """

    try:
        with open(os.environ["PYEDGAR_CONF"], "r") as fh:
            config_txt = fh.read()
            if config_txt:
                return os.environ["PYEDGAR_CONF"]
    except (KeyError, FileNotFoundError):
        pass

    _names = ["pyedgar.conf", ".pyedgar", "pyedgar.ini"]

    _dirs = [
        os.environ.get("PYEDGAR_CONF", "."),  # env variable might point to dir not file
        *PREFERRED_CONFIG_DIRECTORIES,
    ]

    if extra_dirs:
        if isinstance(extra_dirs, str):
            _dirs.append(extra_dirs)
        else:
            _dirs.extend(extra_dirs)

    config_txt = None
    for fpath in starmap(os.path.join, product(_dirs, _names)):
        try:
            with open(fpath, "r") as fh:
                config_txt = fh.read()
                if config_txt:
                    return fpath
        except (IOError, FileNotFoundError):
            pass

    # getting here means we didn't find the file
    return None


_tmp_dir = os.path.join(tempfile.gettempdir(), "pyedgar")

_defaults = {
    "FILING_ROOT": os.path.join(_tmp_dir, "filings"),
    "FEED_CACHE_ROOT": os.path.join(_tmp_dir, "compressed_daily_feeds"),
    "CACHE_FEED": "False",
    "INDEX_ROOT": os.path.join(_tmp_dir, "indices"),
    "INDEX_CACHE_ROOT": os.path.join(_tmp_dir, "indices"),
    "CACHE_INDEX": "False",
    "FILING_PATH_FORMAT": "{accession[11:13]}/{accession}.nc",
    "FEED_CACHE_PATH_FORMAT": "sec_daily_{date:%Y-%m-%d}.tar.gz",
    "INDEX_CACHE_PATH_FORMAT": "full_index_{year}_Q{quarter}.gz",
    "KEEP_ALL": "True",
    "KEEP_REGEX": "",
    "INDEX_DELIMITER": "\t",
    "INDEX_EXTENSION": "tab",
    "USER_AGENT": "pyedgar feed download by YOUREMAIL@example.com, from code at https://github.com/gaulinmp/pyedgar",
}

CONFIG_FILE = get_config_file()
_logger.info("Config file to be loaded: %r", CONFIG_FILE)

CONFIG_OBJECT = configparser.ConfigParser(interpolation=None, defaults=_defaults)
try:
    CONFIG_OBJECT.read(CONFIG_FILE)
    _logger.info(
        "Loaded config file from %r. \n\n" "ALERT!!!! FILING_PATH_FORMAT is %r.\n",
        CONFIG_FILE,
        CONFIG_OBJECT.get("Paths", "FILING_PATH_FORMAT", fallback=None),
    )
except TypeError:
    # Type error means that we tried to read from None file
    _logger.info("Error reading config file: %r", CONFIG_FILE)
    # Come on python... how does a nonexistent section not drop through to DEFAULT?!
    for sec in ("Paths", "Downloader", "Index"):
        CONFIG_OBJECT.add_section(sec)
except Exception:
    _logger.exception("Error reading config file: %r", CONFIG_FILE)
    raise


#  ██████╗ ██████╗ ███╗   ██╗███████╗████████╗ █████╗ ███╗   ██╗████████╗███████╗
# ██╔════╝██╔═══██╗████╗  ██║██╔════╝╚══██╔══╝██╔══██╗████╗  ██║╚══██╔══╝██╔════╝
# ██║     ██║   ██║██╔██╗ ██║███████╗   ██║   ███████║██╔██╗ ██║   ██║   ███████╗
# ██║     ██║   ██║██║╚██╗██║╚════██║   ██║   ██╔══██║██║╚██╗██║   ██║   ╚════██║
# ╚██████╗╚██████╔╝██║ ╚████║███████║   ██║   ██║  ██║██║ ╚████║   ██║   ███████║
#  ╚═════╝ ╚═════╝ ╚═╝  ╚═══╝╚══════╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝   ╚══════╝

# Paths to filings and indices
FILING_ROOT = CONFIG_OBJECT.get("Paths", "FILING_ROOT")
FEED_CACHE_ROOT = CONFIG_OBJECT.get("Paths", "FEED_CACHE_ROOT")
INDEX_ROOT = CONFIG_OBJECT.get("Paths", "INDEX_ROOT")
INDEX_CACHE_ROOT = CONFIG_OBJECT.get("Paths", "INDEX_CACHE_ROOT")
# expand user dir if present
if '~' in FILING_ROOT:
    FILING_ROOT = os.path.expanduser(FILING_ROOT)
if '~' in FEED_CACHE_ROOT:
    FEED_CACHE_ROOT = os.path.expanduser(FEED_CACHE_ROOT)
if '~' in INDEX_ROOT:
    INDEX_ROOT = os.path.expanduser(INDEX_ROOT)
if '~' in INDEX_CACHE_ROOT:
    INDEX_CACHE_ROOT = os.path.expanduser(INDEX_CACHE_ROOT)

# Path format
FILING_PATH_FORMAT = CONFIG_OBJECT.get("Paths", "FILING_PATH_FORMAT")
FEED_CACHE_PATH_FORMAT = CONFIG_OBJECT.get("Paths", "FEED_CACHE_PATH_FORMAT")
INDEX_CACHE_PATH_FORMAT = CONFIG_OBJECT.get("Paths", "INDEX_CACHE_PATH_FORMAT")

# Filings cache settings
CACHE_FEED = CONFIG_OBJECT.getboolean("Paths", "CACHE_FEED")
KEEP_ALL = CONFIG_OBJECT.getboolean("Downloader", "KEEP_ALL")
KEEP_REGEX = CONFIG_OBJECT.get("Downloader", "KEEP_REGEX")
USER_AGENT = CONFIG_OBJECT.get("Downloader", "USER_AGENT")

# Index cache settings
CACHE_INDEX = CONFIG_OBJECT.getboolean("Paths", "CACHE_INDEX")
INDEX_DELIMITER = CONFIG_OBJECT.get("Index", "INDEX_DELIMITER")
INDEX_EXTENSION = CONFIG_OBJECT.get("Index", "INDEX_EXTENSION").lstrip('.')

if INDEX_DELIMITER.lower() in ("\t", "\\t", "tab", "\\\t", "\\\\t"):
    INDEX_DELIMITER = "\t"


# ██████╗  █████╗ ████████╗██╗  ██╗███████╗
# ██╔══██╗██╔══██╗╚══██╔══╝██║  ██║██╔════╝
# ██████╔╝███████║   ██║   ███████║███████╗
# ██╔═══╝ ██╔══██║   ██║   ██╔══██║╚════██║
# ██║     ██║  ██║   ██║   ██║  ██║███████║
# ╚═╝     ╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝╚══════╝


def format_filing_path(**kwargs):
    """
    "If at first you don\'t succeed, don\'t try skydiving."

    That makes about as much sense as a docstring as the workaround below.
    It\'s... horrifying what I\'ve done here.
    So lemme splain the what and why.
    We want a conf file that is useful for paths and whatever format you want to keep your files in on your local copy of EDGAR.
    So to facilitate this, let\'s allow an f-string type FILING_PATH_FORMAT input.
    So how to evaluate it? We can\'t use ``FILING_PATH_FORMAT.format(**kwargs)`` because then you can\'t do cik[:5] for sub-folders.
    Well here comes eval to the rescue! I know, eval-ing user-provided strings is TERRIBLE practice.
    Really TERRIBLE.
    Whatever. It works. I limit it to 250 characters anyway, so your injection has to be shorter than that.
    I'm pretty sure rm -rf / is longer than 250 characters.

    LEGAL DISCLAIMER: Know where you config file is loading from. This is most definitely an attack vector.

    Anyway, back to the code. The trick here is that I don\'t know what format the input passed in will be.
    So I just take all the input (all kwargs) and load it into local.
    Turns out this only works because of the eval statement?
        (See: https://stackoverflow.com/a/8028785/1959876)

    Cool. So we put everything you pass in into the locals, to be accessed by the dynamically eval-ed f-string.

    Last bit is for some sanity. I force the existence of the following variables:
        cik: in int form
        cik_str: in string form, =``f'{cik:010d}'``
        accession: 20 character format with dashes
        accession18: 18 characters of only digits with dashes removed
    So you can safely define the format string using these for variables, and if you're feeling adventuresome, you can add your custom variable to the format string, then pass it into this method and it should work.
    Should. Probably won't. Just stick to CIK/Accession.

    Lastly... sorry for all this.
    """
    # Get that thing from above.
    global FILING_PATH_FORMAT

    # If only someone who knew how to program would write this instead of me.
    locals().update(kwargs)

    try:
        cik = int(kwargs.get("cik", 0))
        cik_str = f"{cik:010d}"
    except (ValueError, TypeError):
        cik = 0
        cik_str = 10 * "0"

    accession = kwargs.get("accession", "9090909090-90-909090")
    accession18 = accession.replace("-", "")

    return eval(f"""f'{FILING_PATH_FORMAT[:250]}'""")


def format_feed_cache_path(datetime_in):
    """
    Formats feed cache path on a given date (from date-time input).
    """
    # Get that thing from above.
    global FEED_CACHE_PATH_FORMAT

    if isinstance(datetime_in, int):
        datetime_in = dt.date.fromordinal(datetime_in)

    # Pass datetime as both the first arg and as date=,
    # in case the config file assumes positional data
    _logger.debug("FEED_CACHE_PATH_FORMAT:%r.format(date=%s)",
                  FEED_CACHE_PATH_FORMAT, datetime_in)

    return FEED_CACHE_PATH_FORMAT.format(datetime_in, date=datetime_in)


def format_index_cache_path(datetime_or_yearQN_str):
    """
    Formats index cache path on a given date.
    Allows a date-time input, or a year-quarter string in the form yyyyQq
    """
    # Get that thing from above.
    global INDEX_CACHE_PATH_FORMAT

    def get_yr_qtr_from_str(yq_string, *, yr_re=re.compile(r"([12]\d{3})Q?([1234])", re.I)):
        """Get year/qtr from string"""
        yq = yr_re.search(yq_string)
        return tuple(int(x) for x in yq.groups()) if yq else (1990, 0)

    try:
        year = datetime_or_yearQN_str.year
        qtr = (datetime_or_yearQN_str.month - 1) // 3 + 1
    except AttributeError:
        year, qtr = get_yr_qtr_from_str(datetime_or_yearQN_str)

        datetime_or_yearQN_str = dt.datetime(year, qtr * 3 - 2, 1)

    return INDEX_CACHE_PATH_FORMAT.format(date=datetime_or_yearQN_str, year=year, quarter=qtr)


def get_filing_path(**kwargs):
    """
    Return path for feed tar file.
    This implementation requires a datetime object.
    """
    global FILING_ROOT

    return os.path.join(FILING_ROOT, format_filing_path(**kwargs))


def get_feed_cache_path(datetime_in):
    """
    Return path for feed tar file.
    This implementation requires a datetime object.
    """
    global FEED_CACHE_ROOT

    return os.path.join(FEED_CACHE_ROOT, format_feed_cache_path(datetime_in))


def get_index_cache_path(datetime_or_yearQN_str):
    """
    Returns the full path for index tar file.
    Requires a datetime object or string of format 2000Q4.
    """
    global INDEX_CACHE_ROOT

    return os.path.join(INDEX_CACHE_ROOT, format_index_cache_path(datetime_or_yearQN_str))
