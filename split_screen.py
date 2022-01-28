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

from complot import logger
from complot.plot import PlotApp, Plot
from complot.lines import Line, CandleStickLine, HistogramLine


class PlotWin(Plot):
    def __init__(self, win):
        Plot.__init__( self,
                       win, 
                       bin_window=datetime.timedelta(minutes=1),
                       left_decimals=5,
                       right_decimals=5,
                       x_axis_type='datetime',
                       show_grid=True )


class App():
    def __init__(self, stdscr):
        term_y_size, width = stdscr.getmaxyx()
        height = int(term_y_size/2)

        win1 = stdscr.subwin(height, width, 0, 0)
        win2 = stdscr.subwin(height, width, height, 0)

        pw1 = PlotWin(win1)
        pw2 = PlotWin(win2)


        l1 = Line(name='dirty sine')
        l2 = Line(name='nice sine')
        l3 = Line(interpolate=False)

        pw1.add_line(l1, orientation='left')
        pw2.add_line(l2, orientation='left')
        pw2.add_line(l3, orientation='right')

        for i in range(0,100000, 60):
            l1.add_point(i, 3*i)
            l2.add_point(i, i**3)
            l3.add_point(i, i**2)

            pw1.plot()
            pw2.plot()

            time.sleep(.1)
        
        time.sleep(5000)



if __name__ == "__main__":
    os.environ.setdefault('ESCDELAY', '25')
    curses.wrapper(App)
