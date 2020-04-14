.. _changelog:

Changelog
#########

.. _api-cahngelog-0.11:

Version 0.12
============

* Drop support for Python 3.4. This includes migrating to using ``async def``
  instead of ``@asyncio.coroutine`` consistently. Future changes will include
  using type annotations.

* Add ``--e2etest-only`` flag to the e2etest nose plugin. This flag will skip
  any test case not derived from :class:`aioxmpp.e2etest.TestCase`. The use
  case for this is to use the aioxmpp test suite to test other servers in their
  CI.

* :class:`aioxmpp.e2etest.provision.StaticPasswordProvisioner`

Version 0.11
============

New XEP implementations
-----------------------

* Support for the :xep:`27` (Current Jabber OpenPGP Usage) schema in
  :mod:`aioxmpp.misc`.

* :xep:`47` (In-Band Bytestreams), see :mod:`aioxmpp.ibb`.

* The :xep:`106` (JID Escaping) encoding can now be used via
  :func:`aioxmpp.jid_escape`, :func:`aioxmpp.jid_unescape`.

* `@LukeMarlin <https://github.com/LukeMarlin>`_ contributed support for the
  :xep:`308` schema in :mod:`aioxmpp.misc`.

* The :xep:`335` (JSON Containers) schema is available for use via
  :class:`aioxmpp.misc.JSONContainer`.

* Implement support for :xep:`410` (MUC Self-Ping (Schrödinger’s Chat)).

  This introduces two new signals to :class:`aioxmpp.muc.Room` objects:

  - :meth:`~aioxmpp.muc.Room.on_muc_stale`: Emits when a possible connectivity
    issue with the MUC is detected, but it is unclear whether the user is still
    joined or not and/or whether messages are being lost.

  - :meth:`~aioxmpp.muc.Room.on_muc_fresh`: Emits when a possible connectivity
    issue with the MUC is detected as resolved and the user is still joined.
    Presence may be out-of-sync and messages may have been lost, however.

  If a connectivity issue which has caused the user to be removed from the MUC
  is detected, the appropriate signals (with
  :attr:`aioxmpp.muc.LeaveMode.DISCONNECTED`) are emitted, *or* the room is
  automatically re-joined if it is set to
  :attr:`~aioxmpp.muc.Room.muc_autorejoin` (no history is requested on this
  rejoin).

  In addition to that, the :meth:`aioxmpp.MUCClient.cycle` method has been
  introduced. It allows an application to leave and join a MUC in quick
  succession using without discarding the :class:`aioxmpp.muc.Room` object
  (just like a stream disconnect would). This is useful to deal with stale
  situations by forcing a resync.

Security Fixes
--------------

* CVE-2019-1000007: Fix incorrect error handling in :mod:`aioxmpp.xso` when a
  supressing :meth:`aioxmpp.xso.XSO.xso_error_handler` is in use.

  Under certain circumstances, it is possible that the handling of supressed
  error causes another error later on because the parsing stack mis-counts the
  depth in which it is inside the XML tree. This makes elements appear in the
  wrong place, typically leading to further errors.

  In the worst case, using a supressing
  :meth:`~aioxmpp.xso.XSO.xso_error_handler` in specific circumstances can be
  vulnerable to denial of service and data injection into the XML stream.

  (The fix was also backported to 0.10.3.)

New major features
------------------

* The :mod:`aioxmpp.pubsub` implementation gained support for node
  configuration and the related publish-options. This is vital for proper
  operation of private storage in PEP.

  Relevant additions are:

  * :meth:`aioxmpp.PubSubClient.get_node_config`
  * :meth:`aioxmpp.PubSubClient.set_node_config`
  * :class:`aioxmpp.pubsub.NodeConfigForm`
  * The new ``publish_options`` argument to
    :meth:`aioxmpp.PubSubClient.publish`
  * The new ``access_model`` argument to :meth:`aioxmpp.PEPClient.publish`

* The new :meth:`aioxmpp.Client.on_stream_resumed` event allows services and
  application code to learn when the stream was resumed after it suspended due
  to loss of connectivity. This is the counterpart to
  :meth:`aioxmpp.Client.on_stream_suspended`.

  This allows services and application code to defer actions until the stream
  is alive again. While this is generally not necessary, it can be good to
  delay periodic tasks or bulk operations in order to not overload the newly
  established stream with queued messages.

New examples
------------

Breaking changes
----------------

* The undocumented and unused descriptors :attr:`aioxmpp.Message.ext`
  and :attr:`aioxmpp.Presence.ext` were removed. If your code relies on them
  you can instead patch a descriptor to the class (with a prefix that uniquely
  identifies your extension).

  A good example is how aioxmpp itself makes use of that feature in
  :mod:`aioxmpp.misc`.

* :mod:`aioxmpp.stringprep` now uses the Unicode database in version 3.2.0 as
  specified in :rfc:`3454`.

* The way the topological sort of service dependencies is handled was
  simplified: We no longer keep a toposort of all service classes.
  *This implies that :class:`Service` subclasses are no longer ordered objects.*
  However, we still guarantee a runtime error when a dependency loop is
  declared—if a class uses only one of `ORDER_BEFORE` respective `ORDER_AFTER`
  it cannot introduce a dependency loop; only when a class uses both we have
  to do an exhaustive search of the dependent nodes. This search touches only
  a few nodes instead of the whole graph and is only triggered for very few
  service classes.

  Summon has been creating an independent toposort of only the required
  classes anyway, so we use this for deriving ordering indices for filter
  chains from now on—this also allows simpler extension, modification of the
  filter order (e.g. ``-index`` orders in reverse).

  Methods for determining transitive dependency (and independency) have been
  added to the service classes:

  * :meth:`aioxmpp.Service.orders_after`,
  * :meth:`aioxmpp.Service.orders_after_any`,
  * :meth:`aioxmpp.Service.independent_from`.

  These search the class graph and are therefore not efficient (and the
  results may change when new classes are defined).

  Tests should always prefer to test the declared attributes when checking for
  correct dependencies.

* :func:`aioxmpp.make_security_layer` now binds the default for the ssl context
  factory early to :func:`aioxmpp.security_layer.default_ssl_context`. This
  means that you can not monkey-patch
  :func:`aioxmpp.security_layer.default_ssl_context` and have your changes
  apply to all security layers anymore. Since this behaviour was never
  documented or intended, there is no transition period for this.

* :meth:`aioxmpp.xso.XSO.unparse_to_sax` was renamed to
  :meth:`~aioxmpp.xso.XSO.xso_serialise_to_sax`.

Minor features and bug fixes
----------------------------

* Support for servers which send a :xep:`198` Stream Management counter in
  resumption errors. This allows us to know precisely which stanzas were (not)
  received by the server and thus improves accuracy of the stanza token state.

  Stanzas which are acknowledged in this way by a server enter the
  :attr:`~aioxmpp.stream.StanzaState.ACKED` state as normal. Stanzas which are
  not covered by the counter enter
  :attr:`~aioxmpp.stream.StanzaState.DISCONNECTED` state instead of
  :attr:`~aioxmpp.stream.StanzaState.SENT_WITHOUT_SM`, since the stream knows
  for sure that the stanza has not been received by the server.

  This only works if the server provides a counter value on failure; if the
  counter value is not provided, sent stanzas which were not acked during the
  previous connection will enter
  :attr:`~aioxmpp.stream.StanzaState.SENT_WITHOUT_SM` state as previously.

* :mod:`aioxmpp.forms` will not complain anymore if multiple ``<option/>``
  elements in a list-single/list-multi are lacking a label. It is recommended
  that you default the label to the option value in such a case.

  (Note that it already has been possible that *one* label was absent (i.e.
  :data:`None`). This just allows more than one label to be absent.)

* :class:`aioxmpp.xso.ChildTextMap` can now also be constructed from a
  tag, an appropriate XSO is then constructed on the fly.

* :meth:`aioxmpp.stream.StanzaStream.register_iq_request_handler`
  and :func:`aioxmpp.service.iq_handler` now
  support a keyword argument `with_send_reply` which makes them pass
  an additional argument to the handler, which is a function that can be
  used to enqueue the reply to the IQ before the handler has returned.
  This allows sequencing other actions after the reply has been sent.

* :mod:`aioxmpp.hashes` now supports the `hashes-used` element and has a
  service that handles registering the disco features and can determine
  which hash functions are supported by us and another entity.

* Moved :class:`aioxmpp.protocol.AlivenessMonitor` to
  :class:`aioxmpp.utils.AlivenessMonitor` for easier reuse.

* Extract :func:`aioxmpp.ping.ping` from :meth:`aioxmpp.PingService.ping`.

* :class:`aioxmpp.utils.proxy_property` for easier use of composed classes over
  inherited classes.

* :class:`aioxmpp.xso.ChildValue` as a natural extension of
  :class:`aioxmpp.xso.ChildValueList` and others.

* :func:`aioxmpp.make_security_layer` now supports the `ssl_context_factory`
  argument which is already known from the (deprecated)
  :func:`aioxmpp.security_layer.tls_with_password_based_authentication`.

  It allows application code to pass a factory to create the SSL context
  instead of defaulting to the SSL context provided by aioxmpp.

* Fix incorrect parsing of :xep:`198` location specifier. We always required a
  port number, while the standards allows omit the port number.

* Fix incorrect serialisation of nested namespace declarations for the same URI.
  One such occurence is often encountered when using the
  ``<{urn:xmpp:forward:0}forwarded/>`` element (see
  :class:`aioxmpp.misc.Forwarded`). It can host a ``<{jabber:client}message/>``.
  Since we declare all namespaces of XSOs as prefixless, the nested message needs
  to re-declare its prefix. Due to incorrect handling of namespace prefix
  rebinding in :class:`aioxmpp.xml.XMPPXMLGenerator`, that re-declaration is not
  emitted, leading to incorrect output.

  This was reported in
  `GitHub Issue #295 <https://github.com/horazont/aioxmpp/issues/295>`_ by
  `@oxoWrk <https://github.com/oxoWrk>`_.

* Fix assignment of enumeration members to descriptors using
  :class:`aioxmpp.xso.EnumCDataType` with `allow_coerce` set to true but
  `deprecate_coerce` set to false.

.. _api-changelog-0.10:

Version 0.10
============

New XEP implementations
-----------------------

