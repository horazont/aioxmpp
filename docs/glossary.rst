Glossary
########

This section defines terms used throughout the :mod:`aioxmpp` documentation.

.. glossary::

   Conversation
     A context for communication between two or more :term:`entities <Entity>`.
     It defines a transport medium (such as direct XMPP or a Multi-User-Chat), a
     set of members along with their addresses and possibly additional features
     such as archive access method.

   Conversation Member
     Representation of an entity which takes part in a :term:`Conversation`. The
     actual definition of "taking part in a conversation" depends on the
     specific medium used.

   Tracking Service
     A :term:`Service` which provides functionality for updating
     :class:`aioxmpp.tracking.MessageTracker` objects.

   Service
     A subclass of :class:`aioxmpp.service.Service` which supplements the base
     :class:`aioxmpp.Client` with additional functionality. Typically, a
     service implements a part of one or more :term:`XEPs <XEP>`.

   Service Member
     A :term:`Conversation Member` representing the service over which the
     conversation is run. For example, some :xep:`45` multi-user chat
     service implementations send messages to all occupants as a service user.
     Those messages appear in :mod:`aioxmpp.muc` as coming from the service
     member.

     Relevant entities:

     * :attr:`aioxmpp.im.conversation.AbstractConversation.service_member`

        * :attr:`aioxmpp.muc.Room.service_member`

     * :class:`aioxmpp.im.conversation.AbstractConversationMember`

        * :attr:`aioxmpp.muc.ServiceMember`

   XEP
   XMPP Extension Proposal
     An XMPP Extension Proposal (or XEP) is a document which extends the basic
     RFCs of the XMPP protocol with additional functionality. Many important
     instant messaging features are specified in XEPs. The index of XEPs is
     located on `xmpp.org <https://xmpp.org/extensions/>`_.
