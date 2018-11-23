Frequently Asked Questions
##########################

Why yet another XMPP library for Python / asyncio?
==================================================

When we started the work on :mod:`aioxmpp`, there was no asyncio XMPP library
for Python. We considered porting `SleekXMPP <http://sleekxmpp.com/>`_, but
did not do so for two reasons:

* We didn’t think that a port to asyncio would be feasible without much of a
  re-write (we’ve been proven wrong, see below!).
* We think that the declarative and highly typed approach we’re following is
  more pythonic and leads to less code duplication.

We learnt a few years later that at approximately the same time we started with
aioxmpp (formerly called ``asyncio_xmpp``), the
`slixmpp <https://slixmpp.readthedocs.io/>`_ folks started to work on that fork
of SleekXMPP for asyncio.


Why does aioxmpp try to handle *everything*?
============================================

First of all, we don’t ;-). More to the point though, we feel that XMPP has a
lot of hard problems (some of which are inherent because IM is actually a
rather hard problem, some of which because of historical cruft), and those
problems deserve a proper solution.

We also think that the understanding of the difficulties of a problem decreases
the farther away from the problem you are. This means that client developers
using some client library would have less understanding about the difficulties
of IM than the developers of the client library.

This implies that the best place to solve XMPP and XMPP-IM specific issues is
close to the source, which is in the client library.

At the same time, we appreciate that there’s no one-size-fits-all. This is why
aioxmpp is extremely modular, and you often have the choice whether you use
a module from aioxmpp or whether you roll your own.

Prominent examples of things which look easy at first but are actually quite
tricky to get right:

* Stream Management (:xep:`198`). Really. In our opinion, Stream Management
  needs to be thought about at the very beginning (which is why it is highly
  integrated in aioxmpp) and downstream code sometimes needs to be aware of
  the difference between a suspended (disconnected) stream and a destroyed
  (disconnected and not resumable) stream.

* Private XML Storage (:xep:`49`) (and some of the :xep:`222`/:xep:`223` based
  protocols) needs a complex read-modify-write-test loop to cover the case when
  multiple clients modify the same storage at the same time. This is
  unfortunate and annoying, and hard to get right. Client developers shouldn’t
  have to care about this: the operations exposed should be things like
  ``update_bookmark`` or ``remove_bookmark`` and the library should take care
  that it either works verifiably or a proper error is raised.

* Multi-User Chats (:xep:`45`) are neat, but they have a lot of weird corner
  cases, some stemming from interference with modern protocols (such as
  :xep:`280` (Message Carbons)), some from oversights in the original design
  related to potential issues between servers. :mod:`aioxmpp.muc` tries to
  address those concerns without the application needing to care about it.


Shouldn’t X be up to the application?
=====================================

First, please read the previous point. If you still think that our way of
handling things in a particular case breaks your use-case, please
`drop us an issue on GitHub <https://github.com/horazont/aioxmpp/issues/new>`_
or the mailing list (see the README for ways to get in contact). We’ll be happy
to either work out a solution which works for you, or adapt the code so that
the use-case is covered.

(Examples of such things in the past:
`add method to disable XEP-0198 <https://github.com/horazont/aioxmpp/issues/114>`_,
`Using simple connector without SSL or TLS <https://github.com/horazont/aioxmpp/issues/153>`_)
