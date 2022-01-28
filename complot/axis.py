#!/usr/bin/env python3

import logging
import datetime

logger = logging.getLogger('complot')


class HorizontalAxisBaseClass():
    """ Baseclass for all X axis """
    def __init__(self, label_color='white', text_color='white', decimals=1):
        self._chr_per_tick = 10

        # round n amount of decimals when not datetime
        self._decimals = decimals

        # store line objects here
        self._lines = []

        # height of axis in lines, override in child
        self._row_height = 2

        # color of labels
        self._label_color = label_color

        # color of text
        self._text_color = text_color

    def get_row_height(self):
        return self._row_height

    def add_line(self, line):
        """ Add a line to this axis """
        self._lines.append(line)

    def is_tick(self, bin_count):
        return (bin_count % self._chr_per_tick) == 0

    def remove_line(self, line):
        self._lines.remove(line)


class HorizontalAxis(HorizontalAxisBaseClass):
    def __init__(self, *args, **kwargs):
        HorizontalAxisBaseClass.__init__(self, *args, **kwargs)

    def draw(self, backend, data):
        for col,b in enumerate(data.get_bins(backend.get_plot_cols())):
            if self.is_tick(b.count):
                for i,c in enumerate(str(round(b.start, self._decimals))):
                    pos = col + i + backend._l_offset
                    if pos > backend.get_cols()-1:
                        break
                    backend.set_char(pos, 1, c, fg_color=self._label_color)


class HorizontalDatetimeAxis(HorizontalAxisBaseClass):
    """ Draws datetime tickers """
    def __init__(self, *args, **kwargs):
        HorizontalAxisBaseClass.__init__(self, *args, **kwargs)
        self._chr_per_tick = 16

        # height of axis in lines
        self._row_height = 3

    def ts_to_date(self, ts):
        try:
            return datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
        except TypeError:
            return ""

    def ts_to_time(self, ts):
        try:
            return datetime.datetime.fromtimestamp(ts).strftime('%H:%M:%S')
        except TypeError:
            return ""

    def draw(self, backend, data):
        for col,b in enumerate(data.get_bins(backend.get_plot_cols())):
            if self.is_tick(b.count):
                for i,c in enumerate(self.ts_to_date(b.start)):
                    pos = col + i + backend._l_offset
                    if pos > backend.get_cols()-1:
                        break
                    backend.set_char(pos, 1, c, fg_color=self._label_color)

                for i,c in enumerate(self.ts_to_time(b.start)):
                    pos = col + i + backend._l_offset
                    if pos > backend.get_cols()-1:
                        break
                    backend.set_char(pos, 2, c, fg_color=self._label_color)


