import unittest

from .stringprep import saslprep, nodeprep, resourceprep

class TestSASLprep(unittest.TestCase):
    def test_map_to_nothing_rfcx(self):
        self.assertEqual(
            "IX",
            saslprep("I\u00ADX"),
            "SASLprep requirement: map SOFT HYPHEN to nothing")

    def test_identity_rfcx(self):
        self.assertEqual(
            "user",
            saslprep("user"),
            "SASLprep requirement: identity transform")

    def test_case_preservation_rfcx(self):
        self.assertEqual(
            "USER",
            saslprep("USER"),
            "SASLprep requirement: preserve case")

    def test_nfkc_rfcx(self):
        self.assertEqual(
            "a",
            saslprep("\u00AA"),
            "SASLprep requirement: NFKC")
        self.assertEqual(
            "IX",
            saslprep("\u2168"),
            "SASLprep requirement: NFKC")

    def test_prohibited_character_rfcx(self):
        with self.assertRaises(
                ValueError,
                msg="SASLprep requirement: prohibited character (C.2.1)") as err:
            saslprep("\u0007")

        with self.assertRaises(
                ValueError,
                msg="SASLprep requirement: prohibited character (C.8)") as err:
            saslprep("\u200E")

    def test_bidirectional_check_rfcx(self):
        with self.assertRaises(
                ValueError,
                msg="SASLprep requirement: bidirectional check") as err:
            saslprep("\u0627\u0031")

    def test_unassigned(self):
        with self.assertRaises(
                ValueError,
                msg="SASLprep requirement: unassigned") as err:
            saslprep("\u0221", allow_unassigned=False)

        with self.assertRaises(
                ValueError,
                msg="enforce no unassigned by default") as err:
            saslprep("\u0221")

        self.assertEqual(
            "\u0221",
            saslprep("\u0221", allow_unassigned=True))


class TestResourceprep(unittest.TestCase):
    def test_map_to_nothing(self):
        self.assertEqual(
            "ix",
            nodeprep("I\u00ADX"),
            "Nodeprep requirement: map SOFT HYPHEN to nothing")

    def test_case_fold(self):
        self.assertEqual(
            "ssa",
            nodeprep("ßA"),
            "Nodeprep requirement: map ß to ss, A to a")

    def test_nfkc(self):
        self.assertEqual(
            "a",
            nodeprep("\u00AA"),
            "Nodeprep requirement: NFKC")
        self.assertEqual(
            "ix",
            nodeprep("\u2168"),
            "Nodeprep requirement: NFKC")

    def test_prohibited_character(self):
        with self.assertRaises(
                ValueError,
                msg="Nodeprep requirement: prohibited character (C.2.1)") as err:
            nodeprep("\u0007")

        with self.assertRaises(
                ValueError,
                msg="Nodeprep requirement: prohibited character (C.8)") as err:
            nodeprep("\u200E")

        with self.assertRaises(
                ValueError,
                msg="Nodeprep requirement: prohibited character (custom)") as err:
            nodeprep(">")


class TestResourceprep(unittest.TestCase):
    def test_map_to_nothing(self):
        self.assertEqual(
            "IX",
            resourceprep("I\u00ADX"),
            "Resourceprep requirement: map SOFT HYPHEN to nothing")

    def test_nfkc(self):
        self.assertEqual(
            "a",
            resourceprep("\u00AA"),
            "Resourceprep requirement: NFKC")
        self.assertEqual(
            "IX",
            resourceprep("\u2168"),
            "Resourceprep requirement: NFKC")

    def test_prohibited_character(self):
        with self.assertRaises(
                ValueError,
                msg="Resourceprep requirement: "
                    "prohibited character (C.2.1)") as err:
            resourceprep("\u0007")

        with self.assertRaises(
                ValueError,
                msg="Resourceprep requirement: "
                    "prohibited character (C.8)") as err:
            resourceprep("\u200E")
