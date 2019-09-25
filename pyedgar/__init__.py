# -*- coding: utf-8 -*-
"""
pyEDGAR SEC data library.
=====================================

pyEDGAR is a general purpose library for all sorts of interactions with the SEC
data sources, primarily the EDGAR distribution system.

Files from the SEC reside at https://www.sec.gov/Archives/edgar/data/CIK/ACCESSION.txt

:copyright: © 2019 by Mac Gaulin
:license: MIT, see LICENSE for more details.
"""

__title__ = 'pyedgar'
__version__ = '0.1.0'
__version_info__ = tuple(int(i) for i in __version__.split("."))
__author__ = 'Mac Gaulin'
__license__ = 'MIT'
__copyright__ = 'Copyright 2019 Mac Gaulin'


# Include sub-modules
from pyedgar.filing import Filing
from pyedgar.index import EDGARIndex

# from pyedgar import utilities
# from pyedgar import exceptions
# from .exceptions import (InputTypeError, WrongFormType,
#                          NoFormTypeFound, NoCIKFound)

# __all__ = [edgarweb, forms, localstore, plaintext, #downloader,
#            InputTypeError, WrongFormType, NoFormTypeFound, NoCIKFound]
