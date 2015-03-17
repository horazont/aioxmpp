from aioxmpp.stanza_props import *
import aioxmpp.stanza as stanza

from aioxmpp.utils import *

import aioxmpp.plugins.xep0030.stanza

namespaces.xep0060_pubsub = "http://jabber.org/protocol/pubsub"
namespaces.xep0060_pubsub_errors = "http://jabber.org/protocol/pubsub#errors"
namespaces.xep0060_pubsub_event = "http://jabber.org/protocol/pubsub#event"
namespaces.xep0060_pubsub_owner = "http://jabber.org/protocol/pubsub#owner"

class PubSub(stanza.StanzaElementBase):
    TAG = "{{{}}}pubsub".format(namespaces.xep0060_pubsub)

class Create(stanza.StanzaElementBase):
    TAG = "{{{}}}create".format(namespaces.xep0060_pubsub)

    node = xmlattr()
