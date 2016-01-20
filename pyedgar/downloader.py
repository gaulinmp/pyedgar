#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Download a local copy of EDGAR. Allows for permenant caching of downloaded daily zips.

Probably only works on Linux.

EDGAR HTML specification: https://www.sec.gov/info/edgar/ednews/edhtml.htm
EDGAR FTP specification: https://www.sec.gov/edgar/searchedgar/ftpusers.htm

COPYRIGHT: None. I don't get paid for this.
"""

import os
import re
import tarfile
import logging
import datetime as dt
from ftplib import FTP, all_errors

from .exceptions import *
from .utilities import localstore
from .utilities import forms
from .utilities import edgarweb


class FilingPathFormatter(object):
    """Placeholder class so you can throw your own pathing here."""
    def get_filing_filename(self, cik, accession, *args, **kwargs):
        """Take cik, accession, and whatever else data. Return Path to local file."""
        return localstore.get_filing_path(cik, accession)

    def get_feed_filename(self, ident_string=None):
        """
        Return temp path for feed tar file. Could be permanent if caching is on.
        This implementation requires a datetime object input.
        """
        return os.path.join(localstore.FEED_CACHE_ROOT,
                            "sec_daily_{0:%Y-%m-%d}.tar.gz"
                            .format(ident_string))

    def get_index_filename(self, ident_string=None):
        """
        Return temp path for index tar file. Could be permanent if caching is on.
        This implementation requires a datetime object input.
        """
        return os.path.join(localstore.INDEX_ROOT, 'src',
                            "full_index_{0:%Y}_Q{1}.idx"
                            .format(ident_string, edgarweb._get_qtr(ident_string)))


class EDGARDownloader(object):
    """
    Class that downloads EDGAR to your very own computer.
    Everyone should have a local copy after all!
    I have just enough flexibility here for my computer. It works on Linux, YWindowsMMV.
    """
    # These should work for everypeople.
    # EDGAR_ENCODING = 'latin-1' # The SEC documentation says it uses latin-1
    EDGAR_ENCODING = 'utf-8' # But I like utf-8. Because.

    # These should be changed for you. Either in source, or more better at runtime.
    email = None
    keep_regex = None

    # Keep these secret. Keep them safe.
    _path_formatter = None
    _cache_daily_feed = True
    _ftp = None

    __logger = logging.getLogger(__name__)

    def __init__(self,
                 path_formatter=None,
                 cache_daily_feed_tars=True,
                 keep_form_type_regex=None):
        """The initialize class. Documentation is hard."""
        if path_formatter is None:
            self._path_formatter = FilingPathFormatter()
        else:
            self._path_formatter = path_formatter

        self._cache_daily_feed = cache_daily_feed_tars

        if keep_form_type_regex is None:
            # Default to 10s, 8s, 13s, and Def 14As.
            self.keep_regex = re.compile(r'10-[KQ]|8-K|13[FDG]|(?:14A$)')

    def _login(self):
        try:
            self._ftp.close()
        except:
            # Squash all errors!
            pass
        self._ftp = FTP(host='ftp.sec.gov', user='anonymous', passwd=self.email)

    def _handle_nc(self, file_or_str):
        """
        Reads file or string, returns {'cik', 'accession', 'form_type', 'doc'}
        or None on failure.

        Raises WrongFormType if FORM-TYPE SGML tag doesn't match `keep_regex`.
        """
        try:
            txt = file_or_str.read()
        except AttributeError:
            txt = file_or_str

        if not txt:
            raise InputTypeError("No text of file object found")

        txt = txt.decode(self.EDGAR_ENCODING) #uuuuuuuuuuunicode

        ret_val = {'form_type': forms.get_header(txt, "FORM-TYPE"),
                   'cik': forms.get_header(txt, "CIK"),
                   'accession': forms.get_header(txt, 'ACCESSION-NUMBER'),
                   'doc': txt}

        if not ret_val['form_type']:
            raise NoFormTypeFound(ret_val['form_type'])

        if not self.keep_regex.search(ret_val['form_type']):
            raise WrongFormType(ret_val['form_type'])

        if not ret_val['cik']:
            raise NoCIKFound("No CIK found in {}".format(txt[:250]))

        return ret_val

    def download_from_ftp(self, ftp_path, local_target):
        """Download a daily feed tar given a datetime input."""
        if not os.path.exists(os.path.dirname(local_target)):
            raise FileNotFoundError('The directory does not exist: {}'
                                    .format(os.path.dirname(local_target)))

        # If it fails, try, try, try, try again. Then stop; accept failure.
        for retries in range(5):
            try:
                self._ftp.sendcmd("TYPE i")    # Switch to Binary mode
                exp_size = self._ftp.size(ftp_path)  # Get size of file
            except all_errors:                 # file doesn't exist, skip.
                return ''
            except AttributeError:             # self._ftp is None. Login and retry.
                self._login()
                continue

            if os.path.exists(local_target):
                size_ratio = exp_size/(os.path.getsize(local_target) + 1e-12)
                if .99 < size_ratio < 1.01:
                    self.__logger.info("Already downloaded {}".format(local_target))
                    break
                else:
                    self.__logger.info("Found file, but wrong size. FTP:{}, Local:{}. Ratio {}."
                                       .format(exp_size, os.path.getsize(local_target), size_ratio))

            with open(local_target, 'wb') as fh:
                self.__logger.info("Downloading {} to {}".format(ftp_path, local_target))
                try:
                    self._ftp.retrbinary("RETR " + ftp_path, fh.write)
                except IOError:
                    # Soemtimes FTP logs us out or times our or something.
                    # Start again from the top, wot wot.
                    self._login()
                    continue
                else:
                    break
        return local_target

    def download_daily_feed(self, dl_date):
        """Download a daily feed tar given a datetime input."""
        sec_path = edgarweb.get_feed_ftp_path(dl_date)
        tmp_filename = self._path_formatter.get_feed_filename(dl_date)

        return self.download_from_ftp(sec_path, tmp_filename)

    def download_daily_index(self, dl_date):
        """Download a daily feed tar given a datetime input."""
        # For now, get the IDX file, not the zipped file. Because laziness and edu internet.
        sec_path = edgarweb.get_idx_ftp_path(dl_date)
        tmp_filename = self._path_formatter.get_index_filename(dl_date)

        return self.download_from_ftp(sec_path, tmp_filename)

    def iter_daily_feeds(self, from_date, to_date=None):
        """
        Generator that yields (dt.date, downloaded daily feed tar file path)
        """
        if to_date is None:
            to_date = dt.date.today()

        for i_date in range(from_date.toordinal(), to_date.toordinal()):
            i_date = dt.date.fromordinal(i_date-1)

            # Actually get the file. This downloads it, or passes the filepath to the cached file.
            yield i_date, self.download_daily_feed(i_date)

    def extract_daily_feeds(self, from_date, to_date=None):
        """
        """
        for i_date, feed_path in self.iter_daily_feeds(from_date, to_date=to_date):
            if not feed_path:
                # This day doesn't exist on EDGAR. Not sure why servers can't work on weekends.
                continue

            if not os.path.exists(feed_path):
                self.__logger.error("Failed to download {} file to {}."
                                    .format(i_date, feed_path))
                continue

            self.__logger.debug("Done with {:%Y-%m-%d}, size is {:4.2f} MB"
                                .format(i_date, os.path.getsize(feed_path)/1024**2))

            with tarfile.open(feed_path, 'r') as tar:
                i_done, i_tot = 0, 0
                for tarinfo in tar:
                    if len(tarinfo.name) < 3:
                        continue
                    i_tot += 1
                    try:
                        nc_file = tar.extractfile(tarinfo)
                    except IOError:
                        continue
                    try:
                        nc_dict = self._handle_nc(nc_file)
                    except InputTypeError:
                        self.__logger.warning("Not a file or string at {} on {}"
                                              .format(tarinfo.name, i_date))
                        continue
                    except NoCIKFound:
                        if ".corr" not in tarinfo.name:
                            self.__logger.warning("No CIK found at {} on {}"
                                                  .format(tarinfo.name, i_date))
                        continue
                    except NoFormTypeFound:
                        if ".corr" not in tarinfo.name:
                            self.__logger.warning("No FormType found at {} on {}"
                                                  .format(tarinfo.name, i_date))
                        continue
                    except WrongFormType:
                        continue
                    if not nc_dict:
                        self.__logger.error("Handling nc file {} on {} passed exceptions"
                                            .format(tarinfo.name, i_date))
                        continue
                    # Get local nc file path. Accession is nc file filename.
                    nc_out_path = self._path_formatter.get_filing_filename(nc_dict['cik'],
                                                                           tarinfo.name)
                    i_done += 1
                    if os.path.exists(nc_out_path):
                        continue
                    if not os.path.exists(os.path.dirname(nc_out_path)):
                        os.makedirs(os.path.dirname(nc_out_path))
                    with open(nc_out_path, 'w', encoding=self.EDGAR_ENCODING) as fh:
                        fh.write(nc_dict['doc'])

            # Log progress on the first of the month.
            if i_date.isoweekday() == 1:
                self.__logger.info("Finished adding {} out of {} from {}"
                .format(i_done, i_tot, i_date))

            if not self._cache_daily_feed:
                try: # cleanup after 14 days
                    os.remove(feed_path)
                except:
                    pass

# Example running script. This will download past 3 months of forms and all indices.
if __name__ == '__main__':
    import pandas as pd
    foo = EDGARDownloader()
    foo.email = 'mpg@rice.edu'

    print("Downloading and extracting the last three months...", end='')
    foo.extract_daily_feeds(dt.date.fromordinal(dt.date.today().toordinal()-90))
    print(" Done!")

    print("Downloading the quarterly indices...", end='')
    df = pd.DataFrame()
    for y in range(1995, dt.date.today().year + 1):
        for q in range(4):
            d = dt.date(y, 1+q*3, 1)
            f = foo.download_daily_index(d)
            if not f:
                continue
            dfi = pd.read_csv(f, sep='|', skiprows=[0,1,2,3,4,5,6,7,9], encoding='latin-1')
            dfi['Accession'] = dfi.Filename.apply(lambda x: x.split('/')[-1][:-4])
            del dfi['Filename']

            df = pd.concat([df, dfi], copy=False)

    df['Date Filed'] = pd.to_datetime(df['Date Filed'])
    df.to_csv(os.path.join(localstore.INDEX_ROOT, 'all_filings.tab'), sep='\t', index=False)
    save_forms = {
        '10-K': [x for x in all_forms if '10-K' in x and '405' not in x and 'NT' not in x],
        '10-Q': [x for x in all_forms if '10-Q' in x and 'NT' not in x],
        'DEF14A':  [x for x in all_forms if x.endswith('14A')],
        '8-K': '8-K 8-K/A'.split(),
    }
    for form,formlist in save_forms.items():
        (df[df['Form Type'].isin(formlist)]
           .to_csv(os.path.join(localstore.INDEX_ROOT, 'form_{}.tab'.format(form)),
                   sep='\t', index=False))
    print(" Done!")
