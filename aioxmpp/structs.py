########################################################################
# File name: structs.py
# This file is part of: aioxmpp
#
# LICENSE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this program.  If not, see
# <http://www.gnu.org/licenses/>.
#
########################################################################
"""
:mod:`~aioxmpp.structs` --- Simple data holders for common data types
#####################################################################

These classes provide a way to hold structured data which is commonly
encountered in the XMPP realm.

Stanza types
============

.. currentmodule:: aioxmpp

.. autoclass:: IQType

.. autoclass:: MessageType

.. autoclass:: PresenceType

.. autoclass:: ErrorType

Jabber IDs
==========

.. autoclass:: JID(localpart, domain, resource)

.. autofunction:: jid_escape

.. autofunction:: jid_unescape

Presence
========

.. autoclass:: PresenceShow

.. autoclass:: PresenceState

.. currentmodule:: aioxmpp.structs

Languages
=========

.. autoclass:: LanguageTag

.. autoclass:: LanguageRange

.. autoclass:: LanguageMap

Functions for working with language tags
----------------------------------------

.. autofunction:: basic_filter_languages

.. autofunction:: lookup_language

"""

import collections
import enum
import functools
import warnings

from .stringprep import nodeprep, resourceprep, nameprep


_USE_COMPAT_ENUM = True


class CompatibilityMixin:
    def __hash__(self):
        return hash(self.value)

    def __eq__(self, other):
        if not _USE_COMPAT_ENUM:
            return super().__eq__(other)

        if super().__eq__(other) is True:
            return True
        if self.value == other:
            warnings.warn(
                "as of aioxmpp 1.0, {} members will not compare equal to "
                "their values".format(type(self).__name__),
                DeprecationWarning,
                stacklevel=2,
            )
            return True
        return False


class ErrorType(CompatibilityMixin, enum.Enum):
    """
    Enumeration for the :rfc:`6120` specified stanza error types.

    These error types reflect are actually more reflecting the error classes,
    but the attribute is called "type" nonetheless. For consistency, we are
    calling it "type" here, too.

    The following types are specified. The quotations in the member
    descriptions are from :rfc:`6120`, Section 8.3.2.

    .. attribute:: AUTH

       The ``"auth"`` error type:

          retry after providing credentials

       When converted to an exception, it uses :exc:`~.XMPPAuthError`.

    .. attribute:: CANCEL

       The ``"cancel"`` error type:

          do not retry (the error cannot be remedied)

       When converted to an exception, it uses :exc:`~.XMPPCancelError`.

    .. attribute:: CONTINUE

       The ``"continue"`` error type:

          proceed (the condition was only a warning)

       When converted to an exception, it uses
       :exc:`~.XMPPContinueError`.

    .. attribute:: MODIFY

       The ``"modify"`` error type:

          retry after changing the data sent

       When converted to an exception, it uses
       :exc:`~.XMPPModifyError`.

    .. attribute:: WAIT

       The ``"wait"`` error type:

          retry after waiting (the error is temporary)

       When converted to an exception, it uses (guess what)
       :exc:`~.XMPPWaitError`.

    :class:`ErrorType` members compare and hash equal to their values. For
    example::

      assert ErrorType.CANCEL == "cancel"
      assert "cancel" == ErrorType.CANCEL
      assert hash(ErrorType.CANCEL) == hash("cancel")

    .. deprecated:: 0.7

       This behaviour will cease with aioxmpp 1.0, and the first assertion will
       fail, the second may fail.

       Please see the Changelog for :ref:`api-changelog-0.7` for further
       details on how to upgrade your code efficiently.

    """

    AUTH = "auth"
    CANCEL = "cancel"
    CONTINUE = "continue"
    MODIFY = "modify"
    WAIT = "wait"


