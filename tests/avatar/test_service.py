########################################################################
# File name: test_service.py
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
import base64
import contextlib
import hashlib
import unittest

import aioxmpp
import aioxmpp.errors as errors
import aioxmpp.avatar.service as avatar_service
import aioxmpp.avatar.xso as avatar_xso
import aioxmpp.pubsub.xso as pubsub_xso
import aioxmpp.vcard
import aioxmpp.vcard.xso as vcard_xso

from aioxmpp.utils import namespaces
from aioxmpp.testutils import (
    make_connected_client,
    CoroutineMock,
    run_coroutine,
)

TEST_IMAGE = base64.decodebytes(b"""
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
""")

sha1 = hashlib.sha1()
sha1.update(TEST_IMAGE)
TEST_IMAGE_SHA1 = sha1.hexdigest()
del sha1

# jids used in the tests
TEST_FROM = aioxmpp.structs.JID.fromstr("foo@bar.example/baz")
TEST_FROM_OTHER = aioxmpp.structs.JID.fromstr("foo@bar.example/quux")
TEST_JID1 = aioxmpp.structs.JID.fromstr("bar@bar.example/baz")
TEST_JID2 = aioxmpp.structs.JID.fromstr("baz@bar.example/baz")
TEST_JID3 = aioxmpp.structs.JID.fromstr("baz@bar.example/quux")


class TestAvatarSet(unittest.TestCase):

    def test_construction(self):
        aset = avatar_service.AvatarSet()
        aset.add_avatar_image("image/png", image_bytes=TEST_IMAGE)
        aset.add_avatar_image("image/png",
                              nbytes=0,
                              id_="0000000000",
                              url="http://example.com/avatar")

        self.assertEqual(
            aset.image_bytes,
            TEST_IMAGE
        )

        self.assertEqual(
            aset.png_id,
            TEST_IMAGE_SHA1,
        )

        self.assertEqual(
            aset.metadata.info["image/png"][0].nbytes,
            len(TEST_IMAGE)
        )

        self.assertEqual(
            aset.metadata.info["image/png"][0].id_,
            TEST_IMAGE_SHA1,
        )

        self.assertEqual(
            aset.metadata.info["image/png"][1].nbytes,
            0,
        )

        self.assertEqual(
            aset.metadata.info["image/png"][1].id_,
            "0000000000",
        )

        self.assertEqual(
            aset.metadata.info["image/png"][1].url,
            "http://example.com/avatar",
        )

    def test_correct_redundant_information_is_ignored(self):
        try:
            aset = avatar_service.AvatarSet()
            aset.add_avatar_image("image/png",
                                  image_bytes=TEST_IMAGE,
                                  nbytes=len(TEST_IMAGE),
                                  id_=TEST_IMAGE_SHA1)
        except RuntimeError:
            self.fail("raises on correct redundant information")

    def test_png_id_is_normalized(self):
        for transmuted_sha1 in (TEST_IMAGE_SHA1.lower(),
                                TEST_IMAGE_SHA1.upper()):

            aset = avatar_service.AvatarSet()
            aset.add_avatar_image("image/png",
                                  image_bytes=TEST_IMAGE,
                                  id_=transmuted_sha1)

            self.assertEqual(
                aset.metadata.info["image/png"][0].id_,
                avatar_service.normalize_id(TEST_IMAGE_SHA1),
            )

    def test_error_id_missing(self):
        with self.assertRaisesRegex(
                RuntimeError,
                "^The SHA1 of the image data is not given an not inferable "):
            aset = avatar_service.AvatarSet()
            aset.add_avatar_image("image/png",
                                  nbytes=1024,
                                  url="http://example.com/avatar")

    def test_error_nbytes_missing(self):
        with self.assertRaisesRegex(
                RuntimeError,
                "^Image data length is not given an not inferable "):
            aset = avatar_service.AvatarSet()
            aset.add_avatar_image("image/png",
                                  id_="00000000000000000000",
                                  url="http://example.com/avatar")

    def test_error_no_image_given(self):
        with self.assertRaisesRegex(
                RuntimeError,
                "^Either the image bytes or an url to retrieve the avatar "):
            aset = avatar_service.AvatarSet()
            aset.add_avatar_image("image/png",
                                  id_="00000000000000000000",
                                  nbytes=0)

    def test_error_image_data_for_something_other_than_png(self):
        with self.assertRaisesRegex(
                RuntimeError,
                "^The image bytes can only be given for image/png data\.$"):
            aset = avatar_service.AvatarSet()
            aset.add_avatar_image("image/gif",
                                  nbytes=1024,
                                  id_="00000000000000000000",
                                  image_bytes=TEST_IMAGE)

    def test_error_two_items_with_image_data(self):
        with self.assertRaisesRegex(
                RuntimeError,
                "^Only one avatar image may be published directly\.$"):
            aset = avatar_service.AvatarSet()
            aset.add_avatar_image("image/png",
                                  image_bytes=TEST_IMAGE)
            aset.add_avatar_image("image/png",
                                  image_bytes=TEST_IMAGE)

    def test_error_redundant_sha_mismatch(self):
        with self.assertRaisesRegex(
                RuntimeError,
                "^The given id does not match the SHA1 of the image data\.$"):
            aset = avatar_service.AvatarSet()
            aset.add_avatar_image("image/png",
                                  id_="00000000000000000000",
                                  image_bytes=TEST_IMAGE)

    def test_error_redundant_nbytes_mismatch(self):
        with self.assertRaisesRegex(
                RuntimeError,
                "^The given length does not match the length "
                "of the image data\.$"):
            aset = avatar_service.AvatarSet()
            aset.add_avatar_image("image/png",
                                  nbytes=0,
                                  image_bytes=TEST_IMAGE)

    def test_error_no_image(self):
        with self.assertRaisesRegex(
                RuntimeError,
                "^Either the image bytes or an url to retrieve the avatar "):
            aset = avatar_service.AvatarSet()
            aset.add_avatar_image("image/png")


