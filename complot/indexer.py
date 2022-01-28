#!/usr/bin/env python3

import time
import logging
import math
import datetime
import random
from pprint import pprint, pformat

#from utils import timeit
from complot.utils import timeit

logger = logging.getLogger('complot')

# NOTE: speed bottlenecks are:
#       - adding col_names in build_index() takes a lot of time
#       - find out if the dynamic adding of columns takes too much time

class Group():
    def __init__(self, start, end, data, count):
        self._data = data

        # start and end index
        self._start = start
        self._end = end

        # column names in data
        self._columns = data.keys()

        # these values are cached when one of the corresponding functions are called, don't access directly
        self._min = None
        self._max = None
        self._avg = None

        # the group number counted from beginning of data
        self._count = count

        #TODO values are cached but when calling a second time, key or column name may have changed

    @property
    def count(self):
        return self._count

    def get_first(self, col_name):
        """ Get first point from column """
        # TODO is this always the oldest point?
        try:
            return list(self.get_col(col_name).values())[0]
        except IndexError:
            # NOTE this is because there may be no data in this group for this column
            #     we need to get data from last group but this info is not available
            #logger.debug(f"Failed to get first value for: {col_name}")
            pass

    def get_last(self, col_name):
        """ Get last point from column """
        # TODO is this always the newest point?
        try:
            return list(self.get_col(col_name).values())[-1]
        except IndexError:
            # NOTE this is because there may be no data in this group for this column
            #     we need to get data from last group but this info is not available
            #logger.debug(f"Failed to get last value for: {col_name}")
            pass

    def get_avg(self, column, key=None):
        """ Calculate average for a column, if key is specified, access object attribute by key """
        if self.is_empty(column):
            return

        if key:
            return sum(getattr(point,key) for point in self.get_col(column).values()) / len(self.get_col(column))
        else:
            return sum(self.get_col(column).values()) / len(self.get_col(column))

    def get_max(self, columns=[], key=None, use_avg=False):
        """ return max for specified column names. If key is specified, access object attribute by key
            If use_avg is True, get avg for every column and return max """
        if type(columns) != list:
            columns = [columns]

        values = []
        for col in columns:
            if use_avg:
                values.append(self.get_avg(col, key=key))
            elif key:
                values.append(max([getattr(v, key) for v in self.get_col(col).values()], default=None))
            else:
                values.append(max(self.get_col(col).values(), default=None))

        self._max = max([v for v in values if v != None], default=None)
        return self._max

    def get_min(self, columns=[], key=None, use_avg=False):
        """ return min for specified column names. If key is specified, access object attribute by key
            If use_avg is True, get avg for every column and return min """
        if type(columns) != list:
            columns = [columns]

        values = []
        for col in columns:
            #values.append(self.get_avg(col, key=key))
            if use_avg:
                values.append(self.get_avg(col, key=key))
            elif key:
                values.append(min([getattr(v, key) for v in self.get_col(col).values()], default=None))
            else:
                values.append(min(self.get_col(col).values(), default=None))

        self._min = min([v for v in values if v != None], default=None)
        return self._min

    @property
    def data(self):
        return self._data

    @property
    def start(self):
        return self._start

    @property
    def end(self):
        return self._end

    def is_empty(self, column):
        return len(self.get_col(column)) == 0

    def __repr__(self):
        out =  f"range:  {self.start} : {self._end}\n"
        #out += f"length: {len(self.data)}\n"
        out += pformat(self._data)
        return out

    def get_col(self, col_name):
        return self._data.get(col_name, {})


class CacheItem():
    """ Representing one item in cache """
    def __init__(self, metadata, data):
        self.dt = datetime.datetime.utcnow()
        self.metadata = metadata
        self.data = data

    def compare(self, metadata, dt=None):
        """ Check if cacheitem is something we're looking for """
        if dt:
            if not (dt < self.dt):
                return
        return metadata == self.metadata