class MessageType(CompatibilityMixin, enum.Enum):
    """
    Enumeration for the :rfc:`6121` specified Message stanza types.

    .. seealso::

       :attr:`~.Message.type_`
          Type attribute of Message stanzas.


    Each member has the following meta-information:

    .. autoattribute:: is_error

    .. autoattribute:: is_request

    .. autoattribute:: is_response

    .. note::

       The :attr:`is_error`, :attr:`is_request` and :attr:`is_response`
       meta-information attributes share semantics across :class:`MessageType`,
       :class:`PresenceType` and :class:`IQType`. You are encouraged to exploit
       this in full duck-typing manner in generic stanza handling code.

    The following types are specified. The quotations in the member
    descriptions are from :rfc:`6121`, Section 5.2.2.

    .. attribute:: NORMAL

       The ``"normal"`` Message type:

          The message is a standalone message that is sent outside the context
          of a one-to-one conversation or groupchat, and to which it is
          expected that the recipient will reply.  Typically a receiving client
          will present a message of type "normal" in an interface that enables
          the recipient to reply, but without a conversation history.  The
          default value of the 'type' attribute is "normal".

       Think of it as somewhat similar to "E-Mail via XMPP".

    .. attribute:: CHAT

       The ``"chat"`` Message type:

          The message is sent in the context of a one-to-one chat session.
          Typically an interactive client will present a message of type "chat"
          in an interface that enables one-to-one chat between the two parties,
          including an appropriate conversation history.

    .. attribute:: GROUPCHAT

       The ``"groupchat"`` Message type:

          The message is sent in the context of a multi-user chat environment
          […].  Typically a receiving client will present a message of type
          "groupchat" in an interface that enables many-to-many chat between
          the parties, including a roster of parties in the chatroom and an
          appropriate conversation history.

    .. attribute:: HEADLINE

       The ``"headline"`` Message type:

          The message provides an alert, a notification, or other transient
          information to which no reply is expected (e.g., news headlines,
          sports updates, near-real-time market data, or syndicated content).
          Because no reply to the message is expected, typically a receiving
          client will present a message of type "headline" in an interface that
          appropriately differentiates the message from standalone messages,
          chat messages, and groupchat messages (e.g., by not providing the
          recipient with the ability to reply).

       Do not confuse this message type with the
       :attr:`~.Message.subject` member of Messages!

    .. attribute:: ERROR

       The ``"error"`` Message type:

          The message is generated by an entity that experiences an error when
          processing a message received from another entity […].  A client that
          receives a message of type "error" SHOULD present an appropriate
          interface informing the original sender regarding the nature of the
          error.

       This is the only message type which is used in direct response to
       another message, in the sense that the Stanza ID is preserved in the
       response.

    :class:`MessageType` members compare and hash equal to their values. For
    example::

      assert MessageType.CHAT == "chat"
      assert "chat" == MessageType.CHAT
      assert hash(MessageType.CHAT) == hash("chat")

    .. deprecated:: 0.7

       This behaviour will cease with aioxmpp 1.0, and the first assertion will
       fail, the second may fail.

       Please see the Changelog for :ref:`api-changelog-0.7` for further
       details on how to upgrade your code efficiently.

    """

    NORMAL = "normal"
    CHAT = "chat"
    GROUPCHAT = "groupchat"
    HEADLINE = "headline"
    ERROR = "error"

    @property
    def is_error(self):
        """
        True for the :attr:`ERROR` type, false for all others.
        """
        return self == MessageType.ERROR

    @property
    def is_response(self):
        """
        True for the :attr:`ERROR` type, false for all others.

        This is intended. Request/Response semantics do not really apply for
        messages, except that errors are generally in response to other
        messages.
        """
        return self == MessageType.ERROR

    @property
    def is_request(self):
        """
        False. See :attr:`is_response`.
        """
        return False


