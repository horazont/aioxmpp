import asyncio
import contextlib
import copy
import unittest
import unittest.mock

import aioxmpp.disco as disco
import aioxmpp.service as service
import aioxmpp.stanza as stanza
import aioxmpp.structs as structs
import aioxmpp.forms as forms
import aioxmpp.forms.xso as forms_xso

import aioxmpp.entitycaps.service as entitycaps_service
import aioxmpp.entitycaps.xso as entitycaps_xso

from aioxmpp.testutils import (
    make_connected_client,
    CoroutineMock,
    run_coroutine,
)


TEST_FROM = structs.JID.fromstr("foo@bar.example/r1")


class Testbuild_identities_string(unittest.TestCase):
    def test_identities(self):
        identities = [
            {
                "category": "fnord",
                "type": "bar",
            },
            {
                "category": "client",
                "type": "bot",
                "name": "aioxmpp library",
            },
            {
                "category": "client",
                "type": "bot",
                "lang": "de-de",
                "name": "aioxmpp Bibliothek",
            }
        ]

        self.assertEqual(
            b"client/bot//aioxmpp library<"
            b"client/bot/de-de/aioxmpp Bibliothek<"
            b"fnord/bar//<",
            entitycaps_service.build_identities_string(identities)
        )

    def test_escaping(self):
        identities = [
            {
                "category": "fnord",
                "type": "bar",
            },
            {
                "category": "client",
                "type": "bot",
                "name": "aioxmpp library > 0.5",
            },
            {
                "category": "client",
                "type": "bot",
                "lang": "de-de",
                "name": "aioxmpp Bibliothek <& 0.5",
            }
        ]

        self.assertEqual(
            b"client/bot//aioxmpp library &gt; 0.5<"
            b"client/bot/de-de/aioxmpp Bibliothek &lt;&amp; 0.5<"
            b"fnord/bar//<",
            entitycaps_service.build_identities_string(identities)
        )

    def test_reject_duplicate_identities(self):
        identities = [
            {
                "category": "fnord",
                "type": "bar",
            },
            {
                "category": "client",
                "type": "bot",
                "name": "aioxmpp library > 0.5",
            },
            {
                "category": "client",
                "type": "bot",
                "lang": "de-de",
                "name": "aioxmpp Bibliothek <& 0.5",
            },
            {
                "category": "client",
                "type": "bot",
                "name": "aioxmpp library > 0.5",
            },
        ]

        with self.assertRaisesRegexp(ValueError,
                                     "duplicate identity"):
            entitycaps_service.build_identities_string(identities)


class Testbuild_features_string(unittest.TestCase):
    def test_features(self):
        features = [
            "http://jabber.org/protocol/disco#info",
            "http://jabber.org/protocol/caps",
            "http://jabber.org/protocol/disco#items",
        ]

        self.assertEqual(
            b"http://jabber.org/protocol/caps<"
            b"http://jabber.org/protocol/disco#info<"
            b"http://jabber.org/protocol/disco#items<",
            entitycaps_service.build_features_string(features)
        )

    def test_escaping(self):
        features = [
            "http://jabber.org/protocol/c<>&aps",
        ]

        self.assertEqual(
            b"http://jabber.org/protocol/c&lt;&gt;&amp;aps<",
            entitycaps_service.build_features_string(features)
        )

    def test_reject_duplicate_features(self):
        features = [
            "http://jabber.org/protocol/disco#info",
            "http://jabber.org/protocol/caps",
            "http://jabber.org/protocol/disco#items",
            "http://jabber.org/protocol/caps",
        ]

        with self.assertRaisesRegexp(ValueError,
                                     "duplicate feature"):
            entitycaps_service.build_features_string(features)


