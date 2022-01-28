#!/usr/bin/env python3

import curses
import time
import datetime
import logging
import argparse
import os,sys

import numpy as np

# crypto streamer
import pandas as pd
import yfinance as yf
import quandl
from binance.client import Client
from binance.exceptions import BinanceAPIException
from requests.exceptions import RequestException
from curses.textpad import Textbox, rectangle

from complot.plot import Plot
from complot.lines import Line, CandleStickLine, HistogramLine, MaxLine, PeaksDetect
from complot.menu import OptionsMenuItem, MenuItem

logger = logging.getLogger('complot')


class DataProviderBaseClass():
    """ Base class for data providers  """
    def __init__(self, stock):
        self.name = None
        self.data = []
        self.stock = stock
        self.ticker_interval = '1m'

    def get(self, stock):
        return self.data


class BinanceDataProvider(DataProviderBaseClass):
    def __init__(self, stock, api_key='', api_secret=''):
        DataProviderBaseClass.__init__(self, stock)
        self.name = 'Binance'
        self.stock = stock

        self._period = None
        self._interval = '5m'
        self._api_key = api_key
        self._api_secret = api_secret

    @property
    def period(self):
        return self._period

    @period.setter
    def period(self, value):
        self._period = value

    @property
    def interval(self):
        return self._interval

    @interval.setter
    def interval(self, value):
        self._interval = value

    def pol_new_data(self, index):
        if index == None:
            # get initial data
            df = self.get(period=self._period, interval=self._interval).copy(deep=True)
        else:
            df = self.get(t_start=index, interval=self._interval).copy(deep=True)
            return df[:-1]

        return df

    def get_symbols(self):
        while True:
            try:
                client = Client(self._api_key, self._api_secret)
                return [x['symbol'] for x in client.get_exchange_info()['symbols']]
            except RequestException as e:
                logger.error(e)
            except BinanceAPIException as e:
                logger.error(e)

            logger.error("Failed to connect to Binance API, will try again in 5 seconds")
            time.sleep(5)

    def get(self, t_start=None, period=None, interval=None):
        if period == None:
            period = self._period

        if t_start == None:
            t_start = datetime.datetime.utcnow() - period

        if interval == None:
            interval = self._interval

        # convert datetime to binance timestamp format (1234567890.123)
        t_start = int(datetime.datetime.timestamp(t_start) * 1000)

        # keep connecting to binance until success
        while True:
            try:
                client = Client(self._api_key, self._api_secret)
                klines = client.get_klines(symbol=self.stock, interval=interval, startTime=t_start)
                break
            except RequestException as e:
                logger.error(e)
            except BinanceAPIException as e:
                logger.error(e)

            logger.error("Failed to connect to Binance API, will try again in 5 seconds")
            time.sleep(5)


        columns = [ "Open_time",
                    "Open",
                    "High",
                    "Low",
                    "Close",
                    "Volume",
                    "Close_time",
                    "Quote_asset_volume",
                    "N_trades",
                    "Base_volume",
                    "Quote_volume",
                    "Ignore" ]

        df = pd.DataFrame(klines, columns=columns)
        df.Open_time = pd.to_datetime(df.Open_time, unit='ms') # change type from object to datetime
        df.Close_time = pd.to_datetime(df.Close_time, unit='ms') # change type from object to datetime
        df = df.set_index("Close_time")
        df.index.name = "Datetime"
        df = df.tz_localize('UTC')

        # types are numerical strings, convert to float
        df.Open = df.Open.astype(float)
        df.High = df.High.astype(float)
        df.Low = df.Low.astype(float)
        df.Close = df.Close.astype(float)
        df.Volume = df.Volume.astype(float)
        df.Quote_asset_volume = df.Quote_asset_volume.astype(float)
        df.N_trades = df.N_trades.astype(float)
        df.Base_volume = df.Base_volume.astype(float)
        df.Quote_volume = df.Quote_volume.astype(float)

        return df


