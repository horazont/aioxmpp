``aioxmpp``
###########

.. image:: https://travis-ci.org/horazont/aioxmpp.svg?branch=devel
  :target: https://travis-ci.org/horazont/aioxmpp

.. image:: https://coveralls.io/repos/github/horazont/aioxmpp/badge.svg?branch=devel
  :target: https://coveralls.io/github/horazont/aioxmpp?branch=devel

.. image:: https://img.shields.io/pypi/v/aioxmpp.svg
  :target: https://pypi.python.org/pypi/aioxmpp/

... is a pure-python XMPP library using the `asyncio`_ standard library module from Python 3.4 (and `available as a third-party module to Python 3.3`__).

.. _asyncio: https://docs.python.org/3/library/asyncio.html
__ https://code.google.com/p/tulip/

.. remember to update the feature list in the docs

Features
========

* Native `Stream Management (XEP-0198)
  <https://xmpp.org/extensions/xep-0198.html>`_ support for robustness against
  transient network failures (such as switching between wireless and wired
  networks).

* Powerful declarative-style definition of XEP-based and custom protocols. Most
  of the time, you will not get in contact with raw XML or character data, even
  when implementing a new protocol.

* Secure by default: TLS is required by default, as well as certificate
  validation. Certificate or public key pinning can be used, if needed.

* Support for `RFC 6121 (Instant Messaging and Presence)
  <https://tools.ietf.org/html/rfc6121>`_ roster and presence management, along
  with `XEP-0045 (Multi-User Chats)
  <https://xmpp.org/extensions/xep-0045.html>`_ for your human-to-human needs.

* Support for `XEP-0060 (Publish-Subscribe)
  <https://xmpp.org/extensions/xep-0060.html>`_ and `XEP-0050 (Ad-Hoc Commands)
  <https://xmpp.org/extensions/xep-0050.html>`_ for your machine-to-machine
  needs.

* Several other XEPs, such as `XEP-0115
  <https://xmpp.org/extensions/xep-0115.html>`_ (including native support for
  the reading and writing the `capsdb <https://github.com/xnyhps/capsdb>`_) and
  `XEP-0131 <https://xmpp.org/extensions/xep-0131.html>`_.

* APIs suitable for both one-shot scripts and long-running multi-account
  clients.

* Well-tested and modular codebase: aioxmpp is developed in test-driven
  style and in addition to that, many modules are automatedly tested against
  `Prosody <https://prosody.im/>`_ and `ejabberd <https://www.ejabberd.im/>`_,
  two popular XMPP servers.


There is more and there’s yet more to come! Check out the list of supported XEPs
in the `official documentation`_ and `open GitHub issues tagged as enhancement
<https://github.com/horazont/aioxmpp/issues?q=is%3Aissue+is%3Aopen+label%3Aenhancement>`_
for things which are planned and read on below on how to contribute.

Documentation
=============

The ``aioxmpp`` API is thoroughly documented using Sphinx. Check out the `official documentation`_ for a `quick start`_ and the `API reference`_.

Dependencies
============

* Python ≥ 3.4 (or Python = 3.3 with tulip and enum34)
* DNSPython
* lxml
* `sortedcollections`__

  __ https://pypi.python.org/pypi/sortedcollections

* `tzlocal`__ (for i18n support)

  __ https://pypi.python.org/pypi/tzlocal

* `pyOpenSSL`__

  __ https://pypi.python.org/pypi/pyOpenSSL

* `pyasn1`_ and `pyasn1_modules`__

  .. _pyasn1: https://pypi.python.org/pypi/pyasn1
  __ https://pypi.python.org/pypi/pyasn1-modules

* `aiosasl`__ (≥ 0.3 for ``ANONYMOUS`` support)

  __ https://pypi.python.org/pypi/aiosasl

* `multidict`__

  __ https://pypi.python.org/pypi/multidict

* `aioopenssl`__

  __ https://github.com/horazont/aioopenssl

* `typing`__ (Python < 3.5 only)

  __ https://pypi.python.org/pypi/typing

Contributing
============

If you consider contributing to aioxmpp, you can do so, even without a GitHub
account. There are several ways to get in touch with the aioxmpp developer(s):

* `The development mailing list
  <https://lists.zombofant.net/cgi-bin/mailman/listinfo/aioxmpp-devel>`_. Feel
  free to subscribe and post, but be polite and adhere to the `Netiquette
  (RFC 1855) <https://tools.ietf.org/html/rfc1855>`_. Pull requests posted to
  the mailing list are also welcome!

* The development MUC at ``aioxmpp@conference.zombofant.net``. Pull requests
  announced in the MUC are also welcome! Note that the MUC is set persistent,
  but nevertheless there may not always be people around. If in doubt, use the
  mailing list instead.

* Open or comment on an issue or post a pull request on `GitHub
  <https://github.com/horazont/aioxmpp/issues>`_.

No idea what to do, but still want to get your hands dirty? Check out the list
of `'help wanted' issues on GitHub
<https://github.com/horazont/aioxmpp/issues?q=is%3Aissue+is%3Aopen+label%3A%22help+wanted%22>`_
or ask in the MUC or on the mailing list. The issues tagged as 'help wanted' are
usually of narrow scope, aimed at beginners.

Be sure to read the ``docs/CONTRIBUTING.rst`` for some hints on how to
author your contribution.

Security issues
---------------

If you believe that a bug you found in aioxmpp has security implications,
you are welcome to notify me privately. To do so, send a mail to `Jonas Schäfer
<mailto:jonas@wielicki.name>`_, encrypted using the GPG public key
0xE5EDE5AC679E300F (Fingerprint AA5A 78FF 508D 8CF4 F355  F682 E5ED E5AC 679E
300F).

If you prefer to disclose security issues immediately, you can do so at any of
the places listed above.

More details can be found in the `SECURITY.md <SECURITY.md>`_ file.

Change log
==========

The `change log`_ is included in the `official documentation`_.

.. _change log: https://docs.zombofant.net/aioxmpp/0.13/api/changelog.html
.. _official documentation: https://docs.zombofant.net/aioxmpp/0.13/
.. _quick start: https://docs.zombofant.net/aioxmpp/0.13/user-guide/quickstart.html
.. _API reference: https://docs.zombofant.net/aioxmpp/0.13/api/index.html
