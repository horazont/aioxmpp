########################################################################
# File name: self_ping.py
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
import time

from datetime import timedelta

import aioxmpp.errors
import aioxmpp.ping
import aioxmpp.stream
import aioxmpp.structs
import aioxmpp.utils


class MUCPinger:
    """
    :param on_fresh: Called when the pinger finds evidence that the user is
        connected
    :param on_exited: Called when the pinger finds evidence that the user is
        disconnected
    :param loop: Event loop to use

    This class manages a coroutine which sends pings to a remote entity and
    interprets the results according to :xep:`410`.

    If the result of a ping indicates that the client is not joined in the MUC
    anymore, `on_exited` is called. If the result of a ping indicates that the
    client is still joined in a MUC, `on_stale` is called. If the result are
    inconclusive, no call is made.

    A ping result does *not* imply a call to :meth:`stop`. The callbacks are
    called on each ping response, thus, on average up to once each
    :attr:`ping_interval` until :meth:`stop` is called.

    Pings are sent once each :attr:`ping_interval` (see there for details on
    the effects of changing the interval while the pinger is running). If
    :attr:`ping_interval` is less than :attr:`ping_timeout`, it is possible that
    multiple pings are in-flight at the same time (this is handled correctly).
    Take into account that resources for tracking up to :attr:`ping_timeout`
    divided by :attr:`ping_interval` IQ responses will be required.

    To start the pinger, :meth:`start` must be called.

    .. automethod:: start

    .. automethod:: stop

    .. attribute:: ping_address

        The address pings are sent to.

        This can be changed while the pinger is running. Changes take effect
        when the next ping is sent. Already in-flight pings are not affected.

    .. attribute:: ping_interval

        The interval at which pings are sent.

        While the pinger is running, every `ping_interval` a new ping is
        started. Each ping has its individual :attr:`ping_timeout`.

        Changing this property takes effect after the next ping has been sent.
        Thus, if the :attr:`ping_interval` was set to one day and is then
        changed to one minute, it takes up to a day until the one minute
        interval starts being used.

    .. attribute:: ping_timeout

        The maximum time to wait for a reply to a ping.

        Each ping sent by the pinger has its individual timeout, based on this
        property at the time the ping is sent.
    """

    def __init__(self, ping_address, client, on_fresh, on_exited, loop):
        super().__init__()
        self.ping_address = ping_address
        self.ping_interval = timedelta(minutes=2)
        self.ping_timeout = timedelta(minutes=8)
        self._client = client
        self._on_fresh = on_fresh
        self._on_exited = on_exited
        self._loop = loop
        self._task = None

    def start(self):
        """
        Start the pinging coroutine using the client and event loop which was
        passed to the constructor.

        :meth:`start` always behaves as if :meth:`stop` was called right before
        it.
        """
        self.stop()
        self._task = asyncio.ensure_future(self._pinger(), loop=self._loop)

    def stop(self):
        """
        Stop the pinger (if it is running) and discard all data on in-flight
        pings.

        This method will do nothing if the pinger is already stopped. It is
        idempotent.
        """
        if self._task is None:
            return

        self._task.cancel()
        self._task = None

    def _interpret_result(self, task):
        """
        Interpret the result of a ping.

        :param task: The pinger task.

        The result or exception of the `task` is interpreted as follows:

        * :data:`None` result: *positive*
        * :class:`aioxmpp.errors.XMPPError`, ``service-unavailable``: *positive*
        * :class:`aioxmpp.errors.XMPPError`, ``feature-not-implemented``:
          *positive*
        * :class:`aioxmpp.errors.XMPPError`, ``item-not-found``: *inconclusive*
        * :class:`aioxmpp.errors.XMPPError`: *negative*
        * :class:`asyncio.TimeoutError`: *inconclusive*
        * Any other exception: *inconclusive*
        """
        if task.exception() is None:
            self._on_fresh()
            return

        exc = task.exception()
        if isinstance(exc, aioxmpp.errors.XMPPError):
            if exc.condition in [
                    aioxmpp.errors.ErrorCondition.SERVICE_UNAVAILABLE,
                    aioxmpp.errors.ErrorCondition.FEATURE_NOT_IMPLEMENTED]:
                self._on_fresh()
                return

            if exc.condition == aioxmpp.errors.ErrorCondition.ITEM_NOT_FOUND:
                return

            self._on_exited()

    @asyncio.coroutine
    def _pinger(self):
        in_flight = []
        last_ping_at = None
        try:
            while True:
                now = time.monotonic()

                ping_interval = self.ping_interval.total_seconds()
                if last_ping_at is None:
                    timeout = 0
                else:
                    timeout = ping_interval - (now - last_ping_at)

                if timeout <= 0:
                    in_flight.append(asyncio.ensure_future(
                        asyncio.wait_for(
                            aioxmpp.ping.ping(self._client, self.ping_address),
                            self.ping_timeout.total_seconds()
                        )
                    ))
                    last_ping_at = now
                    timeout = ping_interval

                assert timeout > 0

                if not in_flight:
                    yield from asyncio.sleep(timeout)
                    continue

                done, pending = yield from asyncio.wait(
                    in_flight,
                    timeout=timeout,
                    return_when=asyncio.FIRST_COMPLETED,
                )

                for fut in done:
                    self._interpret_result(fut)

                in_flight = list(pending)
        finally:
            for fut in in_flight:
                if not fut.done():
                    fut.cancel()


