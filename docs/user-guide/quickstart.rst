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

  await stream.send(msg)

Relevant documentation:

* :class:`aioxmpp.Message`
* :meth:`aioxmpp.stream.StanzaStream.send`


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

Of course, you can react to messages. For this, you need to register with the
:class:`aioxmpp.stream.StanaStream` of the `client`. You better do this before
connecting, to avoid race conditions. So the following code should run
before the ``async with``. To get all chat messages, you could use::

  def message_received(msg):
      print(msg)

  client.stream.register_message_callback(
      aioxmpp.MessageType.CHAT,
      None,
      message_received,
  )

The `message_received` callback will be called for all ``"chat"`` messages from
any sender. By itself, it is not very useful, because the `msg` argument is the
:class:`aioxmpp.Message` object.

This example can be modified to be an echo bot by implementing the
``message_received`` callback differently::

  def message_received(msg):
      if not msg.body:
          # do not reflect anything without a body
          return

      reply = msg.make_reply()
      reply.body.update(msg.body)

      client.stream.enqueue(reply)

.. note::

   A slightly more verbose version can also be found in the examples directory,
   as ``quickstart_echo_bot.py``.

* :meth:`~aioxmpp.stream.StanzaStream.register_message_callback`. Definitely
  check this out for the semantics of the first two arguments!
* :class:`aioxmpp.Message`
* :meth:`~aioxmpp.stream.StanzaStream.enqueue`


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

  def available_presence_received(pres):
      print(pres)

  client.stream.register_presence_callback(
      aioxmpp.PresenceType.AVAILABLE,
      None,
      available_presence_received,
  )

Again, the whole :class:`aioxmpp.Presence` stanza is passed to the
callback.

Relevant documentation:

* :meth:`~aioxmpp.stream.StanzaStream.register_presence_callback`. Definitely
  check this out for the semantics of the first two arguments (they are slightly
  different from the semantics for the relevant message function).
* :class:`aioxmpp.Presence`


React to IQ requests
====================

Reacting to IQ requests is slightly more complex. The reason is that a client
must always reply to IQ requests. Thus, it is most natural to use coroutines as
IQ request handlers, instead of normal functions::

  async def request_handler(request):
      print(request)

  client.stream.register_iq_request_coro(
      aioxmpp.IQType.GET,
      aioxmpp.disco.xso.InfoQuery,
      request_handler,
  )

The coroutine is spawned for each request. The coroutine must return a valid
value for the :attr:`aioxmpp.IQ.payload` attribute, or raise an
exception, ideally one derived from :class:`aioxmpp.errors.XMPPError`. The
exception will be converted to a proper ``"error"`` IQ response.

Relevant documentation:

* :meth:`~aioxmpp.stream.StanzaStream.register_iq_request_coro`
* :class:`aioxmpp.IQ`
* :class:`aioxmpp.errors.XMPPError`


Use services
============

Services have now been mentioned several times. The idea of a
:class:`aioxmpp.service.Service` is to implement a specific XEP or an optional
part of the XMPP protocol. Services essentially do the same thing as discussed
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
are offered by :mod:`aioxmpp`, the easiest way to find those is to simply check
the :ref:`API Reference <api>`; most XEPs supported by :mod:`aioxmpp` are
implemented as services.

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

.. _ug-quickstart-send-iq:

Send a custom IQ payload
========================

As mentioned earlier, IQs are a bit more complex. IQ payloads are more or less
strictly defined, which gives :mod:`aioxmpp` the opportunity to take the load of
data validation off your back. This also means that you need to tell
:mod:`aioxmpp` what format you expect.

We will take :xep:`92` (Software Version) as an example. First we need to define
the IQ payload. You would generally do that in a module you import in your
application::

  import aioxmpp
  import aioxmpp.xso as xso

  namespace = "jabber:iq:version"

  @aioxmpp.IQ.as_payload_class
  class Query(xso.XSO):
      TAG = (namespace, "query")

      name = xso.ChildText(
          (namespace, "name"),
          default=None,
      )

      version = xso.ChildText(
          (namespace, "version"),
          default=None,
      )

      os = xso.ChildText(
          (namespace, "os"),
          default=None,
      )

:class:`~aioxmpp.xso.XSO` is a base class for any element occurring in an XMPP
XML stream. Using declarative-style descriptors, we describe the children we
expect on the :xep:`92` query. There are of course other descriptors, for
example for attributes, lists of children declared as classes, even
dictionaries. See the relevant documentation below for details.

With that declaration, we can construct and send a :xep:`92` IQ like this (we
are now back inside the ``async with`` block)::

  iq = aioxmpp.IQ(
      type_=aioxmpp.IQType.GET,
      payload=Query(),
      to=peer_jid,
  )

  print("sending query to {}".format(peer_jid))
  reply = await stream.send(iq)
  print("got response!")

If the peer complies with the protocol, `reply` is an instance of our freshly
baked :class:`Query`! The attributes will contain the response from the peer, we
could print them like this::

  print("name: {!r}".format(reply.name))
  print("version: {!r}".format(reply.version))
  print("os: {!r}".format(reply.os))

(Note that we passed ``default=None`` to the :class:`aioxmpp.xso.ChildText`
descriptor objects above; otherwise, accessing a descriptor representing
something which was not sent by the peer would result in a
:class:`AttributeError`, just like any other not-set attribute).

Relevant documentation:

* :mod:`aioxmpp.xso`, especially :class:`aioxmpp.xso.XSO` and
  :class:`aioxmpp.xso.ChildText`
* :meth:`aioxmpp.IQ.as_payload_class`
* :meth:`aioxmpp.stream.StanzaStream.send`
* also make sure to read the source of, for example, :mod:`aioxmpp.disco.xso`
  for more examples of :class:`~aioxmpp.XSO` subclasses.

.. note::

   In general, before considering sending an IQ manually, you should check out
   the :ref:`api-xep-modules` section of the API to see whether there is a
   module handling the XEP or RFC for you.

.. note::

   The example in this section can also be found in the `aioxmpp repository,
   at examples/quickstart_query_server_version.py
   <https://github.com/horazont/aioxmpp/blob/devel/examples/quickstart_query_server_version.py>`_.


React to an IQ request
======================

We build on the previous section. This time, we want to stay online for 30
seconds and serve software version requests.

To do this, we register a coroutine to handle IQ requests (before the ``async
with``)::

  async def handler(iq):
      print("software version request from {!r}".format(iq.from_))
      result = Query()
      result.name = "aioxmpp Quick Start Pro"
      result.version = "23.42"
      result.os = "MFHBμKOS (My Fancy HomeBrew Micro Kernel Operating System)"
      return result

  client.stream.register_iq_request_coro(
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

* :meth:`aioxmpp.stream.StanzaStream.register_iq_request_coro`
* :meth:`aioxmpp.IQ.as_payload_class`


Next steps
==========

This quickstart should have given you an impression on how to use
:mod:`aioxmpp` for rather simple tasks. If you develop a complex application,
you might want to look into the more advanced topics in the following chapters
of the user guide.
