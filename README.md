# pyedgar

Python package for downloading EDGAR documents and data


## Usage
There are two primary interfaces to this library, namely indices and filings. 

### index.py
[index.py](pyedgar/index.py) is the main module for accessing extracted EDGAR indices. 
The indices are created in pyedgar.utilities.indices by the IndexMaker class.
Once these indices are created, you can access them by:

```python
from pyedgar.index import EDGARIndex
all_indices = EDGARIndex()
form_10k = all_indices.get_index('form_10-K')

print(form_10k.head(1))
# Output:
#       cik                      name  form    filedate             accession
#    0   20  K TRON INTERNATIONAL INC  10-K  1996-03-28  0000893220-96-000500
```

To get a type of form that isn't automatically extracted, you can use form_all:

```python
df_s1 = EDGARIndex().get_index('form_all').query("form.str.startswith('S-1')")

print(df_s1.head(1))
# Output:
#        cik        name form    filedate             accession
# 5600  1961  WORLDS INC  S-1  2014-02-04  0001264931-14-000033
```

All indices are loaded and saved by pandas, so pandas is a requirement for using this functionality.


### filing.py
[filing.py](pyedgar/filing.py) is the main module for interacting with EDGAR forms.
The forms are loaded lazily, so only when you request the data is the file read from disk.
Filing objects have the following properties:

* ``path``: path to cached filing on disk
* ``urls``: URLs the EDGAR website location for the full text file and the index file
* ``full_text``: Full text of the entire .nc filing (not just the first document)
* ``headers``: Dictionary of all the headers from the full filing (i.e. not the exhibits). E.g. CIK, ACCESSION, PERIOD, etc.
* ``type``: The general type of the document, extracted from the TYPE header and cleaned up (so 10-K405 --> 10-K)
* ``type_exact``: The exact text extracted from the TYPE field
* ``documents``: Array of all the documents (between <DOCUMENT></DOCUMENT> tags). 0th is typically the main form, i.e. the 10-K filing, subsequent documents are exhibits.
    * Each document in this array is itself a dictionary, with fields: TYPE, SEQUENCE, DESCRIPTION (typically the file name), FULL_TEXT. The latter is the text of the exhibit, i.e. just the 10-K filing in text or HTML.

Simple example:

```python
from pyedgar.filing import Filing
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


See the [example config file](pyedgar.conf) for commented config settings.

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

## Requirements

w3m for converting HTML to plaintext (tested on Linux).

Tested only on Python >3.4

HTML parsing tested only on Linux.
Other HTML->text conversion methodologies were tried (html2text, BeautifulSoup, lxml) but w3m was fastest even with the subprocess calling.
Converting multiple HTML files could probably be optimized with one instance of w3m instead of spawning a subprocess for each call.
