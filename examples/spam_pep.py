########################################################################
# File name: spam_pep.py
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
import argparse
import asyncio
import copy
import getpass
import logging
import os
import signal
import sys

import lxml.etree as etree

import aioxmpp
import aioxmpp.pep
import aioxmpp.pubsub.xso


logger = logging.getLogger("spam_pep")


# this gives a nicer name in argparse errors
def jid(s):
    return aioxmpp.JID.fromstr(s)


def notify_logger(filter_sender, filter_node):
    def log_notify(sender, node, item, **kwargs):
        if sender != filter_sender or node != filter_node:
            return
        logger.info("Received item notify: %s", item)

    return log_notify


def make_sigint_event():
    event = asyncio.Event()
    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGINT, event.set)
    loop.add_signal_handler(signal.SIGTERM, event.set)
    logger.info("Received SIGINT/SIGTERM, initiating clean shutdown")
    return event


def make_publish_iq(to, node, payload):
    # we have to compose our own publish request, since PubSubClient does
    # not support publishing arbitrary XML
    publish = aioxmpp.pubsub.xso.Publish()
    publish.node = node
    publish.item = aioxmpp.pubsub.xso.Item()
    publish.item.unregistered_payload[:] = [copy.deepcopy(payload)]

    return aioxmpp.IQ(
        type_=aioxmpp.IQType.SET,
        to=to,
        payload=aioxmpp.pubsub.xso.Request(publish)
    )


async def wait_for_notify_impl(client, node, payload, notify_received):
    logger.info("Publisher ready")
    while True:
        logger.info("Publisher waiting for notify/go")
        await notify_received.wait()
        notify_received.clear()

        logger.info("Publishing new item")
        try:
            await client.send(make_publish_iq(
                client.local_jid.bare(),
                node,
                payload,
            ))
            logger.info("Item published!")
        except aioxmpp.errors.XMPPError:
            logger.error("error on publish", exc_info=True)
            raise


async def spam_impl(client, node, payload):
    logger.info("Publisher ready")
    while True:
        logger.info("Publishing new item")
        try:
            await client.send(make_publish_iq(
                client.local_jid.bare(),
                node,
                payload,
            ))
            logger.info("Item published!")
        except aioxmpp.errors.XMPPError as exc:
            logger.error("error on publish (ignoring): %s", exc)


async def amain(args, password, payload):
    logger.info("Preparing client")
    client = aioxmpp.PresenceManagedClient(
        args.local_jid,
        aioxmpp.make_security_layer(password)
    )
    pubsub = client.summon(aioxmpp.PubSubClient)
    pep = client.summon(aioxmpp.pep.PEPClient)
    claimed_node = pep.claim_pep_node(
        args.node,
        register_feature=True,
        notify=True,
    )

    workers = []

    notify_received = asyncio.Event()
    if args.wait_for_notify:
        workers.append(asyncio.ensure_future(
            wait_for_notify_impl(client, args.node, payload, notify_received)
        ))

        def signal_notify(*args, **kwargs):
            notify_received.set()

        pubsub.on_item_published.connect(signal_notify)

    pubsub.on_item_published.connect(notify_logger(
        args.local_jid.bare(),
        args.node,
    ))

    stop_signal = make_sigint_event()

    logger.info("Connecting as %s...", args.local_jid)
    async with client.connected() as stream:
        logger.info("Connected as %s!", stream.local_jid)

        notify_received.set()
        if not args.wait_for_notify:
            for i in range(args.parallel):
                workers.append(asyncio.ensure_future(
                    spam_impl(client, args.node, payload)
                ))

        await stop_signal.wait()
        logger.info("Shutting down...")
        for worker in workers:
            worker.cancel()

        for worker in workers:
            try:
                await worker
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.error("worker died", exc_info=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--local-jid",
        metavar="JID",
        type=jid,
        help="Address to connect with (full or bare)"
    )

    parser.add_argument(
        "-v",
        action="count",
        default=0,
        help="Increase verbosity of aioxmpp",
        dest="verbosity",
    )

    parser.add_argument(
        "node",
        help="Node to spam"
    )

    parser.add_argument(
        "payload_file",
        metavar="FILE",
        type=argparse.FileType("rb"),
        help="PubSub payload to submit"
    )

    mutex_group = parser.add_mutually_exclusive_group(
        required=True
    )

    mutex_group.add_argument(
        "-P", "--parallel",
        metavar="INT",
        type=int,
        help="If used, INT requests will be fired in parallel and kept "
        "in-flight all the time until the program is interrupted.",
    )

    mutex_group.add_argument(
        "-w", "--wait-for-notify",
        action="store_true",
        default=False,
        help="Serial mode where a publish request is made and only after"
        " receiving the notification a new request is fired",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level={
            0: logging.ERROR,
            1: logging.WARNING,
            2: logging.INFO,
        }.get(args.verbosity, logging.DEBUG),
    )
    logger.setLevel(logging.INFO)

    with args.payload_file as f:
        payload = etree.fromstring(f.read())

    try:
        password = os.environ["SPAM_PASSWORD"]
    except KeyError:
        print("SPAM_PASSWORD is unset, asking interactively")
        password = getpass.getpass()

    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(amain(args, password, payload))
    finally:
        loop.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
