import sys

import aioxmpp.disco
import aioxmpp.xso

from framework import Example, exec_example


# custom XEP definitions from XEP-0191


# this XSO represents a single block list item.
class BlockItem(aioxmpp.xso.XSO):
    # define the tag we are matching for
    # tags consist of an XML namespace URI and an XML element
    TAG = ("urn:xmpp:blocking", "item")

    # bind the ``jid`` python attribute to refer to the ``jid`` XML attribute.
    # in addition, automatic conversion between actual JID objects and XML
    # character data is requested by specifying the `type_` argument as
    # xso.JID() object.
    jid = aioxmpp.xso.Attr(
        "jid",
        type_=aioxmpp.xso.JID()
    )


# we now declare a custom type to convert between JID objects and BlockItem
# instances.
# we can use this custom type together with xso.ChildValueList to access the
# list of <item xmlns="urn:xmpp:blocking" /> elements like a normal python list
# of JIDs.
class BlockItemType(aioxmpp.xso.AbstractType):
    # parse converts from the "raw", formatted representation (usually XML
    # character data strings, in this case it’s a BlockItem instance) to the
    # "rich" python representation, in this case a JID object
    def parse(self, item):
        return item.jid

    # format converts back from the "rich" python representation (a JID object)
    # to the "raw" XML stream representation, in this case a BlockItem XSO
    def format(self, jid):
        item = BlockItem()
        item.jid = jid
        return item

    # we have to tell the XSO framework what type the format method will be
    # returning.
    def get_formatted_type(self):
        return BlockItem


# the decorator tells the IQ stanza class that this is a valid payload; that is
# required to be able to *receive* payloads of this type (sending works without
# that decorator, but is not recommended)
@aioxmpp.stanza.IQ.as_payload_class
class BlockList(aioxmpp.xso.XSO):
    TAG = ("urn:xmpp:blocking", "blocklist")

    # xso.ChildValueList uses an AbstractType (like the one we defined above)
    # to convert between child XSO instances and other python objects.
    # it is accessed like a normal list, but when parsing/serialising, the
    # elements are converted to XML structures using the given type.
    items = aioxmpp.xso.ChildValueList(
        BlockItemType()
    )


class BlockJID(Example):
    def prepare_argparse(self):
        super().prepare_argparse()

        # this gives a nicer name in argparse errors
        def jid(s):
            return aioxmpp.JID.fromstr(s)

        self.argparse.add_argument(
            "--add",
            dest="jids_to_block",
            default=[],
            action="append",
            type=jid,
            metavar="JID",
            help="JID to block (can be specified multiple times)",
        )

        self.argparse.add_argument(
            "-l", "--list",
            action="store_true",
            default=False,
            dest="show_list",
            help="If given, prints the block list at the end of the operation",
        )

    def configure(self):
        super().configure()

        if not self.args.jids_to_block and not self.args.show_list:
            print("nothing to do!", file=sys.stderr)
            print("specify --add and/or --list", file=sys.stderr)
            sys.exit(1)

    async def run_simple_example(self):
        # we are polite and ask the server whether it actually supports the
        # XEP-0191 block list protocol
        disco = self.client.summon(aioxmpp.disco.Service)
        server_info = await disco.query_info(self.client.local_jid.replace(
            resource=None,
            localpart=None,
        ))

        if "urn:xmpp:blocking" not in server_info.features:
            print("server does not support block lists!", file=sys.stderr)
            sys.exit(2)

        # now that we are sure that the server supports it, we can send
        # requests.

        if self.args.jids_to_block:
            # construct the block list request and add the JIDs by simply
            # placing them in the items attribute
            blocklist = BlockList()

            # note that self.args.jids_to_block is a list of JID objects, not a
            # list of strings (that would not work, because BlockItem requires
            # the jid attribute to be a JID)
            blocklist.items[:] = self.args.jids_to_block

            # construct the IQ request
            iq = aioxmpp.IQ(
                type_=aioxmpp.IQType.SET,
                payload=blocklist,
            )

            # send it and wait for a response
            await self.client.stream.send_iq_and_wait_for_reply(
                iq
            )
        else:
            print("nothing to block")

        if self.args.show_list:
            # construct the request to retrieve the block list
            iq = aioxmpp.IQ(
                type_=aioxmpp.IQType.GET,
                payload=BlockList(),
            )

            result = await self.client.stream.send_iq_and_wait_for_reply(
                iq,
            )

            # print all the items; again, .items is a list of JIDs
            print("current block list:")
            for item in result.items:
                print(" ", item)


if __name__ == "__main__":
    exec_example(BlockJID())
