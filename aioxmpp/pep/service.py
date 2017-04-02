########################################################################
# File name: service.py
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
import asyncio

import aioxmpp
import aioxmpp.service as service
import aioxmpp.signal as signal


class PEPClient(service.Service):
    """
    :class:`PEPClient` simplifies working with PEP services.

    Compared to :class:`~aioxmpp.PubSubClient` it supports automatic
    checking for server support, a stream-lined API. It is intended to
    make PEP things easy. If you need more fine-grained control or do
    things which are not usually handled by the defaults when using PEP, use
    :class:`~aioxmpp.PubSubClient` directly.
    """
    ORDER_AFTER = [
        aioxmpp.DiscoClient,
        aioxmpp.DiscoServer,
        aioxmpp.PubSubClient
    ]

    on_personal_event = callbacks.Signal()

    def __init__(self, client, **kwargs):
        super().__init__(client, **kwargs)
        self._pubsub = self.dependencies[aioxmpp.PubSubClient]
        self._disco_client = self.dependencies[aioxmpp.DiscoClient]
        self._disco_server = self.dependencies[aioxmpp.DiscoServer]

    @asyncio.coroutine
    def _check_for_pep(self):
        disco_info = yield from self._disco_client.query_info(
            self.client.local_jid.bare()
        )

        for item in disco_info.identities.filter(attrs={"category": "pubsub"}):
            if item.type_ == "pep":
                break
        else:
            raise RuntimeError("server does not support PEP")

    @service.depsignal(pubsub.PubSubClient, "on_item_published")
    def _handle_pubsub_publish(self, jid, node, item, *, message=None):
        # TODO: filter by determining whether `jid` is a PEP virtual service
        # problem: _handle_pubsub_publish is no coroutine
        self.on_personal_event(jid, node, item, message=message)

    def publish(self, node, data, *, id_=None):
        self._check_for_pep()
        yield from self._pubsub.publish(None, node, data, id_=id_)

class register_notify_feature(service.Descriptor):
    """
    Service descriptor which registers a ``+notify`` feature, for
    automatic pubsub subscription.

    :param node_namespace: The PubSub payload namespace to request
         notifications for. (*This MUST NOT already include the
        ``+notify``).
    """
    # TODO: this needs to check for PEP support
    def __init__(self, node_namespace):
        super().__init__()
        self._node_namespace = node_namespace
        self._underlying_descriptor = aioxmpp.register_feature(
            node_namespace + "+notify"
        )

    @property
    def node_namespace(self):
        """
        The node namespace to request notifications for.
        """
        return self._node_namespace


    @property
    def required_dependencies(self):
        return [PEPClient]

    def init_cm(self, instance):
        return self._underlying_descriptor.init_cm(
            instance.dependencies[PEPClient]
        )
