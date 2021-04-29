# -*- coding: utf-8 -*-
"""
Utilities for general EDGAR website and ftp tasks.

index URL: http://www.sec.gov/Archives/edgar/data/2098/0001026608-05-000015-index.htm
complete submission URL: http://www.sec.gov/Archives/edgar/data/2098/000102660805000015/0001026608-05-000015.txt
Exhibit/form URL: http://www.sec.gov/Archives/edgar/data/2098/000102660815000007/acu_10k123114.htm

EDGAR FTP change in 2016:
<2016 ftp URL: ftp://ftp.sec.gov/edgar/data/2098/0000002098-96-000003.txt
>2016 http URL: https://www.sec.gov/Archives/edgar/data/2098/0000002098-96-000003.txt

EDGAR HTML specification: https://www.sec.gov/info/edgar/ednews/edhtml.htm

:copyright: © 2020 by Mac Gaulin
:license: MIT, see LICENSE for more details.
"""

# Stdlib imports
import os
import re
import logging
import subprocess

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
    cik,accession = utilities.get_cik_acc(cik, accession=accession)

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
    _raw,_idx = get_edgar_urls(cik, accession=accession)

    _html = []
    if index:
        _html.append("<a href='{}' target=_blank>Index</a>".format(_idx))
    if raw:
        _html.append("<a href='{}' target=_blank>Raw</a>".format(_raw))

    return ' '.join(_html)


def _get_qtr(datetime_in):
    """
    Return the quarter (1-4) based on the month.
    Input is either a datetime object (or object with month attribute) or the month (1-12).
    """
    try:
        return int((datetime_in.month - 1) / 3) + 1
    except AttributeError:
        return int((datetime_in - 1) / 3) + 1


def get_feed_url(date):
    """Get URL path to daily feed gzip file.

    Arguments:
        date (datetime): Date for feed file

    Returns:
        str: URL to feed file on `date`"""
    return "{0}/edgar/Feed/{1:%Y}/QTR{2}/{1:%Y%m%d}.nc.tar.gz".format(EDGAR_ROOT, date, _get_qtr(date))


def get_index_url(date_or_year, quarter=None, compressed=True):
    """
    Get URL path to quarterly index file.
    Do not feed it a year and no quarter.

    Arguments:
        date_or_year (datetime,int): Datetime from which the index's quarter will be calculated, or integer year
        quarter (int,None): Quarter of the index, will be inferred from date_or_year if None.
    """
    try:
        date_or_year = date_or_year.year
        # Leave this here, because if date_or_year isn't a datetime, we can't calculate the quarter. So error out.
        if quarter is None:
            quarter = _get_qtr(date_or_year)
    except AttributeError:
        # Then date_or_year is an integer. Leave it be.
        if quarter is None:
            raise AttributeError("Must either pass either datetime or both integer year AND quarter")

    ext = "gz" if compressed else "idx"

    return "{0}/edgar/full-index/{1}/QTR{2}/master.{3}".format(EDGAR_ROOT, date_or_year, quarter, ext)


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
    _raw,_ = get_edgar_urls(cik, accession=accession)

    r = requests.get(_raw, headers=REQUEST_HEADERS)

    data = r.content

    for _decode_type, _errors in zip(("latin-1", "utf-8", "latin-1"), ("strict", "strict", "ignore")):
        try:
            return data.decode(_decode_type, errors=_errors)
        except (UnicodeDecodeError, ValueError):
            continue


def download_from_edgar(edgar_url, local_path, overwrite=False, use_requests=False, chunk_size=10 * 1024 ** 2, overwrite_size_threshold=-1):
    """
    Generic downloader, uses curl by default unless use_requests=True is passed in.

    Arguments:
        edgar_url (str): URL of EDGAR resource.
        local_path (Path, str): Local path to write to
        overwrite (bool): Flag for whether to overwrite any existing file (default False).
        use_requests (bool): Flag for whether to use requests or curl (default False == curl).
        chunk_size (int): Size of chunks to write to disk while streaming from requests
        overwrite_size_threshold (int): Existing files smaller than this will be re-downloaded.

    Returns:
        (str, None): Returns path of downloaded file (or None if download failed).
    """
    if not os.path.exists(os.path.dirname(local_path)):
        raise FileNotFoundError("Trying to write to non-existant directory: {}".format(os.path.dirname(local_path)))

    if os.path.exists(local_path):
        loc_size = os.path.getsize(local_path)
        if not overwrite and loc_size > overwrite_size_threshold:
            _logger.warning("Skipping cache file (%s bytes) at %r", '{:,d}'.format(loc_size), local_path)
            return local_path

        _logger.warning("Removing existing file (%s bytes) at %r", '{:,d}'.format(loc_size), local_path)
        os.remove(local_path)

    _useragent = REQUEST_HEADERS["User-Agent"]

    if not use_requests:
        _logger.info('curl -A "%s" %s -o %s', _useragent, edgar_url, local_path)
        subp = subprocess.run(["curl", '-A "{}"'.format(_useragent), edgar_url, "-o", local_path])
        if subp.returncode != 0:
            raise Exception("Error %r downloading with curl: %r", subp.returncode, subp.stderr)
    else:
        _logger.info("requests.get(%r, headers=%r) >> %r", edgar_url, REQUEST_HEADERS, local_path)
        try:
            with requests.get(edgar_url, headers=REQUEST_HEADERS, stream=True) as response:
                expected_len = int(response.headers["content-length"])
                with open(local_path, "wb") as fh:
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if chunk:  # filter out keep-alive new chunks
                            fh.write(chunk)
        except Exception as excp:
            raise Exception("Error downloading with requests: %r", excp) from excp

        # Now check what we downloaded was what we expected
        try:
            loc_size = os.path.getsize(local_path)
        except FileNotFoundError:
            raise Exception("Error downloading with requests to: %r", local_path)
        if expected_len != loc_size:
            _logger.exception("requests downloaded {:,d} bytes but expected {:,d}".format(loc_size, expected_len))

    if os.path.exists(local_path):
        return local_path
    return None