class PresenceType(CompatibilityMixin, enum.Enum):
    """
    Enumeration for the :rfc:`6121` specified Presence stanza types.

    .. seealso::

       :attr:`~.Presence.type_`
          Type attribute of Presence stanzas.

    Each member has the following meta-information:

    .. autoattribute:: is_error

    .. autoattribute:: is_request

    .. autoattribute:: is_response

    .. autoattribute:: is_presence_state

    .. note::

       The :attr:`is_error`, :attr:`is_request` and :attr:`is_response`
       meta-information attributes share semantics across :class:`MessageType`,
       :class:`PresenceType` and :class:`IQType`. You are encouraged to exploit
       this in full duck-typing manner in generic stanza handling code.


    The following types are specified. The quotes in the member descriptions
    are from :rfc:`6121`, Section 4.7.1.

    .. attribute:: ERROR

       The ``"error"`` Presence type:

          An error has occurred regarding processing of a previously sent
          presence stanza; if the presence stanza is of type "error", it MUST
          include an <error/> child element […].

       This is the only presence stanza type which is used in direct response
       to another presence stanza, in the sense that the Stanza ID is preserved
       in the response.

       In addition, :attr:`ERROR` presence stanzas may be seen during presence
       broadcast if inter-server communication fails.

    .. attribute:: PROBE

       The ``"probe"`` Presence type:

          A request for an entity's current presence; SHOULD be generated only
          by a server on behalf of a user.

       This should not be seen in client code.

    .. attribute:: SUBSCRIBE

       The ``"subscribe"`` Presence type:

          The sender wishes to subscribe to the recipient's presence.

    .. attribute:: SUBSCRIBED

       The ``"subscribed"`` Presence type:

          The sender has allowed the recipient to receive their presence.

    .. attribute:: UNSUBSCRIBE

       The ``"unsubscribe"`` Presence type:

          The sender is unsubscribing from the receiver's presence.

    .. attribute:: UNSUBSCRIBED

       The ``"unsubscribed"`` Presence type:

          The subscription request has been denied or a previously granted
          subscription has been canceled.

    .. attribute:: AVAILABLE

       The Presence type signalled with an absent type attribute:

          The absence of a 'type' attribute signals that the relevant entity is
          available for communication […].

    .. attribute:: UNAVAILABLE

       The ``"unavailable"`` Presence type:

          The sender is no longer available for communication.

    :class:`PresenceType` members compare and hash equal to their values. For
    example::

      assert PresenceType.PROBE == "probe"
      assert "probe" == PresenceType.PROBE
      assert hash(PresenceType.PROBE) == hash("probe")

    .. deprecated:: 0.7

       This behaviour will cease with aioxmpp 1.0, and the first assertion will
       fail, the second may fail.

       Please see the Changelog for :ref:`api-changelog-0.7` for further
       details on how to upgrade your code efficiently.
    """

    ERROR = "error"
    PROBE = "probe"
    SUBSCRIBE = "subscribe"
    SUBSCRIBED = "subscribed"
    UNAVAILABLE = "unavailable"
    UNSUBSCRIBE = "unsubscribe"
    UNSUBSCRIBED = "unsubscribed"
    AVAILABLE = None

    @property
    def is_error(self):
        """
        True for the :attr:`ERROR` type, false otherwise.
        """
        return self == PresenceType.ERROR

    @property
    def is_response(self):
        """
        True for the :attr:`ERROR` type, false otherwise.

        This is intended. Request/Response semantics do not really apply for
        presence stanzas, except that errors are generally in response to other
        presence stanzas.
        """
        return self == PresenceType.ERROR

    @property
    def is_request(self):
        """
        False. See :attr:`is_response`.
        """
        return False

    @property
    def is_presence_state(self):
        """
        True for the :attr:`AVAILABLE` and :attr:`UNAVAILABLE` types, false
        otherwise.

        Useful to discern presence state notifications from meta-stanzas
        regarding presence broadcast control.
        """
        return (self == PresenceType.AVAILABLE or
                self == PresenceType.UNAVAILABLE)


class IQType(CompatibilityMixin, enum.Enum):
    """
    Enumeration for the :rfc:`6120` specified IQ stanza types.

    .. seealso::

       :attr:`~.IQ.type_`
          Type attribute of IQ stanzas.

    Each member has the following meta-information:

    .. autoattribute:: is_error

    .. autoattribute:: is_request

    .. autoattribute:: is_response

    .. note::

       The :attr:`is_error`, :attr:`is_request` and :attr:`is_response`
       meta-information attributes share semantics across :class:`MessageType`,
       :class:`PresenceType` and :class:`IQType`. You are encouraged to exploit
       this in full duck-typing manner in generic stanza handling code.

    The following types are specified. The quotations in the member
    descriptions are from :rfc:`6120`, Section 8.2.3.

    .. attribute:: GET

       The ``"get"`` IQ type:

           The stanza requests information, inquires about what
           data is needed in order to complete further operations, etc.

       A :attr:`GET` IQ must contain a payload, via the
       :attr:`~.IQ.payload` attribute.

    .. attribute:: SET

       The ``"set"`` IQ type:

           The stanza provides data that is needed for an operation to be
           completed, sets new values, replaces existing values, etc.

       A :attr:`SET` IQ must contain a payload, via the
       :attr:`~.IQ.payload` attribute.

    .. attribute:: ERROR

       The ``"error"`` IQ type:

           The stanza reports an error that has occurred regarding processing
           or delivery of a get or set request[…].

       :class:`~.IQ` objects carrying the :attr:`ERROR` type usually
       have the :attr:`~.IQ.error` set to a :class:`~.stanza.Error`
       instance describing the details of the error.

       The :attr:`~.IQ.payload` attribute may also be set if the sender
       of the :attr:`ERROR` was kind enough to include the data which caused
       the problem.

    .. attribute:: RESULT

       The ``"result"`` IQ type:

           The stanza is a response to a successful get or set request.

       A :attr:`RESULT` IQ may contain a payload with more data.

    :class:`IQType` members compare and hash equal to their values. For
    example::

      assert IQType.GET == "get"
      assert "get" == IQType.GET
      assert hash(IQType.GET) == hash("get")

    .. deprecated:: 0.7

       This behaviour will cease with aioxmpp 1.0, and the first assertion will
       fail, the second may fail.

       Please see the Changelog for :ref:`api-changelog-0.7` for further
       details on how to upgrade your code efficiently.
    """

    GET = "get"
    SET = "set"
    ERROR = "error"
    RESULT = "result"

    @property
    def is_error(self):
        """
        True for the :attr:`ERROR` type, false otherwise.
        """
        return self == IQType.ERROR

    @property
    def is_request(self):
        """
        True for request types (:attr:`GET` and :attr:`SET`), false otherwise.
        """
        return self == IQType.GET or self == IQType.SET

    @property
    def is_response(self):
        """
        True for the response types (:attr:`RESULT` and :attr:`ERROR`), false
        otherwise.
        """
        return self == IQType.RESULT or self == IQType.ERROR