class Testbuild_forms_string(unittest.TestCase):
    def test_xep_form(self):
        data = [
            {
                "FORM_TYPE": [
                    "urn:xmpp:dataforms:softwareinfo",
                ],
                "os_version": [
                    "10.5.1",
                ],
                "os": [
                    "Mac",
                ],
                "ip_version": [
                    "ipv6",
                    "ipv4",
                ],
                "software": [
                    "Psi",
                ],
                "software_version": [
                    "0.11",
                ]
            }
        ]

        self.assertEqual(
            b"urn:xmpp:dataforms:softwareinfo<"
            b"ip_version<ipv4<ipv6<"
            b"os<Mac<"
            b"os_version<10.5.1<"
            b"software<Psi<"
            b"software_version<0.11<",
            entitycaps_service.build_forms_string(data)
        )

    def test_value_and_var_escaping(self):
        data = [
            {
                "FORM_TYPE": [
                    "urn:xmpp:<dataforms:softwareinfo",
                ],
                "os_version": [
                    "10.&5.1",
                ],
                "os>": [
                    "Mac"
                ]
            }
        ]

        self.assertEqual(
            b"urn:xmpp:&lt;dataforms:softwareinfo<"
            b"os&gt;<Mac<"
            b"os_version<10.&amp;5.1<",
            entitycaps_service.build_forms_string(data)
        )

    def test_reject_multiple_identical_form_types(self):
        data = [
            {
                "FORM_TYPE": [
                    "urn:xmpp:dataforms:softwareinfo",
                ],
                "os_version": [
                    "10.5.1",
                ],
                "os": [
                    "Mac"
                ]
            },
            {
                "FORM_TYPE": [
                    "urn:xmpp:dataforms:softwareinfo",
                ],
                "os_version": [
                    "10.5.1",
                ],
                "os": [
                    "Mac"
                ]
            }
        ]

        with self.assertRaisesRegex(
                ValueError,
                "multiple forms of type b'urn:xmpp:dataforms:softwareinfo'"):
            entitycaps_service.build_forms_string(data)

    def test_reject_form_with_multiple_different_types(self):
        data = [
            {
                "FORM_TYPE": [
                    "urn:xmpp:dataforms:softwareinfo",
                    "urn:xmpp:dataforms:softwarefoo",
                ],
                "os_version": [
                    "10.5.1",
                ],
                "os": [
                    "Mac"
                ]
            },
        ]

        with self.assertRaisesRegex(
                ValueError,
                "form with multiple types"):
            entitycaps_service.build_forms_string(data)

    def test_ignore_form_without_type(self):
        data = [
            {
                "FORM_TYPE": [
                ],
                "foo": [
                    "bar",
                ],
            },
            {
                "FORM_TYPE": [
                    "urn:xmpp:dataforms:softwareinfo",
                ],
                "os_version": [
                    "10.5.1",
                ],
                "os": [
                    "Mac"
                ]
            }
        ]

        self.assertEqual(
            b"urn:xmpp:dataforms:softwareinfo<"
            b"os<Mac<"
            b"os_version<10.5.1<",
            entitycaps_service.build_forms_string(data)
        )

        data = [
            {
                "FORM_TYPE": [
                ],
                "foo": [
                    "bar",
                ],
            },
            {
                "FORM_TYPE": [
                    "urn:xmpp:dataforms:softwareinfo",
                ],
                "os_version": [
                    "10.5.1",
                ],
                "os": [
                    "Mac"
                ]
            }
        ]

        self.assertEqual(
            b"urn:xmpp:dataforms:softwareinfo<"
            b"os<Mac<"
            b"os_version<10.5.1<",
            entitycaps_service.build_forms_string(data)
        )

    def test_accept_form_with_multiple_identical_types(self):
        data = [
            {
                "FORM_TYPE": [
                    "urn:xmpp:dataforms:softwareinfo",
                    "urn:xmpp:dataforms:softwareinfo",
                ],
                "os_version": [
                    "10.5.1",
                ],
                "os": [
                    "Mac"
                ]
            },
        ]

        entitycaps_service.build_forms_string(data)

    def test_multiple(self):
        data = [
            {
                "FORM_TYPE": [
                    "uri:foo",
                ]
            },
            {
                "FORM_TYPE": [
                    "uri:bar",
                ]
            },
        ]

        self.assertEqual(
            b"uri:bar<uri:foo<",
            entitycaps_service.build_forms_string(data)
        )


class Testhash_query(unittest.TestCase):
    def test_impl(self):
        self.maxDiff = None
        base = unittest.mock.Mock()

        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch(
                "aioxmpp.entitycaps.service.build_identities_string",
                new=base.build_identities_string,
            ))

            stack.enter_context(unittest.mock.patch(
                "aioxmpp.entitycaps.service.build_features_string",
                new=base.build_features_string,
            ))

            stack.enter_context(unittest.mock.patch(
                "aioxmpp.entitycaps.service.build_forms_string",
                new=base.build_forms_string,
            ))

            stack.enter_context(unittest.mock.patch(
                "hashlib.new",
                new=base.hashlib_new,
            ))

            stack.enter_context(unittest.mock.patch(
                "base64.b64encode",
                new=base.base64_b64encode,
            ))

            result = entitycaps_service.hash_query(
                base.query,
                base.algo
            )

        calls = list(base.mock_calls)
        self.assertSequenceEqual(
            calls,
            [
                unittest.mock.call.hashlib_new(base.algo),
                unittest.mock.call.query.get("identities", []),
                unittest.mock.call.build_identities_string(
                    base.query.get(),
                ),
                unittest.mock.call.hashlib_new().update(
                    base.build_identities_string()
                ),
                unittest.mock.call.query.get("features", []),
                unittest.mock.call.build_features_string(
                    base.query.get(),
                ),
                unittest.mock.call.hashlib_new().update(
                    base.build_features_string()
                ),
                unittest.mock.call.query.get("forms", {}),
                unittest.mock.call.build_forms_string(
                    base.query.get(),
                ),
                unittest.mock.call.hashlib_new().update(
                    base.build_forms_string()
                ),
                unittest.mock.call.hashlib_new().digest(),
                unittest.mock.call.base64_b64encode(
                    base.hashlib_new().digest()
                ),
                unittest.mock.call.base64_b64encode().decode("ascii")
            ]
        )

        self.assertEqual(
            result,
            base.base64_b64encode().decode()
        )

    def test_simple_xep_data(self):
        info = {
            "identities": [
                {
                    "category": "client",
                    "name": "Exodus 0.9.1",
                    "type": "pc",
                },
            ],
            "features": [
                "http://jabber.org/protocol/caps",
                "http://jabber.org/protocol/disco#info",
                "http://jabber.org/protocol/disco#items",
                "http://jabber.org/protocol/muc",
            ],
            "forms": {},
        }

        self.assertEqual(
            "QgayPKawpkPSDYmwT/WM94uAlu0=",
            entitycaps_service.hash_query(info, "sha1")
        )

    def test_complex_xep_data(self):
        info ={
            "identities": [
                {
                    "category": "client",
                    "name": "Psi 0.11",
                    "type": "pc",
                    "lang": "en",
                },
                {
                    "category": "client",
                    "name": "Ψ 0.11",
                    "type": "pc",
                    "lang": "el",
                },
            ],
            "features": [
                "http://jabber.org/protocol/caps",
                "http://jabber.org/protocol/disco#info",
                "http://jabber.org/protocol/disco#items",
                "http://jabber.org/protocol/muc",
            ],
            "forms": [
                {
                    "FORM_TYPE": [
                        "urn:xmpp:dataforms:softwareinfo"
                    ],
                    "ip_version": [
                        "ipv4",
                        "ipv6",
                    ],
                    "os": [
                        "Mac",
                    ],
                    "os_version": [
                        "10.5.1",
                    ],
                    "software": [
                        "Psi",
                    ],
                    "software_version": [
                        "0.11",
                    ]
                }
            ]
        }

        self.assertEqual(
            "q07IKJEyjvHSyhy//CH0CxmKi8w=",
            entitycaps_service.hash_query(info, "sha1")
        )


