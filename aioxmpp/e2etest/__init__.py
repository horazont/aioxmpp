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
"""
:mod:`~aioxmpp.e2etest` --- Framework for writing integration tests for :mod:`aioxmpp`
######################################################################################

This subpackage provides utilities for writing end-to-end or intgeration tests
for :mod:`aioxmpp` components.

.. warning::

   For now, the API of this subpackage is classified as internal. Please do not
   test your external components using this API, as it is experimental and
   subject to change.

Overview
========

The basic concept is that tests are written like normal unittests. However,
tests are written by inheriting classes from :class:`aioxmpp.e2etest.TestCase`
instead of :mod:`unittest.TestCase`. :class:`.e2etest.TestCase` has the
:attr:`~.e2etest.TestCase.provisioner` attribute which provides access to a
:class:`.provision.Provisioner` instance.

Provisioners are objects which provide a way to obtain a connected XMPP client.
The JID to which the client is bound is unspecified; however, each client gets
a unique bare JID and the clients are able to communicate with each other. In
addition, provisioners provide information about the environment in which the
clients act. This includes providing JIDs of entities implementing specific
protocols or features. The details are explained in the documentation of the
:class:`~.provision.Provisioner` base class.

By default, tests which are written with :class:`.e2etest.TestCase` are skipped
when using the normal test runners. This is because the provisioners need to be
configured; this is handled using a custom nosetests plugin which is not loaded
by default (for good reasons). To run the tests, use (instead of the normal
``nosetests3`` binary):

.. code-block:: console

   $ python3 -m aioxmpp.e2etest

The command line interface is identical to the one of ``nosetests3``, except
that additional options are provided to configure the plugin. In fact,
:mod:`aioxmpp.e2etest` is simply a nose test runner with an additional plugin.

By default, the configuration is read from ``./.local/e2etest.ini``. For
details on configuring the provisioners, see :ref:`the developer guide
<dg-end-to-end-tests>`.

Main API
========

Decorators for test methods
---------------------------

The following decorators can be used on test methods (including ``setUp`` and
``tearDown``):

.. autodecorator:: require_feature

.. autodecorator:: require_identity

.. autodecorator:: require_feature_subset

.. autodecorator:: skip_with_quirk

General decorators
------------------

.. autodecorator:: blocking()

.. autodecorator:: blocking_timed()

.. autodecorator:: blocking_with_timeout

Class for test cases
--------------------

.. autoclass:: TestCase

.. currentmodule:: aioxmpp.e2etest.provision

Provisioners
============

.. autoclass:: Provisioner

.. autoclass:: AnonymousProvisioner()

.. autoclass:: AnyProvisioner()

.. autoclass:: StaticPasswordProvisioner()

.. currentmodule:: aioxmpp.e2etest

.. autoclass:: Quirk

.. currentmodule:: aioxmpp.e2etest.provision

Helper functions
----------------

.. autofunction:: discover_server_features

.. autofunction:: configure_tls_config

.. autofunction:: configure_quirks
"""  # NOQA: E501
import asyncio
import configparser
import functools
import importlib
import logging
import os
import unittest

import pytest

from ..testutils import get_timeout
from .utils import blocking
from .provision import Quirk  # NOQA: F401


provisioner = None
config = None
only_e2etest = False
e2etest_record = None
timeout = get_timeout(1.0)


