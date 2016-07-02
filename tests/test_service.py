import abc
import itertools
import logging
import unittest

import aioxmpp.service as service

from aioxmpp.testutils import run_coroutine


class TestServiceMeta(unittest.TestCase):
    def test_inherits_from_ABCMeta(self):
        self.assertTrue(issubclass(service.Meta, abc.ABCMeta))

    def test_ordering_attributes(self):
        class Foo(metaclass=service.Meta):
            pass

        self.assertSetEqual(
            set(),
            Foo.ORDER_BEFORE
        )
        self.assertSetEqual(
            set(),
            Foo.ORDER_AFTER
        )

    def test_configure_ordering(self):
        class Foo(metaclass=service.Meta):
            pass

        class Bar(metaclass=service.Meta):
            ORDER_BEFORE = [Foo]

        self.assertSetEqual(
            {Foo},
            Bar.ORDER_BEFORE
        )
        self.assertSetEqual(
            set(),
            Bar.ORDER_AFTER
        )
        self.assertSetEqual(
            {Bar},
            Foo.ORDER_AFTER
        )
        self.assertSetEqual(
            set(),
            Foo.ORDER_BEFORE
        )

    def test_transitive_before_ordering(self):
        class Foo(metaclass=service.Meta):
            pass

        class Bar(metaclass=service.Meta):
            ORDER_BEFORE = [Foo]

        class Baz(metaclass=service.Meta):
            ORDER_BEFORE = [Bar]

        self.assertSetEqual(
            {Foo},
            Bar.ORDER_BEFORE
        )
        self.assertSetEqual(
            {Foo, Bar},
            Baz.ORDER_BEFORE
        )
        self.assertSetEqual(
            {Bar, Baz},
            Foo.ORDER_AFTER
        )
        self.assertSetEqual(
            {Baz},
            Bar.ORDER_AFTER
        )
        self.assertSetEqual(
            set(),
            Foo.ORDER_BEFORE
        )
        self.assertSetEqual(
            set(),
            Baz.ORDER_AFTER
        )

    def test_transitive_after_ordering(self):
        class Foo(metaclass=service.Meta):
            pass

        class Bar(metaclass=service.Meta):
            ORDER_AFTER = [Foo]

        class Baz(metaclass=service.Meta):
            ORDER_AFTER = [Bar]

        self.assertSetEqual(
            {Foo},
            Bar.ORDER_AFTER
        )
        self.assertSetEqual(
            {Foo, Bar},
            Baz.ORDER_AFTER
        )
        self.assertSetEqual(
            {Bar, Baz},
            Foo.ORDER_BEFORE
        )
        self.assertSetEqual(
            {Baz},
            Bar.ORDER_BEFORE
        )
        self.assertSetEqual(
            set(),
            Foo.ORDER_AFTER
        )
        self.assertSetEqual(
            set(),
            Baz.ORDER_BEFORE
        )

    def test_loop_detect(self):
        class Foo(metaclass=service.Meta):
            pass

        class Bar(metaclass=service.Meta):
            ORDER_AFTER = [Foo]

        with self.assertRaisesRegex(
                ValueError,
                "dependency loop: Fnord loops through .*\.(Foo|Bar)"):

            class Fnord(metaclass=service.Meta):
                ORDER_BEFORE = [Foo]
                ORDER_AFTER = [Bar]

            print(Fnord.ORDER_BEFORE)
            print(Fnord.ORDER_AFTER)

    def test_partial_dependency_ordering_puts_earliest_first(self):
        class Foo(metaclass=service.Meta):
            pass

        class Bar(metaclass=service.Meta):
            ORDER_BEFORE = [Foo]

        class Baz(metaclass=service.Meta):
            ORDER_BEFORE = [Bar]

        class Fourth(metaclass=service.Meta):
            ORDER_BEFORE = [Bar]

        self.assertLess(Baz, Bar)
        self.assertLess(Fourth, Bar)
        self.assertLess(Bar, Foo)
        self.assertLess(Baz, Foo)
        self.assertLess(Fourth, Foo)

        self.assertLessEqual(Baz, Bar)
        self.assertLessEqual(Fourth, Bar)
        self.assertLessEqual(Bar, Foo)
        self.assertLessEqual(Baz, Foo)
        self.assertLessEqual(Fourth, Foo)

        self.assertGreater(Foo, Bar)
        self.assertGreater(Foo, Baz)
        self.assertGreater(Foo, Fourth)
        self.assertGreater(Bar, Baz)
        self.assertGreater(Bar, Fourth)

        self.assertGreaterEqual(Foo, Bar)
        self.assertGreaterEqual(Foo, Baz)
        self.assertGreaterEqual(Foo, Fourth)
        self.assertGreaterEqual(Bar, Baz)
        self.assertGreaterEqual(Bar, Fourth)

        services = [Foo, Bar, Baz, Fourth]

        for a, b in itertools.product(services, services):
            if a is b:
                self.assertEqual(a, b)
                self.assertFalse(a != b)
            else:
                self.assertNotEqual(a, b)
                self.assertFalse(a == b)

        services.sort()

        self.assertSequenceEqual(
            [Baz, Fourth, Bar, Foo],
            services
        )

        services = [Foo, Bar, Fourth, Baz]
        services.sort()

        self.assertSequenceEqual(
            [Fourth, Baz, Bar, Foo],
            services
        )

    def test_simple_inheritance_inherit_ordering(self):
        class Foo(metaclass=service.Meta):
            pass

        class Bar(metaclass=service.Meta):
            pass

        class A(metaclass=service.Meta):
            ORDER_BEFORE = [Foo]
            ORDER_AFTER = [Bar]

        class B(A):
            pass

        self.assertSetEqual(A.ORDER_BEFORE, B.ORDER_BEFORE)
        self.assertSetEqual(A.ORDER_AFTER, B.ORDER_AFTER)

        self.assertIsNot(A.ORDER_BEFORE, B.ORDER_BEFORE)
        self.assertIsNot(A.ORDER_AFTER, B.ORDER_AFTER)

    def test_inheritance_ignores_non_service_classes(self):
        class Foo(metaclass=service.Meta):
            pass

        class Bar:
            ORDER_BEFORE = [Foo]

        class Baz(Bar, metaclass=service.Meta):
            pass

        self.assertSetEqual(set(), Baz.ORDER_BEFORE)

    def test_diamond_inheritance(self):
        class Foo(metaclass=service.Meta):
            pass

        class Bar(metaclass=service.Meta):
            pass

        class Baz(metaclass=service.Meta):
            pass

        class A(metaclass=service.Meta):
            ORDER_BEFORE = [Foo]

        class B1(A):
            ORDER_AFTER = [Bar]

        class B2(A):
            ORDER_BEFORE = [Baz]

        class D(B1, B2):
            pass

        self.assertSetEqual(
            {A, B1, B2, D},
            Foo.ORDER_AFTER
        )
        self.assertSetEqual(
            {B1, D},
            Bar.ORDER_BEFORE
        )
        self.assertSetEqual(
            {B2, D},
            Baz.ORDER_AFTER
        )
        self.assertSetEqual(
            {Foo, Baz},
            D.ORDER_BEFORE
        )
        self.assertSetEqual(
            {Foo, Baz},
            B2.ORDER_BEFORE
        )
        self.assertSetEqual(
            {Bar},
            D.ORDER_AFTER
        )
        self.assertSetEqual(
            {Bar},
            B1.ORDER_AFTER
        )

    def test_inherit_dependencies_False(self):
        class Foo(metaclass=service.Meta):
            pass

        class Bar(metaclass=service.Meta):
            pass

        class A(metaclass=service.Meta):
            ORDER_BEFORE = [Foo]
            ORDER_AFTER = [Bar]

        class B(A, inherit_dependencies=False):
            ORDER_AFTER = [Foo]

        self.assertSetEqual(
            {A},
            Foo.ORDER_AFTER
        )
        self.assertSetEqual(
            {B},
            Foo.ORDER_BEFORE
        )
        self.assertSetEqual(
            {Foo, A, Bar},
            B.ORDER_AFTER
        )
        self.assertSetEqual(
            set(),
            B.ORDER_BEFORE
        )

    def test_support_pre_0_3_attributes_on_class(self):
        class Foo(metaclass=service.Meta):
            pass

        class Bar(metaclass=service.Meta):
            pass

        class A(metaclass=service.Meta):
            SERVICE_BEFORE = [Foo]
            SERVICE_AFTER = [Bar]

        class B(A, inherit_dependencies=False):
            SERVICE_AFTER = [Foo]

        self.assertSetEqual(
            {A},
            Foo.ORDER_AFTER
        )
        self.assertSetEqual(
            {B},
            Foo.ORDER_BEFORE
        )
        self.assertSetEqual(
            {Foo, A, Bar},
            B.ORDER_AFTER
        )
        self.assertSetEqual(
            set(),
            B.ORDER_BEFORE
        )

    def test_support_pre_0_3_attributes_on_read(self):
        class Foo(metaclass=service.Meta):
            pass

        self.assertIs(Foo.ORDER_BEFORE, Foo.SERVICE_BEFORE)
        self.assertIs(Foo.ORDER_AFTER, Foo.SERVICE_AFTER)

    def test_support_pre_0_3_attributes_raise_if_both_are_given(self):
        class Foo(metaclass=service.Meta):
            pass

        with self.assertRaisesRegex(ValueError, "mixes old and new"):
            class Bar(metaclass=service.Meta):
                ORDER_BEFORE = [Foo]
                SERVICE_BEFORE = [Foo]

        with self.assertRaisesRegex(ValueError, "mixes old and new"):
            class Bar(metaclass=service.Meta):
                ORDER_AFTER = [Foo]
                SERVICE_AFTER = [Foo]

        with self.assertRaisesRegex(ValueError, "mixes old and new"):
            class Bar(metaclass=service.Meta):
                ORDER_BEFORE = [Foo]
                SERVICE_AFTER = [Foo]

    def test_support_pre_0_3_attributes_with_deprecation_warning(self):
        class Foo(metaclass=service.Meta):
            pass

        with unittest.mock.patch("warnings.warn") as warn:
            class Bar(metaclass=service.Meta):
                SERVICE_BEFORE = [Foo]
            class Bar(metaclass=service.Meta):
                SERVICE_AFTER = [Foo]

        s = "SERVICE_BEFORE/AFTER used on class; use ORDER_BEFORE/AFTER"
        self.assertSequenceEqual(
            warn.mock_calls,
            [
                unittest.mock.call(s, DeprecationWarning),
                unittest.mock.call(s, DeprecationWarning),
            ]
        )


class TestService(unittest.TestCase):
    def test_is_Meta(self):
        self.assertIsInstance(
            service.Service,
            service.Meta
        )

    def test_automatic_logger(self):
        class Service(service.Service):
            pass

        s = Service(None)
        self.assertIsInstance(s.logger, logging.Logger)
        self.assertEqual(
            "tests.test_service.TestService"
            ".test_automatic_logger.<locals>.Service",
            s.logger.name
        )

    def test_custom_logger(self):
        l = logging.getLogger("foo")
        s = service.Service(None, logger_base=l)

        self.assertEqual(s.logger, l.getChild("service.Service"))

    def test_client(self):
        o = object()
        s = service.Service(o)
        self.assertIs(s.client, o)

        with self.assertRaises(AttributeError):
            s.client = o

    def test_shutdown(self):
        o = object()
        s = service.Service(o)

        def coro():
            return
            yield

        with unittest.mock.patch.object(s, "_shutdown") as _shutdown:
            _shutdown.return_value = coro()
            run_coroutine(s.shutdown())

        self.assertSequenceEqual(
            [
                unittest.mock.call(),
            ],
            _shutdown.mock_calls
        )
