#!/usr/bin/env python3

import time
import logging
import math
import datetime
import random
from itertools import cycle
from pprint import pprint, pformat

# for find peaks to smoothen data
from scipy.signal import savgol_filter

from complot.utils import timeit

# import global lock
from complot import lock

logger = logging.getLogger('complot')


class LineBaseClass():
    """ Stores all datapoints and metadata belonging to a line.
        Is instantiated by Plot() """
    colors = cycle([ 'green',
                     'blue',
                     'red',
                     'cyan',
                     'yellow',
                     'magenta',
                     'white' ])

    # create incrementing line numbers
    counter = 0

    def __init__(self, char='█', color=None, enabled=True, name=None, symbol=None, hidden=False):
        # symbol used when values are presented eg. %|$ etc...
        self.symbol = symbol
        self.char   = char
        self.icon   = char
        self.color  = next(Line.colors) if not color else color
        self.name   = "".join([ str(chr(round(random.uniform(65,90)))) for i in range(10)]) if not name else name
        self._is_enabled = enabled
        self._default_enabled = enabled

        # if enabled, line will not show in legend and last values
        self._hidden = hidden

        # holds point objects belonging to this line
        self._points = []

        # Data() object stores all data. bins that represent one column are retrieved by using the get_bins() method
        # they represent one column in matrix
        self._data = None

        # indicate if new data is available
        self._is_updated = False

        LineBaseClass.counter += 1
        self._line_number = LineBaseClass.counter

    def is_hidden(self):
        """ Don't show line in legend et al """
        return self._hidden

    def toggle_enabled(self):
        self._is_enabled = not self._is_enabled

    def set_default_enabled(self):
        self._is_enabled = self._default_enabled

    def set_enabled(self):
        self._is_enabled = True

    def is_enabled(self):
        return self._is_enabled
    
    @property
    def line_number(self):
        return self._line_number

    def set_data_obj(self, data):
        """ Add the Bins object to line object so Line can access indexed data, this is done in the Plot.add_line() method """
        self._data = data

    def reset(self):
        """ Reset line data """
        self._points = []
        self._is_updated = True
        self.set_default_enabled()

    def is_populated(self):
        """ Check if points exist in this line """
        return len(self._points)

    def is_updated(self):
        """ Check updated flag, is set in add_point() method """
        if self._is_updated:
            self._is_updated = False
            return True

    def y_interpolate(self, x0, y0, x1, y1):
        """ Interpolate two points in the Y direction """
        points = []

        # calc how many ys need to be filled
        y_len = y1 - y0

        # line is ascending
        if y_len > 0:

            # if ys are not on the same line
            if y_len > 1:
                for y_fill in range(y0+1, y1):
                    points.append([x1, y_fill])

        # line is decending
        elif y_len < 0:
            if y_len < -1:
                for y_fill in range(y1+1, y0):
                    points.append([x1, y_fill])

        return points

    def x_interpolate(self, x0, y0, x1, y1):
        """ Interpolate two points in the X direction """
        points = []

        # calculate grow factor between points: y = xd + y
        d = (y1 - y0) / (x1 - x0)

        # calculate how many xs we need to interpolate
        x_len = x1 - x0

        # calculate x,y for inbetween points (x0,y0) and (x1,y1)
        for x in range(1,x_len):
            x += x0
            y = (x - x0) * d + y0

            x = math.floor(x)
            y = math.floor(y)

            points.append([x, y])
        return points

    def interpolate(self, x0, y0, x1, y1):
        """ interpolate points """
        points = []

        # on first iteration, set to point0
        last_x = x0
        last_y = y0

        # check if xs inbetween bin_containers are missing
        if (x1 - x0 -1) > 0:

            # x interpolate between databins (b0.x,b0.y) and (b1.x,b1.y)
            for x,y in self.x_interpolate(x0, y0, x1, y1):
                points.append([x,y])

                # Y interpolate points that are next to eachother on x axis
                for x_fill,y_fill in self.y_interpolate(last_x, last_y, x, y):
                    points.append([x_fill,y_fill])

                # save coordinates of last interpolated point
                last_x = x
                last_y = y

        # also y interpolate from last inbetween point up to data point
        for x_fill,y_fill in self.y_interpolate(last_x, last_y, x1, y1):
            points.append([x_fill,y_fill])

        points.append([x1,y1])
            
        return points

    def get_scaled_y(self, y, y_min, y_max, matrix_size):
        """ Scale a value to the plot dimensions """
        return int(self.map_value(y, y_min, y_max, 0, matrix_size-1))

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

    def add_point(self, x, y, name=None):
        """ Add point to line, this will trigger a Plot.draw() action by UpdateThread """
        lock.wait_for_lock(name='add_point')

        point = Point(x, y, self, name=name)

        self._points.append(point)
        self._data.add_point(point)

        # set new data flag
        self._is_updated = True

        lock.release_lock()

        if len(self._points) % 500 == 0:
            logger.debug(f"[{self.name}] Processed {len(self._points)} points")

    def get_last_value(self):
        """ used by LastValues actor to display last values """
        if not len(self._points):
            return {}

        return self._points[-1].get_values()


