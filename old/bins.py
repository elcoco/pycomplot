#!/usr/bin/env python3

import time
import logging
import math
import datetime

from complot.utils import timeit
from complot.data_indexer import IndexedData

logger = logging.getLogger('complot')


class Bins():
    """ The Bins() class holds multiple Bincontainer() objects.
        The Bincontainer() objects represent one column on the screen and can contain multiple Bin() objects for every line.

        The idea is that if you want to request all containers that fit on the screen you can do for example:

            # get containers for display
            containers = Bins.get_bin_containers(plot_width)

            # grab first container, corresponding to the first column on screen
            container = containers[0]

            # get bin for line_obj
            bin = container.get_bin(line_obj)

            # print out x,y
            print(container.x)
            print(bin.y)
        """

    def __init__(self):
        self._bin_containers = []

        # length of one bin in float or float timestamp
        self._bin_window = None

        # all points in plot, used to regenerate all bins
        self._points = []

        # last end position when getting data from bins
        self._last_start_position = None
        self._last_end_position = None

        self._keep_position = False
        self._offset = 0

        # an bin_container index to our bcs to find them quicker
        self._bc_index = {}

        # the interval inbetween indices
        self._bc_index_interval = 100

    def adjust_offset(self, amount, plot_width):
        """ Set offset, influences what is returned by get_bin_containers().
            Is used for panning """
        if self._last_end_position + self._offset + amount > (plot_width - 1):
            self._offset += amount

    def keep_position(self):
        """ Don't move on updates, influences what is returned by get_bin_containers().
            Is used for panning """
        self._keep_position = True

    def forget_position(self):
        """ Reset position """
        self._keep_position = False
        self._offset = 0

    def set_window_all(self, plot_width):
        """ Set window to display all data """
        if len(self._bin_containers) < 2:
            logger.error("ERROR: not enough data to set window to all")
            return
        oldest = self._bin_containers[0].get_x_min()
        newest = self._bin_containers[-1].get_x_max()

        if oldest == None or newest == None:
            logger.error("ERROR: unknown error")
            return

        window = newest - oldest
        self._bin_window = window / plot_width
        logger.debug(f"Setting bin window to: {self._bin_window}")

    def set_bin_window(self, window):
        """ Set the width (time/float) of one column """
        self._bin_window =  window

    @timeit
    def sort_bins(self, points):
        # if we sort first, updating is much faster
        return sorted(points, key=lambda x: x.x)

    @timeit
    def regenerate_bins(self):
        """ When a resize occures or the window is changed, also the time per bin/column changes.
            We need to regenerate all bins to make sure the data is represented correctly """
        logger.debug(f"regenerating: containers={len(self._bin_containers)}, points={len(self._points)}")

        # reset index
        self._bc_index = self.build_index(self._bin_containers, self._bc_index_interval)
        
        # if we sort first, updating is much faster
        points = self.sort_bins(self._points)

        # reset lists
        self._bin_containers = []
        self._points = []

        for point in points:
            self.add_point(point)

    def get_bin_containers(self, amount):
        """ Get slices of self._bin_containers
            If amount==None, return all containers
            self._offset decides the offset for the slice that is returned, used for panning """
        if amount == None:
            return self._bin_containers
        elif self._keep_position:
            # panning
            start = self._last_end_position - amount + self._offset
            start = start if start >= 0 else 0
            return self._bin_containers[start:start+amount]
        else:
            self._last_start_position = len(self._bin_containers) - amount
            self._last_end_position   = len(self._bin_containers)
            return self._bin_containers[-amount:]

    def get_y_min(self, amount, lines):
        """ Get the minimum bin y value for lines for last n amount of bins, if lines=None, return for all lines """
        lines = [line for line in lines if line.is_enabled()]
        ymin = [bc.get_y_min(lines) for bc in self.get_bin_containers(amount)]
        return min([y for y in ymin if y != None], default=None)

    def get_y_max(self, amount, lines):
        """ Get the maximum bin y value for lines for last n amount of bins, if lines=None, return for all lines """
        lines = [line for line in lines if line.is_enabled()]
        ymax = [bc.get_y_max(lines) for bc in self.get_bin_containers(amount)]
        return max([y for y in ymax if y != None], default=None)

    def list_bins(self, amount):
        """ List n amount of bin for debugging purposes """
        for i,bc in enumerate(self.get_bin_containers(amount)):
            logger.debug(f"{i}: {bc.start} - {bc.end}")

    def build_index(self, bcs, interval):
        index = {}

        i   = 0

        while True:
            try:
                index[bcs[i].start] = i
            except IndexError:
                return index

            i += interval

    def find_in_index(self, x, bcs, index):
        x_prev = None
        i_prev = None

        for x_start, i in index.items():

            if x_prev == None:
                x_prev = x_start
                i_prev = i
                continue

            if not (x_prev < x < x_start):
                continue

            for bc in bcs[i_prev:]:
                if bc.start <= x < bc.end:
                    return bc

            x_prev = x_start
            i_prev = i

    def add_point(self, point):
        """ Add point to a bin. If bin doesn't exist yet, create. """
        # TODO create bin index dict so we can access our bins quicker
        # keep points in list, these are needed for regeneration
        self._points.append(point)

        # check if it's the first container
        if not self._bin_containers:
            bin_start = point.x
            bin_end = bin_start + self._bin_window

            # create bin container and bin
            bc = BinContainer(bin_start, bin_end)
            self._bin_containers.append(bc)
            b = bc.get_bin(point.line)
            b.add_point(point)

            # reset index
            self._bc_index = self.build_index(self._bin_containers, self._bc_index_interval)
        

        # check if value is bigger than biggest container
        elif point.x >= self._bin_containers[-1].end:
            # start with last container
            bc = self._bin_containers[-1]

            # keep creating containers until it accepts our point which means it is the right one
            while True:
                try:
                    # create bin container and bin
                    bin_start = bc.end
                    bin_end = bin_start + self._bin_window
                    bc = BinContainer(bin_start, bin_end)
                    self._bin_containers.append(bc)
                    b = bc.get_bin(point.line)
                    b.add_point(point)

                    # reset index
                    self._bc_index = self.build_index(self._bin_containers, self._bc_index_interval)
        
                    break
                except ValueError:
                    pass

        # check if point.x is smaller than smallest container
        elif point.x < self._bin_containers[0].start:
            bc = self._bin_containers[0]
            while True:
                try:
                    # create bin container and bin
                    bin_end = bc.start
                    bin_start = bin_end - self._bin_window
                    bc = BinContainer(bin_start, bin_end)
                    self._bin_containers.insert(0,bc)
                    b = bc.get_bin(point.line)
                    b.add_point(point)

                    # reset index
                    self._bc_index = self.build_index(self._bin_containers, self._bc_index_interval)
                    break
                except ValueError:
                    pass

        else:
            bc = self.find_in_index(point.x, self._bin_containers, self._bc_index)
            if bc == None:
                logger.error("Failed to find bincontainer")
            else:
                b = bc.get_bin(point.line)
                b.add_point(point)

            ## find suitable existing container
            #for bc in reversed(self._bin_containers):
            #    if bc.start <= point.x < bc.end:
            #        b = bc.get_bin(point.line)
            #        b.add_point(point)
            #        break

