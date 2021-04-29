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

def datetime_from_string(date):
    """Convert string date in YYYY-MM-DD format to datetime object."""
    if isinstance(date, str):
        date, date_input = __re.sub('[^0-9]', '', date), date
        if len(date) != 8:
            __logger.error("Date must be in YYYYMMDD format (spacing ignored). You passed: %r", date_input)
            return
        date = __dt.datetime(int(date[:4]), int(date[4:6]), int(date[6:]))
    return date