class Line(LineBaseClass):
    """ Class for normal line """
    def __init__(self, *args, interpolate=True, **kwargs):
        LineBaseClass.__init__(self, *args, **kwargs)
        self._interpolate = interpolate
        self.icon = '∿'

    def draw(self, backend, data, y_min, y_max):
        # save last index so we can check if we need to interpolate
        last_valid_bin_index = None
        bins = data.get_bins(backend.get_plot_cols())

        for x1,b1 in enumerate(bins):
            b1_y = b1.get_avg(self.name, key='y')

            # if b1 does not contain data, skip
            if b1_y == None:
                continue

            # scale b1_y to plot rows
            y1 = self.get_scaled_y(b1_y, y_min, y_max, backend.get_plot_rows())

            if not self._interpolate:
                if backend.is_in_plot_area(y1):
                    backend.set_point_in_plot(x1, y1, self.char, fg_color=self.color)
                continue

            # if this is the first valid index, draw point and skip
            if last_valid_bin_index == None:

                # when autorange is off, don't draw points outside of plot area
                if backend.is_in_plot_area(y1):
                    last_valid_bin_index = x1
                    backend.set_point_in_plot(x1, y1, self.char, fg_color=self.color)
                continue

            b0 = bins[last_valid_bin_index]

            x0 = last_valid_bin_index
            last_valid_bin_index = x1

            # scale b0.y to plot rows
            b0_y = b0.get_avg(self.name, key='y')
            y0 = self.get_scaled_y(b0_y, y_min, y_max, backend.get_plot_rows())

            for x,y in  self.interpolate(x0, y0, x1, y1):
                if backend.is_in_plot_area(y):
                    backend.set_point_in_plot(x, y, self.char, fg_color=self.color)


class Arrows(LineBaseClass):
    """ Place an arrow for every point in this line """
    def __init__(self, *args, interpolate=True, **kwargs):
        LineBaseClass.__init__(self, *args, **kwargs)
        self._interpolate = interpolate
        self.icon = '<'

    def draw(self, backend, data, y_min, y_max):
        for x,b in enumerate(data):
            b_avg = b.get_avg(self.name, key='value')

            # if bin1 does not contain data, skip
            if b.is_empty(self.name):
                continue

            for point in b.get_col(self.name):
                # scale b.y to plot rows
                y = self.get_scaled_y(point.y, y_min, y_max, backend.get_plot_rows())
                lines = []
                if point.name != None:
                    lines.append(f"{self.name} [{point.name}]")
                else:
                    lines.append(self.name)
                lines.append(point.y)
                backend.set_arrow(x, y, lines, fg_color=self.color, skip_bg=True)


