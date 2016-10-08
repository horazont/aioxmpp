#!/usr/bin/env python3
########################################################################
# File name: xmpp_bridge.py
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
# General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this program.  If not, see
# <http://www.gnu.org/licenses/>.
#
########################################################################
import asyncio
import asyncio.streams
import os
import signal
import sys

import aioxmpp


async def stdout_writer():
    """
    This is a bit complex, as stdout can be a pipe or a file.

    If it is a file, we cannot use
    :meth:`asycnio.BaseEventLoop.connect_write_pipe`.
    """
    if sys.stdout.seekable():
        # it’s a file
        return sys.stdout.buffer.raw

    if os.isatty(sys.stdin.fileno()):
        # it’s a tty, use fd 0
        fd_to_use = 0
    else:
        fd_to_use = 1

    twrite, pwrite = await loop.connect_write_pipe(
        asyncio.streams.FlowControlMixin,
        os.fdopen(fd_to_use, "wb"),
    )

    swrite = asyncio.StreamWriter(
        twrite,
        pwrite,
        None,
        loop,
    )

    return swrite


async def main(local, password, peer,
               strip_newlines, add_newlines):
    loop = asyncio.get_event_loop()
    swrite = await stdout_writer()

    sread = asyncio.StreamReader()
    tread, pread = await loop.connect_read_pipe(
        lambda: asyncio.StreamReaderProtocol(sread),
        sys.stdin,
    )

    client = aioxmpp.PresenceManagedClient(
        local,
        aioxmpp.make_security_layer(
            password,
        )
    )

    sigint = asyncio.Event()
    loop.add_signal_handler(signal.SIGINT, sigint.set)
    loop.add_signal_handler(signal.SIGTERM, sigint.set)

    def recv(message):
        body = message.body.lookup(
            [aioxmpp.structs.LanguageRange.fromstr("*")]
        )
        if add_newlines:
            body += "\n"
        swrite.write(body.encode("utf-8"))

    client.stream.register_message_callback(
        "chat",
        peer,
        recv
    )

    sigint_future = asyncio.ensure_future(sigint.wait())
    read_future = asyncio.ensure_future(sread.readline())

    try:
        async with client.connected() as stream:
            while True:
                done, pending = await asyncio.wait(
                    [
                        sigint_future,
                        read_future,
                    ],
                    return_when=asyncio.FIRST_COMPLETED,
                )

                if sigint_future in done:
                    break

                if read_future in done:
                    line = read_future.result().decode()
                    if not line:
                        break

                    if strip_newlines:
                        line = line.rstrip()

                    msg = aioxmpp.Message(
                        type_="chat",
                        to=peer,
                    )
                    msg.body[None] = line

                    await stream.send_and_wait_for_sent(msg)

                    read_future = asyncio.ensure_future(
                        sread.readline()
                    )

    finally:
        sigint_future.cancel()
        read_future.cancel()


def jid(s):
    return aioxmpp.JID.fromstr(s)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="""
        Send lines from stdin to the given peer and print messages received
        from the peer to stdout.
        """,
        epilog="""
        The password must be set in the XMPP_BRIDGE_PASSWORD environment
        variable.
        """
    )

    parser.add_argument(
        "--no-strip-newlines",
        dest="strip_newlines",
        action="store_false",
        default=True,
        help="Disable stripping newlines from stdin"
    )

    parser.add_argument(
        "--no-add-newlines",
        dest="add_newlines",
        action="store_false",
        default=True,
        help="Disable adding newlines to stdout"
    )

    parser.add_argument(
        "local",
        help="JID to bind to",
        type=jid,
    )
    parser.add_argument(
        "peer",
        help="JID of the peer to send messages to",
        type=jid,
    )

    args = parser.parse_args()

    try:
        password = os.environ["XMPP_BRIDGE_PASSWORD"]
    except KeyError:
        parser.print_help()
        print("XMPP_BRIDGE_PASSWORD is not set", file=sys.stderr)
        sys.exit(1)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(
        args.local, password, args.peer,
        args.strip_newlines,
        args.add_newlines,
    ))
    loop.close()
