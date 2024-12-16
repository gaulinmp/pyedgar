# -*- coding: utf-8 -*-
"""
Utilities for general EDGAR website and ftp tasks, including download functionality.

index URL: http://www.sec.gov/Archives/edgar/data/2098/0001026608-05-000015-index.htm
complete submission URL: http://www.sec.gov/Archives/edgar/data/2098/000102660805000015/0001026608-05-000015.txt
Exhibit/form URL: http://www.sec.gov/Archives/edgar/data/2098/000102660815000007/acu_10k123114.htm

EDGAR FTP change in 2016:
<2016 ftp URL: ftp://ftp.sec.gov/edgar/data/2098/0000002098-96-000003.txt
>2016 http URL: https://www.sec.gov/Archives/edgar/data/2098/0000002098-96-000003.txt

EDGAR HTML specification: https://www.sec.gov/info/edgar/ednews/edhtml.htm

:copyright: © 2025 by Mac Gaulin
:license: MIT, see LICENSE for more details.
"""

# Stdlib imports
import os
import re
import logging
import subprocess
import datetime as dt
from time import sleep

# 3rd party imports
import requests

# Module Imports
from pyedgar import config
from pyedgar import utilities

# Local logger
_logger = logging.getLogger(__name__)

# Constants
# Used to be (before FTP changed to AWS S3): ftp://ftp.sec.gov
EDGAR_ROOT = "https://www.sec.gov/Archives"
REQUEST_HEADERS = {
    "User-Agent": getattr(
        config, "USER_AGENT", "pyedgar downloader (fallback UA, shame) from gaulinmp+badpyedgarUA@gmail.com"
    )
}


def parse_url(url, url_re=re.compile(r"/(?P<cik>\d{1,10})/" r"(?P<accession>\d{10}-?\d\d-?\d{6})", re.I)):
    """Return CIK and Accession from an EDGAR HTTP or FTP url.

    Arguments:
        url (string): URL from EDGAR website or FTP server.
        url_re (Pattern): regular expression with cik and accession groups

    Returns:
        tuple: Tuple of strings in the form (cik, accession) or (None, None)
    """
    res = url_re.search(url)
    if res:
        acc = res.group("accession")
        if len(acc) == 18:
            acc = acc[:10] + "-" + acc[10:12] + "-" + acc[12:]
        return res.group("cik"), acc
    return None, None


def get_edgar_urls(cik, accession=None):
    """Generage URLs for EDGAR 'bulk download' and 'user facing' sites.
    `cik` parameter can be object with `cik` and `accession` attributes or keys.

    Arguments:
        cik (str,dict,object): String CIK, or object with cik and accession attributes or keys.
        accession (str): String ACCESSION number, or None if accession in CIK object.

    Returns:
        tuple: Tuple of strings in the form (raw url, Filing Index url)
    """
    _obj = utilities.get_cik_acc(cik, accession=accession)
    cik, accession = _obj.get("cik", None), _obj.get("accession", None)

    if cik is None or accession is None:
        return ("", "")

    return (
        "{}/edgar/data/{}/{}.txt".format(EDGAR_ROOT, cik, accession),
        "{}/edgar/data/{}/{}-index.htm".format(EDGAR_ROOT, cik, accession),
    )


def edgar_links(cik, accession=None, index=True, raw=True):
    """Generage HTML encoded links (using `a` tag) to EDGAR 'bulk download' and 'user facing' sites.
    `cik` parameter can be object with `cik` and `accession` attributes or keys.

    Arguments:
        cik (str,dict,object): String CIK, or object with cik and accession attributes or keys.
        accession (str): String ACCESSION number, or None if accession in CIK object.
        index (bool): Include link to Index of accession
        raw (bool): Include link to raw text of accession

    Returns:
        str: HTML `a` tag with href pointing to EDGAR index and/or raw file of of `accession`.
    """
    _raw, _idx = get_edgar_urls(cik, accession=accession)

    _html = []
    if index:
        _html.append("<a href='{}' target=_blank>Index</a>".format(_idx))
    if raw:
        _html.append("<a href='{}' target=_blank>Raw</a>".format(_raw))

    return " ".join(_html)


def get_feed_url(date):
    """Get URL path to daily feed gzip file.

    Arguments:
        date (datetime): Date for feed file

    Returns:
        str: URL to feed file on `date`"""
    return "{0}/edgar/Feed/{1:%Y}/QTR{2}/{1:%Y%m%d}.nc.tar.gz".format(EDGAR_ROOT, date, utilities.get_quarter(date))


def get_index_url(date_or_year, quarter=None, compressed=True):
    """
    Get URL path to quarterly index file.
    Do not feed it a year and no quarter.

    Arguments:
        date_or_year (datetime,int): Datetime from which the index's quarter will be calculated, or integer year
        quarter (int,None): Quarter of the index, will be inferred from date_or_year if None.
    """
    try:
        year = date_or_year.year
        # Leave this here, because if date_or_year isn't a datetime, we can't calculate the quarter. So error out.
        if quarter is None:
            quarter = utilities.get_quarter(date_or_year)
    except AttributeError:
        # Then date_or_year is an integer, cast just in case
        year = int(date_or_year)
        if quarter is None:
            raise AttributeError("Must either pass either datetime or both integer year AND quarter")

    ext = "gz" if compressed else "idx"

    return "{0}/edgar/full-index/{1}/QTR{2}/master.{3}".format(EDGAR_ROOT, year, quarter, ext)