* :mod:`aioxmpp.version` (:xep:`92`): Support for publishing the software
  version of the client and accessing version information of other entities.

* :mod:`aioxmpp.mdr` (:xep:`184`): A tracking implementation (see
  :mod:`aioxmpp.tracking`) which uses :xep:`184` Message Delivery Receipts.

* :mod:`aioxmpp.ibr` (:xep:`77`): Support for registering new accounts,
  changing the password and deleting an account (via the non-data-form flow).
  Contributed by `Sergio Alemany <https://github.com/Gersiete>`_.

* :mod:`aioxmpp.httpupload` (:xep:`363`): Support for requesting an upload slot
  (the actual uploading via HTTP is out of scope for this project, but look at
  the ``upload.py`` example which uses :mod:`aiohttp`).

* :mod:`aioxmpp.misc` gained support for:

  * parts of the :xep:`66` schema
  * the :xep:`333` schema
  * the ``<preauth/>`` element of :xep:`379`

* Be robust against invalid IQ stanzas.

New major features
------------------

* *Improved timeout handling*: Before 0.10, there was an extremely simple
  timeout logic: the :class:`aioxmpp.stream.StanzaStream` would send a ping of
  some kind and expect a reply to that ping back within a certain timeframe. If
  no reply *to that ping* was received within that timeframe, the stream would
  be considered dead and it would be aborted.

  The new timeout handling does not require that *a reply* is received; instead,
  the stream is considered live as long as data is coming in, irrespective of
  the latency. Only if no data has been received for a configurable time (
  :attr:`aioxmpp.streams.StanzaStream.soft_timeout`), a ping is sent. New data
  has to be received within :attr:`aioxmpp.streams.StanzaStream.round_trip_time`
  after the ping has been sent (but it does not need to necessarily be a reply
  to that ping).

* *Strict Ordering of Stanzas*: It is now possible to make use of the ordering
  guarantee on XMPP XML streams for IQ handling. For this to work, normal
  functions returning an awaitable are used instead of coroutines. This is
  needed to prevent any possible ambiguity as to when coroutines handling IQ
  requests are scheduled with respect to other IQ handler coroutines and other
  stanza processing.

  The following changes make this possible:

  * Support for passing a function returning an awaitable as callback to
    :meth:`aioxmpp.stream.StanzaStream.register_iq_request_coro`. In contrast
    to coroutines, a callback function can exploit the strong ordering guarantee
    of the XMPP XML Stream.

  * Support for passing a callback function to
    :meth:`aioxmpp.stream.StanzaStream.send` which is invoked on responses to an
    IQ request sent through :meth:`~aioxmpp.stream.StanzaStream.send`. In
    contrast to awaiting the result of
    :meth:`~aioxmpp.stream.StanzaStream.send`, the callback can exploit the
    strong ordering guarantee of the XMPP XML Stream.

  * The :func:`aioxmpp.service.iq_handler` decorator function now allows normal
    functions to be decorated (in addition to coroutine functions).

  * Add `cb` argument to :func:`aioxmpp.protocol.send_and_wait_for` to allow to
    act synchronously on the response. This is needed for transactional things
    like stream management.

* *Consistent Member Argument for*
  :meth:`~aioxmpp.im.conversation.AbstractConversation.on_message`:
  The :meth:`aioxmpp.muc.Room.on_message` now always have a non-:data:`None`
  `member` argument.

  Please see the documentation of the event for some caveats of this `member`
  argument as well as the rationale.

  .. note::

      Prosody ≤ 0.9.12 (for the 0.9 branch) and ≤ 0.10.0 (for the 0.10
      branch) are affected by `Prosody issue #1053
      <https://prosody.im/issues/1053>`_.

      This means that by itself, :class:`aioxmpp.muc.Room` cannot detect that
      history replay is over and will stay in the history replay state forever.
      However, two workarounds help with that: once the first live message is
      or the first presence update is received, the :class:`~aioxmpp.muc.Room`
      will assume a buggy server and transition to
      :attr:`~aioxmpp.muc.RoomState.ACTIVE` state.

      These workarounds are not perfect; in particular it is possible that the
      first message workaround is defeated if a client includes a ``<delay/>``
      into that message.

      Until either a fixed version of Prosody is used or the workarounds take
      effect, the following issues will be observed:

      * :attr:`aioxmpp.muc.Occupant.uid` will not be useful in any way (but also
        not harmful, security-wise).
      * :meth:`aioxmpp.muc.Room.on_message` may receive `member` arguments which
        are not part of the :attr:`aioxmpp.muc.Room.members` and which may also
        lack other information (such as bare JIDs).
      * :attr:`aioxmpp.muc.Room.muc_state` will not reach the
        :attr:`aioxmpp.muc.RoomState.ACTIVE` state.

      Applications which support e.g. :xep:`85` (Chat State Notifications) may
      use a chat state notification (for example, active or inactive) to cause
      a message to be received from the MUC, forcing the transition to
      :attr:`~aioxmpp.muc.RoomState.ACTIVE` state.

  This comes together with the new :attr:`aioxmpp.muc.Room.muc_state` attribute
  which indicates the current local state of the room. See
  :class:`aioxmpp.muc.RoomState`.

* *Recognizability of Occupants across Rejoins/Reboots*: The
  :attr:`aioxmpp.im.conversation.AbstractConversationMember.uid`
  attribute holds a (reasonably) unique string indentifying the occupant. If
  the :attr:`~aioxmpp.im.conversation.AbstractConversationMember.uid` of two
  member objects compares equal, an application can be reasonably sure that
  the two members refer to the same identity. If the UIDs of two members are
  *not* equal, the application can be *sure* that the two members do not have
  the same identity. This can be used for permission checks e.g. in the context
  of Last Message Correction or similar applications.

* *Improved handling of pre-connection stanzas*:
  The API for sending stanzas now lives at the :class:`aioxmpp.Client` as
  :meth:`aioxmpp.Client.send` and :meth:`aioxmpp.Client.enqueue`. In addition,
  :meth:`~aioxmpp.Client.send`\ -ing a stanza will block until the client has
  a valid stream. Attempting to :meth:`~aioxmpp.Client.enqueue` a stanza while
  the client does not have a valid stream raises a :class:`ConnectionError`.

  A valid stream is either an actually connected stream or a suspended stream
  with support for :xep:`198` resumption.

  This prevents attempting to send stanzas over a stream which is not ready
  yet. In the worst case, this can cause various errors if the stanza is then
  effectively sent before resource binding has taken place.

* *Invitations*: :mod:`aioxmpp.muc` now supports sending invitations (via
  :meth:`aioxmpp.muc.Room.invite`) and receiving invitations (via
  :meth:`aioxmpp.MUCClient.on_muc_invitation`). The interface for
  :meth:`aioxmpp.im.conversation.AbstractConversation.invite` has been reworked.

* *Service Members*:
  :class:`aioxmpp.im.conversation.AbstractConversation`\ s can now have a
  :class:`aioxmpp.im.conversation.AbstractConversationMember` representing the
  conversation service itself inside that conversation (see
  :term:`Service Member`).

  The primary use is to represent messages originating from a :xep:`45` room
  itself (on the protocol level, those messages have the bare JID of the room
  as :attr:`~aioxmpp.Message.from`).

  The service member of each conversation (if it is defined), is never contained
  in the :attr:`aioxmpp.im.conversation.AbstractConversation.members` and
  available at
  :attr:`~aioxmpp.im.conversation.AbstractConversation.service_member`.

* *Better Child Element Enumerations*:
  The :class:`aioxmpp.xso.XSOEnumMixin` is a mixin which can be used with
  :class:`enum.Enum` to create an enumeration where each enumeration member has
  its own XSO *class*.

  This is useful for e.g. error conditions where a defined set of children
  exists, but :class:`aioxmpp.xso.ChildTag` with an enumeration isn’t
  appropriate because the child XSOs may have additional data. Refer to the
  docs for more details.

* *Error Condition Data*:
  The representation of XMPP error conditions on the XSO level has been
  reworked. This is to support error conditions which have a data payload
  (most importantly :attr:`aioxmpp.ErrorCondition.GONE`).

  The entire error condition XSO is now available on both
  :class:`aioxmpp.errors.XMPPError` (as
  :attr:`~aioxmpp.errors.XMPPError.condition_obj`) exceptions and
  :class:`aioxmpp.stanza.Error` payloads (as
  :attr:`~aioxmpp.stanza.Error.condition_obj`).

  For this change, the following subchanges are relevant:

  * The constructors of :class:`aioxmpp.stanza.Error` and
    :class:`aioxmpp.errors.XMPPError` (and subclasses) now accept either a
    member of the :class:`aioxmpp.ErrorCondition` enumeration or an instance of
    the respective XSO. This allows to attach additional data to error
    conditions which support this, such as the
    :attr:`aioxmpp.ErrorCondition.GONE` error.

  * :attr:`aioxmpp.errors.XMPPError.application_defined_condition` is now
    attached to :attr:`aioxmpp.stanza.Error.application_condition` when
    :meth:`aioxmpp.stanza.Error.from_exception` is used.

  Please see the breaking changes below for how to handle the transition from
  namespace-name tuples to enumeration members.

New examples
------------

* ``upload.py``: uses :class:`aioxmpp.httpupload` and :class:`aiohttp` to upload
  any file to an HTTP service offered by the XMPP server, if the server
  supports the feature.

* ``register.py``: Register an account at an XMPP server which offers classic
  :xep:`77` In-Band Registration.

Breaking changes
----------------

* Converted stanza and stream error conditions
  to enumerations based on :class:`aioxmpp.xso.XSOEnumMixin`.

  This is similar to the transition in the 0.7 release. The following
  attributes, methods and constructors now expect enumeration members instead
  of tuples:

  * :class:`aioxmpp.stanza.Error`, the `condition` argument
  * :attr:`aioxmpp.stanza.Error.condition`
  * :attr:`aioxmpp.nonza.StreamError.condition`
  * :class:`aioxmpp.errors.XMPPError` (and its subclasses), the `condition`
    argument
  * :attr:`aioxmpp.errors.XMPPError.condition`

  To simplify the transition, the enumerations will compare equal to the
  equivalent tuples until the release of 1.0.

  The affected code locations can be found with the
  ``utils/find-v0.10-type-transition.sh`` script. It finds all tuples which
  form error conditions. In addition, :class:`DeprecationWarning` type warnings
  are emitted in the following cases:

  * Enumeration member compared to tuple
  * Tuple assigned to attribute or passed to method where an enumeration member
    is expected

  To make those warnings fatal, use the following code at the start of your
  application::

        import warnings
        warnings.filterwarnings(
            # make the warnings fatal
            "error",
            # match only deprecation warnings
            category=DeprecationWarning,
            # match only warnings concerning the ErrorCondition and
            # StreamErrorCondition enumerations
            message=".+(Stream)?ErrorCondition",
        )

