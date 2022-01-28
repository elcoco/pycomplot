#!/usr/bin/env python3

import logging

logger = logging.getLogger('complot')


class StatusLine():
    """ Representation of the status line """
    def __init__(self, row=0):
        self._status = {}
        self._row = row

    def set(self, k, v):
        """ Set a status field """
        self._status[k] = v

    def clear(self):
        """ Clear all statusses """
        self._status = {}

    def draw(self, backend):
        """ Draw status line """
        x_counter = 0

        for i,(k,v) in enumerate(self._status.items(), 1):
            divider = "" if i == len(self._status) else " | "
            if k == None:
                status = f"{v}{divider}"
            else:
                status = f"{k}: {v}{divider}"

            for c in status:
                if x_counter == (backend.get_cols()-1):
                    return

                backend.set_char(x_counter, self._row, c, fg_color='red')
                x_counter += 1


class Grid():
    def __init__(self, char='.', chr_between_lines=16):
        self._chr_between_lines = chr_between_lines
        self._char = char
        self._color = 'blue'

    def is_tick(self, bin_count):
        return (bin_count % self._chr_between_lines) == 0

    def draw(self, backend, bins):
        last_tick_col = None
        col = None

        for col,b in  enumerate(bins.get_bins(backend.get_plot_cols())):
            if self.is_tick(b.count):
                backend.set_col_in_plot(col, [self._char] * (backend.get_plot_rows()), fg_color='blue')
                last_tick_col = col

        # abort in case of no data
        if col == None or last_tick_col == None:
            return

        # when there is not enough data to draw all gridlines, fill in all lines anyway
        while col < backend.get_plot_cols()-1:
            if self.is_tick(col-last_tick_col):
                backend.set_col_in_plot(col, [self._char] * (backend.get_plot_rows()), fg_color='blue')
            col += 1


class Legend():
    def __init__(self):
        self._left_lines = []
        self._right_lines = []

    def add_line(self, line, orientation='left'):
        if orientation == 'left':
            self._left_lines.append(line)
        else:
            self._right_lines.append(line)

    def draw(self, backend):
        x = 0
        y = backend.get_rows() -1

        for i,line in enumerate(self._left_lines):
            if line.is_hidden():
                continue
            x = backend.set_string(x, y, line.icon, fg_color=line.color)
            x = backend.set_string(x, y, f" = {line.name} [{line.line_number}]")

            if i != len(self._left_lines)-1:
                x = backend.set_string(x, y, f", ")

        x = backend.get_cols() -1
        for i,line in enumerate(reversed(self._right_lines)):
            if line.is_hidden():
                continue
            x = backend.set_string(x, y, f" = {line.name} [{line.line_number}]"[::-1], right_to_left=True)
            x = backend.set_string(x, y, line.icon[::-1], fg_color=line.color, right_to_left=True)

            if i != len(self._right_lines)-1:
                x = backend.set_string(x, y, f", "[::-1], right_to_left=True)


class LastValues():
    """ Show the last Y values for every line in plot """
    def __init__(self):
        self._left_lines = []
        self._right_lines = []

    def add_line(self, line, orientation='left'):
        if orientation == 'left':
            self._left_lines.append(line)
        else:
            self._right_lines.append(line)

    def draw(self, backend):
        x = backend._l_offset
        y = backend.get_rows() - 2 - backend._t_offset

        for i,line in enumerate(self._left_lines + self._right_lines):
            for k,v in line.get_last_value().items():
                symbol = line.symbol if line.symbol != None else ''

                # don't add symbol to x value
                if k.startswith('x'):
                    symbol = ''

                backend.set_string(x, y, str(f"{k} {v}{symbol}"), fg_color=line.color, reverse=True, skip_bg=True)
                y -= 1
