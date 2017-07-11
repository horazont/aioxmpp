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
import contextlib
import copy
import logging
import random
import unittest
import unittest.mock

import aioxmpp
import aioxmpp.private_xml
import aioxmpp.xso

import aioxmpp.bookmarks

from aioxmpp.testutils import (
    make_connected_client,
    CoroutineMock,
    run_coroutine
)

TEST_JID1 = aioxmpp.JID.fromstr("foo@bar.baz")
TEST_JID2 = aioxmpp.JID.fromstr("bar@bar.baz")


class PrivateXMLSimulator:

    def __init__(self, *, delay=0):
        self.stored = {}
        self.delay = 0

    @asyncio.coroutine
    def get_private_xml(self, xso):
        payload = copy.deepcopy(
            self.stored.setdefault(xso.TAG[0], copy.deepcopy(xso))
        )
        return aioxmpp.private_xml.Query(payload)

    @asyncio.coroutine
    def set_private_xml(self, xso):
        if self.delay == 0:
            self.stored[xso.TAG[0]] = copy.deepcopy(xso)
        else:
            self.delay -= 1


@aioxmpp.private_xml.Query.as_payload_class
class ExampleXSO(aioxmpp.xso.XSO):
    TAG = ("urn:example:foo", "example")

    text = aioxmpp.xso.Text()

    def __init__(self, text=""):
        self.text = text


class TestPrivateXMLSimulator(unittest.TestCase):

    def setUp(self):
        self.cc = make_connected_client()
        self.private_xml = PrivateXMLSimulator()

    def tearDown(self):
        del self.cc
        del self.private_xml

    def test_retrieve_store_and_retrieve(self):
        before = None
        after = None

        @asyncio.coroutine
        def test_private_xml():
            nonlocal before, after
            before = (
                yield from self.private_xml.get_private_xml(ExampleXSO())
            ).registered_payload
            yield from self.private_xml.set_private_xml(ExampleXSO("foo"))
            after = (
                yield from self.private_xml.get_private_xml(ExampleXSO())
            ).registered_payload

        run_coroutine(test_private_xml())

        self.assertIsInstance(before, ExampleXSO)
        self.assertEqual(before.text, "")

        self.assertIsInstance(after, ExampleXSO)
        self.assertEqual(after.text, "foo")

    def test_store_and_retrieve(self):
        @asyncio.coroutine
        def test_private_xml():
            yield from self.private_xml.set_private_xml(ExampleXSO("foo"))
            return (
                yield from self.private_xml.get_private_xml(ExampleXSO())
            ).registered_payload

        res = run_coroutine(test_private_xml())
        self.assertIsInstance(res, ExampleXSO)
        self.assertEqual(res.text, "foo")

    def test_store_delay(self):
        results = []
        self.private_xml.delay = 3

        @asyncio.coroutine
        def test_private_xml():
            for i in range(5):
                yield from self.private_xml.set_private_xml(ExampleXSO("foo"))
                results.append((
                    yield from self.private_xml.get_private_xml(ExampleXSO())
                ).registered_payload)
        run_coroutine(test_private_xml())

        self.assertEqual(results[0].text, "")
        self.assertEqual(results[1].text, "")
        self.assertEqual(results[2].text, "")
        self.assertEqual(results[3].text, "foo")
        self.assertEqual(results[4].text, "foo")