def require_feature(feature_var, argname=None, *, multiple=False):
    """
    :param feature_var: :xep:`30` feature ``var`` of the required feature
    :type feature_var: :class:`str`
    :param argname: Optional argument name to pass the :class:`FeatureInfo` to
    :type argname: :class:`str` or :data:`None`
    :param multiple: If true, all peers are returned instead of a random one.
    :type multiple: :class:`bool`

    Before running the function, it is tested that the feature specified by
    `feature_var` is provided in the environment of the current provisioner. If
    it is not, :class:`unittest.SkipTest` is raised to skip the test.

    If the feature is available, the :class:`FeatureInfo` instance is passed to
    the decorated function. If `argname` is :data:`None`, the feature info is
    passed as additional positional argument. otherwise, it is passed as
    keyword argument using the `argname`.

    If `multiple` is true, all peers supporting the given feature are passed
    in a set. Otherwise, only a random peer is returned.

    This decorator can be used on test methods, but not on test classes. If you
    want to skip all tests in a class, apply the decorator to the ``setUp``
    method.
    """
    if isinstance(feature_var, str):
        feature_var = [feature_var]

    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            global provisioner
            if multiple:
                arg = provisioner.get_feature_providers(feature_var)
                has_provider = bool(arg)
            else:
                arg = provisioner.get_feature_provider(feature_var)
                has_provider = arg is not None
            if not has_provider:
                raise unittest.SkipTest(
                    "provisioner does not provide a peer with "
                    "{!r}".format(feature_var)
                )

            if argname is None:
                args = args+(arg,)
            else:
                kwargs[argname] = arg

            return f(*args, **kwargs)
        return wrapper

    return decorator


def require_identity(category, type_, argname=None):
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            global provisioner
            arg = provisioner.get_identity_provider(category, type_)
            has_provider = arg is not None
            if not has_provider:
                raise unittest.SkipTest(
                    "provisioner does not provide a peer with a "
                    "{!r} identity".format((category, type_))
                )

            if argname is None:
                args = args+(arg,)
            else:
                kwargs[argname] = arg

            return f(*args, **kwargs)
        return wrapper

    return decorator


def require_feature_subset(feature_vars, required_subset=[]):
    required_subset = set(required_subset)
    feature_vars = set(feature_vars) | required_subset

    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            global provisioner
            jid, subset = provisioner.get_feature_subset_provider(
                feature_vars,
                required_subset
            )
            if jid is None:
                raise unittest.SkipTest(
                    "no peer could provide a subset of {!r} with at least "
                    "{!r}".format(
                        feature_vars,
                        required_subset,
                    )
                )

            return f(*(args+(jid, feature_vars)),
                     **kwargs)
        return wrapper

    return decorator