* Split :class:`aioxmpp.xso.AbstractType` into
  :class:`aioxmpp.xso.AbstractCDataType` (for which the
  :class:`aioxmpp.xso.AbstractType` was originally intended) and
  :class:`aioxmpp.xso.AbstractElementType` (which it has become through organic
  growth). This split serves the maintainability of the code and offers
  opportunities for better error detection.

* :meth:`aioxmpp.BookmarkService.get_bookmarks`
  now returns a list instead of a :class:`aioxmpp.bookmarks.Storage`
  and :meth:`aioxmpp.BookmarkService.set_bookmarks` now accepts a
  list. The list returned by the get method and its elements *must
  not* be modified.

* Make :meth:`aioxmpp.muc.Room.send_message_tracked` a normal method instead
  of a coroutine (it was never intended to be a coroutine).

* Specify :meth:`aioxmpp.im.conversation.AbstractConversation.on_enter` and
  :meth:`~aioxmpp.im.conversation.AbstractConversation.on_failure` events and
  implement emission of those for the existing conversation implementations.

* Specify that :term:`Conversation Services <Conversation Service>` must
  provide a non-coroutine method to start a conversation. Asynchronous parts
  have to happen in the background. To await the completion of the
  initialisation of the conversation, use
  :func:`aioxmpp.callbacks.first_signal` as described in
  :meth:`aioxmpp.im.conversation.AbstractConversation.on_enter`.

* Make :meth:`aioxmpp.im.p2p.Service.get_conversation` a normal method.

* :meth:`aioxmpp.muc.Room.send_message` is not a
  coroutine anymore, but it returns an awaitable; this means that in most
  cases, this should not break.

  :meth:`~aioxmpp.muc.Room.send_message` was a coroutine by accident; it should
  never have been that, according to the specification in
  :meth:`aioxmpp.im.conversation.AbstractConversation.send_message`.

* Since multiple ``<delay/>`` elements can occur in a
  stanza, :attr:`aioxmpp.Message.xep0203_delay` is now a list instead of a
  single :class:`aioxmpp.misc.Delay` object. Sorry for the inconvenience.

* The type of the value of
  :class:`aioxmpp.xso.Collector` descriptors was changed from
  :class:`list` to :class:`lxml.etree.Element`.

* Assignment to :class:`aioxmpp.xso.Collector` descriptors is now forbidden.
  Instead, you should use ``some_xso.collector_attr[:] = items`` or a similar
  syntax.

* :meth:`aioxmpp.muc.Room.on_enter` does not receive any
  arguments anymore to comply with the updated
  :class:`aioxmpp.im.AbstractConversation` spec. The
  :meth:`aioxmpp.muc.Room.on_muc_enter` event provides the arguments
  :meth:`~aioxmpp.muc.Room.on_enter` received before and fires right after
  :meth:`~aioxmpp.muc.Room.on_enter`.

  As a workaround (if you need the arguments), you can test whether the
  :meth:`~aioxmpp.muc.Room.on_muc_enter` exists on a
  :class:`~aioxmpp.muc.Room`. If it does, connect to it, otherwise connect to
  :meth:`~aioxmpp.muc.Room.on_enter`.

  If you don’t need the arguments, make your :meth:`~aioxmpp.muc.Room.on_enter`
  handlers accept ``*args``.

* :meth:`aioxmpp.AvatarService.get_avatar_metadata`
  now returns a list instead of a mapping from MIME types to lists of
  descriptors.

* Replaced the
  :attr:`aioxmpp.stream.StanzaStream.ping_interval` and
  :attr:`~aioxmpp.stream.StanzaStream.ping_opportunistic_interval` attributes
  with a new ping implementation.

  It is described in the :ref:`aioxmpp.stream.General Information.Timeouts`
  section in :mod:`aioxmpp.stream`.

* :meth:`aioxmpp.connector.BaseConnector.connect`
  implementations are expected to set the
  :attr:`aioxmpp.protocol.XMLStream.deadtime_hard_limit` to the
  value of their `negotiation_timeout` argument and use this mechanism to handle
  any stream-level timeouts.

* :attr:`aioxmpp.muc.Occupant.direct_jid`
  is now always a bare jid. This implies that the resource part of a
  jid passed in by a muc member item now is always ignored.  Passing a
  full jid to the constructor now raises a :class:`ValueError`.

Minor features and bug fixes
----------------------------

* Make :mod:`aioopenssl` a mandatory dependency.

* Replace :mod:`orderedset` with :mod:`sortedcollections`.

* Emit :meth:`aioxmpp.im.conversation.AbstractConversation.on_message` for
  MUC messages sent via :meth:`~aioxmpp.muc.Room.send_message_tracked`.

* Add ``tracker`` argument to
  :meth:`aioxmpp.im.conversation.AbstractConversation.on_message`. It carries
  a :class:`aioxmpp.tracking.MessageTracker` for sent messages (including
  those sent by other resources of the account in the same conversation).

* Fix (harmless) traceback in logs which could occur when using
  :meth:`aioxmpp.muc.Room.send_message_tracked`.

* Fix :func:`aioxmpp.service.is_depsignal_handler` and
  :func:`~aioxmpp.service.is_attrsignal_handler` when used with ``defer=True``.

* You can now register custom bookmark classes with
  :func:`aioxmpp.bookmarks.as_bookmark_class`. The bookmark classes
  must subclass the ABC :class:`aioxmpp.bookmarks.Bookmark`.

* Implement :func:`aioxmpp.callbacks.first_signal`.

* Fixed duplicate emission of
  :meth:`~aioxmpp.im.conversation.AbstractConversation.on_message` events
  for untracked (sent through :meth:`aioxmpp.muc.Room.send_message`) MUC
  messages.

* Re-read the nameserver config if :class:`dns.resolver.NoNameservers` is
  raised during a query using the thread-local global resolver (the default).

  The resolver config is only reloaded up to once for each query; any further
  errors are treated as authoritative / related to the zone.

* Add :meth:`aioxmpp.protocol.XMLStream.mute` context manager to suppress debug
  logging of stream contents.

* Exclude authentication information sent during SASL.

* The new :meth:`aioxmpp.structs.LanguageMap.any` method allows to obtain an
  arbitrary element from the language map.

* New `erroneous_as_absent` argument to :class:`aioxmpp.xso.Attr`,
  :class:`~aioxmpp.xso.Text` and :class:`~aioxmpp.xso.ChildText`. See the
  documentation of :class:`~aioxmpp.xso.Attr` for details.

* Treat absent ``@type`` XML attribute on message stanzas as
  :class:`aioxmpp.MessageType.NORMAL`, as specified in :rfc:`6121`,
  section 5.2.2.

* Treat empty ``<show/>`` XML child on presence stanzas like absent
  ``<show/>``. This is not legal as per :rfc:`6120`, but apparently there are
  some broken implementations out there.

  Not having this workaround leads to being unable to receive presence stanzas
  from those entities, which is rather unfortunate.

* :func:`aioxmpp.service.iq_handler` now checks that its payload class is in
  fact registered as IQ payload and raises :class:`ValueError` if not.

* :func:`aioxmpp.node.discover_connectors` will now continue of only one of the
  two SRV lookups fails with the DNSPython :class:`dns.resolver.NoNameservers`
  exception; this case might still indicate a configuration issue (so we log
  it), but since we actually got a useful result on the other query, we can
  still continue.

* :func:`aioxmpp.node.discover_connectors` now uses a proper fully-qualified
  domain name (including the trailing dot) for DNS queries to avoid improper
  fallback to locally configured search domains.

* Ignore presence stanzas from the bare JID of a joined MUC, even if they
  contain a MUC user tag. A functional MUC should never emit this.

* We now will always attempt STARTTLS negotiation if
  :attr:`aioxmpp.security_layer.SecurityLayer.tls_required` is true, even if
  the server does not advertise a STARTTLS stream feature. This is because we
  have nothing to lose, and it may mitigate some types of STARTTLS stripping
  attacks.

* Compatibility fixes for ejabberd (cf.
  `ejabberd#2287 <https://github.com/processone/ejabberd/issues/2287>`_
  and `ejabberd#2288 <https://github.com/processone/ejabberd/issues/2288>`_).

* Harden MUC implementation against incomplete presence stanzas.

* Fix a race condition where stream management handlers would be installed too
  late on the XML stream, leading it to be closed with an
  ``unsupported-stanza-type`` because :mod:`aioxmpp` failed to interpret SM
  requests.

* Support for escaping additional characters as entities when writing XML, see
  the `additional_escapes` argument to :class:`aioxmpp.xml.XMPPXMLGenerator`.

* Support for the new :xep:`45` 1.30 status code for kicks due to errors.
  See :attr:`aioxmpp.muc.LeaveMode.ERROR`.

* Minor compatibility fixes for :xep:`153` vcard-based avatar support.

* Add a global IM :meth:`aioxmpp.im.service.Conversation.on_message` event. This
  aggregates message events from all conversations.

  This can be used by applications which want to perform central processing of
  all IM messages, for example for logging purposes.
  :class:`aioxmpp.im.service.Conversation` handles the lifecycle of event
  listeners to the individual conversations, which takes some burden off of the
  application.

* Fix a bug where monkey-patched :class:`aioxmpp.xso.ChildFlag` descriptors
  would not be picked up by the XSO handling code.

* Make sure that the message ID is set before the
  :attr:`aioxmpp.im.conversation.AbstractConversation.on_message` event is
  emitted from :class:`aioxmpp.im.p2p.Conversation` objects.

* Ensure that all
  :attr:`aioxmpp.MessageType.CHAT`/:attr:`~aioxmpp.MessageType.NORMAL` messages
  are forwarded to the respective :class:`aioxmpp.im.p2p.Conversation` if it
  exists.

  (Previously, only messages with a non-empty :attr:`aioxmpp.Message.body`
  would be forwarded.)

  This is needed for e.g. Chat Markers.

