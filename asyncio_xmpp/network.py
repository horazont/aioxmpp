import asyncio
import functools
import itertools
import logging
import random
import socket

import dns
import dns.resolver

logger = logging.getLogger(__name__)

def repeated_query(qname, rdtype, nattempts, resolver=None):
    if nattempts <= 0:
        raise ValueError("Query cannot succeed with zero or less attempts")


    resolver = resolver or dns.resolver.get_default_resolver()
    for i in range(nattempts):
        try:
            answer = resolver.query(qname, rdtype, tcp=i>0)
            break
        except (TimeoutError, dns.resolver.Timeout):
            if i == 0:
                logger.warn("DNS is timing out, switching to TCP")
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
            return None
    else:
        raise TimeoutError("SRV query timed out")

    return answer

def lookup_srv(domain, service, transport=b"tcp", nattempts=3, resolver=None):
    record = b".".join([
        b"_"+service,
        b"_"+transport,
        domain])

    answer = repeated_query(
        record,
        dns.rdatatype.SRV,
        nattempts=nattempts,
        resolver=resolver)

    if answer is None:
        return None

    items = [
        (rec.priority, rec.weight, (rec.target, rec.port))
        for rec in answer
    ]

    for i, (prio, weight, (host, port)) in enumerate(items):
        if host == b".":
            raise ValueError("Protocol explicitly not supported")

        items[i] = (prio, weight, (host.rstrip(b".").decode("IDNA"), port))

    return items

def group_and_order_srv_records(all_records, rng=None):
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
