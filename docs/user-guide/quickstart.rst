.. _ug-quick-start:

Quick start
###########

This chapter wants to get you started quickly with :mod:`aioxmpp`. It will spare
you with most architectural and design details and simply throw some code
snippets at you which do some work.

.. note::

   Even though :mod:`aioxmpp` does technically not require it, we will use
   :pep:`492` features throughout this chapter.

   It makes the code much more concise at some points; there are (currently)
   always ways around having to use :pep:`492` features—please refer to the
   examples along with the source code to see alternatives e.g. for connecting.


In this section, we will assume that you are familiar with the basic concepts of
XMPP. If you are not, you may still try to walk through this, but a lot of
things which are obvious when you are used to work with XMPP will not be
explained.


Preparations
============

We assume that you have both a :class:`aioxmpp.JID` and a password as
:class:`str` at hand. One way to obtain would be to ask the user::

   jid = aioxmpp.JID.fromstr(input("JID: "))
   password = getpass.getpass()


.. note::

   :mod:`getpass` is a standard Python module for blockingly asking the user for
   a password in a terminal. You can use different means of obtaining a
   password. Most importantly, in this tutorial, you could replace `password`
   with a coroutine taking two arguments, a :class:`aioxmpp.JID` and an integer;
   the integer would increase with every authentication attempt during a
   connection attempt (starting at 0). The caller expects that the coroutine
   returns a password to try, or :data:`None` to abort the authentication.

   In fact, passing a :class:`str` as password below simply makes the code wrap
   that :class:`str` in a coroutine which returns the :class:`str` when the
   second argument is zero and :data:`None` otherwise.


Connect to an XMPP server, with JID and Password
================================================

To connect to an XMPP server, we use a :class:`aioxmpp.PresenceManagedClient`::

  client = aioxmpp.PresenceManagedClient(
      jid,
      aioxmpp.make_security_layer(password)
  )

  async with client.connected() as stream:
      ...

At ``...``, the client is connected and has sent initial presence with an
available state. We will get back to the `stream` object returned by the context
manager later on.

Relevant documentation:

* :func:`aioxmpp.security_layer.make`, :mod:`aioxmpp.security_layer`
* :meth:`aioxmpp.PresenceManagedClient.connected`


Send a message
==============

We assume that you did the part from the previous section, and we’ll now work
inside the ``async with`` block::

  msg = aioxmpp.Message(
      to=recipient_jid,  # recipient_jid must be an aioxmpp.JID
      type_=aioxmpp.MessageType.CHAT,
  )
  # None is for "default language"
  msg.body[None] = "Hello World!"

  await client.send(msg)

Relevant documentation:

* :class:`aioxmpp.Message`
* :meth:`aioxmpp.Client.send`


.. note::

   Want to send an IQ instead? IQs are a bit more complex, due to their rather
   formal nature. We suggest that you read through this quickstart step-by-step,
   but you may as well jump ahead to :ref:`ug-quickstart-send-iq`.


Change presence
===============

:meth:`aioxmpp.PresenceManagedClient.connected` automatically sets an
available presence. To change presence during runtime, there are two ways::

  # the simple way: simply set to Do-Not-Disturb
  client.presence = aioxmpp.PresenceState(available=True, show="dnd")

  # the advanced way: change presence and set the textual status
  client.set_presence(
      aioxmpp.PresenceState(available=True, show="dnd"),
      "Busy with stuff",
  )

Relevant documentation:

* :class:`aioxmpp.PresenceState`
* :meth:`aioxmpp.PresenceManagedClient.set_presence` (It also accepts
  dictionaries instead of strings. Want to know why? Read the documentation! ☺), :attr:`aioxmpp.PresenceManagedClient.presence`


React to messages (Echo Bot)
============================

Of course, you can react to messages. For simple use-cases, you can use the
:class:`aioxmpp.dispatcher.SimpleMessageDispatcher` service. You better do this
before connecting, to avoid race conditions. So the following code should run
before the ``async with``. To get all chat messages, you could use::

  import aioxmpp.dispatcher

  def message_received(msg):
      print(msg)

  # obtain an instance of the service (we’ll discuss services later)
  message_dispatcher = client.summon(
     aioxmpp.dispatcher.SimpleMessageDispatcher
  )

  # register a message callback here
  message_dispatcher.register_callback(
      aioxmpp.MessageType.CHAT,
      None,
      message_received,
  )