class CryptoStreamer(Plot):
    def __init__(self, stdscr):
        Plot.__init__(self, stdscr, bin_window=datetime.timedelta(minutes=1), left_decimals=5, right_decimals=5, x_axis_type='datetime')
        #Plot.__init__(self, stdscr, window=datetime.timedelta(days=1), left_decimals=5, right_decimals=5)
        self._ticker = None
        self._interval = '5m'
        self._period = datetime.timedelta(days=1)

        if not self.parse_args():
            return

        self.start_threads()

        self.l1 = HistogramLine(name='Volume Bullish', color='blue')
        self.l2 = HistogramLine(name='Volume Bearish', color='magenta')
        self.l3 = CandleStickLine(name=self._ticker, symbol='$')
        self.l4 = PeaksDetect(self.l3, name='Peaks', smoothing=7, color='blue')

        self.add_line(self.l1, orientation='left')
        self.add_line(self.l2, orientation='left')
        self.add_line(self.l3, orientation='right')
        self.add_line(self.l4, orientation='right')

        self.last_pol_index = None
        self.last_df = None

        # set menu option to select ticker
        ticker_menu = OptionsMenuItem(stdscr, 'Tickers', buttons=[ord('t')], button_name='t')
        for ticker in self.dp_eth.get_symbols():
            ticker_menu.add_option(MenuItem(ticker, callback=self.set_ticker_callback))
        self._menu.add_item(ticker_menu, position=0)

        interval_menu = OptionsMenuItem(stdscr, 'Interval', default='5 minutes')
        interval_menu.add_option(MenuItem('1 minute',   callback=self.bin_window_callback, state=datetime.timedelta(minutes=1)))
        interval_menu.add_option(MenuItem('5 minutes',  callback=self.bin_window_callback, state=datetime.timedelta(minutes=5)))
        interval_menu.add_option(MenuItem('15 minutes', callback=self.bin_window_callback, state=datetime.timedelta(minutes=15)))
        interval_menu.add_option(MenuItem('1 hour',     callback=self.bin_window_callback, state=datetime.timedelta(hours=1)))
        interval_menu.add_option(MenuItem('1 day',      callback=self.bin_window_callback, state=datetime.timedelta(days=1)))
        interval_menu.add_option(MenuItem('1 week',     callback=self.bin_window_callback, state=datetime.timedelta(days=7)))
        interval_menu.reset()
        self._menu.add_item(interval_menu, position=0)

        period_menu = OptionsMenuItem(stdscr, 'Period', default='1 day')
        period_menu.add_option(MenuItem('1 day',    callback=self.period_callback, state=datetime.timedelta(days=1)))
        period_menu.add_option(MenuItem('7 days',   callback=self.period_callback, state=datetime.timedelta(days=7)))
        period_menu.add_option(MenuItem('1 month',  callback=self.period_callback, state=datetime.timedelta(days=30)))
        period_menu.add_option(MenuItem('3 months', callback=self.period_callback, state=datetime.timedelta(days=90)))
        period_menu.add_option(MenuItem('1 year',   callback=self.period_callback, state=datetime.timedelta(days=365)))
        period_menu.reset()
        self._menu.add_item(period_menu, position=0)
        try:
            self.loop()
        except KeyboardInterrupt:
            pass

        self.stop_threads()

    def set_ticker_callback(self, item):
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

    def set_interval(self, td):
        logger.debug(td)
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

    def bin_window_callback(self, item):
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

    def period_callback(self, item):
        logger.debug(f"Setting period: {item.state}")
        self._period = item.state
        self.reset_data()
        self.connect(self._ticker, self._interval, self._period)

        self.last_pol_index = None
        self.last_df = None
        self.l1.name = self._ticker

        self.draw()

    def connect(self, ticker, interval, period):
        api_key = ''
        api_secret = ''

        self.dp_eth = BinanceDataProvider(ticker, api_key=api_key, api_secret=api_secret)
        self.dp_eth.period   = period
        self.dp_eth.interval = interval

    def parse_args(self):
        parser = argparse.ArgumentParser(description='Cryptostreamer unit stuff.')
        parser.add_argument('ticker', help="ticker")
        args = parser.parse_args()

        if args.ticker:
            self._ticker = args.ticker
            self.connect(self._ticker, self._interval, self._period)
            return True

    def loop(self):
        # TODO retrieve symbols and put in menu
        while not self.is_stopped():
            logger.debug("polling for new data")
            df = self.dp_eth.pol_new_data(self.last_pol_index)

            if not df.equals(self.last_df):
                for index, row in df.iterrows():

                    if row['Close'] >= row['Open']:
                        self.l1.add_point(index, row['Volume'])
                    else:
                        self.l2.add_point(index, row['Volume'])

                    self.l3.add_point(index,
                                      row['Open'],
                                      row['High'],
                                      row['Low'],
                                      row['Close'])

                    #self.l4.add_point(index, row['Close'])

                last_df = df.copy(deep=True)

            if not df.empty:
                self.last_pol_index = df.index[-1]

            # this sleep doesn't block our stopped signal
            self.sleep(5)


if __name__ == "__main__":
    os.environ.setdefault('ESCDELAY', '25')
    curses.wrapper(CryptoStreamer)
