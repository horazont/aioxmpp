import aioxmpp.xml
from aioxmpp.utils import *

from .stanza import *
from .client import *

def register(lookup):
    ns = lookup.get_namespace(namespaces.roster)
    ns["query"] = Query
    ns["item"] = Item
    ns["group"] = Group

register(aioxmpp.xml.lookup)
