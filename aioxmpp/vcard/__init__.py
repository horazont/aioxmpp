########################################################################
# File name: __init__.py
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
"""
:mod:`~aioxmpp.vcard` --- vcard-temp support (:xep:`0054`)
##########################################################

This subpackage provides minimal support for setting and retrieving
vCard as per :xep:`0054`.

.. versionadded:: 0.10

We supply the service:

.. autoclass:: VCardService()

.. currentmodule:: aioxmpp.vcard.xso

The VCards are exposed as:

.. autoclass:: VCard()

"""
from .service import VCardService  # NOQA: F401