* Ensure that Message Carbons are
  re-:meth:`aioxmpp.carbons.CarbonsClient.enable`\ -d after failed stream
  resumption. Thanks, Ge0rG.

* Fix :rfc:`6121` violation: the default of the ``@subscription`` attribute of
  roster items is ``"none"``. :mod:`aioxmpp` treated an absent attribute as
  fatal.

* Pass pre-stream-features exception down to stream feature listeners. This
  fixes hangs on errors before the stream features are received. This can
  happen with misconfigured SRV records or lack of ALPN support in a :xep:`368`
  setting. Thanks to Travis Burtrum for providing a test setup for hunting this
  down.

* Set ALPN to ``xmpp-client`` by default. This is useful for :xep:`368`
  deployments.

* Fix handling of SRV records with equal priority, weight, hostname and port.

* Support for ``<optional/>`` element in :rfc:`3921` ``<session/>`` negotiation
  feature; the feature is not needed with modern servers, but since legacy
  clients require it, they still announce it. The feature introduces a new
  round-trip for no gain. An `rfc-draft by Dave Cridland
  <https://tools.ietf.org/html/draft-cridland-xmpp-session-01>`_ standardises
  the ``<optional/>`` element which allows a server to tell the client that it
  doesn’t require the session negotiation step. :mod:`aioxmpp` now understands
  this and will skip that step, saving a round-trip with most modern servers.

* :mod:`aioxmpp.tracking` now allows some state transitions out of the
  :attr:`aioxmpp.tracking.MessageState.ERROR` state. See the documentation there
  for details.

* Fix a bug in :meth:`aioxmpp.JID.fromstr` which would incorrectly parse and
  then reject some valid JIDs.

* Add :meth:`aioxmpp.DiscoClient.flush_cache` allowing to flush the cached
  entries.

* Add :meth:`aioxmpp.disco.Node.set_identity_names`. This is much more
  convenient than adding a dummy identity, removing the existing identity,
  re-adding the identity with new names and then removing the dummy identity.

* Remove restriction on data form types (not to be confused with
  ``FORM_TYPE``) when instantiating a form with
  :meth:`aioxmpp.forms.Form.from_xso`.

* Fix an issue which prevented single-valued form fields from being rendered
  into XSOs if no value had been set (but a default was given).

* Ensure that forms with :attr:`aioxmpp.forms.Form.FORM_TYPE` attribute render
  a proper :xep:`68` ``FORM_TYPE`` field.

* Allow unset field type in data forms. This may seem weird, but unfortunately
  it is widespread practice. In some data form types, omitting the field type
  is common (including it is merely a MAY in the XEP), and even in the most
  strict case it is only a SHOULD.

  Relying on the field type to be present is thus a non-starter.

* Some data form classes were added:

    * :class:`aioxmpp.muc.InfoForm`
    * :class:`aioxmpp.muc.VoiceRequestForm`

* Support for answering requests for voice/role change in MUCs (cf.
  `XEP-0045 §8.6 Approving Voice Requests <https://xmpp.org/extensions/xep-0045.html#voiceapprove>`_). See
  :meth:`aioxmpp.muc.Room.on_muc_role_request` for details.

* Support for unwrapped unknown values in :class:`aioxmpp.xso.EnumCDataType`.
  This can be used with :class:`enum.IntEnum` for fun and profit.

* The status codes for :mod:`aioxmpp.muc` events are now an enumeration (see
  :class:`aioxmpp.muc.StatusCode`). The status codes are now also available
  on the following events: :meth:`aioxmpp.muc.Room.on_muc_enter`,
  :meth:`~aioxmpp.muc.Room.on_exit`,
  :meth:`~aioxmpp.muc.Room.on_leave`, :meth:`~aioxmpp.muc.Room.on_join`,
  :meth:`~aioxmpp.muc.Room.on_muc_role_changed`, and
  :meth:`~aioxmpp.muc.Room.on_muc_affiliation_changed`.

* The :meth:`aioxmpp.im.conversation.AbstractConversation.invite` was
  overhauled and improved.

* :class:`aioxmpp.PEPClient` now depends on :class:`aioxmpp.EntityCapsService`.
  This prevents a common mistake of loading :class:`~aioxmpp.PEPClient` without
  :class:`~aioxmpp.EntityCapsService`, which prevents PEP auto-subscription
  from working.

* Handle :class:`ValueError` raised by :mod:`aiosasl` when the credentials are
  malformed.

* Fix exception when attempting to leave a :class:`aioxmpp.im.p2p.Conversation`.

Deprecations
------------

* The above split of :class:`aioxmpp.xso.AbstractType` also caused a split of
  :class:`aioxmpp.xso.EnumType` into :class:`aioxmpp.xso.EnumCDataType` and
  :class:`aioxmpp.xso.EnumElementType`. :func:`aioxmpp.xso.EnumType` is now a
  function which transparently creates the correct class. Use of that function
  is deprecated and you should upgrade your code to use one of the two named
  classes explicitly.

* The name :meth:`aioxmpp.stream.StanzaStream.register_iq_request_coro` is
  deprecated in favour of
  :meth:`~aioxmpp.stream.StanzaStream.register_iq_request_handler`.
  The old alias persists, but will be removed with the release of 1.0. Using
  the old alias emits a warning.

  Likewise, :meth:`~aioxmpp.stream.StanzaStream.unregister_iq_request_coro` was
  renamed to :meth:`~aioxmpp.stream.StanzaStream.unregister_iq_request_handler`.

* :meth:`aioxmpp.stream.StanzaStream.enqueue` and
  :meth:`aioxmpp.stream.StanzaStream.send` were moved to the client as
  :meth:`aioxmpp.Client.enqueue` and :meth:`aioxmpp.Client.send`.

  The old names are deprecated, but aliases are provided until version 1.0.

* The `negotiation_timeout` argument for
  :func:`aioxmpp.security_layer.negotiate_sasl` has been deprecated in favour
  of :class:`aioxmpp.protocol.XMLStream`\ -level handling of timeouts.

  This means that the respective timeouts need to be configured on the XML
  stream if they are to be used (the normal connection setup takes care of
  that).

* The use of namespace-name tuples for error conditions has been deprecated
  (see the breaking changes).

.. _api-changelog-0.9:

Version 0.9
===========

New XEP implementations
-----------------------

* :mod:`aioxmpp.bookmarks` (:xep:`48`): Support for accessing bookmark storage
  (currently only from Private XML storage).

* :mod:`aioxmpp.private_xml` (:xep:`49`): Support for accessing a server-side
  account-private XML storage.

* :mod:`aioxmpp.avatar` (:xep:`84`): Support for retrieving avatars,
  notifications for changed avatars in contacts and setting the avatar of the
  account itself.

* :mod:`aioxmpp.pep` (:xep:`163`): Support for making use of the Personal
  Eventing Protocol, a versatile protocol used to store and publish
  account-specific information such as Avatars, OMEMO keys, etc. throughout the
  XMPP network.

* :mod:`aioxmpp.blocking` (:xep:`191`): Support for blocking contacts on the
  server-side.

* :mod:`aioxmpp.ping` (:xep:`199`): XMPP Ping has been used internally since
  the very beginning (if Stream Management is not supported), but now there’s
  also a service for applications to use.

* :mod:`aioxmpp.carbons` (:xep:`280`): Support for receiving carbon-copies of
  messages sent and received by other resources.

* :mod:`aioxmpp.entitycaps` (:xep:`390`): Support for the new Entity
  Capabilities 2.0 protocol was added.

Most of these have been contributed by Sebastian Riese. Thanks for that!

New major features
------------------

* :mod:`aioxmpp.im` is a new subpackage which provides Instant Messaging
  services. It is still highly experimental, and feedback on the API is highly
  appreciated.

  The idea is to provide a unified interface to the different instant messaging
  transports, such as direct one-on-one chat, Multi-User Chats (:xep:`45`) and
  the soon-to-come Mediated Information Exchange (:xep:`369`).

  Applications shall be able to use the interface without knowing the details
  of the transport; features such as message delivery receipts and message
  carbons shall work transparently.

  In the course of this (see below), some breaking changes had to be made, but
  we think that the gain is worth the damage.

  For an introduction in those features, read the documentation of the
  :mod:`aioxmpp.im` subpackage. The examples using IM features have been
  updated accordingly.

* The distribution of received presence and message stanzas has been reworked
  (to help with :mod:`aioxmpp.im`, which needs a very different model of
  message distribution than the traditional "register a handler for a sender
  and type"). The classic registration functions have been deprecated (see
  below) and were replaced by simple dispatcher services provided in
  :mod:`aioxmpp.dispatcher`.

New examples
------------

* ``carbons_sniffer.py``: Show a log of all messages received and sent by other
  resources of the same account.

* ``set_avatar.py``: Change the avatar of the account.

* ``retrieve_avatar.py``: Retrieve the avatar of a member of the XMPP network
  (sufficient permissions required, normally a roster subscription is enough).

Breaking changes
----------------

* Classes using :func:`aioxmpp.service.message_handler` or
  :func:`aioxmpp.service.presence_handler` have to declare
  :class:`aioxmpp.dispatcher.SimpleMessageDispatcher` or
  :class:`aioxmpp.dispatcher.SimplePresenceDispatcher` (respectively) in their
  dependencies.

  A backward-compatible way to do so is to declare the dependency
  conditionally::

    class FooService(aioxmpp.service.Service):
        ORDER_AFTER = []
        try:
            import aioxmpp.dispatcher
        except ImportError:
            pass
        else:
            ORDER_AFTER.append(
                aioxmpp.dispatcher.SimpleMessageDispatcher
            )

* :class:`aioxmpp.stream.Filter` got renamed to
  :class:`aioxmpp.callbacks.Filter`. This should normally not affect your code.

* Re-write of :mod:`aioxmpp.tracking` for :mod:`aioxmpp.im`. Sorry. But the new
  API is more clearly defined and more correct. The (ab-)use of
  :class:`aioxmpp.statemachine.OrderedStateMachine` never really worked
  anyways.

* Re-design of interface to :mod:`aioxmpp.muc`. This is unfortunate, but we
  did not see a way to reasonably provide backward-compatibility while still
  allowing for a clean integration with :mod:`aioxmpp.im`.

