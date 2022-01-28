#!/usr/bin/env python3

import time
import logging
import math
import inspect

logger = logging.getLogger('complot')


def timeit(func):
    """ Decorator that displays execution time """
    def function_wrapper(*args, **kwargs):
        t_start = time.time()
        res = func(*args, **kwargs)
        logger.debug(f"[{func.__name__}] exec time: {round(time.time()-t_start, 4)} s")
        return res
    return function_wrapper


class Timer():
    def __init__(self):
        self._timers = {}
        self._counter = 0

    def check(self, name='default'):
        if not name in self._timers.keys():
            self.set(name)

        logger.debug(f"{self._counter}: {time.time() - self._timers[name]} sec")
        self._counter += 1
        self.set(name)

    def set(self, name='default'):
        self._timers[name] = time.time()


class Lock():
    """ Does lock things """
    def __init__(self):
        self._locked = False
        self._holder = None
        self._debugging = False

    def is_locked(self):
        return self._locked

    def do_lock(self):
        self._locked = True

    def release_lock(self):
        self._locked = False
        self._holder = None

    def set_debugging(self, state):
        self._debugging = state

    def wait_for_lock(self, name='default', debug=False):
        if debug or self._debugging:
            class_name = inspect.stack()[1][0].f_locals['self'].__class__.__name__
            method_name = inspect.stack()[1][3]

        while self.is_locked():
            if debug or self._debugging:
                logger.debug(f"[{class_name}.{method_name}] is waiting for lock that is held by {self._holder}...")
            time.sleep(0.01)

        self._holder = name
        self.do_lock()