class JID(collections.namedtuple("JID", ["localpart", "domain", "resource"])):
    """
    Represent a :term:`Jabber ID (JID) <Jabber ID>`.

    To construct a :class:`JID`, either use the actual constructor, or use the
    :meth:`fromstr` class method.

    :param localpart: The part in front of the ``@`` of the JID, or
        :data:`None` if the localpart shall be omitted (which is different from
        it being empty, which would be invalid).
    :type localpart: :class:`str` or :data:`None`
    :param domain: The domain of the JID. This is the only mandatory part of
        a JID.
    :type domain: :class:`str`
    :param resource: The resource part of the JID or :data:`None` to omit the
        resource part.
    :type resource: :class:`str` or :data:`None`
    :param strict: Enable strict validation
    :type strict: :class:`bool`
    :raises ValueError: if the JID composed of the given parts is invalid

    Construct a JID out of its parts. It validates the parts individually, as
    well as the JID as a whole.

    If `strict` is false, unassigned codepoints are allowed in any of the parts
    of the JID. In the future, other deviations from the respective stringprep
    profiles may be allowed, too.

    The idea is to use non-`strict` when output is received from outside and
    when it is reflected, following the old principle "be conservative in what
    you send and liberal in what you receive". Otherwise, strict checking
    should be enabled. This brings maximum interoperability.

    .. automethod:: fromstr

    Information about a JID:

    .. attribute:: localpart

       The localpart, stringprep’d from the argument to the constructor.

    .. attribute:: domain

       The domain, stringprep’d from the argument to the constructor.

    .. attribute:: resource

       The resource, stringprep’d from the argument to the constructor.

    .. autoattribute:: is_bare

    .. autoattribute:: is_domain

    :class:`JID` objects are immutable. To obtain a JID object with a changed
    property, use one of the following methods:

    .. automethod:: bare

    .. automethod:: replace(*, [localpart], [domain], [resource])
    """

    __slots__ = []

    def __new__(cls, localpart, domain, resource, *, strict=True):
        if localpart:
            localpart = nodeprep(
                localpart,
                allow_unassigned=not strict
            )
        if domain is not None:
            domain = nameprep(
                domain,
                allow_unassigned=not strict
            )
        if resource:
            resource = resourceprep(
                resource,
                allow_unassigned=not strict
            )

        if not domain:
            raise ValueError("domain must not be empty or None")
        if len(domain.encode("utf-8")) > 1023:
            raise ValueError("domain too long")
        if localpart is not None:
            if not localpart:
                raise ValueError("localpart must not be empty")
            if len(localpart.encode("utf-8")) > 1023:
                raise ValueError("localpart too long")
        if resource is not None:
            if not resource:
                raise ValueError("resource must not be empty")
            if len(resource.encode("utf-8")) > 1023:
                raise ValueError("resource too long")

        return super().__new__(cls, localpart, domain, resource)

    def replace(self, **kwargs):
        """
        Construct a new :class:`JID` object, using the values of the current
        JID. Use the arguments to override specific attributes on the new
        object.

        All arguments are keyword arguments.

        :param localpart: Set the local part of the resulting JID.
        :param domain: Set the domain of the resulting JID.
        :param resource: Set the resource part of the resulting JID.
        :raises: See :class:`JID`
        :return: A new :class:`JID` object with the corresponding
            substitutions performed.
        :rtype: :class:`JID`

        The attributes of parameters which are omitted are not modified and
        copied down to the result.
        """

        new_kwargs = {}

        strict = kwargs.pop("strict", True)

        try:
            localpart = kwargs.pop("localpart")
        except KeyError:
            pass
        else:
            if localpart:
                localpart = nodeprep(
                    localpart,
                    allow_unassigned=not strict
                )
            new_kwargs["localpart"] = localpart

        try:
            domain = kwargs.pop("domain")
        except KeyError:
            pass
        else:
            if not domain:
                raise ValueError("domain must not be empty or None")
            new_kwargs["domain"] = nameprep(
                domain,
                allow_unassigned=not strict
            )

        try:
            resource = kwargs.pop("resource")
        except KeyError:
            pass
        else:
            if resource:
                resource = resourceprep(
                    resource,
                    allow_unassigned=not strict
                )
            new_kwargs["resource"] = resource

        if kwargs:
            raise TypeError("replace() got an unexpected keyword argument"
                            " {!r}".format(
                                next(iter(kwargs))))

        return super()._replace(**new_kwargs)

    def __str__(self):
        result = self.domain
        if self.localpart:
            result = self.localpart + "@" + result
        if self.resource:
            result += "/" + self.resource
        return result

    def bare(self):
        """
        Create a copy of the :class:`JID` which is bare.

        :return: This JID with the :attr:`resource` set to :data:`None`.
        :rtype: :class:`JID`

        Return the bare version of this JID as new :class:`JID` object.
        """
        return self.replace(resource=None)

    @property
    def is_bare(self):
        """
        :data:`True` if the JID is bare, i.e. has an empty :attr:`resource`
        part.
        """
        return not self.resource

    @property
    def is_domain(self):
        """
        :data:`True` if the JID is a domain, i.e. if both the :attr:`localpart`
        and the :attr:`resource` are empty.
        """
        return not self.resource and not self.localpart

    @classmethod
    def fromstr(cls, s, *, strict=True):
        """
        Construct a JID out of a string containing it.

        :param s: The string to parse.
        :type s: :class:`str`
        :param strict: Whether to enable strict parsing.
        :type strict: :class:`bool`
        :raises: See :class:`JID`
        :return: The parsed JID
        :rtype: :class:`JID`

        See the :class:`JID` class level documentation for the semantics of
        `strict`.
        """
        nodedomain, sep, resource = s.partition("/")
        if not sep:
            resource = None

        localpart, sep, domain = nodedomain.partition("@")
        if not sep:
            domain = localpart
            localpart = None
        return cls(localpart, domain, resource, strict=strict)


