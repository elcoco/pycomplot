#!/usr/bin/env python3

import curses
import inspect
import logging

logger = logging.getLogger('complot')


class CursesColors():
    """ Generate color pairs and provide method to get the right pair index by fg/bg colors """
    def __init__(self):
        self._color_mapping = {}
        self._color_mapping['red']     = curses.COLOR_RED
        self._color_mapping['green']   = curses.COLOR_GREEN
        self._color_mapping['yellow']  = curses.COLOR_YELLOW
        self._color_mapping['blue']    = curses.COLOR_BLUE
        self._color_mapping['magenta'] = curses.COLOR_MAGENTA
        self._color_mapping['cyan']    = curses.COLOR_CYAN
        self._color_mapping['white']   = curses.COLOR_WHITE
        self._color_mapping['black']   = 8

        self.init_colors()

    def init_colors(self):
        index = 1

        for fg_name,fg_c in self._color_mapping.items():
            for bg_name,bg_c in self._color_mapping.items():
                curses.init_pair(index, fg_c, bg_c)
                index += 1

    def get_pair(self, fg, bg):
        index = 1

        for fg_name,fg_c in self._color_mapping.items():
            for bg_name,bg_c in self._color_mapping.items():
                if fg_name == fg and bg_name == bg:
                    return index
                index += 1


