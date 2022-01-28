#!/usr/bin/env python3

import curses
import time
import datetime
import logging
import argparse
import os,sys

import numpy as np
import pandas as pd

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from complot.plot import PlotApp
from complot.lines import Line, CandleStickLine, HistogramLine, MaxLine, PeaksDetect, CurrentValueLine, HorizontalLine, Arrows
from complot.menu import Menu, OptionsMenuItem, MenuItem, EditableMenuItem

logger = logging.getLogger('complot')


class Callbacks():
    def add_line_callback(self, item, args):
        line = HorizontalLine(color='magenta', y=item.state, hidden=True)
        self.add_line(line, orientation='right')

        args = {}
        args['line'] = line

        set_y = EditableMenuItem(self._stdscr, line.name, callback=self.set_y_callback, dtype=float, args=args)
        set_y.on_activated()

        self.lines_menu.add_item(set_y, position=0)

        # add item to args so we can delete it later, but ugly buth yeah ¯\_(ツ)_/¯
        args['item'] = set_y
        self.remove_lines_menu.add_item(MenuItem(line.name, callback=self.remove_line_callback, args=args))

    def remove_line_callback(self, item, args):
        line = args['line']
        self.lines_menu.remove_item(args['item'])
        self.remove_lines_menu.remove_item(item)
        self.remove_line(line)

    def set_y_callback(self, item, args):
        line = args['line']
        line.set_y(item.state)

    def set_ticker_callback(self, item, args):
        """ Custom user input option """
        # NOTE this is not quickly updated, we have to wait for our sleep to end
        logger.debug(f"Setting ticker: {item.state}")
        self._ticker = item.state
        self.connect(self._ticker, self._interval, self._period)
        self.reset_data()

        self.last_pol_index = None
        self.last_df = None
        self.l3.name = self._ticker
        self.draw()

    def bin_window_callback(self, item, args):
        # TODO after setting, we have to refresh to actually show the data
        logger.debug(f"Setting interval: {item.state}")
        self._state_x_bin_window = self.get_td_timestamp(item.state)
        self._default_x_bin_window = self.get_td_timestamp(item.state)
        self.reset_data()

        self.set_interval(item.state)
        self.connect(self._ticker, self._interval, self._period)

        self.last_pol_index = None
        self.last_df = None
        self.l1.name = self._ticker
        self.draw()

    def period_callback(self, item, args):
        logger.debug(f"Setting period: {item.state}")
        self._period = item.state
        self.reset_data()
        self.connect(self._ticker, self._interval, self._period)

        self.last_pol_index = None
        self.last_df = None
        self.l1.name = self._ticker

        self.draw()

    def set_interval(self, td):
        if td == datetime.timedelta(minutes=1):
            self._interval = '1m'
        elif td == datetime.timedelta(minutes=5):
            self._interval = '5m'
        elif td == datetime.timedelta(minutes=15):
            self._interval = '15m'
        elif td == datetime.timedelta(hours=1):
            self._interval = '1h'
        elif td == datetime.timedelta(days=1):
            self._interval = '1d'
            logger.debug("Setting 1d")
        elif td == datetime.timedelta(days=7):
            self._interval = '1w'


class EventHandler(FileSystemEventHandler):
    def __init__(self, callback):
        self.callback = callback
        self.t_last = datetime.datetime.now()

    def on_modified(self, event):
        if not os.path.isfile(event.src_path):
            return
        if not event.src_path.endswith('.csv'):
            return

        # Do a bit of a delay, we want just one event per write
        if (datetime.datetime.now() - self.t_last) < datetime.timedelta(seconds=0.1):
            return
        else:
            self.t_last = datetime.datetime.now()

        logger.debug(f"Modified: {event.src_path}")
        self.callback(event.src_path)


class CSVDataSource():
    def __init__(self, path, callback):
        self.name = os.path.basename(path)
        self.path = path
        self.watchdog = self.set_watchdog()
        self.data = {}
        self.first_pass = True
        self.callback = callback

    def get_data(self, path):
        if not os.path.isfile(path):
            raise Exception(f"File doesn't exist: {path}")

        try:
            return pd.read_csv(path, index_col='Datetime', parse_dates=True)
        except pd.errors.EmptyDataError as e:
            logger.error(f"Something went wrong while reading csv file: {path}")
            logger.error(e)

    def set_watchdog(self):
        # set watchdog to update on file change
        logger.debug("Setting watchdog")
        observer = Observer()
        event_handler = EventHandler(self.update_callback)
        observer.schedule(event_handler, self.path)
        observer.start()
        return observer

    def update_callback(self, path, force=False):
        filename = os.path.basename(path)

        # on first modification
        if not filename in self.data.keys():
            df = self.get_data(path)
            if df is None:
                return
            if not df.empty:
                logger.debug(f"[{self.name}] Received new data, rows={len(df.index)}")
                self.data[filename] = df
                self.callback(filename, df)
            return

        src_df = self.data[filename]
        t_last = src_df.index[-1]

        try:
            df = self.get_data(path)
        except Exception as e:
            logger.error(e)
            return

        if df is None:
            return

        if df.empty:
            logger.debug("Empty dataframe")
            return

        if len(df.columns) == 0:
            logger.debug("No columns in dataframe")
            return

        # if new data exists
        if t_last != df.index[-1]:
            logger.debug(f"[{self.name}] Received new data")
            try:
                loc = df.index.get_loc(t_last) + 1
            except KeyError:
                loc = 0
            df_new = df.iloc[loc:]
            self.callback(filename, df_new)

            # move new data to src_df
            self.data[filename] = df


