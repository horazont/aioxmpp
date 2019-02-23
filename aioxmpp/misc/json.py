import aioxmpp.xso as xso
import aioxmpp.pubsub.xso

from aioxmpp.utils import namespaces


namespaces.xep0335_json = "urn:xmpp:json:0"


@aioxmpp.pubsub.xso.as_payload_class
class JSONContainer(xso.XSO):
    """
    XSO which represents the JSON container specified in :xep:`335`.

    This is a full XSO and not an attribute descriptor. It is registered as
    pubsub payload by default.
    """

    TAG = (namespaces.xep0335_json, "json")

    json_data = xso.Text(
        type_=xso.JSON(),
    )

    def __init__(self, json_data=None):
        super().__init__()
        self.json_data = json_data


class JSONContainerType(xso.AbstractElementType):
    """
    XSO element type to unwrap JSON container payloads specified in :xep:`335`.

    This type is designed to be used with the ChildValue* descriptors provided
    in :mod:`aioxmpp.xso`, for example with :class:`aioxmpp.xso.ChildValue` or
    :class:`aioxmpp.xso.ChildValueList`.

    .. code:: python

        class HTTPRESTMessage(aioxmpp.xso.XSO):
            TAG = ("https://neverdothis.example", "http-rest")

            method = aioxmpp.xso.Attr("method")

            payload = aioxmpp.xso.ChildValue(
                type_=aioxmpp.misc.JSONContainerType
            )
    """

    @classmethod
    def get_xso_types(cls):
        return [JSONContainer]

    @classmethod
    def unpack(cls, v):
        return v.json_data

    @classmethod
    def pack(cls, v):
        return JSONContainer(v)
