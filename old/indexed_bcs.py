#!/usr/bin/env python3

import time
import logging
import math
import datetime
import random
from pprint import pprint

from complot.utils import timeit

logger = logging.getLogger('complot')

class IndexedData():
    """ index a bunch of evenly spaced data with numerical keys.
        An index is created of evenly spaced None objects
        Items are added in this index
        The get_grouped() method does super fast grouping of data by taking slices of the index
    """
    def __init__(self, spacing=1, index_length=100000):
        self._data   = {}

        # mapping between key:datapoint
        self._index_length  = index_length
        self._index_spacing = spacing
        self._index = {}

        # TODO index should dynamically grow when needed

    def build_empty_index(self, start, length, spacing):
        """ Set an empty index of a certain length where keys are evenly spaced """
        index = {}

        for i in range(length):
            index[start] = None
            start += spacing
        return index

    def get(self, key):
        return self._index.get(key, None)

    @timeit
    def get_grouped(self, group_size):
        groups = []
        sorted_keys = sorted(self._index)
        sorted_values = [self._index[k] for k in sorted_keys]

        for i in range(0, len(self._index.keys()), group_size):
            # take slices that correspond to group size
            keys = sorted_keys[i:i+group_size]
            values = sorted_values[i:i+group_size]
            group = dict(zip(keys, values))

            # filter out points without a value
            group = {k:v for k,v in group.items() if v != None}

            if group:
                groups.append(group)

        return groups

    def add(self, key, value):
        self._data[key] = value

        if not self._index:
            start = min(self._data.keys())
            self._index = self.build_empty_index(start, self._index_length, self._index_spacing)

        self._index[key] = value


"""
def enumerate2(xs, start=0, step=1):
    for x in xs:
        yield (start, x)
        start += step

def get_string(length=5):
    return "".join([ str(chr(round(random.uniform(65,90)))) for i in range(length)])

@timeit
def run(names):
    index = IndexedData()

    for i,name in enumerate2(names, 666, step=3):
        index.add(i, name)

    groups = index.get_grouped(100)
    pprint(groups)
    for group in groups:
        print(sum(group.keys())/len(group))


    print(index.get(300456))
    print(index.get(100659))
    print(index.get(7309866))



names = [get_string() for x in range(100_000)]
run(names)
"""
