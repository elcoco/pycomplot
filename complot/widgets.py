#!/usr/bin/env python3

import curses
import logging
import re

from complot import errors_list
from complot.utils import timeit

logger = logging.getLogger('complot')


class ScrollableWindow():
    """ It's a simple scrollable pager window like the UNIX command less """
    def __init__(self, root_win):
        term_height, term_width = root_win.getmaxyx()

        self._win_width = term_width - 8
        self._win_height = term_height - 4

        x_pos = int((term_width - self._win_width) / 2)
        y_pos = int((term_height - self._win_height) / 2)

        self._win = curses.newwin(self._win_height, self._win_width, y_pos, x_pos)
        self._win.keypad(True)

    def run(self, lines):
        end_pos = len(lines) -1

        if len(lines) >= (self._win_height -1):
            start_pos = end_pos - (self._win_height - 2)
        else:
            start_pos = 0

        while True:
            self._win.erase()

            for y, line in enumerate(lines[start_pos:end_pos], 1):
                if line:
                    self._win.addstr(y, 2, f"{y+start_pos}  {line}")

            key = self._win.getch()
            if key == curses.KEY_UP or key == ord('k'):
                if start_pos != 0:
                    start_pos -= 1
                    end_pos -= 1
            elif key == curses.KEY_DOWN or key == ord('j'):
                if end_pos != len(lines)-1:
                    start_pos += 1
                    end_pos += 1
            elif key in [curses.KEY_LEFT, ord('h'), ord('g')]:
                start_pos = 0
                if len(lines) >= (self._win_height -1):
                    end_pos = start_pos + (self._win_height - 2)
                else:
                    end_pos = start_pos + (len(lines) -1)
            elif key in [curses.KEY_RIGHT, ord('l'), ord('G')]:
                end_pos = len(lines) -1

                if len(lines) >= (self._win_height -1):
                    start_pos = end_pos - (self._win_height - 2)
                else:
                    start_pos = 0
            elif key == ord('\n') or key == 27:
                break


