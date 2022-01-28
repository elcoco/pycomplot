
class Matrix_bak():
    """ Handles all the graph drawing stuff """
    def __init__(self, x_axis, left_y_axis, right_y_axis, x_size=None, y_size=None):
        # physical size of terminal
        self._term_x_size = os.get_terminal_size().columns if x_size == None else x_size
        self._term_y_size = os.get_terminal_size().lines if y_size == None else y_size

        # list of lists representing all plot coordinates matrix[y][x]
        self._matrix = []

        # axis objects
        self._x_axis = x_axis
        self._ly_axis = left_y_axis
        self._ry_axis = right_y_axis

        # offset from borders of terminal (axis, labels, legend etc...)
        self._l_offset = self._ly_axis.get_col_width(self._term_y_size)
        self._r_offset = self._ry_axis.get_col_width(self._term_y_size)
        self._t_offset = 0
        self._b_offset = self._x_axis.get_row_height()

        # full matrix
        self._matrix_x_size = self._term_x_size
        self._matrix_y_size = self._term_y_size

        # dimensions of plot without axis, legends etc...
        self._plot_width  = self._matrix_x_size - self._l_offset - self._r_offset
        self._plot_height = self._matrix_y_size - self._t_offset - self._b_offset

        # create matrix
        self._matrix = [['' for c in range(self._matrix_x_size)] for r in range(self._matrix_y_size)]

    def set_point_in_plot(self, x, y, char):
        x = x + self._l_offset
        y = y + self._b_offset
        self.set_char(x, y, char)

    def set_col_in_plot(self, x, col):
        """ Set a column in the plot area """
        x += self._l_offset
        for i,row in enumerate(col):
            y = self._b_offset + i
            self.set_char(x, y, col[i])

    def set_char(self, x, y, char):
        """ Set a character in the plot area """
        try:
            self._matrix[y][x] = char
        except IndexError as e:
            class_name = inspect.stack()[1][0].f_locals['self'].__class__.__name__
            method_name = inspect.stack()[1][3]
            print(f"[{class_name}.{method_name}] {e}: [x:y] {x},{y},{char}")

    def get_matrix_cols(self):
        if self.get_matrix_rows():
            return len(self._matrix[0])
        else:
            return 0

    def get_matrix_rows(self):
        return len(self._matrix)

    def get_plot_cols(self):
        return self._plot_width

    def get_plot_rows(self):
        return self._plot_height

    def display(self):
        for row in reversed(self._matrix):
            for pos in row:
                if pos:
                    print(pos, end='')
                else:
                    print(' ', end='')
            print()



def draw_lines_bak(self, backend, window=None):
    """ Draw points in lines in backend object """
    x_min = self.get_x_min(window)
    x_max = self.get_x_max(window)
    y_min = self.get_y_min(window)
    y_max = self.get_y_max(window)

    # TODO because glitches aint pretty, points and interpolation should not be done over and over again.
    #      it is much easier on the eyes if we don't see things changing all the time
    # TODO when an update is done, do update in steps, not all at once so we can update more fluiently
    #      eg. when more than one point is added make a step for every x, not multiple x at once

    # save coordinates of last point
    last_x = None
    last_y = None

    for line in self._lines:
        points = line.get_range(window)

        # for every point within window, try to interpolate
        for i,point in enumerate(points):

            # if not first
            if i > 0:

                # get last point, for interpolation
                point0 = points[i-1]

                # get coordinates in matrix
                x0 = self.get_scaled_x(point0.x, x_min, x_max, backend.get_plot_cols())
                y0 = self.get_scaled_y(point0.y, y_min, y_max, backend.get_plot_rows())
                x1 = self.get_scaled_x(point.x, x_min, x_max, backend.get_plot_cols())
                y1 = self.get_scaled_y(point.y, y_min, y_max, backend.get_plot_rows())

                # if points are on same column, no need to interpolate
                if x0 == x1:
                    continue

                # if first iteration, set to point0
                last_x = x0
                last_y = y0

                # x interpolate between datapoints (x0,y0) and (x1,y1)
                for x,y in self.x_interpolate(x0, y0, x1, y1):
                    backend.set_point_in_plot(x, y, line.char, fg_color=line.color)

                    # Y interpolate points that are next to eachother on x axis
                    for x_fill,y_fill in self.y_interpolate(last_x, last_y, x, y):
                        backend.set_point_in_plot(x_fill, y_fill, line.char, fg_color=line.color)

                    # save coordinates of last interpolated point
                    last_x = x
                    last_y = y

                # also y interpolate from last inbetween point up to data point
                for x_fill,y_fill in self.y_interpolate(last_x, last_y, x1, y1):
                    backend.set_point_in_plot(x_fill, y_fill, line.char, fg_color=line.color)

                # set datapoint
                backend.set_point_in_plot(x1, y1, point.line.char, fg_color=point.line.color)

            else:
                x_scaled = self.get_scaled_x(point.x, x_min, x_max, backend.get_plot_cols())
                y_scaled = self.get_scaled_y(point.y, y_min, y_max, backend.get_plot_rows())
                backend.set_point_in_plot(x_scaled, y_scaled, point.line.char, fg_color=point.line.color)

