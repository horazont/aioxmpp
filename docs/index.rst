.. aioxmpp documentation master file, created by
   sphinx-quickstart on Mon Dec  1 08:14:58 2014.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to aioxmpp's documentation!
########################################

Welcome to the documentation of :mod:`aioxmpp`! In case you do not know,
:mod:`aioxmpp` is a pure-python XMPP library written for use with
:mod:`asyncio`.

If you are new to :mod:`aioxmpp`, you should check out the
:ref:`ug-quick-start`, or read on below for an overview of the :ref:`features`
of :mod:`aioxmpp`. If you want to check the API reference to look something up,
you should head to :ref:`api`.

Contents:

.. toctree::
   :maxdepth: 2

   user-guide/index.rst
   api/index.rst
   dev-guide/index.rst

.. _features:

Feature overview
################

.. remember to update the feature list in the README

* Native :xep:`198` (Stream Management) support for robustness against transient
  network failures (such as switching between wireless and wired networks).

* Powerful declarative-style definition of XEP-based and custom protocols via
  :mod:`aioxmpp.xso` and :mod:`aioxmpp.service`. Most of the time, you will not
  get in contact with raw XML or character data, even when implementing a new
  protocol.

* Secure by default: TLS is required by default, as well as certificate
  validation. Certificate or public key pinning can be used, if needed.

* Support for :rfc:`6121` (Instant Messaging and Presence,
  :mod:`aioxmpp.presence`, :mod:`aioxmpp.roster`) roster and presence
  management, along with :xep:`45` (Multi-User Chats, :mod:`aioxmpp.muc`) for
  your human-to-human  needs.

* Support for :xep:`60` (Publish-Subscribe, :mod:`aioxmpp.pubsub`) and :xep:`50`
  (Ad-Hoc Commands, :mod:`aioxmpp.adhoc`) for your machine-to-machine needs.

* Several other XEPs, such as :xep:`115` (Entity Capabilities,
  :mod:`aioxmpp.entitycaps`, including native support for reading and writing
  the `capsdb <https://github.com/xnyhps/capsdb>`_) and :xep:`131` (Stanza
  Headers and Internet Metadata, :mod:`aioxmpp.shim`).

* APIs suitable for both one-shot scripts and long-running multi-account
  clients.

* Well-tested and modular codebase: :mod:`aioxmpp` is developed in test-driven
  style and many modules are automatedly tested against a
  `Prosody <https://prosody.im/>`_ 0.9, 0.10 and the most recent development
  version, as well as `ejabberd <https://www.ejabberd.im/>`_, two popular XMPP
  servers.

  .. image:: https://travis-ci.org/horazont/aioxmpp.svg?branch=devel
    :target: https://travis-ci.org/horazont/aioxmpp

  .. image:: https://coveralls.io/repos/github/horazont/aioxmpp/badge.svg?branch=devel
    :target: https://coveralls.io/github/horazont/aioxmpp?branch=devel

Check out the :ref:`ug-quick-start` to get started with :mod:`aioxmpp` now! ☺

Supported protocols
===================

The referenced standards are ordered by their serial number. Not included are
specifications which define procedures which were followed or which are
described in the documentation. Those are also linked at the respective places
throughout the docs.

From IETF RFCs
--------------

* :rfc:`4505` (SASL ANONYMOUS), see :func:`aioxmpp.make_security_layer` and :mod:`aiosasl`
* :rfc:`4616` (SASL PLAIN), see :func:`aioxmpp.make_security_layer` and :mod:`aiosasl`
* :rfc:`5802` (SASL SCRAM), see :func:`aioxmpp.make_security_layer` and :mod:`aiosasl`
* :rfc:`6120` (XMPP Core), including some of the legacy from :rfc:`3920`
* :rfc:`6121` (XMPP Instant Messaging and Presence)

  * see :mod:`aioxmpp.presence` for managing inbound presence
  * see :mod:`aioxmpp.roster` for managing the roster and presence subscriptions