class CurrentValueLine(LineBaseClass):
    """ Create a horizontal line that stays on the current y value of a given line """
    def __init__(self, line, *args, length=None, **kwargs):
        LineBaseClass.__init__(self, *args, **kwargs)
        self._line = line
        self.icon = '─'
        self.char = '─'

    def is_populated(self):
        return True

    def draw(self, backend, data, y_min, y_max):
        bins = data.get_bins(1, offset=0)

        if not bins:
            return

        b = bins[-1]
        if b.is_empty(self._line.name):
            return

        p_last = b.get_last(self._line.name)
        b_avg  = b.get_avg(self._line.name, key='value')

        if p_last == None or b_avg == None:
            logger.debug("Not enough data to create current value line")
            return

        y = self.get_scaled_y(b_avg, y_min, y_max, backend.get_plot_rows())
        y = int(y)

        if not backend.is_in_plot_area(y):
            return

        backend.draw_horizontal_line(y, char=self.char, prefix=f"{p_last.value}├", fg_color=self.color)


class HorizontalLine(LineBaseClass):
    """ Create a horizontal line that stays on the current y value of a given line """
    def __init__(self, *args, y=None, **kwargs):
        LineBaseClass.__init__(self, *args, **kwargs)
        self.icon = '─'
        self.char = '─'
        self._y = y

    def is_populated(self):
        return True

    def set_y(self, y):
        self._y = float(y)

    def move_up(self, step):
        self._y += step

    def move_down(self, step):
        self._y -= step

    def draw(self, backend, bin_containers, y_min, y_max):
        if self._y == None:
            return

        y_scaled = self.get_scaled_y(self._y, y_min, y_max, backend.get_plot_rows())
        y_scaled = int(math.floor(y_scaled))

        if not backend.is_in_plot_area(y_scaled):
            return

        backend.draw_horizontal_line(y_scaled, char=self.char, prefix=f"{self._y}├", fg_color=self.color)


