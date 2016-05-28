.. _api-stability:

On API stability and versioning
###############################

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD",
"SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", and "OPTIONAL" in this
section are to be interpreted as described in `RFC 2119`__.

__ https://tools.ietf.org/html/rfc2119

Requiring :pep:`492`
====================

Using a Python interpreter which implements :pep:`492` will not be required at
least until 0.7. Independent of that, version 1.0.0 *will* require :pep:`492`.

Semantic versioning and version numbers
=======================================

:mod:`aioxmpp` complies with `Semantic Versioning 2.0.0`__. The key points
related to API stability are summarized below for your convenience.

The version of the :mod:`aioxmpp` package can be obtained by inspecting
:data:`aioxmpp.__version__`, which contains the version as a string. Unreleased
versions have the ``-devel`` (up to and including version 0.4) or ``-a0``
(since 0.5) suffix. An additional way to access the version number is
:data:`aioxmpp.version_info`, which provides a tuple which can be compared
against other version tuples to check for a specific range of :mod:`aioxmpp`
versions.

Versions with ``-a0`` suffix are never released; if there will ever be
pre-releases, they start at ``-a1``.

__ http://semver.org/spec/v2.0.0.html

Up to version 1.0.0
===================

Up to version 1.0.0, the API inside the :mod:`aioxmpp` package MAY change
without notice in advance. These changes MAY break code in ways which makes it
impossible to have code which works with both the old and the new version.

Changes to the public, non-plugin API SHOULD NOT break code in a way which
makes it impossible to use with old and new versions.

The :ref:`changelog` may not be complete, but SHOULD contain all changes which
break existing code.

The below text, which describes the behaviour for versions from 1.0 onwards,
MAY change without notice in advance.

From version 1.0.0 onwards
==========================

Still to be done.
