#!/usr/bin/env python3

import os, sys
import math
from pprint import pprint
import datetime
import logging
import time
import curses
import traceback
from queue import Queue
import threading
from dataclasses import dataclass

from complot.actors import Grid, Legend, StatusLine, LastValues
from complot.lines import Line, CandleStickLine
from complot.axis import VerticalAxis, HorizontalDatetimeAxis, HorizontalAxis
from complot.data import Data
from complot.threads import WatchThread, ListenInputThread, UpdateThread
from complot.user_input import InputCallbacks
from complot.menu import Menu, OptionsMenuItem, ToggleMenuItem, MenuItem, MenuItemBaseClass, EditableMenuItem
from complot.backends import CursesBackend


# import global lock
from complot import lock

logger = logging.getLogger('complot')

# TODO Have more sensible grid position like every minute, hour, day, week ...
# TODO y axis should have highlighted positions that scale with plot data
# TODO would be super awesome if candlesticks would not overlap but instead use half blocks
#      this would need unicode half blocks with wicks as well, and i don't think they exist
# TODO index spread should maybe adaptable or something

# NOTE watch thread and line.add_point are the only ways to change datastructures, they use a Lock class

class Plot(InputCallbacks):
    """ Stores all objects and coordinates drawing of plot """
    def __init__(self, stdscr, window=None, bin_window=None, left_decimals=2, right_decimals=2, paused=False, fit_all=False,
                 autorange_left_y=True, autorange_right_y=True, x_pan_steps=10, show_grid=True, show_legend=True, show_statusline=True, show_last_values=True,
                 x_axis_type='datetime', x_decimals=1):

        # drawing backend
        self._backend = CursesBackend(stdscr)

        # handles callbacks and changing of state when keys are pressed. Can also change state through menu.
        self._menu = Menu(stdscr, refresh_callback=self.draw)

        if x_axis_type == 'datetime':
            zoom_menu = OptionsMenuItem(stdscr, 'X zoom unit', default='Minutes', buttons=[ord('z')], button_name='z')
            zoom_menu.add_option(MenuItem('Seconds', state=self.get_td_timestamp(datetime.timedelta(seconds=1)), buttons=[ord('S')], button_name='S'))
            zoom_menu.add_option(MenuItem('Minutes', state=self.get_td_timestamp(datetime.timedelta(minutes=1)), buttons=[ord('M')], button_name='M'))
            zoom_menu.add_option(MenuItem('Hours',   state=self.get_td_timestamp(datetime.timedelta(hours=1)),   buttons=[ord('U')], button_name='U'))
            zoom_menu.add_option(MenuItem('Days',    state=self.get_td_timestamp(datetime.timedelta(days=1)),    buttons=[ord('D')], button_name='D'))
            zoom_menu.reset()
            self._menu.add_item(zoom_menu)
        else:
            self._menu.add_item(EditableMenuItem(stdscr, 'X zoom unit', default=0.1, dtype=float, buttons=[ord('e')], button_name='e'))

        self._menu.add_item(EditableMenuItem(stdscr, 'X pan steps', default=x_pan_steps,  buttons=[ord('e')], button_name='e'))

        self._menu.add_item(MenuItem('X zoom in',  callback=self.zoom_x,   buttons=[ord('L')], button_name='L'))
        self._menu.add_item(MenuItem('X zoom out', callback=self.unzoom_x, buttons=[ord('H')], button_name='H'))
        self._menu.add_item(MenuItem('Y zoom in',  callback=self.zoom_y,   buttons=[ord('K')], button_name='K'))
        self._menu.add_item(MenuItem('Y zoom out', callback=self.unzoom_y, buttons=[ord('J')], button_name='J'))

        self._menu.add_item(MenuItem('Pan up',    callback=self.pan_up,    buttons=[ord('k'), curses.KEY_UP],    button_name='k, ↑'))
        self._menu.add_item(MenuItem('Pan down',  callback=self.pan_down,  buttons=[ord('j'), curses.KEY_DOWN],  button_name='j, ↓'))
        self._menu.add_item(MenuItem('Pan left',  callback=self.pan_left,  buttons=[ord('h'), curses.KEY_LEFT],  button_name='h, ←'))
        self._menu.add_item(MenuItem('Pan right', callback=self.pan_right, buttons=[ord('l'), curses.KEY_RIGHT], button_name='l, →'))

        self._menu.add_item(MenuItem('Reset settings', callback=self.reset_settings, buttons=[ord('r')], button_name='r'))

        self._menu.add_item(ToggleMenuItem('Show legend',      default=show_legend,      buttons=[ord('i')], button_name='i'))
        self._menu.add_item(ToggleMenuItem('Show grid',        default=show_grid,        buttons=[ord('g')], button_name='g'))
        self._menu.add_item(ToggleMenuItem('Show last values', default=show_last_values, buttons=[ord('v')], button_name='v'))
        self._menu.add_item(ToggleMenuItem('Show statusline',  default=show_statusline,  buttons=[ord('s')], button_name='s'))

        self._menu.add_item(MenuItem('Show log',    callback=self.show_log,    buttons=[ord('x')], button_name='x'))
        self._menu.add_item(MenuItem('Show status', callback=self.show_status, buttons=[ord('?')], button_name='?'))
        self._menu.add_item(MenuItem('Draw line',   callback=self.draw_line,   buttons=[ord('d')], button_name='d'))

        self._menu.add_item(ToggleMenuItem('Paused', callback=self.pause, default=False, buttons=[ord(' ')], button_name='SPACE'))
        self._menu.add_item(ToggleMenuItem('Line 1', callback=self.toggle_line, buttons=[ord('1')], button_name='1'))
        self._menu.add_item(ToggleMenuItem('Line 2', callback=self.toggle_line, buttons=[ord('2')], button_name='2'))
        self._menu.add_item(ToggleMenuItem('Line 3', callback=self.toggle_line, buttons=[ord('3')], button_name='3'))
        self._menu.add_item(ToggleMenuItem('Line 4', callback=self.toggle_line, buttons=[ord('4')], button_name='4'))
        self._menu.add_item(ToggleMenuItem('Line 5', callback=self.toggle_line, buttons=[ord('5')], button_name='5'))
        self._menu.add_item(ToggleMenuItem('Line 6', callback=self.toggle_line, buttons=[ord('6')], button_name='6'))
        self._menu.add_item(ToggleMenuItem('Line 7', callback=self.toggle_line, buttons=[ord('7')], button_name='7'))
        self._menu.add_item(ToggleMenuItem('Line 8', callback=self.toggle_line, buttons=[ord('8')], button_name='8'))
        self._menu.add_item(ToggleMenuItem('Line 9', callback=self.toggle_line, buttons=[ord('9')], button_name='9'))

        self._menu.add_item(ToggleMenuItem('Fit all', default=fit_all, buttons=[ord('a')], button_name='a'))
        self._menu.add_item(ToggleMenuItem('Autorange left y', default=autorange_left_y))
        self._menu.add_item(ToggleMenuItem('Autorange right y', default=autorange_right_y))

        self._menu.add_item(MenuItem('Menu', hidden=True, callback=self._menu.on_activated, buttons=[ord(':')], button_name=':'))

        self._menu_items = MenuItemBaseClass.items

        # menu item state (program state) can be accessed through this dict
        self.state = MenuItemBaseClass.state

        # create Data object and set initial screen width
        # this object holds all the bins that represent screen cols
        self._data = Data()

        # create x axis
        if x_axis_type == 'datetime':
            self._x_axis = HorizontalDatetimeAxis(label_color='white')
        else:
            self._x_axis = HorizontalAxis(label_color='white', decimals=x_decimals)

        # convert window/bin_window to timestamp if axis is datetime
        if window:
            window = self.get_td_timestamp(window) if x_axis_type == 'datetime' else window
            self._state_x_bin_window = window / self._backend.get_plot_cols()
        elif bin_window:
            self._state_x_bin_window = self.get_td_timestamp(bin_window) if x_axis_type == 'datetime' else bin_window
        else:
            if x_axis_type == 'datetime':
                self._state_x_bin_window = self.get_td_timestamp(datetime.timedelta(days=1))
            else:
                self._state_x_bin_window = 10

        # set default that will be used when resetting
        self._default_x_bin_window = self._state_x_bin_window
        self._data.set_bin_window(self._state_x_bin_window)

        # create actor objects
        self._left_y_axis  = VerticalAxis(self._x_axis, orientation='left',  label_color='white', decimals=left_decimals)
        self._right_y_axis = VerticalAxis(self._x_axis, orientation='right', label_color='white', decimals=right_decimals)
        self._grid         = Grid(chr_between_lines=self._x_axis._chr_per_tick)
        self._legend       = Legend()
        self._last_values  = LastValues()
        self._status_line  = StatusLine()

        # hold a copy of all line objects
        self._lines = []

        # watch for new data and call self.draw()
        self._watch_thread = WatchThread(self)

        # listen to queue for user input events
        self.event_queue = Queue()
        self._input_thread = ListenInputThread(stdscr, self._menu_items, self.event_queue)

    def reset_data(self):
        """ Reset all lines, points and bins """
        self._data = Data()
        self._data.set_bin_window(self._state_x_bin_window)

        for line in self._lines:
            line.reset()
            line.set_data_obj(self._data)

    def get_td_timestamp(self, td):
        """ Convert timedelta to timestamp """
        now = datetime.datetime.now()
        return (now + td).timestamp() - now.timestamp()

    def add_line(self, line, orientation='left'):
        """ Create a new line object """
        # create and return a line object
        line.set_data_obj(self._data)

        # x axis contains all lines because the axis is shared
        self._x_axis.add_line(line)

        if orientation == 'right':
            self._right_y_axis.add_line(line)
        else:
            self._left_y_axis.add_line(line)

        self._legend.add_line(line, orientation)
        self._last_values.add_line(line, orientation)
        self._lines.append(line)
        return line

    def remove_line(self, line):
        self._x_axis.remove_line(line)
        self._lines.remove(line)

    def start_threads(self):
        """ Start watch and input threads """
        #self._watch_thread.start()
        self._input_thread.start()

    def stop_threads(self):
        """ Stop watch and input threads """
        logger.debug("Stopping threads")
        self._watch_thread.stop()
        self._input_thread.stop()

        #logger.debug("Waiting for watch thread to join")
        #self._watch_thread.join()
        logger.debug("Waiting for input thread to join")
        self._input_thread.join()
        logger.debug("Done!")

    def handle_input_queue(self, queue):
        """ Check queue for events created by input thread.
            Return True is there were events. """
        has_input = not queue.empty()
        while not queue.empty():
            inp_opt = queue.get()
            inp_opt.on_activated()
            self.draw()
        return has_input

    def has_new_data(self):
        return True in [line.is_updated() for line in self._lines]

    def draw(self):
        """ Draw plot on screen """
        self._backend.clear()

        # recalculate y data dimensions
        if self.state['fit all'].state:
            self._data.set_window_all(self._backend.get_plot_cols())
            self._backend.update_ly_col_width(self._left_y_axis.get_col_width(self._backend, self._data))
            self._backend.update_ry_col_width(self._right_y_axis.get_col_width(self._backend, self._data))
            self._backend.init_display()
            self._left_y_axis.set_data_dimensions(self._backend, self._data)
            self._right_y_axis.set_data_dimensions(self._backend, self._data)

        if self.state['autorange left y'].state:
            self._left_y_axis.set_data_dimensions(self._backend, self._data)
        if self.state['autorange right y'].state:
            self._right_y_axis.set_data_dimensions(self._backend, self._data)

        # update all dimensions and paddings and what not
        self._backend.update_ly_col_width(self._left_y_axis.get_col_width(self._backend, self._data))
        self._backend.update_ry_col_width(self._right_y_axis.get_col_width(self._backend, self._data))
        self._backend.init_display()

        if self.state['show grid'].state:
            self._grid.draw(self._backend, self._data)

        self._left_y_axis.draw_lines(self._backend, self._data)
        self._right_y_axis.draw_lines(self._backend, self._data)
        self._x_axis.draw(self._backend, self._data)
        self._left_y_axis.draw(self._backend, self._data)
        self._right_y_axis.draw(self._backend, self._data)

        if self.state['show legend'].state:
            self._legend.draw(self._backend)

        if self.state['show statusline'].state:
            self._status_line.clear()
            self._status_line.set('l_offset',  self._backend._l_offset)
            self._status_line.set('r_offset',  self._backend._r_offset)
            self._status_line.set('bin_window',  self._state_x_bin_window)
            self._status_line.set('x_zoom_unit', self.state['x zoom unit'].menu_entry)
            self._status_line.set('fit_all',     self.state['fit all'].state)
            self._status_line.set('autorange_left_y', self.state['autorange left y'].state)
            self._status_line.set('autorange_right_y', self.state['autorange right y'].state)
            if self.state['paused'].state:
                self._status_line.set(None, 'paused')
            self._status_line.draw(self._backend)

        if self.state['show last values'].state:
            self._last_values.draw(self._backend)

        self._backend.refresh()

    def plot(self):
        # handle user input queue
        if self.handle_input_queue(self._input_thread.queue):
            lock.wait_for_lock(name='input queue draw')
            self.draw()
            lock.release_lock()

        lock.wait_for_lock(name='plot')
        # redraw if terminal is resized
        if self._backend.check_resized():
            self.draw()

        if self.state['paused'].state:
            lock.release_lock()
            return

        if self.has_new_data():
            self.draw()
        else:
            self._backend.refresh()
        lock.release_lock()


