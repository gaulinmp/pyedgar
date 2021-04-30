# -*- coding: utf-8 -*-
"""
pyEDGAR SEC data library: Utilities package
======================================================

These utilities represent lower level functionality, used by the main modules.

:copyright: © 2020 by Mac Gaulin
:license: MIT, see LICENSE for more details.
"""

# Stdlib imports
import re as __re
import datetime as __dt
import logging as __logging

__logger = __logging.getLogger(__name__)


def get_cik_acc(cik, accession=None):
    """
    I found myself wanting to accept flexible cik/acc inputs, and wrote this
    input parsing over and over. So finally we'll DRY and centralize.

    Arguments:
        cik (str,dict,object): String CIK, or object with cik and accession attributes or keys.
        accession (str): String ACCESSION number, or None if accession in CIK object.

    Returns:
        tuple: Tuple of (cik, accession)
    """
    try:  # cik has cik/acc attributes?
        accession = cik.accession if accession is None else accession
        cik = cik.cik
    except AttributeError:
        try:  # cik is dict?
            accession = cik.get("accession") if accession is None else accession
            cik = cik.get("cik")
        except AttributeError:
            # Hopefully cik is a cik, and acc is an acc
            cik = int(cik)

    # why this would happen, who knows. But it might?
    if accession is not None and not isinstance(accession, str):
        try:  # acc has acc attribute?
            accession = accession.accession
        except AttributeError:
            try:  # acc is dict?
                accession = accession.get("accession")
            except AttributeError:
                # Whelp, we tried. Errors will abound downstream.
                pass

    return cik, accession


def parse_date_input(
    date,
    default=None,
    dt_re=__re.compile(r"([12]\d{3})[^0-9]+(\d\d?)[^0-9]+(\d\d?)"),
    dtnodelim_re=__re.compile(r"([12]\d{3})(\d\d)(\d\d)"),
    qtr_re=__re.compile(r"([12]\d{3})[Qq]([1234])"),
    yr_re=__re.compile(r"[12]\d{3}"),
):
    """
    Casts something to a date.
    The something can be:

        date: dt.date(2000, 1, 1)
        year (int or string): 2000 or '2000'
        date string: 20001231 or 2000-1-5 (the former must be MM, the latter can omit leading 0s)
        quarter string: 2001Q3

    Arguments:
        date (str, date, int, None): Input that makes sense cast to a date. Years will be January 1st,
            quarters will be on the 1st day of the 1st month in the quarter.
    """
    if default is None or not hasattr(default, "year"):
        default = __dt.date.today()
    _d = None  # keep _d None until it's date, easier for ifs below

    if date is None:
        _d = default
    elif isinstance(date, str):
        _ymd = dt_re.search(date) or dtnodelim_re.search(date)
        if _ymd:
            _d = __dt.date(*map(int, _ymd.groups()))

        if _d is None and qtr_re.search(date):
            _y, _q = map(int, qtr_re.search(date).groups())
            _d = __dt.date(_y, _q * 3 - 2, 1)

        if _d is None and yr_re.search(date):
            _d = __dt.date(int(yr_re.search(date).group(0)), 1, 1)
    else:  # it could be a date, try that
        try:
            _d = __dt.date(date.year, date.month, date.day)
        except AttributeError:
            pass

    if _d is None:  # well, it's not none, date, or various strings, try int
        try:
            _d = __dt.date(int(date), 1, 1)
        except (TypeError, ValueError):
            pass

    # We've handled none, dates, int, and strings, so at this point we gotta give up
    if not hasattr(_d, "year"):
        raise ValueError("Input format not recognized: {}".format(date))

    return _d


def iterate_dates(from_date, to_date=None, period="daily", skip_weekends=True, inclusive=True):
    """

    Arguments:
        from_date (str, datetime, int): Can be datetime, year (int or string), string of format YYYYMMDD
            or YYYY-M-D, or string of format YYYYq[1234].
        to_date (str, datetime, int, None): Can be datetime, year (int or string), string of format YYYYMMDD
            or YYYY-M-D, or string of format YYYYq[1234]. Default: today.
        period (str): Periodicity of dates yielded, either `yearly`, `quarterly`, or `daily`. Default to daily.
        skip_weekends (bool): Flag for whether to skip returning weekends (sat/sun). Default: True.
        inclusive (bool): Flag for whether to include the to_date (or the quarter/year of to_date). Default: True.
    """
    period = str(period).lower()[0]
    _from = parse_date_input(from_date)
    _to = parse_date_input(to_date)

    if _from > _to:  # greater than means after in date math
        _from, _to = _to, _from

    if period == "y":
        for i_yr in range(_from.year, _to.year + inclusive):
            yield __dt.date(i_yr, 1, 1)
    elif period == "q":
        _yqfrom = _from.year * 4 + (_from.month - 1) // 3
        _yqto = _to.year * 4 + (_to.month - 1) // 3
        for i_qtr in range(_yqfrom, _yqto + inclusive):
            # Now reverse the yr * 4 + qtr math above.
            # I solved this mathematically, without error.
            # Definitely not trial and error in a notebook.
            yield __dt.date(i_qtr // 4, (i_qtr % 4) * 3 + 1, 1)
    else:
        for i_date in range(_from.toordinal(), _to.toordinal() + inclusive):
            i_date = __dt.date.fromordinal(i_date)
            if skip_weekends and i_date.weekday() >= 5:
                continue
            yield i_date
