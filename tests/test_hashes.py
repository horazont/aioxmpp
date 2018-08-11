########################################################################
# File name: test_hashes.py
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
import hashlib
import unittest
import unittest.mock

import aioxmpp.hashes as hashes
import aioxmpp.xso

from aioxmpp.utils import namespaces


class TestNamespaces(unittest.TestCase):
    def test_namespace(self):
        self.assertEqual(
            namespaces.xep0300_hashes2,
            "urn:xmpp:hashes:2",
        )


class TestHash(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            hashes.Hash,
            aioxmpp.xso.XSO
        ))

    def test_tag(self):
        self.assertEqual(
            hashes.Hash.TAG,
            (namespaces.xep0300_hashes2, "hash"),
        )

    def test_init_default(self):
        with self.assertRaises(TypeError):
            hashes.Hash()

    def test_init(self):
        h = hashes.Hash("algo", b"digest")
        self.assertEqual(h.algo, "algo")
        self.assertEqual(h.digest, b"digest")

    def test_get_impl_uses_hash_from_algo(self):
        h = hashes.Hash("some algo", b"foo")
        with unittest.mock.patch(
                "aioxmpp.hashes.hash_from_algo") as hash_from_algo:
            impl = h.get_impl()
            hash_from_algo.assert_called_once_with(
                h.algo,
            )
            self.assertEqual(impl, hash_from_algo())


class TestHashType(unittest.TestCase):
    def test_is_element_type(self):
        self.assertTrue(issubclass(
            hashes.HashType,
            aioxmpp.xso.AbstractElementType,
        ))

    def test_get_xso_types(self):
        self.assertCountEqual(
            hashes.HashType.get_xso_types(),
            [hashes.Hash],
        )

    def test_pack(self):
        t = hashes.HashType()
        h = t.pack(("sha-1", b"foobar"))
        self.assertIsInstance(h, hashes.Hash)
        self.assertEqual(h.algo, "sha-1")
        self.assertEqual(h.digest, b"foobar")

    def test_unpack(self):
        t = hashes.HashType()
        h = hashes.Hash("fnord", b"baz")
        pair = t.unpack(h)
        self.assertSequenceEqual(
            pair,
            (
                "fnord",
                b"baz",
            )
        )


class TestHashesParent(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            hashes.HashesParent,
            aioxmpp.xso.XSO,
        ))

    def test_has_no_tag(self):
        self.assertFalse(
            hasattr(hashes.HashesParent, "TAG")
        )

    def test_digests(self):
        self.assertIsInstance(
            hashes.HashesParent.digests,
            aioxmpp.xso.ChildValueMap
        )
        self.assertIsInstance(
            hashes.HashesParent.digests.type_,
            hashes.HashType,
        )


class Testhash_from_algo(unittest.TestCase):
    def test_all_supported(self):
        for algo_name, (enabled,
                        (fun_name,
                         fun_args,
                         fun_kwargs)) in hashes._HASH_ALGO_MAPPING:
            if not enabled:
                continue

            with unittest.mock.patch(
                    "hashlib.{}".format(fun_name),
                    create=True) as hash_impl:
                result = hashes.hash_from_algo(algo_name)

            hash_impl.assert_called_once_with(
                *fun_args,
                **fun_kwargs
            )

            self.assertEqual(
                result,
                hash_impl(),
            )

    def test_raise_ValueError_for_MUST_NOT_hashes(self):
        with self.assertRaisesRegexp(
                ValueError,
                "support of md2 in XMPP is forbidden"):
            hashes.hash_from_algo("md2")

        with self.assertRaisesRegexp(
                ValueError,
                "support of md4 in XMPP is forbidden"):
            hashes.hash_from_algo("md4")

        with self.assertRaisesRegexp(
                ValueError,
                "support of md5 in XMPP is forbidden"):
            hashes.hash_from_algo("md5")

    def test_raises_NotImplementedError_if_function_not_supported(self):
        _sha1 = hashlib.sha1
        with self.assertRaisesRegexp(
                NotImplementedError,
                "sha-1 not supported by hashlib") as ctx:
            del hashlib.sha1
            try:
                hashes.hash_from_algo("sha-1")
            finally:
                hashlib.sha1 = _sha1

        self.assertIsInstance(ctx.exception.__cause__, AttributeError)

    def test_raises_NotImplementedError_if_function_not_defined(self):
        with self.assertRaisesRegexp(
                NotImplementedError,
                "hash algorithm 'foobar' unknown"):
            hashes.hash_from_algo("foobar")


