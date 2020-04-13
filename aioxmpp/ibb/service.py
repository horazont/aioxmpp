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
import random

from datetime import timedelta

import aioxmpp
import aioxmpp.callbacks
import aioxmpp.errors as errors
import aioxmpp.service as service
import aioxmpp.utils as utils

from . import xso as ibb_xso


MAX_BLOCK_SIZE = (1 << 16) - 1


class IBBTransport(asyncio.Transport):
    """
    The transport for IBB sessions.

    .. note:: Never instantiate this class directly, all instances of
              this class are created the methods
              :meth:`~aioxmpp.ibb.IBBService.open_session` and
              :meth:`~aioxmpp.ibb.IBBService.expect_session` of
              :class:`~aioxmpp.ibb.IBBService`.

    The following keys are supported for
    :meth:`~asyncio.BaseTransport.get_extra_info`:

       `block_size`
           The maximal block size of data in a IBB stanza.

       `peer_jid`
          The JID of the peer.

       `sid`
          The session id of the unerlying IBB session.

       `stanza_type`
          The used stanza type.
    """

    def __init__(self, service, peer_jid, sid, stanza_type, block_size):
        self._protocol = None
        self._service = service
        self._stanza_type = stanza_type
        self._sid = sid
        self._peer_jid = peer_jid
        self._block_size = block_size
        self._incoming_seq = 0
        self._outgoing_seq = 0
        self._closed = False
        self._closing = False

        self.set_write_buffer_limits()
        self._write_buffer = b""
        self._can_write = asyncio.Event()

        self._reading_paused = False
        self._input_buffer = []

        self._write_task = asyncio.ensure_future(self._write_task_main())
        self._write_task.add_done_callback(
            self._handle_close
        )

        self._wait_time = self._service.initial_wait_time.total_seconds()
        self._retries = 0

    def set_write_buffer_limits(self, high=None, low=None):
        if low is None:
            low = 4 * self._block_size

        if high is None:
            high = 8 * self._block_size

        if low < 0:
            raise ValueError("the limits must be positive")

        if high < 0:
            raise ValueError("the limits must be positive")

        if low > high:
            low = high

        self._output_buffer_limit_low = low
        self._output_buffer_limit_high = high

    def get_write_buffer_limits(self):
        return self._output_buffer_limit_low, self._output_buffer_limit_high

    def get_write_buffer_size(self):
        return len(self._write_buffer)

    def set_protocol(self, proto):
        self._protocol = proto
        proto.connection_made(self)

    def get_protocol(self):
        return self._protocol

    def pause_reading(self):
        self._reading_paused = True

    def resume_reading(self):
        self._reading_paused = False
        self._protocol.data_received(b"".join(self._input_buffer))
        self._input_buffer.clear()

    def is_closing(self):
        return self._closing or self._closed

    def get_extra_info(self, key, default=None):
        return {
            "block_size": self._block_size,
            "peer_jid": self._peer_jid,
            "stanza_type": self._stanza_type,
            "sid": self._sid,
        }.get(key, default)

    async def _write_task_main(self):
        e = None
        while True:
            await self._can_write.wait()

            if self._write_buffer:
                data = self._write_buffer[:self._block_size]

                if self._stanza_type == ibb_xso.IBBStanzaType.IQ:
                    stanza = aioxmpp.IQ(
                        aioxmpp.IQType.SET,
                        to=self._peer_jid,
                        payload=ibb_xso.Data(
                            self._sid,
                            self._outgoing_seq,
                            data
                        )
                    )
                elif self._stanza_type == ibb_xso.IBBStanzaType.MESSAGE:
                    # TODO: use some form of tracking for messages
                    stanza = aioxmpp.Message(
                        aioxmpp.MessageType.NORMAL,
                        to=self._peer_jid,
                    )
                    stanza.xep0047_data = ibb_xso.Data(
                        self._sid,
                        self._outgoing_seq,
                        data
                    )

                try:
                    await self._service.client.send(
                        stanza
                    )
                except errors.XMPPWaitError:
                    # wait and try again unless max retries have been reached
                    if self._retries < self._service.max_retries:
                        await asyncio.sleep(self._wait_time)
                        self._wait_time *= self._service.wait_backoff_factor
                        self._retries += 1
                        continue
                    else:
                        e = asyncio.TimeoutError()
                        break
                except errors.StanzaError as _e:
                    # break the loop to close the connection
                    e = _e
                    break
                # update the internal state after the successful
                # write: remove the written data from the buffer and
                # increment the sequence number
                self._write_buffer = self._write_buffer[len(data):]
                self._outgoing_seq += 1
                self._outgoing_seq &= 0xffff

                # reset the wait time
                self._wait_time = \
                    self._service.initial_wait_time.total_seconds()
                self._retries = 0

            if len(self._write_buffer) < self._output_buffer_limit_low:
                self._protocol.resume_writing()

            if not self._write_buffer:
                if self._closing:
                    e = None
                    break
                self._can_write.clear()

        close = ibb_xso.Close()
        close.sid = self._sid
        stanza = aioxmpp.IQ(
            aioxmpp.IQType.SET,
            to=self._peer_jid,
            payload=close,
        )

        try:
            await self._service.client.send(stanza)
        except errors.StanzaError as _e:
            if e is None:
                e = _e
        finally:
            if e is not None:
                raise e

    def write(self, data):
        """
        Send `data` over the IBB. If `data` is larger than the block size
        is is chunked and sent in chunks.

        Chunks from one call of :meth:`write` will always be sent in
        series.
        """

        if self.is_closing():
            return

        self._write_buffer += data

        if len(self._write_buffer) >= self._output_buffer_limit_high:
            self._protocol.pause_writing()

        if self._write_buffer:
            self._can_write.set()

    def _connection_closed(self):
        self._write_task.cancel()

    def _handle_close(self, fut):
        e = None
        self._service._remove_session(self._peer_jid, self._sid)
        try:
            e = fut.exception()
        except asyncio.CancelledError:
            pass
        self._protocol.connection_lost(e)
        self._closed = True

    def close(self):
        """
        Close the session.
        """
        if self.is_closing():
            return

        self._closing = True
        # make sure the writer wakes up
        self._can_write.set()

    def abort(self):
        """
        Abort the session.
        """
        if self.is_closing():
            return
        self._connection_closed()

    def _data_received(self, data):
        if self._closed:
            return

        if self._reading_paused:
            self._input_buffer.append(data)
        else:
            self._protocol.data_received(data)

    def _process_iq(self, payload):
        if payload.seq != self._incoming_seq:
            raise errors.XMPPCancelError(
                condition=errors.ErrorCondition.UNEXPECTED_REQUEST
            )
        self._incoming_seq += 1
        self._incoming_seq &= 0xffff
        self._data_received(payload.content)

    def _process_msg(self, payload):
        if payload.seq != self._incoming_seq:
            return
        self._incoming_seq += 1
        self._incoming_seq &= 0xffff
        self._data_received(payload.content)


