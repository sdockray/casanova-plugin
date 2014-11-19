#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL 3'
__copyright__ = '2014, Alex Kosloff <pisatel1976@gmail.com>'
__docformat__ = 'restructuredtext en'

import re, urllib, collections, copy
from functools import partial
from PyQt4.Qt import (Qt, QVBoxLayout, QLabel, QLineEdit, QApplication,
                      QGroupBox, QHBoxLayout, QToolButton, QTableWidgetItem,
                      QIcon, QTableWidget, QPushButton, QCheckBox, QSizePolicy,
                      QAbstractItemView, QVariant, QDialogButtonBox, QAction,
                      QGridLayout, pyqtSignal, QUrl, QListWidget, QListWidgetItem,
                      QTextEdit)

from calibre.ebooks.metadata import MetaInformation
from calibre.gui2 import error_dialog, question_dialog, gprefs, open_url
from calibre.gui2.library.delegates import RatingDelegate
from calibre.utils.date import qt_to_dt, UNDEFINED_DATE

from calibre_plugins.casanova_plugin.utils import (get_icon, SizePersistedDialog, ImageLabel,
                                         ReadOnlyTableWidgetItem, ImageTitleLayout, ReadOnlyLineEdit,
                                         DateDelegate, RatingTableWidgetItem, DateTableWidgetItem)

class ChooseIssuesToUpdateDialog(SizePersistedDialog):

    def __init__(self, parent=None, mm=None):
        SizePersistedDialog.__init__(self, parent, 'casanova plugin:issues update dialog')
        self.setWindowTitle('Select issues to update:')
        self.gui = parent
        self.mm = mm

        layout = QVBoxLayout(self)
        self.setLayout(layout)

        self.values_list = QListWidget(self)
        self.values_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        layout.addWidget(self.values_list)
        
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self._accept_clicked)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self._display_issues()

        # Cause our dialog size to be restored from prefs or created on first usage
        self.resize_dialog()

    def _display_issues(self):
        self.values_list.clear()
        issues = self.mm.get_all_issues(True)
        for id, issue in issues:
            item = QListWidgetItem(get_icon('images/books.png'), issue, self.values_list)
            item.setData(1, (id,))
            self.values_list.addItem(item)

    def _accept_clicked(self):
        #self._save_preferences()
        self.selected_issues = []
        for item in self.values_list.selectedItems():
        	self.selected_issues.append(item.data(1).toPyObject()[0])
        self.accept()


class AddBookDialog(SizePersistedDialog):

    def __init__(self, parent=None, mm=None, mi = None):
        SizePersistedDialog.__init__(self, parent, 'casanova plugin:add book dialog')
        self.setWindowTitle('Add text to Casanova:')
        self.gui = parent
        self.mm = mm
        self.mi = mi
        self.one_line_description = ''

        layout = QVBoxLayout(self)
        self.setLayout(layout)

        self.one_liner_label = QLabel('Enter a short description (255 chars max) before pressing OK')
        layout.addWidget(self.one_liner_label)
        self.one_liner_str = QLineEdit(self)
        self.one_liner_str.setText('')
        layout.addWidget(self.one_liner_str)
        self.one_liner_label.setBuddy(self.one_liner_str)

        self.values_label = QLabel('Below are potential matches of texts that already exist - please make sure you are adding something new')
        layout.addWidget(self.values_label)
        self.values_list = QListWidget(self)
        self.values_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        layout.addWidget(self.values_list)
        
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self._accept_clicked)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self._display_choices()

        # Cause our dialog size to be restored from prefs or created on first usage
        self.resize_dialog()

    def _display_choices(self):
        self.values_list.clear()
        choices = self.mm.search(self.mi.title)
        if choices is None or len(choices)==0:
            item = QListWidgetItem(get_icon('images/books.png'), _('there seem to be no matches'), self.values_list)
            self.values_list.addItem(item)
        for id, name in choices.items():
            item = QListWidgetItem(get_icon('images/books.png'), name, self.values_list)
            item.setData(1, (id,))
            self.values_list.addItem(item)

    def _accept_clicked(self):
        #self._save_preferences()
        one_liner = unicode(self.one_liner_str.text())
        if one_liner=='':
            self.values_list.clear()
            item = QListWidgetItem(get_icon('images/books.png'), _('you need to enter a short description'), self.values_list)
            self.values_list.addItem(item)
        else:
            self.one_line_description = one_liner
        self.accept()  


