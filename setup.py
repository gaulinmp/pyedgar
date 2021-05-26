"""PyEDGAR is a python based package to interact with and download EDGAR filings.

Supports local caching of EDGAR database with the downloader module.
"""

import os
import re
from codecs import open

# Always prefer setuptools over distutils
from setuptools import setup, find_packages
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

here = os.path.abspath(os.path.dirname(__file__))

# Get the long description from the README file
with open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

# Get the version from pyedgar/__init__.py
_version_re = re.compile(r'^__version__\s*=\s*[\'"](.*)[\'"]\s*$', re.M)

with open('pyedgar/__init__.py', 'r') as fh:
    version = _version_re.search(fh.read()).group(1).strip()

setup(
    name='pyedgar',
    version=version,
    description='Python interface to EDGAR filings.',
    long_description=long_description,
    long_description_content_type='text/markdown',
    keywords='SEC EDGAR filings',
    url='https://github.com/gaulinmp/pyedgar',
    author='Mac Gaulin',
    author_email='gaulinmp+pyedgar@gmail.com',
    license='MIT',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Operating System :: OS Independent',
        'Intended Audience :: Science/Research',
        'Intended Audience :: Education',
        'Topic :: Office/Business :: Financial :: Accounting',
        'Natural Language :: English',
        'License :: OSI Approved :: MIT License',

        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],
    packages=find_packages(),
    include_package_data=True,
    install_requires=['pandas', 'requests'],
    extras_require={
        'dev': ['bs4', 'tqdm'],
        # 'test': ['coverage'],
    },
)
