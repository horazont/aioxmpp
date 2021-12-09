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
import aioxmpp.callbacks as callbacks
import aioxmpp.service as service
import aioxmpp.private_xml as private_xml

from . import xso as bookmark_xso


# TODO: use private storage in pubsub where available.
# TODO: sync bookmarks between pubsub and private xml storage
# TODO: do we need merge-capabilities to reconcile the bookmarks
# from different sources (local bookmark storage, pubsub, private xml
# storage)
class BookmarkClient(service.Service):
    """
    Supports retrieval and storage of bookmarks on the server.
    It currently only supports :xep:`Private XML Storage <49>` as
    backend.

    There is the general rule *never* to modify the bookmark instances
    retrieved from this class (either by :meth:`get_bookmarks` or as
    an argument to one of the signals). If you need to modify a bookmark
    for use with :meth:`update_bookmark` use :func:`copy.copy` to create
    a copy.

    .. automethod:: sync

    .. automethod:: get_bookmarks

    .. automethod:: set_bookmarks

    The following methods change the bookmark list in a get-modify-set
    pattern, to mitigate the danger of race conditions and should be
    used in most circumstances:

    .. automethod:: add_bookmark

    .. automethod:: discard_bookmark

    .. automethod:: update_bookmark


    The following signals are provided that allow tracking the changes to
    the bookmark list:

    .. signal:: on_bookmark_added(added_bookmark)

        Fires when a new bookmark is added.

    .. signal:: on_bookmark_removed(removed_bookmark)

        Fires when a bookmark is removed.

    .. signal:: on_bookmark_changed(old_bookmark, new_bookmark)

        Fires when a bookmark is changed.

    .. note:: A heuristic is used to determine the change of bookmarks
              and the reported changes may not directly reflect the
              used methods, but it will always be possible to
              construct the list of bookmarks from the events. For
              example, when using :meth:`update_bookmark` to change
              the JID of a :class:`Conference` bookmark a removed and
              a added signal will fire.

    .. note:: The bookmark protocol is prone to race conditions if
              several clients access it concurrently. Be careful to
              use a get-modify-set pattern or the provided highlevel
              interface.

    .. note:: Some other clients extend the bookmark format. For now
              those extensions are silently dropped by our XSOs, and
              therefore are lost, when changing the bookmarks with
              aioxmpp. This is considered a bug to be fixed in the future.
    """

    ORDER_AFTER = [
        private_xml.PrivateXMLService,
    ]

    on_bookmark_added = callbacks.Signal()
    on_bookmark_removed = callbacks.Signal()
    on_bookmark_changed = callbacks.Signal()

    def __init__(self, client, **kwargs):
        super().__init__(client, **kwargs)
        self._private_xml = self.dependencies[private_xml.PrivateXMLService]
        self._bookmark_cache = []
        self._lock = asyncio.Lock()

    @service.depsignal(aioxmpp.Client, "on_stream_established", defer=True)
    async def _stream_established(self):
        await self.sync()

    async def _get_bookmarks(self):
        """
        Get the stored bookmarks from the server.

        :returns: a list of bookmarks
        """
        res = await self._private_xml.get_private_xml(
            bookmark_xso.Storage()
        )

        return res.registered_payload.bookmarks

    async def _set_bookmarks(self, bookmarks):
        """
        Set the bookmarks stored on the server.
        """
        storage = bookmark_xso.Storage()
        storage.bookmarks[:] = bookmarks
        await self._private_xml.set_private_xml(storage)

    def _diff_emit_update(self, new_bookmarks):
        """
        Diff the bookmark cache and the new bookmark state, emit signals as
        needed and set the bookmark cache to the new data.
        """

        self.logger.debug("diffing %s, %s", self._bookmark_cache,
                          new_bookmarks)

        def subdivide(level, old, new):
            """
            Subdivide the bookmarks according to the data item
            ``bookmark.secondary[level]`` and emit the appropriate
            events.
            """
            if len(old) == len(new) == 1:
                old_entry = old.pop()
                new_entry = new.pop()
                if old_entry == new_entry:
                    pass
                else:
                    self.on_bookmark_changed(old_entry, new_entry)
                return ([], [])

            elif len(old) == 0:
                return ([], new)

            elif len(new) == 0:
                return (old, [])

            else:
                try:
                    groups = {}
                    for entry in old:
                        group = groups.setdefault(
                            entry.secondary[level],
                            ([], [])
                        )
                        group[0].append(entry)

                    for entry in new:
                        group = groups.setdefault(
                            entry.secondary[level],
                            ([], [])
                        )
                        group[1].append(entry)
                except IndexError:
                    # the classification is exhausted, this means
                    # all entries in this bin are equal by the
                    # definition of bookmark equivalence!
                    common = min(len(old), len(new))
                    assert old[:common] == new[:common]
                    return (old[common:], new[common:])

                old_unhandled, new_unhandled = [], []
                for old, new in groups.values():
                    unhandled = subdivide(level+1, old, new)
                    old_unhandled += unhandled[0]
                    new_unhandled += unhandled[1]

                # match up unhandleds as changes as early as possible
                i = -1
                for i, (old_entry, new_entry) in enumerate(
                        zip(old_unhandled, new_unhandled)):
                    self.logger.debug("changed %s -> %s", old_entry, new_entry)
                    self.on_bookmark_changed(old_entry, new_entry)
                i += 1
                return old_unhandled[i:], new_unhandled[i:]

        # group the bookmarks into groups whose elements may transform
        # among one another by on_bookmark_changed events. This information
        # is given by the type of the bookmark and the .primary property
        changable_groups = {}

        for item in self._bookmark_cache:
            group = changable_groups.setdefault(
                (type(item), item.primary),
                ([], [])
            )
            group[0].append(item)

        for item in new_bookmarks:
            group = changable_groups.setdefault(
                (type(item), item.primary),
                ([], [])
            )
            group[1].append(item)

        for old, new in changable_groups.values():

            # the first branches are fast paths which should catch
            # most cases – especially all cases where each bare jid of
            # a conference bookmark or each url of an url bookmark is
            # only used in one bookmark
            if len(old) == len(new) == 1:
                old_entry = old.pop()
                new_entry = new.pop()
                if old_entry == new_entry:
                    # the bookmark is unchanged, do not emit an event
                    pass
                else:
                    self.logger.debug("changed %s -> %s", old_entry, new_entry)
                    self.on_bookmark_changed(old_entry, new_entry)
            elif len(new) == 0:
                for removed in old:
                    self.logger.debug("removed %s", removed)
                    self.on_bookmark_removed(removed)
            elif len(old) == 0:
                for added in new:
                    self.logger.debug("added %s", added)
                    self.on_bookmark_added(added)
            else:
                old, new = subdivide(0, old, new)

                assert len(old) == 0 or len(new) == 0

                for removed in old:
                    self.logger.debug("removed %s", removed)
                    self.on_bookmark_removed(removed)

                for added in new:
                    self.logger.debug("added %s", added)
                    self.on_bookmark_added(added)

        self._bookmark_cache = new_bookmarks

    async def get_bookmarks(self):
        """
        Get the stored bookmarks from the server. Causes signals to be
        fired to reflect the changes.

        :returns: a list of bookmarks
        """
        async with self._lock:
            bookmarks = await self._get_bookmarks()
            self._diff_emit_update(bookmarks)
            return bookmarks

    async def set_bookmarks(self, bookmarks):
        """
        Store the sequence of bookmarks `bookmarks`.

        Causes signals to be fired to reflect the changes.

        .. note:: This should normally not be used. It does not
                  mitigate the race condition between clients
                  concurrently modifying the bookmarks and may lead to
                  data loss. Use :meth:`add_bookmark`,
                  :meth:`discard_bookmark` and :meth:`update_bookmark`
                  instead. This method still has use-cases (modifying
                  the bookmarklist at large, e.g. by syncing the
                  remote store with local data).
        """
        async with self._lock:
            await self._set_bookmarks(bookmarks)
            self._diff_emit_update(bookmarks)

    async def sync(self):
        """
        Sync the bookmarks between the local representation and the
        server.

        This must be called periodically to assure that the signals
        are fired.
        """
        await self.get_bookmarks()

    async def add_bookmark(self, new_bookmark, *, max_retries=3):
        """
        Add a bookmark and check whether it was successfully added to the
        bookmark list. Already existent bookmarks are not added twice.

        :param new_bookmark: the bookmark to add
        :type new_bookmark: an instance of :class:`~bookmark_xso.Bookmark`
        :param max_retries: the number of retries if setting the bookmark
                            fails
        :type max_retries: :class:`int`

        :raises RuntimeError: if the bookmark is not in the bookmark list
                              after `max_retries` retries.

        After setting the bookmark it is checked, whether the bookmark
        is in the online storage, if it is not it is tried again at most
        `max_retries` times to add the bookmark. A :class:`RuntimeError`
        is raised if the bookmark could not be added successfully after
        `max_retries`.
        """
        async with self._lock:
            bookmarks = await self._get_bookmarks()

            try:
                modified_bookmarks = list(bookmarks)
                if new_bookmark not in bookmarks:
                    modified_bookmarks.append(new_bookmark)
                await self._set_bookmarks(modified_bookmarks)

                retries = 0
                bookmarks = await self._get_bookmarks()
                while retries < max_retries:
                    if new_bookmark in bookmarks:
                        break
                    modified_bookmarks = list(bookmarks)
                    modified_bookmarks.append(new_bookmark)
                    await self._set_bookmarks(modified_bookmarks)
                    bookmarks = await self._get_bookmarks()
                    retries += 1

                if new_bookmark not in bookmarks:
                    raise RuntimeError("Could not add bookmark")

            finally:
                self._diff_emit_update(bookmarks)

    async def discard_bookmark(self, bookmark_to_remove, *, max_retries=3):
        """
        Remove a bookmark and check it has been removed.

        :param bookmark_to_remove: the bookmark to remove
        :type bookmark_to_remove: a :class:`~bookmark_xso.Bookmark` subclass.
        :param max_retries: the number of retries of removing the bookmark
                            fails.
        :type max_retries: :class:`int`

        :raises RuntimeError: if the bookmark is not removed from
                              bookmark list after `max_retries`
                              retries.

        If there are multiple occurrences of the same bookmark exactly
        one is removed.

        This does nothing if the bookmarks does not match an existing
        bookmark according to bookmark-equality.

        After setting the bookmark it is checked, whether the bookmark
        is removed in the online storage, if it is not it is tried
        again at most `max_retries` times to remove the bookmark. A
        :class:`RuntimeError` is raised if the bookmark could not be
        removed successfully after `max_retries`.
        """
        async with self._lock:
            bookmarks = await self._get_bookmarks()
            occurrences = bookmarks.count(bookmark_to_remove)

            try:
                if not occurrences:
                    return

                modified_bookmarks = list(bookmarks)
                modified_bookmarks.remove(bookmark_to_remove)
                await self._set_bookmarks(modified_bookmarks)

                retries = 0
                bookmarks = await self._get_bookmarks()
                new_occurences = bookmarks.count(bookmark_to_remove)
                while retries < max_retries:
                    if new_occurences < occurrences:
                        break
                    modified_bookmarks = list(bookmarks)
                    modified_bookmarks.remove(bookmark_to_remove)
                    await self._set_bookmarks(modified_bookmarks)
                    bookmarks = await self._get_bookmarks()
                    new_occurences = bookmarks.count(bookmark_to_remove)
                    retries += 1

                if new_occurences >= occurrences:
                    raise RuntimeError("Could not remove bookmark")
            finally:
                self._diff_emit_update(bookmarks)

    async def update_bookmark(self, old, new, *, max_retries=3):
        """
        Update a bookmark and check it was successful.

        The bookmark matches an existing bookmark `old` according to
        bookmark equalitiy and replaces it by `new`. The bookmark
        `new` is added if no bookmark matching `old` exists.

        :param old: the bookmark to replace
        :type bookmark_to_remove: a :class:`~bookmark_xso.Bookmark` subclass.
        :param new: the replacement bookmark
        :type bookmark_to_remove: a :class:`~bookmark_xso.Bookmark` subclass.
        :param max_retries: the number of retries of removing the bookmark
                            fails.
        :type max_retries: :class:`int`

        :raises RuntimeError: if the bookmark is not in the bookmark list
                              after `max_retries` retries.

        After replacing the bookmark it is checked, whether the
        bookmark `new` is in the online storage, if it is not it is
        tried again at most `max_retries` times to replace the
        bookmark. A :class:`RuntimeError` is raised if the bookmark
        could not be replaced successfully after `max_retries`.

        .. note:: Do not modify a bookmark retrieved from the signals
                  or from :meth:`get_bookmarks` to obtain the bookmark
                  `new`, this will lead to data corruption as they are
                  passed by reference.  Instead use :func:`copy.copy`
                  and modify the copy.

        """
        def replace_bookmark(bookmarks, old, new):
            modified_bookmarks = list(bookmarks)
            try:
                i = bookmarks.index(old)
                modified_bookmarks[i] = new
            except ValueError:
                modified_bookmarks.append(new)
            return modified_bookmarks

        async with self._lock:
            bookmarks = await self._get_bookmarks()

            try:
                await self._set_bookmarks(
                    replace_bookmark(bookmarks, old, new)
                )

                retries = 0
                bookmarks = await self._get_bookmarks()
                while retries < max_retries:
                    if new in bookmarks:
                        break
                    await self._set_bookmarks(
                        replace_bookmark(bookmarks, old, new)
                    )
                    bookmarks = await self._get_bookmarks()
                    retries += 1

                if new not in bookmarks:
                    raise RuntimeError("Cold not update bookmark")
            finally:
                self._diff_emit_update(bookmarks)