class App(PlotApp, Callbacks):
    def __init__(self, stdscr):
        PlotApp.__init__( self,
                          stdscr, 
                          bin_window=datetime.timedelta(minutes=1),
                          left_decimals=5,
                          right_decimals=5,
                          x_axis_type='datetime',
                          update_interval=5,
                          show_grid=False )

        self._stdscr = stdscr

        self.parse_args()

        if self.path != None:
            if os.path.isfile(self.path):
                logger.debug("bevers")
                df = self.get_data(self.path)
                logger.debug(f"bever::: {df}")
                line = CandleStickLine(name=os.path.basename(self.path), symbol='$')
                self.add_line(line, orientation='left')
                for index, row in df.iterrows():
                    line.add_point(index,
                                      row['Open'],
                                      row['High'],
                                      row['Low'],
                                      row['Close'])
                self.start()
            else:
                self.source = CSVDataSource(self.path, self.update_data)
                self.lines = {}
                self.first_run()
                self.start()

        while not self._stopped:
            time.sleep(1)

    def parse_args(self):
        parser = argparse.ArgumentParser(description='Pennytrader 3000 plotter')
        parser.add_argument('path', help="path")
        args = parser.parse_args()

        if args.path:
            self.path = os.path.abspath(args.path)
        else:
            self.path = None

    def get_data(self, path):
        if not os.path.isfile(path):
            raise Exception(f"File doesn't exist: {path}")

        try:
            return pd.read_csv(path, index_col='Datetime', parse_dates=True)
        except pd.errors.EmptyDataError as e:
            logger.error(f"Something went wrong while reading csv file: {path}")
            logger.error(e)

    def first_run(self):
        """ Do first read of csv files """
        # do initial run
        for f in os.listdir(self.path):
            path = os.path.join(self.path, f)
            if os.path.isfile(path):
                self.source.update_callback(path)

    def update_data(self, name, df):
        """ Feed df to our plot """
        #logger.debug(f"Updating: plot {df}")

        if name == "candlesticks.csv":
            if not name in self.lines.keys():
                line = CandleStickLine(name=name, symbol='$')
                self.add_line(line, orientation='left')
                self.lines[name] = line

                # create current value line
                cv = CurrentValueLine(line, name='Current value', color='magenta', hidden=True)
                self.add_line(cv, orientation='left')
                self.lines['cur_value'] = cv

            line = self.lines[name]

            for index, row in df.iterrows():
                line.add_point(index,
                                  row['Open'],
                                  row['High'],
                                  row['Low'],
                                  row['Close'])

        elif name == "actions.csv":
            if not 'Buy' in self.lines.keys():
                line = Arrows(name='Buy', symbol='$', interpolate=True, color='green')
                self.add_line(line, orientation='left')
                self.lines['Buy'] = line
            if not 'Sell' in self.lines.keys():
                line = Arrows(name='Sell', symbol='$', interpolate=False, color='red')
                self.add_line(line, orientation='left')
                self.lines['Sell'] = line
            #if not 'Takeprofit' in self.lines.keys():
            #    line = Arrows(name='Takeprofit', symbol='$', interpolate=False, color='blue')
            #    self.add_line(line, orientation='right')
            #    self.lines['Takeprofit'] = line
            #if not 'Stoploss' in self.lines.keys():
            #    line = Arrows(name='Stoploss', symbol='$', interpolate=False, color='magenta')
            #    self.add_line(line, orientation='right')
            #    self.lines['Stoploss'] = line

            for index, row in df.iterrows():
                if 'Buy' in df.columns:
                    if not pd.isna(row['Buy']):
                        self.lines['Buy'].add_point(index, row['Buy'], name='#300')
                if 'Sell' in df.columns:
                    if not pd.isna(row['Sell']):
                        self.lines['Sell'].add_point(index, row['Sell'])
                #if not pd.isna(row['Takeprofit']):
                #    self.lines['Takeprofit'].add_point(index, row['Takeprofit'])
                #if not pd.isna(row['Stoploss']):
                #    self.lines['Stoploss'].add_point(index, row['Stoploss'])

        elif name == "wallet.csv":
            return
            if not 'Wallet' in self.lines.keys():
                line = Line(name='Wallet', symbol='$', interpolate=True)
                self.add_line(line, orientation='right')
                self.lines['Wallet'] = line

            for index, row in df.iterrows():
                if not pd.isna(row['Wallet']):
                    self.lines['Wallet'].add_point(index, row['Wallet'])

    def run(self):
        self.first_run()

        while True:
            time.sleep(1)


if __name__ == "__main__":
    os.environ.setdefault('ESCDELAY', '25')
    curses.wrapper(App)
