########################################################################
# File name: network.py
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
:mod:`~aioxmpp.network` --- DNS resolution utilities
####################################################

This module uses :mod:`dns` to handle DNS queries.

.. versionchanged:: 0.5.4

   The module was completely rewritten in 0.5.4. The documented API stayed
   mostly the same though.

Configure the resolver
======================

.. versionadded:: 0.5.4

   The whole thread-local resolver thing was added in 0.5.4. This includes the
   magic to re-configure the used resolver when a query fails.

The module uses a thread-local resolver instance. It can be accessed using
:func:`get_resolver`. Re-read of the system-wide resolver configuration can be
forced by calling :func:`reconfigure_resolver`. To configure a custom resolver
instance, use :func:`set_resolver`.

By setting a custom resolver instance, the facilities which *automatically*
reconfigure the resolver whenever DNS timeouts occur are disabled.

.. note::

   Currently, there is no way to set a resolver per XMPP client. If such a way
   is desired, feel free to open a bug against :mod:`aioxmpp`. I cannot really
   imagine such a situation, but if you encounter one, please let me know.

.. autofunction:: get_resolver

.. autofunction:: reconfigure_resolver

.. autofunction:: set_resolver

Querying records
================

In addition to using the :class:`dns.resolver.Resolver` instance returned by
:func:`get_resolver`, one can also use :func:`repeated_query`. The latter takes
care of re-trying the query up to a configurable amount of times. It will also
automatically call :func:`reconfigure_resolver` (unless a custom resolver has
been set) if a timeout occurs and switch to TCP if problems persist.

.. autofunction:: repeated_query

SRV records
===========

.. autofunction:: find_xmpp_host_addr

.. autofunction:: lookup_srv

.. autofunction:: group_and_order_srv_records


