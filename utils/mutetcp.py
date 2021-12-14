#!/usr/bin/python3
########################################################################
# File name: mutetcp.py
# This file is part of: aioxmpp
#
# LICENSE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at
# your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
########################################################################
import collections
import math
import subprocess
import textwrap
import time

Conn = collections.namedtuple(
    "Conn",
    [
        "proto",
        "laddr",
        "raddr",
        "state",
        "pid",
        "prog"
    ])

def get_connections(search_for_pid=None, search_for_prog=None):
    rows = subprocess.check_output(["netstat", "-tnWp"]).split(b"\n")
    for line in rows:
        line = line.strip()
        parts = line.split()
        try:
            proto, _, _, laddr, raddr, state, pid_prog = parts
        except ValueError:
            # print("skipping input: {}".format(parts))
            continue

        proto = proto.decode()
        laddr = laddr.decode()
        raddr = raddr.decode()
        state = state.decode()

        if pid_prog == b"-":
            pid = None
            prog = None
        else:
            pid, prog = pid_prog.split(b"/", 1)
            pid = int(pid)
            prog = prog.decode("utf8")

        if search_for_pid is not None and pid != search_for_pid:
            continue
        if search_for_prog is not None and prog != search_for_prog:
            continue

        yield Conn(proto, laddr, raddr, state, pid, prog)

def get_connections_by_pid(**kwargs):
    pidmap = {}
    for conn in get_connections(**kwargs):
        pidmap.setdefault(conn.pid, (conn.prog, []))[1].append(conn)

    return pidmap

def select_from_list(keylist, items, formatter, prompt, *, allow_all=False):
    for key in keylist:
        item = items[key]
        print(formatter(key, item))

    while True:
        try:
            s = input(prompt)
            key = int(s)
            value = items[key]
        except ValueError as err:
            if s == "a" and allow_all:
                return None
            print(str(err))
            continue
        except (IndexError, KeyError) as err:
            print("not a valid entry: {}".format(err))
            continue
        break

    return value

def select_process(pidmap):
    pids = sorted(pidmap.keys())
    width = math.ceil(math.log(max(pids), 10))
    formatter = ("({{pid:>{width}d}})  {{progname}} "
                 "({{nconn}} connection{{nconn_pls}})").format(width=width)

    def fmt(pid, progconns):
        nonlocal formatter
        prog, conns = progconns
        return formatter.format(
            pid=pid,
            progname=prog,
            nconn=len(conns),
            nconn_pls="s" if len(conns) != 1 else ""
        )

    print("select a process from the list below, by typing its pid")
    print("({{pid:<{width}s}})  {{info}}".format(width=width).format(
        pid="pid",
        info="info"))
    return select_from_list(pids, pidmap, fmt, "(pid)> ")

def select_conn(conns):
    width = math.ceil(math.log(len(conns), 10))
    formatter = (
        "({{connno:>{width}d}})  {{laddr:30s}} <-> {{raddr:30s}}"
    ).format(width=width)

    def fmt(connno, conn):
        nonlocal formatter
        return formatter.format(
            connno=connno,
            laddr=conn.laddr,
            raddr=conn.raddr
        )

    numbers = list(range(len(conns)))
    print("select a connection from the list below")
    print("({{connno:<{width}s}})  {{info}}".format(width=width).format(
        connno="connno",
        info="info"))
    return select_from_list(numbers, conns, fmt, "(connno)> ")

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-p", "--pid",
        default=None)
    parser.add_argument(
        "-P", "--prog",
        default=None)

    args = parser.parse_args()

    pidmap = get_connections_by_pid(search_for_pid=args.pid,
                                    search_for_prog=args.prog)

    if len(pidmap) > 1:
        print("process selector was ambiguous")
        _, conns = select_process(pidmap)
    elif pidmap:
        _, conns = list(pidmap.values())[0]
    else:
        print("no matching process found")
        sys.exit(1)

    if len(conns) > 1:
        conn = select_conn(conns)
    else:
        conn = conns.pop()

    laddr, lport = conn.laddr.rsplit(":", 1)
    raddr, rport = conn.raddr.rsplit(":", 1)

    print("\n".join(
        textwrap.wrap("muting connection between [{}]:{} (local) and [{}]:{} "
                      "(remote), on process {} (pid={})".format(
                          laddr, lport, raddr, rport, conn.prog, conn.pid))))

    if conn.proto.endswith("6"):
        # ipv6
        iptables = "ip6tables"
    else:
        iptables = "iptables"

    subprocess.check_call(
        [iptables, "-I", "INPUT",
         "-s", raddr,
         "-d", laddr,
         "-p", "tcp",
         "--sport", rport,
         "--dport", lport,
         "-j", "DROP"])

    print("use ^C (SIGINT) to un-mute")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        subprocess.check_call([iptables, "-D", "INPUT", "1"])