class MenuWidget():
    """ Does all the ncurses menu magick.
        Implements a menu with an input prompt, used filter the menu options. """
    def __init__(self, stdscr, name='menu', orientation='bottom', height=30):
        self.name = name
        self.stdscr = stdscr

        # display menu at top or bottom
        self._orientation = orientation

        # height/width of menu
        self._height = height

        self._term_height, self._term_width = self.stdscr.getmaxyx()
        self._width = self._term_width

        # position in menu, value between 0 and self._height-1
        self.menu_pos = 0

        # current position and start/end of view in items
        self.list_pos = 0
        self.view_start = 0
        self.view_end = self._height - 1

        # contents of text field
        self.input = ''

        if self._orientation == 'top':
            self.window_y_pos = 0
            self.input_line_row = 0
        else:
            self.window_y_pos = self._term_height - self._height
            self.input_line_row = self._height -1

    def set_dimensions(self):
        """ Detect terminal dimensions to be able to handle terminal resize """
        self._term_height, self._term_width = self.stdscr.getmaxyx()
        self._width = self._term_width
        self.window_y_pos = self._term_height - self._height

    def __str__(self):
        return f"> {self.name}"

    def reset_state(self):
        """ Reset positions and input field for this menu object """
        self.menu_pos = 0
        self.list_pos = 0
        self.view_start = 0
        self.view_end = self._height - 1
        self.input = ''

    def move_up(self, lines, steps=1):
        # wrap if at top
        if self.list_pos-steps+1 <= 0:

            # make sure we go to top of list before wrapping
            if self.list_pos == 0:
                self.move_to_bottom(lines)
            else:
                self.move_to_top(lines)
        else:
            self.list_pos -= steps
            self.menu_pos -= steps

            # if on first position, shift view up
            if self.menu_pos < 0:
                self.view_start -= steps
                self.view_end -= steps
                self.menu_pos = 0

    def move_down(self, lines, steps=1):
        # wrap if at bottom
        if self.list_pos+steps-1 >= len(lines)-1:

            # make sure we go to bottom of list before wrapping
            if self.list_pos == len(lines)-1:
                self.move_to_top(lines)
            else:
                self.move_to_bottom(lines)
        else:
            self.list_pos += steps
            self.menu_pos += steps

            # if on last position, shift view down
            if self.menu_pos > (self._height-2):
                self.view_start += steps
                self.view_end += steps
                self.menu_pos = self._height-2

    def move_to_top(self, lines):
        self.list_pos = 0
        self.menu_pos = 0
        self.view_start = 0

        # if amount of lines is smaller than lines in view, wrap to last line
        if len(lines) < self._height -1:
            self.view_end = len(lines)
        else:
            self.view_end = self._height -1

    def move_to_bottom(self, lines):
        self.list_pos = len(lines) -1
        self.view_end = len(lines)

        # if amount of lines is smaller than lines in view, wrap to last line
        if len(lines) < self._height -1:
            self.menu_pos = len(lines) -1
            self.view_start = 0
        else:
            self.menu_pos = self._height -2
            self.view_start = self.view_end - (self._height -1)

    def handle_input(self, lines, lines_view, key):
        """ Parse input """
        if self._orientation == 'top':
            if key == curses.KEY_UP:
                self.move_up(lines)
            elif key == curses.KEY_DOWN:
                self.move_down(lines)
            elif key == curses.KEY_LEFT:
                self.move_to_top(lines)
            elif key == curses.KEY_RIGHT:
                self.move_to_bottom(lines)
            elif key == curses.KEY_NPAGE:
                self.move_down(lines, steps=self._height-2)
            elif key == curses.KEY_PPAGE:
                self.move_up(lines, steps=self._height-2)
        else:
            if key == curses.KEY_UP:
                self.move_down(lines)
            elif key == curses.KEY_DOWN:
                self.move_up(lines)
            elif key == curses.KEY_LEFT:
                self.move_to_bottom(lines)
            elif key == curses.KEY_RIGHT:
                self.move_to_top(lines)
            elif key == curses.KEY_NPAGE:
                self.move_up(lines, steps=self._height-2)
            elif key == curses.KEY_PPAGE:
                self.move_down(lines, steps=self._height-2)

        if key == ord('\n'):
            return True

        elif key == 27:
            raise KeyboardInterrupt

        elif key == curses.KEY_BACKSPACE:
            self.input = self.input[:-1]
            self.menu_pos = 0
            self.list_pos = 0
            self.view_start = 0
            self.view_end = self._height -1

        elif chr(key).lower() in ' abcdefghijklmnopqrstuvwxyz1234567890.':
            self.input += chr(key)
            self.menu_pos = 0
            self.list_pos = 0
            self.view_start = 0
            self.view_end = self._height -1

    def input_mode(self, msg=''):
        """ Don't display menu only read input and return """
        self.set_dimensions()

        # create window for menu
        y_pos = 0 if self._orientation == 'top' else self._term_height-1
        menu = curses.newwin(1, self._width, y_pos, 0)

        # map arrow keys to special keys
        menu.keypad(True)
        curses.curs_set(True)

        while True: 
            menu.erase()

            # print menu
            prompt = f"{msg}: "
            menu.addstr(0, 1, f"{prompt}{self.input}")
            menu.move(0, (len(prompt) + len(self.input))+1)

            try:
                if self.handle_input([], [], menu.getch()):
                    break
            except KeyboardInterrupt:
                curses.curs_set(False)
                return

        curses.curs_set(False)
        return self.input

    def print_menu(self, win, lines):
        win.addstr(self.input_line_row, 1, f": {self.input}")

        # TODO bug when doing page up in log
        for y,line in enumerate(lines, 0):
            y_adj = y+1 if self._orientation == 'top' else self._height-y-2
            if y == self.menu_pos:
                win.addstr(y_adj, 1, str(line).ljust(self._width-2)[:self._width-2], curses.A_REVERSE)
            else:
                win.addstr(y_adj, 1, str(line)[:self._width-2])

        # move cursor to end of input line
        win.move(self.input_line_row, len(self.input)+3)

    def filter_list(self, items, string):
        return [line for line in items if string.lower() in str(line).lower()]

    def run(self, items):
        logger.debug("start run")
        # re init terminal dimensions and menu width
        self.set_dimensions()

        # create window for menu
        menu = curses.newwin(self._height, self._width, self.window_y_pos, 0)

        # map arrow keys to special keys
        menu.keypad(True)
        curses.curs_set(True)

        while True: 
            logger.debug("in loop")
            menu.erase()

            # filter lines
            lines = self.filter_list(items, self.input) if self.input else items
            lines_view = lines[self.view_start : self.view_end]
            self.print_menu(menu, lines_view)

            # TODO NOT OK to abuse exceptions like this, they deserve better. Find better flow for this 
            try:
                if self.handle_input(lines, lines_view, menu.getch()):
                    break
            except KeyboardInterrupt:
                curses.curs_set(False)
                return


        curses.curs_set(False)
        if lines_view:
            logger.debug(f"Selected menu item: {lines_view[self.menu_pos]}")
            return lines_view[self.menu_pos]
