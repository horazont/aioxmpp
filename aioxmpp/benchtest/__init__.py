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
import asyncio
import collections
import contextlib
import importlib
import math
import functools
import time
import os

from nose.plugins import Plugin


def scaleinfo(n, significant_digits=None):
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
        rhs = max(round_to, 0)
        lhs = max(math.floor(math.log(n, 10))+1, 1)
        return n, round_to, (lhs, rhs), PREFIXES[prefix_level]
    else:
        s = str(n)
        lhs = s.index(".")
        rhs = len(s)-s.index(".")-1
        return n, 3, (lhs, rhs), PREFIXES[prefix_level]


def autoscale_number(n, significant_digits=None):
    n, round_to, _, prefix = scaleinfo(n, significant_digits)
    n = round(n, round_to)
    fmt_num = "{{:.{}f}}".format(max(round_to, 0))
    fmt = "{} {{prefix}}".format(fmt_num)
    return fmt.format(
        n,
        prefix=prefix
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

    def infodict(self):
        return {
            "nsamples": self.total_runs,
            "avg": self.average,
            "total": self.total,
            "stddev": self.stddev,
            "min": self.min,
            "max": self.max,
        }

    @property
    def structured_avg(self):
        avg = self.average
        stddev = self.stddev
        if stddev == 0:
            digits = None
        else:
            digits = math.ceil(math.log(avg / stddev, 10))
        return scaleinfo(avg, digits) + (self.unit,)

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

    def options(self, options, env=os.environ):
        options.add_option(
            "--benchmark-report",
            dest="aioxmpp_bench_report",
            default=None,
            metavar="FILE",
            help="File to save the report to",
        )
        options.add_option(
            "--benchmark-eventloop",
            dest="aioxmpp_eventloop",
            default=None,
            metavar="CLASS",
            help="Event loop policy class to use",
        )

    def configure(self, options, conf):
        self.enabled = True
        self.report_filename = options.aioxmpp_bench_report
        if options.aioxmpp_eventloop is not None:
            module_name, cls_name = options.aioxmpp_eventloop.rsplit(".", 1)
            module = importlib.import_module(module_name)
            cls = getattr(module, cls_name)()
            asyncio.set_event_loop_policy(cls)
            asyncio.set_event_loop(asyncio.new_event_loop())

    def report(self, stream):
        data = {}
        table = []
        for key, info in sorted(_registry.items(), key=lambda x: x[0]):
            if not info.total_runs:
                continue
            table.append(
                (
                    ".".join(key[:2]),
                    "/".join(key[2:]),
                    info.total_runs,
                    info.structured_avg,
                ),
            )
            data[key] = info.infodict()

        table.sort()
        c12len = max(len(c1)+len(c2)+2 for c1, c2, *_ in table)
        c12fmt = "{{:<{}s}}".format(c12len)
        c3len = max(math.floor(math.log10(v)) + 1
                    for _, _, v, *_ in table)
        c3fmt = "{{:>{}d}}".format(c3len)
        c4lhs = max(lhs for _, _, _, (_, _, (lhs, _), _, _) in table)
        c4rhs = max(rhs for _, _, _, (_, _, (_, rhs), _, _) in table)
        for c1, c2, c3, (v, round_to, (lhs, rhs), prefix, unit) in table:
            c4numberfmt = "{{:{}.{}f}}".format(
                lhs+rhs+1,
                rhs
            )
            if rhs == 0:
                lhs += 1
            c4num = "".join([
                " "*(c4lhs-lhs),
                c4numberfmt.format(v),
                "." if rhs == 0 else "",
                " "*(c4rhs-rhs)
            ])

            print(
                c12fmt.format("{}  {}".format(c1, c2)),
                c3fmt.format(c3),
                "{} {}{}".format(
                    c4num,
                    prefix or " ",
                    unit,
                ),
                sep="  ",
                file=stream
            )

        if self.report_filename is not None:
            with open(self.report_filename, "w") as f:
                f.write(repr(data))


_registry = collections.defaultdict(Accumulator)