class PeaksDetect(LineBaseClass):
    """ Create a horizontal line that stays on the maximum y value of a given line """
    def __init__(self, line, *args, smoothing=7, **kwargs):
        LineBaseClass.__init__(self, *args, **kwargs)
        self._line = line
        self.icon = '▲'
        self._smoothing = smoothing

    def is_populated(self):
        return True

    def find_peaks(self, bins, line=None, smoothing=5):
        """ Find peaks and valleys in denoised data.
            To denoise data a savgol filter is used.
            A maximum/minimum is calculated from data points found between two valleys or peaks.
            smoothening: savgol filter smoothing factor.
            If line is specified, the calculation will be done over that line instead of self """

        if line == None:
            line = self

        # start with a smoothened curve by using a savgol filter
        ys = [b.get_max(columns=[line.name], key='high') for b in bins ]
        length = len(bins)
        length = length - 1 if (length % 2) == 0 else length

        try:
            ys_filtered = savgol_filter(ys, length, smoothing)
        except ValueError as e:
            logger.error(e)
            return [], [], []

        peak_buf   = []    # buffer to store all points in a peak in
        valley_buf = []    # buffer to store all points in a valley in
        peaks = []       # store highest points for every peak_buf here
        valleys = []       # store highest points for every peak_buf here

        for i, y in enumerate(ys_filtered):

            b = bins[i]

            # check for data
            if b.get_max(columns=[line.name], key='high') == None:
                #logger.debug(f"Peaks error max == {b.get_max(columns=[self.name], key='value')}")
                continue


            peak_buf.append(Peak(i, y, b, b.start))
            valley_buf.append(Peak(i, y, b, b.start))

            # find peaks
            if len(peak_buf) >= 3:

                p0 = peak_buf[-3]
                p1 = peak_buf[-2]
                p2 = peak_buf[-1]

                # check if we are in a valley
                if p0.y > p1.y < p2.y:
                    peaks.append(max(peak_buf, key=lambda x:x.bin.get_max(columns=[line.name], key='max')))
                    peak_buf = []

                # check if we're at end
                elif i == (len(ys_filtered) - 1):
                    peaks.append(max(peak_buf, key=lambda x:x.bin.get_max(columns=[line.name], key='max')))

            # find valleys
            if len(valley_buf) >= 3:

                p0 = valley_buf[-3]
                p1 = valley_buf[-2]
                p2 = valley_buf[-1]

                # check if we are on a peak
                if p0.y < p1.y > p2.y:
                    valleys.append(min(valley_buf, key=lambda x:x.bin.get_min(columns=[line.name], key='min')))
                    valley_buf = []

                # check if we're at end
                elif i == (len(ys_filtered) - 1):
                    valleys.append(min(valley_buf, key=lambda x:x.bin.get_min(columns=[line.name], key='min')))

        return peaks, valleys, ys_filtered

    def draw(self, backend, data, y_min, y_max):
        # find and draw peaks
        peaks, valleys, smooth = self.find_peaks(data.get_bins(backend.get_plot_cols()),
                                                 line = self._line,
                                                 smoothing = self._smoothing)
        for peak in peaks:
            y_scaled = self.get_scaled_y(peak.bin.get_max(columns=[self._line.name], key='high'), y_min, y_max, backend.get_plot_rows())
            
            if not backend.is_in_plot_area(y_scaled):
                continue

            lines = []
            lines.append(datetime.datetime.fromtimestamp(peak.x).strftime("%Y-%m-%d %H:%M:%S"))
            lines.append(peak.bin.get_max(columns=[self._line.name], key='value'))
            backend.set_arrow(peak.index, y_scaled, lines=lines, fg_color=self.color, skip_bg=True)

            
        # find and draw valleys
        for peak in valleys:
            y_scaled = self.get_scaled_y(peak.bin.get_min(columns=[self._line.name], key='low'), y_min, y_max, backend.get_plot_rows())

            if not backend.is_in_plot_area(y_scaled):
                continue

            lines = []
            lines.append(datetime.datetime.fromtimestamp(peak.x).strftime("%Y-%m-%d %H:%M:%S"))
            lines.append(peak.bin.get_min(columns=[self._line.name], key='value'))
            backend.set_arrow(peak.index, y_scaled, lines=lines, fg_color=self.color, skip_bg=True)


class HistogramLine(LineBaseClass):
    """ Class for normal line """
    def __init__(self, *args, **kwargs):
        LineBaseClass.__init__(self, *args, **kwargs)
        self.icon = 'П'

    def draw(self, backend, data, y_min, y_max):
        for x1,b in enumerate(data.get_bins(backend.get_plot_cols())):
            b_avg = b.get_avg(self.name, key='y')

            # if bin1 does not contain data, skip
            if b_avg == None:
                continue

            # scale bin1.y to plot rows
            y1 = self.get_scaled_y(b_avg, y_min, y_max, backend.get_plot_rows())

            if backend.is_in_plot_area(y1):
                last_valid_bin_index = x1
                for y in range(0, y1+1):
                    backend.set_point_in_plot(x1, y, self.char, fg_color=self.color)