"""

import asyncio
import functools
import itertools
import logging
import random
import threading

import dns
import dns.flags
import dns.resolver

logger = logging.getLogger(__name__)

_state = threading.local()


class ValidationError(Exception):
    pass


def get_resolver():
    """
    Return the thread-local :class:`dns.resolver.Resolver` instance used by
    :mod:`aioxmpp`.
    """

    global _state
    if not hasattr(_state, "resolver"):
        reconfigure_resolver()
    return _state.resolver


class DummyResolver:
    def set_flags(self, *args, **kwargs):
        # noop
        pass

    def query(self, *args, **kwargs):
        raise dns.resolver.NoAnswer


def reconfigure_resolver():
    """
    Reset the resolver configured for this thread to a fresh instance. This
    essentially re-reads the system-wide resolver configuration.

    If a custom resolver has been set using :func:`set_resolver`, the flag
    indicating that no automatic re-configuration shall take place is cleared.
    """

    global _state
    try:
        _state.resolver = dns.resolver.Resolver()
    except dns.resolver.NoResolverConfiguration:
        _state.resolver = DummyResolver()
    _state.overridden_resolver = False


def set_resolver(resolver):
    """
    Replace the current thread-local resolver (which can be accessed using
    :func:`get_resolver`) with `resolver`.

    This also sets an internal flag which prohibits the automatic calling of
    :func:`reconfigure_resolver` from :func:`repeated_query`. To re-allow
    automatic reconfiguration, call :func:`reconfigure_resolver`.
    """

    global _state
    _state.resolver = resolver
    _state.overridden_resolver = True


async def repeated_query(qname, rdtype,
                         nattempts=None,
                         resolver=None,
                         require_ad=False,
                         executor=None):
    """
    Repeatedly fire a DNS query until either the number of allowed attempts
    (`nattempts`) is exceeded or a non-error result is returned (NXDOMAIN is
    a non-error result).

    If `nattempts` is :data:`None`, it is set to 3 if `resolver` is
    :data:`None` and to 2 otherwise. This way, no query is made without a
    possible change to a local parameter. (When using the thread-local
    resolver, it will be re-configured after the first failed query and after
    the second failed query, TCP is used. With a fixed resolver, TCP is used
    after the first failed query.)

    `qname` must be the (IDNA encoded, as :class:`bytes`) name to query,
    `rdtype` the record type to query for. If `resolver` is not :data:`None`,
    it must be a DNSPython :class:`dns.resolver.Resolver` instance; if it is
    :data:`None`, the resolver obtained from :func:`get_resolver` is used.

    If `require_ad` is :data:`True`, the peer resolver is asked to do DNSSEC
    validation and if the AD flag is missing in the response,
    :class:`ValueError` is raised. If `require_ad` is :data:`False`, the
    resolver is asked to do DNSSEC validation nevertheless, but missing
    validation (in contrast to failed validation) is not an error.

    .. note::

       This function modifies the flags of the `resolver` instance, no matter
       if it uses the thread-local resolver instance or the resolver passed as
       an argument.

    If the first query fails and `resolver` is :data:`None` and the
    thread-local resolver has not been overridden with :func:`set_resolver`,
    :func:`reconfigure_resolver` is called and the query is re-attempted
    immediately.

    If the next query after reconfiguration of the resolver (if the
    preconditions for resolver reconfigurations are not met, this applies to
    the first failing query), :func:`repeated_query` switches to TCP.

    If no result is received before the number of allowed attempts is exceeded,
    :class:`TimeoutError` is raised.

    Return the result set or :data:`None` if the domain does not exist.

    This is a coroutine; the query is executed in an `executor` using the
    :meth:`asyncio.BaseEventLoop.run_in_executor` of the current event loop. By
    default, the default executor provided by the event loop is used, but it
    can be overridden using the `executor` argument.

    If the used resolver raises :class:`dns.resolver.NoNameservers`
    (semantically, that no nameserver was able to answer the request), this
    function suspects that DNSSEC validation failed, as responding with
    SERVFAIL is what unbound does. To test that case, a simple check is made:
    the query is repeated, but with a flag set which indicates that we would
    like to do the validation ourselves. If that query succeeds, we assume that
    the error is in fact due to DNSSEC validation failure and raise
    :class:`ValidationError`. Otherwise, the answer is discarded and the
    :class:`~dns.resolver.NoNameservers` exception is treated as normal
    timeout. If the exception re-occurs in the second query, it is re-raised,
    as it indicates a serious configuration problem.
    """
    global _state

    loop = asyncio.get_event_loop()

    # tlr = thread-local resolver
    use_tlr = False
    if resolver is None:
        resolver = get_resolver()
        use_tlr = not _state.overridden_resolver

    if nattempts is None:
        if use_tlr:
            nattempts = 3
        else:
            nattempts = 2

    if nattempts <= 0:
        raise ValueError("query cannot succeed with non-positive amount "
                         "of attempts")

    qname = qname.decode("ascii")

    def handle_timeout():
        nonlocal use_tlr, resolver, use_tcp
        if use_tlr and i == 0:
            reconfigure_resolver()
            resolver = get_resolver()
        else:
            use_tcp = True

    use_tcp = False
    for i in range(nattempts):
        resolver.set_flags(dns.flags.RD | dns.flags.AD)
        try:
            answer = await loop.run_in_executor(
                executor,
                functools.partial(
                    resolver.query,
                    qname,
                    rdtype,
                    tcp=use_tcp
                )
            )

            if require_ad and not (answer.response.flags & dns.flags.AD):
                raise ValueError("DNSSEC validation not available")
        except (TimeoutError, dns.resolver.Timeout):
            handle_timeout()
            continue
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
            return None
        except (dns.resolver.NoNameservers):
            # make sure we have the correct config
            if use_tlr and i == 0:
                reconfigure_resolver()
                resolver = get_resolver()
                continue
            resolver.set_flags(dns.flags.RD | dns.flags.AD | dns.flags.CD)
            try:
                await loop.run_in_executor(
                    executor,
                    functools.partial(
                        resolver.query,
                        qname,
                        rdtype,
                        tcp=use_tcp,
                        raise_on_no_answer=False
                    ))
            except (dns.resolver.Timeout, TimeoutError):
                handle_timeout()
                continue
            except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
                pass
            raise ValidationError(
                "nameserver error, most likely DNSSEC validation failed",
            )
        break
    else:
        raise TimeoutError()

    return answer


async def lookup_srv(domain: bytes, service: str, transport: str = "tcp",
                     **kwargs):
    """
    Query the DNS for SRV records describing how the given `service` over the
    given `transport` is implemented for the given `domain`. `domain` must be
    an IDNA-encoded :class:`bytes` object; `service` must be a normal
    :class:`str`.

    Keyword arguments are passed to :func:`repeated_query`.

    Return a list of tuples ``(prio, weight, (hostname, port))``, where
    `hostname` is a IDNA-encoded :class:`bytes` object containing the hostname
    obtained from the SRV record. The other fields are also as obtained from
    the SRV records. The trailing dot is stripped from the `hostname`.

    If the DNS query returns an empty result, :data:`None` is returned. If any
    of the found SRV records has the root zone (``.``) as `hostname`, this
    indicates that the service is not available at the given `domain` and
    :class:`ValueError` is raised.
    """

    record = b".".join([
        b"_" + service.encode("ascii"),
        b"_" + transport.encode("ascii"),
        domain])

    answer = await repeated_query(
        record,
        dns.rdatatype.SRV,
        **kwargs)

    if answer is None:
        return None

    items = [
        (rec.priority, rec.weight, (str(rec.target), rec.port))
        for rec in answer
    ]

    for i, (prio, weight, (host, port)) in enumerate(items):
        if host == ".":
            raise ValueError(
                "protocol {!r} over {!r} not supported at {!r}".format(
                    service,
                    transport,
                    domain
                )
            )

        items[i] = (prio, weight, (
            host.rstrip(".").encode("ascii"),
            port))

    return items


async def lookup_tlsa(hostname, port, transport="tcp", require_ad=True,
                      **kwargs):
    """
    Query the DNS for TLSA records describing the certificates and/or keys to
    expect when contacting `hostname` at the given `port` over the given
    `transport`. `hostname` must be an IDNA-encoded :class:`bytes` object.

    The keyword arguments are passed to :func:`repeated_query`; `require_ad`
    defaults to :data:`True` here.

    Return a list of tuples ``(usage, selector, mtype, cert)`` which contains
    the information from the TLSA records.

    If no data is returned by the query, :data:`None` is returned instead.
    """
    record = b".".join([
        b"_" + str(port).encode("ascii"),
        b"_" + transport.encode("ascii"),
        hostname
    ])

    answer = await repeated_query(
        record,
        dns.rdatatype.TLSA,
        require_ad=require_ad,
        **kwargs)

    if answer is None:
        return None

    items = [
        (rec.usage, rec.selector, rec.mtype, rec.cert)
        for rec in answer
    ]

    return items


def group_and_order_srv_records(all_records, rng=None):
    """
    Order a list of SRV record information (as returned by :func:`lookup_srv`)
    and group and order them as specified by the RFC.

    Return an iterable, yielding each ``(hostname, port)`` tuple inside the
    SRV records in the order specified by the RFC. For hosts with the same
    priority, the given `rng` implementation is used (if none is given, the
    :mod:`random` module is used).
    """
    rng = rng or random

    all_records.sort(key=lambda x: x[:2])

    for priority, records in itertools.groupby(
            all_records,
            lambda x: x[0]):

        records = list(records)
        total_weight = sum(
            weight
            for _, weight, _ in records)

        while records:
            if len(records) == 1:
                yield records[0][-1]
                break

            value = rng.randint(0, total_weight)
            running_weight_sum = 0
            for i, (_, weight, addr) in enumerate(records):
                running_weight_sum += weight
                if running_weight_sum >= value:
                    yield addr
                    del records[i]
                    total_weight -= weight
                    break


async def find_xmpp_host_addr(loop, domain, attempts=3):
    domain = domain.encode("IDNA")

    items = await lookup_srv(
        service="xmpp-client",
        domain=domain,
        nattempts=attempts
    )

    if items is not None:
        return items

    return [(0, 0, (domain, 5222))]


async def find_xmpp_host_tlsa(loop, domain, attempts=3, require_ad=True):
    domain = domain.encode("IDNA")

    items = await lookup_tlsa(
        domain=domain,
        port=5222,
        nattempts=attempts,
        require_ad=require_ad
    )

    if items is not None:
        return items
    return []