TEST_INFO = {
    "identities": [
        {
            "category": "client",
            "name": "Psi 0.11",
            "type": "pc",
            "lang": "en",
        },
        {
            "category": "client",
            "name": "Ψ 0.11",
            "type": "pc",
            "lang": "el",
        },
    ],
    "features": [
        "http://jabber.org/protocol/caps",
        "http://jabber.org/protocol/disco#info",
        "http://jabber.org/protocol/disco#items",
        "http://jabber.org/protocol/muc",
    ],
    "forms": {
        "urn:xmpp:dataforms:softwareinfo": {
            "ip_version": [
                "ipv4",
                "ipv6",
            ],
            "os": [
                "Mac",
            ],
            "os_version": [
                "10.5.1",
            ],
            "software": [
                "Psi",
            ],
            "software_version": [
                "0.11",
            ]
        }
    }
}

TEST_INFO_HASH = "sha-1"

_tmp = dict(TEST_INFO)
_tmp["forms"] = [
    dict(value,
         FORM_TYPE=[key])
    for key, value in _tmp["forms"].items()
]

TEST_INFO_VER = entitycaps_service.hash_query(_tmp, "sha1")
del _tmp

TEST_DB = {
    "+0mnUAF1ozCEc37cmdPPsYbsfhg=": {
        "features": [
            "games:board",
            "http://jabber.org/protocol/activity",
            "http://jabber.org/protocol/activity+notify",
            "http://jabber.org/protocol/bytestreams",
            "http://jabber.org/protocol/chatstates",
            "http://jabber.org/protocol/commands",
            "http://jabber.org/protocol/disco#info",
            "http://jabber.org/protocol/disco#items",
            "http://jabber.org/protocol/geoloc",
            "http://jabber.org/protocol/geoloc+notify",
            "http://jabber.org/protocol/ibb",
            "http://jabber.org/protocol/iqibb",
            "http://jabber.org/protocol/mood",
            "http://jabber.org/protocol/mood+notify",
            "http://jabber.org/protocol/rosterx",
            "http://jabber.org/protocol/si",
            "http://jabber.org/protocol/si/profile/file-transfer",
            "http://jabber.org/protocol/tune",
            "jabber:iq:avatar",
            "jabber:iq:browse",
            "jabber:iq:last",
            "jabber:iq:oob",
            "jabber:iq:privacy",
            "jabber:iq:roster",
            "jabber:iq:time",
            "jabber:iq:version",
            "jabber:x:data",
            "jabber:x:event",
            "jabber:x:oob",
            "urn:xmpp:ping",
            "urn:xmpp:time"
        ],
        "forms": {
            "urn:xmpp:dataforms:softwareinfo": {
                "os": [
                    "FreeBSD"
                ],
                "os_version": [
                    "10.0-STABLE"
                ],
                "software": [
                    "Tkabber"
                ],
                "software_version": [
                    "1.0-svn-20140122 (Tcl/Tk 8.4.20)"
                ]
            }
        },
        "hash": "sha-1",
        "identities": [
            {
                "category": "client",
                "name": "Tkabber",
                "type": "pc"
            }
        ],
        "node": "http://tkabber.jabber.ru/"
    },
    "+9oi6+VEwgu5cRmjErECReGvCC0=": {
        "features": [
            "http://jabber.org/protocol/bytestreams",
            "http://jabber.org/protocol/caps",
            "http://jabber.org/protocol/chatstates",
            "http://jabber.org/protocol/disco#info",
            "http://jabber.org/protocol/disco#items",
            "http://jabber.org/protocol/ibb",
            "http://jabber.org/protocol/mood",
            "http://jabber.org/protocol/mood+notify",
            "http://jabber.org/protocol/muc",
            "http://jabber.org/protocol/muc#user",
            "http://jabber.org/protocol/nick",
            "http://jabber.org/protocol/nick+notify",
            "http://jabber.org/protocol/si",
            "http://jabber.org/protocol/si/profile/file-transfer",
            "http://jabber.org/protocol/tune",
            "http://jabber.org/protocol/tune+notify",
            "http://jabber.org/protocol/xhtml-im",
            "jabber:iq:last",
            "jabber:iq:oob",
            "jabber:iq:version",
            "jabber:x:conference",
            "urn:xmpp:attention:0",
            "urn:xmpp:avatar:data",
            "urn:xmpp:avatar:metadata",
            "urn:xmpp:avatar:metadata+notify",
            "urn:xmpp:bob",
            "urn:xmpp:jingle:1",
            "urn:xmpp:jingle:apps:rtp:1",
            "urn:xmpp:jingle:transports:ice-udp:1",
            "urn:xmpp:jingle:transports:raw-udp:1",
            "urn:xmpp:ping",
            "urn:xmpp:time"
        ],
        "forms": {},
        "hash": "sha-1",
        "identities": [
            {
                "category": "client",
                "name": "minbif",
                "type": "pc"
            }
        ],
        "node": "http://pidgin.im/"
    },
}


def wrap_forms(d):
    d["forms"] = [
        dict(value,
             FORM_TYPE=[key])
        for key, value in d["forms"].items()
    ]


