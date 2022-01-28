#!/usr/bin/env python3

import logging
import threading
import time
import curses
import datetime

# import global lock
from complot import lock

logger = logging.getLogger('complot')


class WatchThread(threading.Thread):
    """ Watch data for changes, update plot on change """
    def __init__(self, plot):
        threading.Thread.__init__(self)
        self._plot = plot
        self._stopped = False

        # how often to check for new data
        self._wait_time = .05

    def stop(self):
        self._stopped = True
        logger.debug("Stopping WatchThread")

    def run(self):
        logger.debug("Starting WatchThread")
        while not self._stopped:
            lock.wait_for_lock(name='WatchThread')
            self._plot.plot()
            lock.release_lock()
            time.sleep(self._wait_time)


class UpdateThread(threading.Thread):
    """ Watch data for changes, update plot on change """
    def __init__(self, callback, interval):
        threading.Thread.__init__(self)
        self._callback = callback
        self._interval = interval
        self._stopped = False

    def stop(self):
        self._stopped = True
        logger.debug("Stopping UpdateThread")

    def non_blocking_sleep(self, seconds):
        """ Sleep that will not blocking program flow """
        t_last = datetime.datetime.utcnow()
        while (t_last + datetime.timedelta(seconds=seconds)) > datetime.datetime.utcnow():
            if self._stopped:
                return

            time.sleep(0.1)

    def run(self):
        logger.debug("Starting UpdateThread")
        while not self._stopped:
            self._callback()
            self.non_blocking_sleep(self._interval)
        logger.debug("Stopping UpdateThread... done")


class ListenInputThread(threading.Thread):
    """ Listen for user input """
    def __init__(self, stdscr, input_opts, queue):
        threading.Thread.__init__(self)
        self._stopped = False
        self._stdscr = stdscr
        self.queue = queue
        self._input_opts = input_opts

        # don't block
        self._stdscr.nodelay(1)

        # TODO this may cause flickering but makes sure we don't have to press an
        #      extra key to exit

    def stop(self):
        logger.debug("Stopping ListenInputThread")
        self._stopped = True

    def run(self):
        logger.debug("Starting ListenInputThread")
        while not self._stopped:
            lock.wait_for_lock(name='ListenInputThread')
            c = self._stdscr.getch() 
            lock.release_lock()

            for inp_opt in self._input_opts:
                if c in inp_opt.buttons:
                    logger.debug(f"Received input: {inp_opt.name}")
                    self.queue.put(inp_opt)
                    break

            curses.flushinp()
            time.sleep(0.1)

        logger.debug("Stopping ListenInputThread... done")


class UpdateStatusWindowThread(threading.Thread):
    """ Watch data for changes, update plot on change """
    def __init__(self, plot, interval):
        threading.Thread.__init__(self)
        self._plot = plot
        self._interval = interval
        self._stopped = False

    def stop(self):
        self._stopped = True
        logger.debug("Stopping UpdateStatusWindowThread")

    def non_blocking_sleep(self, seconds):
        """ Sleep that will not blocking program flow """
        t_last = datetime.datetime.utcnow()
        while (t_last + datetime.timedelta(seconds=seconds)) > datetime.datetime.utcnow():
            if self._stopped:
                return

            time.sleep(0.1)

    def update(self, win):
        out = []
        out.append("TERMINAL")
        out.append(f"term cols: {self._plot._backend.get_cols()}")
        out.append(f"term rows: {self._plot._backend.get_rows()}")
        out.append(f"plot cols: {self._plot._backend.get_plot_cols()}")
        out.append(f"plot rows: {self._plot._backend.get_plot_rows()}")
        out.append("")
        out.append("LINES")
        for line in self._plot._lines:
            out.append(f"name:   {line.name}")
            out.append(f"points: {len(line._points)}")
            out.append(f"")
        out.append(f"total points in plot: {sum(len(line._points) for line in self._plot._lines)}")

        win.erase()

        for i,l in enumerate(out):
            win.addstr(i+1, 1, l)

        win.refresh()
        self._plot._backend._stdscr.refresh()

    def run(self):
        logger.debug("Starting UpdateStatusWindowThread")
        height = 30
        width = self._plot._backend.get_cols()
        window_y_pos = self._plot._backend.get_rows() - height

        win = curses.newwin(height, width, window_y_pos, 0)
        #win.nodelay(100)

        while not self._stopped:
            self.update(win)
            self.non_blocking_sleep(self._interval)
            key = win.getch()
            if key != -1:
                break

        logger.debug("Stopping UpdateStatusWindowThread... done")
