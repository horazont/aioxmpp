########################################################################
# File name: service.py
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
import asyncio
import numbers

import aioxmpp.callbacks
import aioxmpp.service
import aioxmpp.structs
import aioxmpp.xso.model


class PresenceClient(aioxmpp.service.Service):
    """
    The presence service tracks all incoming presence information (this does
    not include subscription management stanzas, as these are handled by
    :mod:`aioxmpp.roster`). It is independent of the roster, as directed
    presence is independent of the roster and still needs to be tracked
    accordingly.

    No method to send directed presence is provided; it would basically just
    take a stanza and enqueue it in the clients stream, thus being a mere
    wrapper around :meth:`~.Client.send`, without any benefit.

    The service provides access to presence information summarized by bare JID
    or for each full JID individually. An index over the resources of a bare
    JID is available.

    If an error presence is received for a JID, it replaces all known presence
    information. It is returned for all queries, no matter for which resource
    the query is. As soon as a non-error presence is received for any resource
    of the bare JID, the error is cleared.

    .. automethod:: get_most_available_stanza

    .. automethod:: get_peer_resources

    .. automethod:: get_stanza

    On presence changes of peers, signals are emitted:

    .. signal:: on_bare_available(stanza)

       Fires when the first resource of a peer becomes available.

    .. signal:: on_bare_unavailable(stanza)

       Fires when the last resource of a peer becomes unavailable or enters
       error state.

    .. signal:: on_available(full_jid, stanza)

       Fires when a resource becomes available at `full_jid`. The `stanza`
       which caused the availability is handed over as second argument.

       This signal always fires after :meth:`on_bare_available`.

    .. signal:: on_changed(full_jid, stanza)

       Fires when a the presence of the resource at `full_jid` changes, but
       does not become unavailable or available. The `stanza` which caused the
       change is handed over as second argument.

    .. signal:: on_unavailable(full_jid, stanza)

       Fires when the resource at `full_jid` becomes unavailable, with the
       `stanza` causing the unavailability as second argument.

       This signal always fires before :meth:`on_bare_unavailable`.

       .. note::

          If the resource became unavailable due to an error, the `full_jid`
          will not match the :attr:`~.stanza.StanzaBase.from_` attribute of the
          `stanza`, as the error is coming from the bare JID.

    The three signals :meth:`on_available`,  :meth:`on_changed` and
    :meth:`on_unavailable` never fire for the same stanza.

    .. versionadded:: 0.4

    .. versionchanged:: 0.8

       This class was formerly known as :class:`aioxmpp.presence.Service`. It
       is still available under that name, but the alias will be removed in
       1.0.
    """

    ORDER_AFTER = [
        aioxmpp.dispatcher.SimplePresenceDispatcher,
    ]

    on_bare_available = aioxmpp.callbacks.Signal()
    on_bare_unavailable = aioxmpp.callbacks.Signal()

    on_available = aioxmpp.callbacks.Signal()
    on_changed = aioxmpp.callbacks.Signal()
    on_unavailable = aioxmpp.callbacks.Signal()

    def __init__(self, client, **kwargs):
        super().__init__(client, **kwargs)

        self._presences = {}

    def get_most_available_stanza(self, peer_jid):
        """
        Obtain the stanza describing the most-available presence of the
        contact.

        :param peer_jid: Bare JID of the contact.
        :type peer_jid: :class:`aioxmpp.JID`
        :rtype: :class:`aioxmpp.Presence` or :data:`None`
        :return: The presence stanza of the most available resource or
                 :data:`None` if there is no available resource.

        The "most available" resource is the one whose presence state orderest
        highest according to :class:`~aioxmpp.PresenceState`.

        If there is no available resource for a given `peer_jid`, :data:`None`
        is returned.
        """
        presences = sorted(
            self.get_peer_resources(peer_jid).items(),
            key=lambda item: aioxmpp.structs.PresenceState.from_stanza(item[1])
        )
        if not presences:
            return None
        return presences[-1][1]

    def get_peer_resources(self, peer_jid):
        """
        Return a dict mapping resources of the given bare `peer_jid` to the
        presence state last received for that resource.

        Unavailable presence states are not included. If the bare JID is in a
        error state (i.e. an error presence stanza has been received), the
        returned mapping is empty.
        """
        try:
            d = dict(self._presences[peer_jid])
            d.pop(None, None)
            return d
        except KeyError:
            return {}

    def get_stanza(self, peer_jid):
        """
        Return the last presence recieved for the given bare or full
        `peer_jid`. If the last presence was unavailable, the return value is
        :data:`None`, as if no presence was ever received.

        If no presence was ever received for the given bare JID, :data:`None`
        is returned.
        """
        try:
            return self._presences[peer_jid.bare()][peer_jid.resource]
        except KeyError:
            pass
        try:
            return self._presences[peer_jid.bare()][None]
        except KeyError:
            pass

    @aioxmpp.dispatcher.presence_handler(
        aioxmpp.structs.PresenceType.AVAILABLE,
        None)
    @aioxmpp.dispatcher.presence_handler(
        aioxmpp.structs.PresenceType.UNAVAILABLE,
        None)
    @aioxmpp.dispatcher.presence_handler(
        aioxmpp.structs.PresenceType.ERROR,
        None)
    def handle_presence(self, st):
        if st.from_ is None:
            if st.type_ != aioxmpp.structs.PresenceType.ERROR:
                self.logger.debug(
                    "dropping unhandled presence from account"
                )
            return

        bare = st.from_.bare()
        resource = st.from_.resource

        if st.type_ == aioxmpp.structs.PresenceType.UNAVAILABLE:
            try:
                dest_dict = self._presences[bare]
            except KeyError:
                return
            dest_dict.pop(None, None)
            if resource in dest_dict:
                self.on_unavailable(st.from_, st)
                if len(dest_dict) == 1:
                    self.on_bare_unavailable(st)
                del dest_dict[resource]
        elif st.type_ == aioxmpp.structs.PresenceType.ERROR:
            try:
                dest_dict = self._presences[bare]
            except KeyError:
                pass
            else:
                for resource in dest_dict.keys():
                    self.on_unavailable(st.from_.replace(resource=resource),
                                        st)
                self.on_bare_unavailable(st)
            self._presences[bare] = {None: st}
        else:
            dest_dict = self._presences.setdefault(bare, {})
            dest_dict.pop(None, None)
            bare_became_available = not dest_dict
            resource_became_available = resource not in dest_dict
            dest_dict[resource] = st

            if bare_became_available:
                self.on_bare_available(st)
            if resource_became_available:
                self.on_available(st.from_, st)
            else:
                self.on_changed(st.from_, st)