@functools.total_ordering
class PresenceShow(CompatibilityMixin, enum.Enum):
    """
    Enumeration to support the ``show`` element of presence stanzas.

    The enumeration members support total ordering. The order is defined by
    relevance and is the following (from lesser to greater): :attr:`XA`,
    :attr:`AWAY`, :attr:`NONE`, :attr:`CHAT`, :attr:`DND`. The order is
    intended to be used to extract the most relevant resource e.g. in a roster.

    .. versionadded:: 0.8

    .. attribute:: XA
       :annotation: = "xa"

       .. epigraph::

          The entity or resource is away for an extended period (xa = "eXtended
          Away").

          -- :rfc:`6121`, Section 4.7.2.1

    .. attribute:: EXTENDED_AWAY
       :annotation: = "xa"

       Alias to :attr:`XA`.

    .. attribute:: AWAY
       :annotation: = "away"

       .. epigraph::

          The entity or resource is temporarily away.

          -- :rfc:`6121`, Section 4.7.2.1

    .. attribute:: NONE
       :annotation: = None

       Signifies absence of the ``show`` element.

    .. attribute:: PLAIN
       :annotation: = None

       Alias to :attr:`NONE`.

    .. attribute:: CHAT
       :annotation: = "chat"

       .. epigraph::

          The entity or resource is actively interested in chatting.

          -- :rfc:`6121`, Section 4.7.2.1

    .. attribute:: FREE_FOR_CHAT
       :annotation: = "chat"

       Alias to :attr:`CHAT`.

    .. attribute:: DND
       :annotation: = "dnd"

       .. epigraph::

          The entity or resource is busy (dnd = "Do Not Disturb").

          -- :rfc:`6121`, Section 4.7.2.1

    .. attribute:: DO_NOT_DISTURB
       :annotation: = "dnd"

       Alias to :attr:`DND`.

    """
    XA = "xa"
    EXTENDED_AWAY = "xa"
    AWAY = "away"
    NONE = None
    PLAIN = None
    CHAT = "chat"
    FREE_FOR_CHAT = "chat"
    DND = "dnd"
    DO_NOT_DISTURB = "dnd"

    def __lt__(self, other):
        try:
            w1 = self._WEIGHTS[self]
            w2 = self._WEIGHTS[other]
        except KeyError:
            return NotImplemented
        return w1 < w2