class ChooseAuthorsToUpdateDialog(SizePersistedDialog):

    def __init__(self, parent=None, mm=None, choices = None):
        SizePersistedDialog.__init__(self, parent, 'casanova plugin:author update dialog')
        self.setWindowTitle('Select authors to update:')
        self.gui = parent
        self.mm = mm
        self.choices = choices

        layout = QVBoxLayout(self)
        self.setLayout(layout)

        self.values_list = QListWidget(self)
        self.values_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        layout.addWidget(self.values_list)
        
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self._accept_clicked)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self._display_choices()

        # Cause our dialog size to be restored from prefs or created on first usage
        self.resize_dialog()

    def _display_choices(self):
        self.values_list.clear()
        for author, author_sort in self.choices.items():
            item = QListWidgetItem(get_icon('images/books.png'), author, self.values_list)
            item.setData(1, (author_sort,))
            self.values_list.addItem(item)

    def _accept_clicked(self):
        #self._save_preferences()
        self.selected_authors = []
        for item in self.values_list.selectedItems():
            self.selected_authors.append(item.data(1).toPyObject()[0])
        self.accept()    


class SearchDialog(SizePersistedDialog):

    def __init__(self, parent=None, mm=None):
        SizePersistedDialog.__init__(self, parent, 'casanova plugin:search dialog')
        self.setWindowTitle('Search Casanova:')
        self.gui = parent
        self.mm = mm
        
        layout = QVBoxLayout(self)
        self.setLayout(layout)

        self.search_label = QLabel('Search for:')
        layout.addWidget(self.search_label)
        self.search_str = QLineEdit(self)
        self.search_str.setText('')
        layout.addWidget(self.search_str)
        self.search_label.setBuddy(self.search_str)

        self.find_button = QPushButton("&Find")
        self.search_button_box = QDialogButtonBox(Qt.Horizontal)
        self.search_button_box.addButton(self.find_button, QDialogButtonBox.ActionRole)
        self.search_button_box.clicked.connect(self._find_clicked)
        layout.addWidget(self.search_button_box)        

        self.values_list = QListWidget(self)
        self.values_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        layout.addWidget(self.values_list)
        
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self._accept_clicked)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        # Cause our dialog size to be restored from prefs or created on first usage
        self.resize_dialog()

    def _display_choices(self, choices):
        self.values_list.clear()
        for id, name in choices.items():
            item = QListWidgetItem(get_icon('images/books.png'), name, self.values_list)
            item.setData(1, (id,))
            self.values_list.addItem(item)

    def _find_clicked(self):
        query = unicode(self.search_str.text())
        self._display_choices(self.mm.search(query))

    def _accept_clicked(self):
        #self._save_preferences()
        self.selected_texts = []
        for item in self.values_list.selectedItems():
            self.selected_texts.append(item.data(1).toPyObject()[0])
        self.accept() 

class ChooseFormatToDownloadDialog(SizePersistedDialog):

    def __init__(self, parent=None, dm=None, casanova_id=None):
        SizePersistedDialog.__init__(self, parent, 'casanova plugin:format download dialog')
        self.setWindowTitle('Select format to download:')
        self.gui = parent
        self.dm = dm
        self.casanova_id = casanova_id

        layout = QVBoxLayout(self)
        self.setLayout(layout)

        self.values_list = QListWidget(self)
        self.values_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        layout.addWidget(self.values_list)
        
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self._accept_clicked)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self._display_formats()

        # Cause our dialog size to be restored from prefs or created on first usage
        self.resize_dialog()

    def _display_formats(self):
        self.values_list.clear()
        formats = self.dm.get_download_info(self.casanova_id)
        if isinstance(formats, list):
            for format in formats:
                item = QListWidgetItem(get_icon('images/books.png'), format['type'], self.values_list)
                item.setData(1, (format,))
                self.values_list.addItem(item)
        else:
            return error_dialog(self.gui, 'Casanova message', unicode(formats), show=True) 
        

    def _accept_clicked(self):
        #self._save_preferences()
        self.selected_format = None
        for item in self.values_list.selectedItems():
            self.selected_format = item.data(1).toPyObject()[0]
        self.accept()