class TestAvatarService(unittest.TestCase):
    def setUp(self):
        self.cc = make_connected_client()
        self.cc.local_jid = TEST_FROM

        self.disco_client = aioxmpp.DiscoClient(self.cc)
        self.disco = aioxmpp.DiscoServer(self.cc)
        self.presence_dispatcher = aioxmpp.dispatcher.SimplePresenceDispatcher(
            self.cc
        )
        self.presence_client = aioxmpp.PresenceClient(self.cc, dependencies={
            aioxmpp.dispatcher.SimplePresenceDispatcher:
                self.presence_dispatcher,
        })
        self.presence_server = aioxmpp.PresenceServer(self.cc)
        self.vcard = aioxmpp.vcard.VCardService(self.cc)

        self.pubsub = aioxmpp.PubSubClient(self.cc, dependencies={
            aioxmpp.DiscoClient: self.disco_client
        })

        self.pep = aioxmpp.PEPClient(self.cc, dependencies={
            aioxmpp.DiscoClient: self.disco_client,
            aioxmpp.DiscoServer: self.disco,
            aioxmpp.PubSubClient: self.pubsub,
        })

        self.s = avatar_service.AvatarService(self.cc, dependencies={
            aioxmpp.DiscoClient: self.disco_client,
            aioxmpp.DiscoServer: self.disco,
            aioxmpp.PubSubClient: self.pubsub,
            aioxmpp.PEPClient: self.pep,
            aioxmpp.PresenceClient: self.presence_client,
            aioxmpp.PresenceServer: self.presence_server,
            aioxmpp.vcard.VCardService: self.vcard
        })

        self.pep._check_for_pep = CoroutineMock()
        self.pep.available = CoroutineMock()
        self.pep.available.return_value = True

        self.cc.mock_calls.clear()

    def tearDown(self):
        del self.s
        del self.cc
        del self.disco_client
        del self.disco
        del self.pubsub

    def test_is_service(self):
        self.assertTrue(issubclass(
            avatar_service.AvatarService,
            aioxmpp.service.Service
        ))

    def test_service_order(self):
        self.assertGreater(
            avatar_service.AvatarService,
            aioxmpp.DiscoClient,
        )

        self.assertGreater(
            avatar_service.AvatarService,
            aioxmpp.DiscoServer,
        )

        self.assertGreater(
            avatar_service.AvatarService,
            aioxmpp.PubSubClient,
        )

    def test_metadata_cache_size(self):
        self.assertEqual(self.s.metadata_cache_size, 200)
        self.s.metadata_cache_size = 100
        self.assertEqual(self.s.metadata_cache_size, 100)

    def test_handle_stream_destroyed_is_depsignal_handler(self):
        self.assertTrue(aioxmpp.service.is_depsignal_handler(
            aioxmpp.stream.StanzaStream,
            "on_stream_destroyed",
            self.s.handle_stream_destroyed
        ))

    def test_handle_stream_destroyer(self):
        # for now just check the code can be run without errors,
        # it is difficult to check this properly, as we do not
        # know which caches should be wiped a priori
        self.s.handle_stream_destroyed(unittest.mock.Mock())

    def test_attach_vcard_notify_to_presence_is_depfilter(self):
        self.assertTrue(aioxmpp.service.is_depfilter_handler(
            aioxmpp.stream.StanzaStream,
            "service_outbound_presence_filter",
            self.s._attach_vcard_notify_to_presence
        ))

    def test_attach_vcard_notify_to_presence(self):
        stanza = aioxmpp.Presence()
        stanza = self.s._attach_vcard_notify_to_presence(stanza)
        self.assertIsInstance(stanza.xep0153_x,
                              avatar_xso.VCardTempUpdate)
        self.assertIsNone(stanza.xep0153_x.photo)

        vcard_id = '1234'
        self.s._vcard_id = vcard_id
        stanza = aioxmpp.Presence()
        stanza = self.s._attach_vcard_notify_to_presence(stanza)
        self.assertIsInstance(stanza.xep0153_x,
                              avatar_xso.VCardTempUpdate)
        self.assertEqual(stanza.xep0153_x.photo, vcard_id)

        self.s._vcard_resource_interference.add(TEST_JID1)
        stanza = aioxmpp.Presence()
        stanza = self.s._attach_vcard_notify_to_presence(stanza)
        self.assertIsNone(stanza.xep0153_x)

    def test_handle_on_available_is_depsignal_handler(self):
        self.assertTrue(aioxmpp.service.is_depsignal_handler(
            aioxmpp.PresenceClient,
            "on_available",
            self.s._handle_on_available
        ))

    def test_resource_interference(self):
        stanza = aioxmpp.Presence()

        self.s._handle_on_available(TEST_FROM_OTHER, stanza)
        self.assertCountEqual(
            self.s._vcard_resource_interference,
            [TEST_FROM_OTHER]
        )

        stanza = aioxmpp.Presence()
        self.s._handle_on_unavailable(TEST_FROM_OTHER, stanza)
        self.assertCountEqual(
            self.s._vcard_resource_interference,
            []
        )

    def test_trigger_rehash(self):
        mock_handler = unittest.mock.Mock()
        self.s.on_metadata_changed.connect(mock_handler)

        stanza = aioxmpp.Presence()
        stanza.xep0153_x = avatar_xso.VCardTempUpdate("1234")
        self.s._handle_on_available(TEST_FROM_OTHER, stanza)

        first_rehash_task = self.s._vcard_rehash_task
        self.assertIsNot(first_rehash_task, None)

        # presence with the same hash does not affect the rehash task
        self.s._vcard_id = "1234"
        stanza = aioxmpp.Presence()
        stanza.xep0153_x = avatar_xso.VCardTempUpdate("1234")
        self.s._handle_on_available(TEST_FROM_OTHER, stanza)
        self.assertIs(self.s._vcard_rehash_task, first_rehash_task)

        # presence with another hash cancels the task
        stanza = aioxmpp.Presence()
        stanza.xep0153_x = avatar_xso.VCardTempUpdate("4321")
        self.s._handle_on_available(TEST_FROM_OTHER, stanza)

        with unittest.mock.patch.object(self.vcard, "get_vcard",
                                        new=CoroutineMock()):
            vcard = vcard_xso.VCard()
            self.vcard.get_vcard.return_value = vcard
            vcard.set_photo_data("image/png", TEST_IMAGE)

            loop = asyncio.get_event_loop()
            with self.assertRaises(asyncio.CancelledError):
                loop.run_until_complete(first_rehash_task)
            self.assertTrue(first_rehash_task.cancelled())

            loop.run_until_complete(
                self.s._vcard_rehash_task
            )

        self.assertEqual(self.s._vcard_id, TEST_IMAGE_SHA1)

        with unittest.mock.patch.object(self.vcard, "get_vcard",
                                        new=CoroutineMock()):
            vcard = vcard_xso.VCard()
            self.vcard.get_vcard.return_value = vcard

            stanza = aioxmpp.Presence()
            stanza.xep0153_x = avatar_xso.VCardTempUpdate("9132752")
            self.s._handle_on_available(TEST_FROM_OTHER, stanza)

            loop.run_until_complete(
                self.s._vcard_rehash_task
            )

        self.assertEqual(self.s._vcard_id, "")

        # XXX: should we test minutely that we get the right metadata
        mock_handler.assert_called_with(TEST_FROM_OTHER, unittest.mock.ANY)

    def test_handle_on_changed_is_depsignal_handler(self):
        self.assertTrue(aioxmpp.service.is_depsignal_handler(
            aioxmpp.PresenceClient,
            "on_changed",
            self.s._handle_on_changed
        ))

    def test_handle_notify_without_photo_is_noop(self):
        mock_handler = unittest.mock.Mock()
        self.s.on_metadata_changed.connect(mock_handler)

        stanza = aioxmpp.Presence()
        self.s._handle_notify(TEST_JID1, stanza)
        stanza.xep0153_x = avatar_xso.VCardTempUpdate()
        self.s._handle_notify(TEST_JID1, stanza)

        self.assertEqual(len(mock_handler.mock_calls), 0)

    def test_handle_on_changed(self):
        with unittest.mock.patch.object(self.s, "_handle_notify"):
            self.s._handle_on_changed(unittest.mock.sentinel.jid,
                                      unittest.mock.sentinel.staza)
            self.assertSequenceEqual(
                self.s._handle_notify.mock_calls,
                [
                    unittest.mock.call(unittest.mock.sentinel.jid,
                                       unittest.mock.sentinel.staza)
                ]
            )

    def test_handle_on_unavailable_is_depsignal_handler(self):
        self.assertTrue(aioxmpp.service.is_depsignal_handler(
            aioxmpp.PresenceClient,
            "on_unavailable",
            self.s._handle_on_unavailable
        ))

    def test_publish_avatar_set(self):
        # set the cache to indicate the server has PEP

        avatar_set = avatar_service.AvatarSet()
        avatar_set.add_avatar_image("image/png", image_bytes=TEST_IMAGE)

        with unittest.mock.patch.object(self.pep, "publish",
                                        new=CoroutineMock()):
            run_coroutine(self.s.publish_avatar_set(avatar_set))

            self.assertSequenceEqual(
                self.pep.publish.mock_calls,
                [
                    unittest.mock.call(
                        namespaces.xep0084_data,
                        unittest.mock.ANY,
                        id_=avatar_set.png_id
                    ),
                    unittest.mock.call(
                        namespaces.xep0084_metadata,
                        avatar_set.metadata,
                        id_=avatar_set.png_id
                    )
                ],
            )

            _, args, _ = self.pep.publish.mock_calls[0]
            data = args[1]
            self.assertTrue(isinstance(data, avatar_xso.Data))
            self.assertEqual(data.data, avatar_set.image_bytes)

    def test_publish_avatar_no_protocol_raises(self):
        self.pep.available.return_value = False
        self.s.synchronize_vcard = False

        with self.assertRaises(RuntimeError):
            run_coroutine(self.s.publish_avatar_set(unittest.mock.Mock()))

    def test_publish_avatar_set_synchronize_vcard(self):

        avatar_set = avatar_service.AvatarSet()
        avatar_set.add_avatar_image("image/png", image_bytes=TEST_IMAGE)
        self.assertFalse(self.s.synchronize_vcard)
        self.s.synchronize_vcard = True
        self.assertTrue(self.s.synchronize_vcard)

        with contextlib.ExitStack() as e:
            e.enter_context(unittest.mock.patch.object(self.pep, "publish",
                                                       new=CoroutineMock()))
            e.enter_context(unittest.mock.patch.object(self.presence_server,
                                                       "resend_presence",
                                                       new=CoroutineMock()))
            e.enter_context(unittest.mock.patch.object(self.vcard, "get_vcard",
                                                       new=CoroutineMock()))
            e.enter_context(unittest.mock.patch.object(self.vcard, "set_vcard",
                                                       new=CoroutineMock()))
            self.vcard.get_vcard.return_value = unittest.mock.Mock()
            run_coroutine(self.s.publish_avatar_set(avatar_set))

            self.assertSequenceEqual(
                self.presence_server.resend_presence.mock_calls,
                [unittest.mock.call()]
            )

            self.assertSequenceEqual(
                self.vcard.get_vcard.mock_calls,
                [
                    unittest.mock.call(),
                    unittest.mock.call().set_photo_data("image/png",
                                                        TEST_IMAGE),
                ]
            )

            self.assertSequenceEqual(
                self.vcard.set_vcard.mock_calls,
                [
                    unittest.mock.call(self.vcard.get_vcard.return_value),
                ]
            )

            self.assertSequenceEqual(
                self.pep.publish.mock_calls,
                [
                    unittest.mock.call(
                        namespaces.xep0084_data,
                        unittest.mock.ANY,
                        id_=avatar_set.png_id
                    ),
                    unittest.mock.call(
                        namespaces.xep0084_metadata,
                        avatar_set.metadata,
                        id_=avatar_set.png_id
                    )
                ],
            )

            _, args, _ = self.pep.publish.mock_calls[0]
            data = args[1]
            self.assertTrue(isinstance(data, avatar_xso.Data))
            self.assertEqual(data.data, avatar_set.image_bytes)

    def test_publish_avatar_set_synchronize_vcard_pep_raises(self):
        avatar_set = avatar_service.AvatarSet()
        avatar_set.add_avatar_image("image/png", image_bytes=TEST_IMAGE)
        self.s.synchronize_vcard = True

        with contextlib.ExitStack() as e:
            e.enter_context(unittest.mock.patch.object(self.pep, "publish",
                                                       new=CoroutineMock()))
            e.enter_context(unittest.mock.patch.object(self.presence_server,
                                                       "resend_presence",
                                                       new=CoroutineMock()))
            e.enter_context(unittest.mock.patch.object(self.vcard, "get_vcard",
                                                       new=CoroutineMock()))
            e.enter_context(unittest.mock.patch.object(self.vcard, "set_vcard",
                                                       new=CoroutineMock()))

            # do not do the vcard operations of pep is available but
            # fails
            self.pep.publish.side_effect = RuntimeError

            self.vcard.get_vcard.return_value = unittest.mock.Mock()

            with self.assertRaises(RuntimeError):
                run_coroutine(self.s.publish_avatar_set(avatar_set))

            self.assertSequenceEqual(
                self.presence_server.resend_presence.mock_calls,
                []
            )

            self.assertSequenceEqual(
                self.vcard.get_vcard.mock_calls,
                []
            )

            self.assertSequenceEqual(
                self.vcard.set_vcard.mock_calls,
                []
            )

    def test_disable_avatar(self):
        with unittest.mock.patch.object(self.pep, "publish",
                                        new=CoroutineMock()):
            run_coroutine(self.s.disable_avatar())

            self.assertSequenceEqual(
                self.pep.publish.mock_calls,
                [
                    unittest.mock.call(
                        namespaces.xep0084_metadata,
                        unittest.mock.ANY,
                    ),
                ]
            )

            _, args, _ = self.pep.publish.mock_calls[0]
            metadata = args[1]

            self.assertTrue(isinstance(metadata, avatar_xso.Metadata))
            self.assertEqual(0, len(metadata.info))
            self.assertEqual(0, len(metadata.pointer))

    def test_wipe_avatar(self):
        with unittest.mock.patch.object(self.pep, "publish",
                                        new=CoroutineMock()):
            run_coroutine(self.s.wipe_avatar())

            self.assertSequenceEqual(
                self.pep.publish.mock_calls,
                [
                    unittest.mock.call(
                        namespaces.xep0084_metadata,
                        unittest.mock.ANY,
                    ),
                    unittest.mock.call(
                        namespaces.xep0084_data,
                        unittest.mock.ANY,
                    ),
                ]
            )

            _, args, _ = self.pep.publish.mock_calls[0]
            metadata = args[1]

            self.assertTrue(isinstance(metadata, avatar_xso.Metadata))
            self.assertEqual(0, len(metadata.info))
            self.assertEqual(0, len(metadata.pointer))

            _, args, _ = self.pep.publish.mock_calls[1]
            data = args[1]

            self.assertTrue(isinstance(data, avatar_xso.Data))
            self.assertEqual(0, len(data.data))

    def test_wipe_avatar_with_vcard(self):
        self.s.synchronize_vcard = True
        with contextlib.ExitStack() as e:
            e.enter_context(unittest.mock.patch.object(self.pep, "publish",
                                                       new=CoroutineMock()))
            e.enter_context(unittest.mock.patch.object(self.presence_server,
                                                       "resend_presence",
                                                       new=CoroutineMock()))
            e.enter_context(unittest.mock.patch.object(self.vcard, "get_vcard",
                                                       new=CoroutineMock()))
            e.enter_context(unittest.mock.patch.object(self.vcard, "set_vcard",
                                                       new=CoroutineMock()))
            self.vcard.get_vcard.return_value = unittest.mock.Mock()
            run_coroutine(self.s.wipe_avatar())

            self.assertSequenceEqual(
                self.presence_server.resend_presence.mock_calls,
                [unittest.mock.call()]
            )

            self.assertSequenceEqual(
                self.vcard.get_vcard.mock_calls,
                [unittest.mock.call(),
                 unittest.mock.call().clear_photo_data()]
            )

            self.assertSequenceEqual(
                self.vcard.set_vcard.mock_calls,
                [unittest.mock.call(unittest.mock.ANY)]
            )

            self.assertSequenceEqual(
                self.pep.publish.mock_calls,
                [
                    unittest.mock.call(
                        namespaces.xep0084_metadata,
                        unittest.mock.ANY,
                    ),
                    unittest.mock.call(
                        namespaces.xep0084_data,
                        unittest.mock.ANY,
                    ),
                ]
            )

            _, args, _ = self.pep.publish.mock_calls[0]
            metadata = args[1]

            self.assertTrue(isinstance(metadata, avatar_xso.Metadata))
            self.assertEqual(0, len(metadata.info))
            self.assertEqual(0, len(metadata.pointer))

            _, args, _ = self.pep.publish.mock_calls[1]
            data = args[1]

            self.assertTrue(isinstance(data, avatar_xso.Data))
            self.assertEqual(0, len(data.data))



    def test_disable_avatar_synchronize_vcard_pep_raises(self):
        self.s.synchronize_vcard = True

        with contextlib.ExitStack() as e:
            e.enter_context(unittest.mock.patch.object(self.pep, "publish",
                                                       new=CoroutineMock()))
            e.enter_context(unittest.mock.patch.object(self.presence_server,
                                                       "resend_presence",
                                                       new=CoroutineMock()))
            e.enter_context(unittest.mock.patch.object(self.vcard, "get_vcard",
                                                       new=CoroutineMock()))
            e.enter_context(unittest.mock.patch.object(self.vcard, "set_vcard",
                                                       new=CoroutineMock()))

            # do not do the vcard operations of pep is available but
            # fails
            self.pep.publish.side_effect = RuntimeError

            self.vcard.get_vcard.return_value = unittest.mock.Mock()

            with self.assertRaises(RuntimeError):
                run_coroutine(self.s.disable_avatar())

            self.assertSequenceEqual(
                self.presence_server.resend_presence.mock_calls,
                [unittest.mock.call()]
            )

            self.assertSequenceEqual(
                self.vcard.get_vcard.mock_calls,
                [unittest.mock.call(),
                 unittest.mock.call().clear_photo_data()]
            )

            self.assertSequenceEqual(
                self.vcard.set_vcard.mock_calls,
                [unittest.mock.call(unittest.mock.ANY)]
            )

    def test_handle_pubsub_publish(self):
        self.assertTrue(aioxmpp.service.is_attrsignal_handler(
            avatar_service.AvatarService.avatar_pep,
            "on_item_publish",
            self.s.handle_pubsub_publish
        ))

        aset = avatar_service.AvatarSet()
        aset.add_avatar_image("image/png", image_bytes=TEST_IMAGE)
        aset.add_avatar_image("image/png",
                              nbytes=0,
                              id_="00000000000000000000",
                              url="http://example.com/avatar")

        # construct the proper pubsub response
        item = pubsub_xso.EventItem(aset.metadata, id_=aset.png_id)

        mock_handler = unittest.mock.Mock()
        self.s.on_metadata_changed.connect(mock_handler)

        self.s.handle_pubsub_publish(
            TEST_JID1,
            namespaces.xep0084_metadata,
            item)

        descriptors = self.s._metadata_cache[TEST_JID1]
        self.assertEqual(len(descriptors), 2)

        png_descr = descriptors

        self.assertTrue(isinstance(png_descr[0],
                                   avatar_service.PubsubAvatarDescriptor))
        self.assertEqual(png_descr[0].mime_type, "image/png")
        self.assertEqual(png_descr[0].id_, TEST_IMAGE_SHA1)
        self.assertEqual(png_descr[0].nbytes, len(TEST_IMAGE))
        self.assertEqual(png_descr[0].url, None)

        self.assertTrue(isinstance(png_descr[0],
                                   avatar_service.PubsubAvatarDescriptor))

        self.assertEqual(png_descr[1].mime_type, "image/png")
        self.assertEqual(png_descr[1].id_, "00000000000000000000")
        self.assertEqual(png_descr[1].nbytes, 0)
        self.assertEqual(png_descr[1].url, "http://example.com/avatar")

        mock_handler.assert_called_with(TEST_JID1, descriptors)

    def test_get_avatar_metadata(self):
        aset = avatar_service.AvatarSet()
        aset.add_avatar_image("image/png", image_bytes=TEST_IMAGE)
        aset.add_avatar_image("image/png",
                              nbytes=0,
                              id_="00000000000000000000",
                              url="http://example.com/avatar")

        # construct the proper pubsub response
        items = pubsub_xso.Items(
            namespaces.xep0084_metadata,
        )
        item = pubsub_xso.Item(id_=aset.png_id)
        item.registered_payload = aset.metadata
        items.items.append(item)

        pubsub_result = pubsub_xso.Request(items)

        with unittest.mock.patch.object(self.pubsub, "get_items",
                                        new=CoroutineMock()):
            self.pubsub.get_items.return_value = pubsub_result

            descriptors = run_coroutine(self.s.get_avatar_metadata(TEST_JID1))

            self.assertSequenceEqual(
                self.pubsub.get_items.mock_calls,
                [
                    unittest.mock.call(
                        TEST_JID1,
                        namespaces.xep0084_metadata,
                        max_items=1
                    )
                ]
            )

            self.assertEqual(len(descriptors), 2)

            png_descr = descriptors

            self.assertTrue(isinstance(png_descr[0],
                                       avatar_service.PubsubAvatarDescriptor))
            self.assertEqual(png_descr[0].mime_type, "image/png")
            self.assertEqual(png_descr[0].id_, TEST_IMAGE_SHA1)
            self.assertEqual(png_descr[0].nbytes, len(TEST_IMAGE))
            self.assertEqual(png_descr[0].url, None)

            self.assertTrue(isinstance(png_descr[0],
                                       avatar_service.PubsubAvatarDescriptor))

            self.assertEqual(png_descr[1].mime_type, "image/png")
            self.assertEqual(png_descr[1].id_, "00000000000000000000")
            self.assertEqual(png_descr[1].nbytes, 0)
            self.assertEqual(png_descr[1].url, "http://example.com/avatar")

        with unittest.mock.patch.object(self.pubsub, "get_items",
                                        new=CoroutineMock()):

            cached_descriptors = run_coroutine(
                self.s.get_avatar_metadata(TEST_JID1)
            )

            self.assertEqual(descriptors, cached_descriptors)

            # we must get the descriptors from the cache
            self.pubsub.get_items.assert_not_called()

        with unittest.mock.patch.object(self.pubsub, "get_items",
                                        new=CoroutineMock()):

            self.pubsub.get_items.return_value = pubsub_result
            descriptors = run_coroutine(
                self.s.get_avatar_metadata(TEST_JID1, require_fresh=True)
            )

            self.assertSequenceEqual(
                self.pubsub.get_items.mock_calls,
                [
                    unittest.mock.call(
                        TEST_JID1,
                        namespaces.xep0084_metadata,
                        max_items=1
                    )
                ]
            )

    def test_get_avatar_metadata_with_require_fresh_does_not_crash(self):
        aset = avatar_service.AvatarSet()
        aset.add_avatar_image("image/png", image_bytes=TEST_IMAGE)
        aset.add_avatar_image("image/png",
                              nbytes=0,
                              id_="00000000000000000000",
                              url="http://example.com/avatar")

        # construct the proper pubsub response
        items = pubsub_xso.Items(
            namespaces.xep0084_metadata,
        )
        item = pubsub_xso.Item(id_=aset.png_id)
        item.registered_payload = aset.metadata
        items.items.append(item)

        pubsub_result = pubsub_xso.Request(items)

        with unittest.mock.patch.object(self.pubsub, "get_items",
                                        new=CoroutineMock()):

            self.pubsub.get_items.return_value = pubsub_result
            run_coroutine(
                self.s.get_avatar_metadata(TEST_JID1, require_fresh=True)
            )

            self.assertSequenceEqual(
                self.pubsub.get_items.mock_calls,
                [
                    unittest.mock.call(
                        TEST_JID1,
                        namespaces.xep0084_metadata,
                        max_items=1
                    )
                ]
            )

    def test_get_avatar_metadata_vcard_fallback(self):
        sha1 = hashlib.sha1(b'')
        empty_sha1 = sha1.hexdigest()

        with contextlib.ExitStack() as e:
            e.enter_context(unittest.mock.patch.object(
                self.pubsub, "get_items",
                new=CoroutineMock()))
            e.enter_context(unittest.mock.patch.object(
                self.vcard, "get_vcard",
                new=CoroutineMock()))
            vcard_mock = unittest.mock.Mock()
            vcard_mock.get_photo_data.return_value = b''
            self.vcard.get_vcard.return_value = vcard_mock

            self.pubsub.get_items.side_effect = errors.XMPPCancelError(
                (namespaces.stanzas, "feature-not-implemented")
            )

            res = run_coroutine(self.s.get_avatar_metadata(TEST_JID1))

            self.assertEqual(len(res), 1)
            self.assertIsInstance(res[0],
                                  avatar_service.VCardAvatarDescriptor)
            self.assertEqual(res[0]._image_bytes,
                             b'')
            self.assertEqual(res[0].id_,
                             empty_sha1)
            self.assertEqual(res[0].nbytes,
                             0)

            self.assertSequenceEqual(
                self.pubsub.get_items.mock_calls,
                [
                    unittest.mock.call(
                        TEST_JID1,
                        namespaces.xep0084_metadata,
                        max_items=1
                    ),
                ]
            )

        with contextlib.ExitStack() as e:
            e.enter_context(unittest.mock.patch.object(
                self.pubsub, "get_items",
                new=CoroutineMock()))
            e.enter_context(unittest.mock.patch.object(
                self.vcard, "get_vcard",
                new=CoroutineMock()))
            vcard_mock = unittest.mock.Mock()
            vcard_mock.get_photo_data.return_value = b''
            self.vcard.get_vcard.return_value = vcard_mock

            self.pubsub.get_items.side_effect = errors.XMPPCancelError(
                (namespaces.stanzas, "item-not-found")
            )

            res = run_coroutine(self.s.get_avatar_metadata(TEST_JID2))

            self.assertEqual(len(res), 1)
            self.assertIsInstance(res[0],
                                  avatar_service.VCardAvatarDescriptor)
            self.assertEqual(res[0]._image_bytes,
                             b'')
            self.assertEqual(res[0].id_,
                             empty_sha1)
            self.assertEqual(res[0].nbytes,
                             0)

            self.assertSequenceEqual(
                self.pubsub.get_items.mock_calls,
                [
                    unittest.mock.call(
                        TEST_JID2,
                        namespaces.xep0084_metadata,
                        max_items=1
                    ),
                ]
            )

        with contextlib.ExitStack() as e:
            e.enter_context(unittest.mock.patch.object(
                self.pubsub, "get_items",
                new=CoroutineMock()))
            e.enter_context(unittest.mock.patch.object(
                self.vcard, "get_vcard",
                new=CoroutineMock()))
            vcard_mock = unittest.mock.Mock()
            vcard_mock.get_photo_data.return_value = None
            self.vcard.get_vcard.return_value = vcard_mock

            self.pubsub.get_items.side_effect = errors.XMPPCancelError(
                (namespaces.stanzas, "item-not-found")
            )

            res = run_coroutine(self.s.get_avatar_metadata(TEST_JID3))
            self.assertEqual(len(res), 0)

            self.assertSequenceEqual(
                self.pubsub.get_items.mock_calls,
                [
                    unittest.mock.call(
                        TEST_JID3,
                        namespaces.xep0084_metadata,
                        max_items=1
                    ),
                ]
            )

    def test_subscribe(self):
        with unittest.mock.patch.object(self.pubsub, "subscribe",
                                        new=CoroutineMock()):
            run_coroutine(self.s.subscribe(TEST_JID1))

            self.assertSequenceEqual(
                self.pubsub.subscribe.mock_calls,
                [
                    unittest.mock.call(
                        TEST_JID1,
                        namespaces.xep0084_metadata
                    ),
                ]
            )


