``aioxmpp``
###########

... is a pure-python XMPP library using the `asyncio`_ standard library module from Python 3.4 (and `available as a third-party module to Python 3.3`__).

.. _asyncio: https://docs.python.org/3/library/asyncio.html
__ https://code.google.com/p/tulip/

Dependencies
------------

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


Design goals
------------

* Powerful API to implement all sorts of XEPs
* Reliable message transmission even under dire network circumstances
* Well-tested code base
* A more compelling README than this

Change log
----------

The `change log`_ is included in the `official documentation`__.

.. _change log: http://docs.zombofant.net/aioxmpp/devel/api/changelog.html
__ http://docs.zombofant.net/aioxmpp/0.5/
