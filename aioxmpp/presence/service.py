import asyncio

import aioxmpp.callbacks
import aioxmpp.service
import aioxmpp.structs
import aioxmpp.xso.model


class Service(aioxmpp.service.Service):
    """
    The presence service tracks all incoming presence information (this does
    not include subscription management stanzas, as these are handled by
    :mod:`aioxmpp.roster`). It is independent of the roster, as directed
    presence is independent of the roster and still needs to be tracked
    accordingly.

    No method to send directed presence is provided; it would basically just
    take a stanza and enqueue it in the clients stream, thus being a mere
    wrapper around :meth:`~.stream.StanzaStream.enqueue_stanza`, without any
    benefit.

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
    """

    on_bare_available = aioxmpp.callbacks.Signal()
    on_bare_unavailable = aioxmpp.callbacks.Signal()

    on_available = aioxmpp.callbacks.Signal()
    on_changed = aioxmpp.callbacks.Signal()
    on_unavailable = aioxmpp.callbacks.Signal()

    def __init__(self, client):
        super().__init__(client)

        self._presences = {}

        client.stream.register_presence_callback(
            None,
            None,
            self.handle_presence
        )

        client.stream.register_presence_callback(
            "error",
            None,
            self.handle_presence
        )

        client.stream.register_presence_callback(
            "unavailable",
            None,
            self.handle_presence
        )

    @asyncio.coroutine
    def _shutdown(self):
        self.client.stream.unregister_presence_callback(
            "unavailable",
            None
        )

        self.client.stream.unregister_presence_callback(
            "error",
            None
        )

        self.client.stream.unregister_presence_callback(
            None,
            None
        )

    def get_most_available_stanza(self, peer_jid):
        """
        Return the stanza of the resource with the most available presence.

        The resources are sorted using the ordering defined on
        :class:`~aioxmpp.structs.PresenceState`.
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

    def handle_presence(self, st):
        bare = st.from_.bare()
        resource = st.from_.resource

        if st.type_ == "unavailable":
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
        elif st.type_ == "error":
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
