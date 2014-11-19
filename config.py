#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL 3'
__copyright__ = '2014, Alex Kosloff <pisatel1976@gmail.com>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import QWidget, QVBoxLayout, QLabel, QLineEdit
from time import time

from calibre.utils.config import JSONConfig

# This is where all preferences for this plugin will be stored
# Remember that this name (i.e. plugins/casanova) is also
# in a global namespace, so make it as unique as possible.
# You should always prefix your config file name with plugins/,
# so as to ensure you dont accidentally clobber a calibre config file
prefs = JSONConfig('plugins/casanova')

# Set defaults
prefs.defaults['base_url'] = 'http://website.com'
prefs.defaults['username'] = 'guest'
prefs.defaults['password'] = 'guest'
prefs.defaults['last_updates'] = {}

class ConfigWidget(QWidget):

    def __init__(self):
        QWidget.__init__(self)
        self.l = QVBoxLayout()
        self.setLayout(self.l)

        self.url_label = QLabel('Casanova server:')
        self.l.addWidget(self.url_label)

        self.url_msg = QLineEdit(self)
        self.url_msg.setText(prefs['base_url'])
        self.l.addWidget(self.url_msg)

        self.url_label.setBuddy(self.url_msg)

        self.username_label = QLabel('Username:')
        self.l.addWidget(self.username_label)

        self.username_msg = QLineEdit(self)
        self.username_msg.setText(prefs['username'])
        self.l.addWidget(self.username_msg)

        self.username_label.setBuddy(self.username_msg)        

        self.password_label = QLabel('password:')
        self.l.addWidget(self.password_label)

        self.password_msg = QLineEdit(self)
        self.password_msg.setEchoMode(QLineEdit.Password)
        self.password_msg.setText(prefs['password'])
        self.l.addWidget(self.password_msg)

        self.password_label.setBuddy(self.password_msg)                

    def save_settings(self):
        prefs['base_url'] = unicode(self.url_msg.text())
        prefs['username'] = unicode(self.username_msg.text())
        prefs['password'] = unicode(self.password_msg.text())