class DirectedPresenceHandle:
    """
    Represent a directed presence relationship with a peer.

    Directed Presence is specified in :rfc:`6121` section 4.6. Since the users
    server is not responsible for distributing presence updates to peers to
    which the client has sent directed presence, special handling is needed.
    (The only presence automatically sent by a client’s server to a peer which
    has received directed presence is the
    :attr:`~aioxmpp.PresenceType.UNAVAILABLE` presence which is created when
    the client disconnects.)

        .. note::

            Directed presence relationships get
            :meth:`unsubscribed <unsubscribe>` immediately when the stream is
            destroyed. This is because the peer has received
            :attr:`~aioxmpp.PresenceType.UNAVAILABLE` presence from the client’s
            server.

    .. autoattribute:: address

    .. autoattribute:: muted

    .. autoattribute:: presence_filter

    .. automethod:: set_muted

    .. automethod:: unsubscribe

    .. automethod:: send_presence
    """

    @property
    def address(self) -> aioxmpp.JID:
        """
        The address of the peer. This attribute is read-only.

        To change the address of a peer,
        :meth:`aioxmpp.PresenceServer.rebind_directed_presence` can be used.
        """

    @property
    def muted(self) -> bool:
        """
        Flag to indicate whether the directed presence relationship is *muted*.

        If the relationship is **not** muted, presence updates made through the
        :class:`PresenceServer` will be unicast to the peer entity of the
        relationship.

        For a muted relationships, presence updates will *not* be automatically
        sent to the peer.

        The *muted* behaviour is useful if presence updates need to be managed
        by a service for some reason.

        This attribute is read-only. It must be modified through
        :meth:`set_muted`.
        """

    @property
    def presence_filter(self):
        """
        Optional callback which is invoked on the presence stanza before it is
        sent.

        This is called whenever a presence stanza is sent for this relationship
        by the :class:`PresenceServer`. This is not invoked for presence stanzas
        sent to the peer by other means (e.g. :meth:`aioxmpp.Client.send`).

        If the :attr:`presence_filter` is not :data:`None`, it is called with
        the presence stanza as its only argument. It must either return the
        presence stanza, or :data:`None`. If it returns :data:`None`, the
        presence stanza is not sent.

        The callback operates on a copy of the presence stanza to prevent
        modifications from leaking into other presence relationships; making a
        copy inside the callback is not required or recommended.
        """

    @presence_filter.setter
    def presence_filter(self, new_callback):
        pass

    def set_muted(self, muted, *, send_update_now=True):
        """
        Change the :attr:`muted` state of the relationship.

        (This is not a setter to the property due to the additional options
        which are available when changing the :attr:`muted` state.)

        :param muted: The new muted state.
        :type muted: :class:`bool`
        :param send_update_now: Whether to send a presence update to the peer
            immediately.
        :type send_update_now: :class:`bool`
        :raises RuntimeError: if the presence relationship has been destroyed
            with :meth:`unsubscribe`

        If `muted` is equal to :attr:`muted`, this method does nothing.

        If `muted` is :data:`True`, the presence relationship will be muted.
        `send_update_now` is ignored.

        If `muted` is :data:`False`, the presence relationship will be unmuted.
        If `send_update_now` is :data:`True`, the current presence is sent to
        the peer immediately.
        """

    def unsubscribe(self):
        """
        Destroy the directed presence relationship.

        The presence relationship becomes useless afterwards. Any additional
        calls to the methods will result in :class:`RuntimeError`. No additional
        updates wil be sent to the peer automatically (except, of course, if
        a new relationship is created).

        If the presence relationship is still active when the method is called,
        :attr:`~aioxmpp.PresenceType.UNAVAILABLE` presence is sent to the peer
        immediately. Otherwise, no stanza is sent. The stanza is passed through
        the :attr:`presence_filter`.

        .. note::

            Directed presence relationships get unsubscribed immediately when
            the stream is destroyed. This is because the peer has received
            :attr:`~aioxmpp.PresenceType.UNAVAILABLE` presence from the client’s
            server.

        This operation is idempotent.
        """

    def send_presence(self, stanza: aioxmpp.Presence):
        """
        Send a presence stanza to the peer.

        :param stanza: The stanza to send.
        :type stanza: :class:`aioxmpp.Presence`
        :raises RuntimeError: if the presence relationship has been destroyed
            with :meth:`unsubscribe`

        The type of the presence `stanza` must be either
        :attr:`aioxmpp.PresenceType.AVAILABLE` or
        :attr:`aioxmpp.PresenceType.UNAVAILABLE`.

        The :meth:`presence_filter` is not invoked on this `stanza`; it is
        assumed that the owner of the relationship takes care of setting the
        `stanza` up in the way it is needed.
        """


