Developer Guide
###############

This (very incomplete) document aims at providing some guidance for current and
future developers working on :mod:`aioxmpp`.

Testing
=======

:mod:`aioxmpp` is developed in test-driven development style. You can read up on
the internet what this means in detail, but it boils down to "write code only to
fix tests and write tests to justify writing code".

This implies that the :mod:`aioxmpp` test suite is pretty extensive, and using
the default python unittest runner is not very useful. The recommended test
runner to use is `Nose <https://nose.readthedocs.io/en/latest/>`_. Nose can be
invoked directly (from within the aioxmpp source repository) on the test suite:

.. code-block:: console

   $ nosetests3 tests


End-to-end tests (or integration tests)
---------------------------------------

The normal unittest suite is quite nice, but it consists mostly of unit tests,
which have an important flaw: the *interaction* between units is not well
tested. There are a few exceptions, such as ``tests/test_highlevel.py`` which
tests very few operations through the whole stack (very few, because it is very
cumbersome to write tests in that manner).

To remedy that, :mod:`aioxmpp` features a specialised test runner which allows
for running :mod:`aioxmpp` tests against a real XMPP server. It requires a bit
of configuration (read on), so it won’t work out of the box. It can be invoked
using:

.. code-block:: console

   $ python3 -m aioxmpp.e2etest tests

It needs to be configured though. For this, an ini-style configuration file
(using :mod:`configparser`) is read. The default location is
``./.local/e2etest.ini``, but it can be overriden with the ``--e2etest-config``
command line option.

.. note::

   ``aioxmpp.e2etest`` uses Nose for everything and patches in a plugin and a
   few helper functions to provide the advanced testing functionality. This is
   also why the vanilla nosetests runner doesn’t break on the test cases.

The following global configuration options exist:

.. code-block:: ini

  [global]
  timeout=1
  provisioner=

``provisioner`` must be set to point to a Python class which inherits from
:class:`aioxmpp.e2etest.provision.Provisioner`. The above value is an example.
Each provisioner has different configuration options. The different provisioners
are explained in detail below.

``timeout`` specifies the default timeout for each individual test in seconds.
The default is 1 second. If you have a slow connection to the server, it may be
reasonable to increase this to a higher value.

To test that you got your configuration correct, use:

.. code-block:: console

   $ python3 -m aioxmpp.e2etest tests/test_e2e.py:TestConnect

This should run a single test, which should pass.

Anonymous provisioner
~~~~~~~~~~~~~~~~~~~~~

The anonymous provisioner uses the ``ANONYMOUS`` SASL mechanism to authenticate
with the target XMPP server. This is the most simple provisioner conceivable. An
example config file using that provisioner looks like this:

.. code-block:: ini

  [global]
  provisioner=aioxmpp.e2etest.provision.AnonymousProvisioner

  [aioxmpp.e2etest.provision.AnonymousProvisioner]
  host=localhost
  pin_store=pinstore.json
  pin_type=0

The ``aioxmpp.e2etest.provision.AnonymousProvisioner`` contains the options
specific to that provisioner. ``host`` must be a valid JID domainpart and the
XMPP host to connect to. ``pin_store`` and ``pin_type`` can be used to configure
certificate pinning, in case the server you want to test against does not have a
certificate which passes the default OpenSSL PKIX tests.

If set, ``pin_store`` must point to a JSON file, which consists of a single
object mapping host names to arrays of strings containing the base64
representation of what is being pinned. This is determined by ``pin_type``,
which can be ``0`` for Public Key pinning and ``1`` for Certificate pinning.

There is also the ``no_verify`` option, which, if set to true, will disable
certificate verification altogether. This does not much harm if you are testing
against localhost anyways and saves the configuration nuisance for certificate
pinning. ``no_verfiy`` takes precedence over ``pin_store`` and ``pin_type``.


Writing end-to-end tests
------------------------

For now, please see ``tests/test_e2e.py`` as a reference. A few key points:

* Make sure to inherit from :class:`aioxmpp.e2etest.TestCase` instead of
  :class:`unittest.TestCase`. This will prevent the tests from running with the
  normal nosetests runner and also give you the current provisioner as
  ``self.provisioner``.

* The :func:`aioxmpp.e2etest.blocking` decorator can be used everywhere to
  convert a coroutine function to a normal function. It works by wrapping the
  coroutine function in a :meth:`asyncio.BaseEventLoop.run_until_complete` call,
  with the usual implications.

* You do not need to clean up the clients obtained from the provisioner; the
  provisioner will stop them when the test is over (as if by using a
  ``tearDown`` method).

* Depending on the provisioner, the number of clients you can use at the same
  time may be limited; the anonymous provisioner has no limit.