class TestAvatarDescriptors(unittest.TestCase):

    def setUp(self):
        self.cc = make_connected_client()
        self.cc.local_jid = TEST_FROM
        self.vcard = aioxmpp.vcard.VCardService(self.cc)
        self.disco = aioxmpp.DiscoClient(self.cc)
        self.pubsub = aioxmpp.PubSubClient(self.cc, dependencies={
            aioxmpp.DiscoClient: self.disco
        })

        self.cc.mock_calls.clear()

    def test_attributes_defined_by_AbstractAvatarDescriptor(self):
        a = avatar_service.AbstractAvatarDescriptor(
            TEST_JID1, TEST_IMAGE_SHA1, mime_type="image/png",
            nbytes=len(TEST_IMAGE)
        )
        with self.assertRaises(NotImplementedError):
            run_coroutine(a.get_image_bytes())

        self.assertFalse(a.has_image_data_in_pubsub)
        self.assertFalse(a.can_get_image_bytes_via_xmpp)

        self.assertEqual(a.remote_jid, TEST_JID1)
        self.assertEqual(a.mime_type, "image/png")
        self.assertEqual(a.id_, TEST_IMAGE_SHA1)
        self.assertEqual(a.nbytes, len(TEST_IMAGE))
        self.assertEqual(a.normalized_id,
                         avatar_service.normalize_id(TEST_IMAGE_SHA1))
        self.assertEqual(a.url, None)
        self.assertEqual(a.width, None)
        self.assertEqual(a.height, None)

    def test_vcard_get_image_bytes(self):
        descriptor = avatar_service.VCardAvatarDescriptor(
            TEST_JID1,
            TEST_IMAGE_SHA1.upper(),
            nbytes=len(TEST_IMAGE),
            vcard=self.vcard,
            image_bytes=TEST_IMAGE,
        )

        self.assertTrue(descriptor.has_image_data_in_pubsub)
        self.assertTrue(descriptor.can_get_image_bytes_via_xmpp)

        with unittest.mock.patch.object(self.vcard, "get_vcard",
                                        new=CoroutineMock()):
            self.assertEqual(
                run_coroutine(descriptor.get_image_bytes()),
                TEST_IMAGE
            )
            self.assertSequenceEqual(self.vcard.get_vcard.mock_calls, [])

        descriptor = avatar_service.VCardAvatarDescriptor(
            TEST_JID1,
            TEST_IMAGE_SHA1.upper(),
            nbytes=len(TEST_IMAGE),
            vcard=self.vcard,
        )

        with unittest.mock.patch.object(self.vcard, "get_vcard",
                                        new=CoroutineMock()):
            vcard_mock = unittest.mock.Mock()
            vcard_mock.get_photo_data.return_value = TEST_IMAGE
            self.vcard.get_vcard.return_value = vcard_mock
            self.assertEqual(
                run_coroutine(descriptor.get_image_bytes()),
                TEST_IMAGE
            )

            vcard_mock.get_photo_data.return_value = None
            with self.assertRaises(RuntimeError):
                run_coroutine(descriptor.get_image_bytes())

            self.assertSequenceEqual(
                self.vcard.get_vcard.mock_calls,
                [
                    unittest.mock.call(
                        TEST_JID1
                    ),
                    unittest.mock.call().get_photo_data(),
                    unittest.mock.call(
                        TEST_JID1
                    ),
                    unittest.mock.call().get_photo_data(),
                ]
            )

    def test_pep_get_image_bytes(self):
        descriptor = avatar_service.PubsubAvatarDescriptor(
            TEST_JID1,
            TEST_IMAGE_SHA1.upper(),
            mime_type="image/png",
            nbytes=len(TEST_IMAGE),
            pubsub=self.pubsub
        )

        self.assertTrue(descriptor.has_image_data_in_pubsub)
        self.assertEqual(TEST_IMAGE_SHA1, descriptor.normalized_id)

        items = pubsub_xso.Items(
            namespaces.xep0084_data,
        )
        pubsub_result = pubsub_xso.Request(items)

        with unittest.mock.patch.object(self.pubsub, "get_items_by_id",
                                        new=CoroutineMock()):
            self.pubsub.get_items_by_id.return_value = pubsub_result
            with self.assertRaises(RuntimeError):
                res = run_coroutine(descriptor.get_image_bytes())

            item = pubsub_xso.Item(id_=TEST_IMAGE_SHA1)
            item.registered_payload = avatar_xso.Data(TEST_IMAGE)
            items.items.append(item)

            res = run_coroutine(descriptor.get_image_bytes())

            self.assertSequenceEqual(
                self.pubsub.get_items_by_id.mock_calls,
                [
                    unittest.mock.call(
                        TEST_JID1,
                        namespaces.xep0084_data,
                        [TEST_IMAGE_SHA1.upper()],
                    ),
                    unittest.mock.call(
                        TEST_JID1,
                        namespaces.xep0084_data,
                        [TEST_IMAGE_SHA1.upper()],
                    )
                ]
            )
            self.assertEqual(res, TEST_IMAGE)

    def test_HttpAvatarDescriptor(self):
        descriptor = avatar_service.HttpAvatarDescriptor(
            TEST_JID1,
            TEST_IMAGE_SHA1.upper(),
            mime_type="image/png",
            nbytes=len(TEST_IMAGE),
            url="http://example.com/avatar"
        )

        self.assertFalse(descriptor.has_image_data_in_pubsub)
        with self.assertRaises(NotImplementedError):
            run_coroutine(descriptor.get_image_bytes())
