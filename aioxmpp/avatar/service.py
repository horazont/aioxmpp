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
import logging

import aioxmpp
import aioxmpp.callbacks as callbacks
import aioxmpp.service as service
import aioxmpp.disco as disco
import aioxmpp.pep as pep
import aioxmpp.presence as presence
import aioxmpp.pubsub as pubsub
import aioxmpp.vcard as vcard

from aioxmpp.cache import LRUDict
from aioxmpp.utils import namespaces

from . import xso as avatar_xso

logger = logging.getLogger(__name__)

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

    .. automethod:: get_image_bytes
    """

    def __init__(self, remote_jid, mime_type, id_, nbytes, width=None,
                 height=None, url=None, pubsub=None, vcard=None,
                 image_bytes=None):
        self._remote_jid = remote_jid
        self._mime_type = mime_type
        self._id = id_
        self._nbytes = nbytes
        self._width = width
        self._height = height
        self._url = url
        self._pubsub = pubsub
        self._vcard = vcard
        self._image_bytes = image_bytes

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


class VCardAvatarDescriptor(AbstractAvatarDescriptor):

    @property
    def has_image_data_in_pubsub(self):
        return False

    @asyncio.coroutine
    def get_image_bytes(self):
        if self._image_bytes is not None:
            return self._image_bytes

        logger.debug("retrieving vCard %s", self._remote_jid)
        vcard = yield from self._vcard.get_vcard(self._remote_jid)
        photo = vcard.get_photo_data()
        if photo is not None:
            logger.debug("returning vCard avatar %s", self._remote_jid)
            return photo

        raise RuntimeError("Avatar image is not set")
        # url = item.xpath("/ns0:PHOTO/ns0:EXTVAL/text()",
        #                  namespaces={"ns0": namespaces.xep0054})


class AvatarService(service.Service):
    """Access and publish User Avatars (:xep:`84`). Fallback to vCard based
    avatars (:xep:`153`).

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

    Configuration:

    .. autoattribute:: synchronize_vcard

    .. attribute:: avatar_pep

       The PEP descriptor for claiming the avatar metadata namespace.
       The value is a :class:`~aioxmpp.pep.service.RegisteredPEPNode`,
       whose :attr:`~aioxmpp.pep.service.RegisteredPEPNode.notify`
       property can be used to disable or enable the notification
       feature.

    .. autoattribute:: metadata_cache_size
       :annotation: = 200

    """

    ORDER_AFTER = [
        disco.DiscoClient,
        disco.DiscoServer,
        pubsub.PubSubClient,
        pep.PEPClient,
        vcard.VCardService,
        presence.PresenceClient,
        presence.PresenceServer,
    ]

    avatar_pep = pep.register_pep_node(
        namespaces.xep0084_metadata,
        notify=True,
    )

    on_metadata_changed = callbacks.Signal()

    def __init__(self, client, **kwargs):
        super().__init__(client, **kwargs)
        self._has_pep_avatar = set()
        self._metadata_cache = LRUDict()
        self._metadata_cache.maxsize = 200
        self._pubsub = self.dependencies[pubsub.PubSubClient]
        self._pep = self.dependencies[pep.PEPClient]
        self._presence_server = self.dependencies[presence.PresenceServer]
        self._disco = self.dependencies[disco.DiscoClient]
        self._vcard = self.dependencies[vcard.VCardService]
        # we use this lock to prevent race conditions between different
        # calls of the methods by one client.
        # XXX: Other, independent clients may still cause inconsistent
        # data by race conditions, this should be fixed by at least
        # checking for consistent data after an update.
        self._publish_lock = asyncio.Lock()
        self._synchronize_vcard = False
        self._vcard_ressource_interference = set()
        self._vcard_id = None
        self._vcard_rehash_task = None

    @property
    def metadata_cache_size(self):
        """
        Maximum number of cache entries in the avatar metadata cache.

        This is mostly a measure to prevent malicious peers from
        exhausting memory by spamming vCard based avatar metadata for
        different ressources.

        .. versionadded:: 0.10

        """
        return self._metadata_cache.maxsize

    @metadata_cache_size.setter
    def metadata_cache_size(self, value):
        self._metadata_cache.maxsize = value

    @property
    def synchronize_vcard(self):
        """
        Set this property to true to enable publishing the a vCard avatar.

        This property defaults to false. For the setting true to have
        effect, you have to publish your avatar with :meth:`publish_avatar_set`
        or :meth:`disable_avatar` *after* this switch has been set to true.
        """
        return self._synchronize_vcard

    @synchronize_vcard.setter
    def synchronize_vcard(self, value):
        self._synchronize_vcard = bool(value)

    @service.depfilter(aioxmpp.stream.StanzaStream,
                       "service_outbound_presence_filter")
    def _attach_vcard_notify_to_presence(self, stanza):
        if not self._vcard_ressource_interference:
            stanza.xep0153_x = avatar_xso.VCardTempUpdate(self._vcard_id)
        return stanza

    def _handle_notify(self, full_jid, stanza):
        if stanza.xep0153_x is not None:
            if stanza.xep0153_x.photo is not None:
                if full_jid not in self._has_pep_avatar:
                    metadata = self._cook_vcard_notify(full_jid, stanza)
                    self.on_metadata_changed(
                        full_jid,
                        metadata
                    )
                    self._metadata_cache[full_jid] = metadata

                if (full_jid.bare() == self.client.local_jid.bare() and
                    full_jid != self.client.local_jid):
                    if (self._vcard_id is None or
                        stanza.xep0153_x.photo.lower() !=
                        self._vcard_id.lower()):
                        if self._vcard_rehash_task is not None:
                            self._vcard_rehash_task.cancel()

                        self._vcard_id = None
                        self._vcard_rehash_task = asyncio.async(
                            self._calculate_vcard_id()
                        )
                        def set_new_vcard_id(fut):
                            if not fut.cancelled():
                                self._vcard_id = fut.result()
                        self._vcard_rehash_task.add_done_callback(
                            set_new_vcard_id
                        )

    @asyncio.coroutine
    def _calculate_vcard_id(self):
        logger.debug("updating vcard hash")
        vcard = yield from self._vcard.get_vcard()
        logger.debug("%s", vcard)
        photo = vcard.get_photo_data()
        if photo is None:
            # if no photo is set in the vcard set an empty <photo>
            # element in the update, this means the avatar is disabled
            return ""
        else:
            sha1 = hashlib.sha1()
            sha1.update(photo)
            return sha1.hexdigest().lower()

    @service.depsignal(presence.PresenceClient, "on_available")
    def _handle_on_available(self, full_jid, stanza):
        if (full_jid.bare() == self.client.local_jid.bare() and
                full_jid != self.client.local_jid):
            if stanza.xep0153_x is None:
                self._vcard_ressource_interference.add(full_jid)
            else:
                # just to be on the safe side
                self._vcard_ressource_interference.discard(full_jid)

        self._handle_notify(full_jid, stanza)

    @service.depsignal(presence.PresenceClient, "on_changed")
    def _handle_on_changed(self, full_jid, stanza):
        self._handle_notify(full_jid, stanza)

    @service.depsignal(presence.PresenceClient, "on_unavailable")
    def _handle_on_unavailable(self, full_jid, stanza):
        if full_jid.bare() == self.client.local_jid.bare():
            self._vcard_ressource_interference.discard(full_jid)

    def _cook_vcard_notify(self, jid, stanza):
        result = collections.defaultdict(lambda: [])
        # note: an empty photo element correctly
        # results in an empty avatar metadata list
        if stanza.xep0153_x.photo:
            result[None].append(
                VCardAvatarDescriptor(
                    remote_jid=jid,
                    mime_type=None,
                    id_=stanza.xep0153_x.photo,
                    vcard=self._vcard,
                    nbytes=None,
                )
            )
        return result

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
        self._has_pep_avatar.add(jid)
        self.on_metadata_changed(
            jid,
            metadata
        )

    @asyncio.coroutine
    def get_avatar_metadata(self, jid, *, require_fresh=False):
        """
        Retrieve a mapping from MIME types to avatar descriptors for `jid`.
        The MIME type is set to :data:`None` if it is not known.

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

        def try_vcard_fallback():
            try:
                logger.debug("trying vCard avatar as fallback for %s", jid)
                vcard = yield from self._vcard.get_vcard(jid)
                # XXX: get_photo_data should extract the MIME type as well
                # here we can know, so we should pass it on
                photo = vcard.get_photo_data()
                if photo is not None:
                    logger.debug("success vCard avatar as fallback for %s", jid)
                    sha1 = hashlib.sha1()
                    sha1.update(photo)
                    metadata = collections.defaultdict(lambda: [])
                    metadata[None] = [VCardAvatarDescriptor(
                        remote_jid=jid,
                        mime_type=None,
                        id_=normalize_id(sha1.hexdigest()),
                        vcard=self._vcard,
                        nbytes=len(photo),
                        image_bytes=photo,
                    )]
                    return metadata
            except aioxmpp.XMPPCancelError:
                # set the cache to the empty avatar to prevent retries
                self._metadata_cache[jid] = collections.defaultdict(lambda: [])

            return None

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
            # transparently map feature-not-implemented and
            # item-not-found to be equivalent unset avatar
            if e.condition in (
                    (namespaces.stanzas, "feature-not-implemented"),
                    (namespaces.stanzas, "item-not-found")):
                metadata = collections.defaultdict(lambda: [])
            else:
                metadata = yield from try_vcard_fallback()
                if metadata is None:
                    raise
        else:
            self._has_pep_avatar.add(jid)
            metadata = self._cook_metadata(jid, metadata_raw.payload.items)

        # try the vcard fallback
        if not metadata:
            metadata_fallback = yield from try_vcard_fallback()
            if metadata_fallback is not None:
                metadata = metadata_fallback

        self._metadata_cache[jid] = metadata
        return metadata

    @asyncio.coroutine
    def subscribe(self, jid):
        """
        Explicitly subscribe to metadata change notifications for `jid`.
        """
        yield from self._pubsub.subscribe(jid, namespaces.xep0084_metadata)

    @aioxmpp.service.depsignal(aioxmpp.stream.StanzaStream,
                               "on_stream_destroyed")
    def handle_stream_destroyed(self, reason):
        # invalidate the cache?
        self._vcard_ressource_interference.clear()
        self._has_pep_avatar.clear()

    @asyncio.coroutine
    def publish_avatar_set(self, avatar_set):
        """
        Make `avatar_set` the current avatar of the jid associated with this
        connection.

        This means publishing the ``image/png`` avatar data and the
        avatar metadata set in pubsub. The `avatar_set` must be an
        instance of :class:`AvatarSet`.
        """
        id_ = avatar_set.png_id

        with (yield from self._publish_lock):
            try:
                yield from self._pep.publish(
                    namespaces.xep0084_data,
                    avatar_xso.Data(avatar_set.image_bytes),
                    id_=id_
                )

                yield from self._pep.publish(
                    namespaces.xep0084_metadata,
                    avatar_set.metadata,
                    id_=id_
                )
            finally:
                if self._synchronize_vcard:
                    my_vcard = yield from self._vcard.get_vcard()
                    my_vcard.set_photo_data("image/png", avatar_set.image_bytes)
                    self._vcard_id = avatar_set.png_id
                    yield from self._vcard.set_vcard(my_vcard)
                    yield from self._presence_server.resend_presence()

    @asyncio.coroutine
    def disable_avatar(self):
        """
        Temporarily disable the avatar.

        This is done by setting the avatar metadata node empty.
        """

        with (yield from self._publish_lock):
            try:
                yield from self._pep.publish(
                    namespaces.xep0084_metadata,
                    avatar_xso.Metadata()
                )
            finally:
                if self._synchronize_vcard:
                    my_vcard = yield from self._vcard.get_vcard()
                    my_vcard.clear_photo_data()
                    self._vcard_id = ""
                    yield from self._vcard.set_vcard(my_vcard)
                    yield from self._presence_server.resend_presence()