class Cache():
    """ Store group data in cache, when there were no data updates, we can send back cached items """
    def __init__(self):
        self._cache = []

        # count lookups, cleanup every $cleanup_interval lookups
        self._lookup_counter = 0
        self._cleanup_interval = 500

    def get(self, metadata, dt=None):
        """ Find item in cache where this metadata is the same.
            Only return items newer than index """
        self._lookup_counter += 1

        # cleanup every once in a while
        if (self._lookup_counter % self._cleanup_interval) == 0:
            self.cleanup(dt)

        for ci in reversed(self._cache):
            if ci.compare(metadata, dt=dt):
                return ci.data

    def display_cache(self):
        for i,ci in enumerate(self._cache):
            logger.debug(f"{str(i).ljust(3)} datetime: {ci.dt}")
            for k,v in ci.metadata.items():
                logger.debug(f"    {k}: {v}")

    def add(self, metadata, data):
        """ Add data to cache, identified by item dict """
        if not self.get(metadata, datetime.datetime.utcnow()):
            self._cache.append(CacheItem(metadata, data))

    def cleanup(self, dt):
        """ Cleanup everything older than dt """
        for ci in self._cache:
            if ci.dt < dt:
                logger.debug(f"[CACHE] cleaning up item: {ci.dt}")
                self._cache.remove(ci)