class MUCMonitor:
    """
    :param ping_address: Address to send pings to. Can be changed later with
        :attr:`ping_address`.
    :type ping_address: :class:`aioxmpp.JID`
    :param client: Client to send pings with.
    :type stream: :class:`aioxmpp.stream.StanzaStream`
    :param on_stale: Called when the pinger detects stale state.
    :param on_fresh: Called when the pinger detects fresh state.
    :param on_exited: Called when the pinger detects that the user is not in
        the room anymore.
    :param loop: Event loop to use (defaults to the current event loop)

    .. automethod:: enable

    .. automethod:: disable

    .. automethod:: reset

    .. attribute:: ping_address

        The address to ping.

    .. autoattribute:: stream

    .. autoattribute:: is_stale

    .. autoattribute:: soft_timeout

    .. autoattribute:: hard_timeout

    .. autoattribute:: ping_interval

    .. autoattribute:: ping_timeout
    """

    def __init__(self,
                 ping_address: aioxmpp.structs.JID,
                 client: "aioxmpp.node.Client",
                 on_stale,
                 on_fresh,
                 on_exited,
                 loop=None):
        loop = loop or asyncio.get_event_loop()
        super().__init__()
        self._client = client
        self._is_stale = False
        self.on_stale = on_stale
        self.on_fresh = on_fresh
        self.on_exited = on_exited
        self._soft_timeout = timedelta(minutes=13)
        self._hard_timeout = timedelta(minutes=15)
        self._monitor = aioxmpp.utils.AlivenessMonitor(loop)
        # disable the monitor altogether
        self._monitor.deadtime_hard_limit = None
        self._monitor.deadtime_soft_limit = None
        self._monitor_enabled = False
        self._monitor.on_deadtime_hard_limit_tripped.connect(
            self._hard_limit_tripped
        )
        self._monitor.on_deadtime_soft_limit_tripped.connect(
            self._soft_limit_tripped
        )
        self._pinger = MUCPinger(
            ping_address,
            client,
            self._pinger_fresh_detected,
            self._pinger_exited_detected,
            loop,
        )

        self.ping_address = ping_address

    @property
    def is_stale(self) -> bool:
        return self._is_stale

    @property
    def soft_timeout(self) -> timedelta:
        return self._soft_timeout

    @soft_timeout.setter
    def soft_timeout(self, new_value: timedelta):
        self._soft_timeout = new_value
        if self._monitor_enabled:
            self._monitor.deadtime_soft_limit = new_value

    @property
    def hard_timeout(self) -> timedelta:
        return self._hard_timeout

    @hard_timeout.setter
    def hard_timeout(self, new_value: timedelta):
        self._hard_timeout = new_value
        if self._monitor_enabled:
            self._monitor.deadtime_hard_limit = new_value

    @property
    def ping_address(self) -> aioxmpp.structs.JID:
        return self._pinger.ping_address

    @ping_address.setter
    def ping_address(self, new_address: aioxmpp.structs.JID):
        self._pinger.ping_address = new_address

    @property
    def ping_timeout(self) -> timedelta:
        return self._pinger.ping_timeout

    @ping_timeout.setter
    def ping_timeout(self, new_timeout: timedelta):
        self._pinger.ping_timeout = new_timeout

    @property
    def ping_interval(self) -> timedelta:
        return self._pinger.ping_interval

    @ping_interval.setter
    def ping_interval(self, new_interval: timedelta):
        self._pinger.ping_interval = new_interval

    def enable(self):
        """
        Enable the monitor.

        Reset and start the aliveness timeouts. Clear the stale state.
        """
        self._is_stale = False
        self._enable_monitor()

    def disable(self):
        """
        Disable the monitor.

        Reset and stop the aliveness timeouts. Cancel and stop pinging.
        """
        self._disable_monitor()
        self._pinger.stop()

    def reset(self):
        """
        Reset the monitor.

        Reset the aliveness timeouts. Clear the stale state. Cancel and stop
        pinging.

        Call `on_fresh` if the stale state was set.
        """
        self._monitor.notify_received()
        self._pinger.stop()
        self._mark_fresh()

    def _mark_stale(self):
        """
        - Emit on_stale if stale flag is cleared
        - Set stale flag
        """
        if not self._is_stale:
            self.on_stale()
        self._is_stale = True

    def _mark_fresh(self):
        """
        - Emit on_fresh if stale flag is set
        - Clear stale flag
        """
        if self._is_stale:
            self.on_fresh()
        self._is_stale = False

    def _enable_monitor(self):
        # we need to call notify received *first* to prevent spurious events
        self._monitor.notify_received()
        self._monitor.deadtime_soft_limit = self._soft_timeout
        self._monitor.deadtime_hard_limit = self._hard_timeout
        self._monitor_enabled = True

    def _disable_monitor(self):
        # we need to call notify received *first* to prevent spurious events
        self._monitor.notify_received()
        self._monitor.deadtime_soft_limit = None
        self._monitor.deadtime_hard_limit = None
        self._monitor_enabled = False

    def _pinger_fresh_detected(self):
        self._pinger.stop()
        self._monitor.notify_received()
        self._mark_fresh()

    def _pinger_exited_detected(self):
        self._pinger.stop()
        self.on_exited()

    def _soft_limit_tripped(self):
        self._pinger.start()

    def _hard_limit_tripped(self):
        self._mark_stale()
