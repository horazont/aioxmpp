.. _api-stability:

On API stability and versioning
###############################

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD",
"SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", and "OPTIONAL" in this
section are to be interpreted as described in :rfc:`2119`.

Requiring :pep:`492`
====================

Using a Python interpreter which implements :pep:`492` will not be required at
least until 0.7. Independent of that, version 1.0.0 *will* require :pep:`492`.
There may be features which are not or only inconveniently usable without
:pep:`492` before :pep:`492` support becomes mandatory for :mod:`aioxmpp` (one
example is :meth:`PresenceManagedClient.connected`).

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

Branching
---------

Two active development branches are used, one for the next minor and one for
the next major release. The branch for the next minor release is called
``devel-X.Y``, where ``X`` and ``Y`` are the major and minor version number of
the upcoming release, respectively. The branch for the next major release is
called ``devel``.

When a minor release is due, two new branches are created (``devel-X.Yn``,
where ``Yn = Y+1``) and ``release-X.Y.0``. In the ``devel-X.Yn`` branch, a new
commit is made to update the version number to ``(X, Yn, 0, 'a0')``. In the
``release-X.Y.0`` branch, the final preparations for the release (such as
updating the readme) are done. ``devel-X.Y`` is kept around to prepare patch
releases and it receives a commit which increments the patch version number by
one without removing the pre-release marker. When the release has been fully
prepared in ``release-X.Y.0``, the commit is tagged appropriately and packages
for all targets are prepared.

When a major release is due, a new branch is created (``devel-Xn.0``,
where ``Xn = X+1``). The remaining procedure is identical to preparing a minor
release for ``X.0``, including the creation of the two (additional) branches.

When a patch release is needed, the patch must be prepared in a feature branch,
branched off the *oldest* release to which the patch is supposed to be applied.
The feature branch can then be merged in all the ``devel-X.Y`` branches where
the patch is needed. Each of these branches is then merged in the corresponding
``release-X.Y`` branch with a non-fast-forward merge. The version number in the
release branches is bumped and the usual release procedure takes place.

In general, the tree of a commit in a devel branch MUST always have a
prerelease marker. The trees in the heads of the ``release-X.Y`` branches may
not have prerelease markers, if they are also tagged as releases.

An appealing property of this scheme is that merging from lower versions to
upper versions is possible (or the other way round, but not in both directions;
the other way round makes not as much sense though). At the first merge from a
lower to a higher version, a merge conflict with respect to the version number
will appear. Future merges will not have this conflict again, which is also why
merging downwards is not allowed (it would override the lower version number
with the higher version number).

The release with the highest version number is always merged into ``master``.
The version number in ``master`` MUST increase monotonically; patch releases are
thus not merged into ``master``, unless they are made against the most recent
release in ``master``.

Versioning and stability
------------------------

Still to be done.