PresenceShow._WEIGHTS = {
    PresenceShow.XA: -2,
    PresenceShow.AWAY: -1,
    PresenceShow.NONE: 0,
    PresenceShow.CHAT: 1,
    PresenceShow.DND: 2,
}


@functools.total_ordering
class PresenceState:
    """
    Hold a presence state of an XMPP resource, as defined by the presence
    stanza semantics.

    `available` must be a boolean value, which defines whether the resource is
    available or not. If the resource is available, `show` may be set to one of
    ``"dnd"``, ``"xa"``, ``"away"``, :data:`None`, ``"chat"`` (it is a
    :class:`ValueError` to attempt to set `show` to a non-:data:`None` value if
    `available` is false).

    :class:`PresenceState` objects are ordered by their availability and by
    their show values. Non-availability sorts lower than availability, and for
    available presence states the order is in the order of valid values given
    for the `show` above.

    .. attribute:: available

       As per the argument to the constructor, converted to a :class:`bool`.

    .. attribute:: show

       As per the argument to the constructor.

    .. automethod:: apply_to_stanza

    .. automethod:: from_stanza

    :class:`PresenceState` objects are immutable.

    """

    __slots__ = ["_available", "_show"]

    def __init__(self, available=False, show=PresenceShow.NONE):
        super().__init__()
        if not available and show != PresenceShow.NONE:
            raise ValueError("Unavailable state cannot have show value")
        if not isinstance(show, PresenceShow):
            try:
                show = PresenceShow(show)
            except ValueError:
                raise ValueError("Not a valid show value") from None
            else:
                warnings.warn(
                    "as of aioxmpp 1.0, the show argument must use "
                    "PresenceShow instead of str",
                    DeprecationWarning,
                    stacklevel=2
                )

        self._available = bool(available)
        self._show = show

    @property
    def available(self):
        return self._available

    @property
    def show(self):
        return self._show

    def __lt__(self, other):
        my_key = (self.available, self.show)
        try:
            other_key = (other.available, other.show)
        except AttributeError:
            return NotImplemented
        return my_key < other_key

    def __eq__(self, other):
        try:
            return (self.available == other.available and
                    self.show == other.show)
        except AttributeError:
            return NotImplemented

    def __repr__(self):
        more = ""
        if self.available:
            if self.show != PresenceShow.NONE:
                more = " available show={!r}".format(self.show)
            else:
                more = " available"
        return "<PresenceState{}>".format(more)

    def apply_to_stanza(self, stanza_obj):
        """
        Apply the properties of this :class:`PresenceState` to a
        :class:`~aioxmpp.Presence` `stanza_obj`. The
        :attr:`~aioxmpp.Presence.type_` and
        :attr:`~aioxmpp.Presence.show` attributes of the object will be
        modified to fit the values in this object.
        """
        if self.available:
            stanza_obj.type_ = PresenceType.AVAILABLE
        else:
            stanza_obj.type_ = PresenceType.UNAVAILABLE
        stanza_obj.show = self.show

    @classmethod
    def from_stanza(cls, stanza_obj, strict=False):
        """
        Create and return a new :class:`PresenceState` object which inherits
        the presence state as advertised in the given
        :class:`~aioxmpp.Presence` stanza.

        If `strict` is :data:`True`, the value of `show` is strictly checked,
        that is, it is required to be :data:`None` if the stanza indicates an
        unavailable state.

        The default is not to check this.
        """

        if not stanza_obj.type_.is_presence_state:
            raise ValueError("presence state stanza required")
        available = stanza_obj.type_ == PresenceType.AVAILABLE
        if not strict:
            show = stanza_obj.show if available else PresenceShow.NONE
        else:
            show = stanza_obj.show
        return cls(available=available, show=show)


