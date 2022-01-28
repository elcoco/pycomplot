#!/usr/bin/env python3

import curses
import time
import datetime
import logging

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
                          update_interval=.01,
                          show_grid=True )

        self.l1 = Line(name='dirty sine')
        self.l2 = Line(name='nice sine')
        self.l3 = Line(interpolate=False)

        self.add_line(self.l1, orientation='left')
        self.add_line(self.l2, orientation='right')
        self.add_line(self.l3, orientation='right')

        self.xs = np.linspace(1, 100, 110000)
        self.sine = self.get_sine(self.xs)
        self.mean = self.get_running_mean(self.sine, 100)
        self.stock = self.get_stock(self.xs)

        self.counter = 0
        self.t_last = datetime.datetime.utcnow()

        self.start()

    def get_sine(self, x):
        return np.sin(x) + np.random.normal(scale=0.1, size=len(x))

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

        self.l1.add_point(self.t_last, self.sine[self.counter])
        self.l2.add_point(self.t_last, self.mean[self.counter])
        self.l3.add_point(self.t_last, self.sine[self.counter] + 3)
        self.t_last += datetime.timedelta(minutes=1)
        self.counter += 1

if __name__ == "__main__":
    curses.wrapper(App)
