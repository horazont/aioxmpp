import asyncio
import itertools
import logging
import socket

import dns
import dns.resolver

logger = logging.getLogger(__name__)

def lookup_srv(record, attempts):
    for i in range(attempts):
        try:
            answer = dns.resolver.query(
                record,
                dns.rdatatype.SRV)
            break
        except dns.resolver.Timeout:
            if i == 0:
                logger.warn("DNS is timing out")
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
            return None
    else:
        raise TimeoutError("SRV query timed out")

    items = [
        (rec.priority, rec.weight, (str(rec.target).rstrip("."), rec.port))
        for rec in answer
    ]

    if any(host == '.' for _, _, (host, _) in items):
        raise ValueError("Protocol explicitly not supported.")

    return items

def group_and_order_srv_records(all_records):
    all_records.sort()

    for priority, records in itertools.groupby(
            all_records,
            lambda x: x[0]):

        records = list(records)
        if len(records) == 1:
            yield records[0][-1]
            continue

        total_weight = sum(
            weight
            for _, weight, _ in records)
        while records:
            value = random.randint(0, total_weight)
            for i, (_, weight, addr) in enumerate(records):
                if weight >= value:
                    yield addr
                    del records[i]
                    total_weight -= weight
                    break


@asyncio.coroutine
def find_xmpp_host_addr(loop, domain, attempts=3):
    domain = domain.encode("IDNA")

    items = yield from loop.run_in_executor(
        None,
        lookup_srv,
        "_xmpp-client._tcp."+domain.decode("ascii"),
        attempts)

    if items is not None:
        return items

    return [(0, 0, (domain, 5222))]