class TestCache(unittest.TestCase):
    def setUp(self):
        self.c = entitycaps_service.Cache()

    def test_load_trusted_from_json_yields_lookup(self):
        self.c.load_trusted_from_json(TEST_DB)

        expected = dict(TEST_DB["+9oi6+VEwgu5cRmjErECReGvCC0="])
        del expected["node"]
        del expected["hash"]
        wrap_forms(expected)

        self.assertDictEqual(
            self.c.lookup_in_database("+9oi6+VEwgu5cRmjErECReGvCC0="),
            expected
        )

    def test_load_trusted_from_json_copies(self):
        data = dict(TEST_DB)

        self.c.load_trusted_from_json(data)

        del data["+9oi6+VEwgu5cRmjErECReGvCC0="]

        expected = dict(TEST_DB["+9oi6+VEwgu5cRmjErECReGvCC0="])
        del expected["node"]
        del expected["hash"]
        wrap_forms(expected)

        self.assertDictEqual(
            self.c.lookup_in_database("+9oi6+VEwgu5cRmjErECReGvCC0="),
            expected
        )

    def test_load_trusted_from_json_deepcopies(self):
        data = copy.deepcopy(TEST_DB)

        self.c.load_trusted_from_json(data)

        del data["+9oi6+VEwgu5cRmjErECReGvCC0="]["features"]

        expected = dict(TEST_DB["+9oi6+VEwgu5cRmjErECReGvCC0="])
        del expected["node"]
        del expected["hash"]
        wrap_forms(expected)

        self.assertDictEqual(
            self.c.lookup_in_database("+9oi6+VEwgu5cRmjErECReGvCC0="),
            expected
        )

    def test_load_user_from_json_yields_lookup(self):
        self.c.load_user_from_json(TEST_DB)

        expected = dict(TEST_DB["+9oi6+VEwgu5cRmjErECReGvCC0="])
        del expected["node"]
        del expected["hash"]
        wrap_forms(expected)

        self.assertDictEqual(
            self.c.lookup_in_database("+9oi6+VEwgu5cRmjErECReGvCC0="),
            expected
        )

    def test_load_user_from_json_deepcopies(self):
        data = copy.deepcopy(TEST_DB)

        self.c.load_user_from_json(data)

        del data["+9oi6+VEwgu5cRmjErECReGvCC0="]["features"]

        expected = dict(TEST_DB["+9oi6+VEwgu5cRmjErECReGvCC0="])
        del expected["node"]
        del expected["hash"]
        wrap_forms(expected)

        self.assertDictEqual(
            self.c.lookup_in_database("+9oi6+VEwgu5cRmjErECReGvCC0="),
            expected
        )

    def test_trusted_wins_over_user(self):
        userdb = copy.deepcopy(TEST_DB)
        userdb["+9oi6+VEwgu5cRmjErECReGvCC0="]["features"] = []

        trusteddb = dict(TEST_DB)

        self.c.load_trusted_from_json(trusteddb)
        self.c.load_user_from_json(userdb)

        expected = dict(TEST_DB["+9oi6+VEwgu5cRmjErECReGvCC0="])
        del expected["node"]
        del expected["hash"]
        wrap_forms(expected)

        self.assertDictEqual(
            self.c.lookup_in_database("+9oi6+VEwgu5cRmjErECReGvCC0="),
            expected
        )

    def test_lookup_in_database_deepcopies(self):
        data = copy.deepcopy(TEST_DB)

        self.c.load_user_from_json(data)

        expected = dict(TEST_DB["+9oi6+VEwgu5cRmjErECReGvCC0="])
        del expected["node"]
        del expected["hash"]
        wrap_forms(expected)

        result = self.c.lookup_in_database("+9oi6+VEwgu5cRmjErECReGvCC0=")
        self.assertDictEqual(
            result,
            expected
        )

        result["features"].pop()

        self.assertDictEqual(
            self.c.lookup_in_database("+9oi6+VEwgu5cRmjErECReGvCC0="),
            expected
        )

    def test_userdb_is_empty_by_default(self):
        self.assertDictEqual({}, self.c.save_user_to_json())

    def test_load_user_from_json_fills_savev(self):
        self.c.load_user_from_json(TEST_DB)

        expected = dict(TEST_DB["+9oi6+VEwgu5cRmjErECReGvCC0="])
        del expected["node"]
        del expected["hash"]
        wrap_forms(expected)

        self.assertDictEqual(
            self.c.lookup_in_database("+9oi6+VEwgu5cRmjErECReGvCC0="),
            expected
        )

    def test_load_user_from_json_populates_userdb(self):
        self.c.load_user_from_json(TEST_DB)
        self.assertDictEqual(TEST_DB, self.c.save_user_to_json())

    def test_save_user_to_json_deepcopies(self):
        self.c.load_user_from_json(TEST_DB)

        result1 = self.c.save_user_to_json()
        result1["+9oi6+VEwgu5cRmjErECReGvCC0="]["features"].pop()

        self.assertDictEqual(TEST_DB, self.c.save_user_to_json())

    def test_save_user_to_json_does_not_emit_entries_which_are_in_trusted(
            self):
        self.c.load_user_from_json(TEST_DB)

        trusted = dict(TEST_DB)
        del trusted["+9oi6+VEwgu5cRmjErECReGvCC0="]
        self.c.load_trusted_from_json(trusted)

        expected = dict(TEST_DB)
        del expected["+0mnUAF1ozCEc37cmdPPsYbsfhg="]

        self.assertDictEqual(expected, self.c.save_user_to_json())

    def test_lookup_in_database_key_errors_if_no_such_entry(self):
        with self.assertRaises(KeyError):
            self.c.lookup_in_database("+9oi6+VEwgu5cRmjErECReGvCC0=")

    def test_lookup_uses_lookup_in_database(self):
        hash_ = object()
        with unittest.mock.patch.object(
                self.c,
                "lookup_in_database") as lookup_in_database:
            result = run_coroutine(self.c.lookup(hash_))

        lookup_in_database.assert_called_with(hash_)
        self.assertEqual(result, lookup_in_database())

    def test_create_query_future_used_by_lookup(self):
        fut = asyncio.Future()

        base = unittest.mock.Mock()
        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch(
                "asyncio.Future",
                new=base.Future
            ))

            stack.enter_context(unittest.mock.patch.object(
                self.c,
                "lookup_in_database",
                new=base.lookup_in_database
            ))

            base.lookup_in_database.side_effect = KeyError()
            base.Future.return_value = fut

            self.assertIs(
                self.c.create_query_future(base.hash_),
                fut,
            )

            task = asyncio.async(
                self.c.lookup(base.hash_)
            )
            run_coroutine(asyncio.sleep(0))

            self.assertFalse(task.done())

            fut.set_result(base.result)

            run_coroutine(asyncio.sleep(0))

            self.assertIs(task.result(), base.result)

    def test_lookup_key_errors_if_no_matching_entry_or_future(self):
        fut = asyncio.Future()

        base = unittest.mock.Mock()
        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch(
                "asyncio.Future",
                new=base.Future
            ))

            stack.enter_context(unittest.mock.patch.object(
                self.c,
                "lookup_in_database",
                new=base.lookup_in_database
            ))

            base.lookup_in_database.side_effect = KeyError()
            base.Future.return_value = fut

            self.assertIs(
                self.c.create_query_future(base.hash_),
                fut,
            )

            with self.assertRaises(KeyError):
                run_coroutine(self.c.lookup(base.other_hash))

    def test_lookup_loops_on_query_futures(self):
        fut1 = asyncio.Future()
        fut2 = asyncio.Future()
        fut3 = asyncio.Future()

        base = unittest.mock.Mock()
        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch(
                "asyncio.Future",
                new=base.Future
            ))

            stack.enter_context(unittest.mock.patch.object(
                self.c,
                "lookup_in_database",
                new=base.lookup_in_database
            ))

            base.lookup_in_database.side_effect = KeyError()
            base.Future.return_value = fut1
            self.c.create_query_future(base.hash_)

            task = asyncio.async(
                self.c.lookup(base.hash_)
            )
            run_coroutine(asyncio.sleep(0))

            self.assertFalse(task.done())

            fut1.set_exception(ValueError())

            base.Future.return_value = fut2
            self.c.create_query_future(base.hash_)

            run_coroutine(asyncio.sleep(0))

            self.assertFalse(task.done())

            fut2.set_exception(ValueError())

            base.Future.return_value = fut3
            self.c.create_query_future(base.hash_)

            run_coroutine(asyncio.sleep(0))

            self.assertFalse(task.done())

            fut3.set_result(base.result)

            run_coroutine(asyncio.sleep(0))

            self.assertIs(task.result(), base.result)

    def test_lookup_key_errors_if_last_query_future_fails(self):
        fut = asyncio.Future()

        base = unittest.mock.Mock()
        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch(
                "asyncio.Future",
                new=base.Future
            ))

            stack.enter_context(unittest.mock.patch.object(
                self.c,
                "lookup_in_database",
                new=base.lookup_in_database
            ))

            base.lookup_in_database.side_effect = KeyError()
            base.Future.return_value = fut

            self.assertIs(
                self.c.create_query_future(base.hash_),
                fut,
            )

            task = asyncio.async(
                self.c.lookup(base.hash_)
            )
            run_coroutine(asyncio.sleep(0))

            self.assertFalse(task.done())

            fut.set_exception(ValueError())

            run_coroutine(asyncio.sleep(0))

            with self.assertRaises(KeyError):
                run_coroutine(task)

    def test_add_cache_entry_populates_user_database(self):
        self.c.add_cache_entry(
            "+9oi6+VEwgu5cRmjErECReGvCC0=",
            TEST_DB["+9oi6+VEwgu5cRmjErECReGvCC0="],
        )
        self.assertDictEqual(
            self.c.save_user_to_json(),
            {
                "+9oi6+VEwgu5cRmjErECReGvCC0=":
                TEST_DB["+9oi6+VEwgu5cRmjErECReGvCC0="]
            },
        )

    def tearDown(self):
        del self.c