@functools.total_ordering
class LanguageTag:
    """
    Implementation of a language tag. This may be a fully RFC5646 compliant
    implementation some day, but for now it is only very simplistic stub.

    There is no input validation of any kind.

    :class:`LanguageTag` instances compare and hash case-insensitively.

    .. automethod:: fromstr

    .. autoattribute:: match_str

    .. autoattribute:: print_str

    """

    __slots__ = ("_tag",)

    def __init__(self, *, tag=None):
        if not tag:
            raise ValueError("tag cannot be empty")

        self._tag = tag

    @property
    def match_str(self):
        """
        The string which is used for matching two language tags. This is the
        lower-cased version of the :attr:`print_str`.
        """
        return self._tag.lower()

    @property
    def print_str(self):
        """
        The stringified language tag.
        """
        return self._tag

    @classmethod
    def fromstr(cls, s):
        """
        Create a language tag from the given string `s`.

        .. note::

           This is a stub implementation which merely refers to the given
           string as the :attr:`print_str` and derives the :attr:`match_str`
           from that.

        """
        return cls(tag=s)

    def __str__(self):
        return self.print_str

    def __eq__(self, other):
        try:
            return self.match_str == other.match_str
        except AttributeError:
            return False

    def __lt__(self, other):
        try:
            return self.match_str < other.match_str
        except AttributeError:
            return NotImplemented

    def __le__(self, other):
        try:
            return self.match_str <= other.match_str
        except AttributeError:
            return NotImplemented

    def __hash__(self):
        return hash(self.match_str)

    def __repr__(self):
        return "<{}.{}.fromstr({!r})>".format(
            type(self).__module__,
            type(self).__qualname__,
            str(self))


class LanguageRange:
    """
    Implementation of a language range. This may be a fully RFC4647 compliant
    implementation some day, but for now it is only very simplistic stub.

    There is no input validation of any kind.

    :class:`LanguageRange` instances compare and hash case-insensitively.

    .. automethod:: fromstr

    .. automethod:: strip_rightmost

    .. autoattribute:: match_str

    .. autoattribute:: print_str

    """

    __slots__ = ("_tag",)

    def __init__(self, *, tag=None):
        if not tag:
            raise ValueError("range cannot be empty")

        self._tag = tag

    @property
    def match_str(self):
        """
        The string which is used for matching two language tags. This is the
        lower-cased version of the :attr:`print_str`.
        """
        return self._tag.lower()

    @property
    def print_str(self):
        """
        The stringified language tag.
        """
        return self._tag

    @classmethod
    def fromstr(cls, s):
        """
        Create a language tag from the given string `s`.

        .. note::

           This is a stub implementation which merely refers to the given
           string as the :attr:`print_str` and derives the :attr:`match_str`
           from that.

        """
        if s == "*":
            return cls.WILDCARD

        return cls(tag=s)

    def __str__(self):
        return self.print_str

    def __eq__(self, other):
        try:
            return self.match_str == other.match_str
        except AttributeError:
            return False

    def __hash__(self):
        return hash(self.match_str)

    def __repr__(self):
        return "<{}.{}.fromstr({!r})>".format(
            type(self).__module__,
            type(self).__qualname__,
            str(self))

    def strip_rightmost(self):
        """
        Strip the rightmost part of the language range. If the new rightmost
        part is a singleton or ``x`` (i.e. starts an extension or private use
        part), it is also stripped.

        Return the newly created :class:`LanguageRange`.
        """

        parts = self.print_str.split("-")
        parts.pop()
        if parts and len(parts[-1]) == 1:
            parts.pop()
        return type(self).fromstr("-".join(parts))


LanguageRange.WILDCARD = LanguageRange(tag="*")


def basic_filter_languages(languages, ranges):
    """
    Filter languages using the string-based basic filter algorithm described in
    RFC4647.

    `languages` must be a sequence of :class:`LanguageTag` instances which are
    to be filtered.

    `ranges` must be an iterable which represent the basic language ranges to
    filter with, in priority order. The language ranges must be given as
    :class:`LanguageRange` objects.

    Return an iterator of languages which matched any of the `ranges`. The
    sequence produced by the iterator is in match order and duplicate-free. The
    first range to match a language yields the language into the iterator, no
    other range can yield that language afterwards.
    """

    if LanguageRange.WILDCARD in ranges:
        yield from languages
        return

    found = set()

    for language_range in ranges:
        range_str = language_range.match_str
        for language in languages:
            if language in found:
                continue

            match_str = language.match_str
            if match_str == range_str:
                yield language
                found.add(language)
                continue

            if len(range_str) < len(match_str):
                if     (match_str[:len(range_str)] == range_str and
                        match_str[len(range_str)] == "-"):
                    yield language
                    found.add(language)
                    continue


