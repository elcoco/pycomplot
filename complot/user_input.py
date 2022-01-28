#!/usr/bin/env python3

import datetime
import curses
import logging
import time
from pprint import pprint, pformat

from complot import errors_list, lock
from complot.widgets import ScrollableWindow, MenuWidget
from complot.threads import UpdateStatusWindowThread
from complot.lines import Line

logger = logging.getLogger('complot')

class InputCallbacks():
    """ Contains callbacks for menu and keypress actions """

    def pan_left(self, item, args):
        self.state['paused'].enable()
        self.state['fit all'].disable()
        self._data.keep_position()
        self._data.increase_offset(int(self.state['x pan steps'].state), self._backend.get_plot_cols())

    def pan_right(self, item, args):
        self.state['paused'].enable()
        self.state['fit all'].disable()
        self._data.keep_position()
        self._data.decrease_offset(int(self.state['x pan steps'].state), self._backend.get_plot_cols())

    def pan_up(self, item, args):
        self.state['autorange left y'].disable()
        self.state['autorange right y'].disable()
        self._left_y_axis.set_pan_up()
        self._right_y_axis.set_pan_up()

    def pan_down(self, item, args):
        self.state['autorange left y'].disable()
        self.state['autorange right y'].disable()
        self._left_y_axis.set_pan_down()
        self._right_y_axis.set_pan_down()

    def unzoom_x(self, item, args):
        self._state_x_bin_window += float(self.state['x zoom unit'].state)
        self._data.set_bin_window(self._state_x_bin_window)

    def zoom_x(self, item, args):
        if (self._state_x_bin_window - float(self.state['x zoom unit'].state)) <= 0:
            return
        self._state_x_bin_window -= float(self.state['x zoom unit'].state)
        self._data.set_bin_window(self._state_x_bin_window)

    def zoom_y(self, item, args):
        self.state['autorange left y'].disable()
        self.state['autorange right y'].disable()
        self._left_y_axis.set_zoom()
        self._right_y_axis.set_zoom()

    def unzoom_y(self, item, args):
        self.state['autorange left y'].disable()
        self.state['autorange right y'].disable()
        self._left_y_axis.set_unzoom()
        self._right_y_axis.set_unzoom()

    def pause(self, item, args):
        self._data.forget_position()

    def reset_settings(self, item, args):
        self.state['x zoom unit'].reset()
        self.state['autorange left y'].reset()
        self.state['autorange right y'].reset()
        self.state['fit all'].reset()
        self.state['x pan steps'].reset()
        self.state['show statusline'].reset()
        self.state['show grid'].reset()
        self.state['show last values'].reset()
        self.state['show legend'].reset()

        self._state_x_bin_window = self._default_x_bin_window

        self._data.forget_position()
        self._data._show_all_data = False

        for line in self._lines:
            line.set_default_enabled()

        self._data.set_bin_window(self._state_x_bin_window)

    def toggle_line(self, item, args):
        for line in self._lines:
            if str(line.line_number) == item.button_name:
                logger.debug(f"Toggling line: {line.name}")
                line.toggle_enabled()
                break

    def show_log(self, item, args):
        out = errors_list.getvalue().split('\n')
        out = [f"{len(out)-i}  {l}" for i,l in enumerate(reversed(out)) if l]
        menu = MenuWidget(self._backend._stdscr)
        menu.run(out)

    def show_status(self, item, args):
        out = []
        out.append("TERMINAL")
        out.append(f"term cols: {self._backend.get_cols()}")
        out.append(f"term rows: {self._backend.get_rows()}")
        out.append(f"plot cols: {self._backend.get_plot_cols()}")
        out.append(f"plot rows: {self._backend.get_plot_rows()}")
        out.append("")
        out.append("LINES")
        for line in self._lines:
            out.append(f"name:   {line.name}")
            out.append(f"points: {len(line._points)}")
            out.append(f"")
        out.append(f"total points in plot: {sum(len(line._points) for line in self._lines)}")

        out = list(reversed(out))
        menu = MenuWidget(self._backend._stdscr)
        menu.run(out)

    def draw_line(self, item, args):
        # NOTE many bugs here
        X,Y = 0,1
        cursor = [None, None]
        selected_chr = 'x'
        line = Line()

        options = ['Left Y axis', 'Right Y axis']
        menu = MenuWidget(self._backend._stdscr)
        result = menu.run(options)

        if result == 'Left Y axis':
            y_axis = self._left_y_axis
            self.add_line(line, orientation='left')
        elif result == 'Right Y axis':
            y_axis = self._right_y_axis
            self.add_line(line, orientation='right')
        else:
            return


        while cursor:
            lock.wait_for_lock(debug=True, name='draw_line')
            cursor = self._backend.select_point(*cursor, callback=self.draw)
            bins = self._data.get_bins(self._backend.get_plot_cols())
            lock.release_lock()

            if cursor:
                b = bins[cursor[X]]
                x = b.start

                y_min = y_axis._y_min
                y_max = y_axis._y_max
                if None in [y_min, y_max]:
                    logger.debug("No y_min and y_max")
                    continue

                y = line.map_value(cursor[Y], 0, self._backend.get_plot_rows()-1, y_min, y_max)

                if x == None:
                    logger.debug(f"No data @ {cursor[X]}")
                    continue

                logger.debug(f"adding point: {cursor} = {x}, {y}")

                line.add_point(x,y)

                self.draw()

        logger.debug(f"exzit")
        logger.debug(f"points: {line._points}")

