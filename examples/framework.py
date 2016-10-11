########################################################################
# File name: framework.py
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
import abc
import argparse
import asyncio
import configparser
import getpass
import json
import logging
import signal
import sys

try:
    import readline  # NOQA
except ImportError:
    pass

import aioxmpp


class Example(metaclass=abc.ABCMeta):
    def __init__(self):
        super().__init__()
        self.argparse = argparse.ArgumentParser()

    def prepare_argparse(self):
        self.argparse.add_argument(
            "-c", "--config",
            default=None,
            type=argparse.FileType("r"),
            help="Configuration file to read",
        )

        # this gives a nicer name in argparse errors
        def jid(s):
            return aioxmpp.JID.fromstr(s)

        self.argparse.add_argument(
            "-j", "--local-jid",
            type=jid,
            help="JID to authenticate with (only required if not in config)"
        )

        self.argparse.add_argument(
            "-p",
            dest="ask_password",
            action="store_true",
            default=False,
            help="Ask for password on stdio"
        )

        self.argparse.add_argument(
            "-v",
            help="Increase verbosity",
            default=0,
            dest="verbosity",
            action="count",
        )

    def configure(self):
        self.args = self.argparse.parse_args()
        logging.basicConfig(
            level={
                0: logging.ERROR,
                1: logging.WARNING,
                2: logging.INFO,
            }.get(self.args.verbosity, logging.DEBUG)
        )

        self.config = configparser.ConfigParser()
        if self.args.config is not None:
            with self.args.config:
                self.config.read_file(self.args.config)

        self.g_jid = self.args.local_jid
        if self.g_jid is None:
            try:
                self.g_jid = aioxmpp.JID.fromstr(
                    self.config.get("global", "local_jid"),
                )
            except (configparser.NoSectionError,
                    configparser.NoOptionError):
                self.g_jid = aioxmpp.JID.fromstr(
                    input("Account JID> ")
                )

        if self.config.has_option("global", "pin_store"):
            with open(self.config.get("global", "pin_store")) as f:
                pin_store = json.load(f)
            pin_type = aioxmpp.security_layer.PinType(
                self.config.getint("global", "pin_type", fallback=0)
            )
        else:
            pin_store = None
            pin_type = None

        if self.args.ask_password:
            password = getpass.getpass()
        else:
            password = self.config.get("global", "password")

        self.g_security_layer = aioxmpp.make_security_layer(
            password,
            pin_store=pin_store,
            pin_type=pin_type,
        )

    def make_simple_client(self):
        return aioxmpp.PresenceManagedClient(
            self.g_jid,
            self.g_security_layer,
        )

    def make_sigint_event(self):
        event = asyncio.Event()
        loop = asyncio.get_event_loop()
        loop.add_signal_handler(
            signal.SIGINT,
            event.set,
        )
        return event

    @asyncio.coroutine
    def run_simple_example(self):
        raise NotImplementedError(
            "run_simple_example must be overriden if run_example isn’t"
        )

    @asyncio.coroutine
    def run_example(self):
        self.client = self.make_simple_client()
        cm = self.client.connected()
        aexit = cm.__aexit__
        yield from cm.__aenter__()
        try:
            yield from self.run_simple_example()
        except:
            if not (yield from aexit(*sys.exc_info())):
                raise
        else:
            yield from aexit(None, None, None)


def exec_example(example):
    example.prepare_argparse()
    example.configure()
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(example.run_example())
    finally:
        loop.close()
