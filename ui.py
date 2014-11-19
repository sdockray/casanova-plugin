#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL 3'
__copyright__ = '2014, Alex Kosloff <pisatel1976@gmail.com>'
__docformat__ = 'restructuredtext en'

from functools import partial
from PyQt4.Qt import QMenu, QToolButton, QUrl
from calibre.gui2 import error_dialog, question_dialog, info_dialog, open_url
from calibre.gui2.actions import InterfaceAction
from calibre.utils.config import config_dir

from calibre.gui2.tag_browser.view import TagsView
# The class that all interface action plugins must inherit from
from calibre.gui2.actions import InterfaceAction
#from calibre_plugins.casanova_plugin.main import DemoDialog
from calibre_plugins.casanova_plugin.config import prefs
from calibre_plugins.casanova_plugin.utils import (set_plugin_icon_resources, get_icon,
                                                         create_menu_action_unique)

from calibre_plugins.casanova_plugin.download import CasanovaDownloadManager
from calibre_plugins.casanova_plugin.upload import CasanovaAddManager
from calibre_plugins.casanova_plugin.metadata import CasanovaMetadataManager
from calibre_plugins.casanova_plugin.dialogs import ChooseIssuesToUpdateDialog, ChooseAuthorsToUpdateDialog, ChooseFormatToDownloadDialog, SearchDialog, AddBookDialog


PLUGIN_ICONS = ['images/icon.png']

