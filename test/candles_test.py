#!/usr/bin/env python3

import curses
import time
import datetime
import logging
import random

import numpy as np

from complot.plot import PlotApp
from complot.lines import Line, CandleStickLine, HistogramLine

logger = logging.getLogger('complot')


class App(PlotApp):
    def __init__(self, stdscr):
        PlotApp.__init__( self,
                          stdscr, 
                          bin_window=datetime.timedelta(minutes=1),
                          left_decimals=5,
                          right_decimals=5,
                          x_axis_type='datetime',
                          update_interval=.5,
                          show_grid=True )


        self.l1 = CandleStickLine(name='bever')

        self.add_line(self.l1, orientation='left')


        dt = datetime.datetime.utcnow()
        last_y = 0

        highest = None
        lowest = None

        xs = np.linspace(1, 100, 1000)

        for y in range(1, 50, 5):

            if last_y == None:
                last_y = y
                continue

            self.l1.add_point(dt, last_y, y, last_y, y)
            last_y = y

            dt += datetime.timedelta(minutes=1)

        for y in range(1, 50, 5):
            y = 50 - y

            if last_y == None:
                last_y = y
                continue

            self.l1.add_point(dt, last_y, y, last_y, y)
            last_y = y

            dt += datetime.timedelta(minutes=1)
        self.start()


    def get_sine(self, x):
        return np.sin(x) + np.random.normal(scale=1, size=len(x))

    def get_stock(self, x):
        y = 0
        result = []
        for _ in x:
            result.append(y)
            y += np.random.normal(scale=1)
        return np.array(result)

    def get_running_mean(self, x, N):
        return np.convolve(x, np.ones((N,))/N)[(N-1):]

    def update(self):
        pass


if __name__ == "__main__":
    curses.wrapper(App)