class Grid(Shared):
    def __init__(self, x_axis, window, char='.', chr_between_lines=10):
        self._positions = []
        self._chr_between_lines = chr_between_lines
        self._char = char
        self._color = 'blue'
        self._x_axis = x_axis
        self._window = window

    def draw(self, backend):
        tickers = self._x_axis.get_x_ticks_new(backend, self._window, self._chr_between_lines, tickers=self._x_axis.tickers)

        # check if data is available
        if tickers == None:
            return

        self._x_axis.tickers = tickers

        for tick in tickers:
            backend.set_col_in_plot(tick["position"], [self._char] * (backend.get_plot_rows()), fg_color='blue')


class HorizontalDatetimeAxis_bak(HorizontalAxisBaseClass):
    def __init__(self, *args, **kwargs):
        HorizontalAxisBaseClass.__init__(self, *args, **kwargs)
        self._chr_per_tick = 16

        # height of axis in lines
        self._row_height = 3

    def get_labels(self, backend, window):
        data_min = self.get_x_min(window)
        data_max = self.get_x_max(window)
        data_span = data_max - data_min
        plot_size = backend.get_plot_cols()

        fractions, offset = self.get_fractions(backend, self._chr_per_tick)

        # get first line with dates
        labels = [round((x*data_span)+data_min, 2) for x in fractions]

        date_labels = [datetime.datetime.fromtimestamp(label).strftime('%Y-%m-%d') for label in labels]
        time_labels = [datetime.datetime.fromtimestamp(label).strftime('%M:%H:%S') for label in labels]

        date_line = self.get_spreaded_labels(date_labels, plot_size, len(fractions))
        time_line = self.get_spreaded_labels(time_labels, plot_size, len(fractions))

        # center
        date_line = offset + date_line
        time_line = offset + time_line

        return date_line, time_line

    def get_x_ticks(self, backend, window):
        data_min = self.get_x_min(window)
        data_max = self.get_x_max(window)
        data_span = data_max - data_min
        plot_size = backend.get_plot_cols()

        fractions, offset = self.get_fractions(backend, self._chr_per_tick)

        # get first line with dates
        xs = [round((x*data_span)+data_min, 2) for x in fractions]
        return xs


    def draw(self, backend, window):
        """ Draw axis in backend """
        symbols = self.get_label_symbols(backend)
        dates, times = self.get_labels(backend, window)

        if not self.last_ticks:
            self.last_ticks = self.get_x_ticks(backend, window)
            logger.debug(self.last_ticks)

        for i,c in enumerate(symbols):
            x = i + backend._l_offset
            # NOTE y=1 for status line
            y = 1
            backend.set_char(x, y+2, c, fg_color=self._label_color)

        for i,c in enumerate(dates):
            x = i + backend._l_offset
            backend.set_char(x, y+1, c, fg_color=self._text_color)

        for i,c in enumerate(times):
            x = i + backend._l_offset
            backend.set_char(x, y+0, c, fg_color=self._text_color)

class HorizontalAxis(HorizontalAxisBaseClass):
    def __init__(self, *args, **kwargs):
        HorizontalAxisBaseClass.__init__(self, *args, **kwargs)

        # height of axis in lines
        self._row_height = 2

    def get_labels(self, backend):
        data_min = self.get_x_min()
        data_max = self.get_x_max()
        data_span = data_max - data_min
        plot_size = backend.get_plot_cols()

        fractions, offset = self.get_fractions(backend, self._chr_per_tick)
        labels = [round((x*data_span)+data_min, 2) for x in fractions]
        labels = self.get_spreaded_labels(labels, plot_size, len(fractions))
        return labels

    def draw(self, backend):
        symbols = self.get_label_symbols(backend)
        labels = self.get_labels(backend)

        for i,c in enumerate(symbols):
            x = i + backend._l_offset
            backend.set_char(x, 1, c)

        for i,c in enumerate(labels):
            x = i + backend._l_offset
            backend.set_char(x, 0, c)


