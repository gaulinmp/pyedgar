# pyedgar

Python package for downloading EDGAR documents and data



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


## Requirements

w3m for converting HTML to plaintext (tested on Linux).

Tested only on Python >3.4

HTML parsing tested only on Linux.
Other HTML->text conversion methodologies were tried (html2text, BeautifulSoup, lxml) but w3m was fastest even with the subprocess calling.
Converting multiple HTML files could probably be optimized with one instance of w3m instead of spawning a subprocess for each call.
