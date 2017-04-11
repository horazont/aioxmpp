########################################################################
# File name: body.py
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
import functools

import aioxmpp.structs


@functools.singledispatch
def set_message_body(x, message):
    raise NotImplementedError(
        "type {!r} is not supported as message body".format(
            type(x)
        )
    )


@set_message_body.register(str)
def set_message_body_str(x, message):
    message.body.clear()
    message.body[None] = x


@set_message_body.register(aioxmpp.structs.LanguageMap)
def set_message_body_langmap(x, message):
    message.body.clear()
    message.body.update(x)