class Shared():
    def get_fractions(self, matrix, chr_between_tick, orientation='left'):
        """ Create a list of centered fractions with an offset
            Because ascii does not allow us to arange tickers the way it would fit best
            we have to create a division that fits best and center that.
            Left and right there will be an offset.
            This method calculates these centered fractions and returns the offset
            |..x...x...x...x...x..]
        """
        plot_size = matrix.get_plot_cols()

        # calculate numbers below ticker
        n_ticks = int(plot_size / chr_between_tick) + 1

        # calculate the amount of characters that are on the right that do not fit withing tickers
        rest = plot_size - ((n_ticks-1) * chr_between_tick) -1

        # calculate percent of rest from plot
        perc = rest / plot_size

        # get centered fractions and calculate offset
        fractions = self.calculate_fractions_left(n_ticks, offset=perc)

        offset = int((rest/2)) * [' ']
        return fractions, offset

    def calculate_fractions_right(self, amount, offset=0):
        total = 1 - offset
        return [ ((total/(amount-total))*i) + offset for i in range(amount) ]

    def calculate_fractions_left(self, amount, offset=0):
        total = 1 - offset
        return [ ((total/(amount-total))*i) for i in range(amount) ]

    def calculate_fractions_centered(self, amount, offset=0):
        total = 1 - offset
        return [ ((total/(amount-total))*i) + offset/2 for i in range(amount) ]

    def get_x_ticks(self, backend, window, step, tick_start=None):
        """ Return list of dicts containing values/col position, starting from tick_start.
            Space ticks n cols appart by defining step.
            If tick_start is None, start from beginning of window. """
        data_min = self.get_x_min(window)
        data_max = self.get_x_max(window)
        data_span = data_max - data_min
        plot_size = backend.get_plot_cols()

        # if tick start does not exist yet, create first tick on window start
        if tick_start == None:
            tick_start = data_min

        # exit when no data is within window
        if data_span == 0:
            return

        # get location of first ticker
        pos_tick_start = math.floor(self.map_value(tick_start, data_min, data_max, 0, plot_size-1))

        # save ticker x values here
        tickers = []

        # if pos is still in window
        if pos_tick_start >= 0:
            tick = {}
            tick["position"] = pos_tick_start
            tick["value"] = tick_start
            tickers.append(tick)

        # start finding ticker x values starting from pos_tick_start
        counter = 0
        for pos in range(pos_tick_start+1, plot_size):
            counter += 1

            # if tick is not within window, do not return
            if pos < 0:
                continue

            if counter % step == 0:
                tick = {}
                tick["position"] = pos
                tick["value"] = self.map_value(pos, 0, plot_size-1, data_min, data_max)
                tickers.append(tick)

        return tickers

    def get_x_ticks_new(self, backend, window, step, tickers={}):
        """ Return list of dicts containing values/col position, starting from tick_start.
            Space ticks n cols appart by defining step.
            If tick_start is None, start from beginning of window. """
        data_min = self.get_x_min(window)
        data_max = self.get_x_max(window)
        data_span = data_max - data_min
        plot_size = backend.get_plot_cols()

        # exit when no data is within window
        if data_span == 0:
            return

        # save returnable tickers here
        ret_tickers = []

        # keep ticker that are still within window, update positions
        for ticker in tickers:
            if data_min < ticker["value"] < data_max:
                ticker["position"] = math.floor(self.map_value(ticker["value"], data_min, data_max, 0, plot_size-1))
                ret_tickers.append(ticker)

        # start searching for new tickers at last known ticker
        if not tickers:
            tick_start = data_min
        else:
            tick_start = tickers[-1]["value"]

        # get location of first ticker
        pos_tick_start = math.floor(self.map_value(tick_start, data_min, data_max, 0, plot_size-1))

        # start finding ticker x values starting from pos_tick_start
        counter = 0
        for pos in range(pos_tick_start+1, plot_size):
            counter += 1

            # if tick is not within window, do not return
            if pos < 0:
                continue

            if counter % step == 0:
                tick = {}
                tick["position"] = pos
                tick["value"] = self.map_value(pos, 0, plot_size-1, data_min, data_max)
                ret_tickers.append(tick)

        return ret_tickers