* Re-design of :class:`aioxmpp.entitycaps` to support
  :xep:`390`. The interface of the :class:`aioxmpp.entitycaps.Cache` class has
  been redesigned and some internal classes and functions have been renamed.

* :attr:`aioxmpp.IQ.payload`,
  :attr:`aioxmpp.pubsub.xso.Item.registered_payload` and
  :attr:`aioxmpp.pubsub.xso.EventItem.registered_payload` now strictly check
  the type of objects assigned. The classes of those objects *must* be
  registered with :meth:`aioxmpp.IQ.as_payload_class` or
  :func:`aioxmpp.pubsub.xso.as_payload_class`, respectively.

  Technically, that requirement existed always as soon as one wanted to be able
  to *receive* those payloads: otherwise, one would simply not receive the
  payload, but an exception or empty object instead. By enforcing this
  requirement also for sending, we hope to improve the debugability of these
  issues.

* The descriptors and decorators for
  :class:`aioxmpp.service.Service` subclasses are now initialised in the order
  they are declared.

  This should normally not affect you, there are only very specific
  corner-cases where it makes a difference.

Minor features and bug fixes
----------------------------

* Handle local serialisation issues more gracefully. Instead of sending a
  half-serialised XSO down the stream and then raising an exception, leaving the
  stream in an undefined state, XSOs are now serialised into a buffer (which is
  re-used for performance when possible) and only if serialisation was
  successful sent down the stream.

* Replaced the hack-ish use of generators for
  :func:`aioxmpp.xml.write_xmlstream` with a proper class,
  :class:`aioxmpp.xml.XMLStreamWriter`.

  The generator blew up when we tried to exfiltrate exceptions from it. For the
  curious and brave, see the ``bug/odd-exception-thing`` branch. I actually
  suspect a CPython bug there, but I was unable to isolate a proper test case.
  It only blows up in the end-to-end tests.

* :mod:`aioxmpp.dispatcher`: This is in connection with the :mod:`aioxmpp.im`
  package

* :mod:`aioxmpp.misc` provides XSO definitions for two minor XMPP protocol
  parts (:xep:`203`, :xep:`297`), which are however reused in some of the
  protocols implemented in this release.

* :mod:`aioxmpp.hashes` (:xep:`300`): Friendly interface to the hash functions
  and hash function names defined in :xep:`300`.

* :xep:`Stream Management <198>` counters now wrap around as unsigned
  32 bit integers, as the standard specifies.

* :func:`aioxmpp.service.depsignal` now supports connecting to
  :class:`aioxmpp.stream.StanzaStream` and :class:`aioxmpp.Client` signals.

* Unknown and unhandled IQ get/set payloads are now replied to with
  ``<service-unavailable/>`` instead of ``<feature-not-implemented/>``, as the
  former is actually specified in :rfc:`6120` section 8.4.

* The :class:`aioxmpp.protocol.XMLStream` loggers for :class:`aioxmpp.Client`
  objects are now a child of the client logger itself, and not at
  ``aioxmpp.XMLStream``.

* Fix bug in :class:`aioxmpp.EntityCapsService` rendering it useless for
  providing caps hashes to other entities.

* Fix :meth:`aioxmpp.callbacks.AdHocSignal.future`, which was entirely unusable
  before.

* :func:`aioxmpp.service.depfilter`: A decorator (similar to the
  :func:`aioxmpp.service.depsignal` decorator) which allows to add a
  :class:`aioxmpp.service.Service` method to a
  :class:`aioxmpp.callbacks.Filter` chain.

* Fix :attr:`aioxmpp.RosterClient.groups` not being updated when items are
  removed during initial roster update.

* The two signals :meth:`aioxmpp.RosterClient.on_group_added`,
  :meth:`~aioxmpp.RosterClient.on_group_removed` were added, which allow to
  track which groups exist in a roster at all (a group exists if there’s at
  least one member).

* Roster pushes are now accepted also if the :attr:`~.StanzaBase.from_` is the
  bare local JID instead of missing/empty (those are semantically equivalent).

* :class:`aioxmpp.disco.RegisteredFeature` and changes to
  :class:`aioxmpp.disco.register_feature`. Effectively, attributes described by
  :class:`~aioxmpp.disco.register_feature` now have an
  :attr:`~aioxmpp.disco.RegisteredFeature.enabled` attribute which can be used
  to temporarily or permanently disable the registration of the feature on a
  service object.

* The :meth:`aioxmpp.disco.StaticNode.clone` method allows to copy another
  :meth:`aioxmpp.disco.Node` as a :class:`aioxmpp.disco.StaticNode`.

* The :meth:`aioxmpp.disco.Node.as_info_xso` methdo creates a
  :class:`aioxmpp.disco.xso.InfoQuery` object containing the features and
  identities of the node.

* The `strict` argument was added to :class:`aioxmpp.xso.Child`. It allows to
  enable strict type checking of the objects assigned to the descriptor. Only
  those objects whose classes have been registered with the descriptor can be
  assigned.

  This helps with debugging issues for "extensible" descriptors such as the
  :attr:`aioxmpp.IQ.payload` as described in the Breaking Changes section of
  this release.

* :class:`aioxmpp.DiscoClient` now uses :class:`aioxmpp.cache.LRUDict`
  for its internal caches to prevent memory exhaustion in long running
  applications and/or with malicious peers.

* :meth:`aioxmpp.DiscoClient.query_info` now supports a `no_cache` argument
  which prevents caching of the request and response.

* :func:`aioxmpp.service.attrsignal`: A decorator (similar to the
  :func:`aioxmpp.service.depsignal` decorator) which allows to connect to a
  signal on a descriptor.

* The `default` of XSO descriptors has incorrectly been passed through the
  validator, despite the documentation saying otherwise. This has been fixed.

* :attr:`aioxmpp.Client.resumption_timeout`: Support for specifying the
  lifetime of a Stream  Management (:xep:`198`) session and disabling stream
  resumption altogether. Thanks to `@jomag for bringing up the use-case
  <https://github.com/horazont/aioxmpp/issues/114>`_.

* Fix serialisation of :class:`aioxmpp.xso.Collector` descriptors.

* Make :class:`aioxmpp.xml.XMPPXMLGenerator` avoid the use of namespace
  prefixes if a namespace is undeclared if possible.

* Attempt to reconnect if generic OpenSSL errors occur. Thanks to `@jomag for
  reporting <https://github.com/horazont/aioxmpp/issues/116>`_.

* The new :meth:`aioxmpp.stream.StanzaStream.on_message_received`,
  :meth:`~aioxmpp.stream.StanzaStream.on_presence_received` signals
  unconditionally fire when a message or presence is received. They are used
  by the :mod:`aioxmpp.dispatcher` and :mod:`aioxmpp.im` implementations.

Deprecations
------------

* The following methods on :class:`aioxmpp.stream.StanzaStream`
  have been deprecated and will be removed in 1.0:

  * :meth:`~.StanzaStream.register_message_callback`
  * :meth:`~.StanzaStream.unregister_message_callback`
  * :meth:`~.StanzaStream.register_presence_callback`
  * :meth:`~.StanzaStream.unregister_presence_callback`

  The former two are replaced by the
  :class:`aioxmpp.dispatcher.SimpleMessageDispatcher` service and the latter two
  should be replaced by proper use of the :class:`aioxmpp.PresenceClient` or
  by :class:`aioxmpp.dispatcher.SimplePresenceDispatcher` if the
  :class:`~aioxmpp.PresenceClient` is not sufficient.

* :func:`aioxmpp.stream.stanza_filter` got renamed to
  :meth:`aioxmpp.callbacks.Filter.context_register`.

Version 0.9.1
-------------

* *Slight Breaking change* (yes, I know!) to fix a crucial bug with Python
  3.4.6. :func:`aioxmpp.node.discover_connectors` now takes a :class:`str`
  argument instead of :class:`bytes` for the domain name. Passing a
  :class:`bytes` will fail.

  As this issue prohibited use with Python 3.4.6 under certain circumstances,
  we had to make a slight breaking change in a minor release. We also consider
  :func:`~aioxmpp.node.discover_connectors` to be sufficiently rarely useful
  to warrant breaking compatibility here.

  For the same reason, :func:`aioxmpp.network.lookup_srv` now returns
  :class:`bytes` for hostnames instead of :class:`str`.

* Fix issues with different versions of :mod:`pyasn1`.


.. _api-changelog-0.8:

Version 0.8
===========

New XEP implementations
-----------------------

* :mod:`aioxmpp.adhoc` (:xep:`50`): Support for using Ad-Hoc commands;
  publishing own Ad-Hoc commands for others to use is not supported yet.

New major features
------------------

* Services (see :mod:`aioxmpp.service`) are now even easier to write, using
  the new :ref:`api-aioxmpp.service-decorators`. These allow automagically
  registering methods as handlers or filters for stanzas and other often-used
  things.

  Existing services have been ported to this new system, and we recommend to
  do the same with your own services!

* :mod:`aioxmpp` now supports end-to-end testing using an XMPP server (such as
  `Prosody <https://prosody.im>`_). For the crude details see
  :mod:`aioxmpp.e2etest` and the :ref:`dg-end-to-end-tests` section in the
  Developer Guide. The :mod:`aioxmpp.e2etest` API is still highly experimental
  and should not be used outside of :mod:`aioxmpp`.

New examples
------------

* ``adhoc_browser``: A graphical tool to browse and execute Ad-Hoc Commands.
  Requires PyQt5. Run ``make`` in the examples directory and start with
  ``python3 -m adhoc_browser``.

* ``entity_items.py``, ``entity_info.py``: Show service discovery info and items
  for arbitrary JIDs.

* ``list_adhoc_commands.py``: List the Ad-Hoc commands offered by an entity.

Breaking changes
----------------

Changes to the connection procedure:

* If any of the connection errors encountered in
  :meth:`aioxmpp.node.connect_xmlstream` is a
  :class:`aioxmpp.errors.TLSFailure` *and all* other connection options also
  failed, the :class:`~.errors.TLSFailure` is re-raised instead of a
  :class:`aioxmpp.errors.MultiOSError` instance. This helps to prevent masking
  of configuration problems.

* The change of :meth:`aioxmpp.node.connect_xmlstream` described above also
  affects the behaviour of :class:`aioxmpp.Client`, as
  :class:`~.errors.TLSFailure` errors are treated as critical (in contrast to
  :class:`OSError` subclasses).

