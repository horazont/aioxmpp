Client design
#############

The client is designed to be resilent against connection failures. The key part
for this is to implement `XEP-198`_ (Stream Management), which supports resuming
a previous session without losing messages.

Queues
======

The client features multiple queues:

Active queue
------------

The active queue is the queue where stanzas are stored which are about to be
submitted to the XMPP server. This queue should be empty most of the time, but
messages may aggregate while connection issues are taking place. The active
queue cannot be introspected from outside the client.

Hold queue
----------

Stanzas cannot be placed into the hold queue directly; however, if resumption of
a stream fails (e.g. because the server doesn’t support stream management), the
stanzas from the active queue are moved into the hold queue, for manual review
by the user (it might make sense to not re-send some messages, e.g. if they’re
10 hours old).

Events
======

The client inherently has some events, directly related to the state of the
underlying stream:

.. function:: connecting(nattempt)

   A connection attempt is currently being made. It is not known yet whether it
   will succeed. It is the *nattempt*th attempt to establish the connection since
   the last successful connection.

.. function:: connection_failed()

   The connection failed during establishment of the connection.

.. function:: connection_made()

   The connection was successfully established.

.. function:: connection_lost()

   The connection has been lost. Automatic reconnect will take place (unless
   *max_reconnect_attempts* is 0; in that case, the ``closed`` event is fired
   next).

.. function:: closed()

   The maximum amount of reconnects has been surpassed, or the user has
   explicitly closed the client by calling :meth:`Client.close`.


.. _XEP-198: http://xmpp.org/extensions/xep-0198.html
