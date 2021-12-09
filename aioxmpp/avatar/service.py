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
import hashlib
import logging
import warnings

import aioxmpp
import aioxmpp.callbacks as callbacks
import aioxmpp.service as service
import aioxmpp.disco as disco
import aioxmpp.pep as pep
import aioxmpp.presence as presence
import aioxmpp.pubsub as pubsub
import aioxmpp.vcard as vcard

from aioxmpp.cache import LRUDict
from aioxmpp.utils import namespaces, gather_reraise_multi

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
        *the same image*, in different formats and sizes.

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
    Description of the properties of and how to retrieve a specific
    avatar.

    The following attributes are available for all instances:

    .. autoattribute:: remote_jid

    .. autoattribute:: id_

    .. autoattribute:: normalized_id

    .. autoattribute:: can_get_image_bytes_via_xmpp

    .. autoattribute:: has_image_data_in_pubsub

    The following attributes may be :data:`None` and are supposed to
    be used as hints for selection of the avatar to download:

    .. autoattribute:: nbytes

    .. autoattribute:: width

    .. autoattribute:: height

    .. autoattribute:: mime_type

    If this attribute is not :data:`None` it is an URL that points to
    the location of the avatar image:

    .. autoattribute:: url

    The image data belonging to the descriptor can be retrieved by the
    following coroutine:

    .. automethod:: get_image_bytes
    """

    def __init__(self, remote_jid, id_, *, mime_type=None,
                 nbytes=None, width=None, height=None, url=None):
        self._remote_jid = remote_jid
        self._mime_type = mime_type
        self._id = id_
        self._nbytes = nbytes
        self._width = width
        self._height = height
        self._url = url

    def __eq__(self, other):
        return (self._remote_jid == other._remote_jid and
                self._mime_type == other._mime_type and
                self._id == other._id and
                self._nbytes == other._nbytes and
                self._width == other._width and
                self._height == other._height and
                self._url == other._url)

    async def get_image_bytes(self):
        """
        Try to retrieve the image data corresponding to this avatar
        descriptor.

        :returns: the image contents
        :rtype: :class:`bytes`

        :raises NotImplementedError: if we do not implement the
            capability to retrieve the image data of this type. It is
            guaranteed to not raise :class:`NotImplementedError` if
            :attr:`can_get_image_bytes_via_xmpp` is true.

        :raises RuntimeError: if the image data described by this
            descriptor is not at the specified location.

        :raises aiomxpp.XMPPCancelError: if trying to retrieve the
            image data causes an XMPP error.
        """
        raise NotImplementedError

    @property
    def can_get_image_bytes_via_xmpp(self):
        """
        Return whether :meth:`get_image_bytes` raises
        :class:`NotImplementedError`.
        """
        return False

    @property
    def has_image_data_in_pubsub(self):
        """
        Whether the image can be retrieved from PubSub.

        .. deprecated:: 0.10

           Use :attr:`can_get_image_bytes_via_xmpp` instead.

           As we support vCard based avatars now the name of this is
           misleading.

           This attribute will be removed in aioxmpp 1.0
        """
        warnings.warn(
            "the has_image_data_in_pubsub attribute is deprecated and will be"
            " removed in 1.0",
            DeprecationWarning,
            stacklevel=1
        )
        return self.can_get_image_bytes_via_xmpp

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

        This may be :data:`None` if the avatar is not given as an URL
        of the image data.
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

        This is the original value returned from the underlying
        protocol and should be used for any further interaction with
        the underlying protocol.
        """
        return self._id

    @property
    def normalized_id(self):
        """
        The normalized SHA1 of the image data.

        This is supposed to be used for caching and comparison.
        """
        return normalize_id(self._id)

    @property
    def mime_type(self):
        """
        The MIME type of the image data.
        """
        return self._mime_type


class PubsubAvatarDescriptor(AbstractAvatarDescriptor):

    def __init__(self, remote_jid, id_, *, pubsub=None, **kwargs):
        super().__init__(remote_jid, id_, **kwargs)
        self._pubsub = pubsub

    def __eq__(self, other):
        return (isinstance(other, PubsubAvatarDescriptor) and
                super().__eq__(other))

    @property
    def can_get_image_bytes_via_xmpp(self):
        return True

    async def get_image_bytes(self):
        image_data = await self._pubsub.get_items_by_id(
            self._remote_jid,
            namespaces.xep0084_data,
            [self.id_],
        )
        if not image_data.payload.items:
            raise RuntimeError("Avatar image data is not set.")

        item, = image_data.payload.items
        return item.registered_payload.data


