"""
:mod:`~aioxmpp.network` --- DNS resolution utilities
####################################################

This module uses DNSPython to resolve SRV records.

Querying SRV records
====================

.. autofunction:: find_xmpp_host_addr

.. autofunction:: lookup_srv

.. autofunction:: repeated_query

Ordering SRV records
====================

.. autofunction:: group_and_order_srv_records


"""

import asyncio
import functools
import itertools
import logging
import random

import dns
import dns.flags
import dns.resolver

logger = logging.getLogger(__name__)


def repeated_query(qname, rdtype,
                   nattempts=3,
                   resolver=None,
                   require_ad=False):
    """
    Repeatedly fire a DNS query until either the number of allowed attempts
    (``nattempts``) is excedeed or a result is found.

    ``qname`` must be the (IDNA encoded, as :class:`bytes`) name to query,
    ``rdtype`` the record type to query for. If `resolver` is not :data:`None`,
    it must be a DNSPython :class:`dns.resolver.Resolver` instance; if it is
    :data:`None`, the current default resolver is used.

    If `require_ad` is :data:`True`, the peer resolver is asked to do DNSSEC
    validation and if the AD flag is missing in the response,
    :class:`ValueError` is raised.

    The resolution automatically starts using the TCP transport after the first
    attempt.

    If no result is received before the number of allowed attempts is exceeded,
    :class:`TimeoutError` is raised.

    Return the result set or :data:`None` if the domain does not exist.
    """

    if nattempts <= 0:
        raise ValueError("Query cannot succeed with zero or less attempts")

    resolver = resolver or dns.resolver.get_default_resolver()
    for i in range(nattempts):
        try:
            if require_ad:
                resolver.set_flags(dns.flags.AD | dns.flags.RD)
            else:
                resolver.set_flags(None)
            answer = resolver.query(
                qname.decode("ascii"),
                rdtype,
                tcp=(i > 0),
            )
            if require_ad:
                if not (answer.response.flags & dns.flags.AD):
                    raise ValueError("DNSSEC validation not available")
            break
        except (TimeoutError, dns.resolver.Timeout):
            if i == 0:
                logger.warn("DNS is timing out, switching to TCP")
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
            return None
    else:
        raise TimeoutError("SRV query timed out")

    return answer


def lookup_srv(domain, service, transport=b"tcp", **kwargs):
    """
    Look up and format the SRV records for the given ``service`` over
    ``transport`` at the given ``domain``.

    Keyword arguments are passed to :func:`repeated_query`.

    Returns a list of tuples ``(prio, weight, (hostname, port))``, where
    ``hostname`` is a IDNA-encoded :class:`bytes` object containing the
    hostname obtained from the SRV record. The other fields are also those
    obtained from the SRV record.

    If the query returns an empty result, :data:`None` is returned.

    If any of the SRV records indicates the ``.`` host name (the root name),
    the domain indicates that the service is not available and
    :class:`ValueError` is raised.
    """

    record = b".".join([
        b"_" + service,
        b"_" + transport,
        domain])

    answer = repeated_query(
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
            raise ValueError("Protocol explicitly not supported")

        items[i] = (prio, weight, (
            host.rstrip(".").encode("ascii").decode("IDNA"),
            port))

    return items


def lookup_tlsa(domain, port, transport=b"tcp", require_ad=True, **kwargs):
    record = b".".join([
        b"_" + str(port).encode("ascii"),
        b"_" + transport,
        domain
    ])

    answer = repeated_query(
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

    all_records.sort()

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


@asyncio.coroutine
def find_xmpp_host_addr(loop, domain, attempts=3):
    domain = domain.encode("IDNA")

    items = yield from loop.run_in_executor(
        None,
        functools.partial(
            lookup_srv,
            service=b"xmpp-client",
            domain=domain,
            nattempts=attempts)
    )

    if items is not None:
        return items

    return [(0, 0, (domain, 5222))]


@asyncio.coroutine
def find_xmpp_host_tlsa(loop, domain, attempts=3, require_ad=True):
    domain = domain.encode("IDNA")

    items = yield from loop.run_in_executor(
        None,
        functools.partial(
            lookup_tlsa,
            domain=domain,
            port=5222,
            nattempts=attempts,
            require_ad=require_ad)
    )

    if items is not None:
        return items
    return []
