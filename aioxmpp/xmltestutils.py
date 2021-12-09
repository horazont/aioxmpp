########################################################################
# File name: xmltestutils.py
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
import unittest


def element_path(el, upto=None):
    segments = []
    parent = el.getparent()

    while parent != upto:
        similar = list(parent.iterchildren(el.tag))
        index = similar.index(el)
        segments.insert(0, (el.tag, index))
        el = parent
        parent = el.getparent()

    base = "/" + el.tag
    if segments:
        return base + "/" + "/".join(
            "{}[{}]".format(tag, index)
            for tag, index in segments
        )
    return base


class XMLTestCase(unittest.TestCase):
    def assertChildrenEqual(self, tree1, tree2,
                            strict_ordering=False,
                            ignore_surplus_children=False,
                            ignore_surplus_attr=False):
        if not strict_ordering:
            t1_childmap = {}
            for child in tree1:
                t1_childmap.setdefault(child.tag, []).append(child)
            t2_childmap = {}
            for child in tree2:
                t2_childmap.setdefault(child.tag, []).append(child)

            t1_childtags = frozenset(t1_childmap)
            t2_childtags = frozenset(t2_childmap)

            if not ignore_surplus_children or (t1_childtags - t2_childtags):
                self.assertSetEqual(
                    t1_childtags,
                    t2_childtags,
                    "Child tag occurrence differences at {}".format(
                        element_path(tree2)))

            for tag, t1_children in t1_childmap.items():
                t2_children = t2_childmap.get(tag, [])
                self.assertLessEqual(
                    len(t1_children),
                    len(t2_children),
                    "Surplus child at {}".format(element_path(tree2))
                )
                if not ignore_surplus_children:
                    self.assertGreaterEqual(
                        len(t1_children),
                        len(t2_children),
                        "Surplus child at {}".format(element_path(tree2))
                    )

                for c1, c2 in zip(t1_children, t2_children):
                    self.assertSubtreeEqual(
                        c1, c2,
                        ignore_surplus_attr=ignore_surplus_attr,
                        ignore_surplus_children=ignore_surplus_children,
                        strict_ordering=strict_ordering)
        else:
            t1_children = list(tree1)
            t2_children = list(tree2)
            self.assertLessEqual(
                len(t1_children),
                len(t2_children),
                "Surplus child at {}".format(element_path(tree2))
            )
            if not ignore_surplus_children:
                self.assertGreaterEqual(
                    len(t1_children),
                    len(t2_children),
                    "Surplus child at {}".format(element_path(tree2))
                )

            for c1, c2 in zip(t1_children, t2_children):
                self.assertSubtreeEqual(
                    c1, c2,
                    ignore_surplus_attr=ignore_surplus_attr,
                    ignore_surplus_children=ignore_surplus_children,
                    strict_ordering=strict_ordering)

    def assertAttributesEqual(self, el1, el2,
                              ignore_surplus_attr=False):
        t1_attrdict = el1.attrib
        t2_attrdict = el2.attrib
        t1_attrs = set(t1_attrdict)
        t2_attrs = set(t2_attrdict)

        if not ignore_surplus_attr or (t1_attrs - t2_attrs):
            self.assertSetEqual(
                t1_attrs,
                t2_attrs,
                "Attribute key differences at {}".format(element_path(el2))
            )

        for attr in t1_attrs:
            self.assertEqual(
                t1_attrdict[attr],
                t2_attrdict[attr],
                "Attribute value difference at {}@{}".format(
                    element_path(el2),
                    attr))

    def _collect_text_parts(self, el):
        parts = [el.text or ""]
        parts.extend(child.tail or "" for child in el)
        return parts

    def assertTextContentEqual(self, el1, el2, join_text_parts=True):
        parts1 = self._collect_text_parts(el1)
        parts2 = self._collect_text_parts(el2)
        if join_text_parts:
            self.assertEqual(
                "".join(parts1),
                "".join(parts2),
                "text mismatch at {}".format(element_path(el2))
            )
        else:
            self.assertSequenceEqual(
                parts1,
                parts2,
                "text mismatch at {}".format(element_path(el2))
            )

    def assertSubtreeEqual(self, tree1, tree2,
                           ignore_surplus_attr=False,
                           ignore_surplus_children=False,
                           strict_ordering=False,
                           join_text_parts=True):
        self.assertEqual(tree1.tag, tree2.tag,
                         "tag mismatch at {}".format(element_path(tree2)))

        self.assertTextContentEqual(tree1, tree2,
                                    join_text_parts=join_text_parts)

        self.assertAttributesEqual(tree1, tree2,
                                   ignore_surplus_attr=ignore_surplus_attr)
        self.assertChildrenEqual(
            tree1, tree2,
            ignore_surplus_children=ignore_surplus_children,
            ignore_surplus_attr=ignore_surplus_attr,
            strict_ordering=strict_ordering)
