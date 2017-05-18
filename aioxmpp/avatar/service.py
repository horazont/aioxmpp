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
import collections
import hashlib

import aioxmpp
import aioxmpp.callbacks as callbacks
import aioxmpp.service as service
import aioxmpp.disco as disco
import aioxmpp.pep as pep
import aioxmpp.pubsub as pubsub

from aioxmpp.utils import namespaces

from . import xso as avatar_xso


def normalize_id(id_):
    """
    Normalize a SHA1 sum encoded as hexadecimal number in ASCII.

    This does nothing but lowercase the string as to enable robust
    comparison.
    """
    return id_.lower()


class AvatarSet:
    """
    A list of sources of an avatar.

    Exactly one of the sources must include image data in the
    ``image/png`` format. The others provide the location of the
    image data as an URL.

    Adding pointer avatar data is not yet supported.

    .. automethod:: add_avatar_image
    """

    def __init__(self):
        self._image_bytes = None
        self._png_id = None
        self._metadata = avatar_xso.Metadata()

    @property
    def image_bytes(self):
        """
        The image data bytes for MIME type ``text/png``.
        """
        return self._image_bytes

    @property
    def metadata(self):
        """
        The :class:`Metadata` XSO corresponding to this avatar set.
        """
        return self._metadata

    @property
    def png_id(self):
        """
        The SHA1 of the ``image/png`` image data.

        This id is always normalized in the sense of :function:`normalize_id`.
        """
        return self._png_id

    def add_avatar_image(self, mime_type, *, id_=None,
                         image_bytes=None, width=None, height=None,
                         url=None, nbytes=None):
        """
        Add a source of the avatar image.

        All sources of an avatar image added to an avatar set must be
        *the same image*, in different formats.

        :param mime_type: The MIME type of the avatar image.
        :param id_: The SHA1 of the image data.
        :param nbytes: The size of the image data in bytes.
        :param image_bytes: The image data, this must be supplied only
                            in one call.
        :param url: The URL of the avatar image.
        :param height: The height of the image in pixels (optional).
        :param width: The width of the image in pixels (optional).

        `id_` and `nbytes` may be omitted if and only if `image_data`
        is given and `mime_type` is ``image/png``. If they are
        supplied *and* image data is given, they are checked to match
        the image data.

        It is the caller's responsibility to assure that the provided
        links exist and the files have the correct SHA1 sums.
        """

        if mime_type == "image/png":
            if image_bytes is not None:
                if self._image_bytes is not None:
                    raise RuntimeError(
                        "Only one avatar image may be published directly."
                    )

                sha1 = hashlib.sha1()
                sha1.update(image_bytes)
                id_computed = normalize_id(sha1.hexdigest())
                if id_ is not None:
                    id_ = normalize_id(id_)
                    if id_ != id_computed:
                        raise RuntimeError(
                            "The given id does not match the SHA1 of "
                            "the image data."
                        )
                else:
                    id_ = id_computed

                nbytes_computed = len(image_bytes)
                if nbytes is not None:
                    if nbytes != nbytes_computed:
                        raise RuntimeError(
                            "The given length does not match the length "
                            "of the image data."
                        )
                else:
                    nbytes = nbytes_computed

                self._image_bytes = image_bytes
                self._png_id = id_

        if image_bytes is None and url is None:
            raise RuntimeError(
                "Either the image bytes or an url to retrieve the avatar "
                "image must be given."
            )

        if nbytes is None:
            raise RuntimeError(
                "Image data length is not given an not inferable "
                "from the other arguments."
            )

        if id_ is None:
            raise RuntimeError(
                "The SHA1 of the image data is not given an not inferable "
                "from the other arguments."
            )

        if image_bytes is not None and mime_type != "image/png":
            raise RuntimeError(
                "The image bytes can only be given for image/png data."
            )

        self._metadata.info[mime_type].append(
            avatar_xso.Info(
                id_=id_, mime_type=mime_type, nbytes=nbytes,
                width=width, height=height, url=url
            )
        )


