#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Download a local copy of EDGAR. Allows for permenant caching of downloaded daily zips.

Probably only works on Linux.

EDGAR HTML specification: https://www.sec.gov/info/edgar/ednews/edhtml.htm
EDGAR FTP specification: https://www.sec.gov/edgar/searchedgar/ftpusers.htm

URL Change in 2016:
  <2016 ftp URL: ftp://ftp.sec.gov/edgar/data/2098/0000002098-96-000003.txt
  >2016 http URL: https://www.sec.gov/Archives/edgar/data/2098/0000002098-96-000003.txt

:copyright: © 2019 by Mac Gaulin
:license: MIT, see LICENSE for more details.
"""

import os
# import sys
# import re
import tarfile
import logging
import datetime as dt
import requests

try:
    from tqdm import tqdm
except ModuleNotFoundError:
    def tqdm(x, *args, **kwargs):
        return x

from pyedgar import config
from pyedgar.exceptions import (InputTypeError, WrongFormType,
                                NoFormTypeFound, NoCIKFound)
from pyedgar.utilities import localstore
from pyedgar.utilities import forms
from pyedgar.utilities import edgarweb


class FilingPathFormatter(object):
    """Placeholder class so you can throw your own pathing here."""
    def get_filing_filename(self, cik, accession, *args, **kwargs):
        """Take cik, accession, and whatever else data. Return Path to local file."""
        return localstore.get_filing_path(cik=cik, accession=accession, **kwargs)

    def get_feed_filename(self, datetime_in=None):
        """
        Return temp path for feed tar file. Could be permanent if caching is on.
        This implementation requires a datetime object input.
        """
        return os.path.join(config.FEED_CACHE_ROOT,
                            "sec_daily_{0:%Y-%m-%d}.tar.gz"
                            .format(datetime_in))

    def get_index_filename(self, datetime_in=None, compressed=False):
        """
        Return temp path for index tar file. Could be permanent if caching is on.
        This implementation requires a datetime object input.
        """
        return os.path.join(config.INDEX_CACHE_ROOT, 'src',
                            "full_index_{0:%Y}_Q{1}.{2}"
                            .format(datetime_in,
                                    edgarweb._get_qtr(datetime_in),
                                    'gz' if compressed else 'idx'))


class EDGARDownloader(object):
    """
    Class that downloads EDGAR to your very own computer.
    Everyone should have a local copy after all!
    I have just enough flexibility here for my computer. It works on Linux, YWindowsMMV.
    """
    # These should work for everypeople.
    EDGAR_ENCODING = 'latin-1' # The SEC documentation says it uses latin-1
    # EDGAR_ENCODING = 'utf-8' # Alternatively one could use utf-8.

    # These should be changed for you. Either in source, or more better at runtime.
    email = None
    keep_regex = None
    check_cik = False

    # Keep these secret. Keep them safe.
    _path_formatter = None
    _cache_daily_feed = True

    _logger = logging.getLogger(__name__)

    def __init__(self,
                 path_formatter=None,
                 cache_daily_feed_tars=True,
                 keep_form_type_regex=None,
                 check_cik=False):
        """The initialize class. Documentation is hard."""
        if path_formatter is None:
            self._path_formatter = FilingPathFormatter()
        else:
            self._path_formatter = path_formatter

        self._cache_daily_feed = cache_daily_feed_tars

        self.check_cik = check_cik
        self.keep_regex = keep_form_type_regex
        # Use the following to default to 10s, 20s, 8s, 13s, and Def 14As.
        # if keep_form_type_regex is None:
        #    re.compile(r'10-[KQ]|10[KQ]SB|20-F|8-K|13[FDG]|(?:14A$)')

    def _handle_nc(self, file_or_str):
        """
        Reads file or string, returns dictionary based on flags or None on failure.
        At a minimum, it returns: {'doc'}

        If keep_regex is set (not None), it adds 'form_type'.
            (Raises WrongFormType if FORM-TYPE SGML tag doesn't match `keep_regex`.)

        If check_cik is True, it extracts and adds 'cik'.
        """
        try:
            txt = file_or_str.read()
        except AttributeError:
            txt = file_or_str

        if not txt:
            raise InputTypeError("No text of file object found")

        try:
            txt = txt.decode(self.EDGAR_ENCODING) #uuuuuuuuuuunicode
        except UnicodeDecodeError:
            self._logger.error("UNICODE ERROR: %r", txt[:1000])
            txt = txt.decode(self.EDGAR_ENCODING, errors='ignore') #uuuuuuuuuuunicode

        ret_val = {'doc': txt}

        if self.keep_regex is not None:
            ret_val['form_type'] = forms.get_header(txt, "FORM-TYPE")

            if not ret_val['form_type']:
                raise NoFormTypeFound(ret_val['form_type'])

            if not self.keep_regex.search(ret_val['form_type']):
                raise WrongFormType(ret_val['form_type'])

        if self.check_cik:
            ret_val['cik'] = forms.get_header(txt, "CIK")
            ret_val['accession'] = forms.get_header(txt, 'ACCESSION-NUMBER')

            if not ret_val['cik']:
                raise NoCIKFound("No CIK found in {}".format(txt[:250]))

        return ret_val

    def download_tar(self, remote_path, local_target, chunk_size=1024**2):
        """Download a file from `remote_path` to `local_target`."""
        from_addr = ('https://www.sec.gov/Archives{remote_path}'
                     .format(remote_path=remote_path))

        # Verify destination directory exists
        if not os.path.exists(os.path.dirname(local_target)):
            raise FileNotFoundError('The directory does not exist: {}'
                                    .format(os.path.dirname(local_target)))

        # If it fails, try, try, try, try again. Then stop; accept failure.
        for n_retries in range(5):
            self._logger.info(("Downloading {n_retries} of 5: "
                               "{remote_path} to {local_target}")
                              .format(n_retries=n_retries,
                                      remote_path=remote_path,
                                      local_target=local_target))

            # Check for local copy and determine length (for caching/resuming)
            try:
                loc_size = os.path.getsize(local_target)
                headers = {'Range': 'bytes={loc_size}-'.format(loc_size=loc_size)}
                # Resume with header: Range: bytes=StartPos- (implicit end pos)
            except FileNotFoundError:
                loc_size = 0
                headers = None

            # Check total file length on server
            with requests.get(from_addr, stream=True) as response:
                if response.status_code // 100 == 4:
                    # No such file
                    return None
                expected_tot_len = int(response.headers['content-length'])

            # If local length matches, we are done. Return local path
            if expected_tot_len == loc_size:
                self._logger.info(("Already downloaded ({loc_size:,d}=={expected_tot_len:,d}) "
                                   "from {remote_path} to {local_target}")
                                  .format(loc_size=loc_size,
                                          expected_tot_len=expected_tot_len,
                                          remote_path=remote_path,
                                          local_target=local_target))
                break

            # If local length matches, we are done. Return local path
            if loc_size > expected_tot_len:
                self._logger.info(("Downloaded too much ({loc_size:,d} > {expected_tot_len:,d}) "
                                   "from {remote_path}, removing {local_target}")
                                  .format(loc_size=loc_size,
                                          expected_tot_len=expected_tot_len,
                                          remote_path=remote_path,
                                          local_target=local_target))
                os.remove(local_target)
                continue

            # Download or resume
            with requests.get(from_addr, headers=headers, stream=True) as response:
                expected_len = int(response.headers['content-length'])

                if loc_size:
                    self._logger.info(("Already downloaded ({loc_size}/"
                                        "{expected_tot_len}, remaining:"
                                        "{expected_len}) from {remote_path} "
                                        "to {local_target}")
                                        .format(loc_size=loc_size,
                                                expected_tot_len=expected_tot_len,
                                                expected_len=expected_len,
                                                remote_path=remote_path,
                                                local_target=local_target))

                with open(local_target, 'ab' if loc_size else 'wb') as fh:
                    self._logger.info("Saving tar {} to {}"
                                      .format(remote_path, local_target))

                    for chunk in tqdm(response.iter_content(chunk_size=chunk_size),
                                      total=expected_len//chunk_size,
                                      unit="Mb",
                                      desc=os.path.basename(local_target)):
                        if chunk:  # filter out keep-alive new chunks
                            fh.write(chunk)

                    self._logger.info("Done saving (len: {}) {}"
                                      .format(os.path.getsize(local_target),
                                              local_target))

                    break  # Done downloading, break out of range(5)

        return local_target

    def download_plaintext(self, remote_path, local_target,
                           chunk_size=1024**2, overwrite=False):
        """Download a plaintext file from `remote_path` to `local_target`."""
        from_addr = ('https://www.sec.gov/Archives{remote_path}'
                     .format(remote_path=remote_path))

        # Return if exists. Delete if it is partial?
        if os.path.exists(local_target) and not overwrite:
            return local_target

        # Verify destination directory exists
        if not os.path.exists(os.path.dirname(local_target)):
            raise FileNotFoundError('The directory does not exist: {}'
                                    .format(os.path.dirname(local_target)))

        self._logger.info(("Downloading plaintext: "
                            "{remote_path} to {local_target}")
                            .format(remote_path=remote_path,
                                    local_target=local_target))

        # Check total file length on server
        with requests.get(from_addr, stream=True) as response:
            if response.status_code // 100 == 4:
                # No such file
                return None
            expected_tot_len = int(response.headers.get('content-length', 10 * 1024**2))

            with open(local_target, 'wb') as fh:
                self._logger.info("Saving plaintext {} to {}"
                                    .format(remote_path, local_target))

                for chunk in tqdm(response.iter_content(chunk_size=chunk_size),
                                    total=expected_tot_len//chunk_size,
                                    unit="Mb",
                                    desc=os.path.basename(local_target)):
                    if chunk:  # filter out keep-alive new chunks
                        fh.write(chunk)

                self._logger.info("Done saving (len: {}) {}"
                                    .format(os.path.getsize(local_target),
                                            local_target))

        return local_target

    def download_daily_feed(self, dl_date):
        """Download a daily feed tar given a datetime input."""
        sec_path = edgarweb.get_feed_path(dl_date)
        tmp_filename = self._path_formatter.get_feed_filename(dl_date)

        return self.download_tar(sec_path, tmp_filename)

    def download_daily_index(self, dl_date, compressed=False, overwrite=False):
        """Download a quarterly index given a datetime input."""
        # For now, get the IDX file, not the zipped file. Because laziness and edu internet.
        sec_path = edgarweb.get_idx_path(dl_date, tar=compressed)
        tmp_filename = self._path_formatter.get_index_filename(dl_date, compressed=compressed)

        if overwrite:
            try:
                os.remove(tmp_filename)
            except:
                pass

        if compressed:
            return self.download_tar(sec_path, tmp_filename)

        return self.download_plaintext(sec_path, tmp_filename)

    def iter_daily_feeds(self, from_date, to_date=None):
        """
        Generator that yields (dt.date, downloaded daily feed tar file path)
        """
        if to_date is None:
            to_date = dt.date.today()

        for i_date in range(from_date.toordinal(), to_date.toordinal()):
            i_date = dt.date.fromordinal(i_date)

            # Actually get the file. This downloads it, or passes the filepath to the cached file.
            yield i_date, self.download_daily_feed(i_date)

    def extract_daily_feeds(self, from_date, to_date=None):
        """
        Loop through daily feed compressed files and extract them to local cache.
        Uses the object's path formatter to determine file paths.
        """
        for i_date, feed_path in self.iter_daily_feeds(from_date, to_date=to_date):
            if not feed_path:
                # This day doesn't exist on EDGAR.
                # Not sure why servers can't work on weekends.
                continue

            if not os.path.exists(feed_path):
                self._logger.error("Failed to download {} file to {}."
                                    .format(i_date, feed_path))
                continue

            self._logger.debug("Done with {:%Y-%m-%d}, size is {:4.2f} MB"
                                .format(i_date, os.path.getsize(feed_path)/1024**2))

            with tarfile.open(feed_path, 'r') as tar:
                i_done, i_tot = 0, 0
                try:
                    for tarinfo in tar:
                        if len(tarinfo.name) < 3 or '.corr' in tarinfo.name or not tarinfo.name.endswith('.nc'):
                            continue
                        i_tot += 1
                        nc_acc = tarinfo.name.split('/')[-1][:-3]
                        if len(nc_acc) != 20:
                            self._logger.warning("Accession in filename seems suspect. %r", nc_acc)
                        try:
                            nc_file = tar.extractfile(tarinfo)
                        except IOError:
                            continue

                        # At this point, we have a file, and we have an accession.
                        # This should be all we need to save it off.
                        try:
                            nc_dict = self._handle_nc(nc_file)
                        except InputTypeError:
                            self._logger.warning("Not a file or string at {} on {} ({}/{} extracted)"
                                                 .format(tarinfo.name, i_date, i_done, i_tot))
                            continue
                        except NoCIKFound:
                            # This only triggers if self.check_cik is set.
                            if ".corr" not in tarinfo.name:
                                self._logger.warning("No CIK found at {} on {} ({}/{} extracted)"
                                                     .format(tarinfo.name, i_date, i_done, i_tot))
                            continue
                        except NoFormTypeFound:
                            # This only triggers if self.keep_regex is set.
                            if ".corr" not in tarinfo.name:
                                self._logger.warning("No FormType found at {} on {} ({}/{} extracted)"
                                                     .format(tarinfo.name, i_date, i_done, i_tot))
                            continue
                        except WrongFormType:
                            # This only triggers if self.keep_regex is set.
                            continue
                        if not nc_dict:
                            self._logger.error("Handling nc file {} on {} passed exceptions ({}/{} extracted)"
                                               .format(tarinfo.name, i_date, i_done, i_tot))
                            continue
                        # Get local nc file path. Accession is nc file filename.
                        nc_out_path = self._path_formatter.get_filing_filename(1, nc_acc)
                        i_done += 1
                        if os.path.exists(nc_out_path):
                            continue

                        # Sometimes the containing dir (cik or year) doesn't exist. Make it so.
                        if not os.path.exists(os.path.dirname(nc_out_path)):
                            os.makedirs(os.path.dirname(nc_out_path))

                        with open(nc_out_path, 'w', encoding=self.EDGAR_ENCODING) as fh:
                            fh.write(nc_dict['doc'])

                except tarfile.ReadError:
                    self._logger.error("Handling nc file {} raised Read Error ({}/{} extracted)"
                                       .format(tarinfo.name, i_done, i_tot))
            # Log progress after each tar file is done
            self._logger.info("Finished adding {} out of {} from {}\n"
                              .format(i_done, i_tot, i_date))

            if not self._cache_daily_feed:
                try:
                    os.remove(feed_path)
                except:
                    pass

# Example running script. This will download past 30 days of forms and all indices.
# run with ```python -m pyedgar.downloader --help```
def main(start_date=None, get_indices=True, get_feeds=True, extract_feeds=True):
    import pandas as pd

    foo = EDGARDownloader()
    foo._logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    foo._logger.addHandler(ch)

    if start_date is None:
        start_date = dt.date.fromordinal(dt.date.today().toordinal()-30)

    if get_feeds:
        print("Downloading and extracting since {:%Y-%m-%d}...".format(start_date))
        if extract_feeds:
            foo.extract_daily_feeds(start_date)
        else:
            for i_date, feed_path in foo.iter_daily_feeds(start_date):
                if not feed_path:
                    # This day doesn't exist on EDGAR.
                    # Not sure why servers can't work on weekends.
                    continue

                if not os.path.exists(feed_path):
                    foo._logger.error("Failed to download {} file to {}."
                                       .format(i_date, feed_path))
                    continue
                print("Done downloading {}".format(feed_path))

        print(" Done!")

    if not get_indices:
        return

    print("Downloading the quarterly indices...")
    df = pd.DataFrame()
    for y in range(1995, dt.date.today().year + 1):
        for q in range(4):
            d = dt.date(y, 1+q*3, 1)
            f = foo.download_daily_index(d, compressed=True)
            if not f:
                continue
            try:
                dfi = pd.read_csv(f, sep='|', encoding='latin-1',
                                skiprows=[0, 1, 2, 3, 4, 5, 6, 7, 8, 10])
            except OSError:
                dfi = pd.read_csv(foo.download_daily_index(d, compressed=True, overwrite=True),
                                  sep='|', encoding='latin-1',
                                  skiprows=[0, 1, 2, 3, 4, 5, 6, 7, 8, 10])
            dfi['Accession'] = dfi.Filename.apply(lambda x: x.split('/')[-1][:-4])
            del dfi['Filename']

            df = pd.concat([df, dfi], copy=False)

    df['Date Filed'] = pd.to_datetime(df['Date Filed'])
    df.to_csv(os.path.join(config.INDEX_ROOT, 'all_filings.tab'), sep='\t', index=False)
    all_forms = df['Form Type'].unique()
    save_forms = {
        '10-K':   [x for x in all_forms if x[:4] == '10-K' or x[:5] == '10KSB'],
        '10-Q':   [x for x in all_forms if x[:4] == '10-Q'],
        'DEF14A': [x for x in all_forms if x.endswith('14A')],
        '13s':    [x for x in all_forms if 'SC 13' in x or '13F-' in x],
        '8-K': '8-K 8-K/A'.split(),
        '20-F':   [x for x in all_forms if x[:4] == '20-F'],
    }
    for form,formlist in save_forms.items():
        (df[df['Form Type'].isin(formlist)]
           .sort_values(['CIK','Date Filed'])
           .to_csv(os.path.join(config.INDEX_ROOT, 'form_{}.tab'.format(form)),
                   sep='\t', index=False))
    print(" Done!")


if __name__ == '__main__':
    from argparse import ArgumentParser

    argp = ArgumentParser(description='Downloader for pyedgar, downloads past'
                                      ' 30 days (or since DATE) of forms and'
                                      ' all indices (unless -f or -i flags'
                                      ' respectively are set).')

    argp.add_argument('-d', '--start-date', nargs='?', default=None,
                      dest='start_date', metavar='YYYY-MM-DD',
                      type=lambda s: dt.datetime.strptime(s, "%Y-%m-%d"),
                      help='An optional date of form YYYY-MM-DD to start '
                           'downloading indices from')

    argp.add_argument('-i', '--no-indices', action='store_false', dest='get_indices',
                      help='Do not download and update indices.')
    argp.add_argument('-f', '--no-feeds', action='store_false', dest='get_feeds',
                      help='Do not download or extract daily feed feeds.')
    argp.add_argument('-e', '--no-extract', action='store_false', dest='extract_feeds',
                      help='Do not extract daily feed feeds.')

    cl_args = argp.parse_args()

    main(start_date=cl_args.start_date,
         get_indices=cl_args.get_indices,
         get_feeds=cl_args.get_feeds,
         extract_feeds=cl_args.extract_feeds)