Changes in :class:`aioxmpp.Client` (formerly :class:`aioxmpp.AbstractClient`,
see in the deprecations below for the name change)

* The number of connection attempts made before the first connection is
  successful is now bounded, configurable through the new parameter
  `max_initial_attempts`. The default is at 4, which gives (together with the
  default exponential backoff parameters) a minimum time of attempted
  connections of about 5 seconds.

* :meth:`~.Client.on_stream_suspended` was added (this is not a breaking
  change, but belongs to the :class:`aioxmpp.Client` changes discussed here).

* :meth:`~.Client.on_stream_destroyed` got a new argument `reason`
  which gives the exception which caused the stream to be destroyed.

Other breaking changes:

* :attr:`aioxmpp.tracking.MessageState.UNKNOWN` renamed to
  :attr:`~.MessageState.CLOSED`.

* :meth:`aioxmpp.disco.Node.iter_items`,
  :meth:`~aioxmpp.disco.Node.iter_features` and
  :meth:`~aioxmpp.disco.Node.iter_identities` now get the request stanza passed
  as first argument.

* :attr:`aioxmpp.Presence.show` now uses the
  :class:`aioxmpp.PresenceShow` enumeration. The breakage is similar to the
  breakage in the 0.7 release; if I had thought of it at that time, I would have
  made the change back then, but it was overlooked.

  Again, a utility script (``find-v0.8-type-transitions.sh``) is provided which
  helps finding locations of code which need changing. See the
  :ref:`api-changelog-0.7` for details.

* Presence states with ``show`` set to
  :attr:`~.PresenceShow.DND` now order highest (before,
  :attr:`~.PresenceShow.DND` ordered lowest). The rationale is that if a user
  indicates :attr:`~.PresenceShow.DND` state at one resource, one should
  probably respect the Do-Not-Disturb request on all resources.

The following changes are not severe, but may still break code depending on how
it is used:

* :class:`aioxmpp.disco.Service` was split into
  :class:`aioxmpp.DiscoClient` and :class:`aioxmpp.DiscoServer`.

  If you need to be compatible with old versions, use code like this::

    try:
        from aioxmpp import DiscoClient, DiscoServer
    except ImportError:
        import aioxmpp.disco
        DiscoClient = aioxmpp.disco.Service
        DiscoServer = aioxmpp.disco.Service

* Type coercion in XSO descriptors now behaves differently. Previously,
  :data:`None` was hard-coded to be exempt from type coercion; this allowed
  *any* :class:`~.xso.Text`,  :class:`~.xso.ChildText`, :class:`~.xso.Attr` and
  other scalar descriptor to be assigned :data:`None`, unless a validator which
  explicitly forbade that was installed. The use case was to have a default,
  absence-indicating value which is outside the valid value range of the
  ``type_``.

  This is now handled by exempting the ``default`` of the descriptor from type
  coercion and thus allowing assignment of that default by default. The change
  thus only affects descriptors which have a ``default`` other than
  :data:`None` (which includes an unset default).

Minor features and bug fixes
----------------------------

* :class:`aioxmpp.stream.StanzaToken` objects are now :term:`awaitable`.

* :meth:`aioxmpp.stream.StanzaStream.send` introduced as method which can be
  used to send arbitrary stanzas. See the docs there to observe the full
  awesomeness.

* Improvement and fixes to :mod:`aioxmpp.muc`:

  * Implemented :meth:`aioxmpp.muc.Room.request_voice`.
  * Fix :meth:`aioxmpp.muc.Room.leave_and_wait` never returning.
  * Do not emit :meth:`aioxmpp.muc.Room.on_join` when an unavailable presence
    from an unknown occupant JID is received.

* Added context managers for registering a callable as stanza handler or filter
  temporarily:

  * :func:`aioxmpp.stream.iq_handler`,
  * :func:`aioxmpp.stream.message_handler`,
  * :func:`aioxmpp.stream.presence_handler`, and
  * :func:`aioxmpp.stream.stanza_filter`.

* The :attr:`aioxmpp.service.Service.dependencies` attribute was added.

* Support for ANONYMOUS SASL mechanism. See :meth:`aioxmpp.security_layer.make`
  for details (requires aiosasl 0.3+).

* Get rid of dependency on libxml2 development files. libxml2 itself is still
  required, both directly and indirectly (through the lxml dependency).

* The :class:`aioxmpp.PresenceServer` service was introduced and the
  :class:`aioxmpp.PresenceManagedClient` was re-implemented on top of that.

* Fix :exc:`AttributeError` being raised from ``state > None`` (and other
  comparison operators), with ``state`` being a :class:`aioxmpp.PresenceState`
  instance.

  The more correct :exc:`TypeError` is now raised.

* The handling of stanzas with unparseable attributes and stanzas originating
  from the clients bare JID (i.e. from the clients server on behalf on the
  account) has improved.

* The examples now default to ``$XDG_CONFIG_HOME/aioxmpp-examples.ini`` for
  configuration if it exists. (thanks, `@mcepl
  <https://github.com/horazont/aioxmpp/pull/27>`_).

Deprecations
------------

* Several classes were renamed:

  * :class:`aioxmpp.node.AbstractClient` → :class:`aioxmpp.Client`
  * :class:`aioxmpp.shim.Service` → :class:`aioxmpp.SHIMService`
  * :class:`aioxmpp.muc.Service` → :class:`aioxmpp.MUCClient`
  * :class:`aioxmpp.presence.Service` → :class:`aioxmpp.PresenceClient`
  * :class:`aioxmpp.roster.Service` → :class:`aioxmpp.RosterClient`
  * :class:`aioxmpp.entitycaps.Service` → :class:`aioxmpp.EntityCapsService`
  * :class:`aioxmpp.pubsub.Service` → :class:`aioxmpp.PubSubClient`

  The old names are still available until 1.0.

* :meth:`~.StanzaStream.send_and_wait_for_sent` deprecated in favour of
  :meth:`~.StanzaStream.send`.

* :meth:`~.StanzaStream.send_iq_and_wait_for_reply` deprecated in favour of
  :meth:`~.StanzaStream.send`.

* :meth:`~.StanzaStream.enqueue_stanza` is now called
  :meth:`~aioxmpp.stream.StanzaStream.enqueue`.

* The `presence` argument to the constructor of and the
  :attr:`~.UseConnected.presence` and :attr:`~.UseConnected.timeout` attributes
  on :class:`aioxmpp.node.UseConnected` objects are deprecated.

  See the respective documentation for details on the deprecation procedure.

.. _api-changelog-0.7:

Version 0.7
===========

* **License change**: As of version 0.7, :mod:`aioxmpp` is distributed under the
  terms of the GNU Lesser General Public License version 3 or later (LGPLv3+).
  The exact terms are, as usual, found by taking a look at ``COPYING.LESSER`` in
  the source code repository.

* New XEP implementations:

  * :mod:`aioxmpp.forms` (:xep:`4`): An implementation of the Data Forms XEP.
    Take a look and see where it gets you.

* New features in the :mod:`aioxmpp.xso` submodule:

  * The new :class:`aioxmpp.xso.ChildFlag` descriptor is a simplification of the
    :class:`aioxmpp.xso.ChildTag`. It can be used where the presence or absence of
    a child element *only* signals a boolean flag.

  * The new :class:`aioxmpp.xso.EnumType` type allows using a :mod:`enum`
    enumeration as XSO descriptor type.

* Often-used names have now been moved to the :mod:`aioxmpp` namespace:

  * The stanza classes :class:`aioxmpp.IQ`, :class:`aioxmpp.Message`,
    :class:`aioxmpp.Presence`
  * The type enumerations (see below) :class:`aioxmpp.IQType`,
    :class:`aioxmpp.MessageType`, :class:`aioxmpp.PresenceType`
  * Commonly used structures: :class:`aioxmpp.JID`,
    :class:`aioxmpp.PresenceState`
  * Exceptions: :class:`aioxmpp.XMPPCancelError` and its buddies

* **Horribly Breaking Change** in the future: :attr:`aioxmpp.IQ.type_`,
  :attr:`aioxmpp.Message.type_`, :attr:`aioxmpp.Presence.type_`
  and :attr:`aioxmpp.stanza.Error.type_` now use :class:`aioxmpp.xso.EnumType`,
  with corresponding enumerations (see docs of the respective attributes).

  This will break about every piece of code ever written for aioxmpp, and it is
  not trivial to fix automatically. This is why the following fallbacks have
  been implemented:

  1. The :attr:`type_` attributes still accept their string (or :data:`None` in
     the case of :attr:`.Presence.type_`) values when being written. When being
     read, the attributes always return the actual enumeration value.

  2. The relevant enumeration members compare equal (and hash equally) to their
     values. Thus, ``MessageType.CHAT == "chat"`` is still true (and
     ``MessageType.CHAT != "chat"`` is false).

  3. :meth:`~.StanzaStream.register_message_callback`,
     :meth:`~.StanzaStream.register_presence_callback`, and
     :meth:`~.StanzaStream.register_iq_request_coro`, as well as their
     corresponding un-registration methods, all accept the string variants for
     their arguments, internally mapping them to the actual enumeration values.

  .. note::

     As a matter of fact (good news!), with only the fallbacks and no code
     fixes, the :mod:`aioxmpp` test suite passes. So it is likely that you will
     not notice any breakage in the 0.7 release, giving you quite some time to
     react.

  These fallbacks will be *removed* with aioxmpp 1.0, making the legacy use
  raise :exc:`TypeError` or fail silently. Each of these fallbacks currently
  produces a :exc:`DeprecationWarning`.

  .. note::

     :exc:`DeprecationWarning` warnings are not shown by default in Python 3. To
     enable them, either run the interpreter with the ``-Wd`` option, un-filter
     them explicitly using ``warnings.simplefilter("always")`` at the top of
     your program, or explore other options as documented in :mod:`warnings`.

  So, now I said I will be breaking all your code, how do you fix it? There are
  two ways to find affected pieces of code: (1) run it with warnings (see
  above), which will find all affected pieces of code and (2) use the shell
  script provided at `utils/find-v0.7-type-transitions.sh
  <https://github.com/horazont/aioxmpp/blob/devel/utils/find-v0.7-type-transitions.sh>`_
  to find a subset of potentially affected pieces of code automatically. The
  shell script uses `The Silver Searcher (ag) <http://geoff.greer.fm/ag/>`_
  (find it in your distributions package repositories, I know it is there on
  Fedora, Arch and Debian!) and regular expressions to find common patterns.
  Example usage::

    # find everything in the current subdirectory
    $ $AIOXMPPPATH/utils/find-v0.7-type-transitions.sh
    # only search in the foobar/ subdirectory
    $ $AIOXMPPPATH/utils/find-v0.7-type-transitions.sh foobar/
    # only look at the foobar/baz.py file
    $ $AIOXMPPPATH/utils/find-v0.7-type-transitions.sh foobar/baz.py

  The script was built while fixing :mod:`aioxmpp` itself after the bug. It has
  not found *all* affected pieces of code, but the vast majority. The others can
  be found by inspecting :exc:`DeprecationWarning` warnings being emitted.

