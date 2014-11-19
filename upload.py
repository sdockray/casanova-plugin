# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2014, Alex Kosloff <pisatel1976@gmail.com>'
__docformat__ = 'restructuredtext en'

import os
import shutil
from contextlib import closing
from mechanize import MozillaCookieJar
import json
import mimetypes
import urllib
import urllib2
import StringIO
from base64 import b64encode

from calibre import browser, get_download_filename, url_slash_cleaner
from calibre.ebooks import BOOK_EXTENSIONS
from calibre.gui2 import Dispatcher, info_dialog, error_dialog
from calibre.gui2.threaded_jobs import ThreadedJob
from calibre.ptempfile import PersistentTemporaryFile
from calibre.utils.filenames import ascii_filename

from calibre.ebooks.metadata import author_to_author_sort
from calibre.ebooks.metadata.opf2 import OPF, metadata_to_opf

from calibre_plugins.casanova_plugin.config import prefs


class CasanovaAdder(object):
	''' Simple class to encapsulate posting a new text to Casanova server '''

	def __call__(self, gui, title, authors, description, one_liner, issues, opf, file_loc, mi, book_id, log=None, abort=None, notifications=None):
		values = {'cmd' : 'new_text',
		          'title' : title,
		          'authors' : authors,
		          'one_liner' : one_liner,
		          'description' : description,
		          'issues' : issues,
		          'opf' : opf }
		if file_loc:
			with open(file_loc, 'rb') as f:
				td = f.read()
				values['text'] = b64encode(td)
				fn, ext = os.path.splitext(file_loc)
				values['text_ext'] = ext
		response = self._post(values)
		the_page = response.read()
		try: 
			doc = json.loads(the_page)
		except:
			return False
		if 'status' in doc and doc['status']=='success':
			mi.identifiers['casanova'] = doc['casanova_id']
			gui.current_db.set_metadata(book_id, mi)
			gui.current_db.commit()
			print('book added with casanova id=' + doc['casanova_id'])
			return True
		return False

	def _post(self, values, path='/api/do'):
		''' Posts something to the casanova listener url '''
		self.base_url = prefs['base_url']
		url = url_slash_cleaner(self.base_url + path)
		user_agent = 'Casanova/1.0 (compatible; MSIE 5.5; Windows NT)'
		values['un'] = prefs['username']
		values['pw'] = prefs['password']
		headers = { 'User-Agent' : user_agent, 'Content-type': 'application/x-www-form-urlencoded; charset=UTF-8' }
		data = urllib.urlencode(values)
		req = urllib2.Request(url, data, headers)
		response = urllib2.urlopen(req)
		return response


gui_casanova_adder = CasanovaAdder()

def start_casanova_upload(callback, job_manager, gui, title, authors, description, one_liner, issues, opf, file_loc, mi, book_id):
	description = _('Adding %s') % title
	job = ThreadedJob('casanova_add', description, gui_casanova_adder, (gui, title, authors, description, one_liner, issues, opf, file_loc, mi, book_id), {}, callback, max_concurrent_count=1, killable=False)
	job_manager.run_threaded_job(job)


class CasanovaAddManager(object):
	def __init__(self, gui):
		print('New Casanova add manager created')
		self.gui = gui
		self.db = gui.current_db

	def add(self, book_id,  mi, formats, one_liner=''):
		self.one_liner = one_liner
		self.title = mi.title
		# authors
		authors = []
		for x in mi.authors:
			authors.append(author_to_author_sort(x))
		self.authors = '|'.join(authors)
		# issues
		issues = []
		um = mi.get_all_user_metadata(False)
		if '#issue' in um:
			issue_strs = um['#issue']['#value#']
			for issue_str in issue_strs:
				issue_id = issue_str.rpartition('(')[-1].partition(')')[0]
				issues.append(issue_id)
		self.issues = '|'.join(issues)
		# etc
		self.description = mi.comments
		# opf
		self.opf = metadata_to_opf(mi)
		# file to upload
		for format, file_loc in formats.items():
			self.file = file_loc
		# metadata
		self.mi = mi
		self.book_id = book_id
		self._start()

	def _start(self):
		start_casanova_upload(Dispatcher(self.added), self.gui.job_manager, self.gui, self.title, self.authors, self.description, self.one_liner, self.issues, self.opf, self.file, self.mi, self.book_id)
		self.gui.status_bar.show_message(_('Adding') + ' ' + unicode(self.title), 3000)


	def added(self, job):
		if job.failed:
			self.gui.job_exception(job, dialog_title=_('Failed to add text. Sorry.'))
			return
		self.gui.status_bar.show_message(job.description + ' ' + _('finished'), 5000)


