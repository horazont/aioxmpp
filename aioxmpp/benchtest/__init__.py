########################################################################
# File name: __init__.py
# This file is part of: aioxmpp
#
# LICENSE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this program.  If not, see
# <http://www.gnu.org/licenses/>.
#
########################################################################
import collections
import contextlib
import math
import functools
import time
import unittest

from nose.plugins import Plugin


def autoscale_number(n, significant_digits=None):
    if abs(n) == 0:
        order_of_magnitude = 0
    else:
        order_of_magnitude = math.floor(math.log(n, 10))

    prefix_level = math.floor(order_of_magnitude / 3)
    prefix_level = min(6, max(-6, prefix_level))

    PREFIXES = {
        -6: "a",
        -5: "f",
        -4: "p",
        -3: "n",
        -2: "μ",
        -1: "m",
        0: "",
        1: "k",
        2: "M",
        3: "G",
        4: "T",
        5: "P",
        6: "E",
    }

    prefix_magnitude = prefix_level*3
    scale = 10**prefix_magnitude

    n /= scale

    if significant_digits is not None:
        digits = order_of_magnitude - prefix_magnitude + 1
        round_to = significant_digits - digits
        n = round(n, round_to)
        fmt_num = "{{:.{}f}}".format(max(round_to, 0))
    else:
        fmt_num = "{:f}"

    fmt = "{} {{prefix}}".format(fmt_num)

    return fmt.format(
        n,
        prefix=PREFIXES[prefix_level]
    )


class Accumulator:
    def __init__(self):
        super().__init__()
        self.items = []
        self.total = 0
        self.unit = None

    def add(self, value):
        self.items.append(value)
        self.total += value

    def set_unit(self, unit):
        if self.unit is not None and self.unit != unit:
            raise RuntimeError(
                "attempt to change unit of accumulator"
            )
        self.unit = unit

    @property
    def average(self):
        return self.total / self.total_runs

    @property
    def max(self):
        return max(self.items)

    @property
    def min(self):
        return min(self.items)

    @property
    def stddev(self):
        return math.sqrt(self.variance)

    @property
    def variance(self):
        avg = self.average
        accum = 0
        for value in self.items:
            accum += (value - avg)**2

        return accum / len(self.items)

    @property
    def total_runs(self):
        return len(self.items)

    def __str__(self):
        avg = self.average
        stddev = self.stddev
        if stddev == 0:
            digits = None
        else:
            digits = math.ceil(math.log(avg / stddev, 10))
        return "nsamples: {}; average: {}{}".format(
            self.total_runs,
            autoscale_number(avg, digits),
            self.unit or ""
        )


class Timer:
    start = None
    end = None

    @property
    def elapsed(self):
        if self.end is None or self.start is None:
            raise RuntimeError("timer is still running")
        return self.end - self.start


@contextlib.contextmanager
def timed(key=None):
    timer = Timer()
    t0 = time.monotonic()
    try:
        yield timer
    finally:
        t1 = time.monotonic()
        timer.start = t0
        timer.end = t1
        if key is not None:
            accum = _registry[key]
            accum.add(timer.elapsed)
            accum.set_unit("s")


def record(key, value, unit):
    accum = _registry[key]
    accum.set_unit(unit)
    accum.add(value)


def times(n, pass_iteration=False):
    if n < 1:
        raise ValueError(
            "times decorator needs at least one iteration"
        )

    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            base_kwargs = kwargs
            for i in range(n-1):
                if pass_iteration:
                    kwargs = dict(base_kwargs)
                    kwargs["iteration"] = i
                f(*args, **kwargs)
            if pass_iteration:
                kwargs = dict(base_kwargs)
                kwargs["iteration"] = n-1
            return f(*args, **kwargs)
        return wrapper

    return decorator


class BenchmarkPlugin(Plugin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def configure(self, options, conf):
        self.enabled = True
        global instance
        if self.enabled:
            instance = self

    def report(self, stream):
        for key, info in sorted(_registry.items(), key=lambda x: x[0]):
            if not info.total_runs:
                continue
            print(key, info, file=stream)


_registry = collections.defaultdict(Accumulator)
