import asyncio
import collections
import itertools

from .. import base

from . import stanza

from asyncio_xmpp.utils import *

__all__ = [
    "DiscoInfoService"
]

class DiscoInfoService(base.Service):
    """
    Provide a server-side (in the sense of replying to XEP-0030 related queries,
    not in the sense of on the side of an XMPP server) implementation of
    XEP-0030 features.

    .. seealso::

       General APIs and the constructor arguments of extension services are
       described in the base class :class:`.base.Service`.

    .. automethod:: add_feature

    .. automethod:: remove_feature

    .. autoattribute:: identity_name

    .. automethod:: add_identity

    .. automethod:: remove_identity

    """

    def __init__(self, node, **kwargs):
        super().__init__(node, **kwargs)

        self._node.register_iq_request_coro(
            stanza.InfoQuery.TAG,
            "get",
            self._handle_info_query)

        self._features = set()
        self._identities = collections.Counter()
        self._name = None

    def add_feature(self, feature):
        """
        Register a *feature* to show it in service discovery. *feature* must be
        a non-empty string, which will be used as the ``var`` attribute on the
        feature element in the query response.

        If the *feature* is already registered, :class:`KeyError` is raised.
        """
        if not feature or not isinstance(feature, str):
            raise ValueError("Feature must be a non-empty string")
        if feature in self._features:
            raise KeyError(feature)
        self._features.add(feature)

    def add_identity(self, category, type_):
        """
        Add an identity of *category* and *type_*. Identities are counted, that
        is if multiple callers add the same identity and type, both must remove
        the identity again for it to vanish from the query.

        * ``category``: A non-empty string which serves as a category for the
          identity.
        * ``type_``: A non-empty string which serves as the type for the
          identity.
        """

        if not category or not isinstance(category, str):
            raise ValueError("Identity category must a non-empty string")
        if not type_ or not isinstance(type_, str):
            raise ValueError("Identity type must a non-empty string")
        self._identities[category, type_] += 1

    def remove_feature(self, feature):
        """
        Remove a *feature* from the service discovery info list.

        Raise :class:`KeyError` if the feature has not been registered before.
        """
        self._features.remove(feature)

    def remove_identity(self, category, type_):
        """
        Remove an identity which has previously been added, identified by their
        *category* and *type_*.

        This never raises.
        """
        identity = category, type_
        ctr = self._identities[identity] - 1
        if ctr <= 0:
            del self._identities[identity]
        else:
            self._identities[identity] = ctr

    @property
    def identity_name(self):
        """
        The name for use in any identity nodes which are created in a
        ``disco#info`` response.

        .. note::

           The rationale for allowing only exactly one name is that the XEP-0030
           specifies that the name on each identity SHOULD be equal.

           This helps to enforce that across all users of this service. In
           addition, as the name is supposed to identify the entity, it is
           usually decoupled from any identity providers.

        """
        return self._name

    @identity_name.setter
    def identity_name(self, value):
        self._name = value

    @asyncio.coroutine
    def _handle_info_query(self, iq):
        self.logger.debug("received disco#info from %s", iq.from_)
        result = stanza.InfoQuery()
        for feature in self._features:
            item = stanza.Feature()
            item.var = feature
            result.append(item)

        for category, type_ in self._identities.keys():
            item = stanza.Identity()
            item.category = identity.category
            item.type_ = identity.type_
            if self._name:
                item.name = self._name

        self.logger.debug(
            "sending disco#info response with %d elements",
            len(result))
        return result