def find_peaks2(self, bin_containers, look_back=4, look_ahead=4, n_cluster=4, change=0.0005):
    """ Find peaks in a list of bin containers
        LOOK_BACK: amount of cols to look back to find peak
        LOOK_AHEAD: amount of cols to look ahead to find peak
        N_CLUSTER: allowed cols inbetween peaks and still be considered a cluster
        CHANGE: percentage of change (difference) before calling it a peak
    """
    out = {}        # store highest points for every found cluster here
    cluster = {}    # tmp dict to store cluster in
    dropped = {}    # store dropped peaks from cluster here

    # last index counter
    last_i = 0


    # start with a smoothened curve
    ys = [bc.get_bin(self).get_max() for bc in bin_containers ]
    length = len(bin_containers) -1
    length = length -1 if (length % 2) == 0 else length
    ys_filtered = savgol_filter(ys, length, 10)

    for i,y1 in enumerate(ys_filtered):

        # don't go out of range of list
        if i < look_back or i > (len(bin_containers) - look_ahead - 1):
            continue

        # get previous, current and next bin containers
        b0 = bin_containers[i - look_back].get_bin(self)
        b1 = bin_containers[i].get_bin(self)
        b2 = bin_containers[i + look_ahead].get_bin(self)

        y0 = ys_filtered[i - look_back]
        y2 = ys_filtered[i + look_ahead]

        # skip when no data
        if b0.get_max() == None:
            continue
        if b1.get_max() == None:
            continue
        if b2.get_max() == None:
            continue

        # calculate minimum difference before calling it a peak
        #min_diff = b1.get_max() * change

        #logger.debug(min_diff)
        #logger.debug(b1.get_max() - min_diff)

        # find peaks
        #if b0.get_max() < (b1.get_max() - min_diff) > b2.get_max():
        if y0 < y1 > y2:

            # check if it is not a consecutive point to see if our cluster is full
            if (i - last_i) > n_cluster:

                # dict must contain data
                if len(cluster) > 0:

                    # start with first k,v in sub dict
                    biggest_x, biggest_b = next(iter(cluster.items()))

                    # find biggest value in sub list
                    for x,b in cluster.items():
                        if b.get_max() > biggest_b.get_max():
                            biggest_x = x
                            biggest_b = b
                        else:
                            dropped[x] = b

                    out[biggest_x] = biggest_b

                    if len(cluster)-1 > 0:
                        logger.debug(f"Dropping {len(cluster)-1} peaks")

                    # reset
                    cluster = {}

            cluster[i] = b1
            last_i = i
    return out, dropped

def find_peaks(self, bin_containers, smoothing=5):
    """ Find peaks in denoised data.
        To denoise data a savgol filter is used.
        A maximum is calculated from data points found between two valleys.
        smoothening: savgol filter smoothing factor. """

    # start with a smoothened curve
    ys = [bc.get_bin(self).get_max() for bc in bin_containers ]
    length = len(bin_containers)
    length = length -1 if (length % 2) == 0 else length
    ys_filtered = savgol_filter(ys, length, smoothing)

    last_point = None   # last peak object
    ascending = None    # indicate direction
    peaks = []          # buffer to store all points in a peak in
    out = []            # store highest points for every found cluster here
    dropped = []        # the peaks that didn't make it :(

    for i, y in enumerate(ys_filtered):
        b = bin_containers[i].get_bin(self)
        point = Peak(i, y, b)

        if last_point == None:
            last_point = point
            continue

        if ascending == None:
            ascending = last_point.y_filtered < point.y_filtered
            continue

        # we are at top of peak, direction changed from ascending --> descending
        if ascending and last_point.y_filtered > point.y_filtered:
            ascending = False

        # we are at bottom, direction changed from descending --> ascending
        elif not ascending and last_point.y_filtered < point.y_filtered:
            ascending = True

            # find biggest value in our peak buffer and add this one to the out list
            if peaks:
                out.append(max(peaks, key=lambda x:x.bin.get_max()))
                peaks = []

            dropped.append(point)

        # if this is at the end of line, add to out
        elif not ascending and i == (len(ys_filtered) - 1):
            if peaks:
                out.append(max(peaks, key=lambda x:x.bin.get_max()))

        peaks.append(point)
        last_point = point

    return out, dropped


