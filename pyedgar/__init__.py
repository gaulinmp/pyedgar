# -*- coding: utf-8 -*-

"""
pyEDGAR SEC data library.
=====================================

pyEDGAR is a general purpose library for all sorts of interactions with the SEC
data sources, primarily the EDGAR distribution system.

Files from the SEC reside at https://www.sec.gov/Archives/edgar/data/CIK/ACCESSION.txt

:copyright: © 2018 by Mac Gaulin
:license: MIT, see LICENSE for more details.
"""

__title__ = 'pyedgar'
__version__ = '0.0.3a1'
__author__ = 'Mac Gaulin'
__license__ = 'MIT'
__copyright__ = 'Copyright 2018 Mac Gaulin'


# Include top level modules
from . import filing
from . import downloader

# Include sub-modules
from . import utilities
from . import exceptions
from .exceptions import (InputTypeError, WrongFormType,
                         NoFormTypeFound, NoCIKFound)

# __all__ = [edgarweb, forms, localstore, plaintext, #downloader,
#            InputTypeError, WrongFormType, NoFormTypeFound, NoCIKFound]