class Testis_algo_supported(unittest.TestCase):
    def test_all_supported(self):
        for algo_name, (enabled,
                        (fun_name,
                         fun_args,
                         fun_kwargs)) in hashes._HASH_ALGO_MAPPING:
            if not enabled:
                self.assertFalse(
                    hashes.is_algo_supported(algo_name)
                )
            else:
                with unittest.mock.patch(
                        "hashlib.{}".format(fun_name),
                        create=True) as hash_impl:
                    self.assertTrue(hashes.is_algo_supported(algo_name))

                hash_impl.assert_not_called()

    def test_return_false_for_MUST_NOT_hashes(self):
        self.assertFalse(hashes.is_algo_supported("md2"))
        self.assertFalse(hashes.is_algo_supported("md4"))
        self.assertFalse(hashes.is_algo_supported("md5"))

    def test_return_false_if_function_not_implemented(self):
        try:
            _sha3_256 = hashlib.sha3_256
        except AttributeError:
            self.assertFalse(hashes.is_algo_supported("sha3-256"))
            return

        self.assertTrue(hashes.is_algo_supported("sha3-256"))
        del hashlib.sha3_256

        try:
            self.assertFalse(hashes.is_algo_supported("sha3-256"))
        finally:
            hashlib.sha3_256 = _sha3_256

    def test_return_false_if_function_not_defined(self):
        self.assertFalse(hashes.is_algo_supported("foobar"))


class Testalgo_from_hashlib(unittest.TestCase):
    def test_all_supported(self):
        for algo_name, (enabled,
                        (fun_name,
                         fun_args,
                         fun_kwargs)) in hashes._HASH_ALGO_MAPPING:
            if not enabled:
                continue

            try:
                impl = hashes.hash_from_algo(algo_name)
            except NotImplementedError:
                continue

            self.assertEqual(
                algo_name,
                hashes.algo_of_hash(impl)
            )

    def test_raise_ValueError_for_MUST_NOT_hashes(self):
        with self.assertRaisesRegexp(
                ValueError,
                "support of md5 in XMPP is forbidden"):
            hashes.algo_of_hash(hashlib.md5())

    def test_sha1(self):
        m = unittest.mock.Mock()
        m.name = "sha1"

        self.assertEqual(
            "sha-1",
            hashes.algo_of_hash(m),
        )

    def test_sha2(self):
        for size in ["224", "256", "384", "512"]:
            m = unittest.mock.Mock()
            m.name = "sha{}".format(size)

            self.assertEqual(
                "sha-{}".format(size),
                hashes.algo_of_hash(m),
            )

    def test_sha3(self):
        for size in ["256", "512"]:
            m = unittest.mock.Mock()
            m.name = "sha3_{}".format(size)

            self.assertEqual(
                "sha3-{}".format(size),
                hashes.algo_of_hash(m),
            )

    def test_blake2b(self):
        versions = [
            (32, "blake2b-256"),
            (64, "blake2b-512"),
        ]

        for digest_size, algo in versions:
            m = unittest.mock.Mock()
            m.digest_size = digest_size
            m.name = "blake2b"

            self.assertEqual(
                algo,
                hashes.algo_of_hash(m),
            )

    def test_raise_ValueError_on_unknown(self):
        m = unittest.mock.Mock()
        with self.assertRaisesRegexp(
                ValueError,
                "unknown hash implementation: <Mock id=.+>"):
            hashes.algo_of_hash(m)


class Testdefault_hash_algorithms(unittest.TestCase):
    def test_selection(self):
        selected = set(hashes.default_hash_algorithms)
        self.assertIn(
            "sha-256",
            selected,
        )

        try:
            hashes.hash_from_algo("sha3-256")
        except NotImplementedError:
            self.assertNotIn("sha3-256", selected)
        else:
            self.assertIn("sha3-256", selected)

        try:
            hashes.hash_from_algo("blake2b-256")
        except NotImplementedError:
            self.assertNotIn("blake2b-256", selected)
        else:
            self.assertIn("blake2b-256", selected)

    def test_all_selected_can_be_instantiated(self):
        for algo in hashes.default_hash_algorithms:
            hashes.hash_from_algo(algo)