class TestService(unittest.TestCase):
    def setUp(self):
        self.cc = make_connected_client()
        self.disco = unittest.mock.Mock()
        self.disco.query_info = CoroutineMock()
        self.disco.query_info.side_effect = AssertionError()
        self.cc.mock_services[disco.Service] = self.disco
        self.s = entitycaps_service.Service(self.cc)

        self.disco.mock_calls.clear()
        self.cc.mock_calls.clear()

        self.disco.iter_features.return_value = [
            "http://jabber.org/protocol/disco#items",
            "http://jabber.org/protocol/disco#info",
        ]

        self.disco.iter_identities.return_value = [
            ("client", "pc", None, None),
            ("client", "pc", structs.LanguageTag.fromstr("en"), "foo"),
        ]

    def test_is_Service_subclass(self):
        self.assertTrue(issubclass(
            entitycaps_service.Service,
            service.Service
        ))

    def test_after_disco(self):
        self.assertLess(
            disco.Service,
            entitycaps_service.Service
        )

    def test_setup_and_shutdown(self):
        cc = make_connected_client()
        disco_service = unittest.mock.Mock()
        cc.mock_services[disco.Service] = disco_service

        cc.mock_calls.clear()
        s = entitycaps_service.Service(cc)

        calls = list(cc.mock_calls)
        self.assertSequenceEqual(
            calls,
            [
                unittest.mock.call.
                stream.service_inbound_presence_filter.register(
                    s.handle_inbound_presence,
                    entitycaps_service.Service
                ),
                unittest.mock.call.
                stream.service_outbound_presence_filter.register(
                    s.handle_outbound_presence,
                    entitycaps_service.Service
                ),
            ]
        )
        cc.mock_calls.clear()

        self.assertSequenceEqual(
            disco_service.mock_calls,
            [
                # make sure that the callback is connected first, this will
                # make us receive the on_info_changed which causes the hash to
                # update
                unittest.mock.call.on_info_changed.connect(
                    s._info_changed
                ),
                unittest.mock.call.register_feature(
                    "http://jabber.org/protocol/caps"
                ),
            ]
        )
        disco_service.mock_calls.clear()

        run_coroutine(s.shutdown())

        calls = list(cc.mock_calls)
        self.assertSequenceEqual(
            calls,
            [
                unittest.mock.call.
                stream.service_outbound_presence_filter.unregister(
                    cc.stream.service_outbound_presence_filter.register(),
                ),
                unittest.mock.call.
                stream.service_inbound_presence_filter.unregister(
                    cc.stream.service_inbound_presence_filter.register(),
                )
            ],
        )

        calls = list(disco_service.mock_calls)
        self.assertSequenceEqual(
            calls,
            [
                unittest.mock.call.on_info_changed.disconnect(
                    disco_service.on_info_changed.connect()
                ),
                unittest.mock.call.unregister_feature(
                    "http://jabber.org/protocol/caps"
                ),
            ]
        )

    def test_cache_defaults(self):
        self.assertIsInstance(
            self.s.cache,
            entitycaps_service.Cache
        )

    def test_cache_defaults_when_deleted(self):
        c1 = self.s.cache
        del self.s.cache
        c2 = self.s.cache
        self.assertIsNot(c1, c2)
        self.assertIsInstance(c2, entitycaps_service.Cache)

    def test_cache_can_be_set(self):
        c = unittest.mock.Mock()
        self.s.cache = c
        self.assertIs(self.s.cache, c)

    def test_handle_inbound_presence_queries_disco(self):
        caps = entitycaps_xso.Caps(
            "node",
            TEST_INFO_VER,
            TEST_INFO_HASH,
        )

        presence = stanza.Presence()
        presence.from_ = TEST_FROM
        presence.xep0115_caps = caps

        with contextlib.ExitStack() as stack:
            async = stack.enter_context(
                unittest.mock.patch("asyncio.async")
            )

            lookup_info = stack.enter_context(
                unittest.mock.patch.object(self.s, "lookup_info")
            )

            result = self.s.handle_inbound_presence(presence)

        lookup_info.assert_called_with(
            presence.from_,
            caps.node, caps.ver, caps.hash_
        )

        async.assert_called_with(
            lookup_info()
        )

        self.disco.set_info_future.assert_called_with(
            TEST_FROM,
            None,
            async(),
        )

        self.assertIs(
            result,
            presence
        )

        self.assertIsNone(presence.xep0115_caps)

    def test_handle_inbound_presence_deals_with_None(self):
        presence = stanza.Presence()
        presence.from_ = TEST_FROM
        presence.xep0115_caps = None

        with contextlib.ExitStack() as stack:
            async = stack.enter_context(
                unittest.mock.patch("asyncio.async")
            )

            lookup_info = stack.enter_context(
                unittest.mock.patch.object(self.s, "lookup_info")
            )

            result = self.s.handle_inbound_presence(presence)

        self.assertFalse(lookup_info.mock_calls)
        self.assertFalse(async.mock_calls)
        self.assertFalse(self.disco.mock_calls)
        self.assertIs(
            result,
            presence
        )

        self.assertIsNone(presence.xep0115_caps)

    def test_handle_inbound_presence_discards_if_hash_unset(self):
        caps = entitycaps_xso.Caps(
            "node",
            TEST_INFO_VER,
            "foo",
        )

        # we have to hack deeply here, the validators are too smart for us
        # it is still possible to receive such a stanza, as the validator is
        # set to FROM_CODE
        caps._stanza_props[entitycaps_xso.Caps.hash_] = None
        self.assertIsNone(caps.hash_)

        presence = stanza.Presence()
        presence.xep0115_caps = caps

        with unittest.mock.patch("asyncio.async") as async:
            result = self.s.handle_inbound_presence(presence)

        self.assertFalse(async.mock_calls)

        self.assertIs(
            result,
            presence
        )

        self.assertIsNone(presence.xep0115_caps)

    def test_query_and_cache(self):
        self.maxDiff = None

        ver = "+0mnUAF1ozCEc37cmdPPsYbsfhg="
        response = dict(TEST_DB[ver])
        del response["node"]
        del response["hash"]
        response["forms"] = [
            dict(
                value,
                FORM_TYPE=[
                    key,
                ],
            )
            for key, value in response["forms"].items()
        ]

        base = unittest.mock.Mock()
        base.disco = self.disco
        base.disco.query_info.side_effect = None
        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch(
                "aioxmpp.entitycaps.service.hash_query",
                new=base.hash_query
            ))

            stack.enter_context(unittest.mock.patch.object(
                self.s.cache,
                "add_cache_entry",
                new=base.add_cache_entry
            ))

            base.disco.query_info.return_value = response
            base.hash_query.return_value = ver

            result = run_coroutine(self.s.query_and_cache(
                TEST_FROM,
                "foobar",
                ver,
                "sha-1",
                base.fut,
            ))

        cache_entry = dict(response)
        cache_entry["node"] = "foobar"
        cache_entry["hash"] = "sha-1"
        cache_entry["forms"] = dict(TEST_DB[ver]["forms"])

        calls = list(base.mock_calls)
        self.assertSequenceEqual(
            calls,
            [
                unittest.mock.call.disco.query_info(
                    TEST_FROM,
                    node="foobar#"+ver,
                    require_fresh=True
                ),
                unittest.mock.call.hash_query(
                    response,
                    "sha1"
                ),
                unittest.mock.call.add_cache_entry(
                    ver,
                    cache_entry,
                ),
                unittest.mock.call.fut.set_result(
                    result,
                )
            ]
        )

        self.assertEqual(result, response)

    def test_query_and_cache_checks_hash(self):
        self.maxDiff = None

        ver = "+0mnUAF1ozCEc37cmdPPsYbsfhg="
        response = dict(TEST_DB[ver])
        del response["node"]
        del response["hash"]

        base = unittest.mock.Mock()
        base.disco = self.disco
        base.disco.query_info.side_effect = None
        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch(
                "aioxmpp.entitycaps.service.hash_query",
                new=base.hash_query
            ))

            stack.enter_context(unittest.mock.patch.object(
                self.s.cache,
                "add_cache_entry",
                new=base.add_cache_entry
            ))

            base.disco.query_info.return_value = response
            base.hash_query.return_value = ver[:2]

            result = run_coroutine(self.s.query_and_cache(
                TEST_FROM,
                "foobar",
                ver,
                "sha-1",
                base.fut,
            ))

        calls = list(base.mock_calls)
        self.assertSequenceEqual(
            calls,
            [
                unittest.mock.call.disco.query_info(
                    TEST_FROM,
                    node="foobar#"+ver,
                    require_fresh=True
                ),
                unittest.mock.call.hash_query(
                    response,
                    "sha1"
                ),
                unittest.mock.call.fut.set_exception(unittest.mock.ANY)
            ]
        )

        _, (exc,), _ = base.fut.mock_calls[0]
        self.assertIsInstance(exc, ValueError)

        self.assertEqual(result, response)

    def test_query_and_cache_does_not_cache_on_ValueError(self):
        self.maxDiff = None

        ver = "+0mnUAF1ozCEc37cmdPPsYbsfhg="
        response = dict(TEST_DB[ver])
        del response["node"]
        del response["hash"]

        base = unittest.mock.Mock()
        base.disco = self.disco
        base.disco.query_info.side_effect = None
        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch(
                "aioxmpp.entitycaps.service.hash_query",
                new=base.hash_query
            ))

            stack.enter_context(unittest.mock.patch.object(
                self.s.cache,
                "add_cache_entry",
                new=base.add_cache_entry
            ))

            base.disco.query_info.return_value = response
            exc = ValueError()
            base.hash_query.side_effect = exc

            result = run_coroutine(self.s.query_and_cache(
                TEST_FROM,
                "foobar",
                ver,
                "sha-1",
                base.fut,
            ))

        calls = list(base.mock_calls)
        self.assertSequenceEqual(
            calls,
            [
                unittest.mock.call.disco.query_info(
                    TEST_FROM,
                    node="foobar#"+ver,
                    require_fresh=True
                ),
                unittest.mock.call.hash_query(
                    response,
                    "sha1"
                ),
                unittest.mock.call.fut.set_exception(exc)
            ]
        )

        self.assertEqual(result, response)

    def test_lookup_info_asks_cache_first_and_returns_value(self):
        base = unittest.mock.Mock()
        base.disco = self.disco
        base.disco.query_info.side_effect = None
        base.query_and_cache = CoroutineMock()
        base.lookup = CoroutineMock()

        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch.object(
                self.s.cache,
                "lookup",
                new=base.lookup,
            ))

            stack.enter_context(unittest.mock.patch.object(
                self.s,
                "query_and_cache",
                new=base.query_and_cache
            ))

            cache_result = {}
            base.lookup.return_value = cache_result

            result = run_coroutine(self.s.lookup_info(
                TEST_FROM,
                "foobar",
                "ver",
                "hash"
            ))

        self.assertSequenceEqual(
            base.mock_calls,
            [
                unittest.mock.call.lookup("ver"),
            ]
        )

        self.assertIs(result, cache_result)

    def test_lookup_info_delegates_to_query_and_cache_on_miss(self):
        base = unittest.mock.Mock()
        base.disco = self.disco
        base.disco.query_info.side_effect = None
        base.query_and_cache = CoroutineMock()

        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch.object(
                self.s.cache,
                "lookup",
                new=base.lookup
            ))

            stack.enter_context(unittest.mock.patch.object(
                self.s.cache,
                "create_query_future",
                new=base.create_query_future
            ))

            stack.enter_context(unittest.mock.patch.object(
                self.s,
                "query_and_cache",
                new=base.query_and_cache
            ))

            query_result = {}
            base.lookup.side_effect = KeyError()
            base.query_and_cache.return_value = query_result

            result = run_coroutine(self.s.lookup_info(
                TEST_FROM,
                "foobar",
                "ver",
                "hash"
            ))

        calls = list(base.mock_calls)
        self.assertSequenceEqual(
            calls,
            [
                unittest.mock.call.lookup("ver"),
                unittest.mock.call.create_query_future("ver"),
                unittest.mock.call.query_and_cache(
                    TEST_FROM,
                    "foobar",
                    "ver",
                    "hash",
                    base.create_query_future()
                )
            ]
        )

        self.assertIs(result, query_result)

    def test_update_hash(self):
        self.disco.iter_features.return_value = iter([
            "http://jabber.org/protocol/caps",
            "http://jabber.org/protocol/disco#items",
            "http://jabber.org/protocol/disco#info",
        ])

        self.disco.iter_identities.return_value = iter([
            ("client", "pc", None, None),
            ("client", "pc", structs.LanguageTag.fromstr("en"), "foo"),
        ])

        self.s.ver = "old_ver"
        old_ver = self.s.ver

        base = unittest.mock.Mock()
        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch(
                "aioxmpp.entitycaps.service.hash_query",
                new=base.hash_query
            ))
            base.hash_query.return_value = "hash_query_result"

            self.s.update_hash()

        base.hash_query.assert_called_with(
            {
                "features": [
                    "http://jabber.org/protocol/caps",
                    "http://jabber.org/protocol/disco#items",
                    "http://jabber.org/protocol/disco#info",
                ],
                "identities": [
                    {
                        "category": "client",
                        "type": "pc",
                    },
                    {
                        "category": "client",
                        "type": "pc",
                        "lang": "en",
                        "name": "foo",
                    }
                ],
                "forms": {}
            },
            "sha1",
        )

        calls = list(self.disco.mock_calls)
        self.assertSequenceEqual(
            calls,
            [
                unittest.mock.call.iter_identities(),
                unittest.mock.call.iter_features(),
                unittest.mock.call.unmount_node(
                    "http://aioxmpp.zombofant.net/#"+old_ver
                ),
                unittest.mock.call.mount_node(
                    "http://aioxmpp.zombofant.net/#"+base.hash_query(),
                    self.disco
                ),
            ]
        )

        self.assertEqual(
            self.s.ver,
            base.hash_query()
        )

    def test_update_hash_emits_on_ver_changed(self):
        self.disco.iter_features.return_value = iter([
            "http://jabber.org/protocol/caps",
            "http://jabber.org/protocol/disco#items",
            "http://jabber.org/protocol/disco#info",
        ])

        self.disco.iter_identities.return_value = iter([
            ("client", "pc", None, None),
            ("client", "pc", structs.LanguageTag.fromstr("en"), "foo"),
        ])

        self.s.ver = "old_ver"

        cb = unittest.mock.Mock()

        self.s.on_ver_changed.connect(cb)

        self.s.update_hash()

        cb.assert_called_with()

    def test_update_hash_noop_if_unchanged(self):
        self.s.ver = "hash_query_result"

        cb = unittest.mock.Mock()

        self.s.on_ver_changed.connect(cb)

        base = unittest.mock.Mock()
        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch(
                "aioxmpp.entitycaps.service.hash_query",
                new=base.hash_query
            ))
            base.hash_query.return_value = "hash_query_result"

            self.s.update_hash()

        self.assertFalse(cb.mock_calls)
        calls = list(self.disco.mock_calls)
        self.assertSequenceEqual(
            calls,
            [
                unittest.mock.call.iter_identities(),
                unittest.mock.call.iter_features(),
            ]
        )

    def test_update_hash_no_unmount_if_previous_was_None(self):
        self.s.ver = None

        base = unittest.mock.Mock()
        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch(
                "aioxmpp.entitycaps.service.hash_query",
                new=base.hash_query
            ))
            base.hash_query.return_value = "hash_query_result"

            self.s.update_hash()

        calls = list(self.disco.mock_calls)
        self.assertSequenceEqual(
            calls,
            [
                unittest.mock.call.iter_identities(),
                unittest.mock.call.iter_features(),
                unittest.mock.call.mount_node(
                    "http://aioxmpp.zombofant.net/#"+base.hash_query(),
                    self.disco
                ),
            ]
        )

    def test_update_hash_unmount_on_shutdown(self):
        self.s.ver = None

        base = unittest.mock.Mock()
        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch(
                "aioxmpp.entitycaps.service.hash_query",
                new=base.hash_query
            ))
            base.hash_query.return_value = "hash_query_result"

            self.s.update_hash()

        calls = list(self.disco.mock_calls)
        self.assertSequenceEqual(
            calls,
            [
                unittest.mock.call.iter_identities(),
                unittest.mock.call.iter_features(),
                unittest.mock.call.mount_node(
                    "http://aioxmpp.zombofant.net/#"+base.hash_query(),
                    self.disco
                ),
            ]
        )

        self.disco.mock_calls.clear()

        run_coroutine(self.s.shutdown())

        calls = list(self.disco.mock_calls)
        self.assertIn(
            unittest.mock.call.unmount_node(
                "http://aioxmpp.zombofant.net/#"+base.hash_query(),
            ),
            calls
        )

    def test__info_changed_calls_update_hash_soon(self):
        with contextlib.ExitStack() as stack:
            get_event_loop = stack.enter_context(unittest.mock.patch(
                "asyncio.get_event_loop"
            ))

            self.s._info_changed()

        get_event_loop.assert_called_with()
        get_event_loop().call_soon.assert_called_with(
            self.s.update_hash
        )

    def test_handle_outbound_presence_does_not_attach_caps_if_ver_is_None(
            self):
        self.s.ver = None

        presence = stanza.Presence()
        result = self.s.handle_outbound_presence(presence)
        self.assertIs(result, presence)

        self.assertIsNone(presence.xep0115_caps, None)

    def test_handle_outbound_presence_attaches_caps_if_not_None(self):
        self.s.ver = "foo"

        presence = stanza.Presence()
        result = self.s.handle_outbound_presence(presence)
        self.assertIs(result, presence)

        self.assertIsInstance(
            presence.xep0115_caps,
            entitycaps_xso.Caps
        )
        self.assertEqual(
            presence.xep0115_caps.ver,
            self.s.ver
        )
        self.assertEqual(
            presence.xep0115_caps.node,
            self.s.NODE
        )
        self.assertEqual(
            presence.xep0115_caps.hash_,
            "sha-1"
        )
        self.assertEqual(
            presence.xep0115_caps.ext,
            None
        )

    def test_handle_outbound_presence_does_not_attach_caps_to_non_available(
            self):
        self.s.ver = "foo"

        types = [
            "unavailable",
            "subscribe",
            "unsubscribe",
            "subscribed",
            "unsubscribed",
            "error",
        ]

        for type_ in types:
            presence = stanza.Presence(type_=type_)
            result = self.s.handle_outbound_presence(presence)
            self.assertIs(result, presence)
            self.assertIsNone(result.xep0115_caps)

# foo