class TestBookmarkClient(unittest.TestCase):

    def test_is_service(self):
        self.assertTrue(issubclass(
            aioxmpp.bookmarks.BookmarkClient,
            aioxmpp.service.Service
        ))

    def test_after_private_xml(self):
        self.assertIn(
            aioxmpp.private_xml.PrivateXMLService,
            aioxmpp.bookmarks.BookmarkClient.ORDER_AFTER
        )

    def test__stream_established_is_decorated(self):
        self.assertTrue(
            aioxmpp.service.is_depsignal_handler(
                aioxmpp.Client,
                "on_stream_established",
                aioxmpp.bookmarks.BookmarkClient._stream_established,
                defer=True,
            )
        )

    def test__stream_established(self):
        with unittest.mock.patch.object(
                self.s,
                "sync",
                CoroutineMock()) as sync:
            run_coroutine(self.s._stream_established())
        self.assertEqual(len(sync.mock_calls), 1)

    def setUp(self):
        self.cc = make_connected_client()
        self.private_xml = PrivateXMLSimulator()
        self.s = aioxmpp.bookmarks.BookmarkClient(self.cc, dependencies={
            aioxmpp.private_xml.PrivateXMLService: self.private_xml
        })

    def tearDown(self):
        del self.cc
        del self.private_xml
        del self.s

    def connect_mocks(self):
        self.on_added = unittest.mock.Mock()
        self.on_added.return_value = None
        self.on_removed = unittest.mock.Mock()
        self.on_removed.return_value = None
        self.on_changed = unittest.mock.Mock()
        self.on_changed.return_value = None

        self.s.on_bookmark_added.connect(self.on_added)
        self.s.on_bookmark_removed.connect(self.on_removed)
        self.s.on_bookmark_changed.connect(self.on_changed)

    def test__get_bookmarks(self):
        with unittest.mock.patch.object(
                self.private_xml,
                "get_private_xml",
                new=CoroutineMock()) as get_private_xml_mock:
            get_private_xml_mock.return_value.registered_payload.bookmarks = \
                unittest.mock.sentinel.result
            res = run_coroutine(self.s._get_bookmarks())

        self.assertIs(res, unittest.mock.sentinel.result)
        self.assertEqual(
            len(get_private_xml_mock.mock_calls),
            1
        )
        (_, (arg,), kwargs), = get_private_xml_mock.mock_calls
        self.assertEqual(len(kwargs), 0)
        self.assertIsInstance(arg, aioxmpp.bookmarks.Storage)
        self.assertEqual(len(arg.bookmarks), 0)

    def test__set_bookmarks(self):
        bookmarks = []
        bookmarks.append(
            aioxmpp.bookmarks.Conference(
                "Coven", aioxmpp.JID.fromstr("coven@example.com")),
        )
        bookmarks.append(
            aioxmpp.bookmarks.URL(
                "Interesting",
                "http://example.com/"),
        )

        with unittest.mock.patch.object(
                self.private_xml,
                "set_private_xml",
                new=CoroutineMock()) as set_private_xml_mock:
            run_coroutine(self.s._set_bookmarks(bookmarks))

        self.assertEqual(
            len(set_private_xml_mock.mock_calls),
            1
        )
        (_, (arg,), kwargs), = set_private_xml_mock.mock_calls
        self.assertEqual(len(kwargs), 0)
        self.assertEqual(arg.bookmarks, bookmarks)

    def test__set_bookmarks_failure(self):
        bookmarks = unittest.mock.sentinel.something_else
        with unittest.mock.patch.object(
                self.private_xml,
                "set_private_xml",
                new=CoroutineMock()) as set_private_xml_mock:
            with self.assertRaisesRegex(
                    TypeError,
                    "can only assign an iterable$"):
                run_coroutine(self.s._set_bookmarks(bookmarks))

        self.assertEqual(
            len(set_private_xml_mock.mock_calls),
            0
        )

    def test_sync(self):
        on_added = unittest.mock.Mock()
        on_added.return_value = None
        on_removed = unittest.mock.Mock()
        on_removed.return_value = None
        on_changed = unittest.mock.Mock()
        on_changed.return_value = None

        self.s.on_bookmark_added.connect(on_added)
        self.s.on_bookmark_removed.connect(on_removed)
        self.s.on_bookmark_changed.connect(on_changed)

        with unittest.mock.patch.object(
                self.private_xml,
                "get_private_xml",
                new=CoroutineMock()) as get_private_xml_mock:
            result = aioxmpp.private_xml.Query(
                aioxmpp.bookmarks.Storage()
            )
            result.registered_payload.bookmarks.append(
                aioxmpp.bookmarks.Conference(
                    jid=aioxmpp.JID.fromstr("foo@bar.baz"),
                    name="foo",
                    nick="quux"
                )
            )
            get_private_xml_mock.return_value = result

            run_coroutine(self.s.sync())
            run_coroutine(self.s.sync())

            result = aioxmpp.private_xml.Query(
                aioxmpp.bookmarks.Storage()
            )
            result.registered_payload.bookmarks.append(
                aioxmpp.bookmarks.Conference(
                    jid=TEST_JID1,
                    name="foo",
                    nick="quux"
                )
            )
            result.registered_payload.bookmarks.append(
                aioxmpp.bookmarks.Conference(
                    jid=TEST_JID1,
                    name="foo",
                    nick="quuux"
                )
            )
            get_private_xml_mock.return_value = result

            run_coroutine(self.s.sync())
            run_coroutine(self.s.sync())

            result = aioxmpp.private_xml.Query(
                aioxmpp.bookmarks.Storage()
            )
            result.registered_payload.bookmarks.append(
                aioxmpp.bookmarks.Conference(
                    jid=TEST_JID1,
                    name="foo",
                    nick="quux"
                )
            )
            get_private_xml_mock.return_value = result

            run_coroutine(self.s.sync())
            run_coroutine(self.s.sync())

            result = aioxmpp.private_xml.Query(
                aioxmpp.bookmarks.Storage()
            )
            result.registered_payload.bookmarks.append(
                aioxmpp.bookmarks.Conference(
                    jid=aioxmpp.JID.fromstr("foo@bar.baz"),
                    name="foo",
                    nick="quuux"
                )
            )
            get_private_xml_mock.return_value = result

            run_coroutine(self.s.sync())
            run_coroutine(self.s.sync())

        self.assertEqual(
            len(on_added.mock_calls), 2
        )

        self.assertEqual(
            len(on_removed.mock_calls), 1
        )

        self.assertEqual(
            len(on_changed.mock_calls), 1
        )

    def test_set_bookmarks(self):
        bookmarks = [
            aioxmpp.bookmarks.URL("An URL", "http://foo.bar/"),
            aioxmpp.bookmarks.Conference(
                "Coven",
                aioxmpp.JID.fromstr("coven@conference.shakespeare.lit"),
                nick="Wayward Sister"
            )
        ]

        self.connect_mocks()
        run_coroutine(self.s.set_bookmarks(bookmarks))
        self.assertEqual(len(self.on_changed.mock_calls), 0)
        self.assertEqual(len(self.on_removed.mock_calls), 0)
        self.assertEqual(len(self.on_added.mock_calls), 2)

    def test_add_bookmark(self):
        self.connect_mocks()
        bookmark = aioxmpp.bookmarks.URL("An URL", "http://foo.bar/")
        run_coroutine(self.s.add_bookmark(bookmark))

        self.assertEqual(len(self.on_changed.mock_calls), 0)
        self.assertEqual(len(self.on_removed.mock_calls), 0)
        self.on_added.assert_called_once_with(bookmark)

    def test_add_bookmark_delay(self):
        self.private_xml.delay = 3
        self.connect_mocks()
        bookmark = aioxmpp.bookmarks.URL("An URL", "http://foo.bar/")
        run_coroutine(self.s.add_bookmark(bookmark))

        self.assertEqual(len(self.on_changed.mock_calls), 0)
        self.assertEqual(len(self.on_removed.mock_calls), 0)
        self.on_added.assert_called_once_with(bookmark)

    def test_add_bookmark_delay_raises(self):
        self.private_xml.delay = 4
        with self.assertRaises(RuntimeError):
            with unittest.mock.patch.object(self.s, "_diff_emit_update") as f:
                bookmark = aioxmpp.bookmarks.URL("An URL", "http://foo.bar/")
                run_coroutine(self.s.add_bookmark(bookmark))

        # check that _diff_emit_update is called
        self.assertEqual(len(f.mock_calls), 1)

    def test_add_bookmark_set_raises(self):
        class TokenException(Exception):
            pass

        def set_bookmarks(*args, **kwargs):
            raise TokenException

        with contextlib.ExitStack() as e:
            e.enter_context(self.assertRaises(TokenException))
            diff_emit_update = e.enter_context(
                unittest.mock.patch.object(self.s, "_diff_emit_update",)
            )
            e.enter_context(
                unittest.mock.patch.object(self.s, "_set_bookmarks",
                                           set_bookmarks)
            )
            bookmark = aioxmpp.bookmarks.URL("An URL", "http://foo.bar/")
            run_coroutine(self.s.add_bookmark(bookmark))

        # check that _diff_emit_update is called
        self.assertEqual(len(diff_emit_update.mock_calls), 1)

    def test_add_bookmark_already_present(self):
        bookmark = aioxmpp.bookmarks.URL("An URL", "http://foo.bar/")
        run_coroutine(self.s.add_bookmark(bookmark))
        stored = run_coroutine(
            self.private_xml.get_private_xml(aioxmpp.bookmarks.Storage())
        )
        self.assertCountEqual(self.s._bookmark_cache,
                              [bookmark])
        self.assertCountEqual(stored.registered_payload.bookmarks,
                              [bookmark])
        self.connect_mocks()
        run_coroutine(self.s.add_bookmark(bookmark))
        self.assertEqual(len(self.on_changed.mock_calls), 0)
        self.assertEqual(len(self.on_removed.mock_calls), 0)
        self.assertEqual(len(self.on_added.mock_calls), 0)

    def test_discard_bookmark(self):
        bookmark = aioxmpp.bookmarks.URL("An URL", "http://foo.bar/")
        run_coroutine(self.s.add_bookmark(bookmark))
        self.connect_mocks()
        run_coroutine(self.s.discard_bookmark(bookmark))
        self.assertEqual(len(self.on_changed.mock_calls), 0)
        self.assertEqual(len(self.on_added.mock_calls), 0)
        self.on_removed.assert_called_once_with(bookmark)

    def test_discard_bookmark_delay(self):
        bookmark = aioxmpp.bookmarks.URL("An URL", "http://foo.bar/")
        run_coroutine(self.s.add_bookmark(bookmark))
        self.private_xml.delay = 3
        self.connect_mocks()
        run_coroutine(self.s.discard_bookmark(bookmark))
        self.assertEqual(len(self.on_changed.mock_calls), 0)
        self.assertEqual(len(self.on_added.mock_calls), 0)
        self.on_removed.assert_called_once_with(bookmark)

    def test_discard_bookmark_delay_raises(self):
        bookmark = aioxmpp.bookmarks.URL("An URL", "http://foo.bar/")
        run_coroutine(self.s.add_bookmark(bookmark))
        self.private_xml.delay = 4
        with contextlib.ExitStack() as e:
            e.enter_context(self.assertRaises(RuntimeError))
            f = e.enter_context(
                unittest.mock.patch.object(self.s, "_diff_emit_update")
            )
            run_coroutine(self.s.discard_bookmark(bookmark))
        # check that _diff_emit_update is called
        self.assertEqual(len(f.mock_calls), 1)

    def test_discard_bookmark_set_raises(self):
        bookmark = aioxmpp.bookmarks.URL("An URL", "http://foo.bar/")
        run_coroutine(self.s.add_bookmark(bookmark))

        class TokenException(Exception):
            pass

        def set_bookmarks(*args, **kwargs):
            raise TokenException

        with contextlib.ExitStack() as e:
            e.enter_context(self.assertRaises(TokenException))
            diff_emit_update = e.enter_context(
                unittest.mock.patch.object(self.s, "_diff_emit_update",)
            )
            e.enter_context(
                unittest.mock.patch.object(self.s, "_set_bookmarks",
                                           set_bookmarks)
            )
            run_coroutine(self.s.discard_bookmark(bookmark))

        # check that _diff_emit_update is called
        self.assertEqual(len(diff_emit_update.mock_calls), 1)

    def test_discard_bookmark_removes_one(self):
        bookmark = aioxmpp.bookmarks.URL("An URL", "http://foo.bar/")
        run_coroutine(self.s.set_bookmarks([bookmark, bookmark]))
        self.connect_mocks()
        run_coroutine(self.s.discard_bookmark(bookmark))
        self.assertEqual(len(self.on_changed.mock_calls), 0)
        self.assertEqual(len(self.on_added.mock_calls), 0)
        self.on_removed.assert_called_once_with(bookmark)
        self.assertCountEqual(self.s._bookmark_cache, [bookmark])

    def test_discard_bookmark_already_gone(self):
        bookmark = aioxmpp.bookmarks.URL("An URL", "http://foo.bar/")
        self.connect_mocks()
        run_coroutine(self.s.discard_bookmark(bookmark))
        self.assertEqual(len(self.on_changed.mock_calls), 0)
        self.assertEqual(len(self.on_removed.mock_calls), 0)
        self.assertEqual(len(self.on_added.mock_calls), 0)

    def test_update_bookmark(self):
        bookmark = aioxmpp.bookmarks.URL("An URL", "http://foo.bar/")
        run_coroutine(self.s.add_bookmark(bookmark))

        self.connect_mocks()
        new_bookmark = copy.copy(bookmark)
        new_bookmark.name = "THE URL"
        run_coroutine(self.s.update_bookmark(bookmark, new_bookmark))
        self.assertEqual(len(self.on_removed.mock_calls), 0)
        self.assertEqual(len(self.on_added.mock_calls), 0)
        self.on_changed.assert_called_once_with(bookmark, new_bookmark)

    def test_update_bookmark_delay(self):
        bookmark = aioxmpp.bookmarks.URL("An URL", "http://foo.bar/")
        run_coroutine(self.s.add_bookmark(bookmark))
        self.private_xml.delay = 3
        self.connect_mocks()
        new_bookmark = copy.copy(bookmark)
        new_bookmark.name = "THE URL"
        run_coroutine(self.s.update_bookmark(bookmark, new_bookmark))
        self.assertEqual(len(self.on_removed.mock_calls), 0)
        self.assertEqual(len(self.on_added.mock_calls), 0)
        self.on_changed.assert_called_once_with(bookmark, new_bookmark)

    def test_update_bookmark_delay_raises(self):
        bookmark = aioxmpp.bookmarks.URL("An URL", "http://foo.bar/")
        new_bookmark = copy.copy(bookmark)
        new_bookmark.name = "THE URL"
        run_coroutine(self.s.add_bookmark(bookmark))

        self.private_xml.delay = 4
        with contextlib.ExitStack() as e:
            e.enter_context(self.assertRaises(RuntimeError))
            f = e.enter_context(
                unittest.mock.patch.object(self.s, "_diff_emit_update")
            )
            run_coroutine(self.s.update_bookmark(bookmark, new_bookmark))
        # check that _diff_emit_update is called
        self.assertEqual(len(f.mock_calls), 1)

    def test_update_bookmark_set_raises(self):
        bookmark = aioxmpp.bookmarks.URL("An URL", "http://foo.bar/")
        new_bookmark = copy.copy(bookmark)
        new_bookmark.name = "THE URL"
        run_coroutine(self.s.add_bookmark(bookmark))

        class TokenException(Exception):
            pass

        def set_bookmarks(*args, **kwargs):
            raise TokenException

        with contextlib.ExitStack() as e:
            e.enter_context(self.assertRaises(TokenException))
            diff_emit_update = e.enter_context(
                unittest.mock.patch.object(self.s, "_diff_emit_update",)
            )
            e.enter_context(
                unittest.mock.patch.object(self.s, "_set_bookmarks",
                                           set_bookmarks)
            )
            run_coroutine(self.s.update_bookmark(bookmark, new_bookmark))

        # check that _diff_emit_update is called
        self.assertEqual(len(diff_emit_update.mock_calls), 1)

    def test_concurrent_update_bookmark(self):
        bookmark = aioxmpp.bookmarks.URL("An URL", "http://foo.bar/")
        run_coroutine(self.s.add_bookmark(bookmark))

        self.private_xml.stored["storage:bookmarks"].bookmarks.clear()

        self.connect_mocks()
        new_bookmark = copy.copy(bookmark)
        new_bookmark.name = "THE URL"
        run_coroutine(self.s.update_bookmark(bookmark, new_bookmark))
        self.assertEqual(len(self.on_removed.mock_calls), 0)
        self.assertEqual(len(self.on_added.mock_calls), 0)
        self.on_changed.assert_called_once_with(bookmark, new_bookmark)

    def test_on_change_from_two_branches(self):
        pass

    def test_fuzz_bookmark_changes(self):
        bookmark_list = []

        logging.info(
            "This is a fuzzing test it may fail or not fail randomly"
            " depending on the chosen seed."
            "If it fails, please report a bug which includes "
            "the random generator state given in the next log message"
        )
        logging.info("The random seed is %s", random.getstate())

        def on_added(added):
            bookmark_list.append(added)

        def on_removed(removed):
            bookmark_list.remove(removed)

        def on_changed(old, new):
            bookmark_list.remove(old)
            bookmark_list.append(new)

        self.s.on_bookmark_added.connect(on_added)
        self.s.on_bookmark_removed.connect(on_removed)
        self.s.on_bookmark_changed.connect(on_changed)

        def random_nick():
            return "foo{}".format(random.randint(0, 5))

        def random_name():
            return "name{}".format(random.randint(0, 5))

        def random_pw():
            return "name{}".format(random.randint(0, 5))

        jids = [aioxmpp.JID.fromstr("foo{}@bar.baz".format(i))
                for i in range(5)]

        def random_jid():
            return random.choice(jids)

        def random_url():
            return "http://foo{}.bar/".format(random.randint(0, 5))

        for i in range(100):
            operation = random.randint(0, 100)
            if operation < 20:
                if random.randint(0, 1):
                    bookmark = aioxmpp.bookmarks.Conference(
                        random_name(),
                        random_jid(),
                        nick=random_nick(),
                        password=random_pw(),
                        autojoin=bool(random.randint(0, 1)),
                    )
                else:
                    bookmark = aioxmpp.bookmarks.URL(
                        random_name(),
                        random_url(),
                    )

                run_coroutine(self.s.add_bookmark(bookmark))
            elif operation < 30:
                if not bookmark_list:
                    continue

                run_coroutine(self.s.discard_bookmark(
                    bookmark_list[random.randrange(len(bookmark_list))]
                ))
            else:
                if not bookmark_list:
                    continue

                to_change = bookmark_list[random.randrange(len(bookmark_list))]
                changed = copy.copy(to_change)

                if type(to_change) is aioxmpp.bookmarks.Conference:
                    if random.randint(0, 4) == 0:
                        changed.name = random_name()
                    if random.randint(0, 4) == 0:
                        changed.jid = random_jid()
                    if random.randint(0, 4) == 0:
                        changed.nick = random_nick()
                    if random.randint(0, 4) == 0:
                        changed.password = random_pw()
                    if random.randint(0, 4) == 0:
                        changed.autojoin = bool(random.randint(0, 1))
                else:
                    if random.randint(0, 2) == 0:
                        changed.name = random_name()
                    if random.randint(0, 2) == 0:
                        changed.url = random_url()
                run_coroutine(self.s.update_bookmark(to_change, changed))

            self.assertCountEqual(bookmark_list, self.s._bookmark_cache)