* The :func:`aioxmpp.security_layer.make` makes creating a security layer much
  less cumbersome than before. It provides a simple interface supporting
  password authentication, certificate pinning and others.

  The interface of this function will be extended in the future when more
  authentication or certificate verification mechanisms come around.

* The two methods :meth:`aioxmpp.muc.Service.get_room_config`,
  :meth:`aioxmpp.muc.Service.set_room_config` have been implemented, allowing to
  manage MUC room configurations.

* Fix bug in :meth:`aioxmpp.xso.ChildValueMultiMap.to_sax` which rendered XSOs
  with that descriptor useless.

* Fix documentation on :meth:`aioxmpp.PresenceManagedClient.set_presence`.

* :class:`aioxmpp.callbacks.AdHocSignal` now logs when coroutines registered
  with :meth:`aioxmpp.callbacks.AdHocSignal.SPAWN_WITH_LOOP` raise exceptions or
  return non-:data:`None` values. See the documentation of
  :meth:`~aioxmpp.callbacks.AdHocSignal.SPAWN_WITH_LOOP` for details.

* :func:`aioxmpp.pubsub.xso.as_payload_class` is a decorator (akin to
  :meth:`aioxmpp.IQ.as_payload_class`) to declare that your
  :class:`~aioxmpp.xso.XSO` shall be allowed as pubsub payload.

* :meth:`~.StanzaStream.register_message_callback` and
  :meth:`~.StanzaStream.register_presence_callback` now explicitly raise
  :class:`ValueError` when an attempt to overwrite an existing listener is made,
  instead of silently replacing the callback.

Version 0.7.2
-------------

* Fix resource leak which would emit::

    task: <Task pending coro=<OrderedStateMachine.wait_for() running at /home/horazont/Projects/python/aioxmpp/aioxmpp/statemachine.py:170> wait_for=<Future pending cb=[Task._wakeup()]> cb=[XMLStream._stream_starts_closing()]>

* Improve compatibility of :mod:`aioxmpp.muc` with Prosody 0.9 and below, which
  misses sending the ``110`` status code on some presences.

* Handle inbound message stanzas with empty from attribute. Those are legal as
  per :rfc:`6120`, but were not handled properly.


Version 0.6
===========

* New dependencies:

  * :mod:`multidict` from :mod:`aiohttp`.
  * :mod:`aioopenssl`: This is the former :mod:`aioxmpp.ssl_transport` as a
    separate package; :mod:`aioxmpp` still ships with a fallback in case that
    package is not installed.

* New XEP implementations:

  * partial :mod:`aioxmpp.pubsub` (:xep:`60`): Everything which requires forms
    is not implemented yet. Publish/Subscribe/Retract and creation/deletion of
    nodes is verified to work (against `Prosody <https://prosody.im>`_ at
    least).

  * :mod:`aioxmpp.shim` (:xep:`131`), used for :mod:`aioxmpp.pubsub`.

  * :xep:`368` support was added.

* New features in the :mod:`aioxmpp.xso` subpackage:

  * :class:`aioxmpp.xso.NumericRange` validator, which can be used to validate
    the range of any orderable type.

  * :mod:`aioxmpp.xso.query`, a module which allows for running queries against
    XSOs. This is still highly experimental.

  * :class:`aioxmpp.xso.ChildValueMultiMap` descriptor, which uses
    :mod:`multidict` and is used in :mod:`aioxmpp.shim`.

* :mod:`aioxmpp.network` was rewritten for 0.5.4

  The control over the used DNS resolver is now more sophisticated. Most
  notably, :mod:`aioxmpp.network` uses a thread-local resolver which is used for
  all queries by default.

  Normally, :func:`aioxmpp.network.repeated_query` will now re-configure the
  resolver from system-wide resolver configuration after the first timeout
  occurs.

  The resolver can be overridden (disabling the reconfiguration magic) using
  :func:`aioxmpp.network.set_resolver`.

* **Breaking change:** :class:`aioxmpp.service.Service` does not accept a
  `logger` argument anymore; instead, it now accepts a `base_logger` argument.
  Refer to the documentation of the class for details.

  The `base_logger` is automatically passed by
  :meth:`aioxmpp.node.AbstractClient.summon` on construction of the service and
  is the :attr:`aioxmpp.node.AbstractClient.logger` of the client instance.

* **Breaking change:** :class:`aioxmpp.xso.XSO` subclasses (or more
  specifically, instances of the :class:`aioxmpp.xso.model.XMLStreamClass`
  metaclass) now automatically declare a :attr:`__slots__` attribute.

  The mechanics are documented in detail on
  :attr:`aioxmpp.xso.model.XMLStreamClass.__slots__`.

* **Breaking change:** The following functions have been removed:

  * :func:`aioxmpp.node.connect_to_xmpp_server`
  * :func:`aioxmpp.node.connect_secured_xmlstream`
  * :func:`aioxmpp.security_layer.negotiate_stream_security`

  Use :func:`aioxmpp.node.connect_xmlstream` instead, but check the docs for the
  slightly different semantics.

  The following functions have been deprecated:

  * :class:`aioxmpp.security_layer.STARTTLSProvider`
  * :func:`aioxmpp.security_layer.security_layer`

  Use :class:`aioxmpp.security_layer.SecurityLayer` instead.

  The existing helper function
  :func:`aioxmpp.security_layer.tls_with_password_based_authentication` is still
  live and has been modified to use the new code.

* *Possibly breaking change:* The arguments to
  :meth:`aioxmpp.CertificateVerifier.pre_handshake` are now completely
  different. But as this method is not documented, this should not be a problem.

* *Possibly breaking change:* Attributes starting with ``_xso_`` are now also
  reserved on subclasses of :class:`aioxmpp.xso.XSO` (together with the
  long-standing reservation of attributes starting with ``xso_``).

* :meth:`aioxmpp.stanza.Error.as_application_condition`
* :meth:`aioxmpp.stanza.make_application_error`

* Several bugfixes in :mod:`aioxmpp.muc`:

  * :meth:`aioxmpp.muc.Room.on_message` now receives a proper `occupant` argument
    if occupant data is available when the message is received.

  * MUCs now autorejoin correctly after a disconnect.

  * Fix crash when using :class:`aioxmpp.tracking.MessageTracker` (e.g.
    indirectly through :meth:`aioxmpp.muc.Room.send_tracked_message`).

    Thanks to `@gudvnir <https://github.com/gudvinr>`_ over at github for
    pointing this out (see `issue#7
    <https://github.com/horazont/aioxmpp/issues/7>`_).

* Several bugfixes related to :class:`aioxmpp.protocol.XMLStream`:

  * :mod:`asyncio` errors/warnings about pending tasks being destroyed after
    disconnects should be gone now (:class:`aioxmpp.protocol.XMLStream` now
    properly cleans up its running coroutines).

  * The :class:`aioxmpp.protocol.XMLStream` is now closed or aborted by the
    :class:`aioxmpp.stream.StanzaStream` if the stream fails. This prevents
    lingering half-open TCP streams.

    See :meth:`aioxmpp.stream.StanzaStream.on_failure` for details.

* Some behaviour changes in :class:`aioxmpp.stream.StanzaStream`:

  When the stream is stopped without SM enabled, the following new behaviour has
  been introduced:

  * :attr:`~aioxmpp.stream.StanzaState.ACTIVE` stanza tokens are set to
    :attr:`~aioxmpp.stream.StanzaState.DISCONNECTED` state.

  * Coroutines which were spawned due to them being registered with
    :meth:`~aioxmpp.stream.StanzaStream.register_iq_request_coro` are
    :meth:`asyncio.Task.cancel`\ -ed.

  The same as above holds if the stream is closed, even if SM is enabled (as
  stream closure is clean and will broadcast unavailable presence server-side).

  This provides more fail-safe behaviour while still providing enough feedback.

* New method: :meth:`aioxmpp.stream.StanzaStream.send_and_wait_for_sent`.
  :meth:`~aioxmpp.stream.StanzaStream.send_iq_and_wait_for_reply` now also uses
  this.

* New method :meth:`aioxmpp.PresenceManagedClient.connected` and new class
  :class:`aioxmpp.node.UseConnected`.

  The former uses the latter to provide an asynchronous context manager which
  starts and stops a :class:`aioxmpp.PresenceManagedClient`. Intended for
  use in situations where an XMPP client is needed in-line. It saves a lot of
  boiler plate by taking care of properly waiting for the connection to be
  established etc.

* Fixed incorrect documentation of :meth:`aioxmpp.disco.Service.query_info`.
  Previously, the docstring incorrectly claimed that the method would return the
  result of :meth:`aioxmpp.disco.xso.InfoQuery.to_dict`, while it would in fact
  return the :class:`aioxmpp.disco.xso.InfoQuery` instance.

* Added `strict` arguments to :class:`aioxmpp.JID`. See the class
  docmuentation for details.

* Added `strict` argument to :class:`aioxmpp.xso.JID` and made it non-strict by
  default. See the documentation for rationale and details.

* Improve robustness against erroneous and malicious stanzas.

  All parsing errors on stanzas are now caught and handled by
  :meth:`aioxmpp.stream._process_incoming_erroneous_stanza`, which at least logs
  the synopsis of the stanza as parsed. It also makes sure that stream
  management works correctly, even if some stanzas are not understood.

  Additionally, a bug in the :class:`aioxmpp.xml.XMPPXMLProcessor` has been
  fixed which prevented errors in text content from being caught.