class VerticalAxis():
    """ Baseclass for the two vertical (Y) axis """
    def __init__(self, x_axis, orientation='left', label_color='blue', decimals=2):
        # minimum amount of characters inbetween ticks, will count upwards to fit
        self._chr_per_tick = 1

        # width of column in chars, is determined after get_labels()
        self._col_width = 0

        # color of labels
        self._label_color = label_color

        # store line objects here
        self._lines = []

        # reference to the x axis object that is shared among the axis
        self._x_axis = x_axis

        # data dimensions, set by self.set_data_dimensions()
        self._y_min = None
        self._y_max = None

        # round y column labels to n decimals
        self._decimals = decimals

        self._orientation = orientation

    def map_value(self, value, a_min, a_max, b_min, b_max):
        """ Map/scale one range to another """
        # Figure out how 'wide' each range is
        a_span = a_max - a_min
        b_span = b_max - b_min

        try:
            # Convert the left range into a 0-1 range (float)
            value_scaled = float(value - a_min) / float(a_span)
        except ZeroDivisionError:
            return  0

        # Convert the 0-1 range into a value in the right range.
        return b_min + (value_scaled * b_span)

    def add_line(self, line):
        """ Add line to this axis """
        self._lines.append(line)

    def get_scaled_y(self, y, y_min, y_max, matrix_size):
        """ Scale a value to the plot dimensions """
        return int(self.map_value(y, y_min, y_max, 0, matrix_size-1))

    def set_data_dimensions(self, backend, data):
        self._y_min = data.get_y_min(backend.get_plot_cols(), lines=self._lines)
        self._y_max = data.get_y_max(backend.get_plot_cols(), lines=self._lines)

    def set_zoom(self):
        # calculate positive factor
        if self._y_min == None or self._y_max == None:
            return
        y_max_factor = (self._y_max - self._y_min) / 10

        #y_max_factor = abs(self._y_max_last * factor)
        self._y_min += y_max_factor
        self._y_max -= y_max_factor

    def set_unzoom(self):
        if self._y_min == None or self._y_max == None:
            return
        # calculate positive factor
        y_max_factor = (self._y_max - self._y_min) / 10
        #y_max_factor = abs(self._y_max_last * factor)
        self._y_min -= y_max_factor
        self._y_max += y_max_factor

    def set_pan_up(self):
        if self._y_min == None or self._y_max == None:
            return

        y_max_factor = (self._y_max - self._y_min) / 10
        self._y_min += y_max_factor
        self._y_max += y_max_factor
        logger.debug(f"{self._y_min} :: {self._y_max}")

    def set_pan_down(self):
        if self._y_min == None or self._y_max == None:
            return

        y_max_factor = (self._y_max - self._y_min) / 10
        self._y_min -= y_max_factor
        self._y_max -= y_max_factor

    def draw_lines(self, backend, data):
        """ Draw all points for all lines in backend object """
        if self._y_min == None or self._y_max == None:
            return

        for line in self._lines:
            if not line.is_enabled():
                continue

            if line.is_populated():
                line.draw(backend, data, self._y_min, self._y_max)

    def calculate_fractions(self, amount):
        return [ (1/(amount-1))*i for i in range(amount) ]

    def get_col_width(self, backend, data):
        """ Get width of Y axis """
        # if there is no data, return
        y_min = data.get_y_min(backend.get_plot_cols(), lines=self._lines)
        y_max = data.get_y_max(backend.get_plot_cols(), lines=self._lines)

        if y_min == None or y_max == None:
            return 0

        labels = self.get_labels(backend, data, y_min, y_max)
        return max(len(x) for x in labels)

    def get_labels(self, backend, data, y_min, y_max):
        """ Create the text labels for the Y axis """
        # if there is no data, return
        offset      = backend._b_offset
        matrix_size = backend.get_plot_rows()
        data_span   = y_max - y_min

        # calculate label values and convert to strings
        labels = [str(round((x*data_span)+y_min, self._decimals)) for x in self.calculate_fractions(matrix_size)]

        # calculate longest label value in str positions
        col_width = max(len(x) for x in labels)

        # justify values with zero's
        labels_just = [ list(x.ljust(col_width, '0')) for x in labels ] 

        for label in labels_just:
            for i,char in enumerate(label):
                label[i] = char

        return labels_just

    def get_last_value(self, backend, data, labels, line):
        """ Return label corresponding to line end value """
        b = data.get_bins(1, offset=0)[0]

        last_point = b.get_last(line.name)
        if not last_point:
            return
        value = last_point.value

        if value == None:
            return None

        return self.get_scaled_y(value, self._y_min, self._y_max, backend.get_plot_rows())

    def draw_left(self, backend, data):
        """ Get ticker labels and draw axis """
        if not self._lines:
            return

        if self._y_min == None or self._y_max == None:
            return

        labels = self.get_labels(backend, data, self._y_min, self._y_max)

        highlights = {}
        for line in self._lines:
            highlights[self.get_last_value(backend, data, labels, line)] = line

        # need some blank lines to compensate for x axis
        offset = backend._b_offset

        for y, label in enumerate(labels):
            if y in highlights.keys():
                for x, c in enumerate(label):
                    backend.set_char(x, y+offset, c, fg_color=highlights[y].color, reverse=True)
            else:
                for x, c in enumerate(label):
                    backend.set_char(x, y+offset, c, fg_color=self._label_color)

    def draw_right(self, backend, data):
        """ Get ticker labels and draw axis """
        if not self._lines:
            return

        if self._y_min == None or self._y_max == None:
            return

        labels = self.get_labels(backend, data, self._y_min, self._y_max)

        highlights = {}
        for line in self._lines:
            highlights[self.get_last_value(backend, data, labels, line)] = line

        # need some blank lines to compensate for x axis
        offset = backend._b_offset

        for y, label in enumerate(labels):
            if y in highlights.keys():
                color = highlights[y].color
                reverse = True
            else:
                color = self._label_color
                reverse = False

            for x, c in enumerate(reversed(label)):
                x = backend.get_cols() - x - 1
                backend.set_char(x, y+offset, c, fg_color=color, reverse=reverse)

    def draw(self, *args):
        """ Draw the axis tickers on screen """
        if self._orientation == 'left':
            self.draw_left(*args)
        else:
            self.draw_right(*args)
