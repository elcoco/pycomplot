#!/usr/bin/env python3

import numpy as np
import time
import random
import datetime

from tplot import Plot


def get_sine(x):
    return np.sin(x) + np.random.normal(scale=0.1, size=len(x))

def get_stock(x):
    y = 0
    result = []
    for _ in x:
        result.append(y)
        y += np.random.normal(scale=1)
    return np.array(result)

def get_running_mean(x, N):
    return np.convolve(x, np.ones((N,))/N)[(N-1):]

def dt_animate_test():
    p = Plot(y_size=40)
    #p.start_watch()

    l1 = p.add_line('o', name='sine', color='green')
    l2 = p.add_line('o', orientation='right', name='mean', color='red')
    l3 = p.add_line('o', orientation='right', name='stock', color='cyan')

    x = np.linspace(1, 100, 1000)

    sine = get_sine(x)
    mean = get_running_mean(sine, 100)
    stock = get_stock(x)

    t_now = datetime.datetime.now()

    for i in range(1000):
        l1.add_point(i, sine[i])
        #l2.add_point(t_now, mean[i])
        #l3.add_point(t_now, stock[i])
        t_now += datetime.timedelta(days=1)
        time.sleep(0.1)
        p.plot()



    #p.stop_watch()

def dt_test():
    p = Plot(y_size=40)
    l1 = p.add_line('o', name='left', color='green')
    l2 = p.add_line('o', orientation='right', name='right', color='red')
    l3 = p.add_line('o', orientation='right', name='right', color='cyan')

    t_now = datetime.datetime.now()
    for i in range(1000):
        l1.add_point(t_now, i*i)
        t_now += datetime.timedelta(days=1)

    t_now = datetime.datetime.now() + datetime.timedelta(days=150, hours=10)
    for i in range(500, 1500):
        l2.add_point(t_now, math.sqrt(i))
        l3.add_point(t_now, math.sqrt(i)+10)
        t_now += datetime.timedelta(days=1)

    p.plot()

def test():
    p = Plot(y_size=40)
    l1 = p.add_line('o', name='disko', color='green')
    l2 = p.add_line('*', name='rechts_1', orientation='right', color='red')
    l3 = p.add_line('@', name='rechts_2', orientation='right', color='cyan')

    for i in range(-500,801):
        l1.add_point(i,i*i/3)

    for i in range(-1000,1000):
        l2.add_point(i,i*i/3)

    for i in range(-1000,1001):
        l3.add_point(i,i*i)


    l1.add_point(-30, 33)
    l2.add_point(0, -40000)
    l2.add_point(59, 70)
    l2.add_point(70, 40)

    p.plot()

dt_animate_test()