class PlotApp(Plot):
    """ Subclass this class to create a plot application.
        Override update() to get new data every self._update_interval """
    def __init__(self, *args, update_interval=5, **kwargs):
        Plot.__init__(self, *args, **kwargs)

        # interval between calls to update callback
        self._update_interval = update_interval

        # indicate stopped state
        self._stopped = False
        self._menu.add_item(MenuItem('Quit', callback=self.quit_callback, buttons=[ord('q')], button_name='q'))

        # thread will check callback periodically
        self._update_thread = UpdateThread(self.check_update, self._update_interval)

    def is_stopped(self):
        """ Check if status is stopped """
        return self._stopped

    def quit_callback(self, inp_opt, args):
        self._stopped = True

    def sleep(self, seconds):
        """ Sleep that will not blocking program flow """
        t_last = datetime.datetime.utcnow()
        while (t_last + datetime.timedelta(seconds=seconds)) > datetime.datetime.utcnow():
            if self._stopped:
                return

            self.plot()
            time.sleep(0.1)

    def start(self):
        self._input_thread.start()
        self._update_thread.start()

        while not self._stopped:
            try:
                self.sleep(self._update_interval)
            except KeyboardInterrupt:
                break

        self._input_thread.stop()
        self._update_thread.stop()

    def check_update(self):
        #lock.wait_for_lock(name='plotapp update', debug=True)
        self.update()
        #lock.release_lock()
