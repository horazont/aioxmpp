"""
:mod:`~aioxmpp.rfc3921` --- XSOs for legacy protocol parts
##########################################################

This module was introduced to ensure compatibility with legacy XMPP servers
(such as ejabberd).

.. autoclass:: Session

.. autoclass:: SessionFeature

"""



from . import stanza, nonza, xso

from .utils import namespaces


namespaces.rfc3921_session = "urn:ietf:params:xml:ns:xmpp-session"


@stanza.IQ.as_payload_class
class Session(xso.XSO):
    """
    IQ payload to establish a legacy XMPP session.

    .. versionadded:: 0.4
    """

    UNKNOWN_CHILD_POLICY = xso.UnknownChildPolicy.DROP
    UNKNOWN_ATTR_POLICY = xso.UnknownAttrPolicy.DROP

    TAG = (namespaces.rfc3921_session, "session")


@nonza.StreamFeatures.as_feature_class
class SessionFeature(xso.XSO):
    """
    Stream feature which the server uses to announce that it supports legacy
    XMPP sessions.

    .. versionadded:: 0.4
    """

    UNKNOWN_CHILD_POLICY = xso.UnknownChildPolicy.DROP
    UNKNOWN_ATTR_POLICY = xso.UnknownAttrPolicy.DROP

    TAG = (namespaces.rfc3921_session, "session")