class PresenceServer(aioxmpp.service.Service):
    """
    Manage the presence broadcast by the client.

    .. .. note::

    ..    This was formerly handled by the :class:`aioxmpp.PresenceManagedClient`,
    ..    which is now merely a shim wrapper around :class:`aioxmpp.Client` and
    ..    :class:`PresenceServer`.

    The :class:`PresenceServer` manages broadcasting and re-broadcasting the
    presence of the client as needed.

    The presence state is initialised to an unavailable presence. Unavailable
    presences are not emitted when the stream is established.

    Presence information:

    .. autoattribute:: state

    .. autoattribute:: status

    .. autoattribute:: priority

    .. automethod:: make_stanza

    Changing/sending/watching presence:

    .. automethod:: set_presence

    .. automethod:: resend_presence

    .. signal:: on_presence_changed()

       Emits after the presence has been changed in the
       :class:`PresenceServer`.

    .. signal:: on_presence_state_changed(new_state)

       Emits after the presence *state* has been changed in the
       :class:`PresenceServer`.

       This signal does not emit if other parts of the presence (such as
       priority or status texts) change, while the presence state itself stays
       the same.

    .. versionadded:: 0.8
    """

    on_presence_changed = aioxmpp.callbacks.Signal()
    on_presence_state_changed = aioxmpp.callbacks.Signal()

    def __init__(self, client, **kwargs):
        super().__init__(client, **kwargs)
        self._state = aioxmpp.PresenceState(False)
        self._status = {}
        self._priority = 0

        client.before_stream_established.connect(
            self._before_stream_established
        )

    @asyncio.coroutine
    def _before_stream_established(self):
        if not self._state.available:
            return True

        yield from self.client.send(self.make_stanza())

        return True

    @property
    def state(self):
        """
        The currently set presence state (as :class:`aioxmpp.PresenceState`)
        which is broadcast when the client connects and when the presence is
        re-emitted.

        This attribute cannot be written. It does not reflect the actual
        presence seen by others. For example when the client is in fact
        offline, others will see unavailable presence no matter what is set
        here.
        """
        return self._state

    @property
    def status(self):
        """
        The currently set textual presence status which is broadcast when the
        client connects and when the presence is re-emitted.

        This attribute cannot be written. It does not reflect the actual
        presence seen by others. For example when the client is in fact
        offline, others will see unavailable presence no matter what is set
        here.
        """
        return self._status

    @property
    def priority(self):
        """
        The currently set priority which is broadcast when the client connects
        and when the presence is re-emitted.

        This attribute cannot be written. It does not reflect the actual
        presence seen by others. For example when the client is in fact
        offline, others will see unavailable presence no matter what is set
        here.
        """
        return self._priority

    def make_stanza(self):
        """
        Create and return a presence stanza with the current settings.

        :return: Presence stanza
        :rtype: :class:`aioxmpp.Presence`
        """
        stanza = aioxmpp.Presence()
        self._state.apply_to_stanza(stanza)
        stanza.status.update(self._status)
        return stanza

    def set_presence(self, state, status={}, priority=0):
        """
        Change the presence broadcast by the client.

        :param state: New presence state to broadcast
        :type state: :class:`aioxmpp.PresenceState`
        :param status: New status information to broadcast
        :type status: :class:`dict` or :class:`str`
        :param priority: New priority for the resource
        :type priority: :class:`int`
        :return: Stanza token of the presence stanza or :data:`None` if the
                 presence is unchanged or the stream is not connected.
        :rtype: :class:`~.stream.StanzaToken`

        If the client is currently connected, the new presence is broadcast
        immediately.

        `status` must be either a string or something which can be passed to
        the :class:`dict` constructor. If it is a string, it is wrapped into a
        dict using ``{None: status}``. The mapping must map
        :class:`~.LanguageTag` objects (or :data:`None`) to strings. The
        information will be used to generate internationalised presence status
        information. If you do not need internationalisation, simply use the
        string version of the argument.
        """

        if not isinstance(priority, numbers.Integral):
            raise TypeError(
                "invalid priority: got {}, expected integer".format(
                    type(priority)
                )
            )

        if not isinstance(state, aioxmpp.PresenceState):
            raise TypeError(
                "invalid state: got {}, expected aioxmpp.PresenceState".format(
                    type(state),
                )
            )

        if isinstance(status, str):
            new_status = {None: status}
        else:
            new_status = dict(status)
        new_priority = int(priority)

        emit_state_event = self._state != state
        emit_overall_event = (
            emit_state_event or
            self._priority != new_priority or
            self._status != new_status
        )

        self._state = state
        self._status = new_status
        self._priority = new_priority

        if emit_state_event:
            self.on_presence_state_changed()
        if emit_overall_event:
            self.on_presence_changed()
            return self.resend_presence()

    def resend_presence(self):
        """
        Re-send the currently configured presence.

        :return: Stanza token of the presence stanza or :data:`None` if the
                 stream is not established.
        :rtype: :class:`~.stream.StanzaToken`

        .. note::

           :meth:`set_presence` automatically broadcasts the new presence if
           any of the parameters changed.
        """

        if self.client.established:
            return self.client.enqueue(self.make_stanza())

    def subscribe_peer_directed(self,
                                peer: aioxmpp.JID,
                                muted: bool = False):
        """
        Create a directed presence relationship with a peer.

        :param peer: The address of the peer. This can be a full or bare JID.
        :type peer: :class:`aioxmpp.JID`
        :param muted: Flag to create the relationship in muted state.
        :type muted: :class:`bool`
        :rtype: :class:`DirectedPresenceHandle`
        :return: The new directed presence handle.

        `peer` is the address of the peer which is going to receive directed
        presence. For each bare JID, there can only exist either a single bare
        JID directed presence relationship, or zero or more full JID directed
        presence relationships. It is not possible to have a bare JID directed
        presence relationship and a full JID directed presence relationship for
        the same bare JID.

        If `muted` is :data:`False` (the default), the current presence is
        unicast to `peer` when the relationship is created and the relationship
        is created with :attr:`~.DirectedPresenceHandle.muted` set to
        :data:`False`.

        If `muted` is :data:`True`, no presence is sent when the relationship is
        created, and it is created with :attr:`~.DirectedPresenceHandle.muted`
        set to :data:`True`.

        If the user of this method needs to set a
        :attr:`~.DirectedPresenceHandle.presence_filter` on the relationship,
        creating it with `muted` set to true is the only way to achieve this
        before the initial directed presence to the peer is sent.

        The newly created handle is returned.
        """

    def rebind_directed_presence(self,
                                 relationship: DirectedPresenceHandle,
                                 new_peer: aioxmpp.JID):
        """
        Modify the peer of an existing directed presence relationship.

        :param relationship: The relationship to operate on.
        :type relationship: :class:`DirectedPresenceHandle`
        :param new_peer: The new destination address of the relationship.
        :type new_peer: :class:`aioxmpp.JID`
        :raises RuntimeError: if the `relationship` has been destroyed with
            :meth:`~DirectedPresenceHandle.unsubscribe` already.
        :raises ValueError: if another relationship for `new_peer` exists and
            is active

        This changes the peer :attr:`~.DirectedPresenceHandle.address` of the
        `relationship` to `new_peer`. The conditions for peer addresses of
        directed presence relationships as described in
        :meth:`subscribe_peer_directed` are enforced in this operation. If they
        are violated, :class:`ValueError` is raised.

        If the `relationship` has already been closed/destroyed using
        :meth:`~DirectedPresenceHandle.unsubscribe`, :class:`RuntimeError` is
        raised.
        """