def lookup_language(languages, ranges):
    """
    Look up a single language in the sequence `languages` using the lookup
    mechanism described in RFC4647. If no match is found, :data:`None` is
    returned. Otherwise, the first matching language is returned.

    `languages` must be a sequence of :class:`LanguageTag` objects, while
    `ranges` must be an iterable of :class:`LanguageRange` objects.
    """

    for language_range in ranges:
        while True:
            try:
                return next(iter(basic_filter_languages(
                    languages,
                    [language_range])))
            except StopIteration:
                pass

            try:
                language_range = language_range.strip_rightmost()
            except ValueError:
                break


class LanguageMap(dict):
    """
    A :class:`dict` subclass specialized for holding :class:`LanugageTag`
    instances as keys.

    In addition to the interface provided by :class:`dict`, instances of this
    class also have the following methods:

    .. automethod:: lookup

    .. automethod:: any
    """

    def lookup(self, language_ranges):
        """
        Perform an RFC4647 language range lookup on the keys in the
        dictionary. `language_ranges` must be a sequence of
        :class:`LanguageRange` instances.

        Return the entry in the dictionary with a key as produced by
        `lookup_language`. If `lookup_language` does not find a match and the
        mapping contains an entry with key :data:`None`, that entry is
        returned, otherwise :class:`KeyError` is raised.
        """
        keys = list(self.keys())
        try:
            keys.remove(None)
        except ValueError:
            pass
        keys.sort()
        key = lookup_language(keys, language_ranges)
        return self[key]

    def any(self):
        """
        Returns any element from the language map, preferring the :data:`None`
        key if it is available.

        Guarantees to always return the same element for a map with the same
        keys, even if the keys are iterated over in a different order.
        """
        if not self:
            raise ValueError("any() on empty map")

        try:
            return self[None]
        except KeyError:
            return self[min(self)]


# \ is treated specially because it is only escaped if followed by a valid
# escape sequence... that is so weird.
ESCAPABLE_CODEPOINTS = " \"&'/:<>@"


def jid_escape(s):
    """
    Return an escaped version of a string for use in a JID localpart.

    .. seealso::

        :func:`jid_unescape`
            for the reverse transformation

    :param s: The string to escape for use as localpart.
    :type s: :class:`str`
    :raise ValueError: If the string starts or ends with a space.
    :return: The escaped string.
    :rtype: :class:`str`

    .. note::

        JID Escaping does not allow embedding arbitrary characters in the
        localpart. Only a defined subset of characters can be escaped.
        Refer to :xep:`0106` for details.

    .. note::

        No validity check is made on the result. It is assumed that the
        result is passed to the :class:`JID` constructor, which will
        perform validity checks on its own.

    """

    # we first escape all backslashes which need to be escaped
    for cp in "\\" + ESCAPABLE_CODEPOINTS:
        seq = "\\{:02x}".format(ord(cp))
        s = s.replace(seq, "\\5c{:02x}".format(ord(cp)))

    # now we escape all the other stuff
    for cp in ESCAPABLE_CODEPOINTS:
        s = s.replace(cp, "\\{:02x}".format(ord(cp)))

    return s


def jid_unescape(localpart):
    """
    Un-escape a JID Escaped localpart.

    .. seealso::

        :func:`jid_escape`
            for the reverse transformation

    :param localpart: The escaped localpart
    :type localpart: :class:`str`
    :return: The unescaped localpart.
    :rtype: :class:`str`

    .. note::

        JID Escaping does not allow embedding arbitrary characters in the
        localpart. Only a defined subset of characters can be escaped.
        Refer to :xep:`0106` for details.
    """
    s = localpart

    for cp in ESCAPABLE_CODEPOINTS:
        s = s.replace("\\{:02x}".format(ord(cp)), cp)

    for cp in ESCAPABLE_CODEPOINTS + "\\":
        s = s.replace(
            "\\5c{:02x}".format(ord(cp)),
            "\\{:02x}".format(ord(cp)),
        )

    return s