* No visible side-effects: Replaced deprecated
  :meth:`unittest.TestCase.assertRaisesRegexp` with
  :meth:`unittest.TestCase.assertRaisesRegex` (`thanks, Maxim
  <https://github.com/horazont/aioxmpp/pull/5>`_).

* Fix generation of IDs when sending stanzas. It has been broken for anything
  but IQ stanzas for some time.

* Send SM acknowledgement when closing down stream. This prevents servers from
  sending error stanzas for the unacked stanzas ☺.

* New callback mode :meth:`aioxmpp.callbacks.AdHocSignal.SPAWN_WITH_LOOP`.

* :mod:`aioxmpp.connector` added. This module provides classes which connect and
  return a :class:`aioxmpp.protocol.XMLStream`. They also handle TLS
  negotiation, if any.

* :class:`aioxmpp.node.AbstractClient` now accepts an `override_peer` argument,
  which may be a sequence of connection options as returned by
  :func:`aioxmpp.node.discover_connectors`. See the class documentation for
  details.

Version 0.6.1
-------------

* Fix :exc:`TypeError` crashes when using :mod:`aioxmpp.entitycaps`,
  :mod:`aioxmpp.presence` or :mod:`aioxmpp.roster`, arising from the argument
  change to service classes.

Version 0.5
===========

* Support for :xep:`0045` multi-user chats is now available in the
  :mod:`aioxmpp.muc` subpackage.

* Mostly transparent support for :xep:`0115` (Entity Capabilities) is now
  available using the :mod:`aioxmpp.entitycaps` subpackage.

* Support for transparent non-scalar attributes, which get mapped to XSOs. Use
  cases are dicts mapping language tags to strings (such as for message
  ``body`` elements) or sets of values which are represented by discrete XML
  elements.

  For this, the method :meth:`~aioxmpp.xso.AbstractType.get_formatted_type` was
  added to :class:`aioxmpp.xso.AbstractType` and two new descriptors,
  :class:`aioxmpp.xso.ChildValueMap` and :class:`aioxmpp.xso.ChildValueList`,
  were implemented.

  .. autosummary::

     ~aioxmpp.xso.ChildValueMap
     ~aioxmpp.xso.ChildValueList
     ~aioxmpp.xso.ChildTextMap

  **Breaking change**: The above descriptors are now used at several places,
  breaking the way these attributes need to be accessed:

  * :attr:`aioxmpp.Message.subject`,
  * :attr:`aioxmpp.Message.body`,
  * :attr:`aioxmpp.Presence.status`,
  * :attr:`aioxmpp.disco.xso.InfoQuery.features`,
  * and possibly others.

* Several stability improvements have been made. A race condition during stream
  management resumption was fixed and :class:`aioxmpp.node.AbstractClient`
  instances now stop if non-:class:`OSError` exceptions emerge from the
  stream (as these usually indicate an implementation or user error).

  :class:`aioxmpp.callbacks.AdHocSignal` now provides full exception
  isolation.

* Support for capturing the raw XML events used for creating
  :class:`aioxmpp.xso.XSO` instances from SAX is now provided through
  :class:`aioxmpp.xso.CapturingXSO`. Helper functions to work with these events
  are also provided, most notably :func:`aioxmpp.xso.events_to_sax`, which can
  be used to re-create the original XML from those events.

  The main use case is to be able to write out a transcript of received XML
  data, independent of XSO-level understanding for the data received, provided
  the parts which are understood are semantically correct (transcripts will be
  incomplete if parsing fails due to incorrect contents).

  .. autosummary::

     ~aioxmpp.xso.CapturingXSO
     ~aioxmpp.xso.capture_events
     ~aioxmpp.xso.events_to_sax

  This feature is already used in :class:`aioxmpp.disco.xso.InfoQuery`, which
  now inherits from :class:`~aioxmpp.xso.CapturingXSO` and provides its
  transcript (if available) at
  :attr:`~aioxmpp.disco.xso.InfoQuery.captured_events`.

* The core SASL implementation has been refactored in its own independent
  package, :mod:`aiosasl`. Only the XMPP specific parts reside in
  :mod:`aioxmpp.sasl` and :mod:`aioxmpp` now depends on :mod:`aiosasl`.

* :meth:`aioxmpp.stream.StanzaStream.register_message_callback` is more clearly
  specified now, a bug in the documentation has been fixed.

* :mod:`aioxmpp.stream_xsos` is now called :mod:`aioxmpp.nonza`, in accordance
  with :xep:`0360`.

* :class:`aioxmpp.xso.Date` and :class:`aioxmpp.xso.Time` are now available to
  for :xep:`0082` use. In addition, support for the legacy date time format is
  now provided in :class:`aioxmpp.xso.DateTime`.

  .. autosummary::

     ~aioxmpp.xso.Date
     ~aioxmpp.xso.Time
     ~aioxmpp.xso.DateTime

* The Python 3.5 compatibility of the test suite has been improved. In a
  corner-case, :class:`StopIteration` was emitted from ``data_received``, which
  caused a test to fail with a :class:`RuntimeError` due to implementation of
  :pep:`0479` in Python 3.5. See the `issue at github
  <https://github.com/horazont/aioxmpp/issues/3>`_.

* Helper functions for reading and writing single XSOs (and their children) to
  binary file-like objects have been introduced.

  .. autosummary::

     ~aioxmpp.xml.write_single_xso
     ~aioxmpp.xml.read_xso
     ~aioxmpp.xml.read_single_xso

* In 0.5.4, :mod:`aioxmpp.network` was re-written. More details will follow in
  the 0.6 changelog. The takeaway is that the network stack now automatically
  reloads the DNS configuration after the first timeout, to accomodate to
  changing resolvers.

Version 0.4
===========

* Documentation change: A simple sphinx extension has been added which
  auto-detects coroutines and adds a directive to mark up signals.

  The latter has been added to relevant places and the former automatically
  improves the documentations quality.

* :class:`aioxmpp.roster.Service` now implements presence subscription
  management. To track the presence of peers, :mod:`aioxmpp.presence` has been
  added.

* :mod:`aioxmpp.stream` and :mod:`aioxmpp.nonza` are part of the public
  API now. :mod:`aioxmpp.nonza` has gained the XSOs for SASL (previously
  in :mod:`aioxmpp.sasl`) and StartTLS (previously in
  :mod:`aioxmpp.security_layer`).

* :class:`aioxmpp.xso.XSO` subclasses now support copying and deepcopying.

* :mod:`aioxmpp.protocol` has been moved into the internal API part.

* :class:`aioxmpp.Message` specification fixed to have
  ``"normal"`` as default for :attr:`~aioxmpp.Message.type_` and relax
  the unknown child policy.

* *Possibly breaking change*: :attr:`aioxmpp.xso.XSO.DECLARE_NS` is now
  automatically generated by the meta class
  :class:`aioxmpp.xso.model.XMLStreamClass`. See the documentation for the
  detailed rules.

  To get the old behaviour for your class, you have to put ``DECLARE_NS = {}``
  in its declaration.

* :class:`aioxmpp.stream.StanzaStream` has a positional, optional argument
  (`local_jid`) for ejabberd compatiblity.

* Several fixes and workarounds, finally providing ejabberd compatibility:

  * :class:`aioxmpp.nonza.StartTLS` declares its namespace
    prefixless. Otherwise, connections to some versions of ejabberd fail in a
    very humorous way: client says "I want to start TLS", server says "You have
    to use TLS" and closes the stream with a policy-violation stream error.

  * Most XSOs now declare their namespace prefixless, too.

  * Support for legacy (`RFC 3921`__) XMPP session negotiation implemented in
    :class:`aioxmpp.node.AbstractClient`. See :mod:`aioxmpp.rfc3921`.

    __ https://tools.ietf.org/html/rfc3921

  * :class:`aioxmpp.stream.StanzaStream` now supports incoming IQs with the
    bare JID of the local entity as sender, taking them as coming from the
    server.

* Allow pinning of certificates for which no issuer certificate is available,
  because it is missing in the server-provided chain and not available in the
  local certificate store. This is, with respect to trust, treated equivalent
  to a self-signed cert.

* Fix stream management state going out-of-sync when an erroneous stanza
  (unknown payload, type or validator errors on the payload) was received. In
  addition, IQ replies which cannot be processed raise
  :class:`aioxmpp.errors.ErroneousStanza` from
  :meth:`aioxmpp.stream.StanzaStream.send_iq_and_wait_for_reply` and when
  registering futures for the response using
  :meth:`aioxmpp.stream.StanzaStream.register_iq_response_future`. See the
  latter for details on the semantics.

* Fixed a bug in :class:`aioxmpp.xml.XMPPXMLGenerator` which would emit
  elements in the wrong namespace if the meaning of a XML namespace prefix was
  being changed at the same time an element was emitted using that namespace.

* The defaults for unknown child and attribute policies on
  :class:`aioxmpp.xso.XSO` are now ``DROP`` and not ``FAIL``. This is for
  better compatibility with old implementations and future features.

Version 0.3
===========

* **Breaking change**: The `required` keyword argument on most
  :mod:`aioxmpp.xso` descriptors has been removed. The semantics of the
  `default` keyword argument have been changed.

  Before 0.3, the XML elements represented by descriptors were not required by
  default and had to be marked as required e.g. by setting ``required=True`` in
  :class:`.xso.Attr` constructor.

  Since 0.3, the descriptors are generally required by default. However, the
  interface on how to change that is different. Attributes and text have a
  `default` keyword argument which may be set to a value (which may also be
  :data:`None`). In that case, that value indicates that the attribute or text
  is absent: it is used if the attribute or text is missing in the source XML
  and if the attribute or text is set to the `default` value, it will not be
  emitted in XML.

  Children do not support default values other than :data:`None`; thus, they
  are simply controlled by a boolean flag `required` which needs to be passed
  to the constructor.

* The class attributes :attr:`~aioxmpp.service.Meta.SERVICE_BEFORE` and
  :attr:`~aioxmpp.service.Meta.SERVICE_AFTER` have been
  renamed to :attr:`~aioxmpp.service.Meta.ORDER_BEFORE` and
  :attr:`~aioxmpp.service.Meta.ORDER_AFTER` respectively.

  The :class:`aioxmpp.service.Service` class has additional support to handle
  the old attributes, but will emit a DeprecationWarning if they are used on a
  class declaration.

  See :attr:`aioxmpp.service.Meta.SERVICE_AFTER` for more information on the
  deprecation cycle of these attributes.
