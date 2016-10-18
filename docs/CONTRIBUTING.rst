Contribution guidelines
#######################

* Adhere to `PEP 8 <https://www.python.org/dev/peps/pep-0008>`_ wherever
  possible and deviate from it where it makes sense. Follow the style of the
  code around you.

* Make sure the test suite passes with and without your change. If the test
  suite does not pass without your change, check if an issue exists for that
  failure, and if not, `open an issue on GitHub
  <https://github.com/horazont/aioxmpp/issues/new>`_ or post to the mailing list
  (see the ``README.rst`` for details) if you do not have a GitHub account.

* Write tests for your code, preferably in test-driven development style.
  Patches without good test coverage are less likely to be accepted, because
  someone will have to write tests for them.

* If possible, get in touch with the developers via the `mailing list
  <https://lists.zombofant.net/cgi-bin/mailman/listinfo/aioxmpp-devel>`_ or the
  XMPP Multi-User Chat before and while you are working on your patch. See the
  ``README.rst`` for contact opportunities.

* If your code implements a XEP, double-check that the schema in the XEP matches
  the examples and the text. It is tempting to simply convert the schema to XSO
  classes, but often the schema is slightly wrong. `The schema is only
  informative!
  <http://mail.jabber.org/pipermail/standards/2016-May/031126.html>`_.

* By contributing, you agree that your code is going to be licensed under the
  LGPLv3+ (see ``COPYING.LESSER``), like the rest of aioxmpp.
