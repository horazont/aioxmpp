#!/usr/bin/env python3
import asyncio
import json
import logging
import pathlib
import socket
import signal

import toml

import aioxmpp


class MessageProtocol(asyncio.DatagramProtocol):
    def __init__(self, queue):
        super().__init__()
        self.logger = logging.getLogger(type(self).__name__)
        self.queue = queue

    def datagram_received(self, data, addr):
        try:
            parsed = json.loads(data.decode("utf-8"))
        except Exception:
            self.logger.error("failed to parse client message %r",
                              data,
                              exc_info=True)
            return

        try:
            self.queue.put_nowait(parsed)
        except asyncio.QueueFull:
            self.logger.error("input queue full! dropped message %r",
                              parsed)


async def process_item(item, rooms, logger):
    target_rooms = rooms.keys()

    tokens = []

    for room_address in target_rooms:
        try:
            room_info = rooms[room_address]
        except KeyError:
            continue

        body_parts = []

        if room_info["head_format"]:
            body_parts.append(
                room_info["head_format"].format(
                    nitems=len(item["items"]),
                    root_item=item,
                )
            )

        for sub_item in item["items"]:
            required_fields = room_info["required_fields"]
            if required_fields:
                item_fields = set(sub_item.keys()) & required_fields
                if len(item_fields) < len(required_fields):
                    continue

            format_ = room_info["format"]
            if format_:
                body = format_.format(**sub_item)
            else:
                body = repr(item)

            body_parts.append(body)

        msg = aioxmpp.Message(
            type_=aioxmpp.MessageType.GROUPCHAT,
        )
        msg.body[None] = "\n".join(body_parts)

        tokens.append(asyncio.ensure_future(
            room_info["room"].send_message(msg)
        ))

    if not tokens:
        logger.warning("item %r generated no message!", item)
        return

    await asyncio.wait(tokens, return_when=asyncio.ALL_COMPLETED)


async def process_queue(queue, rooms):
    logger = logging.getLogger("processor")

    while True:
        item = await queue.get()
        try:
            await process_item(item, rooms, logger)
        except Exception:
            logger.error("failed to process item!", exc_info=True)
            continue


async def amain(loop, xmpp_cfg, unix_cfg, mucs):
    message_queue = asyncio.Queue(maxsize=16)
    message_handler = MessageProtocol(message_queue)

    sigint_received = asyncio.Event()
    sigint_future = asyncio.ensure_future(sigint_received.wait())

    loop.add_signal_handler(signal.SIGINT, sigint_received.set)
    loop.add_signal_handler(signal.SIGTERM, sigint_received.set)

    socket_path, = unix_cfg

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM, 0)
    sock.bind(str(socket_path))

    unix_transport, _ = await loop.create_datagram_endpoint(
        lambda: message_handler,
        sock=sock,
    )

    address, password = xmpp_cfg

    xmpp_client = aioxmpp.Client(
        address,
        aioxmpp.make_security_layer(password)
    )

    muc_client = xmpp_client.summon(aioxmpp.MUCClient)

    try:
        async with xmpp_client.connected() as stream:
            rooms = {}
            for muc_info in mucs:
                room, fut = muc_client.join(
                    muc_info["address"],
                    muc_info["nickname"],
                    autorejoin=True,
                )

                await fut
                muc_info["room"] = room
                rooms[muc_info["address"]] = muc_info

            processor = asyncio.ensure_future(process_queue(
                message_queue,
                rooms
            ))

            done, pending = await asyncio.wait(
                [
                    processor,
                    sigint_future,
                ],
                return_when=asyncio.FIRST_COMPLETED,
            )

            if sigint_future in done:
                if not processor.done():
                    processor.cancel()
                try:
                    await processor
                except asyncio.CancelledError:
                    pass
                return

            if processor in done:
                processor.result()
                raise RuntimeError("processor exited early!")
    finally:
        if not sigint_future.done():
            sigint_future.cancel()
        unix_transport.close()


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c", "--config",
        type=pathlib.Path,
        default=pathlib.Path.cwd() / "config.toml",
        help="Path to config file (default: ./config.toml)"
    )
    parser.add_argument(
        "-v", "--verbose",
        default=0,
        dest="verbosity",
        action="count",
        help="Increase verbosity (up to -vvv)"
    )

    args = parser.parse_args()

    logging.basicConfig(
        level={
            0: logging.ERROR,
            1: logging.WARNING,
            2: logging.INFO,
        }.get(args.verbosity, logging.DEBUG)
    )

    with args.config.open("r") as f:
        config = toml.load(f)

    address = aioxmpp.JID.fromstr(config["xmpp"]["account"])
    password = config["xmpp"]["password"]

    socket_path = pathlib.Path(config["unix"]["path"])

    mucs = []
    for muc_cfg in config["xmpp"]["muc"]:
        mucs.append(
            {
                "address": aioxmpp.JID.fromstr(muc_cfg["address"]),
                "nickname": muc_cfg.get("nickname", address.localpart),
                "format": muc_cfg.get("format"),
                "required_fields": frozenset(muc_cfg.get("required_fields", [])),
                "head_format": muc_cfg.get("head_format"),
            }
        )

    if socket_path.exists():
        if not socket_path.is_socket():
            raise RuntimeError("{} exists and is not a socket!".format(
                socket_path,
            ))

        # FIXME: do not unlink the socket if it’s still live; abort instead.
        socket_path.unlink()

    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(amain(
            loop,
            (address, password),
            (socket_path, ),
            mucs,
        ))
    finally:
        loop.close()


if __name__ == "__main__":
    main()
