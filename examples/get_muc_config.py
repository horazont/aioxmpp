import configparser

import aioxmpp.muc
import aioxmpp.muc.xso

from framework import Example, exec_example


class ServerInfo(Example):
    def prepare_argparse(self):
        super().prepare_argparse()

        # this gives a nicer name in argparse errors
        def jid(s):
            return aioxmpp.JID.fromstr(s)

        self.argparse.add_argument(
            "--muc",
            type=jid,
            default=None,
            help="JID of the muc to query"
        )

    def configure(self):
        super().configure()

        self.muc_jid = self.args.muc
        if self.muc_jid is None:
            try:
                self.muc_jid = aioxmpp.JID.fromstr(
                    self.config.get("get_muc_config", "muc_jid")
                )
            except (configparser.NoSectionError,
                    configparser.NoOptionError):
                self.muc_jid = aioxmpp.JID.fromstr(
                    input("MUC JID> ")
                )

    def make_simple_client(self):
        client = super().make_simple_client()
        client.summon(aioxmpp.muc.Service)
        return client

    async def run_example(self):
        self.stop_event = self.make_sigint_event()
        await super().run_example()

    async def run_simple_example(self):
        config = await self.client.summon(aioxmpp.muc.Service).get_room_config(
            self.muc_jid
        )
        form = aioxmpp.muc.xso.ConfigurationForm.from_xso(config)

        print("name:", form.roomname.value)
        print("description:", form.roomdesc.value)

        print("moderated?", form.moderatedroom.value)

        print("members only?", form.membersonly.value)

        print("persistent?", form.persistentroom.value)


if __name__ == "__main__":
    exec_example(ServerInfo())
