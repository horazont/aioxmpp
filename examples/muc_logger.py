import asyncio
import configparser
import locale

from datetime import datetime

import aioxmpp.muc
import aioxmpp.structs

from framework import Example, exec_example


class MucLogger(Example):
    def prepare_argparse(self):
        super().prepare_argparse()

        language_name = locale.getlocale()[0]
        if language_name == "C":
            language_name = "en-gb"

        def language_range(s):
            return aioxmpp.structs.LanguageRange.fromstr(
                s.replace("_", "-")
            )

        default_language = language_range(language_name)

        self.argparse.add_argument(
            "--language",
            default=language_range(language_name),
            type=language_range,
            help="Preferred language: if messages are sent with "
            "multiple languages, this is the language shown "
            "(default: {})".format(default_language),
        )

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

    def configure(self):
        super().configure()

        self.language_selectors = [
            self.args.language,
            aioxmpp.structs.LanguageRange.fromstr("*")
        ]

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
        muc = client.summon(aioxmpp.muc.Service)
        room, self.room_future = muc.join(
            self.muc_jid,
            self.muc_nick
        )

        room.on_message.connect(self._on_message)
        room.on_subject_change.connect(self._on_subject_change)
        room.on_enter.connect(self._on_enter)
        room.on_exit.connect(self._on_exit)
        room.on_leave.connect(self._on_leave)
        room.on_join.connect(self._on_join)

        return client

    def _on_message(self, message, **kwargs):
        print("{} {}: {}".format(
            datetime.utcnow().isoformat(),
            message.from_.resource,
            message.body.lookup(self.language_selectors),
        ))

    def _on_subject_change(self, message, subject, **kwargs):
        print("{} *** topic set by {}: {}".format(
            datetime.utcnow().isoformat(),
            message.from_.resource,
            subject.lookup(self.language_selectors),
        ))

    def _on_enter(self, presence, occupant=None, **kwargs):
        print("{} *** entered room {}".format(
            datetime.utcnow().isoformat(),
            presence.from_.bare()
        ))

    def _on_exit(self, presence, occupant=None, **kwargs):
        print("{} *** left room {}".format(
            datetime.utcnow().isoformat(),
            presence.from_.bare()
        ))

    def _on_join(self, presence, occupant=None, **kwargs):
        print("{} *** {} [{}] entered room".format(
            datetime.utcnow().isoformat(),
            occupant.nick,
            occupant.jid,
        ))

    def _on_leave(self, presence, occupant, mode, **kwargs):
        print("{} *** {} [{}] left room ({})".format(
            datetime.utcnow().isoformat(),
            occupant.nick,
            occupant.jid,
            mode
        ))

    async def run_example(self):
        self.stop_event = self.make_sigint_event()
        await super().run_example()

    async def run_simple_example(self):
        print("waiting to join room...")
        done, pending = await asyncio.wait(
            [
                self.room_future,
                self.stop_event.wait(),
            ],
            return_when=asyncio.FIRST_COMPLETED
        )
        if self.room_future not in done:
            self.room_future.cancel()
            return

        for fut in pending:
            fut.cancel()

        await self.stop_event.wait()


if __name__ == "__main__":
    exec_example(MucLogger())
