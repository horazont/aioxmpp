Message Dispatching Rewrite
###########################

Issues with the current system:

* Precedence of wildcarding is not clear
* No distinction between "wildcard for a bare JID + all of its resources" and "only the bare JID" (it’s always the wildcard)
* Precedence is important as stanzas are delivered to only exactly one handler.


Proposed solution
=================

* Break the message dispatching out of the StanzaStream for easier re-writing.
* Handle it in a separate class.
* Allow applications to configure which message dispatcher is used.

This allows for:

* Creation of a mesasge dispatcher specialised for Instant Messaging. It could
  allow for out-of-band flags for messages, e.g. "Sent—Carbon",
  "Received-Carbon", …. The interface could be internal so that we can easily
  add features.

* Implement the previous behaviour in a separate class. It would provide a
  stable interface for applications not focused on the concept of a
  conversation.


Issues
======

* While this gives us nice features, we may want to be able to support both
  styles at the same time. This may lead to duplicate messages throughout
  different services, which is annoying and potentially bad.

  Workaround: Make these dispatchers work filter-style: if they have handled the
  message, the message is dropped from dispatching.

  -> needs priorities for dispatchers. User-controlled or dispatcher-controlled?


Interface for Message Dispatchers
=================================


.. class:: AbstractMessageDispatcher

   .. method:: handle_message(stanza)

      Called by the stanza stream when a message is received and has passed
      stream-level filters.





Transition path for existing StanzaStream methods
=================================================

1. Allow multiple Message Dispatchers, have a default one which provides that
   interface and make the methods simply redirect there.

2. Allow only a single Message Dispatcher and create a legacy one by default.
   Use the methods to redirect there. Fail loudly when the message dispatcher
   has been changed (or when it is being changed and there are still callbacks
   registered).

3. Delete them right away.
