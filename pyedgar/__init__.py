#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
pyEDGAR SEC data library.
=====================================

pyEDGAR is a general purpose library for all sorts of interactions with the SEC
data sources, primarily the EDGAR distribution system.

Files from the SEC reside at ftp://ftp.sec.gov/edgar/

"""

__title__ = 'pyedgar'
__version__ = '0.0.1'
__author__ = 'Mac Gaulin'
__license__ = 'MIT'
__copyright__ = 'Copyright 2015 Mac Gaulin'

from .utilities import edgarweb
from .utilities import forms
from .utilities import localstore
from .utilities import plaintext

from .exceptions import (InputTypeError, WrongFormType,
                         NoFormTypeFound, NoCIKFound)


__all__ = [edgarweb, forms, localstore, plaintext,
           InputTypeError, WrongFormType, NoFormTypeFound, NoCIKFound]