class AbstractAvatarDescriptor:
    """
    Description of an avatar source retrieved from pubsub.

    .. autoattribute:: mime_type

    .. autoattribute:: id_

    .. autoattribute:: normalized_id

    .. autoattribute:: nbytes

    .. autoattribute:: remote_jid

    .. autoattribute:: width

    .. autoattribute:: height

    .. autoattribute:: has_image_data_in_pubsub

    .. autoattribute:: url

    If :attr:`has_image_data_in_pubsub` is true, the image can be
    retrieved by the following coroutine:

    .. autocoroutine:: get_image_bytes
    """

    def __init__(self, remote_jid, mime_type, id_, nbytes, width=None,
                 height=None, url=None, pubsub=None):
        self._remote_jid = remote_jid
        self._mime_type = mime_type
        self._id = id_
        self._nbytes = nbytes
        self._width = width
        self._height = height
        self._url = url
        self._pubsub = pubsub

    @asyncio.coroutine
    def get_image_bytes(self):
        """
        Try to retrieve the image data corresponding to this avatar
        descriptor.

        This will raise :class:`NotImplementedError` if we are not
        capable to retrieve the image data. It is guaranteed to not
        raise :class:`NotImplementedError` if :attr:`image_in_pubsub`
        is true.
        """
        raise NotImplementedError

    @property
    def has_image_data_in_pubsub(self):
        """
        Whether the image can be retrieved from PubSub.
        """
        raise NotImplementedError

    @property
    def remote_jid(self):
        """
        The remote JID this avatar belongs to.
        """
        return self._remote_jid

    @property
    def url(self):
        """
        The URL where the avatar image data can be found.

        This is :data:`None` if :attr:`has_image_data_in_pubsub` is true.
        """
        return self._url

    @property
    def width(self):
        """
        The width of the avatar image in pixels.

        This is :data:`None` if this information is not supplied.
        """
        return self._width

    @property
    def height(self):
        """
        The height of the avatar image in pixels.

        This is :data:`None` if this information is not supplied.
        """
        return self._height

    @property
    def nbytes(self):
        """
        The size of the avatar image data in bytes.
        """
        return self._nbytes

    @property
    def id_(self):
        """
        The SHA1 of the image encoded as hexadecimal number in ASCII.

        This is the original value returned from pubsub and should be
        used for any further interaction with pubsub.
        """
        return self._id

    @property
    def normalized_id(self):
        """
        The SHA1 of the image data decoded to a :class:`bytes` object.

        This is supposed to be used for caching.
        """
        return normalize_id(self._id)

    @property
    def mime_type(self):
        """
        The MIME type of the image data.
        """
        return self._mime_type


class PubsubAvatarDescriptor(AbstractAvatarDescriptor):

    @property
    def has_image_data_in_pubsub(self):
        return True

    @asyncio.coroutine
    def get_image_bytes(self):
        image_data = yield from self._pubsub.get_items_by_id(
            self._remote_jid,
            namespaces.xep0084_data,
            [self.id_],
        )
        if not image_data.payload.items:
            raise RuntimeError("Avatar image data is not set.")

        item, = image_data.payload.items
        return item.registered_payload.data


class HttpAvatarDescriptor(AbstractAvatarDescriptor):

    @property
    def has_image_data_in_pubsub(self):
        return False

    @asyncio.coroutine
    def get_image_bytes(self):
        """
        Try to retrieve the avatar image date.

        May raise NotImplementedError
        """
        raise NotImplementedError


