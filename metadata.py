# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2014, Alex Kosloff <pisatel1976@gmail.com>'
__docformat__ = 'restructuredtext en'

import os
import re
from contextlib import closing
from time import time
import json
import mechanize
import mimetypes
import urllib
import urllib2
import StringIO
from base64 import b64encode

from PyQt4.Qt import QModelIndex

from calibre import browser, get_download_filename, url_slash_cleaner
from calibre.ebooks import BOOK_EXTENSIONS
from calibre.utils.filenames import ascii_filename
from calibre.utils.zipfile import ZipFile
from calibre.ebooks.metadata.opf2 import OPF, metadata_to_opf

from calibre_plugins.casanova_plugin.config import prefs


class CasanovaMetadataManager(object):

	def __init__(self, gui):
		print('New Casanova metadata manager created')
		self.gui = gui
		self.db = gui.current_db
		self.model = self.gui.library_view.model()
		self.base_url = prefs['base_url']
		self.refresh_book_map()
		self.refresh_issue_map()

		#self.get_all_issues(True)		
		#self.get_local_books_in_issue('17492')


	def commit(self, book_id):
		''' Commits any local changes to the metadata for this book up to the Casanova server '''
    # get the opf that will be posted
		mi = self.db.get_metadata(book_id, index_is_id=True, get_cover=True)
		opf = metadata_to_opf(mi)
		# get the remote id
		try:
			casanova_id = mi.identifiers['casanova']
		except AttributeError:
			print('There is no Casanova identifier for this book')
		# now post the metadata
		return self._post_metadata(casanova_id, opf, mi.cover)
    

	def update(self, book_id=False):
		''' Updates the metadata from the Casanova server for this book '''
		if not book_id:
			# we are updating all metadata for all books and issues that we have
			print('updating everything?')
			#casanova_book_ids = self.get_all_casanova_books()
			#casanova_issue_ids = self.get_all_issues()
			# @todo!
		else:
			mi = self.db.get_metadata(book_id, index_is_id=True)
			if mi.has_identifier('casanova'):
				return self._post_update_request(mi.identifiers['casanova'])


	def sync(self, id):
		''' Syncs an issue, ensuring that any new books in the issue remotely are added locally '''
		if id in prefs['last_updates']:
			# for now, just add things that were added after the date of last update
			local_books = self.get_local_books_in_issue(id)
			updates_zip = self._post_sync_request(id, local_books, prefs['last_updates'][id])
		else:
			# use the remote issue as the target - we want to match it by the end of the sync
			local_books = self.get_local_books_in_issue(id)
			updates_zip = self._post_sync_request(id, local_books)

		# Add new books
		# If a book is in an issue locally, but not remotely, we have to ignore it, because it might have been removed remotely and we shouldn't re-add
		# If a book is missing locally but it exists remotely, we should see if the remote add date is before or after the "last_updates" value (delete if before)
		books_to_create_on_casanova = []
		books_to_add_to_issue = []

		last_updates = prefs['last_updates']
		last_updates[id] = time()
		prefs['last_updates'] = last_updates
		return updates_zip

	def author_sync(self, str):
		''' Gets all metadata for one or more authors '''
		values = {'cmd' : 'get_author',
		          'authors' : str }
		
		response = self._post(values)
		the_zip = response.read()
		response_type = response.info().getheader('Content-Type')
		if 'archive/zip' in response_type:
			io = StringIO.StringIO()
			io.write(the_zip)
			return self.handle_zip_of_opf_files(io) #@todo : pick up here
		else:
			return 'Something went wrong :('

	def _post(self, values, path='/api/do'):
		''' Posts something to the casanova listener url '''
		prefs.refresh()
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


	def _post_metadata(self, id, opf, cover=None):
		''' Posts updated metadata to Casanova server '''
		values = {'cmd' : 'commit_metadata',
		          'id' : id,
		          'opf' : opf }
		if cover:
			with open(cover, 'rb') as f:
				cd = f.read()
				values['cover'] = b64encode(cd)
				fn, ext = os.path.splitext(cover)
				values['cover_ext'] = ext
		response = self._post(values)
		the_page = response.read()
		return the_page


	def _post_update_request(self, casanova_id):
		''' Asks Casanova server for updates to a certain piece of Casanova metadata '''
		values = {'cmd' : 'update_metadata',
		          'id' : casanova_id }
		response = self._post(values)
		response_type = response.info().getheader('Content-Type')
		response_content = response.read()
		if 'text/html' in response_type:
			return response_content
		if 'archive/zip' in response_type:
			io = StringIO.StringIO()
			io.write(response_content)
			return self.handle_zip_of_opf_files(io) #@todo : pick up here


	def _post_sync_request(self, id, local_casanova_ids, since=0):
		''' Posts a arequest for syncing an issue '''
		values = {'cmd' : 'sync_issue',
		          'id' : id,
		          'casanova_ids' : ','.join(local_casanova_ids),
		          'last_update' : since }
		
		response = self._post(values)
		the_zip = response.read()
		response_type = response.info().getheader('Content-Type')
		if 'archive/zip' in response_type:
			io = StringIO.StringIO()
			io.write(the_zip)
			return self.handle_zip_of_opf_files(io) #@todo : pick up here
		else:
			return 'Something went wrong :('

	def search(self, str):
		''' Searches for text metadata on Casanova '''
		values = {'cmd' : 'search',
							'query' : str }
		response = self._post(values)
		text = response.read()
		ret_dict = {}
		try: 
			doc = json.loads(text)
		except:
			return ret_dict
		if len(doc)==0:
			return ret_dict
		for id, data in doc.items():
			name = data['title'].strip() + ' <' + data['author'].strip() + '>' 
			k = id
			v = name
			ret_dict[k] = v
		return ret_dict

	def get_texts(self, casanova_ids):
		''' Given base Casanova ids, get the metadata from the server '''
		values = {'cmd' : 'get_texts',
		          'casanova_ids' : ','.join(casanova_ids) }
		
		response = self._post(values)
		the_zip = response.read()
		response_type = response.info().getheader('Content-Type')
		if 'archive/zip' in response_type:
			io = StringIO.StringIO()
			io.write(the_zip)
			return self.handle_zip_of_opf_files(io) #@todo : pick up here
		else:
			return 'Something went wrong :('


	def get_remote_formats(self, id, timeout=60):
		''' Retrieves information about where the actual file is located to download. Id is a casanova id '''
		values = {'cmd' : 'get_formats',
							'id' : id }
		response = self._post(values)
		try:
			doc = json.load(response)
			formats = []
			for fid, data in doc.items():
				type = None
				if 'type' in data:
					type = data['type'].strip()
					href = data['href'].strip()
					if type:
						ext = mimetypes.guess_extension(type)
						if ext:
							formats.append({'type':ext, 'href':href})
			return formats
		except:
			return _('Something went wrong :(')

	def get_remote_issues(self):
		''' Gets a list of remote issues - the Casanova server itself will decide how to implement this '''
		values = {'cmd' : 'get_issues' }
		response = self._post(values)		
		try:
			doc = json.load(response)
			ret_dict = {}
			for id, data in doc.iteritems():
				k = str(id)
				v = str(data['name'])
				ret_dict[k] = v
			return ret_dict
		except:
			return _('Something went wrong :(')

	def get_all_casanova_books(self):
		''' Gets every Casanova book in the library '''
		rows = xrange(self.model.rowCount(QModelIndex()))
		ids = []
		for i in rows:
			mi = self.db.get_metadata(i)
			if mi.has_identifier('casanova'):
				ids.append(mi.identifiers['casanova'])
		return ids


	def get_all_issues(self, include_external=False):
		from operator import itemgetter
		ids = []
		tags_model = self.gui.tags_view.model()
		result = tags_model.get_category_editor_data('#issue')
		followed={}
		downloaded={}
		synced={}
		if result is not None:
			for key, category_name, num in result:
				#print(category_name)
				m = re.match( r'(.*)\((\d+)\)' , category_name)
				if m:
					#ids[ m.group(2) ] = m.group(1)
					issue_id = m.group(2);
					issue_name = m.group(1)
					if 'last_updates' in prefs and issue_id in prefs['last_updates']:
						synced[issue_id] = issue_name
					else:
						downloaded[issue_id] = issue_name
		if include_external:
			ei = self.get_remote_issues()
			for k, v in ei.iteritems():
				if v is not None:
					if not k in ids:
						#ids[k] = ei[k]
						if k not in synced and k not in downloaded:
							followed[k] = v
		sorted_ids = sorted(synced, key=synced.__getitem__)
		if len(sorted_ids)>0:
			ids.append((0, '** issues that you have updated **'))
		for i in sorted_ids:
			ids.append((i,synced[i]))
		sorted_ids = sorted(followed, key=followed.__getitem__)
		if len(sorted_ids)>0:
			ids.append((0, '** issues that you are following **'))
		for i in sorted_ids:
			ids.append((i,followed[i]))
		sorted_ids = sorted(downloaded, key=downloaded.__getitem__)
		if len(sorted_ids)>0:
			ids.append((0, '** other issues in your library **'))
		for i in sorted_ids:
			ids.append((i,downloaded[i]))
		return ids


	def get_casanova_metadata(self, casanova_id, cover_as_data=False):
		''' Gets a local book (metadata) by its casanova id '''
		rows = xrange(self.model.rowCount(QModelIndex()))
		for i in rows:
			mi = self.db.get_metadata(i, cover_as_data=cover_as_data)
			candidate = self.extract_id(mi)
			if candidate:
				if candidate['id']==casanova_id:
					return mi
		return False


	def get_local_books_in_issue(self, id, return_casanova_id_strings=True):
		''' Given an issue's id, return a list of books '''
		ret_ids = []
		if id in self.issue_map:
			calibre_id = self.issue_map[id]
			book_ids = self.get_book_ids_in_issue(calibre_id)
			for book_id in book_ids:
				if return_casanova_id_strings:
					mi = self.db.get_metadata(book_id, index_is_id=True)
					if mi.has_identifier('casanova'):
						ret_ids.append(mi.identifiers['casanova'])
				else:
					ret_ids.append(book_id)
		return ret_ids


	def get_book_ids_in_issue(self, id):
		''' This is a hack which will probably break in future Calibre versions... 
		all it does is get a list of book ids for books in a particular issue,
		using the internal tag id '''
		fm = self.db.field_metadata['#issue']
		result = self.db.conn.get(
		'SELECT book FROM books_{0}_link WHERE {1}=?'.format(fm['table'], fm['link_column']), (id, ), all=True)
		if not result:
			return set([])
		return set([r[0] for r in result])


	def handle_zip_of_opf_files(self, stream):
		''' Given a zip up of a bunch of opf files, either merge them or add them to library '''
		result = {'updated':0, 'added':0}
		with ZipFile(stream, 'r') as zf:
			self.start_applying_updates()
			for zi in zf.infolist():
				ext = zi.filename.rpartition('.')[-1].lower()
				if ext in {'opf'}:
					try:
						raw = zf.open(zi)
						opf = OPF(raw)
						mi = opf.to_book_metadata()
						casanova_id = self.extract_id(mi)
						if casanova_id:
							book_mi = self.get_casanova_metadata(casanova_id['id'])
							if book_mi:
								# Update an existing book's metadata!
								result['updated'] = result['updated'] + 1
								self.apply_metadata_update(casanova_id['id'], book_mi, mi)
							else:
								# Create a new book entry
								result['added'] = result['added'] + 1
								self.model.db.import_book(mi,[])
					except:
						foo=False
				if ext in {'jpg', 'png', 'gif'}:
					# try and handle the cover
					casanova_id = zi.filename.partition('.')[0].lower()
					if casanova_id in self.book_map:
						book_id = self.book_map[casanova_id]
						raw = zf.open(zi)
						self.db.set_cover(book_id, raw)
			self.finish_applying_updates()
			return result
			# @todo: display a message with the results


	def apply_metadata_update(self, casanova_id, current_mi, new_mi):
		''' Updates existing metadata '''
		if casanova_id in self.book_map:
			current_mi.smart_update(new_mi)
			book_id = self.book_map[casanova_id]
			self.db.set_metadata(book_id, current_mi)
			self.applied_update_ids.add(book_id)
			return True


	def start_applying_updates(self):
		self.applied_update_ids = set()


	def finish_applying_updates(self):
		if self.applied_update_ids:
			self.db.commit()
			cr = self.gui.library_view.currentIndex().row()
			self.model.refresh_ids(list(self.applied_update_ids), cr)
			if self.gui.cover_flow:
				self.gui.cover_flow.dataChanged()
			self.gui.tags_view.recount()


	def refresh_book_map(self):
		self.book_map = {}
		rows = xrange(self.model.rowCount(QModelIndex()))
		for i in rows:
			mi = self.model.db.get_metadata(i)
			candidate = self.extract_id(mi)
			if candidate:
				casanova_id = candidate['id']
				self.book_map[casanova_id] = self.model.db.id(i)

	def refresh_issue_map(self):
		self.issue_map = {}
		tags_model = self.gui.tags_view.model()
		result = tags_model.get_category_editor_data('#issue')
		if result is not None:
			for key, category_name, num in result:
				m = re.match( r'(.*)\((\d+)\)' , category_name)
				if m:
					self.issue_map[m.group(2)] = key

	def extract_id(self, mi):
		if mi.has_identifier('casanova'):
			res = mi.identifiers['casanova'].split('.')
			if (len(res)==2):
				return {'id':res[0], 'revision':res[1]}
		return False

	def extract_id_from_string(self,str, id_only=False):
		res = str.split('.')
		if (len(res)==2):
			if id_only:
				return res[0]
			else:
				return {'id':res[0], 'revision':res[1]}
		return False