def require_pep(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        global provisioner
        if not provisioner.has_pep():
            raise unittest.SkipTest(
                "the provisioned account does not support PEP",
            )

        return f(*args, **kwargs)
    return wrapper


def skip_with_quirk(quirk):
    """
    :param quirk: The quirk to skip on
    :type quirk: :class:`Quirks`

    If the provisioner indicates that the environment has the given `quirk`,
    the test is skipped.

    This decorator can be used on test methods, but not on test classes. If you
    want to skip all tests in a class, apply the decorator to the ``setUp``
    method.
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
    """
    The decorated coroutine function is run using the
    :meth:`~asyncio.AbstractEventLoop.run_until_complete` method of the current
    (at the time of call) event loop.

    If the execution takes longer than `timeout` seconds,
    :class:`asyncio.TimeoutError` is raised.

    The decorated function behaves like a normal function and is not a
    coroutine function.

    This decorator must be applied to a coroutine function (or method).
    """

    def decorator(f):
        @blocking
        @functools.wraps(f)
        async def wrapper(*args, **kwargs):
            return await asyncio.wait_for(f(*args, **kwargs), timeout)
        return wrapper
    return decorator


def blocking_timed(f):
    """
    Like :func:`blocking_with_timeout`, the decorated coroutine function is
    executed using :meth:`asyncio.AbstractEventLoop.run_until_complete` with a
    timeout, but the timeout is configured in the end-to-end test configuration
    (see :ref:`dg-end-to-end-tests`).

    This is the recommended decorator for any test function or method, to
    prevent the tests from hanging when anythin goes wrong. The timeout is
    under control of the provisioner configuration, which means that it can be
    adapted to different setups (for example, running against an XMPP server in
    the internet will be slower than if it runs on localhost).

    The decorated function behaves like a normal function and is not a
    coroutine function.

    This decorator must be applied to a coroutine function (or method).
    """
    @blocking
    @functools.wraps(f)
    async def wrapper(*args, **kwargs):
        global timeout
        await asyncio.wait_for(f(*args, **kwargs), timeout)
    return wrapper


@blocking
async def setup_package():
    global provisioner, config, timeout
    if config is None:
        return

    timeout = config.getfloat("global", "timeout", fallback=timeout)

    provisioner_name = config.get("global", "provisioner")
    module_path, class_name = provisioner_name.rsplit(".", 1)
    mod = importlib.import_module(module_path)
    cls_ = getattr(mod, class_name)

    section = config[provisioner_name]
    provisioner = cls_()
    provisioner.configure(section)
    await provisioner.initialise()


def teardown_package():
    global provisioner, config
    if config is None:
        return

    loop = asyncio.get_event_loop()
    loop.run_until_complete(provisioner.finalise())
    loop.close()


class TestCase(unittest.TestCase):
    """
    A subclass of :class:`unittest.TestCase` for end-to-end test cases.

    This subclass provides a single additional attribute:

    .. autoattribute:: provisioner
    """

    __unittest_skip__ = True
    __unittest_skip_why__ = "this is not the aioxmpp test runner"

    @property
    def provisioner(self):
        """
        This is the configured :class:`.provision.Provisioner` instance.

        If no provisioner is configured (for example because the e2etest nose
        plugin is not loaded), this reads as :data:`None`.

        .. note::

           Under nosetests and the vanilla unittest runner, tests inheriting
           from :class:`TestCase` are automatically skipped if
           :attr:`provisioner` is :data:`None`.
        """
        global provisioner
        return provisioner


def pytest_load_initial_conftests(early_config, parser, args):
    parser.addoption(
        "--e2etest-config",
        dest="aioxmpp_e2e_config",
        default=".local/e2etest.ini",
        metavar="FILE",
        help="Configuration file for end-to-end tests "
        "(default: .local/e2etest.ini)",
    )
    parser.addoption(
        "--e2etest-record",
        dest="aioxmpp_e2e_record",
        metavar="FILE",
        default=None,
        help="A file to write a transcript to"
    )
    parser.addoption(
        "--e2etest-only",
        dest="aioxmpp_e2e_only",
        action="store_true",
        default=False,
        help="If set, only E2E tests will be executed."
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "aioxmpp_e2etest: end-to-end test")


def pytest_cmdline_main(config):
    return _pytest_cmdline_main_impl(config)


def _pytest_cmdline_main_impl(pytest_config):
    global config, only_e2etest, e2etest_record
    config = configparser.ConfigParser()
    with open(pytest_config.option.aioxmpp_e2e_config, "r") as f:
        config.read_file(f)

    e2etest_record = pytest_config.option.aioxmpp_e2e_record
    only_e2etest = pytest_config.option.aioxmpp_e2e_only
    TestCase.__unittest_skip__ = False


def pytest_sessionstart(session):
    setup_package()


def pytest_sessionfinish(session):
    teardown_package()


@pytest.hookimpl(hookwrapper=True)
def pytest_pycollect_makeitem(collector, name, obj):
    global config, only_e2etest
    outcome = yield
    item = outcome.get_result()
    if isinstance(obj, type) and issubclass(obj, TestCase):
        if config is None:
            item.add_marker(pytest.mark.skip("e2e tests not enabled"))
        else:
            item.add_marker("aioxmpp_e2etest")
    elif isinstance(obj, type) and issubclass(obj, unittest.TestCase):
        if only_e2etest:
            item.add_marker(pytest.mark.skip("only e2e tests enabled"))


def pytest_runtest_setup(item):
    global provisioner, e2etest_record
    if item.get_closest_marker("aioxmpp_e2etest") is not None:
        blocking(provisioner.setup)()


def pytest_runtest_call(item):
    if e2etest_record:
        handler = logging.FileHandler(
            e2etest_record, "w",
        )
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            "%(name)s: %(levelname)s: %(message)s",
            style="%"
        )
        handler.setFormatter(formatter)
        logger = logging.getLogger("aioxmpp.e2etest.provision")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)


def pytest_runtest_teardown(item):
    global provisioner
    if item.get_closest_marker("aioxmpp_e2etest") is not None:
        blocking(provisioner.teardown)()