* :rfc:`6122` (XMPP Address Format)

From XMPP Extension Proposals (XEPs)
------------------------------------

* :xep:`4` (Data Forms), see :mod:`aioxmpp.forms`
* :xep:`30` (Service Discovery), see :mod:`aioxmpp.disco`
* :xep:`45` (Multi-User Chat), see :mod:`aioxmpp.muc`
* :xep:`48` (Bookmarks), see :mod:`aioxmpp.bookmarks`
* :xep:`49` (Private XML Storage), see :mod:`aioxmpp.private_xml`
* :xep:`50` (Ad-Hoc Commands), see :mod:`aioxmpp.adhoc` (no support for offering
  commands to other entities)
* :xep:`59` (Result Set Management), see :mod:`aioxmpp.rsm`
* :xep:`60` (Publish-Subscribe), see :mod:`aioxmpp.pubsub`
* :xep:`66` (Out-of-Band Data), schema-only, see :mod:`aioxmpp.misc`
* :xep:`68` (Field Standardisation for Data Forms), see :mod:`aioxmpp.forms`
* :xep:`77` (In-Band Registration), see :mod:`aioxmpp.ibr`
* :xep:`82` (XMPP Date and Time Profiles), via :class:`aioxmpp.xso.DateTime` and others
* :xep:`84` (User Avatar), see :mod:`aioxmpp.avatar`
* :xep:`92` (Software Version), see :mod:`aioxmpp.version`
* :xep:`115` (Entity Capabilities), see :mod:`aioxmpp.entitycaps`, including
  read/write support for the capsdb
* :xep:`163` (Personal Eventing Protocol), see :mod:`aioxmpp.pep`
* :xep:`184` (Message Delivery Receipts), see :mod:`aioxmpp.mdr`
* :xep:`191` (Blocking Command), see :mod:`aioxmpp.blocking`
* :xep:`198` (Stream Management), always enabled if supported by the server
* :xep:`199` (XMPP Ping), used for aliveness-checks if Stream Management is not
  avaliable and :mod:`aioxmpp.ping`
* :xep:`203` (Delayed Delivery), see :mod:`aioxmpp.misc`
* :xep:`249` (Direct MUC Invitations), see :mod:`aioxmpp.muc`
* :xep:`297` (Stanza Forwarding), see :mod:`aioxmpp.misc`
* :xep:`280` (Message Carbons), see :mod:`aioxmpp.carbons`
* :xep:`300` (Use of Cryptographic Hash Functions in XMPP),
  see :mod:`aioxmpp.hashes`
* :xep:`333` (Chat Markers), schema-only, see :mod:`aioxmpp.misc`
* :xep:`363` (HTTP Upload), see :mod:`aioxmpp.httpupload`
* :xep:`368` (SRV records for XMPP over TLS)
* :xep:`379` (Pre-Authenticared Roster Subscription), schema-only, see
  :mod:`aioxmpp.misc`
* :xep:`390` (Entity Capabilities 2.0), see :mod:`aioxmpp.entitycaps`


Dependencies
############

.. remember to update the dependency list in the README

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


Contributing
############

The contribution guidelines are outlined in the README in the source code
repository. The repository is `hosted at GitHub
<https://github.com/horazont/aioxmpp/>`_.


Security Issues
###############

If you believe that a bug you found in aioxmpp has security implications,
you are welcome to notify me privately. To do so, send a mail to `Jonas Wielicki
<mailto:jonas@wielicki.name>`_, encrypted using the GPG public key::

  0xE5EDE5AC679E300F
  Fingerprint AA5A 78FF 508D 8CF4 F355  F682 E5ED E5AC 679E 300F

If you prefer to disclose security issues immediately, you can do so at any of
the places listed in the contribution guidelines (see above).


Indices and tables
##################

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
