#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Utilities for interacting with edgar forms.
"""

# import os
# import re
import logging

from . import localstore
from . import forms
# from . import plaintext
# from .htmlparse import RE_HTML_TAGS, convert_html_to_text, html_ent_re_sub
# from .. import exceptions as EX

__logger = logging.getLogger(__name__)

def get_headers(cik, accession, file_date):
    orig_fname = localstore.get_filing_path(cik, accession)
    with open(orig_fname) as fh:
        orig_txt = fh.read(10000)

    keep_hdrs = 'filing-date fiscal-year-end form-type period fyend fyear quarter'.split()
    hdrs = {k:forms.get_header(orig_txt, k) for k in keep_hdrs}

    for k in keep_hdrs:
        if hdrs[k] == '':
            pass
#             print("We failed to find {}".format(k))

    tmp = hdrs.get('filing-date', None)
    try:
        hdrs['fdate'] = dt.datetime(int(tmp[:4]), int(tmp[4:6]), int(tmp[-2:]))
    except ValueError:
        hdrs['fdate'] = file_date

    tmp = hdrs.get('period', None)
    try:
        hdrs['pdate'] = dt.datetime(int(tmp[:4]), int(tmp[4:6]), int(tmp[-2:]))
    except ValueError:
        pass

    tmp = hdrs.get('fiscal-year-end', None)
    try:
        hdrs['fyend'] = dt.datetime(hdrs.get('pdate', file_date-dt.timedelta(90)).year,
                                    int(tmp[:2]), int(tmp[-2:]))

        if hdrs['fyend'] > hdrs.get('pdate', file_date-dt.timedelta(90)):
            hdrs['fyend'] = dt.datetime(hdrs['fyend'].year - 1,
                                        hdrs['fyend'].month,
                                        hdrs['fyend'].day)
    except ValueError:
        pass

    try:
        hdrs['quarter'] = round((hdrs.get('pdate', file_date-dt.timedelta(90)) -
                                 hdrs['fyend']).days/90)
        hdrs['fyear'] = hdrs['fyend'].year
    except TypeError:
        pass

    hdrs['cik'] = cik
    hdrs['accession'] = forms.get_header(orig_txt, 'accession-number')

    return hdrs
