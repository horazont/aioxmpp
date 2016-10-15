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
import configparser
import importlib
import os
import unittest

from nose.plugins import Plugin

from .utils import blocking


provisioner = None


@blocking
@asyncio.coroutine
def setup_package():
    global provisioner, config
    provisioner_name = config.get("global", "provisioner")
    module_path, class_name = provisioner_name.rsplit(".", 1)
    mod = importlib.import_module(module_path)
    cls_ = getattr(mod, class_name)

    section = config[provisioner_name]
    provisioner = cls_()
    provisioner.configure(section)
    yield from provisioner.initialise()


@asyncio.coroutine
def teardown_package():
    global provisioner
    loop = asyncio.get_event_loop()
    loop.run_until_complete(provisioner.finalise())
    loop.close()


class AioxmppPlugin(Plugin):
    name = "aioxmpp"

    def options(self, options, env=os.environ):
        # super().options(options, env=env)
        options.add_option(
            "--e2etest-config",
            dest="aioxmpptest_config",
            metavar="FILE",
            default="e2etest.ini",
            help="Configuration file for end-to-end tests "
            "(default: e2etest.ini)"
        )

    def configure(self, options, conf):
        self.enabled = True
        global config
        config = configparser.ConfigParser()
        with open(options.aioxmpptest_config, "r") as f:
            config.read_file(f)

    @blocking
    @asyncio.coroutine
    def beforeTest(self, test):
        global provisioner
        if provisioner is not None:
            yield from provisioner.setup()

    @blocking
    @asyncio.coroutine
    def afterTest(self, test):
        global provisioner
        if provisioner is not None:
            yield from provisioner.teardown()


class TestCase(unittest.TestCase):
    def setUp(self):
        global provisioner
        self.provisioner = provisioner

    def tearDown(self):
        pass
