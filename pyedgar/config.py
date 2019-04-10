#!/usr/bin/env python
# -*- coding: utf-8 -*-

# STDlib imports
import os
import logging
import configparser
from itertools import product, starmap

# 3rd party imports


__logger = logging.getLogger(__name__)

def get_preferred_config_location(check_existing=True):
    if check_existing:
        config_file = get_config_file()
        if config_file:
            return config_file

    package_path = os.path.abspath(os.path.dirname(__file__))

    _name = 'pyedgar.conf'

    _dirs = [
        os.path.expanduser("~/.config/pyedgar"),
        os.path.expanduser("~/AppData/Local/pyedgar"),
        os.path.expanduser("~/AppData/Roaming/pyedgar"),
        os.path.expanduser("~/Library/Preferences/pyedgar"),
        os.path.expanduser("~/.config/"),
        os.path.expanduser("~/"),
        package_path,
    ]

    for _d in _dirs:
        if os.path.exists(_d) or os.path.exists(os.path.dirname(_d)):
            break

    return os.path.join(_d, _name)


def get_config_file(extra_dirs=None):

    package_path = os.path.abspath(os.path.dirname(__file__))

    _names = ['pyedgar.conf', '.pyedgar', 'pyedgar.ini']

    _dirs = [
        os.environ.get("PYEDGAR_CONF", '.'),
        os.curdir,
        os.path.expanduser("~/.config/pyedgar"),
        os.path.expanduser("~/AppData/Local/pyedgar"),
        os.path.expanduser("~/AppData/Roaming/pyedgar"),
        os.path.expanduser("~/Library/Preferences/pyedgar"),
        os.path.expanduser("~/.config/"),
        os.path.expanduser("~/"),
        os.path.expanduser("~/Documents/"),
        package_path,
    ]

    if extra_dirs:
        if isinstance(extra_dirs, str):
            _dirs.append(extra_dirs)
        else:
            _dirs.extend(extra_dirs)

    config_txt = None
    for fpath in starmap(os.path.join, product(_dirs, _names)):
        try:
            with open(fpath, 'r') as fh:
                config_txt = fh.read()
                if config_txt:
                    break
        except IOError:
            pass

    if fpath and config_txt:
        return fpath

    return None


#  ██████╗ ██████╗ ███╗   ██╗███████╗████████╗ █████╗ ███╗   ██╗████████╗███████╗
# ██╔════╝██╔═══██╗████╗  ██║██╔════╝╚══██╔══╝██╔══██╗████╗  ██║╚══██╔══╝██╔════╝
# ██║     ██║   ██║██╔██╗ ██║███████╗   ██║   ███████║██╔██╗ ██║   ██║   ███████╗
# ██║     ██║   ██║██║╚██╗██║╚════██║   ██║   ██╔══██║██║╚██╗██║   ██║   ╚════██║
# ╚██████╗╚██████╔╝██║ ╚████║███████║   ██║   ██║  ██║██║ ╚████║   ██║   ███████║
#  ╚═════╝ ╚═════╝ ╚═╝  ╚═══╝╚══════╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝   ╚══════╝
_defaults = {
    'FILING_ROOT': '/data/bulk/data/edgar/filings/',
    'FEED_CACHE_ROOT': '/data/bulk/data/edgar/raw_from_edgar/compressed_daily_feeds/',
    'INDEX_ROOT': '/data/storage/edgar/indices/',
    'INDEX_CACHE_ROOT': '/data/storage/edgar/raw_from_edgar/indices/',
    'FILING_PATH_FORMAT': '{accession[11:13]}/{accession}.nc',
    'KEEP_ALL': True,
    'KEEP_REGEX': '',
    'INDEX_DELIMITER': '\t',
    'INDEX_EXTENSION': 'tab',
    'INDEX_FILE_COMPRESSION': '',
}

CONFIG_FILE = get_config_file()
__logger.info("Config file to be loaded: %r", CONFIG_FILE)

