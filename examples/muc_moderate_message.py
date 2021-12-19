########################################################################
# File name: muc_logger.py
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
import configparser
import locale

from datetime import datetime

import aioxmpp.muc
import aioxmpp.structs

from framework import Example, exec_example


class Moderate(aioxmpp.xso.XSO):
    TAG = ("urn:xmpp:message-moderate:0", "moderate")

    retract_flag = aioxmpp.xso.ChildFlag(("urn:xmpp:message-retract:0", "retract"))

    reason = aioxmpp.xso.ChildText(("urn:xmpp:message-moderate:0", "reason"))


@aioxmpp.IQ.as_payload_class
class ApplyTo(aioxmpp.xso.XSO):
    TAG = ("urn:xmpp:fasten:0", "apply-to")

    id_ = aioxmpp.xso.Attr("id")

    payload = aioxmpp.xso.Child([Moderate])


class Moderator(Example):
    def prepare_argparse(self):
        super().prepare_argparse()

        # this gives a nicer name in argparse errors
        def jid(s):
            return aioxmpp.JID.fromstr(s)

        self.argparse.add_argument(
            "--muc",
            type=jid,
            default=None,
            help="JID of the muc to join"
        )

        self.argparse.add_argument(
            "--nick",
            default=None,
            help="Nick name to use"
        )

        self.argparse.add_argument(
            "msgid",
        )

        self.argparse.add_argument(
            "reason",
        )

    def configure(self):
        super().configure()

        self.muc_jid = self.args.muc
        if self.muc_jid is None:
            try:
                self.muc_jid = aioxmpp.JID.fromstr(
                    self.config.get("muc_logger", "muc_jid")
                )
            except (configparser.NoSectionError,
                    configparser.NoOptionError):
                self.muc_jid = aioxmpp.JID.fromstr(
                    input("MUC JID> ")
                )

        self.muc_nick = self.args.nick
        if self.muc_nick is None:
            try:
                self.muc_nick = self.config.get("muc_logger", "nick")
            except (configparser.NoSectionError,
                    configparser.NoOptionError):
                self.muc_nick = input("Nickname> ")

    def make_simple_client(self):
        client = super().make_simple_client()
        muc = client.summon(aioxmpp.MUCClient)
        room, self.room_future = muc.join(
            self.muc_jid,
            self.muc_nick
        )

        return client

    async def run_example(self):
        self.stop_event = self.make_sigint_event()
        await super().run_example()

    async def run_simple_example(self):
        print("waiting to join room...")
        done, pending = await asyncio.wait(
            [
                self.room_future,
                asyncio.create_task(self.stop_event.wait()),
            ],
            return_when=asyncio.FIRST_COMPLETED
        )
        if self.room_future not in done:
            self.room_future.cancel()
            return

        for fut in pending:
            fut.cancel()

        payload = ApplyTo()
        payload.id_ = self.args.msgid
        payload.payload = Moderate()
        payload.payload.reason = self.args.reason
        payload.payload.retract_flag = True

        await self.client.send(aioxmpp.IQ(
            type_=aioxmpp.IQType.SET,
            to=self.muc_jid,
            payload=payload,
        ))


if __name__ == "__main__":
    exec_example(Moderator())
