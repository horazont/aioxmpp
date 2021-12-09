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
import logging.config
import os
import os.path
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

        config_default_path = os.path.join(
            os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
            "aioxmpp_examples.ini")
        if not os.path.exists(config_default_path):
            config_default_path = None

        self.argparse.add_argument(
            "-c", "--config",
            default=config_default_path,
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

        mutex = self.argparse.add_mutually_exclusive_group()
        mutex.add_argument(
            "-p",
            dest="ask_password",
            action="store_true",
            default=False,
            help="Ask for password on stdio"
        )
        mutex.add_argument(
            "-A",
            nargs="?",
            dest="anonymous",
            default=False,
            help="Perform ANONYMOUS authentication"
        )

        self.argparse.add_argument(
            "-v",
            help="Increase verbosity (this has no effect if a logging config"
            " file is specified in the config file)",
            default=0,
            dest="verbosity",
            action="count",
        )

    def configure(self):
        self.args = self.argparse.parse_args()
        self.config = configparser.ConfigParser()
        if self.args.config is not None:
            with self.args.config:
                self.config.read_file(self.args.config)

        if self.config.has_option("global", "logging"):
            logging.config.fileConfig(
                self.config.get("global", "logging")
            )
        else:
            logging.basicConfig(
                level={
                    0: logging.ERROR,
                    1: logging.WARNING,
                    2: logging.INFO,
                }.get(self.args.verbosity, logging.DEBUG)
            )

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

        anonymous = self.args.anonymous
        if anonymous is False:
            if self.args.ask_password:
                password = getpass.getpass()
            else:
                try:
                    jid_sect = str(self.g_jid)
                    if jid_sect not in self.config:
                        jid_sect = "global"
                    password = self.config.get(jid_sect, "password")
                except (configparser.NoOptionError,
                        configparser.NoSectionError):
                    logging.error(('When the local JID %s is set, password ' +
                                   'must be set as well.') % str(self.g_jid))
                    raise
        else:
            password = None
            anonymous = anonymous or ""

        no_verify = self.config.getboolean(
            str(self.g_jid), "no_verify",
            fallback=self.config.getboolean("global", "no_verify",
                                            fallback=False)
        )
        logging.info(
            "constructing security layer with "
            "pin_store=%r, "
            "pin_type=%r, "
            "anonymous=%r, "
            "no_verify=%r, "
            "not-None password %s",
            pin_store,
            pin_type,
            anonymous,
            no_verify,
            password is not None,
        )

        self.g_security_layer = aioxmpp.make_security_layer(
            password,
            pin_store=pin_store,
            pin_type=pin_type,
            anonymous=anonymous,
            no_verify=no_verify,
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

    async def run_simple_example(self):
        raise NotImplementedError(
            "run_simple_example must be overridden if run_example isn’t"
        )

    async def run_example(self):
        self.client = self.make_simple_client()
        async with self.client.connected():
            await self.run_simple_example()


def exec_example(example):
    example.prepare_argparse()
    example.configure()
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(example.run_example())
    finally:
        loop.close()
