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

:copyright: © 2019 by Mac Gaulin
:license: MIT, see LICENSE for more details.
"""

import os
# import sys
import re
# import tarfile
import logging
# import datetime as dt
import requests

# Local logger
_logger = logging.getLogger(__name__)

try:
    def _faketqdm(x, *args, **kwargs):
        return x
    from tqdm import tqdm as _tqdm
except ModuleNotFoundError:
    _tqdm = _faketqdm


# Constants
# Used to be (before FTP changed to AWS S3): ftp://ftp.sec.gov
EDGAR_ROOT = 'https://www.sec.gov/Archives'


def parse_url(url):
    """Return CIK and Accession from an EDGAR HTTP or FTP url.

    :param string url: URL from EDGAR website or FTP server.

    :return: Tuple of strings in the form (cik, accession) or (None, None)
    :rtype: tuple (string/None, string/None)
    """
    url_re = re.compile(r'/(?P<cik>\d{1,10})/'
                        r'(?P<accession>\d{10}-?\d\d-?\d{6})', re.I)
    res = url_re.search(url)
    if res:
        acc = res.group('accession')
        if len(acc) == 18:
            acc = acc[:10] + '-' + acc[10:12] + '-' + acc[12:]
        return res.group('cik'), acc
    return None, None

def get_edgar_urls(cik, accession=None):
    """Generage URLs for EDGAR 'bulk download' and 'user facing' sites.
    `cik` parameter can be object with `cik` and `accession` attributes or keys.

    :param string,object cik: String CIK, or object with cik and accession attributes or keys.
    :param string accession: String ACCESSION number, or None if accession in CIK object.

    :return: Tuple of strings in the form (bulk DL url, user website url)
    :rtype: tuple (string, string)
    """
    if accession is None:
        try: # cik has cik/acc attributes?
            cik = cik.cik
            accession = cik.accession if accession is None else accession
        except AttributeError:
            try: # cik is dict?
                cik = cik.get('cik')
                accession = cik.get('accession')
            except AttributeError:
                pass

    return ('{}/edgar/data/{}/{}.txt'.format(EDGAR_ROOT, cik, accession),
            '{}/edgar/data/{}/{}-index.htm'.format(EDGAR_ROOT, cik, accession))

def edgar_links(cik, accession=None):
    """Generage HTML encoded links (using `a` tag) to EDGAR 'bulk download' and 'user facing' sites.
    `cik` parameter can be object with `cik` and `accession` attributes or keys.

    :param string,object cik: String CIK, or object with cik and accession attributes or keys.
    :param string accession: String ACCESSION number, or None if accession in CIK object.

    :return: String of HTTP encoded links
    :rtype: string
    """
    return ("<a href='{1}' target=_blank>Index</a> <a href='{0}' target=_blank>Raw</a>"
            .format(*get_edgar_urls(cik, accession=accession)))

def _get_qtr(datetime_in):
    """
    Return the quarter (1-4) based on the month.
    Input is either a datetime object (or object with month attribute) or the month (1-12).
    """
    try:
        return int((datetime_in.month-1)/3)+1
    except AttributeError:
        pass
    return int((datetime_in-1)/3)+1

def get_feed_path(date):
    """Get URL path to daily feed gzip file."""
    feed_path = "/edgar/Feed/{0:%Y}/QTR{1}/{0:%Y%m%d}.nc.tar.gz"
    return feed_path.format(date, _get_qtr(date))

def get_idx_path(date_or_year, quarter=None, compressed=False):
    """
    Get URL path to quarterly index file.
    Do not feed it a year and no quarter.
    """
    if quarter is None:
        quarter = _get_qtr(date_or_year)
    try:
        date_or_year = date_or_year.year
    except AttributeError:
        # Then date_or_year is an integer. Leave it be.
        pass

    return ("/edgar/full-index/{0}/QTR{1}/master.{2}"
            .format(date_or_year, quarter, 'gz' if compressed else 'idx'))

def download_form_from_web(cik, accession):
    """
    Sometimes the cache file is not there, or you do not have local cache.
    In those cases, you can download the EDGAR forms from S3 directly.

    NOTE: None of the header parsing functionality will work because the Web
          version of EDGAR converts the SGML header to indented plain text.
    """

    cik = int(cik)
    try:
        url = get_edgar_urls(int(cik), accession)[0]
    except ValueError:
        _logger.exception("CIK must be an integer: %r", cik)
        raise

    r = requests.get(url)

    data = r.content

    for _decode_type, _errors in zip(('latin-1', 'utf-8', 'latin-1'),
                                     ('strict', 'strict', 'ignore')):
        try:
            txt = data.decode(_decode_type, errors=_errors)
        except (UnicodeDecodeError, ValueError):
            continue
        break

    return txt


class EDGARDownloader(object):
    """
    Class that downloads files from EDGAR.
    Supports resuming on compressed (tar) files.
    """

    # May as well share this across instances (instead of setting in __init__)
    _logger = logging.getLogger(__name__)

    _tq = None

    def __init__(self, use_tqdm=True):
        """
        Initialize the downloader object.

        use_tqdm: sets whether download progress is wrapped in tqdm.
        """
        self._tq = _tqdm if use_tqdm else _faketqdm

    def download_tar(self, remote_path, local_target, chunk_size=1024**2, retries=5, resume=True):
        """Download a file from `remote_path` to `local_target`."""
        from_addr = ('{edgar_root}{remote_path}'
                     .format(edgar_root=EDGAR_ROOT, remote_path=remote_path))

        # Verify destination directory exists
        if not os.path.exists(os.path.dirname(local_target)):
            raise FileNotFoundError('The directory does not exist: {}'
                                    .format(os.path.dirname(local_target)))

        # If it fails, try, try, try, try again. Then stop; accept failure.
        for n_retries in range(retries):
            # Check for local copy and determine length (for caching/resuming)
            try:
                loc_size = os.path.getsize(local_target)
                headers = {'Range': 'bytes={loc_size}-'.format(loc_size=loc_size)}
                # Resume with header: Range: bytes=StartPos- (implicit end pos)
            except FileNotFoundError:
                loc_size = 0
                headers = None

            # Check total file length on server
            with requests.get(from_addr, stream=True) as response:
                if response.status_code // 100 == 4:
                    # No such file
                    return None
                expected_tot_len = int(response.headers['content-length'])

            # If local length matches, we are done. Return local path
            if expected_tot_len == loc_size:
                self._logger.info("Already downloaded (%r == %r) from %r to %r",
                                  loc_size, expected_tot_len, remote_path, local_target)
                break

            # If local length is longer than server, we done goofed. Delete it and try again.
            if loc_size > expected_tot_len:
                self._logger.info("Downloaded too much (%r > %r) from %r, removing %r",
                                  loc_size, expected_tot_len, remote_path, local_target)
                os.remove(local_target)
                loc_size = 0
                headers = None
            elif not resume and (0 < loc_size < expected_tot_len):
                self._logger.info("No resuming (%r < %r), removing %r",
                                  loc_size, expected_tot_len, local_target)
                os.remove(local_target)
                loc_size = 0
                headers = None

            self._logger.info("Downloading %r of %r: %r to %r",
                              n_retries, retries, remote_path, local_target)

            # Download or resume
            with requests.get(from_addr, headers=headers, stream=True) as response:
                expected_len = int(response.headers['content-length'])

                if loc_size:
                    self._logger.info("Already downloaded (%r/%r, remaining: %r) from %r to %r",
                                      loc_size, expected_tot_len, expected_len, remote_path, local_target)

                with open(local_target, 'ab' if loc_size else 'wb') as fh:
                    self._logger.info("Saving tar {} to {}"
                                      .format(remote_path, local_target))

                    for chunk in self._tq(response.iter_content(chunk_size=chunk_size),
                                          total=expected_len//chunk_size,
                                          unit="Mb",
                                          desc=os.path.basename(local_target)):
                        if chunk:  # filter out keep-alive new chunks
                            fh.write(chunk)

            self._logger.info("Done saving (len: {}) {}"
                                .format(os.path.getsize(local_target),
                                        local_target))

            break  # Done downloading, break out of range(5)

        return local_target

    def download_plaintext(self, remote_path, local_target, chunk_size=1024**2):
        """
        Download a plaintext file from `remote_path` to `local_target`.
        Forces download, because there's no way to verify with server that the whole file is downloaded,
        unlike gzip compressed files above.
        """
        from_addr = ('https://www.sec.gov/Archives{remote_path}'
                     .format(remote_path=remote_path))

        # Return if exists. Delete if it is partial?
        if os.path.exists(local_target):
            os.remove(local_target)

        # Verify destination directory exists
        if not os.path.exists(os.path.dirname(local_target)):
            raise FileNotFoundError('The directory does not exist: {}'
                                    .format(os.path.dirname(local_target)))

        self._logger.info(("Downloading plaintext: "
                           "{remote_path} to {local_target}")
                           .format(remote_path=remote_path,
                                   local_target=local_target))

        # Check total file length on server
        with requests.get(from_addr, stream=True) as response:
            if response.status_code // 100 == 4:
                # No such file
                return None
            expected_tot_len = int(response.headers.get('content-length', 10 * 1024**2))

            with open(local_target, 'wb') as fh:
                self._logger.info("Saving plaintext {} to {}"
                                    .format(remote_path, local_target))

                for chunk in self._tq(response.iter_content(chunk_size=chunk_size),
                                      total=expected_tot_len//chunk_size,
                                      unit="Mb",
                                      desc=os.path.basename(local_target)):
                    if chunk:  # filter out keep-alive new chunks
                        fh.write(chunk)

        self._logger.info("Done saving (len: {}) {}"
                            .format(os.path.getsize(local_target),
                                    local_target))

        return local_target