def download_form_from_web(cik, accession=None):
    """
    Sometimes the cache file is not there, or you do not have local cache.
    In those cases, you can download the EDGAR forms from S3 directly.

    Arguments:
        cik (str,dict,object): String CIK, or object with cik and accession attributes or keys.
        accession (str): String ACCESSION number, or None if accession in CIK object.

    Returns:
        tuple: Tuple of strings in the form (bulk DL url, user website url)
    """
    _raw, _ = get_edgar_urls(cik, accession=accession)

    r = requests.get(_raw, headers=REQUEST_HEADERS)

    data = r.content

    for _decode_type, _errors in zip(("latin-1", "utf-8", "latin-1"), ("strict", "strict", "ignore")):
        try:
            return data.decode(_decode_type, errors=_errors)
        except (UnicodeDecodeError, ValueError):
            continue


def use_subprocess(process_list):
    """Call subprocess.run, but allow for backwards compatability with python <3.7 that doesn't have `capture_output`.

    Args:
        process_list (list): Argument list passed to `subprocess.run`.

    Returns:
        subprocess.CompletedProcess: Process object.
    """
    try:
        return subprocess.run(process_list, capture_output=True)
    except TypeError:
        return subprocess.run(process_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except AttributeError:
        return subprocess.call(process_list)


def has_curl():
    try:
        use_subprocess(["curl", '-A "pyedgar test"', "https://www.google.com"])
    except FileNotFoundError:
        # apparently if curl isn't found it's FileNotFoundError.
        return False
    except Exception:
        return False
    return True


def download_from_edgar(
    edgar_url,
    local_path,
    overwrite=False,
    use_requests=False,
    chunk_size=10 * 1024 ** 2,
    overwrite_size_threshold=-1,
    sleep_after=0,
    force_make_index_cache_directory=True,
):
    """
    Generic downloader, uses curl by default unless use_requests=True is passed in.

    Arguments:
        edgar_url (str): URL of EDGAR resource.
        local_path (Path, str): Local path to write to
        overwrite (bool): Flag for whether to overwrite any existing file (default False).
        use_requests (bool): Flag for whether to use requests or curl (default False == curl).
        chunk_size (int): Size of chunks to write to disk while streaming from requests
        overwrite_size_threshold (int): Existing files smaller than this will be re-downloaded.
        sleep_after (int): Number of seconds to sleep after downloading file (default 0)

    Returns:
        (str, None): Returns path of downloaded file (or None if download failed).
    """
    if not os.path.exists(os.path.dirname(local_path)):
        if force_make_index_cache_directory:
            os.makedirs(os.path.dirname(local_path))
        else:
            raise FileNotFoundError("Trying to write to non-existant directory: {}".format(os.path.dirname(local_path)))

    if os.path.exists(local_path):
        loc_size = os.path.getsize(local_path)
        if not overwrite and loc_size > overwrite_size_threshold:
            _logger.info("Skipping cache file (%s bytes) at %r", "{:,d}".format(loc_size), local_path)
            return local_path

        _logger.warning("Removing existing file (%s bytes) at %r", "{:,d}".format(loc_size), local_path)
        os.remove(local_path)

    _useragent = REQUEST_HEADERS["User-Agent"]

    if not use_requests:
        _logger.debug('curl -A "%s" %s -o %s', _useragent, edgar_url, local_path)
        subp = use_subprocess(["curl", '-A "{}"'.format(_useragent), edgar_url, "-o", local_path])
        _logger.debug(subp.stdout)
        sleep(sleep_after)
        if subp.returncode != 0:
            raise Exception("Error {} downloading with curl: {}".format(subp.returncode, subp.stderr))
    else:
        _logger.debug("requests.get(%r, headers=%r) >> %r", edgar_url, REQUEST_HEADERS, local_path)
        try:
            with requests.get(edgar_url, headers=REQUEST_HEADERS, stream=True) as response:
                expected_len = int(response.headers["content-length"])
                with open(local_path, "wb") as fh:
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if chunk:  # filter out keep-alive new chunks
                            fh.write(chunk)
            sleep(sleep_after)
        except Exception as excp:
            raise Exception("Error downloading with requests: {}".format(excp)) from excp

        # Now check what we downloaded was what we expected
        try:
            loc_size = os.path.getsize(local_path)
        except FileNotFoundError:
            raise Exception("Error downloading with requests to: {}".format(local_path))
        if expected_len != loc_size:
            _logger.exception("requests downloaded {:,d} bytes but expected {:,d}".format(loc_size, expected_len))

    if os.path.exists(local_path):
        _logger.info("Done downloading %.3f MB to %s", os.path.getsize(local_path) / 1024 ** 2, local_path)
        return local_path
    return None


def download_feed(date, overwrite=False, use_requests=False, overwrite_size_threshold=8 * 1024, sleep_after=0):
    """Download an edgar daily feed compressed file.

    Args:
        date (datetime, str): Date of feed file to download. Can be datetime
            or string (YYYYMMDD format with optional spacing).
        overwrite (bool): Flag for whether to overwrite any existing file (default False).
        use_requests (bool): Flag for whether to use requests or curl (default False == curl).
        overwrite_size_threshold (int): Existing files smaller than this will be re-downloaded.
        sleep_after (int): Number of seconds to sleep after downloading file (default 0)

    Returns:
        str: output file path
    """
    date = utilities.parse_date_input(date)

    if date.weekday() >= 5:  # skip sat/sun, because computers don't work weekends. Union rules, I think?
        return None

    feed_path = config.get_feed_cache_path(date)
    url = get_feed_url(date)

    return download_from_edgar(
        url,
        feed_path,
        overwrite=overwrite,
        use_requests=use_requests,
        overwrite_size_threshold=overwrite_size_threshold,
        sleep_after=sleep_after,
    )


def download_feeds_recursively(
    start_date, end_date=None, overwrite=False, use_requests=False, overwrite_size_threshold=8 * 1024, loop_sleep=1
):
    """Download edgar daily feed compressed files recursively from start to end.
    If `end_date` is `None`, default to today.
    Error downloads, or rate limited downloads are around 6kb,
    thus set the overwrite_size_threshold to larger than that
    to automatically re-download those error files.

    Args:
        start_date (datetime, str): Starting date of feeds to download. Can be datetime
            or string (YYYYMMDD format with optional spacing).
        end_date (None,datetime, str): Ending date of feeds to download (default today).
            Can be datetime or string (YYYYMMDD format with optional spacing).
        overwrite (bool): Flag for whether to overwrite any existing file (default False).
        use_requests (bool): Flag for whether to use requests or curl (default False == curl).
        overwrite_size_threshold (int): Existing files smaller than this will be re-downloaded.
        loop_sleep (int): Number of seconds to wait each loop after downloading file (default 1).

    Returns:
        tuple: output file path, return code
    """
    start_date = utilities.parse_date_input(start_date)
    end_date = utilities.parse_date_input(end_date or dt.datetime.today())
    loop_sleep = max(0.1, loop_sleep)

    _dls = []
    for i_date in utilities.iterate_dates(start_date, end_date, period="daily"):
        try:
            _dl = download_feed(
                i_date,
                overwrite=overwrite,
                use_requests=use_requests,
                overwrite_size_threshold=overwrite_size_threshold,
                sleep_after=loop_sleep,
            )
            _dls.append(_dl)
        except Exception as e:
            _logger.exception("Error downloading %d-%d-%d: %r", i_date.year, i_date.month, i_date.day, e)

    return _dls


def download_indexes_recursively(
    start_date,
    end_date=None,
    overwrite=False,
    use_requests=False,
    overwrite_size_threshold=8 * 1024,
    compressed=True,
    loop_sleep=1,
):
    """Download edgar quarterly compressed filing index files recursively from start to end.
    If `end_date` is `None`, default to today.
    Error downloads, or rate limited downloads are around 6kb,
    thus set the overwrite_size_threshold to larger than that
    to automatically re-download those error files.

    Args:
        start_date (datetime, str): Starting date of feeds to download. Can be datetime
            or string (YYYYMMDD format with optional spacing).
        end_date (None,datetime, str): Ending date of feeds to download. Default to today.
            Can be datetime or string (YYYYMMDD format with optional spacing).
        overwrite (bool): Flag for whether to overwrite any existing file. Default False).
        use_requests (bool): Flag for whether to use requests or curl. Default False == curl).
        overwrite_size_threshold (int): Existing files smaller than this will be re-downloaded. Default 8k.
        compressed (bool): Flag for whether compressed or uncompressed index files should be downloaded. Default True.
        loop_sleep (int): Number of seconds to wait each loop after downloading file (default 1).

    Returns:
        tuple: output file path, return code
    """
    start_date = utilities.parse_date_input(start_date)
    end_date = utilities.parse_date_input(end_date or dt.datetime.today())
    loop_sleep = max(0.1, loop_sleep)

    _dls = []
    for i_date in utilities.iterate_dates(start_date, end_date, period="quarterly"):
        edgar_url = get_index_url(i_date, compressed=compressed)
        index_cache = config.get_index_cache_path(i_date)

        try:
            _dl = download_from_edgar(
                edgar_url,
                index_cache,
                overwrite=overwrite,
                use_requests=use_requests,
                overwrite_size_threshold=overwrite_size_threshold,
                sleep_after=loop_sleep,
            )
            _dls.append(_dl)
        except Exception as e:
            _logger.exception("Error downloading %r: %r", i_date, e)

    return _dls
