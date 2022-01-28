#!/usr/bin/env python3

import datetime
import curses
import logging

from complot.widgets import MenuWidget

logger = logging.getLogger('complot')


class MenuItemBaseClass():
    # list and dict containing all items that are created using this baseclass
    items = []
    state = {}
    max_name       = 0
    max_menu_entry = 0

    def __init__(self, name, hidden=False, buttons=[], button_name='', callback=None, args={}):
        self.name = name

        # buttons and friendly button name for help text
        self.buttons = buttons
        self.button_name = button_name

        # don't show this item in menu
        self.hidden = hidden

        # keep list of all items
        MenuItemBaseClass.items.append(self)
        MenuItemBaseClass.state[self.name.lower()] = self
        #MenuItemBaseClass.items[self.name] = self

        # arguments to callback
        self._callback = callback
        self._args = args

    def update_max(self):
        # update name and status field lengths used for justifying the output of __str__
        MenuItemBaseClass.max_name       = max([len(x.name) for x in MenuItemBaseClass.items])
        MenuItemBaseClass.max_menu_entry = max([len(str(x.menu_entry)) for x in MenuItemBaseClass.items])


class OptionsMenuItem(MenuItemBaseClass):
    """ Menu item that holds a defined set op options """
    def __init__(self, win, *args, default=None, options=None, **kwargs):
        MenuItemBaseClass.__init__(self, *args, **kwargs)
        self.options = options if options != None else []
        self.choice = None
        self.win = win
        self.default = default

        # update name and status field lengths used for justifying the output of __str__
        self.update_max()

    def add_option(self, option):
        if self.choice == None:
            self.choice = option
        self.options.append(option)

        # update name and status field lengths used for justifying the output of __str__
        self.update_max()

    @property
    def state(self):
        return self.choice.state

    @property
    def menu_entry(self):
        if self.choice != None:
            return self.choice.menu_entry

    def on_activated(self):
        menu = Menu(self.win)
        choice = menu.run(self.options)
        if choice in self.options:
            self.choice = choice
            choice.on_activated()

    def set_default(self, name):
        self.default = name

    def reset(self):
        self.set_option(self.default)

    def set_option(self, name):
        for option in self.options:
            if name == option.name:
                self.choice = option
                break
        else:
            raise ValueError(f"Option not found: {name}")

    def __str__(self):
        max_menu_entry = MenuItemBaseClass.max_menu_entry
        max_name       = MenuItemBaseClass.max_name
        if self.button_name:
            return f"> {self.name.ljust(max_name-2)}  {str(self.menu_entry).ljust(max_menu_entry)}  [{self.button_name}]"
        else:
            return f"> {self.name.ljust(max_name-2)}  {str(self.menu_entry).ljust(max_menu_entry)}"


class EditableMenuItem(MenuItemBaseClass):
    def __init__(self, win, *args, dtype=int, default=None, **kwargs):
        MenuItemBaseClass.__init__(self, *args, **kwargs)
        self._state = default
        self.default = default
        self.win = win
        self._dtype = dtype

        # update name and status field lengths used for justifying the output of __str__
        self.update_max()

    @property
    def state(self):
        return self._state

    @property
    def menu_entry(self):
        return self._state

    def reset(self):
        self._state = self.default

    def set_default(self, default):
        self.default = default

    def on_activated(self):
        menu = Menu(self.win)
        state = menu.input_mode(self.name)
        if state == None:
            return

        # check if data type is valid
        try:
            self._state = self._dtype(state)
        except ValueError:
            logger.error(f"Error: wrong data type. Expected {str(self._dtype)}, got {str(type(state))}")
            return

        # update name and status field lengths used for justifying the output of __str__
        self.update_max()

        if self._callback:
            self._callback(self, self._args)

    def __str__(self):
        max_menu_entry = MenuItemBaseClass.max_menu_entry
        max_name       = MenuItemBaseClass.max_name
        if self.button_name:
            return f"{self.name.ljust(max_name)}  {str(self.menu_entry).ljust(max_menu_entry)}  [{self.button_name}]"
        else:
            return f"{self.name.ljust(max_name)}  {str(self.menu_entry).ljust(max_menu_entry)}"


class MenuItem(MenuItemBaseClass):
    """ Run a callback when selected. If state is specified, this value will be returned instead of the menu entry. 
        Eg when you want to have a menu entry like '5 minutes' and want to return a datetime.timedelta object """
    def __init__(self, *args, state=None, **kwargs):
        MenuItemBaseClass.__init__(self, *args, **kwargs)
        self._state = state

        # update name and status field lengths used for justifying the output of __str__
        self.update_max()

    @property
    def state(self):
        return self._state if self._state else self.name

    @property
    def menu_entry(self):
        return self.name

    def on_activated(self):
        if self._callback:
            self._callback(self, self._args)

    def __str__(self):
        max_len = MenuItemBaseClass.max_menu_entry + MenuItemBaseClass.max_name + 2
        if self.button_name:
            return f"{self.name.ljust(max_len)}  [{self.button_name}]"
        else:
            return f"{self.name.ljust(max_len)}"


class ToggleMenuItem(MenuItemBaseClass):
    def __init__(self, *args, default=True, **kwargs):
        MenuItemBaseClass.__init__(self, *args, **kwargs)
        self.enabled = default
        self.default = default

        # update name and status field lengths used for justifying the output of __str__
        self.update_max()

    @property
    def state(self):
        return self.enabled

    @property
    def menu_entry(self):
        return 'on' if self.enabled else 'off'

    def reset(self):
        self.enabled = self.default

    def toggle(self):
        self.enabled = not self.enabled

    def enable(self):
        self.enabled = True

    def disable(self):
        self.enabled = False

    def on_activated(self):
        self.toggle()

        if self._callback:
            self._callback(self, self._args)

        # update name and status field lengths used for justifying the output of __str__
        self.update_max()

    def __str__(self):
        max_menu_entry = MenuItemBaseClass.max_menu_entry
        max_name       = MenuItemBaseClass.max_name
        if self.button_name:
            return f"{self.name.ljust(max_name)}  {str(self.menu_entry).ljust(max_menu_entry)}  [{self.button_name}]"
        else:
            return f"{self.name.ljust(max_name)}  {str(self.menu_entry).ljust(max_menu_entry)}"


class Menu(MenuWidget):
    """ Wraps menu widget, handles menu items.
        A lot of functions are integrated in the Menu class and its MenuItemBaseClass based classes:
          - program state
          - buttons to press to change state
          - callbacks to run when changing state
          - menu to change state """

    def __init__(self, *args, refresh_callback=None, **kwargs):
        MenuWidget.__init__(self, *args, **kwargs)
        self._items = []
        self._refresh_callback = refresh_callback
        self.hidden = False

    def add_item(self, item, position=None):
        """ Add a menu item, must be an object based on MenuItemBaseClass """
        if position == None:
            self._items.append(item)
        else:
            self._items.insert(position, item)

    def remove_item(self, item):
        self._items.remove(item)

    def on_activated(self, item=None, args=None):
        # filter out hidden items
        items = [item for item in self._items if not item.hidden]

        while True:
            item = self.run(items)
            if not item:
                break

            item.on_activated()

            # do screen refresh after action
            if self._refresh_callback:
                self._refresh_callback()
