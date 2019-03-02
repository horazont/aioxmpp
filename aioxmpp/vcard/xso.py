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
import base64
import lxml.etree as etree

import aioxmpp
import aioxmpp.xso as xso

from aioxmpp.utils import namespaces

namespaces.xep0054 = "vcard-temp"


@aioxmpp.IQ.as_payload_class
class VCard(xso.XSO):
    """
    The container for vCard data as per :xep:`vcard-temp <54>`.

    .. attribute:: elements

       The raw elements of the vCard (as etree).

    The following methods are defined to access and modify certain
    entries of the vCard in a highlevel manner:

    .. automethod:: get_photo_data

    .. automethod:: set_photo_data

    .. automethod:: clear_photo_data
    """

    TAG = (namespaces.xep0054, "vCard")

    elements = xso.Collector()

    def get_photo_mime_type(self):
        """
        Get the mime type of the photo stored in the vCard.

        :returns: the MIME type of the photo as :class:`str` or :data:`None`.
        """
        mime_type = self.elements.xpath("/ns0:vCard/ns0:PHOTO/ns0:TYPE/text()",
                                        namespaces={"ns0": namespaces.xep0054})
        if mime_type:
            return mime_type[0]
        return None

    def get_photo_data(self):
        """
        Get the photo stored in the vCard.

        :returns: the photo as :class:`bytes` or :data:`None`.
        """
        photo = self.elements.xpath("/ns0:vCard/ns0:PHOTO/ns0:BINVAL/text()",
                                    namespaces={"ns0": namespaces.xep0054})
        if photo:
            return base64.b64decode(photo[0])
        return None

    def set_photo_data(self, mime_type, data):
        """
        Set the photo stored in the vCard.

        :param mime_type: the MIME type of the image data
        :param data: the image data as :class:`bytes`
        """
        res = self.elements.xpath("/ns0:vCard/ns0:PHOTO",
                                  namespaces={"ns0": namespaces.xep0054})
        if res:
            photo = res[0]
            photo.clear()
        else:
            photo = etree.SubElement(
                self.elements,
                etree.QName(namespaces.xep0054, "PHOTO")
            )

        binval = etree.SubElement(
            photo,
            etree.QName(namespaces.xep0054, "BINVAL")
        )
        binval.text = base64.b64encode(data)
        type_ = etree.SubElement(
            photo,
            etree.QName(namespaces.xep0054, "TYPE")
        )
        type_.text = mime_type

    def clear_photo_data(self):
        """
        Remove the photo stored in the vCard.
        """
        res = self.elements.xpath("/ns0:vCard/ns0:PHOTO",
                                  namespaces={"ns0": namespaces.xep0054})
        for to_remove in res:
            self.elements.remove(to_remove)