class State(dict):
    """ Keep track of state in program, option to reset to default state """
    def __init__(self):
        """ Keep track of states and handle reset to defaults """
        self._state = {}
        self._defaults = {}

    def __str__(self):
        return str(self._state)

    def __getitem__(self, k):
        return self._state[k]

    def __setitem__(self, k, v):
        """ if state doesn't exist yet, create and set v as default value """
        if not k in self._state.keys():
            self._defaults[k] = v
        self._state[k] = v

    def set_default(self, k, v):
        self._defaults[k] = v

    def reset(self, k):
        self._state[k] = self._defaults[k]
        return self._state[k]

    def toggle(self, k):
        self._state[k] = not self._state[k]


class UserInput():
    def __init__(self, name, buttons, button_name, callback):
        self.name = name
        self.buttons = buttons
        self.button_name = button_name
        self.callback = callback


def show_help(self, inp_opt):
    """ Show help window """
    longest = max(len(str(x.button_name)) for x in self._input_opts) + 1
    width = max(len(str(f"{opt.button_name.ljust(longest)} {opt.name}")) for opt in self._input_opts) + 4
    height = len(self._input_opts) + 4
    x_pos = int((self._backend.get_cols() - width) / 2)
    y_pos = int((self._backend.get_rows() - height) / 2)

    win = curses.newwin(height, width, y_pos, x_pos)

    win.addstr(1, 2, f"Keys:")
    for y, opt in enumerate(self._input_opts, 3):
        win.addstr(y, 2, f"{opt.button_name.ljust(longest)} {opt.name}")

    win.refresh()
    c = win.getch()
    del win


def list_bins(self, amount):
    """ List n amount of bin for debugging purposes """
    for i,bc in enumerate(self.get_bin_containers(amount)):
        logger.debug(f"{i}: {bc.start} - {bc.end}")


def get_grouped_from_end(self, group_size, end, amount):
    """ Return groups, starting from end position """
    end_key   = self.get_index_key(end)
    start_key = int(end_key - (group_size * amount))
    return self.get_grouped(group_size, start_key, end_key, amount)


def get_grouped_bak(self, group_size, start_key, end_key, amount):
    """ Return list of group object that contain data
        Groups have a start and end value that corresponds with the index
        $group_size specifies the key spacing, not index spacing
    """
    # use cache if possible
    metadata = {'start_key' : start_key,
                'end_key'   : end_key,
                'amount'    : amount,
                'group_size': group_size}

    groups = self._cache.get(metadata, dt=self._last_update)
    if groups:
        return groups

    if (group_size % self._index_spread) != 0:
        raise ValueError(f"Group size {group_size} is not compatible with current index spread {self._index_spread}")
    elif not self.has_data():
        logger.error("No data in index")
        return []

    # get sorted list containing key/values from index
    # NOTE this is takes up most resources and is cached, refreshes when new data is added
    keys, values = self.get_keys_values(updated=self._is_updated)
    
    try:
        end_i = self.get_index_by_key(end_key)
    except ValueError:
        print(f"End key ({end_key}) out of index bounds [{self._index_start_key}:{self._index_end_key}]")
        return []

    start_i = end_i - (amount)

    # calculate index offset from last data point
    # used to calculate group count
    # BUG when calculating groups from end, it is easy to always have last data in view but
    #     since groups are calculated starting from the right, the plot becomes very noisy when zoomed.
    #     this is because taking averages from groups that keep changing doesn't give reliable results

    # calculate amount of groups from start to start_i
    offset = int(start_i / int(group_size/self._index_spread))

    groups = []

    # traverse index $group_size sized steps and take slices for every group
    for count in range(amount):
        group_end_i   = end_i - (count * int(group_size/self._index_spread))
        group_start_i = group_end_i - int(group_size/self._index_spread)
        group_end_key   = keys[group_end_i]

        if group_end_i < 0:
            # no data available yet
            logger.error(f"Right side group index below 0, {group_end_i} < 0")
            group_start_key = None
            group_end_key = None
            buckets = []

        elif group_start_i < 0:
            # first group is not complete yet, since we don't wanna wait till period of first group is complete, display anyways
            logger.error(f"Left side group index below 0, {group_start_i} < 0")
            group_start_key = None
            buckets = values[0:group_end_i]

        else:
            # slice all buckets for this group
            buckets = values[group_start_i:group_end_i]
            group_start_key = keys[group_start_i]

        # join data in buckets
        data = {name : {} for name in self._columns}
        for bucket in buckets:
            for col in self._columns:
                data[col].update(bucket.get(col, {}))

        count = amount - 1 - count + offset
        groups.insert(0, Group(group_start_key, group_end_key, data, count))

    self._cache.add(metadata, groups)
    self.display_groups(groups)
    return groups

