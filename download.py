# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2014, Alex Kosloff <pisatel197@gmail.com>'
__docformat__ = 'restructuredtext en'

import os
import shutil
from contextlib import closing
from mechanize import MozillaCookieJar
import json
import mimetypes

from calibre import browser, get_download_filename, url_slash_cleaner
from calibre.ebooks import BOOK_EXTENSIONS
from calibre.gui2 import Dispatcher
from calibre.gui2.threaded_jobs import ThreadedJob
from calibre.ptempfile import PersistentTemporaryFile
from calibre.utils.filenames import ascii_filename

from calibre_plugins.casanova_plugin.config import prefs


class CasanovaDownload(object):

    def __call__(self, gui, url='', filename='', save_loc='', id=False, log=None, abort=None, notifications=None):
        dfilename = ''
        try:
            dfilename = self._download(url, filename, save_loc)
            self._add(dfilename, gui, id)
            #self._save_as(dfilename, save_loc) # commented out because double files were being stored
        except Exception as e:
            raise e
        finally:
            try:
                if dfilename:
                    os.remove(dfilename)
            except:
                pass

    def _download(self, url, filename, save_loc):
        dfilename = ''

        if not url:
            raise Exception(_('No file specified to download.'))
        if not save_loc:
            # Nothing to do.
            return dfilename

        if not filename:
            filename = get_download_filename(url)
            filename, ext = os.path.splitext(filename)
            filename = filename[:60] + ext
            filename = ascii_filename(filename)

        br = browser()
        with closing(br.open(url)) as r:
            tf = PersistentTemporaryFile(suffix=filename)
            tf.write(r.read())
            dfilename = tf.name

        return dfilename

    def _add(self, filename, gui, id):
        if not filename:
            return
        ext = os.path.splitext(filename)[1][1:].lower()
        if ext not in BOOK_EXTENSIONS:
            raise Exception(_('Not a support ebook format.'))

        from calibre.ebooks.metadata.meta import get_metadata
        with open(filename, 'rb') as f:
            gui.library_view.model().db.add_format(id, ext.upper(), f, index_is_id=True)
            gui.library_view.model().books_added(1)
            gui.library_view.model().count_changed()

    def _save_as(self, dfilename, save_loc):
        if not save_loc or not dfilename:
            return
        shutil.copy(dfilename, save_loc)


gui_casanova_download = CasanovaDownload()

def start_casanova_download(callback, job_manager, gui, url='', filename='', save_loc='', id=False):
    description = _('Downloading %s') % filename.decode('utf-8', 'ignore') if filename else url.decode('utf-8', 'ignore')
    job = ThreadedJob('casanova_download', description, gui_casanova_download, (gui, url, filename, save_loc, id), {}, callback, max_concurrent_count=2, killable=False)
    job_manager.run_threaded_job(job)


class CasanovaDownloadManager(object):

    def __init__(self, gui, mm):
        print('New Casanova download manager created')
        self.gui = gui
        self.mm = mm
        self.db = gui.current_db
        self.base_url = prefs['base_url']

    def download_ebook(self, book_id, di=None):
        # Get the current metadata for this book from the db
        mi = self.db.get_metadata(book_id, index_is_id=True,
                get_cover=True, cover_as_data=True)
        
        # get save directory & filename
        try:
            path_to_book = self.gui.library_view.model().db.abspath(mi.id, True)
            book_file_name = self.gui.library_view.model().db.construct_file_name(mi.id)
        except  Exception as e:
            print('Failed to get path and filename from book metadata')
            raise e
        
        if not di:        
            try:
                # @todo: fix this line to get the base id part
                casanova_id = mi.identifiers['casanova']
            except AttributeError:
                print('There is no aaaarg attribute for this book')                
            # download detail from site
            di = self.get_first_download_info(casanova_id)
        if di:
            book_file_name = book_file_name + di['type']
            start_casanova_download(Dispatcher(self.downloaded_ebook), self.gui.job_manager, self.gui, di['href'], book_file_name, path_to_book, mi.id)
            self.gui.status_bar.show_message(_('Downloading') + ' ' + book_file_name.decode('utf-8', 'ignore') if book_file_name else url.decode('utf-8', 'ignore'), 3000)


    def downloaded_ebook(self, job):
        if job.failed:
            self.gui.job_exception(job, dialog_title=_('Failed to download ebook'))
            return

        self.gui.status_bar.show_message(job.description + ' ' + _('finished'), 5000)

    def get_download_info(self, id):
        return self.mm.get_remote_formats(id)

    def get_first_download_info(self, id, timeout=60):
        ''' Retrieves information about where the actual file is located to download '''
        formats = self.mm.get_remote_formats(id)
        if formats is None or len(formats)==0:
            return False
        else:
            return formats[0]