class CandleStickLine(LineBaseClass):
    def __init__(self, *args, **kwargs):
        LineBaseClass.__init__(self, *args, **kwargs)
        self.icon = '┿'
        self._char_body_small = '╋'

        self._char_wick       = '┃'
        self._char_body       = '█'

        self._char_upper_half = '▀'
        self._char_lower_half = '▄'

    def add_point(self, x, Open, High, Low, Close):
        """ Add point to line, this will trigger an action in watch thread """
        lock.wait_for_lock(name='CandleStickLine')

        point = CandleStickPoint(x, Open, High, Low, Close, self)

        self._points.append(point)
        self._data.add_point(point)

        # set new data flag
        self._is_updated = True
        lock.release_lock()

        if len(self._points) % 500 == 0:
            logger.debug(f"[{self.name}] Processed {len(self._points)} points")

    def draw(self, backend, data, y_min, y_max):
        for x,b in enumerate(data.get_bins(backend.get_plot_cols())):
            if b.is_empty(self.name):
                continue

            b_open  = b.get_first(self.name).open
            b_high  = b.get_max([self.name], key='high')
            b_low   = b.get_min([self.name], key='low')
            b_close = b.get_last(self.name).close

            # if bin1 does not contain data, skip
            if b_close == None:
                continue

            # scale bin1.y to plot rows
            y_open  = self.get_scaled_y(b_open,  y_min, y_max, backend.get_plot_rows())
            y_high  = self.get_scaled_y(b_high,  y_min, y_max, backend.get_plot_rows())
            y_low   = self.get_scaled_y(b_low,   y_min, y_max, backend.get_plot_rows())
            y_close = self.get_scaled_y(b_close, y_min, y_max, backend.get_plot_rows())

            #---------- row1 highest point
            #           
            # row 1
            #           row1 lowest point
            #---------- 
            #           row0 highest point
            # row 0
            #           
            #---------- row0 lowest point

            was_green = True

            # bullish or bearish
            if b_open < b_close:
                color = 'green'
                body = range(y_open, y_close+1)
            else:
                color = 'red'
                body = range(y_close, y_open+1)

            for y in range(y_low, y_high+1):
                if backend.is_in_plot_area(y):
                    backend.set_point_in_plot(x, y, self._char_wick, fg_color=color)

            if y_open == y_close:
                if backend.is_in_plot_area(y_close):
                    backend.set_point_in_plot(x, y_close, self._char_body_small, fg_color=color)
            else:
                for i,y in enumerate(body):
                    if backend.is_in_plot_area(y):
                        backend.set_point_in_plot(x, y, self._char_body, fg_color=color)


class PointBaseClass():
    def __init__(self, x, line):
        self.is_datetime = False
        self.x = self.index_to_float(x)
        self.line = line                # link to line object

    def index_to_float(self, index):
        """ Convert any x (datetime,pandas timestamp etc...) to a float representation, because we love floats! """
        if type(index) == datetime.datetime:
            self.is_datetime = True
            return index.timestamp()
        elif str(type(index)) == "<class 'pandas._libs.tslibs.timestamps.Timestamp'>":
            self.is_datetime = True
            return index.timestamp()
        else:
            return index


class Point(PointBaseClass):
    def __init__(self, x, y, line, name=None):
        PointBaseClass.__init__(self, x, line)
        self.y = y
        self.high = y
        self.name = name

    def get_values(self):
        data = { 'x'  : datetime.datetime.fromtimestamp(self.x).strftime("%Y-%m-%d %H:%M:%S") if self.is_datetime else self.x,
                 'y'  : self.y }
        return data

    @property
    def value(self):
        # return value when going over point objects to find min/max
        return self.y

    @property
    def max(self):
        # return value when finding max values
        return self.y

    @property
    def min(self):
        # return value when finding min values
        return self.y


class CandleStickPoint(PointBaseClass):
    def __init__(self, x, Open, High, Low, Close, line):
        PointBaseClass.__init__(self, x, line)
        self.y = None
        self.open = Open
        self.high = High
        self.low = Low
        self.close = Close

    def get_values(self):
        data = { 'x'     : datetime.datetime.fromtimestamp(self.x).strftime("%Y-%m-%d %H:%M:%S") if self.is_datetime else self.x,
                 'open'  : self.open,
                 'high'  : self.high,
                 'low'   : self.low,
                 'close' : self.close }
        return data

    @property
    def value(self):
        # return value when going over point objects to find min/max
        return self.close


    @property
    def max(self):
        # return value when finding max values
        return self.high

    @property
    def min(self):
        # return value when finding min values
        return self.low


class Peak():
    """ Peak data type for peak detection class """
    def __init__(self, index, y, b, x):
        self.index = index
        self.bin = b
        self.y = y
        self.x = x
