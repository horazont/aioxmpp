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
import random
import time

from datetime import timedelta

import aioxmpp.errors
import aioxmpp.ping
import aioxmpp.stream
import aioxmpp.structs
import aioxmpp.utils


def _apply_jitter(v, amplitude):
    return v * ((random.random() * 2 - 1) * amplitude + 1)


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
    :attr:`ping_interval` is less than :attr:`ping_timeout`, it is possible
    that multiple pings are in-flight at the same time (this is handled
    correctly). Take into account that resources for tracking up to
    :attr:`ping_timeout` divided by :attr:`ping_interval` IQ responses will be
    required.

    To start the pinger, :meth:`start` must be called.

    .. automethod:: start

    .. automethod:: stop

    .. attribute:: ping_address

        The address pings are sent to.

        This can be changed while the pinger is running. Changes take effect
        when the next ping is sent. Already in-flight pings are not affected.

    .. autoattribute:: ping_interval

    .. autoattribute:: ping_timeout
    """

    def __init__(self, ping_address, client, on_fresh, on_exited, logger, loop):
        super().__init__()
        self.ping_address = ping_address
        self._ping_interval = timedelta(minutes=2)
        self._ping_timeout = timedelta(minutes=8)
        self._client = client
        self._on_fresh = on_fresh
        self._on_exited = on_exited
        self._loop = loop
        self._logger = logger
        self._task = None

    @property
    def ping_interval(self) -> timedelta:
        """
        The interval at which pings are sent.

        While the pinger is running, every `ping_interval` a new ping is
        started. Each ping has its individual :attr:`ping_timeout`.

        Changing this property takes effect after the next ping has been sent.
        Thus, if the :attr:`ping_interval` was set to one day and is then
        changed to one minute, it takes up to a day until the one minute
        interval starts being used.
        """
        return self._ping_interval

    @ping_interval.setter
    def ping_interval(self, value: timedelta):
        # cheap & duck-typey enforcement of timedelta compatibility
        self._ping_interval = value + timedelta()

    @property
    def ping_timeout(self) -> timedelta:
        """
        The maximum time to wait for a reply to a ping.

        Each ping sent by the pinger has its individual timeout, based on this
        property at the time the ping is sent.
        """
        return self._ping_timeout

    @ping_timeout.setter
    def ping_timeout(self, value: timedelta):
        # cheap & duck-typey enforcement of timedelta compatibility
        self._ping_timeout = value + timedelta()

    def start(self):
        """
        Start the pinging coroutine using the client and event loop which was
        passed to the constructor.

        :meth:`start` always behaves as if :meth:`stop` was called right before
        it.
        """
        self._logger.debug("%s: request to start pinger",
                           self.ping_address)
        self.stop()
        self._task = asyncio.ensure_future(self._pinger(), loop=self._loop)

    def stop(self):
        """
        Stop the pinger (if it is running) and discard all data on in-flight
        pings.

        This method will do nothing if the pinger is already stopped. It is
        idempotent.
        """
        self._logger.debug("%s: request to stop pinger",
                           self.ping_address)
        if self._task is None:
            self._logger.debug("%s: already stopped", self.ping_address)
            return

        self._logger.debug("%s: sending cancel signal", self.ping_address)
        self._task.cancel()
        self._task = None

    def _interpret_result(self, task):
        """
        Interpret the result of a ping.

        :param task: The pinger task.

        The result or exception of the `task` is interpreted as follows:

        * :data:`None` result: *positive*
        * :class:`aioxmpp.errors.XMPPError`, ``service-unavailable``:
          *positive*
        * :class:`aioxmpp.errors.XMPPError`, ``feature-not-implemented``:
          *positive*
        * :class:`aioxmpp.errors.XMPPError`, ``item-not-found``: *inconclusive*
        * :class:`aioxmpp.errors.XMPPError`, ``remote-server-not-found``:
          *inconclusive*
        * :class:`aioxmpp.errors.XMPPError`, ``remote-server-timeout``:
          *inconclusive*
        * :class:`aioxmpp.errors.XMPPError`: *negative*
        * :class:`asyncio.TimeoutError`: *inconclusive*
        * Any other exception: *inconclusive*
        """
        if task.exception() is None:
            self._logger.debug("%s: ping reply has no error -> emitting fresh "
                               "event", self.ping_address)
            self._on_fresh()
            return

        exc = task.exception()
        if isinstance(exc, aioxmpp.errors.XMPPError):
            if exc.condition in [
                    aioxmpp.errors.ErrorCondition.SERVICE_UNAVAILABLE,
                    aioxmpp.errors.ErrorCondition.FEATURE_NOT_IMPLEMENTED]:
                self._logger.debug(
                    "%s: ping reply has error indicating freshness: %s",
                    self.ping_address,
                    exc.condition,
                )
                self._on_fresh()
                return

            if exc.condition in [
                    aioxmpp.errors.ErrorCondition.ITEM_NOT_FOUND,
                    aioxmpp.errors.ErrorCondition.REMOTE_SERVER_NOT_FOUND,
                    aioxmpp.errors.ErrorCondition.REMOTE_SERVER_TIMEOUT]:
                self._logger.debug(
                    "%s: ping reply has inconclusive error: %s",
                    self.ping_address,
                    exc.condition,
                )
                return

            self._logger.debug(
                "%s: ping reply has error indicating that the client got "
                "removed: %s",
                self.ping_address,
                exc.condition,
            )
            self._on_exited()

    async def _pinger(self):
        in_flight = []
        next_ping_at = None
        self._logger.debug("%s: pinger booted up", self.ping_address)
        try:
            while True:
                self._logger.debug("%s: pinger loop. interval=%r",
                                   self.ping_address,
                                   self.ping_interval)
                now = time.monotonic()

                ping_interval = self.ping_interval.total_seconds()
                if next_ping_at is None:
                    next_ping_at = now - 1

                timeout = next_ping_at - now

                if timeout <= 0:
                    # do not send pings while the client is in suspended state
                    # (= Stream Management hibernation). This will only add to
                    # the queue for no good reason, we won’t get any reply soon
                    # anyways.
                    if self._client.suspended:
                        self._logger.debug(
                            "%s: omitting self-ping, as the stream is "
                            "currently hibernated",
                            self.ping_address,
                        )
                    else:
                        self._logger.debug(
                            "%s: sending self-ping with timeout %r",
                            self.ping_address,
                            self.ping_timeout,
                        )
                        in_flight.append(asyncio.ensure_future(
                            asyncio.wait_for(
                                aioxmpp.ping.ping(self._client,
                                                  self.ping_address),
                                self.ping_timeout.total_seconds()
                            )
                        ))
                    next_ping_at = now + _apply_jitter(ping_interval, 0.1)
                    timeout = ping_interval

                assert timeout > 0

                if not in_flight:
                    self._logger.debug(
                        "%s: pinger has nothing to do, sleeping for %s",
                        self.ping_address,
                        timeout,
                    )
                    await asyncio.sleep(timeout)
                    continue

                self._logger.debug(
                    "%s: pinger waiting for %d pings for at most %ss",
                    self.ping_address,
                    len(in_flight),
                    timeout,
                )
                done, pending = await asyncio.wait(
                    in_flight,
                    timeout=timeout,
                    return_when=asyncio.FIRST_COMPLETED,
                )

                for fut in done:
                    self._interpret_result(fut)

                in_flight = list(pending)
        finally:
            self._logger.debug("%s: pinger exited", self.ping_address,
                               exc_info=True)
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
                 logger,
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
        self._logger = logger
        self._pinger = MUCPinger(
            ping_address,
            client,
            self._pinger_fresh_detected,
            self._pinger_exited_detected,
            logger,
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
        # cheap & duck-typey enforcement of timedelta compatibility
        self._soft_timeout = new_value + timedelta()
        if self._monitor_enabled:
            self._monitor.deadtime_soft_limit = new_value

    @property
    def hard_timeout(self) -> timedelta:
        return self._hard_timeout

    @hard_timeout.setter
    def hard_timeout(self, new_value: timedelta):
        # cheap & duck-typey enforcement of timedelta compatibility
        self._hard_timeout = new_value + timedelta()
        if self._monitor_enabled:
            self._monitor.deadtime_hard_limit = new_value

    ping_address = aioxmpp.utils.proxy_property(
        "_pinger",
        "ping_address",
    )

    ping_timeout = aioxmpp.utils.proxy_property(
        "_pinger",
        "ping_timeout",
    )

    ping_interval = aioxmpp.utils.proxy_property(
        "_pinger",
        "ping_interval",
    )

    def enable(self):
        """
        Enable the monitor, if it is not enabled already.

        If the monitor is not already enabled, the aliveness timeouts are reset
        and configured and the stale state is cleared.
        """
        self._logger.debug("%s: request to enable monitoring",
                           self.ping_address)
        if self._monitor_enabled:
            return
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
            self._logger.debug("%s: transition to stale", self.ping_address)
            self.on_stale()
        self._is_stale = True

    def _mark_fresh(self):
        """
        - Emit on_fresh if stale flag is set
        - Clear stale flag
        """
        if self._is_stale:
            self._logger.debug("%s: transition to fresh", self.ping_address)
            self.on_fresh()
        self._is_stale = False

    def _enable_monitor(self):
        # we need to call notify received *first* to prevent spurious events
        self._monitor.notify_received()
        self._monitor.deadtime_soft_limit = self._soft_timeout
        self._monitor.deadtime_hard_limit = self._hard_timeout
        self._monitor_enabled = True
        self._logger.debug("%s: enabled monitoring: "
                           "soft_timeout=%r "
                           "hard_timeout=%r "
                           "ping_interval=%r "
                           "ping_timeout=%r",
                           self.ping_address,
                           self._soft_timeout,
                           self._hard_timeout,
                           self.ping_interval,
                           self.ping_timeout)

    def _disable_monitor(self):
        # we need to call notify received *first* to prevent spurious events
        self._monitor.notify_received()
        self._monitor.deadtime_soft_limit = None
        self._monitor.deadtime_hard_limit = None
        self._monitor_enabled = False
        self._logger.debug("%s: disabled monitoring", self.ping_address)

    def _pinger_fresh_detected(self):
        self._logger.debug("%s: fresh detected", self.ping_address)
        self._pinger.stop()
        self._monitor.notify_received()
        self._mark_fresh()

    def _pinger_exited_detected(self):
        self._logger.debug("%s: exited detected", self.ping_address)
        self._pinger.stop()
        self.on_exited()

    def _soft_limit_tripped(self):
        self._logger.debug("%s: soft-limit tripped, starting pinger",
                           self.ping_address)
        self._pinger.start()

    def _hard_limit_tripped(self):
        self._logger.debug("%s: hard-limit tripped, marking stale",
                           self.ping_address)
        self._mark_stale()
