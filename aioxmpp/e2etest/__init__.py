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
import functools
import importlib
import os
import unittest

from nose.plugins import Plugin

from .utils import blocking
from .provision import Quirk  # NOQA


provisioner = None
config = None
timeout = 1


def require_feature(feature_var, argname=None):
    """
    :param feature_var: :xep:`30` feature ``var`` of the required feature
    :param argname: Optional argument name to pass the :class:`FeatureInfo` to

    Before running the function, it is tested that the feature specified by
    `feature_var` is provided in the environment of the current provisioner. If
    it is not, :class:`unittest.SkipTest` is raised to skip the test.

    If the feature is available, the :class:`FeatureInfo` instance is passed to
    the decorated function. If `argname` is :data:`None`, the feature info is
    passed as additional positional argument. otherwise, it is passed as
    keyword argument using the `argname`.
    """

    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            global provisioner
            info = provisioner.get_feature_info(feature_var)
            if info is None:
                raise unittest.SkipTest(
                    "provisioner does not provide a peer with "
                    "{!r}".format(feature_var)
                )

            if argname is None:
                args = args+(info,)
            else:
                kwargs[argname] = info

            return f(*args, **kwargs)
        return wrapper

    return decorator


def skip_with_quirk(quirk):
    """
    :param quirk: The quirk to skip on
    :type quirk: :class:`Quirks`

    If the provisioner indicates that the environment has the given `quirk`,
    the test is skipped.
    """

    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            global provisioner
            if provisioner.has_quirk(quirk):
                raise unittest.SkipTest(
                    "provisioner has quirk {!r}".format(quirk)
                )
            return f(*args, **kwargs)
        return wrapper

    return decorator


def blocking_with_timeout(timeout):
    def decorator(f):
        @blocking
        @functools.wraps(f)
        @asyncio.coroutine
        def wrapper(*args, **kwargs):
            yield from asyncio.wait_for(f(*args, **kwargs), timeout)
        return wrapper
    return decorator


def blocking_timed(f):
    @blocking
    @functools.wraps(f)
    @asyncio.coroutine
    def wrapper(*args, **kwargs):
        global timeout
        yield from asyncio.wait_for(f(*args, **kwargs), timeout)
    return wrapper


@blocking
@asyncio.coroutine
def setup_package():
    global provisioner, config, timeout
    if config is None:
        # AioxmppPlugin is not used -> skip all e2e tests
        for subclass in TestCase.__subclasses__():
            # XXX: this depends on unittest implementation details :)
            subclass.__unittest_skip__ = True
            subclass.__unittest_skip_why__ = \
                "this is not the aioxmpp test runner"
        return

    timeout = config.get("global", "timeout", fallback=timeout)

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
    global provisioner, config
    if config is None:
        return

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
            default=".local/e2etest.ini",
            help="Configuration file for end-to-end tests "
            "(default: .local/e2etest.ini)"
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
    @property
    def provisioner(self):
        global provisioner
        return provisioner