class CursesBackend():
    """ This backend takes care of the plot drawing in an ncurses matrix """
    def __init__(self, stdscr, x_size=None, y_size=None):
        # curses screen object
        self._stdscr = stdscr

        # init color pairs
        self._colors = CursesColors()

        # paint background default terminal colors
        self._stdscr.bkgd(' ', curses.color_pair(self._colors.get_pair('white', 'black')))

        # turn off cursor
        curses.curs_set(False)

        # is updated with update_ly_col_width, update_ry_col_width
        self.ly_axis_col_width = 0
        self.ry_axis_col_width = 0

        self.init_display()

    def update_ly_col_width(self, width):
        self.ly_axis_col_width = width

    def update_ry_col_width(self, width):
        self.ry_axis_col_width = width

    def init_display(self):
        """ initialize all window and plot dimensions """
        self._old_rows, self._old_cols = self._stdscr.getmaxyx()
        self._term_y_size, self._term_x_size = self._stdscr.getmaxyx()
        self._term_y_size -= 0
        self._term_x_size -= 0

        status_row = 1
        legenda_row = 1
        plot_padding = 1
        x_axis_height = 2

        # offset from borders of terminal (axis, labels, legend etc...)
        self._l_offset = self.ly_axis_col_width + plot_padding
        self._r_offset = self.ry_axis_col_width + plot_padding
        self._t_offset = legenda_row
        self._b_offset = x_axis_height + status_row

        # dimensions of plot without axis, legends etc...
        self._plot_width  = self._term_x_size - self._l_offset - self._r_offset
        self._plot_height = self._term_y_size - self._t_offset - self._b_offset

        # used to determin the chars and colors on a coordinate so we know how to draw over them
        self._color_matrix = [['' for x in range(self.get_cols())] for y in range(self.get_rows())]
        self._char_matrix = [['' for x in range(self.get_cols())] for y in range(self.get_rows())]

    def get_char(self, x, y):
        y = self._term_y_size - y -1
        return chr(self._stdscr.inch(y, x) & 0xFF).strip(' ')

    def draw_horizontal_line(self, y, *args, char='─', prefix=None, draw_on_top=False, **kwargs):
        """ Draw a line, don't draw over existing chars if draw_on_top==False """
        y_matrix = self._term_y_size - y -1
        y_matrix = y_matrix - self._b_offset

        for x in range(self.get_plot_cols()):
            x_matrix = x + self._l_offset
            if self._char_matrix[y_matrix][x_matrix] == '█':
                self.set_point_in_plot(x, y, char, *args, **kwargs)
            elif not self._char_matrix[y_matrix][x_matrix] or draw_on_top:
                self.set_point_in_plot(x, y, char, *args, **kwargs)

        if prefix:
            self.set_string_in_plot(0, y, str(prefix), **kwargs)

    def set_arrow(self, x, y, lines=None, left_arrow='◀ ', right_arrow=' ▶', **kwargs):
        """ Place a string next to a point in plot, place on left or right side depending on position
            When multiple lines are specified in lines list, display below each other"""
        # calculate max string length
        longest = max([len(left_arrow) + len(str(line)) for line in lines])

        for i,line in enumerate(lines):
            # don't place an array symbol on other lines than the first
            if i > 0:
                left_arrow, right_arrow = ' '*len(left_arrow), ' '*len(right_arrow)

            if self.get_plot_cols()-1 < x + longest:
                string = f"{line}{right_arrow}".rjust(longest)
                x_start = x - longest
            else:
                string = f"{left_arrow}{line}"
                x_start = x + 1

            for z, c in enumerate(string, x_start):
                # if line is below plot area, put line above
                if y-i < 0:
                    self.set_point_in_plot(z, y+i, c, **kwargs)
                else:
                    self.set_point_in_plot(z, y-i, c, **kwargs)

    def set_col_in_plot(self, x, col, **kwargs):
        """ Set a column in the plot area """
        x += self._l_offset
        for i,row in enumerate(col):
            y = self._b_offset + i
            self.set_char(x, y, col[i], **kwargs)

    def set_point_in_plot(self, x, y, char, **kwargs):
        x = x + self._l_offset
        y = y + self._b_offset
        self.set_char(x, y, char, **kwargs)

    def set_string_in_plot(self, x, y, *args, **kwargs):
        x = x + self._l_offset
        y = y + self._b_offset
        self.set_string(x, y, *args, **kwargs)

    def set_string(self, x, y, string, right_to_left=False, **kwargs):
        for i,c in enumerate(string):
            if right_to_left:
                self.set_char(x-i, y, c, **kwargs)
            else:
                self.set_char(x+i, y, c, **kwargs)
        if right_to_left:
            return x - len(string)
        else:
            return x + len(string)

    def set_status(self, string):
        self.set_string(0, 0, str(string), fg_color='red')

    def set_char(self, x, y, char, fg_color='white', bg_color='black', reverse=False, dim=False, skip_bg=False):
        """ Draw character in plot
            if skip_bg==True, don't get background color from line beneath """
        y = self._term_y_size - y -1

        # save color in matrix so other lines can write on top while using their fg color as bg color
        #logger.debug(f"{y}  :  {x}")
        if not skip_bg and self._color_matrix[y][x]:
            if fg_color != self._color_matrix[y][x]:
                bg_color = self._color_matrix[y][x]

        args = 0
        pair = self._colors.get_pair(fg_color, bg_color)
        args |= curses.color_pair(pair)

        if reverse:
            args |= curses.A_REVERSE
        if dim:
            args |= curses.A_DIM

        try:
            self._stdscr.addch(y, x, char, args)
            
        except curses.error as e:
            logger.error(f"ERROR: Failed to set point: {x},{y} '{char}'")

        # save color in color matrix so we can use its fg color later as bg color when drawing lines on top
        if char == '█':
            self._color_matrix[y][x] = fg_color

        self._char_matrix[y][x] = char

    def get_cols(self):
        if self.get_rows():
            return self._term_x_size
        else:
            return 0

    def get_rows(self):
        return self._term_y_size

    def get_plot_cols(self):
        return self._plot_width

    def get_plot_rows(self):
        return self._plot_height

    def refresh(self):
        self._stdscr.refresh()

    def clear(self):
        self._stdscr.clear()

    def check_resized(self):
        if (self._old_rows , self._old_cols) != self._stdscr.getmaxyx():
            self._old_rows, self._old_cols = self._stdscr.getmaxyx()
            curses.resizeterm(*self._stdscr.getmaxyx())
            self.init_display()
            return True

    def is_in_plot_area(self, value):
        return 0 <= value <= (self.get_plot_rows()-1)

    def get_user_input(self, x, y, msg=None):
        """ Get user input """
        y_calc = self._term_y_size - y -1
        curses.curs_set(True)
        self._stdscr.move(y_calc, x)
        self._stdscr.clrtoeol()
        self.set_string(x, y, f"{msg}: ")
        self.refresh()
        sub = self._stdscr.subwin(1, 50, y_calc, len(msg) + 2)
        tb = curses.textpad.Textbox(sub)
        tb.edit()
        curses.curs_set(False)
        self.refresh()
        return tb.gather().strip()

    def convert_point_to_plot(self, x, y):
        """ translate terminal coordinates to plot coordinates """
        return x - self._l_offset, y - self._b_offset

    def select_point(self, x_pos=None, y_pos=None, callback=None, cursor_chr='█'):
        """ Move cursor around screen and select point with enter, $callback is called to update screen when specified """
        X,Y = 0,1

        if None in [x_pos, y_pos]:
            cursor = [int(self.get_plot_cols()/2), int(self.get_plot_rows()/2)]
        else:
            cursor = [x_pos, y_pos]

        self.set_point_in_plot(*cursor, cursor_chr)

        while True:
            key = self._stdscr.getch()

            if key in [curses.KEY_LEFT, ord('h')]:
                cursor[X]  = cursor[X] - 1 if cursor[X] != 0 else 0
            elif key in [curses.KEY_RIGHT, ord('l')]:
                cursor[X]  = cursor[X] + 1 if cursor[X] != self.get_plot_cols()-1 else self.get_plot_cols()-1
            elif key in [curses.KEY_UP, ord('k')]:
                cursor[Y]  = cursor[Y] + 1 if cursor[Y] != self.get_plot_rows()-1 else self.get_plot_rows()-1
            elif key in [curses.KEY_DOWN, ord('j')]:
                cursor[Y]  = cursor[Y] - 1 if cursor[Y] != 0 else 0
            elif key == 10:
                return cursor
            elif key != -1:
                return
            else:
                continue

            # if callback is given, call it to refresh screen
            if callback:
                callback()

            self.set_point_in_plot(*cursor, cursor_chr)
            #self.refresh()
            curses.flushinp()
