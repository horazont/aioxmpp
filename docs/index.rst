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

.. _features:

Features
########

.. remember to update the feature list in the README

* Native :xep:`198` (Stream Management) support for robustness against transient
  network failures (such as switching between wireless and wired networks).

* Support for :rfc:`6121` (Instant Messaging and Presence,
  :mod:`aioxmpp.presence`, :mod:`aioxmpp.roster`) roster and presence
  management, along with :xep:`45` (Multi-User Chats, :mod:`aioxmpp.muc`) for
  your human-to-human  needs.

* Support for :xep:`60` (Publish-Subscribe, :mod:`aioxmpp.pubsub`) as well as powerful
  declarative-style definition of your own protocols (:mod:`aioxmpp.xso`,
  :mod:`aioxmpp.service`) for your machine-to-machine needs.

* Several other XEPs, such as :xep:`115` (Entity Capabilities,
  :mod:`aioxmpp.entitycaps`, including native support for reading and writing
  the `capsdb <https://github.com/xnyhps/capsdb>`_) and :xep:`131` (Stanza
  Headers and Internet Metadata, :mod:`aioxmpp.shim`).

* APIs suitable for both one-shot scripts and long-running multi-account
  clients.

* Secure by default: TLS is required by default, as well as certificate
  validation. Certificate or public key pinning can be used, if needed.

* Well-tested and modular codebase.

Check out the :ref:`ug-quick-start` to get started with :mod:`aioxmpp` now! ☺

Dependencies
############

.. remember to update the dependency list in the README

* Python ≥ 3.4 (or Python = 3.3 with tulip and enum34)
* DNSPython
* libxml2-devel (for some XML helpers)
* lxml
* `orderedset`__

  (Note that ``ordered_set`` does not work!)

  __ https://pypi.python.org/pypi/orderedset

* `tzlocal`__ (for i18n support)

  __ https://pypi.python.org/pypi/tzlocal

* `pyOpenSSL`__

  __ https://pypi.python.org/pypi/pyOpenSSL

* `pyasn1`_ and `pyasn1_modules`__

  .. _pyasn1: https://pypi.python.org/pypi/pyasn1
  __ https://pypi.python.org/pypi/pyasn1-modules

* `aiosasl`__

  __ https://pypi.python.org/pypi/aiosasl

* `multidict`__

  __ https://pypi.python.org/pypi/multidict

* `aioopenssl`__ (optional, for now)

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