class HttpAvatarDescriptor(AbstractAvatarDescriptor):

    async def get_image_bytes(self):
        raise NotImplementedError

    def __eq__(self, other):
        return (isinstance(other, HttpAvatarDescriptor) and
                super().__eq__(other))


class VCardAvatarDescriptor(AbstractAvatarDescriptor):

    def __init__(self, remote_jid, id_, *, vcard=None, image_bytes=None,
                 **kwargs):
        super().__init__(remote_jid, id_, **kwargs)
        self._vcard = vcard
        self._image_bytes = image_bytes

    def __eq__(self, other):
        # NOTE: we explicitly do *not* check for the equality of
        # image bytes: image bytes is a hidden optimization
        return (isinstance(other, VCardAvatarDescriptor) and
                super().__eq__(other))

    @property
    def can_get_image_bytes_via_xmpp(self):
        return True

    async def get_image_bytes(self):
        if self._image_bytes is not None:
            return self._image_bytes

        logger.debug("retrieving vCard %s", self._remote_jid)
        vcard = await self._vcard.get_vcard(self._remote_jid)
        photo = vcard.get_photo_data()
        if photo is None:
            raise RuntimeError("Avatar image is not set")

        logger.debug("returning vCard avatar %s", self._remote_jid)
        return photo


class AvatarService(service.Service):
    """
    Access and publish User Avatars (:xep:`84`). Fallback to vCard
    based avatars (:xep:`153`) if no PEP avatar is available.

    This service provides an interface for accessing the avatar of other
    entities in the network, getting notifications on avatar changes and
    publishing an avatar for this entity.

    .. versionchanged:: 0.10

       Support for :xep:`vCard-Based Avatars <153>` was added.

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

    .. automethod:: wipe_avatar

    Configuration:

    .. autoattribute:: synchronize_vcard

    .. autoattribute:: advertise_vcard

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
        self._advertise_vcard = True
        self._vcard_resource_interference = set()
        self._vcard_id = None
        self._vcard_rehashing_for = None
        self._vcard_rehash_task = None

    @property
    def metadata_cache_size(self):
        """
        Maximum number of cache entries in the avatar metadata cache.

        This is mostly a measure to prevent malicious peers from
        exhausting memory by spamming vCard based avatar metadata for
        different resources.

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

    @property
    def advertise_vcard(self):
        """
        Set this property to false to disable advertisement of the vCard
        avatar via presence broadcast.

        Note, that this reduces traffic, since it makes the presence
        stanzas smaller and we no longer have to recalculate the hash,
        this also disables vCard advertisement for all other
        resources of the bare local jid, by the business rules of
        :xep:`0153`.

        Note that, when enabling this feature again the vCard has to
        be fetched from the server to recalculate the hash.
        """
        return self._advertise_vcard

    @advertise_vcard.setter
    def advertise_vcard(self, value):
        self._advertise_vcard = bool(value)
        if self._advertise_vcard:
            self._vcard_id = None
            self._start_rehash_task()

    @service.depfilter(aioxmpp.stream.StanzaStream,
                       "service_outbound_presence_filter")
    def _attach_vcard_notify_to_presence(self, stanza):
        if self._advertise_vcard:
            if self._vcard_resource_interference:
                # do not advertise the hash if there is resource interference
                stanza.xep0153_x = avatar_xso.VCardTempUpdate()
            else:
                stanza.xep0153_x = avatar_xso.VCardTempUpdate(self._vcard_id)

        return stanza

    def _update_metadata(self, cache_jid, metadata):
        try:
            cached_metadata = self._metadata_cache[cache_jid]
        except KeyError:
            pass
        else:
            if cached_metadata == metadata:
                return

        self._metadata_cache[cache_jid] = metadata
        self.on_metadata_changed(
            cache_jid,
            metadata
        )

    def _handle_notify(self, full_jid, stanza):
        # handle resource interference as per XEP-153 business rules,
        # we go along with this tracking even if vcard advertisement
        # is off
        if (full_jid.bare() == self.client.local_jid.bare() and
                full_jid != self.client.local_jid):
            if stanza.xep0153_x is None:
                self._vcard_resource_interference.add(full_jid)
            else:
                if self._vcard_resource_interference:
                    self._vcard_resource_interference.discard(full_jid)
                    if not self._vcard_resource_interference:
                        self._vcard_id = None

        # otherwise ignore stanzas without xep0153_x payload, or
        # no photo tag.
        if stanza.xep0153_x is None:
            return

        if stanza.xep0153_x.photo is None:
            return

        # special case MUC presence – otherwise the vcard is retrieved
        # for the bare jid
        if stanza.xep0045_muc_user is not None:
            cache_jid = full_jid
        else:
            cache_jid = full_jid.bare()

        if cache_jid not in self._has_pep_avatar:
            metadata = self._cook_vcard_notify(cache_jid, stanza)
            self._update_metadata(cache_jid, metadata)

        # trigger the download of the vCard and calculation of the
        # vCard avatar hash, if some other resource of our bare jid
        # reported a hash distinct from ours!
        # don't do this if there is a non-compliant resource, we don't
        # send the hash in that case anyway
        if (full_jid.bare() == self.client.local_jid.bare() and
                full_jid != self.client.local_jid and
                self._advertise_vcard and
                not self._vcard_resource_interference):
            if (self._vcard_id is None or
                    stanza.xep0153_x.photo.lower() !=
                    self._vcard_id.lower()):

                # do not rehash if we already have a rehash task that
                # was triggered by an update with the same hash
                if (self._vcard_rehashing_for is None or
                        self._vcard_rehashing_for !=
                        stanza.xep0153_x.photo.lower()):
                    self._vcard_rehashing_for = stanza.xep0153_x.photo.lower()
                    self._start_rehash_task()

    def _start_rehash_task(self):
        if self._vcard_rehash_task is not None:
            self._vcard_rehash_task.cancel()

        self._vcard_id = None
        # as per XEP immediately resend the presence with empty update
        # element, as this is not synchronous it might already contaiin
        # the new hash, but this is okay as well (as it makes the cached
        # presence stanzas coherent as well).
        self._presence_server.resend_presence()

        self._vcard_rehash_task = asyncio.ensure_future(
            self._calculate_vcard_id()
        )

        def set_new_vcard_id(fut):
            self._vcard_rehashing_for = None
            if not fut.cancelled():
                self._vcard_id = fut.result()

        self._vcard_rehash_task.add_done_callback(
            set_new_vcard_id
        )

    async def _calculate_vcard_id(self):
        self.logger.debug("updating vcard hash")
        vcard = await self._vcard.get_vcard()
        self.logger.debug("got vcard for hash update: %s", vcard)
        photo = vcard.get_photo_data()

        # if no photo is set in the vcard, set an empty <photo> element
        # in the update; according to the spec this means the avatar
        # is disabled
        if photo is None:
            self.logger.debug("no photo in vcard, advertising as such")
            return ""

        sha1 = hashlib.sha1()
        sha1.update(photo)
        new_hash = sha1.hexdigest().lower()
        self.logger.debug("updated hash to %s", new_hash)
        return new_hash

    @service.depsignal(presence.PresenceClient, "on_available")
    def _handle_on_available(self, full_jid, stanza):
        self._handle_notify(full_jid, stanza)

    @service.depsignal(presence.PresenceClient, "on_changed")
    def _handle_on_changed(self, full_jid, stanza):
        self._handle_notify(full_jid, stanza)

    @service.depsignal(presence.PresenceClient, "on_unavailable")
    def _handle_on_unavailable(self, full_jid, stanza):
        if full_jid.bare() == self.client.local_jid.bare():
            if self._vcard_resource_interference:
                self._vcard_resource_interference.discard(full_jid)
                if not self._vcard_resource_interference:
                    self._start_rehash_task()

        # correctly handle MUC avatars
        if stanza.xep0045_muc_user is not None:
            self._metadata_cache.pop(full_jid, None)

    def _cook_vcard_notify(self, jid, stanza):
        result = []
        # note: an empty photo element correctly
        # results in an empty avatar metadata list
        if stanza.xep0153_x.photo:
            result.append(
                VCardAvatarDescriptor(
                    remote_jid=jid,
                    id_=stanza.xep0153_x.photo,
                    mime_type=None,
                    vcard=self._vcard,
                    nbytes=None,
                )
            )
        return result

    def _cook_metadata(self, jid, items):
        def iter_metadata_info_nodes(items):
            for item in items:
                yield from item.registered_payload.iter_info_nodes()

        result = []
        for info_node in iter_metadata_info_nodes(items):
            if info_node.url is not None:
                descriptor = HttpAvatarDescriptor(
                    remote_jid=jid,
                    id_=info_node.id_,
                    mime_type=info_node.mime_type,
                    nbytes=info_node.nbytes,
                    width=info_node.width,
                    height=info_node.height,
                    url=info_node.url,
                )
            else:
                descriptor = PubsubAvatarDescriptor(
                    remote_jid=jid,
                    id_=info_node.id_,
                    mime_type=info_node.mime_type,
                    nbytes=info_node.nbytes,
                    width=info_node.width,
                    height=info_node.height,
                    pubsub=self._pubsub,
                )
            result.append(descriptor)

        return result

    @service.attrsignal(avatar_pep, "on_item_publish")
    def _handle_pubsub_publish(self, jid, node, item, *, message=None):
        # update the metadata cache
        metadata = self._cook_metadata(jid, [item])
        self._has_pep_avatar.add(jid)
        self._update_metadata(jid, metadata)

    async def _get_avatar_metadata_vcard(self, jid):
        logger.debug("trying vCard avatar as fallback for %s", jid)
        vcard = await self._vcard.get_vcard(jid)
        photo = vcard.get_photo_data()
        mime_type = vcard.get_photo_mime_type()
        if photo is None:
            return []

        logger.debug("success vCard avatar as fallback for %s",
                     jid)
        sha1 = hashlib.sha1()
        sha1.update(photo)
        return [VCardAvatarDescriptor(
            remote_jid=jid,
            id_=sha1.hexdigest(),
            mime_type=mime_type,
            nbytes=len(photo),
            vcard=self._vcard,
            image_bytes=photo,
        )]

    async def _get_avatar_metadata_pep(self, jid):
        try:
            metadata_raw = await self._pubsub.get_items(
                jid,
                namespaces.xep0084_metadata,
                max_items=1
            )
        except aioxmpp.XMPPCancelError as e:
            # transparently map feature-not-implemented and
            # item-not-found to be equivalent unset avatar
            if e.condition in (
                    aioxmpp.ErrorCondition.FEATURE_NOT_IMPLEMENTED,
                    aioxmpp.ErrorCondition.ITEM_NOT_FOUND):
                return []
            raise

        self._has_pep_avatar.add(jid)
        return self._cook_metadata(jid, metadata_raw.payload.items)

    async def get_avatar_metadata(self, jid, *, require_fresh=False,
                                  disable_pep=False):
        """
        Retrieve a list of avatar descriptors.

        :param jid: the JID for which to retrieve the avatar metadata.
        :type jid: :class:`aioxmpp.JID`
        :param require_fresh: if true, do not return results from the
            avatar metadata cache, but retrieve them again from the server.
        :type require_fresh: :class:`bool`
        :param disable_pep: if true, do not try to retrieve the avatar
            via pep, only try the vCard fallback. This usually only
            useful when querying avatars via MUC, where the PEP request
            would be invalid (since it would be for a full jid).
        :type disable_pep: :class:`bool`

        :returns: an iterable of avatar descriptors.
        :rtype: a :class:`list` of
            :class:`~aioxmpp.avatar.service.AbstractAvatarDescriptor`
            instances

        Returning an empty list means that the avatar not set.

        We mask a :class:`XMPPCancelError` in the case that it is
        ``feature-not-implemented`` or ``item-not-found`` and return
        an empty list of avatar descriptors, since this is
        semantically equivalent to not having an avatar.

        .. note::

           It is usually an error to get the avatar for a full jid,
           normally, the avatar is set for the bare jid of a user. The
           exception are vCard avatars over MUC, where the IQ requests
           for the vCard may be translated by the MUC server. It is
           recommended to use the `disable_pep` option in that case.
        """

        if require_fresh:
            self._metadata_cache.pop(jid, None)
        else:
            try:
                return self._metadata_cache[jid]
            except KeyError:
                pass

        if disable_pep:
            metadata = []
        else:
            metadata = await self._get_avatar_metadata_pep(jid)

        # try the vcard fallback, note: we don't try this
        # if the PEP avatar is disabled!
        if not metadata and jid not in self._has_pep_avatar:
            metadata = await self._get_avatar_metadata_vcard(jid)

        # if a notify was fired while we waited for the results, then
        # use the version in the cache, this will mitigate the race
        # condition because if our version is actually newer we will
        # soon get another notify for this version change!
        if jid not in self._metadata_cache:
            self._update_metadata(jid, metadata)
        return self._metadata_cache[jid]

    async def subscribe(self, jid):
        """
        Explicitly subscribe to metadata change notifications for `jid`.
        """
        await self._pubsub.subscribe(jid, namespaces.xep0084_metadata)

    @aioxmpp.service.depsignal(aioxmpp.stream.StanzaStream,
                               "on_stream_destroyed")
    def handle_stream_destroyed(self, reason):
        self._metadata_cache.clear()
        self._vcard_resource_interference.clear()
        self._has_pep_avatar.clear()

    async def publish_avatar_set(self, avatar_set):
        """
        Make `avatar_set` the current avatar of the jid associated with this
        connection.

        If :attr:`synchronize_vcard` is true and PEP is available the
        vCard is only synchronized if the PEP update is successful.

        This means publishing the ``image/png`` avatar data and the
        avatar metadata set in pubsub. The `avatar_set` must be an
        instance of :class:`AvatarSet`. If :attr:`synchronize_vcard` is
        true the avatar is additionally published in the user vCard.
        """
        id_ = avatar_set.png_id

        done = False
        async with self._publish_lock:
            if await self._pep.available():
                await self._pep.publish(
                    namespaces.xep0084_data,
                    avatar_xso.Data(avatar_set.image_bytes),
                    id_=id_
                )

                await self._pep.publish(
                    namespaces.xep0084_metadata,
                    avatar_set.metadata,
                    id_=id_
                )
                done = True

            if self._synchronize_vcard:
                my_vcard = await self._vcard.get_vcard()
                my_vcard.set_photo_data("image/png",
                                        avatar_set.image_bytes)
                self._vcard_id = avatar_set.png_id
                await self._vcard.set_vcard(my_vcard)
                self._presence_server.resend_presence()
                done = True

        if not done:
            raise RuntimeError(
                "failed to publish avatar: no protocol available"
            )

    async def _disable_vcard_avatar(self):
        my_vcard = await self._vcard.get_vcard()
        my_vcard.clear_photo_data()
        self._vcard_id = ""
        await self._vcard.set_vcard(my_vcard)
        self._presence_server.resend_presence()

    async def disable_avatar(self):
        """
        Temporarily disable the avatar.

        If :attr:`synchronize_vcard` is true, the vCard avatar is
        disabled (even if disabling the PEP avatar fails).

        This is done by setting the avatar metadata node empty and if
        :attr:`synchronize_vcard` is true, downloading the vCard,
        removing the avatar data and re-uploading the vCard.

        This method does not error if neither protocol is active.

        :raises aioxmpp.errors.GatherError: if an exception is raised
            by the spawned tasks.
        """

        async with self._publish_lock:
            todo = []
            if self._synchronize_vcard:
                todo.append(self._disable_vcard_avatar())

            if await self._pep.available():
                todo.append(self._pep.publish(
                    namespaces.xep0084_metadata,
                    avatar_xso.Metadata()
                ))

            await gather_reraise_multi(*todo, message="disable_avatar")

    async def wipe_avatar(self):
        """
        Remove all avatar data stored on the server.

        If :attr:`synchronize_vcard` is true, the vCard avatar is
        disabled even if disabling the PEP avatar fails.

        This is equivalent to :meth:`disable_avatar` for vCard-based
        avatars, but will also remove the data PubSub node for
        PEP avatars.

        This method does not error if neither protocol is active.

        :raises aioxmpp.errors.GatherError: if an exception is raised
            by the spawned tasks.
        """

        async def _wipe_pep_avatar():
            await self._pep.publish(
                namespaces.xep0084_metadata,
                avatar_xso.Metadata()
            )
            await self._pep.publish(
                namespaces.xep0084_data,
                avatar_xso.Data(b'')
            )

        async with self._publish_lock:
            todo = []
            if self._synchronize_vcard:
                todo.append(self._disable_vcard_avatar())

            if await self._pep.available():
                todo.append(_wipe_pep_avatar())

            await gather_reraise_multi(*todo, message="wipe_avatar")
