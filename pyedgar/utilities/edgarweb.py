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

:copyright: © 2018 by Mac Gaulin
:license: MIT, see LICENSE for more details.
"""
import re
# import datetime as dt


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

    # Before FPT change: ftp://ftp.sec.gov/edgar/
    return ('https://www.sec.gov/Archives/edgar/data/{}/{}.txt'.format(cik, accession),
            'http://www.sec.gov/Archives/edgar/data/{}/{}-index.htm'.format(cik, accession))

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

def get_idx_path(date_or_year, quarter=None, tar=False):
    """
    Get URL path to quarterly index file. Don't feed it a year and no quarter.
    """
    if quarter is None:
        quarter = _get_qtr(date_or_year)
    try:
        date_or_year = date_or_year.year
    except AttributeError:
        # Then date_or_year is an integer. Leave it be.
        pass
    idx_path = "/edgar/full-index/{0}/QTR{1}/master.{2}"
    return idx_path.format(date_or_year, quarter, 'gz' if tar else 'idx')