class CasanovaUI(InterfaceAction):

    name = "Casanova"
    action_spec = (_('Casanova'), None, None, None)
    action_type = 'current'
    popup_type = QToolButton.InstantPopup
    
    def genesis(self):
        # This method is called once per plugin, do initial setup here
        self.menu = QMenu(self.gui)
        self.old_actions_unique_map = {}

        icon_resources = self.load_resources(PLUGIN_ICONS)

        self.qaction.setMenu(self.menu)
        #self.qaction.setIcon(get_icon(PLUGIN_ICONS[0]))
        self.menu.aboutToShow.connect(self.about_to_show_menu)

    def initialization_complete(self):
        ''' An InterfaceAction method '''
        # @todo : create Casanova managers here
        self.mm = CasanovaMetadataManager(self.gui)
        self.dm = CasanovaDownloadManager(self.gui, self.mm)
        self.am = CasanovaAddManager(self.gui)
        self.rebuild_menus()


    def about_to_show_menu(self):
        ''' Just before the menu is displayed '''
        if hasattr(self, 'casanova_book_submenu'):
            selected_linked = self.is_one_casanova_book_selected()
            self.casanova_book_submenu.setEnabled(selected_linked)
        if hasattr(self, 'author_menu_item'):
            author_selected_linked = self.is_one_casanova_book_selected(include_non_casanova=True)
            self.author_menu_item.setEnabled(author_selected_linked)
        if hasattr(self, 'add_new_menu_item'):
            add_selected_linked = self.is_one_casanova_book_selected(only_non_casanova=True)
            self.add_new_menu_item.setEnabled(add_selected_linked)
        #if hasattr(self, 'casanova_issue_submenu'):
        #    selected_linked = self.is_no_books_selected()
        #    self.casanova_issue_submenu.setEnabled(selected_linked)


    def is_one_casanova_book_selected(self, include_non_casanova=False, only_non_casanova=False):
        ''' Checks that there is one and only one casanova book selected (for updating, etc) '''
        db = self.gui.current_db
        rows = self.gui.library_view.selectionModel().selectedRows()
        if not rows or len(rows) != 1:
            return False
        if only_non_casanova:
            for row in rows:
                calibre_id = db.id(row.row())
                mi = db.get_metadata(calibre_id, index_is_id=True)
                if not mi.has_identifier('casanova'):
                    return True
        else:
            if include_non_casanova:
                return True
            for row in rows:
                calibre_id = db.id(row.row())
                mi = db.get_metadata(calibre_id, index_is_id=True)
                if mi.has_identifier('casanova'):
                    return True
        return False


    def is_no_books_selected(self):
        ''' Checks that there are no books at all currently selected '''
        db = self.gui.current_db
        rows = self.gui.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            return True
        return False

    def get_selected_row(self):
        rows = self.gui.current_view().selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            return None
        return rows[0].row()

    def get_selected_casanova_id(self, base_only=False):
        ''' Gets the selected book's Casanova id (if multiple are selected, it gets the first one) '''
        db = self.gui.current_db
        rows = self.gui.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            return False
        for row in rows:
            calibre_id = db.id(row.row())
            mi = db.get_metadata(calibre_id, index_is_id=True)
            if mi.has_identifier('casanova'):
                res = mi.identifiers['casanova'].split('.')
                if (len(res)==2):
                    if base_only:
                        return res[0]
                    else:
                        return {'id':res[0], 'revision':res[1]}
        return False


    def rebuild_menus(self):
        ''' Builds the UI menus '''
        print('Rebuilding menus')
        m = self.menu
        m.clear()
        self.actions_unique_map = {}

        if prefs['username']=='guest' and prefs['password']=='guest':
            foo = True
        else:
            self.add_new_menu_item = create_menu_action_unique(self, m, _('&Add to Casanova') + '...', None, shortcut=False, triggered=self.add_book)
            self.casanova_book_submenu = m.addMenu(get_icon('images/link.png'), 'Linked text')
            self.create_menu_item_ex(self.casanova_book_submenu, 'Refresh metadata',
                    'images/update.png', 'Gets any updates to the metadata for this text from the server',
                    triggered=self.refresh_metadata)
            self.create_menu_item_ex(self.casanova_book_submenu, 'Upload metadata',
                    'images/commit.png', 'Send your metadata changes for this text to the server',
                    triggered=self.upload_metadata)
            self.casanova_book_submenu.addSeparator()
            self.create_menu_item_ex(self.casanova_book_submenu, 'Download',
                    'images/download.png', 'Download a file format from the Casanova server',
                    triggered=self.download_format)
            m.addSeparator()
            self.casanova_issue_submenu = m.addMenu(get_icon('images/link.png'), 'Get metadata')
            self.create_menu_item_ex(self.casanova_issue_submenu, 'Update issues',
                    'images/refresh.png', 'Get updates to issues from the Casanova server',
                    triggered=self.update_issues)
            self.author_menu_item = self.create_menu_item_ex(self.casanova_issue_submenu, 'Get all by author',
                    'images/download.png', 'Get metadata for all texts by this author',
                    triggered=self.update_author)
            self.create_menu_item_ex(self.casanova_issue_submenu, 'Search',
                    'images/download.png', 'Search Casanova titles and authors',
                    triggered=self.search)

        m.addSeparator()
        create_menu_action_unique(self, m, _('&Settings') + '...', None, shortcut=False, triggered=self.show_configuration)
        # Before we finalize, make sure we delete any actions for menus that are no longer displayed
        for menu_id, unique_name in self.old_actions_unique_map.iteritems():
            if menu_id not in self.actions_unique_map:
                self.gui.keyboard.unregister_shortcut(unique_name)
        self.old_actions_unique_map = self.actions_unique_map
        self.gui.keyboard.finalize()

        from calibre.gui2 import gprefs
        
        if self.name not in gprefs['action-layout-context-menu']:
            gprefs['action-layout-context-menu'] += (self.name, )
        if self.name not in gprefs['action-layout-toolbar']:
            gprefs['action-layout-toolbar'] += (self.name, )
        
        #gprefs['action-layout-context-menu'] += ('AAAARG', )
        #gprefs['action-layout-toolbar'] += ('AAAARG', )
        #print(gprefs['action-layout-toolbar'])
        # force add our menu into the gui toolbar
        #print(self.gui.tags_view.context_menu)
        #print(gprefs['action-layout-context-menu'])
        for x in (self.gui.preferences_action, self.qaction):
            x.triggered.connect(self.show_configuration)


    def gui_layout_complete(self):
        '''
        We should add the custom column here, if it doesn't already exist
        '''
        from calibre.gui2 import get_current_db, show_restart_warning
        do_restart = False
        # create issue
        cust_col_id = '#issue'
        db = get_current_db()
        cust_cols = db.field_metadata.custom_field_metadata()
        col = unicode(cust_col_id)
        if col not in cust_cols:
            print('Custom column being created')
            db.create_custom_column(
                    label=cust_col_id[1:],
                    name=unicode('Issues'),
                    datatype='text',
                    is_multiple=True,
                    display = {'is_names': False})
            do_restart = show_restart_warning(_('Casanova needed to create a custom column. Please restart now!'))
        else:
            print('The issue column already exists, so skip creation')
        if do_restart:
            self.gui.quit(restart=True)


    def add_book(self):
        ''' Adds a book to Casanova '''
        db = self.gui.current_db
        row = self.get_selected_row()
        if self.gui.current_view() is self.gui.library_view:
            book_id = self.gui.library_view.model().id(row)
        else:
            book_id = self.gui.current_view().model().id(row)
        mi = db.get_metadata(book_id, index_is_id=True)

        formats = {}
        fmts = db.formats(book_id, index_is_id=True, verify_formats=False)
        if fmts:
            fmts = fmts.split(',')
            for fmt in fmts:
                fpath = db.format(book_id, fmt, index_is_id=True, as_path=True)
                if fpath is not None:
                    formats[fmt.lower()] = fpath
        if len(formats)==0:
            return

        add_dialog = AddBookDialog(self.gui, self.mm, mi)
        add_dialog.exec_()
        if add_dialog.result() != add_dialog.Accepted:
            return
        self.am.add(book_id, mi, formats, add_dialog.one_line_description)
        db.commit()

    def refresh_metadata(self):
        ''' Download any changes on the Casanova metadata server to an item locally '''
        row = self.get_selected_row()
        if self.gui.current_view() is self.gui.library_view:
            id = self.gui.library_view.model().id(row)
        else:
            id = self.gui.current_view().model().id(row)
        result = self.mm.update(id)
        if isinstance(result, dict):
            return info_dialog(self.gui, 'Metadata retrieved',
                        unicode(result['added']) + ' added and ' + unicode(result['updated']) + ' updated', show=True)
        elif isinstance(result, str):
            return info_dialog(self.gui, 'Casanova message', unicode(result), show=True)


    def upload_metadata(self):
        ''' Upload any changes we have made locally to the Casanova metadata server '''
        row = self.get_selected_row()
        if self.gui.current_view() is self.gui.library_view:
            id = self.gui.library_view.model().id(row)
        else:
            id = self.gui.current_view().model().id(row)
        result = self.mm.commit(id)
        if isinstance(result, str):
            return info_dialog(self.gui, 'Casanova message', unicode(result), show=True)
            

    def show_configuration(self):
        print('Configuration')
        self.interface_action_base_plugin.do_user_config(self.gui)
        self.rebuild_menus()

    def apply_settings(self):
        pass


    def download_format(self):
        ''' Callback for downloading a format for a book '''
        self.mm.refresh_book_map()
        casanova_id = self.get_selected_casanova_id(True)
        if not casanova_id:
            return error_dialog(self.gui, 'Unable to Sync',
                                'This doesn\'t seem to be a Casanova text.', show=True)
        choose_dialog = ChooseFormatToDownloadDialog(self.gui, self.dm, casanova_id)
        choose_dialog.exec_()
        if choose_dialog.result() != choose_dialog.Accepted:
            return
        if choose_dialog.selected_format is None:
            return error_dialog(self.gui, 'Unable to Sync',
                                'Unable to download anything.', show=True)
        if casanova_id in self.mm.book_map:
            book_id = self.mm.book_map[casanova_id]
            self.dm.download_ebook(book_id, choose_dialog.selected_format)
        else:
            return error_dialog(self.gui, 'Unable to Sync',
                                'Mapping is messed up. Sorry!', show=True)

    def update_issues(self):
        ''' Callback for syncing an issue '''
        self.mm.refresh_issue_map()
        choose_dialog = ChooseIssuesToUpdateDialog(self.gui, self.mm)
        choose_dialog.exec_()
        if choose_dialog.result() != choose_dialog.Accepted:
            return

        if choose_dialog.selected_issues is None:
            return error_dialog(self.gui, 'Unable to Sync',
                                'Unable to retrieve updates to selected issues.', show=True)
        # @todo: put this in a Dispatcher job
        result = {'added':0, 'updated':0}
        for issue in choose_dialog.selected_issues:
            r = self.mm.sync(issue)
            result['added'] = r['added']
            result['updated'] = r['updated']

        return info_dialog(self.gui, 'Metadata retrieved',
                                unicode(result['added']) + ' added and ' + unicode(result['updated']) + ' updated', show=True)               


    def update_author(self):
        ''' Gets all metadata for an author from Casanova '''
        from calibre.ebooks.metadata import author_to_author_sort
        row = self.get_selected_row()
        authors = []
        
        if self.gui.current_view() is self.gui.library_view:
            a = self.gui.library_view.model().authors(row)
            authors = a.split(',')
        else:
            mi = self.gui.current_view().model().get_book_display_info(row)
            authors = mi.authors
        
        corrected_authors = {}
        for x in authors:
            corrected_authors[x] = author_to_author_sort(x)
        
        result = {'added':0, 'updated':0}
        if len(corrected_authors)>1:
            choose_dialog = ChooseAuthorsToUpdateDialog(self.gui, self.mm, corrected_authors)
            choose_dialog.exec_()
            if choose_dialog.result() != choose_dialog.Accepted:
                return
            if choose_dialog.selected_authors is None:
                return error_dialog(self.gui, 'Unable to Sync',
                                    'Unable to retrieve updates to selected issues.', show=True)
            # @todo: put this in a Dispatcher job
            selected_authors_string = '|'.join(choose_dialog.selected_authors)
            result = self.mm.author_sync(selected_authors_string)
        if len(corrected_authors) == 1:
            for k,v in corrected_authors.items():
                result = self.mm.author_sync(v) 

        return info_dialog(self.gui, 'Metadata retrieved',
                                unicode(result['added']) + ' added and ' + unicode(result['updated']) + ' updated', show=True)               

    def search(self):
        search_dialog = SearchDialog(self.gui, self.mm)
        search_dialog.exec_()
        if search_dialog.result() != search_dialog.Accepted:
            return
        if search_dialog.selected_texts is None:
            return error_dialog(self.gui, 'Unable to Sync',
                                'No results!', show=True)
        result = self.mm.get_texts(search_dialog.selected_texts)
        return info_dialog(self.gui, 'Metadata retrieved',
                                unicode(result['added']) + ' added and ' + unicode(result['updated']) + ' updated', show=True)


    def create_menu_item_ex(self, parent_menu, menu_text, image=None, tooltip=None,
                           shortcut=None, triggered=None, is_checked=None, shortcut_name=None,
                           unique_name=None):
        ac = create_menu_action_unique(self, parent_menu, menu_text, image, tooltip,
                                       shortcut, triggered, is_checked, shortcut_name, unique_name)
        self.actions_unique_map[ac.calibre_shortcut_unique_name] = ac.calibre_shortcut_unique_name
        return ac

    def show_dialog(self):
        # The base plugin object defined in __init__.py
        base_plugin_object = self.interface_action_base_plugin
        # Show the config dialog
        # The config dialog can also be shown from within
        # Preferences->Plugins, which is why the do_user_config
        # method is defined on the base plugin class
        do_user_config = base_plugin_object.do_user_config

        # self.gui is the main calibre GUI. It acts as the gateway to access
        # all the elements of the calibre user interface, it should also be the
        # parent of the dialog
        d = DemoDialog(self.gui, self.qaction.icon(), do_user_config)
        d.show()

    def show_dialog2(self, *args):
        '''
        Delete selected books from device or library.
        '''
        view = self.gui.current_view()
        rows = view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            return
        # Library view is visible.
        if self.gui.stack.currentIndex() == 0:
            to_process_ids = [view.model().id(r) for r in rows]
            # The following will run if the selected books are not on a connected device.
            # The user has selected to delete from the library or the device and library.
            if not confirm('<p>'+_('The selected books will be '
                                   '<b>permanently deleted</b> and the files '
                                   'removed from your calibre library. Are you sure?')
                                +'</p>', 'library_delete_books', self.gui):
                return
            next_id = view.next_id
            if len(rows) < 5:
                #view.model().delete_books_by_id(to_process_ids)
                #self.library_ids_deleted2(to_process_ids, next_id=next_id)
                print('processing fewer than 5 titles')
