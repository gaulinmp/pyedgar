# -*- coding: utf-8 -*-
"""
pyEDGAR SEC data library: Utilities package
======================================================

These utilities represent lower level functionality, used by the main modules.

:copyright: © 2025 by Mac Gaulin
:license: MIT, see LICENSE for more details.
"""

# Stdlib imports
import re as __re
import datetime as __dt
import logging as __logging

__logger = __logging.getLogger(__name__)


def get_cik_acc(*args, additional_extract=None, accession_pattern=__re.compile("\d{10}-?\d{2}-?\d{6}"), **kwargs):
    """
    I found myself wanting to accept flexible cik/acc inputs, and wrote this
    input parsing over and over. So finally we'll DRY and centralize.

    Examples:
        Can be called in any of the following ways::

            cik,acc = 1750, '1234567890-12-123456'
            get_cik_acc(cik, acc)
            get_cik_acc(acc, cik)
            get_cik_acc(namedtuple('foo', ['cik', 'accession'])(cik=cik, accession=acc))
            get_cik_acc({'cik':cik, 'accession':acc})
            get_cik_acc({'cik':cik, 'accession':acc, 'gvkey': 1, 'datadate':dt.date(2020,1,1)})
            get_cik_acc({'cik':cik, 'accession':acc, 'gvkey': 1, 'datadate':dt.date(2020,1,1)}, additional_extract='gvkey datadate'.split())
            get_cik_acc(**{'cik':cik, 'accession':acc, 'gvkey': 1, 'datadate':dt.date(2020,1,1)}, additional_extract='datadate')
            get_cik_acc(**{'cik_from':cik, 'accession_from':acc}, additional_extract='cik_from accession_from'.split())


    Arguments:
        positional arguments: will grab the first cik and acccession looking values, put the rest in 'args' key
        additional_extract (str, list): one (str) or more (list) additional keywords to extract from inputs
        kwargs: will overwrite any positional arg matches, put non-looked for

    Returns:
        tuple: Tuple of (cik, accession, etc?)
    """
    _ret = {}
    _unused_args = []
    _unused_kwargs = {}

    if additional_extract is None:
        additional_extract = []
    elif isinstance(additional_extract, str):
        additional_extract = [additional_extract]

    def _get_thing(thing, box_o_things):
        try:
            return getattr(box_o_things, thing)
        except AttributeError:
            pass
        try:
            return box_o_things.get(thing, None)
        except AttributeError:
            pass
        return None

    if len(args):
        # Here, look for cik & acc, put the rest into the args/kwargs key
        for arg in args:
            if arg is None:
                continue

            if isinstance(arg, str) and accession_pattern.search(arg):
                # Definitively an accession
                if "accession" in _ret:
                    _unused_args.append(arg)
                else:
                    _ret["accession"] = accession_pattern.search(arg).group(0)
            elif "cik" in _ret:  # If we already have a cik, then don't overwrite it
                _unused_args.append(arg)
            elif isinstance(arg, (str, int, float)):  # ciks are just numbers
                try:
                    # int of float because pandas might convert cik to float
                    _ret["cik"] = int(float(arg))
                except ValueError:  # no TypeError beause of isinstance match above
                    _unused_args.append(arg)
            else:
                # At this point, if cik/acc is num/str format, we handled it.
                # So we just have dicts/objects to check, then bail
                _val = _get_thing("cik", arg)
                if _val is not None:
                    try:
                        # int of float because pandas might convert cik to float
                        _ret["cik"] = int(float(_val))
                    except (ValueError, TypeError):  # no TypeError beause of isinstance match above
                        pass
                _val = _get_thing("accession", arg)
                if _val is not None:
                    if isinstance(_val, str) and accession_pattern.search(_val):
                        # Definitively an accession
                        if "accession" not in _ret:
                            _ret["accession"] = accession_pattern.search(_val).group(0)

                for addtl_val in additional_extract:
                    _val = _get_thing(addtl_val, arg)
                    if _val is not None:
                        _ret[addtl_val] = _val
                # We don't know if we used them all, so tack the dict/obj on to the 'unused'
                _unused_args.append(arg)

    if len(kwargs):
        try:
            # int of float of input, because pandas might convert cik to float
            _ret["cik"] = int(float(kwargs["cik"]))
        except (ValueError, TypeError, KeyError):
            # Wasn't the right type/parseable, or no cik key
            pass

        _val = kwargs.get("accession", None)
        if isinstance(_val, str) and accession_pattern.search(_val):
            # Definitively an accession
            _ret["accession"] = accession_pattern.search(_val).group(0)

        for addtl_val in additional_extract:
            _val = kwargs.get(addtl_val, None)
            if _val is not None:
                _ret[addtl_val] = _val

        for _key, _val in kwargs.items():
            if _key not in _ret:
                _unused_kwargs[_key] = _val

    if len(_unused_args):
        _ret["args"] = _unused_args
    if len(_unused_kwargs):
        _ret["kwargs"] = _unused_kwargs
        for _key, _val in _unused_kwargs.items():
            if _key not in _ret:
                _ret[_key] = _val

    return _ret


def parse_date_input(
    date,
    default=None,
    dt_re=__re.compile(r"([12]\d{3})[^0-9]+(\d\d?)[^0-9]+(\d\d?)"),
    dtnodelim_re=__re.compile(r"([12]\d{3})(\d\d)(\d\d)"),
    qtr_re=__re.compile(r"([12]\d{3})[Qq]([1234])"),
    yr_re=__re.compile(r"[12]\d{3}"),
):
    """
    Casts something to a date, defaulting to yesterday if nothing is passed in.
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
        default = __dt.date.fromordinal(__dt.date.today().toordinal() - 1)
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


def get_quarter(datetime_in):
    """
    Return the quarter (1-4) based on the month.
    Input is either a datetime object (or object with month attribute) or the month (1-12).
    """
    try:
        return int((datetime_in.month - 1) / 3) + 1
    except AttributeError:
        return int((datetime_in - 1) / 3) + 1


def iterate_dates(from_date, to_date=None, period="daily", skip_weekends=True, inclusive=True):
    """
    Iterates over a date range at a given 'periodicity', where the period is represented by the first occuring date.
    So Q1, 2000 would be `dt.date(2000, 1, 1)`.
    Can skip weekends, but does not know about holidays.

    Arguments:
        from_date (str, datetime, int): Can be datetime, year (int or string), string of format YYYYMMDD
            or YYYY-M-D, or string of format YYYYq[1234].
        to_date (str, datetime, int, None): Can be datetime, year (int or string), string of format YYYYMMDD
            or YYYY-M-D, or string of format YYYYq[1234]. Default: yesterday.
        period (str): Periodicity of dates yielded, either `yearly`, `quarterly`, or `daily`. Default to daily.
        skip_weekends (bool): Flag for whether to skip returning weekends (sat/sun). Default: True.
        inclusive (bool): Flag for whether to include the to_date (or the quarter/year of to_date). Default: True.

    Returns:
        (datetime): Yields datetime objects
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