CONFIG_OBJECT = configparser.ConfigParser()
try:
    CONFIG_OBJECT.read(CONFIG_FILE)
    __logger.warning("Loaded config file from %r. \n\n"
                     "ALERT!!!! FILING_PATH_FORMAT is %r.\n",
                     CONFIG_FILE,
                     CONFIG_OBJECT.get('Paths', 'FILING_PATH_FORMAT', fallback=None))
except Exception:
    __logger.exception("Error reading config file: %r", CONFIG_FILE)


# Paths section
FILING_ROOT = CONFIG_OBJECT.get('Paths', 'FILING_ROOT')
FEED_CACHE_ROOT = CONFIG_OBJECT.get('Paths', 'FEED_CACHE_ROOT')
INDEX_ROOT = CONFIG_OBJECT.get('Paths', 'INDEX_ROOT')
INDEX_CACHE_ROOT = CONFIG_OBJECT.get('Paths', 'INDEX_CACHE_ROOT')
FILING_PATH_FORMAT = CONFIG_OBJECT.get('Paths', 'FILING_PATH_FORMAT')

# Downloader section
KEEP_ALL = CONFIG_OBJECT.getboolean('Downloader', 'KEEP_ALL')
KEEP_REGEX = CONFIG_OBJECT.get('Downloader', 'KEEP_REGEX')

# Index section
INDEX_DELIMITER = CONFIG_OBJECT.get('Index', 'INDEX_DELIMITER')
INDEX_EXTENSION = CONFIG_OBJECT.get('Index', 'INDEX_EXTENSION')
INDEX_FILE_COMPRESSION = CONFIG_OBJECT.get('Index', 'INDEX_FILE_COMPRESSION')

# Fix this. Srsly.

def format_filing_path(**kwargs):
    """
    "If at first you don't succeed, don't try skydiving."

    That makes about as much sense as a docstring as the workaround below.
    It's... horrifying what I've done here.
    So lemme splain the what and why.
    We want a conf file that is useful for paths and whatever format you want to keep your files in on your local copy of EDGAR.
    So to facilitate this, let's allow an f-string type FILING_PATH_FORMAT input.
    So how to evaluate it? We can't use FILING_PATH_FORMAT.format(**kwargs) because then you can't do cik[:5] for sub-folders.
    Well here comes eval to the rescue! I know, eval-ing user-provided strings is TERRIBLE practice.
    Really TERRIBLE.
    Whatever. It works. I limit it to 150 characters anyway, so your injection has to be shorter than that.

    LEGAL DISCLAIMER: Know where you config file is loading from. This is most definitely an injection vector.

    Anyway, back to the code. The trick here is that I don't know what format the input passed in will be.
    So I just take all the input (all kwargs) and load it into local.
    Turns out this only works because of the eval statement? See: https://stackoverflow.com/a/8028785/1959876

    Cool. So we put everything you pass in into the locals, to be accessed by the dynamically eval-ed f-string.

    Last bit is for some sanity. I force the existence of the following variables:
        cik: in int form
        cik_str: in string form, =f'{cik:010d}'
        accession: 20 character format with dashes
        accession18: 18 characters of only digits with dashes removed
    So you can safely define the format string using these for variables, and if you're feeling adventuresome, you can add your custom variable to the format string, then pass it into this method and it should work.
    Should. Probably won't. Just stick to CIK/Accession.

    Lastly... sorry for all this.
    """
    # Get that thing from above.
    global FILING_PATH_FORMAT

    locals().update(kwargs)

    try:
        cik = int(kwargs.get('cik', 0))
        cik_str = f'{cik:010d}'
    except (ValueError, TypeError):
        cik = 0
        cik_str = 10*'0'

    accession = kwargs.get('accession', '9090909090-90-909090')
    accession18 = accession.replace('-', '')

    return eval(f"""f'{FILING_PATH_FORMAT[:150]}'""")