class IBBService(service.Service):
    """
    A service implementing in-band bytestreams.

    Methods for establishing sessions:

    .. automethod:: expect_session

    .. automethod:: open_session

    The following attributes control the establishment of sessions due
    to a received request, that was not announced to the service by
    :meth:`expect_session`:

    .. attribute:: session_limit
       :annotation: = 0

       The maximal number of sessions to be accepted. If there are
       that many or more active sessions, no new sessions are
       accepted, unless they are whitelisted by
       :meth:`expect_session`. (This means, that by default only
       expected sessions are accepted!).

    .. attribute:: default_protocol_factory

       The protocol factory to be used when an unexpected connection
       is established. This *must* be set when changing
       :attr:`session_limit` to a non-zero value.

    .. signal:: on_session_accepted(transport, protocol)

       Fires when a session is established due to a received open
       request that was not expected (compare
       :meth:`expect_session`). This can only happen when
       :attr:`session_limit` is set to another value than its default
       value.

    The following attributes control how the IBB sessions react to
    errors of type wait:

    .. attribute:: max_retries
       :annotation: = 5

       The number of times it is tried to resend a data stanza, when a
       :class:`~aioxmpp.errors.XMPPWaitError` is received. When
       :attr:`max_retries` have been tried, the session is closed.
       `connection_lost` of the protocol receives an
       :class:`asyncio.TimeoutError`.

    .. attribute:: initial_wait_time
       :annotation: = timedelta(seconds=1)

       The time to wait when receiving a
       :class:`~aioxmpp.errors.XMPPWaitError` for the first time.

    .. attribute:: wait_backoff_factor
       :annotation: = 1.2

       The factor by which the wait time is prolonged on each
       successive wait error.
    """

    on_session_accepted = aioxmpp.callbacks.Signal()

    def __init__(self, client, **kwargs):
        super().__init__(client, **kwargs)

        self._sessions = {}

        self.session_limit = 0
        self._expected_sessions = {}

        self.default_protocol_factory = None

        self.client.on_stream_destroyed.connect(
            self._on_stream_destroyed
        )

        self.max_retries = 5
        self.initial_wait_time = timedelta(seconds=1)
        self.wait_backoff_factor = 1.2

    def _on_stream_destroyed(self):
        self._expected_sessions = {}

        # tear down the remaining open sessions
        for session in list(self._sessions.values()):
            session.abort()

    def expect_session(self, protocol_factory, peer_jid, sid):
        """
        Whitelist the session with `peer_jid` and the session id `sid` and
        return it when it is established. This is meant to be used
        with signalling protocols like Jingle and is the counterpart
        to :meth:`open_session`.

        :returns: an awaitable object, whose result is the tuple
                  `(transport, protocol)`
        """
        def on_done(fut):
            del self._expected_sessions[sid, peer_jid]

        _, fut = self._expected_sessions[sid, peer_jid] = (
            protocol_factory, asyncio.Future()
        )
        fut.add_done_callback(on_done)
        return fut

    async def open_session(self, protocol_factory, peer_jid, *,
                           stanza_type=ibb_xso.IBBStanzaType.IQ,
                           block_size=4096, sid=None):
        """
        Establish an in-band bytestream session with `peer_jid` and
        return the transport and protocol.

        :param protocol_factory: the protocol factory
        :type protocol_factory: a nullary callable returning an
                                :class:`asyncio.Protocol` instance
        :param peer_jid: the JID with which to establish the byte-stream.
        :type peer_jid: :class:`aioxmpp.JID`
        :param stanza_type: the stanza type to use
        :type stanza_type: class:`~aioxmpp.ibb.IBBStanzaType`
        :param block_size: the maximal size of blocks to transfer
        :type block_size: :class:`int`
        :param sid: the session id to use
        :type sid: :class:`str` (must be a valid NMTOKEN)

        :returns: the transport and protocol
        :rtype: a tuple of :class:`aioxmpp.ibb.service.IBBTransport`
                and :class:`asyncio.Protocol`
        """
        if block_size > MAX_BLOCK_SIZE:
            raise ValueError("block_size too large")

        if sid is None:
            sid = utils.to_nmtoken(random.getrandbits(8*8))
        open_ = ibb_xso.Open()
        open_.stanza = stanza_type
        open_.sid = sid
        open_.block_size = block_size

        # XXX: retry on XMPPModifyError with RESOURCE_CONSTRAINT
        await self.client.send(
            aioxmpp.IQ(
                aioxmpp.IQType.SET,
                to=peer_jid,
                payload=open_,
            )
        )

        handle = self._sessions[sid, peer_jid] = IBBTransport(
            self,
            peer_jid,
            sid,
            stanza_type,
            block_size,
        )

        protocol = protocol_factory()
        handle.set_protocol(protocol)
        return handle, protocol

    @service.iq_handler(
        aioxmpp.IQType.SET,
        ibb_xso.Open)
    async def _handle_open_request(self, iq):
        peer_jid = iq.from_
        sid = iq.payload.sid
        block_size = iq.payload.block_size
        stanza_type = iq.payload.stanza

        if block_size > MAX_BLOCK_SIZE:
            raise errors.XMPPModifyError(
                condition=errors.ErrorCondition.RESOURCE_CONSTRAINT
            )

        try:
            protocol_factory, expected_future = \
                self._expected_sessions[sid, peer_jid]
        except KeyError:
            if len(self._sessions) >= self.session_limit:
                raise errors.XMPPCancelError(
                    condition=errors.ErrorCondition.NOT_ACCEPTABLE
                )
            expected_future = None
            protocol_factory = self.default_protocol_factory

        if (sid, peer_jid) in self._sessions:
            # disallow opening a session twice
            if expected_future is not None:
                # is this correct?
                expected_future.cancel()
            raise errors.XMPPCancelError(
                condition=errors.ErrorCondition.NOT_ACCEPTABLE
            )

        handle = self._sessions[sid, peer_jid] = IBBTransport(
            self,
            peer_jid,
            sid,
            stanza_type,
            block_size
        )

        protocol = protocol_factory()
        handle.set_protocol(protocol)

        if expected_future is None:
            self.on_session_accepted((handle, protocol))
        else:
            expected_future.set_result((handle, protocol))

    @service.iq_handler(
        aioxmpp.IQType.SET,
        ibb_xso.Close)
    async def _handle_close_request(self, iq):
        peer_jid = iq.from_
        sid = iq.payload.sid

        try:
            session_handle = self._sessions[sid, peer_jid]
        except KeyError:
            raise errors.XMPPCancelError(
                condition=errors.ErrorCondition.ITEM_NOT_FOUND
            )

        session_handle._connection_closed()

    @service.iq_handler(
        aioxmpp.IQType.SET,
        ibb_xso.Data)
    async def _handle_data(self, iq):
        peer_jid = iq.from_
        sid = iq.payload.sid

        try:
            session_handle = self._sessions[sid, peer_jid]
        except KeyError:
            raise errors.XMPPCancelError(
                condition=errors.ErrorCondition.ITEM_NOT_FOUND
            )

        session_handle._process_iq(iq.payload)

    @service.inbound_message_filter
    def _handle_message(self, msg):
        if msg.xep0047_data is None:
            return msg

        payload = msg.xep0047_data
        peer_jid = msg.from_
        sid = payload.sid

        try:
            session = self._sessions[sid, peer_jid]
        except KeyError:
            return None

        session._process_msg(payload)

        return None

    def _remove_session(self, peer_jid, sid):
        del self._sessions[sid, peer_jid]
