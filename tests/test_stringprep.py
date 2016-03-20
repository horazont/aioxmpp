import unittest

from aioxmpp.stringprep import (
    nodeprep, resourceprep, nameprep,
    check_bidi
)


class Testcheck_bidi(unittest.TestCase):
    # some test cases which are not covered by the other tests
    def test_empty_string(self):
        check_bidi("")

    def test_L_RAL_violation(self):
        with self.assertRaises(ValueError):
            check_bidi("\u05be\u0041")


class TestNodeprep(unittest.TestCase):
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
        with self.assertRaisesRegex(
                ValueError,
                r"U\+0007",
                msg="Nodeprep requirement: prohibited character (C.2.1)"):
            nodeprep("\u0007")

        with self.assertRaisesRegex(
                ValueError,
                r"U\+200e",
                msg="Nodeprep requirement: prohibited character (C.8)"):
            nodeprep("\u200E")

        with self.assertRaisesRegex(
                ValueError,
                r"U\+003e",
                msg="Nodeprep requirement: prohibited character (custom)"):
            nodeprep(">")

    def test_unassigned(self):
        with self.assertRaises(
                ValueError,
                msg="Nodeprep requirement: unassigned"):
            nodeprep("\u0221", allow_unassigned=False)

        with self.assertRaises(
                ValueError,
                msg="enforce no unassigned by default"):
            nodeprep("\u0221")

        self.assertEqual(
            "\u0221",
            nodeprep("\u0221", allow_unassigned=True))


class TestNameprep(unittest.TestCase):
    def test_map_to_nothing(self):
        self.assertEqual(
            "ix",
            nameprep("I\u00ADX"),
            "Nameprep requirement: map SOFT HYPHEN to nothing")

    def test_case_fold(self):
        self.assertEqual(
            "ssa",
            nameprep("ßA"),
            "Nameprep requirement: map ß to ss, A to a")

    def test_nfkc(self):
        self.assertEqual(
            "a",
            nodeprep("\u00AA"),
            "Nameprep requirement: NFKC")
        self.assertEqual(
            "ix",
            nodeprep("\u2168"),
            "Nameprep requirement: NFKC")

    def test_prohibited_character(self):
        with self.assertRaisesRegex(
                ValueError,
                r"U\+06dd",
                msg="Nameprep requirement: prohibited character (C.2.2)"):
            nameprep("\u06DD")

        with self.assertRaisesRegex(
                ValueError,
                r"U\+e000",
                msg="Nameprep requirement: prohibited character (C.3)"):
            nameprep("\uE000")

        with self.assertRaisesRegex(
                ValueError,
                r"U\+1fffe",
                msg="Nameprep requirement: prohibited character (C.4)"):
            nameprep("\U0001FFFE")

        with self.assertRaisesRegex(
                ValueError,
                r"U\+d800",
                msg="Nameprep requirement: prohibited character (C.5)"):
            nameprep("\uD800")

        with self.assertRaisesRegex(
                ValueError,
                r"U\+fff9",
                msg="Nameprep requirement: prohibited character (C.6)"):
            nameprep("\uFFF9")

        with self.assertRaisesRegex(
                ValueError,
                r"U\+2ff0",
                msg="Nameprep requirement: prohibited character (C.7)"):
            nameprep("\u2FF0")

        with self.assertRaisesRegex(
                ValueError,
                r"U\+e0001",
                msg="Nameprep requirement: prohibited character (C.9)"):
            nameprep("\U000E0001")

    def test_unassigned(self):
        with self.assertRaises(
                ValueError,
                msg="Nameprep requirement: unassigned"):
            nameprep("\u0221", allow_unassigned=False)

        with self.assertRaises(
                ValueError,
                msg="enforce no unassigned by default"):
            nameprep("\u0221")

        self.assertEqual(
            "\u0221",
            nameprep("\u0221", allow_unassigned=True))


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
        with self.assertRaisesRegex(
                ValueError,
                r"U\+0007",
                msg="Resourceprep requirement: "
                    "prohibited character (C.2.1)"):
            resourceprep("\u0007")

        with self.assertRaisesRegex(
                ValueError,
                r"U\+200e",
                msg="Resourceprep requirement: "
                    "prohibited character (C.8)"):
            resourceprep("\u200E")

    def test_unassigned(self):
        with self.assertRaises(
                ValueError,
                msg="Resourceprep requirement: unassigned"):
            resourceprep("\u0221", allow_unassigned=False)

        with self.assertRaises(
                ValueError,
                msg="enforce no unassigned by default"):
            resourceprep("\u0221")

        self.assertEqual(
            "\u0221",
            resourceprep("\u0221", allow_unassigned=True))