The `message_received` callback will be called for all ``"chat"`` messages from
any sender. As it stands, the callback is not very useful, because the `msg`
argument is the :class:`aioxmpp.Message` object and printing it won’t show the
message contents.

This example can be modified to be an echo bot by implementing the
``message_received`` callback differently::

  def message_received(msg):
      if not msg.body:
          # do not reflect anything without a body
          return

      reply = msg.make_reply()
      reply.body.update(msg.body)

      client.enqueue(reply)

.. note::

   A slightly more verbose version can also be found in the examples directory,
   as ``quickstart_echo_bot.py``.

* :class:`aioxmpp.dispatcher.SimpleMessageDispatcher`,
  :meth:`~aioxmpp.dispatcher.SimpleStanzaDispatcher.register_callback`.
  Definitely check this out for the semantics of the first two arguments!
* :class:`aioxmpp.Message`
* :meth:`~aioxmpp.Client.enqueue`
* :meth:`aioxmpp.Client.summon`


React to presences
==================

Similar to handling messages, presences can also be handled.

.. note::

   There exists a service which handles and manages peer presence
   (:class:`aioxmpp.PresenceClient`) and one which manages roster
   subscriptions (:class:`aioxmpp.RosterClient`), which make most manual
   handling of presence obsolete. Read on on how to use services.

Again, the code should be run before
:meth:`~aioxmpp.PresenceManagedClient.connected`::

  import aioxmpp.dispatcher

  def available_presence_received(pres):
      print(pres)

  presence_dispatcher = client.summon(
      aioxmpp.dispatcher.SimplePresenceDispatcher,
  )

  presence_dispatcher.register_callback(
      aioxmpp.PresenceType.AVAILABLE,
      None,
      available_presence_received,
  )

Again, the whole :class:`aioxmpp.Presence` stanza is passed to the
callback.

Relevant documentation:

* :class:`aioxmpp.dispatcher.SimplePresenceDispatcher`,
  :meth:`~aioxmpp.dispatcher.SimpleStanzaDispatcher.register_callback`.
  Definitely check this out for the semantics of the first two arguments.
* :class:`aioxmpp.Presence`


React to IQ requests
====================

Reacting to IQ requests is slightly more complex. The reason is that a client
must always reply to IQ requests. Thus, it is most natural to use coroutines as
IQ request handlers, instead of normal functions::

  async def request_handler(request):
      print(request)

  client.stream.register_iq_request_handler(
      aioxmpp.IQType.GET,
      aioxmpp.disco.xso.InfoQuery,
      request_handler,
  )

The coroutine is spawned for each request. The coroutine must return a valid
value for the :attr:`aioxmpp.IQ.payload` attribute, or raise an
exception, ideally one derived from :class:`aioxmpp.errors.XMPPError`. The
exception will be converted to a proper ``"error"`` IQ response.

Relevant documentation:

* :meth:`~aioxmpp.stream.StanzaStream.register_iq_request_handler`
* :class:`aioxmpp.IQ`
* :class:`aioxmpp.errors.XMPPError`


Use services
============

Services have now been mentioned several times. The idea of a
:class:`aioxmpp.service.Service` is to implement a specific XEP or a part of
the XMPP protocol. Services essentially do the same thing as discussed
in the previous sections (sending and receiving messages, IQs and/or presences),
but encapsulated away in a class. For details on that, see
:mod:`aioxmpp.service` and an implementation, such as
:class:`aioxmpp.DiscoClient`.

Here we’ll show how to use services::

  client = aioxmpp.PresenceManagedClient(
      jid,
      aioxmpp.make_security_layer(password)
  )

  disco = client.summon(aioxmpp.DiscoClient)

  async with client.connected() as stream:
      info = await disco.query_info(
          target_jid,
      )

In this case, `info` is a :class:`aioxmpp.disco.xso.InfoQuery` object returned
by the entity identified by `target_jid`.

The idea of services is to abstract away the details of the protocol
implemented, and offer additional features (such as caching). Several services
are offered by :mod:`aioxmpp`; most XEPs supported by :mod:`aioxmpp` are
implemented as services. An overview of the existing services can be found in
the API reference at :ref:`api-aioxmpp-services`.

Relevant docmuentation:

* :meth:`aioxmpp.Client.summon`
* :mod:`aioxmpp.disco`, :class:`aioxmpp.DiscoClient`,
  :meth:`~aioxmpp.DiscoClient.query_info`


Use :class:`aioxmpp.PresenceClient` presence implementation
===========================================================

This section is mainly there to show you a service which is mostly used with
callbacks::

  client = aioxmpp.PresenceManagedClient(
      jid,
      aioxmpp.make_security_layer(password)
  )

  def peer_available(jid):
      print("{} came online".format(jid))

  def peer_unavailable(jid):
      print("{} went offline".format(jid))

  presence = client.summon(aioxmpp.PresenceClient)
  presence.on_bare_available.connect(peer_available)
  presence.on_bare_unavailable.connect(peer_unavailable)

  async with client.connected() as stream:
      await asyncio.sleep(10)

This simply stays online for ten seconds and prints the bare JIDs from which
available and unavailable presence is received.

Relevant documentation:

* :class:`aioxmpp.PresenceClient`
* :class:`aioxmpp.callbacks.AdHocSignal`

React to a XEP-0092 Software Version IQ request
===============================================

This time, we want to stay online for 30 seconds and serve :xep:`92` software
version requests. The format for those is already defined in
:mod:`aioxmpp.version`, so we can re-use that. Before we go into how to use
that, we will briefly show what such a format definition looks like:

.. code:: python

    namespaces.xep0092_version = "jabber:iq:version"


    @aioxmpp.IQ.as_payload_class
    class Query(xso.XSO):
        TAG = namespaces.xep0092_version, "query"

        version = xso.ChildText(
            (namespaces.xep0092_version, "version"),
            default=None,
        )

        name = xso.ChildText(
            (namespaces.xep0092_version, "name"),
            default=None,
        )

        os = xso.ChildText(
            (namespaces.xep0092_version, "os"),
            default=None,
        )


The XML element is defined declarative-style as class. The ``TAG`` attribute
defines the fully qualified name of the XML element to match, in this case,
it is the ``query`` element in the ``jabber:iq:version`` namespace.

The other attributes are XSO properties (see :mod:`aioxmpp.xso`). In this case,
all properties are :class:`aioxmpp.xso.ChildText` properties. Each of those
maps to the text content of a child element, again identified by their
respective fully qualified names. The ``name`` attribute for example maps to the
text of the ``name`` child in the ``jabber:iq:version`` namespace.

You do not need to include this code in your application, because it’s already
there in aioxmpp. You can import it using
``from aioxmpp.version.xso import Query``.

Now to reply to version requests, we register a coroutine to handle IQ requests
(before the ``async with``)::

  from aioxmpp.version.xso import Query

  async def handler(iq):
      print("software version request from {!r}".format(iq.from_))
      result = Query()
      result.name = "aioxmpp Quick Start Pro"
      result.version = "23.42"
      result.os = "MFHBμKOS (My Fancy HomeBrew Micro Kernel Operating System)"
      return result

  client.stream.register_iq_request_handler(
      aioxmpp.IQType.GET,
      Query,
      handler,
  )

  async with client.connected():
      await asyncio.sleep(30)

While the client is online, it will respond to IQ requests of type ``"get"``
which carry a :class:`Query` payload; the payload is identified by its qualified
XML name (that is, the namespace and element name tuple). :mod:`aioxmpp` was
made aware of the :class:`Query` using the
:meth:`aioxmpp.IQ.as_payload_class` descriptor.

It then calls the `handler` coroutine we declared with the
:class:`aioxmpp.IQ` object as its only argument. The coroutine is
expected to return a valid payload (hint: :data:`None` is also a valid payload)
for the ``"result"`` IQ or raise an exception (which would be converted to an
``"error"`` IQ).

Relevant documentation:

* :meth:`aioxmpp.stream.StanzaStream.register_iq_request_handler`
* :meth:`aioxmpp.IQ.as_payload_class`
* :class:`aioxmpp.version.xso.Query`

.. note::

    In general, you should check whether aioxmpp implements a feature already.
    In this case, :xep:`92` is implemented by :mod:`aioxmpp.version`. Check
    that module out for a more user-friendly way to handle things.


Next steps
==========

This quickstart should have given you an impression on how to use
:mod:`aioxmpp` for rather simple tasks. If you develop a complex application,
you might want to look into the more advanced topics in the following chapters
of the user guide.