class EDGARDownloader(object):
    """
    Class that downloads feeds, indexes, or filings from EDGAR.
    """

    # May as well share this across instances (instead of setting in __init__)
    _logger = logging.getLogger(__name__)

    def download_tar(self, edgar_url, local_target, chunk_size=1024 ** 2, retries=5, resume=True):
        """Download a file from `edgar_url` to `local_target`."""

        # Verify destination directory exists
        if not os.path.exists(os.path.dirname(local_target)):
            raise FileNotFoundError("The directory does not exist: {}".format(os.path.dirname(local_target)))

        # If it fails, try, try, try, try again. Then stop; accept failure.
        for n_retries in range(retries):
            # Check for local copy and determine length (for caching/resuming)
            try:
                loc_size = os.path.getsize(local_target)
                headers = {"Range": "bytes={loc_size}-".format(loc_size=loc_size)}
                # Resume with header: Range: bytes=StartPos- (implicit end pos)
            except FileNotFoundError:
                loc_size = 0
                headers = None

            # Check total file length on server
            with requests.get(edgar_url, stream=True) as response:
                if response.status_code // 100 == 4:
                    # No such file
                    return None
                expected_tot_len = int(response.headers["content-length"])

            # If local length matches, we are done. Return local path
            if expected_tot_len == loc_size:
                self._logger.info(
                    "Already downloaded (%r == %r) from %r to %r", loc_size, expected_tot_len, edgar_url, local_target
                )
                break

            # If local length is longer than server, we done goofed. Delete it and try again.
            if loc_size > expected_tot_len:
                self._logger.info(
                    "Downloaded too much (%r > %r) from %r, removing %r",
                    loc_size,
                    expected_tot_len,
                    edgar_url,
                    local_target,
                )
                os.remove(local_target)
                loc_size = 0
                headers = None
            elif not resume and (0 < loc_size < expected_tot_len):
                self._logger.info("No resuming (%r < %r), removing %r", loc_size, expected_tot_len, local_target)
                os.remove(local_target)
                loc_size = 0
                headers = None

            self._logger.info("Downloading %r of %r: %r to %r", n_retries, retries, edgar_url, local_target)

            # Download or resume
            with requests.get(edgar_url, headers=headers, stream=True) as response:
                expected_len = int(response.headers["content-length"])

                if loc_size:
                    self._logger.info(
                        "Already downloaded (%r/%r, remaining: %r) from %r to %r",
                        loc_size,
                        expected_tot_len,
                        expected_len,
                        edgar_url,
                        local_target,
                    )

                with open(local_target, "ab" if loc_size else "wb") as fh:
                    self._logger.info("Saving tar {} to {}".format(edgar_url, local_target))

                    for chunk in self._tq(
                        response.iter_content(chunk_size=chunk_size),
                        total=expected_len // chunk_size,
                        unit="Mb",
                        desc=os.path.basename(local_target),
                    ):
                        if chunk:  # filter out keep-alive new chunks
                            fh.write(chunk)

            self._logger.info("Done saving (len: {}) {}".format(os.path.getsize(local_target), local_target))

            break  # Done downloading, break out of range(5)

        return local_target

    def download_plaintext(self, edgar_url, local_target, chunk_size=1024 ** 2, overwrite=True):
        """
        Download a plaintext file from `edgar_url` to `local_target`.
        """
        # Return if exists. Delete if it is partial?
        if os.path.exists(local_target):
            if overwrite:
                os.remove(local_target)
            else:
                return local_target

        # Verify destination directory exists
        if not os.path.exists(os.path.dirname(local_target)):
            raise FileNotFoundError("The directory does not exist: {}".format(os.path.dirname(local_target)))

        self._logger.info("Downloading plaintext: %r to %r", edgar_url, local_target)

        # Check total file length on server
        with requests.get(edgar_url, stream=True) as response:
            if response.status_code // 100 == 4:
                # No such file
                return None
            expected_tot_len = int(response.headers.get("content-length", 10 * 1024 ** 2))

            with open(local_target, "wb") as fh:
                self._logger.info("Saving plaintext %r to %r", edgar_url, local_target)

                for chunk in self._tq(
                    response.iter_content(chunk_size=chunk_size),
                    total=expected_tot_len // chunk_size,
                    unit="Mb",
                    desc=os.path.basename(local_target),
                ):
                    if chunk:  # filter out keep-alive new chunks
                        fh.write(chunk)

        self._logger.info("Done saving (len: {}) {}".format(os.path.getsize(local_target), local_target))

        return local_target
