# -*- coding: utf-8 -*-
"""
General python utility functions.

:copyright: © 2018 by Mac Gaulin
:license: MIT, see LICENSE for more details.
"""

# STDlib imports
import json
import logging

# 3rd party imports

# current module imports


def addlogger(cls):
    """
    Decorator to add __log to class object.

    Example:
    --------------------------------------------

    @addlogger
    class foo(object):
        def bar(self):
            self.__log.debug("We're in bar")
    """
    aname = '_{}__log'.format(cls.__name__)
    setattr(cls, aname, logging.getLogger(cls.__module__ + '.' + cls.__name__))
    return cls
