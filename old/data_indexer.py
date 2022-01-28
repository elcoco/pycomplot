#!/usr/bin/env python3

import time
import logging
import math
import datetime
import random
from pprint import pprint

from utils import timeit

logger = logging.getLogger('complot')

formatter = logging.Formatter('%(asctime)s  %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

fileHandler = logging.FileHandler("complot.log")


logger = logging.getLogger('complot')
logger.setLevel(logging.DEBUG)

logger.addHandler(fileHandler)

class Group():
    def __init__(self, name, start, end, data={}):
        self.name = name
        self._data = data

        # start and end point of slice in original index
        # in other words, the index span of this slice.
        # This is not the same as lowest and highest data points
        self.start = start
        self.end   = end

    @property
    def data(self):
        return {k:v for k,v in self._data.items() if v != None}

    def has_data(self):
        return list(self._data.values()).count(None) != len(self._data)


class Index():
    def __init__(self, name, start, spacing):
        self.name = name

        # decides after what length index should grow
        self._index_length = 100_000

        self._index_spacing = spacing
        self._index = self.get_index(start, self._index_length, spacing)

        # holds first and last index point, NOTE: this is not a data point
        self._index_start = start
        self._index_end   = list(self._index)[-1]

        # indecate updated state
        self._is_updated = False

        # TODO rebuild index from index option when start changes


    def get_min(self):
        return min(self._index.keys())

    def get(self, key):
        return self._index.get(key)

    def add_point(self, key, value):
        # check if we need to grow the index to be able to include the key
        if key > self._index_end:
            self._index = self.extend_index(self._index, self._index_end, self._index_length, self._index_spacing)

        # TODO only add points that fit into index, find an efficient way to do this
        if key < self._index_start:
            #logger.error("Point is smaller than index start, needs rebuild")
            pass

        self._index[key] = value
        self._is_updated = True


    @timeit
    def rebuild_index(self, old_index, start, length, spacing):
        """ rebuild index when eg start point changes or spacing is different """

        # TODO extend index until all our data fits in

        # get all data out of index
        #old_data = {k:old_index[k] for k in old_index if old_index[k] != None}
        old_data = {k:v for k,v in old_index.items() if v != None}

        # create new index
        self._index = self.get_index(start, length, spacing)

        # set some variables so we know what the specs of this index are
        self._index_spacing = spacing
        self._index_length  = length
        self._index_end     = list(self._index)[-1]
        self._index_start   = start

        # set flag
        self._is_updated = True

        # move old data back to new index
        self._index.update(old_data)
        #self.dict_update(self._index, old_data)


    def extend_index(self, index, start, length, spacing):
        """ Extend the index to be able to include point """
        logger.debug(f"{self.name}: Extending index")
        new_index = self.get_index(start, length, spacing)
        index.update(new_index)

        # update last index point
        self._index_end = list(index)[-1]

        return index

    def get_index(self, start, length, spacing):
        """ Return an empty index of a certain length where keys are evenly spaced """
        return {start + (i*spacing):None for i in range(length)}

    def get_keys_values(self, d, updated=True):
        """ Split dict into keys,values lists """
        if updated:
            self._sorted_keys = sorted(self._index)
            self._sorted_values = [self._index[k] for k in self._sorted_keys]
        return self._sorted_keys, self._sorted_values

    def get_index_start(self, keys, values, group_size, offset=0):
        """ calculate the group start index $offset groups from the end """
        # find latest data point in index that is not None
        last_key = self.get_last_valid_index(keys, values)

        # calculate start key of last group
        last_group_start = last_k - ((last_k-self._index_start) % group_size)

        # calculate start key of first group that we want to get
        start = last_group_start - ((offset-1) * group_size)

        # find indices
        return keys.index(start), keys.index(last_k)

    def get_group_index_by_key(self, keys, key, group_size):
        """ Calculate the start index of the group that $key belongs in """
        group_start_key = key - ((key-self._index_start) % group_size)
        return keys.index(group_start_key)

    def get_last_valid_index(self, keys, values):
            last_k = next(k for i,k in enumerate(reversed(keys)) if values[len(keys)-i-1] != None)
            return keys.index(last_k)

    @timeit
    def get_grouped(self, group_size, start=None, amount=None, from_end=False):
        """ Efficiently group data in chunks of group_size
            start = key,  start at key position
            amount = int, only get $amount groups starting from $start
            from_end = bool, get last $amount groups, start counting in chunks of $group_size from beginning
        """
        groups = []

        # this is a resource hungry operation so only perform if new data is available
        sorted_keys, sorted_values = self.get_keys_values(self._index, updated=self._is_updated)

        # NOTE ugly because our index is way longer than the actual data it contains
        #      do it anyway because it is 2x as fast, and $amount will break the loop anyways
        i_end = len(sorted_keys)

        # get last $amount groups, start counting in chunks of $group_size from beginning
        # so last group may not be complete yet depending on the data in the index
        if from_end:
            i_start = i_end - ((amount * group_size))
            i_end = self.get_last_valid_index(sorted_keys, sorted_values)
            # TODO take into account index spacing, now only works when spacing=1

        # assume start at begin
        elif start == None:
            i_start = 0

        # find index for start key
        else:
            # TODO find the index of group start where $start belongs in
            #i_start = sorted_keys.index(start)
            i_start = self.get_group_index_by_key(sorted_keys, start, group_size)

        for i in range(i_start, i_end, group_size):

            # break when we reached our desired amount of groups
            if amount != None and len(groups) == amount:
                break

            # calculate index locations of group
            group_i_start = i
            group_i_end   = group_i_start+group_size

            # take slice from lists corresponding to group
            keys = sorted_keys[group_i_start:group_i_end]
            values = sorted_values[group_i_start:group_i_end]

            # find actual group start/end keys
            group_start = keys[0]
            group_end   = keys[-1]

            # create group object
            group = Group(self.name, group_start, group_end, dict(zip(keys, values)))
            groups.append(group)

        # reset flag
        self._is_updated = False

        return groups


class IndexedData():
    """ index a bunch of evenly spaced data with numerical keys.
        An index is created of evenly spaced None objects

        We can use this index to have predictable indexes that we can access quickly
        Using this method slices can be taken quickly to create grouped data without looping
        over all the datapoints.
    """
    def __init__(self, spacing=1):
        self._index_spacing = spacing
        self._indexes = []

        # index start point, to keep all indexes in sync
        self._index_start = None

    def get_index(self, name):
        for index in self._indexes:
            if index.name == name:
                return index
        #return next(x for x in self._indexes if x.name == name)

    def add(self, name, key, value):
        if self._index_start == None:
            print("Setting index start to:", key)
            self._index_start = key
        elif key < self._index_start:
            print("Rebuild index", key, self._index_start)

        index = self.get_index(name)

        if index == None:
            if self._index_start == None:
                print("Setting index start to:", key)
                self._index_start = key
            # first point decides start point for all indexes
            index = Index(name, self._index_start, self._index_spacing)
            self._indexes.append(index)

        index.add_point(key, value)

    def add(self, name, key, value):
        index = self.get_index(name)

        if index == None:
            # first point decides start point for all indexes
            if self._index_start == None:
                self._index_start = key

            index = Index(name, self._index_start, self._index_spacing)
            self._indexes.append(index)

        index.add_point(key, value)




def enumerate2(xs, start=0, step=1):
    for x in xs:
        yield (start, x)
        start += step

def get_string(length=5):
    return "".join([ str(chr(round(random.uniform(65,90)))) for i in range(length)])

@timeit
def run(names):
    indexer = IndexedData()

    for i,name in enumerate2(names, 666, step=3):
        indexer.add('col1', i, name)

    for i,name in enumerate2(names, 233, step=5):
        indexer.add('col2', i, name)

    i1 = indexer.get_index('col1')
    i2 = indexer.get_index('col2')

    #groups = i1.get_grouped(50, amount=300)
    #groups = i1.get_grouped(50, amount=300)
    #groups = i1.get_grouped(50, start=300516, amount=None)
    print(i1.get(300450))

    i1.rebuild_index(i1._index, 0, 500000, 5)

    #groups = i1.get_grouped(50, from_end=False, amount=5)
    #groups = i1.get_grouped(50, from_end=True, amount=5)
    groups = i1.get_grouped(50, start=300486, amount=3)

    for group in groups:
        pprint(group.data)



    print(i1.get(300450))



if __name__ == "__main__":
    names = [get_string() for x in range(100_000)]
    run(names)
