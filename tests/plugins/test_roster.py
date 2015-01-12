import unittest

import asyncio_xmpp.plugins.roster as roster
import asyncio_xmpp.jid as jid

class TestRosterItemChange(unittest.TestCase):
    def setUp(self):
        item = roster.RosterItemInfo()
        item.jid = jid.JID.fromstr("foo@example.invalid")
        item.name = "foo"
        self.item = item

    def test_init_defaults(self):
        kwargs = {
            "itemjid": jid.JID.fromstr("foo@example.invalid"),
        }
        item1 = roster.RosterItemChange(**kwargs)
        kwargs.update(
            name=None,
            add_to_groups=None,
            remove_from_groups=None,
            delete=False
        )
        item2 = roster.RosterItemChange(**kwargs)

        self.assertEqual(item1, item2)
        # test that values are handled correctly
        self.assertSetEqual(set(), item1.remove_from_groups)
        self.assertDictEqual(dict(), item1.add_to_groups)
        self.assertIsNone(item1.name)
        self.assertFalse(item1.delete)

    def test_strict_init(self):
        kwargs_template = {
            "itemjid": jid.JID.fromstr("foo@example.invalid"),
        }

        kwargs = kwargs_template.copy()
        kwargs["itemjid"] = jid.JID.fromstr("foo@example.invalid/nonbare")
        with self.assertRaises(ValueError):
            roster.RosterItemChange(**kwargs)

        kwargs = kwargs_template.copy()
        kwargs["name"] = "foobar"
        with self.assertRaises(ValueError):
            roster.RosterItemChange(**kwargs)

        kwargs = kwargs_template.copy()
        kwargs["name"] = ("A", "B", "C")
        with self.assertRaises(ValueError):
            roster.RosterItemChange(**kwargs)

        kwargs = kwargs_template.copy()
        kwargs["delete"] = True
        kwargs["name"] = ("a", "b")
        with self.assertRaises(ValueError):
            roster.RosterItemChange(**kwargs)

    def test_apply_failures(self):
        change = roster.RosterItemChange(
            itemjid=self.item.jid,
            name=("bar", "fnord")
        )
        with self.assertRaisesRegexp(ValueError, "apply failed:.*"):
            change.apply(self.item)

        change = roster.RosterItemChange(
            itemjid=self.item.jid,
            remove_from_groups=["a"]
        )
        with self.assertRaisesRegexp(ValueError, "apply failed:.*"):
            change.apply(self.item)

        self.item.groups.add("foo")

        change = roster.RosterItemChange(
            itemjid=self.item.jid,
            add_to_groups=[("foo", None)]
        )
        with self.assertRaisesRegexp(ValueError, "apply failed:.*"):
            change.apply(self.item)

    def test_apply_change_name(self):
        roster.RosterItemChange(
            itemjid=self.item.jid,
            name=(self.item.name, "bar")
        ).apply(self.item)

        self.assertEqual("bar", self.item.name)

    def test_apply_add_to_group(self):
        roster.RosterItemChange(
            itemjid=self.item.jid,
            add_to_groups={"foo": None}
        ).apply(self.item)

        self.assertSetEqual(
            {"foo"},
            self.item.groups)

    def test_apply_remove_from_group(self):
        self.item.groups = {"foo"}
        roster.RosterItemChange(
            itemjid=self.item.jid,
            remove_from_groups={"foo"}
        ).apply(self.item)

        self.assertSetEqual(
            set(),
            self.item.groups)

    def test_rebase_remove_from_groups(self):
        change = roster.RosterItemChange(
            itemjid=self.item.jid,
            remove_from_groups={"foo"}
        ).rebase(self.item)
        self.assertSetEqual(set(), change.remove_from_groups)

    def test_rebase_add_to_groups(self):
        self.item.groups = {"foo"}
        change = roster.RosterItemChange(
            itemjid=self.item.jid,
            add_to_groups={"foo": None}
        ).rebase(self.item)
        self.assertDictEqual(dict(), change.add_to_groups)

    def test_rebase_name(self):
        change = roster.RosterItemChange(
            itemjid=self.item.jid,
            name=None
        ).rebase(self.item)
        self.assertIsNone(change.name)

        change = roster.RosterItemChange(
            itemjid=self.item.jid,
            name=("fnord", "bar")
        ).rebase(self.item)
        self.assertEqual(("foo", "bar"), change.name)

    def test_add_failures_jid_mismatch(self):
        change1 = roster.RosterItemChange(
            itemjid=jid.JID.fromstr("foo@example.invalid")
        )
        change2 = roster.RosterItemChange(
            itemjid=jid.JID.fromstr("foo@bar.invalid")
        )
        with self.assertRaisesRegexp(ValueError,
                                     "jids of changes must be equal.*"):
            change1.add(change2)

    def test_add_strict_failures_delete_delete(self):
        change = roster.RosterItemChange(
            itemjid=self.item.jid,
            delete=True
        )
        with self.assertRaisesRegexp(ValueError, "delete/delete conflict"):
            change.add(change, strict=True)

    def test_add_strict_failures_modify_modify(self):
        change1 = roster.RosterItemChange(
            itemjid=self.item.jid,
            name=("foo", "bar")
        )
        change2 = roster.RosterItemChange(
            itemjid=self.item.jid,
            name=("foo", "baz")
        )
        with self.assertRaisesRegexp(ValueError, "modify/modify conflict"):
            change1.add(change2, strict=True)

    def test_add_strict_failures_add_add(self):
        change1 = roster.RosterItemChange(
            itemjid=self.item.jid,
            add_to_groups={"foo": None},
        )
        change2 = roster.RosterItemChange(
            itemjid=self.item.jid,
            add_to_groups={"foo": None}
        )
        with self.assertRaisesRegexp(ValueError, "add/add conflict"):
            change1.add(change2, strict=True)

    def test_add_name(self):
        change_base = roster.RosterItemChange(
            itemjid=self.item.jid,
            name=("foo", "bar")
        )

        self.assertEqual(
            roster.RosterItemChange(
                itemjid=self.item.jid,
                name=("foo", "baz")
            ),
            change_base.add(
                roster.RosterItemChange(
                    itemjid=self.item.jid,
                    name=("bar", "baz")
                ),
                strict=True
            )
        )

        self.assertEqual(
            roster.RosterItemChange(
                itemjid=self.item.jid,
                name=("foo", "baz")
            ),
            change_base.add(
                roster.RosterItemChange(
                    itemjid=self.item.jid,
                    name=("foo", "baz")
                ),
                strict=False
            )
        )

        self.assertEqual(
            change_base,
            roster.RosterItemChange(
                itemjid=self.item.jid,
                name=None
            ).add(change_base,
                  strict=True)
        )

    def test_add_add_to_groups(self):
        change_base = roster.RosterItemChange(
            itemjid=self.item.jid,
            add_to_groups={"foo": 1}
        )

        self.assertEqual(
            roster.RosterItemChange(
                itemjid=self.item.jid,
                add_to_groups={"foo": 1, "bar": 2}
            ),
            change_base.add(
                roster.RosterItemChange(
                    itemjid=self.item.jid,
                    add_to_groups={"bar": 2}
                ),
                strict=True
            )
        )

        self.assertEqual(
            roster.RosterItemChange(
                itemjid=self.item.jid,
                add_to_groups={"foo": 2}
            ),
            change_base.add(
                roster.RosterItemChange(
                    itemjid=self.item.jid,
                    add_to_groups={"foo": 2}
                ),
                strict=False
            )
        )

    def test_add_remove_from_groups(self):
        change_base = roster.RosterItemChange(
            itemjid=self.item.jid,
            remove_from_groups={"foo"}
        )

        self.assertEqual(
            change_base,
            change_base.add(change_base)
        )
        self.assertEqual(
            change_base,
            change_base.add(change_base, strict=True)
        )
        self.assertEqual(
            roster.RosterItemChange(
                itemjid=self.item.jid,
                remove_from_groups={"foo", "bar"}
            ),
            change_base.add(
                roster.RosterItemChange(
                    itemjid=self.item.jid,
                    remove_from_groups={"foo", "bar"}
                ),
                strict=True)
        )

    def test_add_add_and_remove_from_groups(self):
        self.assertEqual(
            roster.RosterItemChange(
                itemjid=self.item.jid,
                add_to_groups={"foo": 1}
            ),
            roster.RosterItemChange(
                itemjid=self.item.jid,
                remove_from_groups={"foo"}
            ).add(
                roster.RosterItemChange(
                    itemjid=self.item.jid,
                    add_to_groups={"foo": 1}
                ),
                strict=True
            )
        )

        self.assertEqual(
            roster.RosterItemChange(
                itemjid=self.item.jid,
                remove_from_groups={"foo"}
            ),
            roster.RosterItemChange(
                itemjid=self.item.jid,
                add_to_groups={"foo": 1}
            ).add(
                roster.RosterItemChange(
                    itemjid=self.item.jid,
                    remove_from_groups={"foo"}
                ),
                strict=True
            )
        )
