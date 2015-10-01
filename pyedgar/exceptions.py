#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
pyedgar.exceptions

This module contains pyEDGAR's exceptions.
"""

class InputTypeError(Exception):
    """Input to method is of wrong type."""

class WrongFormType(Exception):
    """Form provided is of wrong type"""

class NoFormTypeFound(Exception):
    """Form type not found in file (no <FORM-TYPE> tag)"""

class NoCIKFound(Exception):
    """CIK code not found in file (no <CIK> tag)"""

class EDGARFilingFormatError(Exception):
    """File does not appear to be in proper EDGAR SGML format."""