class Index():
    def __init__(self, amount, spread):
        # when index is out of bounds, grow this amount of keys
        self._index_grow_amount = amount

        # this is a list of column names that will be added to each bucket
        # this way all columns are using the same index and everything stays in sync
        self._columns = []
         
        # space inbetween keys
        self._index_spread = spread

        # dimensions of index
        self._index = {}
        self._index_start_key = None
        self._index_end_key   = None

        # biggest/smallest key in index
        self._index_max_key   = None
        self._index_min_key   = None

        self._sorted_keys = []
        self._sorted_values = []
        self._is_updated = True

        # keep the groups cached for efficiency's sake
        self._cache = Cache()
        self._last_update = datetime.datetime.utcnow()

    def has_data(self):
        """ If data is in index, columns is defined """
        return self._index_start_key != None

    @timeit
    def build_index(self, start_key, amount, spread):
        logger.debug(f"Building index with length: {amount}")
        index = {}

        # NOTE: was using Bucket object before, using a dict is 5x faster
        for i in range(amount):

            # NOTE generating col names takes a lot of time need to find a faster solution for this
            #col_names = {name : {} for name in self._col_names}

            b_start = start_key + (i * spread)
            b_end   = b_start + spread
            index[b_start] = {}
            #index[b_start] = col_names
        return index

    @timeit
    def extend_index_left(self, k):
        """ Rebuild index from old index.
            Create new index and add in existing data """
        while k < self._index_start_key:
            logger.debug(f"Extending index to left to fit key: {k}")
            start_key = self._index_start_key - (self._index_grow_amount * self._index_spread)
            index = self.build_index(start_key, self._index_grow_amount, self._index_spread)
            self._index.update(index)
            self._index_start_key = start_key

    @timeit
    def extend_index_right(self, k):
        """ Grow index to the left until k fits in """
        while k > self._index_end_key:
            logger.debug(f"Extending index to right to fit key: {k}")
            new_index = self.build_index(self._index_end_key, self._index_grow_amount, self._index_spread)
            self._index.update(new_index)

            ## update last index point
            self._index_end_key = list(self._index)[-1]

    def reset_index(self):
        Index.__init__(self, self._index_grow_amount, self._index_spread)

    def insert(self, col_name, k, v):
        """ Find the right bucket and insert point into it """
        ## is a mapping between index keys and buckets
        #self._index = self.build_index(start, self._index_grow_amount, self._index_spread)
        if col_name not in self._columns:
            self._columns.append(col_name)
            logger.debug(f"New column detected: {col_name}")

        # create index if not exist
        if not self._index:
            self._index_start_key = int(k)
            self._index = self.build_index(self._index_start_key, self._index_grow_amount, self._index_spread)
            self._index_end_key   = list(self._index)[-1]

        # if this is the biggest point yet, save it
        if self._index_max_key == None or k > self._index_max_key:
            self._index_max_key = k
        if self._index_min_key == None or k < self._index_min_key:
            self._index_min_key = k

        # extend index if necessary
        if k > self._index_end_key:
            self.extend_index_right(k)
        elif k < self._index_start_key:
            self.extend_index_left(k)

        bucket_key = self.get_index_key(k)

        # create column if it doesn't exist
        if col_name in self._index[bucket_key]:
            self._index[bucket_key][col_name][k] = v
        else:
            self._index[bucket_key][col_name] = {}
            self._index[bucket_key][col_name][k] = v

        # use this to cache keys/values from get_keys_values()
        self._is_updated = True

        # NOTE not sure about the speed punishment for this
        # used for caching of groups
        self._last_update = datetime.datetime.utcnow()

    def get_index_key(self, key):
        """ Calculate index key from any given key that exists in index """
        return key - ((key-self._index_start_key) % self._index_spread)

    def get_keys_values(self, updated=False):
        """ Split and sort index, save results in variable to save resources """
        if updated:
            # split and sort index
            self._sorted_keys   = sorted(self._index)
            self._sorted_values = [self._index[k] for k in self._sorted_keys]
            self._is_updated = False
        return self._sorted_keys, self._sorted_values

    def bucket_is_populated(self, bucket):
        # TODO this doesn't work anymore now column names are used
        return list(bucket.values()).count(None) != len(bucket)

    def get(self, col_name, k):
        """ Get key from index """
        bucket_key = self.get_index_key(k)
        bucket = self._index[bucket_key]
        return bucket[col_name].get(k)

    def get_all_grouped(self, amount):
        """ Return all data grouped """
        if self._index_min_key == None or self._index_max_key == None:
            logger.error("Not enough data to get all grouped")
            return []

        group_size = int((self._index_max_key - self._index_min_key) / amount)
        group_size -= group_size % self._index_spread

        if self._index_spread > group_size:
            logger.error(f"spread > group_size, {self._index_spread} > {group_size}")
            return []

        return self.get_grouped_from_last_data(group_size, amount=amount)

    def get_grouped_from_last_data(self, group_size, amount, offset=0):
        """ Return groups, starting from last data point """
        if not self.has_data():
            logger.debug("Failed to get groups, no data yet in index")
            return []

        end_key   = int(self.get_index_key(self._index_max_key))
        end_key -= offset
        return self.get_grouped(group_size, end_key, amount)

    def get_index_by_key(self, key):
        """ Get index number from self._index identified by key """
        # get sorted list containing key/values from index
        # NOTE this is takes up most resources and is cached, refreshes when new data is added
        keys, _ = self.get_keys_values(updated=self._is_updated)
        return keys.index(key)

    def get_grouped(self, group_size, end_key, amount):
        """ Return list of group object that contain data
            Groups have a start and end value that corresponds with the index
            $group_size specifies the key spacing, not index spacing
        """
        # TODO remove start_key, is not used anymore
        # use cache if possible
        metadata = {'end_key'   : end_key,
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
            last_i = self.get_index_by_key(end_key)
        except ValueError:
            print(f"End key ({end_key}) out of index bounds [{self._index_start_key}:{self._index_end_key}]")
            return []

        # size/span of group in index numbers
        group_index_size = int(group_size/self._index_spread)

        # calculate at which bin the last group starts
        # NOTE this group may not be complete yet but we want the data to be displayed anyways
        last_group_i  = last_i - (last_i % group_index_size)
        first_group_i = last_group_i - (amount * group_index_size)

        # when there is an unfinished group at the end, make sure the amount is correct
        if last_i > last_i - (last_i % group_index_size):
            first_group_i  += group_index_size

        groups = []

        # traverse index $group_size sized steps and take slices for every group
        for group_start_i in range(first_group_i, last_i, group_index_size):
            group_end_i = group_start_i + group_index_size
            count = group_start_i / group_index_size

            if group_start_i < 0 or group_end_i < 0:
                groups.append(Group(None, None, {}, count))
            else:
                group_start_key = keys[group_start_i]
                group_end_key   = keys[group_end_i]
                buckets = values[group_start_i:group_end_i]

                # join data in buckets
                data = {name : {} for name in self._columns}
                for bucket in buckets:
                    for col in self._columns:
                        data[col].update(bucket.get(col, {}))

                groups.append(Group(group_start_key, group_end_key, data, count))

        #self.display_groups(groups)
        self._cache.add(metadata, groups)
        return groups

    def display_groups(self, groups):
        logger.debug(50*'-')
        group_span    = (groups[-1].end - groups[0].start) if None not in [groups[-1].end, groups[0].start] else None
        group_span_dt = datetime.timedelta(seconds=group_span) if group_span != None else None
        data_span = (self._index_max_key - self._index_min_key) if None not in (self._index_min_key, self._index_max_key) else None
        data_span_dt = datetime.timedelta(seconds=data_span) if data_span != None else None
        logger.debug(f"Groups start:  {groups[0].start}")
        logger.debug(f"Groups end:    {groups[-1].end}")
        logger.debug(f"Groups span:   {group_span}, {group_span_dt}")
        logger.debug(f"Groups length: {len(groups)}")
        logger.debug(f"Data start:    {self._index_min_key}")
        logger.debug(f"Data end:      {self._index_max_key}")
        logger.debug(f"Data span:     {data_span}, {data_span_dt}")
        for i,group in enumerate(groups):
            t_diff = group.end-group.start if None not in [group.end,group.start] else None
            logger.debug(f"{str(group.count).rjust(3)} {str(group.start).ljust(12)} {str(group.end).ljust(12)} diff: {t_diff}s")
            #logger.debug(pformat(group.data))
        logger.debug(50*'-')


""" Below is for testing only """
class TestPoint():
    def __init__(self):
        self.value = self.get_number()

    def get_number(self, length=5):
        return round(random.randint(1000,9999))


class App():
    def enumerate2(self, xs, start=0, step=1):
        for x in xs:
            yield (start, x)
            start += step

    def get_string(self, length=5):
        return "".join([ str(chr(round(random.uniform(65,90)))) for i in range(length)])

    def get_number(self, length=5):
        return round(random.randint(1000,9999))

    def get_object(self):
        return TestPoint()

    @timeit
    def insert_points(self, col_name, index, keys, values):
        logger.debug(f"Inserting {col_name} {len(keys)} points")
        for i in range(len(keys)):
            index.insert(col_name, keys[i], values[i])

    @timeit
    def run(self):
        index = Index(100_000, 5)

        amount = 100_000
        start  = 800
        step   = 3

        keys   = [i for i in range(start, start+(amount*step), step)] 
        #values = [self.get_number() for x in range(100_000)]
        #values = [self.get_string() for x in range(100_000)]
        values = [self.get_object() for x in range(100_000)]

        self.insert_points('col1', index, keys, values)

        values = [self.get_object() for x in range(100_000)]
        self.insert_points('col2', index, keys, values)
        #print(index.get('col1', 833))
        index.insert('col1', 50, 'BEVER')
        #print(index.get('col1', 833))

        groups = index.get_grouped_from_end(30, 50000, 5)
        groups = index.get_grouped_from_end(30, 50000, 5)
        groups = index.get_grouped_from_start(30, start=3000, amount=4)
        groups = index.get_grouped_from_start(30, start=3000, amount=500)
        #for group in groups:
        #    print(group.get_avg('col1'))
        #groups = index.get_grouped_from_last_data('col1', 30, amount=3)

        for group in groups:
            print(group.get_avg('col1', key='value'))

if __name__ == "__main__":
    app = App()
    app.run()