class BinContainer():
    """ Store bins in here, bin containers store one bin for each line """
    counter = 0

    def __init__(self, start, end):
        self._bins = {}
        self._index = BinContainer.counter

        # counter to help determin where ticks should go
        BinContainer.counter += 1

        # start and end x values for all bins in this container
        self.start = start
        self.end = end

        # x axis value for all bins in this container
        self.x = start + ((end - start) / 2)

        # datetime representation of x
        self.dt = datetime.datetime.fromtimestamp(self.x)
        self.date = self.dt.strftime('%Y-%m-%d')
        self.time = self.dt.strftime('%H:%M:%S')

    def get_x_min(self):
        """ Get oldest x """
        oldest = None
        for l,b in self._bins.items():
            for p in b.points:
                if oldest == None:
                    oldest = p.x
                elif p.x < oldest:
                    oldest = p.x
        return oldest

    def get_x_max(self):
        """ Get newest x """
        newest = None
        for l,b in self._bins.items():
            for p in b.points:
                if newest == None:
                    newest = p.x
                elif p.x > newest:
                    newest = p.x
        return newest

    def get_y_max(self, lines):
        """ Return max for lines """
        return max([b.get_max() for l,b in self._bins.items() if (b.get_max() != None and l in lines)], default=None)

    def get_y_min(self, lines):
        """ Return min for lines """
        return min([b.get_min() for l,b in self._bins.items() if (b.get_min() != None and l in lines)], default=None)

    def add_bin(self, line, b):
        """ Add a bin object to this container """
        self._bins[line] = b

    def is_tick(self, amount):
        return self._index % amount == 0

    def get_bin(self, line):
        """ find or create Bin() object that fits value """
        if not line in self._bins.keys():
            b = line.create_bin(self.start, self.end)
            self.add_bin(line, b)
            return b
        return self._bins.get(line, None)


class Bin():
    """ Keep points here, bins are groups of points within a certain x period.
        They represent one column in matrix
        This is calculated by: screen_x/screen_cols
        It contains an average y value.
        """
    def __init__(self, start, end):
        # contains averages for points in this bin, is updated when a point is added
        self.y = None
        self.points = []
        self._start = start
        self._end = end

    @property
    def value(self):
        """ Return value from this Bin """
        return self.y

    def get_min(self):
        """ Return lowest value. For this bin it is y but other bins may have multiple values """
        return self.y

    def get_max(self):
        """ Return highest value. For this bin it is y but other bins may have multiple values """
        return self.y

    def get_avg(self, values):
        return sum(values) / len(values)

    def add_point(self, point):
        """ Raise ValueError if point is out of the scope of this bin """
        if self._start <= point.x < self._end:
            self.points.append(point)

            # recalculate x,y for this bin
            self.y = self.get_avg([point.y for point in self.points])
        else:
            raise ValueError


class CandleStickBin():
    """ Keep bins here, bins are groups of points within a certain x period.
        They represent one column in matrix
        This is calculated by: screen_x/screen_cols
        It contains an average y value.

        """
    def __init__(self, start, end):
        # contains averages for points in this bin, is updated when a point is added
        self.close = None
        self.open = None
        self.high = None
        self.low = None

        self.points = []
        self._start = start
        self._end = end

    @property
    def value(self):
        """ Return value from this Bin, for this bin it is close but for other bins it may be Y """
        return self.close

    def get_min(self):
        return self.low

    def get_max(self):
        return self.high

    def get_avg(self, values):
        return sum(values) / len(values)

    def get_oldest(self):
        return next(p for p in self.points if p.x == min(p.x for p in self.points))

    def get_newest(self):
        return next(p for p in self.points if p.x == max(p.x for p in self.points))

    def add_point(self, point):
        """ Raise ValueError if point is out of the scope of this bin """
        if self._start <= point.x < self._end:
            self.points.append(point)

            self.open = self.get_oldest().open
            self.close = self.get_newest().close
            self.high = max([point.high for point in self.points])
            self.low = min([point.low for point in self.points])
        else:
            raise ValueError
