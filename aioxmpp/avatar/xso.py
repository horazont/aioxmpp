########################################################################
# File name: xso.py
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
import aioxmpp.xso as xso
import aioxmpp.pubsub.xso as pubsub_xso

from aioxmpp.utils import namespaces

from ..stanza import Presence


namespaces.xep0084_data = "urn:xmpp:avatar:data"
namespaces.xep0084_metadata = "urn:xmpp:avatar:metadata"

namespaces.xep0153 = "vcard-temp:x:update"


class VCardTempUpdate(xso.XSO):
    """
    The vcard update notify element as per :xep:`0153`
    """

    TAG = (namespaces.xep0153, "x")

    def __init__(self, photo=None):
        self.photo = photo

    photo = xso.ChildText((namespaces.xep0153, "photo"),
                          type_=xso.String(),
                          default=None)


Presence.xep0153_x = xso.Child([VCardTempUpdate])


@pubsub_xso.as_payload_class
class Data(xso.XSO):
    """
    A data node, as used to publish and receive the avatar image data
    as image/png.

    .. attribute:: data

       The binary image data.
    """
    TAG = (namespaces.xep0084_data, "data")

    data = xso.Text(type_=xso.Base64Binary())

    def __init__(self, image_data):
        self.data = image_data


class Info(xso.XSO):
    """
    An info node specifying avatar metadata for a specific MIME type.

    .. attribute:: id_

       The SHA1 of the avatar image data.

    .. attribute:: mime_type

       The MIME type of the avatar image.

    .. attribute:: nbytes

       The size of the image data in bytes.

    .. attribute:: width

       The width of the image in pixels. Defaults to :data:`None`.

    .. attribute:: height

       The height of the image in pixels. Defaults to :data:`None`.

    .. attribute:: url

       The URL of the image. Defaults to :data:`None`.
    """
    TAG = (namespaces.xep0084_metadata, "info")

    id_ = xso.Attr(tag="id", type_=xso.String())
    mime_type = xso.Attr(tag="type", type_=xso.String())
    nbytes = xso.Attr(tag="bytes", type_=xso.Integer())
    width = xso.Attr(tag="width", type_=xso.Integer(), default=None)
    height = xso.Attr(tag="height", type_=xso.Integer(), default=None)
    url = xso.Attr(tag="url", type_=xso.String(), default=None)

    def __init__(self, id_, mime_type, nbytes, width=None,
                 height=None, url=None):
        self.id_ = id_
        self.mime_type = mime_type
        self.nbytes = nbytes
        self.width = width
        self.height = height
        self.url = url


class Pointer(xso.XSO):
    """
    A pointer metadata node. The contents are implementation defined.

    The following attributes may be present (they default to
    :data:`None`):

    .. attribute:: id_

       The SHA1 of the avatar image data.

    .. attribute:: mime_type

       The MIME type of the avatar image.

    .. attribute:: nbytes

       The size of the image data in bytes.

    .. attribute:: width

       The width of the image in pixels.

    .. attribute:: height

       The height of the image in pixels.
    """
    TAG = (namespaces.xep0084_metadata, "pointer")

    # according to the XEP those MAY occur if their values are known
    id_ = xso.Attr(tag="id", type_=xso.String(), default=None)
    mime_type = xso.Attr(tag="type", type_=xso.String(), default=None)
    nbytes = xso.Attr(tag="bytes", type_=xso.Integer(), default=None)
    width = xso.Attr(tag="width", type_=xso.Integer(), default=None)
    height = xso.Attr(tag="height", type_=xso.Integer(), default=None)

    registered_payload = xso.Child([])
    unregistered_payload = xso.Collector()

    @classmethod
    def as_payload_class(mycls, cls):
        """
        Register the given class `cls` as possible payload for a
        :class:`Pointer`.

        Return the class, to allow this to be used as decorator.
        """

        mycls.register_child(
            Pointer.registered_payload,
            cls
        )

        return cls

    def __init__(self, payload, id_, mime_type, nbytes, width=None,
                 height=None, url=None):
        self.registered_payload = payload

        self.id_ = id_
        self.mime_type = mime_type
        self.nbytes = nbytes
        self.width = width
        self.height = height


@pubsub_xso.as_payload_class
class Metadata(xso.XSO):
    """
    A metadata node which used to publish and reveice avatar image
    metadata.

    .. attribute:: info

       A map from the MIME type to the corresponding :class:`Info` XSO.

    .. attribute:: pointer

       A list of the :class:`Pointer` children.
    """
    TAG = (namespaces.xep0084_metadata, "metadata")

    info = xso.ChildMap([Info], key=lambda x: x.mime_type)
    pointer = xso.ChildList([Pointer])

    def iter_info_nodes(self):
        """
        Iterate over all :class:`Info` children.
        """
        info_map = self.info
        for mime_type in info_map:
            for metadata_info_node in info_map[mime_type]:
                yield metadata_info_node
