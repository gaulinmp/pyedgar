# pyedgar

Python package for downloading EDGAR documents and data


## Usage
There are two primary interfaces to this library, namely filings and indices.



### filing.py
[filing.py](pyedgar/filing.py) is the main module for interacting with EDGAR forms.

Simple example:

```python
from pyedgar import Filing
f = Filing(20, '0000893220-96-000500')

print(f)
#output: <EDGAR filing (20/0000893220-96-000500) Headers:False, Text:False, Documents:False>

print(f.type, f)
# output: 10-K <EDGAR filing (20/0000893220-96-000500) Headers:True, Text:True, Documents:False>

print(f.documents[0]['full_text'][:800])
# Output:
#                         SECURITIES AND EXCHANGE COMMISSION
#                               WASHINGTON, D.C. 20549
#
#                                     FORM 10-K
#
#  (Mark One)
#  /X/  Annual report pursuant to section 13 or 15(d) of the Securities Exchange
#       Act of 1934 [Fee Required] for the fiscal year ended December 30, 1995 or
#
#  / / Transition report pursuant to section 13 or 15(d) of the Securities
#      Exchange Act of 1934 [No Fee Required] for the transition period from
#      ________ to ________
#
#  COMMISSION FILE NUMBER 0-9576
#
#
#                             K-TRON INTERNATIONAL, INC.
#               (EXACT NAME OF REGISTRANT AS SPECIFIED IN ITS CHARTER)
#
#                 New Jersey                                22-1759452
#     (State or other jurisdiction of         (I.R.S. Employer Identification No.)
```

The forms are loaded lazily, so only when you request the data is the file read from disk or downloaded from the EDGAR website.
Filing objects have the following properties:

* ``path``: path to cached filing on disk
* ``urls``: URLs the EDGAR website location for the full text file and the index file
* ``full_text``: Full text of the entire .nc filing (not just the first document)
* ``headers``: Dictionary of all the headers from the full filing (i.e. not the exhibits). E.g. CIK, ACCESSION, PERIOD, etc.
* ``type``: The general type of the document, extracted from the TYPE header and cleaned up (so 10-K405 --> 10-K)
* ``type_exact``: The exact text extracted from the TYPE field
* ``documents``: Array of all the documents (between <DOCUMENT></DOCUMENT> tags). 0th is typically the main form, i.e. the 10-K filing, subsequent documents are exhibits.
    * Each document in this array is itself a dictionary, with fields: TYPE, SEQUENCE, DESCRIPTION (typically the file name), FULL_TEXT. The latter is the text of the exhibit, i.e. just the 10-K filing in text or HTML.


### index.py
[index.py](pyedgar/index.py) is the main module for accessing extracted EDGAR indices.
The indices are created in [pyedgar.utilities.indices](pyedgar/utilities/indices.py#L34) by the IndexMaker class.
Once these indices are created (which you can do by setting ``force_download=True``), you can view them via the ``indices`` property:

```python
from pyedgar import EDGARIndex
all_indices = EDGARIndex(force_download=False)

print(all_indices.indices)
# Output:
# {'form_all.tab': '/data/storage/edgar/indices/form_all.tab',
#  'form_10-Q.tab': '/data/storage/edgar/indices/form_10-Q.tab',
#  'form_13s.tab': '/data/storage/edgar/indices/form_13s.tab',
#  'form_DEF14A.tab': '/data/storage/edgar/indices/form_DEF14A.tab',
#  'form_8-K.tab': '/data/storage/edgar/indices/form_8-K.tab',
#  'form_20-F.tab': '/data/storage/edgar/indices/form_20-F.tab',
#  'form_10-K.tab': '/data/storage/edgar/indices/form_10-K.tab'}
```

These indices are accessible as a pandas dataframe via [] or the ``get_index`` method, where the index is selected via the key above (with or without the form_ or .tab).

```python
form_10k = all_indices['10-K']

print(form_10k.head(1))
# Output:
#       cik                      name  form    filedate             accession
#    0   20  K TRON INTERNATIONAL INC  10-K  1996-03-28  0000893220-96-000500
```

To get a type of form that isn't automatically extracted, you can use form_all:

```python
df_s1 = EDGARIndex().get_index('all').query("form.str.startswith('S-1')")

print(df_s1.head(1))
# Output:
#        cik        name form    filedate             accession
# 5600  1961  WORLDS INC  S-1  2014-02-04  0001264931-14-000033
```

All indices are loaded and saved by pandas, so pandas is a requirement for using this functionality.



## Config

Config files named ``pyedgar.conf``, ``.pyedgar``, ``pyedgar.ini`` are searched for at (in order):

1. ``os.environ.get("PYEDGAR_CONF", '.')`` <-- PYEDGAR_CONF environmental variable
2. ``./``
3. ``~/.config/pyedgar``
4. ``~/AppData/Local/pyedgar``
5. ``~/AppData/Roaming/pyedgar``
6. ``~/Library/Preferences/pyedgar``
7. ``~/.config/``
8. ``~/``
9. ``~/Documents/``
10. ``os.path.abspath(os.path.dirname(__file__))`` <-- directory of the package. Default package ships with this existing.


See the [example config file](pyedgar/pyedgar.conf) for commented config settings.

Running multiple configs is quite easy, by setting ``os.environ`` manually:

```python

import os
# os.environ['PYEDGAR_CONF'] = os.path.expanduser('~/Dropbox/config/pyedgar/hades.local.pyedgar.conf')
os.environ['PYEDGAR_CONF'] = os.path.expanduser('~/Dropbox/config/pyedgar/hades.desb.pyedgar.conf')

from pyedgar import config
print(config.CONFIG_FILE)

# Output:
#     WARNING:pyedgar.config:Loaded config file from '[~]/Dropbox/config/pyedgar/hades.desb.pyedgar.conf'.
#     ALERT!!!! FILING_PATH_FORMAT is '{accession[11:13]}/{accession}.nc'.
#     [~]/Dropbox/config/pyedgar/hades.desb.pyedgar.conf
```

## Install

Pip installable:

```bash
pip install pyedgar
```

Or pip installable from github:

```bash
pip install git+https://github.com/gaulinmp/pyedgar#egg=pyedgar
```

or by checking out from github and installing in editable mode:

```bash
git clone https://github.com/gaulinmp/pyedgar
cd pyedgar
pip install -e ./
```

## Requirements

w3m for converting HTML to plaintext (tested on Linux).
A fallback method might one day be added.

Tested only on Python >3.4

HTML parsing tested only on Linux.
Other HTML->text conversion methodologies were tried (html2text, BeautifulSoup, lxml) but w3m was fastest even with the subprocess calling.
Converting multiple HTML files could probably be optimized with one instance of w3m instead of spawning a subprocess for each call.
But that's for future Mac to work on.
