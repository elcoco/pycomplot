#!/usr/bin/env python3

import curses
import time
import datetime
import logging
import argparse
import os,sys

import numpy as np
import pandas as pd

from complot.plot import PlotApp
from complot.lines import Line, CandleStickLine, HistogramLine, PeaksDetect, CurrentValueLine, HorizontalLine, Arrows
from complot.menu import Menu, OptionsMenuItem, MenuItem, EditableMenuItem
from complot.utils import timeit

logger = logging.getLogger('complot')


class App(PlotApp):
    def __init__(self, stdscr):
        PlotApp.__init__( self,
                          stdscr, 
                          bin_window=datetime.timedelta(minutes=5),
                          left_decimals=5,
                          right_decimals=5,
                          x_axis_type='datetime',
                          update_interval=5,
                          show_grid=False )

        self._stdscr = stdscr

        self.lines = {}
        self.parse_args()

        self.run()
        self.start()

    def parse_args(self):
        parser = argparse.ArgumentParser(description='Pennytrader 3000 plotter')
        parser.add_argument('path', help="path")
        args = parser.parse_args()

        if args.path:
            self.path = os.path.abspath(args.path)
        else:
            self.path = None

    def plot_file(self, path):
        if not path.endswith('.csv'):
            logger.error(f"Not a csv file: {path}")
            return

        df = self.get_data(path)

        if df is None:
            return

        self.update_plot(os.path.basename(path), df)

    def get_data(self, path):
        if not os.path.isfile(path):
            raise Exception(f"File doesn't exist: {path}")

        try:
            return pd.read_csv(path, index_col='Datetime', parse_dates=True)
        except pd.errors.EmptyDataError as e:
            logger.error(f"Something went wrong while reading csv file: {path}")
            logger.error(e)

    @timeit
    def plot_candlesticks(self, name, df):
        line = CandleStickLine(name=name, symbol='$')
        self.add_line(line, orientation='left')

        # create current value line
        cv = CurrentValueLine(line, name='Current value', color='magenta', hidden=True)
        self.add_line(cv, orientation='left')

        df.apply(lambda row : line.add_point(row.name, row['Open'], row['High'], row['Low'], row['Close']), axis = 1) 

    def plot_orders(self, name, df):
        line_buy = Arrows(name='Buy', symbol='$', color='green')
        self.add_line(line_buy, orientation='left')

        line_sell = Arrows(name='Sell', symbol='$', color='red')
        self.add_line(line_sell, orientation='left')

        for index, row in df.iterrows():
            if 'Buy' in df.columns:
                if not pd.isna(row['Buy']) and not pd.isna(row['Id']):
                    line_buy.add_point(index, row['Buy'], name=f"#{int(row['Id'])}")
            if 'Sell' in df.columns:
                if not pd.isna(row['Sell']) and not pd.isna(row['Id']):
                    line_sell.add_point(index, row['Sell'], name=f"#{int(row['Id'])}")
        #df['Buy'].dropna().apply(lambda row : line_sell.add_point(row.name, row['Buy'], name=f"#{int(row['Id'])}")) 
        #df['Sell'].dropna().apply(lambda row : line_sell.add_point(row.name, row['Sell'], name=f"#{int(row['Id'])}")) 

    @timeit
    def plot_wallet(self, name, df):
        line = Line(name='Wallet', symbol='$', interpolate=True, color='magenta')
        self.add_line(line, orientation='right')
        df.apply(lambda row : line.add_point(row.name, row['Wallet']), axis = 1) 

    def update_plot(self, name, df):
        """ Feed df to our plot """
        logger.debug(f"Plotting: {name}")
        if name == "candlesticks.csv":
            self.plot_candlesticks('candlesticks', df)

        elif name == "orders.csv":
            self.plot_orders('orders', df)

        elif name == "wallet.csv":
            self.plot_wallet('wallet', df)

        #else:
        #    self.plot_candlesticks(name, df)

    def run(self):
        if self.path == None:
            return
        if os.path.isfile(self.path):
            self.plot_file(self.path)
        elif os.path.isdir(self.path):
            for path in os.listdir(self.path):
                if os.path.isfile(os.path.join(self.path, path)):
                    self.plot_file(os.path.join(self.path, path))


if __name__ == "__main__":
    os.environ.setdefault('ESCDELAY', '25')
    curses.wrapper(App)