class AvatarService(service.Service):
    """
    Access and publish User Avatars (:xep:`84`).

    This service provides an interface for accessing the avatar of other
    entities in the network, getting notifications on avatar changes and
    publishing an avatar for this entity.

    Observing avatars:

    .. note:: :class:`AvatarService` only caches the metadata, not the
              actual image data. This is the job of the caller.

    .. signal:: on_metadata_changed(jid, metadata)

        Fires when avatar metadata changes.

        :param jid: The JID which the avatar belongs to.
        :param metadata: The new metadata descriptors.
        :type metadata: a sequence of
            :class:`~aioxmpp.avatar.service.AbstractAvatarDescriptor`
            instances

    .. automethod:: get_avatar_metadata

    .. automethod:: subscribe

    Publishing avatars:

    .. automethod:: publish_avatar_set

    .. automethod:: disable_avatar

    """

    ORDER_AFTER = [
        disco.DiscoClient,
        disco.DiscoServer,
        pubsub.PubSubClient,
        pep.PEPClient,
    ]

    avatar_pep = pep.register_pep_node(
        namespaces.xep0084_metadata,
        notify=True,
    )

    on_metadata_changed = callbacks.Signal()

    def __init__(self, client, **kwargs):
        super().__init__(client, **kwargs)
        self._has_pep = None
        self._metadata_cache = {}
        self._pubsub = self.dependencies[pubsub.PubSubClient]
        self._notify_lock = asyncio.Lock()
        self._disco = self.dependencies[disco.DiscoClient]
        # we use this lock to prevent race conditions between different
        # calls of the methods by one client.
        # XXX: Other, independent clients may still cause inconsistent
        # data by race conditions, this should be fixed by at least
        # checking for consistent data after an update.
        self._publish_lock = asyncio.Lock()

    def _cook_metadata(self, jid, items):
        def iter_metadata_info_nodes(items):
            for item in items:
                yield from item.registered_payload.iter_info_nodes()

        result = collections.defaultdict(lambda: [])
        for info_node in iter_metadata_info_nodes(items):
            if info_node.url is not None:
                descriptor = HttpAvatarDescriptor(
                    remote_jid=jid,
                    mime_type=info_node.mime_type,
                    id_=info_node.id_,
                    nbytes=info_node.nbytes,
                    width=info_node.width,
                    height=info_node.height,
                    url=info_node.url,
                )
            else:
                descriptor = PubsubAvatarDescriptor(
                    remote_jid=jid,
                    mime_type=info_node.mime_type,
                    id_=info_node.id_,
                    nbytes=info_node.nbytes,
                    width=info_node.width,
                    height=info_node.height,
                    pubsub=self._pubsub,
                )
            result[info_node.mime_type].append(descriptor)

        return result

    @service.attrsignal(avatar_pep, "on_item_publish")
    def handle_pubsub_publish(self, jid, node, item, *, message=None):
        # update the metadata cache
        metadata = self._cook_metadata(jid, [item])
        self._metadata_cache[jid] = metadata

        self.on_metadata_changed(
            jid,
            metadata
        )

    @asyncio.coroutine
    def get_avatar_metadata(self, jid, *, require_fresh=False):
        """
        Retrieve a list of avatar descriptors for `jid`.

        The avatar descriptors are returned as a list of instances of
        :class:`~aioxmpp.avatar.service.AbstractAvatarDescriptor`.
        An empty list means that the avatar is unset.

        If `require_fresh` is true, we will not lookup the avatar
        metadata from the cache, but make a new pubsub request.

        We mask a :class:`XMPPCancelError` in the case that it is
        ``feature-not-implemented`` or ``item-not-found`` and return
        an empty list of avatar descriptors, since this is
        semantically equivalent to not having an avatar.
        """
        if not require_fresh:
            try:
                return self._metadata_cache[jid]
            except KeyError:
                pass

        with (yield from self._notify_lock):
            if jid in self._metadata_cache:
                if require_fresh:
                    del self._metadata_cache[jid]
                else:
                    return self._metadata_cache[jid]

            try:
                metadata_raw = yield from self._pubsub.get_items(
                    jid,
                    namespaces.xep0084_metadata,
                    max_items=1
                )
            except aioxmpp.XMPPCancelError as e:
                # transparently map feature-not-implemente and
                # item-not-found to be equivalent unset avatar
                if e.condition in (
                        (namespaces.stanzas, "feature-not-implemented"),
                        (namespaces.stanzas, "item-not-found")):
                    metadata = collections.defaultdict(lambda: [])
                else:
                    raise
            else:
                metadata = self._cook_metadata(jid, metadata_raw.payload.items)

            self._metadata_cache[jid] = metadata
            return metadata

    @asyncio.coroutine
    def subscribe(self, jid):
        """
        Explicitly subscribe to metadata change notifications for `jid`.
        """
        yield from self._pubsub.subscribe(jid, namespaces.xep0084_metadata)

    @asyncio.coroutine
    def _check_for_pep(self):
        # determine support for PEP as specified in XEP-0163 section 6
        # XXX: fix this by implementing a PEPService that is derived from
        # pubsub and checks for the server capability and simplifies the
        # handling
        def raise_exception():
            raise NotImplementedError(
                "Server does not support PEP and we do not support "
                "surrogating for lack of PEP support"
            )

        if self._has_pep is not None:
            if self._has_pep:
                return
            else:
                raise_exception()

        disco_info = yield from self._disco.query_info(
            self.client.local_jid.bare()
        )

        for item in disco_info.identities.filter(attrs={"category": "pubsub"}):
            if item.type_ == "pep":
                self._has_pep = True
                break
        else:
            self._has_pep = False
            raise_exception()

    @aioxmpp.service.depsignal(aioxmpp.stream.StanzaStream,
                               "on_stream_destroyed")
    def handle_stream_destroyed(self, reason):
        # invalidate the cache
        self._has_pep = None

    @asyncio.coroutine
    def publish_avatar_set(self, avatar_set):
        """
        Make `avatar_set` the current avatar of the jid associated with this
        connection.

        This means publishing the ``image/png`` avatar data and the
        avatar metadata set in pubsub. The `avatar_set` must be an
        instance of :class:`AvatarSet`.
        """
        yield from self._check_for_pep()

        id_ = avatar_set.png_id

        with (yield from self._publish_lock):
            yield from self._pubsub.publish(
                None,
                namespaces.xep0084_data,
                avatar_xso.Data(avatar_set.image_bytes),
                id_=id_
            )

            yield from self._pubsub.publish(
                None,
                namespaces.xep0084_metadata,
                avatar_set.metadata,
                id_=id_
            )

    @asyncio.coroutine
    def disable_avatar(self):
        """
        Temporarily disable the avatar.

        This is done by setting the avatar metadata node empty.
        """
        yield from self._check_for_pep()

        with (yield from self._publish_lock):
            yield from self._pubsub.publish(
                None,
                namespaces.xep0084_metadata,
                avatar_xso.Metadata()
            )
