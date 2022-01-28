#!/usr/bin/env python3

import time
import logging
import math
import datetime
from pprint import pformat

from complot.utils import timeit
from complot.indexer import Index

logger = logging.getLogger('complot')


class Data(Index):
    """ The Bins() class handles all data """
    def __init__(self):
        # grow index $grow_factor amount of keys when inserted key doesn't fit in index
        grow_factor = 10000

        # internal bin size in index object
        # BUG the bin size part becomes a problem when we want to have bin windows of <60
        bin_size    = 60
        Index.__init__(self, grow_factor, bin_size)

        # length of one bin in float or float timestamp
        self._bin_window = None

        self._keep_position = False
        self._show_all_data = False

        # offset, is amount of groups from last data (end), is used for panning
        self._offset = 0

    def increase_offset(self, amount, plot_width):
        """ The offset from last data, is used by get_bins(). used for panning """
        # TODO saveguard for out of bound
        self._offset += (amount * self._bin_window)

    def decrease_offset(self, amount, plot_width):
        offset = self._offset - (amount * self._bin_window)
        if offset < 0:
            self._offset = 0
        else:
            self._offset = offset

    def keep_position(self):
        """ Don't move on updates, influences what is returned by get_bin_containers().
            Is used for panning """
        self._keep_position = True

    def forget_position(self):
        """ Reset position """
        self._keep_position = False
        self._offset = 0

    def set_window_all(self, plot_width):
        """ Get all data """
        self._show_all_data = True

    def set_bin_window(self, window):
        """ Set the width (time/float) of one column """
        self._bin_window =  window

    def get_bins(self, amount, offset=None):
        if offset == None:
            offset = self._offset

        if self._keep_position:
            return self.get_grouped_from_last_data(int(self._bin_window), amount, offset=offset)
        if self._show_all_data:
            return self.get_all_grouped(amount)
        else:
            return self.get_grouped_from_last_data(int(self._bin_window), amount)

    def get_y_min(self, amount, lines):
        """ Get the minimum bin y value for lines for last n amount of bins, if lines=None, return for all lines """
        lines = [line.name for line in lines if line.is_enabled()]
        ymin = [group.get_min(columns=lines, key='min', use_avg=True) for group in self.get_bins(amount)]
        return min([y for y in ymin if y != None], default=None)

    def get_y_max(self, amount, lines):
        """ Get the maximum bin y value for lines for last n amount of bins, if lines=None, return for all lines """
        lines = [line.name for line in lines if line.is_enabled()]
        ymax = [group.get_max(lines, key='max', use_avg=True) for group in self.get_bins(amount)]
        return max([y for y in ymax if y != None], default=None)

    def add_point(self, point):
        """ Add point to index """
        self.insert(point.line.name, point.x, point)
