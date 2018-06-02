#!/usr/bin/env python3
########################################################################
# File name: log-to-scs.py
# This file is part of: aioxmpp
#
# LICENSE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at
# your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
########################################################################
import ast
import enum
import re

import lxml.etree as etree

import aioxmpp


_client_prefix = r"^aioxmpp\.e2etest\.provision\.client(?P<client_id>[0-9]+)"


SENT_LINE = re.compile(
    _client_prefix + r"\.XMLStream:\ DEBUG:\ SENT\ (?P<bytes>b.+)$",
    re.VERBOSE
)


RECV_LINE = re.compile(
    _client_prefix + r"\.XMLStream:\ DEBUG:\ RECV\ (?P<bytes>b.+)$",
    re.VERBOSE
)

JID_LINE = re.compile(
    _client_prefix + r":\ INFO:\ bound\ to\ jid:\ (?P<jid>.+)",
    re.VERBOSE,
)


def _parse_stream_bytes(b):
    FOOTER = b"</stream:stream>"
    b = ast.literal_eval(b)
    # stream header, ignore
    if b.startswith(b"<?xml"):
        return
    if b.startswith(FOOTER):
        return
    if b.endswith(FOOTER):
        b = b[:-len(FOOTER)]
    if not b.strip():
        return
    try:
        tree = etree.fromstring(b"<root xmlns:stream='http://etherx.jabber.org/streams'>"+b+b"</root>")
    except:
        print(b)
        raise
    yield from tree


def _wrap_bytes(match, wrapper_name):
    client_id = int(match["client_id"])
    for piece in _parse_stream_bytes(match["bytes"]):
        yield {
            "client_id": client_id,
            wrapper_name: {
                "xml": piece
            }
        }


def parse_sent_line(match):
    yield from _wrap_bytes(match, "sent")


def parse_recv_line(match):
    yield from _wrap_bytes(match, "recv")


def parse_jid_line(match):
    yield {
        "client_id": int(match["client_id"]),
        "bound": {
            "jid": aioxmpp.JID.fromstr(match["jid"]),
        }
    }


line_parsers = [
    (SENT_LINE, parse_sent_line),
    (RECV_LINE, parse_recv_line),
    (JID_LINE, parse_jid_line),
]


def parse_line(l):
    for rx, parser in line_parsers:
        match = rx.match(l)
        if match is None:
            continue
        yield from parser(match.groupdict())


def parse_lines(ls):
    for line in ls:
        parsed = parse_line(line)
        if parsed is not None:
            yield from parsed


def xmllines(tree):
    serialised = etree.tostring(tree, encoding="utf-8", pretty_print=True)
    lines = serialised.decode("utf-8").split("\n")
    return [line for line in lines if line.strip()]


def filter_sessions(actions):
    ids_to_drop = set()
    for action in actions:
        xml = action.get("sent", action.get("recv", {})).get("xml")
        if xml is None:
            yield action
            continue

        id_ = xml.get("id")
        key = (action["client_id"], id_)
        if key in ids_to_drop:
            ids_to_drop.discard(key)
            continue

        if xml.tag == "iq" and len(xml) > 0:
            # IQ with payload
            if xml[0].tag == "{urn:ietf:params:xml:ns:xmpp-session}session":
                # drop!
                ids_to_drop.add(key)
                continue

        yield action


def filter_serverdisco(actions):
    ids_to_drop = set()
    client_jids = {}
    for action in actions:
        try:
            jid = action["bound"]["jid"]
        except KeyError:
            pass
        else:
            client_jids[action["client_id"]] = jid

        xml = action.get("sent", action.get("recv", {})).get("xml")
        if xml is None:
            yield action
            continue

        id_ = xml.get("id")
        key = (action["client_id"], id_)
        if key in ids_to_drop:
            ids_to_drop.discard(key)
            continue

        try:
            client_jid = client_jids[action["client_id"]]
        except KeyError:
            yield action
            continue

        if (xml.tag == "iq" and len(xml) > 0 and
                xml.get("to") == client_jid.domain and
                xml[0].tag == "{http://jabber.org/protocol/disco#info}query"):
            # drop!
            ids_to_drop.add(key)
            continue

        yield action


class FinalAction(enum.Enum):
    CONNECT = "connects"
    SEND = "sends"
    RECEIVE = "receives"


def generate(actions, out, characters=[], remove_clients=[]):
    client_names = characters or [
        "Juliet",
        "Romeo",
    ]

    clients = {}
    result_actions = []

    def bind_client(client_id, jid):
        clients[client_id] = {
            "id": client_id,
            "name": client_names.pop(0),
            "jid": jid,
        }
        result_actions.append(
            (client_id, (FinalAction.CONNECT, None))
        )

    for action in actions:
        try:
            client = clients[action["client_id"]]
        except KeyError:
            if "bound" in action and action["client_id"] not in remove_clients:
                bind_client(action["client_id"], action["bound"]["jid"])
            continue

        if "sent" in action:
            result_actions.append(
                (client["id"], (FinalAction.SEND, action["sent"]["xml"]))
            )
        elif "recv" in action:
            result_actions.append(
                (client["id"], (FinalAction.RECEIVE, action["recv"]["xml"]))
            )
        else:
            raise RuntimeError("unknown action: {}".format(action))

    for client in sorted(clients.values(), key=lambda x: x["id"]):
        print(
            "[Client] {name}\n\tjid: {jid}\n\tpassword: password\n".format(
                **client,
            ),
            file=out,
        )

    print("---------\n")

    for client_id, (action, xml) in result_actions:
        client = clients[client_id]
        print(
            "{client[name]} {action.value}".format(
                client=client, action=action
            ),
            end="",
            file=out
        )
        if xml is not None:
            print(":\n\t{}".format("\n\t".join(xmllines(xml))), file=out)
        else:
            print(file=out)
        print(file=out)


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--characters",
        nargs="+",
        dest="characters",
        default=[],
    )
    parser.add_argument(
        "--strip-serverdisco",
        action="append_const",
        dest="add_filters",
        default=[],
        const=filter_serverdisco,
    )
    parser.add_argument(
        "--no-strip-sessions",
        action="append_const",
        dest="remove_filters",
        default=[],
        const=filter_sessions,
    )
    parser.add_argument(
        "--remove-client",
        action="append",
        dest="remove_clients",
        default=[],
        type=int,
    )

    parser.add_argument(
        "-o", "--output",
        default=sys.stdout,
        type=argparse.FileType("w"),
    )

    parser.add_argument(
        "input",
        nargs="?",
        default=sys.stdin,
        type=argparse.FileType("r"),
    )

    args = parser.parse_args()

    filters = [filter_sessions]
    for to_add in args.add_filters:
        filters.append(to_add)
    for to_remove in args.remove_filters:
        try:
            filters.remove(to_remove)
        except ValueError:
            pass

    with args.input as f:
        actions = list(parse_lines(f))

    for filter_func in filters:
        actions = filter_func(actions)

    with args.output as f:
        generate(actions, f, characters=list(args.characters),
                 remove_clients=args.remove_clients)

