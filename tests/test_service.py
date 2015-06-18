import abc
import itertools
import logging
import unittest

import aioxmpp.service as service

from .testutils import run_coroutine


class TestServiceMeta(unittest.TestCase):
    def test_inherits_from_ABCMeta(self):
        self.assertTrue(issubclass(service.Meta, abc.ABCMeta))

    def test_ordering_attributes(self):
        class Foo(metaclass=service.Meta):
            pass

        self.assertSetEqual(
            set(),
            Foo.SERVICE_BEFORE
        )
        self.assertSetEqual(
            set(),
            Foo.SERVICE_AFTER
        )

    def test_configure_ordering(self):
        class Foo(metaclass=service.Meta):
            pass

        class Bar(metaclass=service.Meta):
            SERVICE_BEFORE = [Foo]

        self.assertSetEqual(
            {Foo},
            Bar.SERVICE_BEFORE
        )
        self.assertSetEqual(
            set(),
            Bar.SERVICE_AFTER
        )
        self.assertSetEqual(
            {Bar},
            Foo.SERVICE_AFTER
        )
        self.assertSetEqual(
            set(),
            Foo.SERVICE_BEFORE
        )

    def test_transitive_before_ordering(self):
        class Foo(metaclass=service.Meta):
            pass

        class Bar(metaclass=service.Meta):
            SERVICE_BEFORE = [Foo]

        class Baz(metaclass=service.Meta):
            SERVICE_BEFORE = [Bar]

        self.assertSetEqual(
            {Foo},
            Bar.SERVICE_BEFORE
        )
        self.assertSetEqual(
            {Foo, Bar},
            Baz.SERVICE_BEFORE
        )
        self.assertSetEqual(
            {Bar, Baz},
            Foo.SERVICE_AFTER
        )
        self.assertSetEqual(
            {Baz},
            Bar.SERVICE_AFTER
        )
        self.assertSetEqual(
            set(),
            Foo.SERVICE_BEFORE
        )
        self.assertSetEqual(
            set(),
            Baz.SERVICE_AFTER
        )

    def test_transitive_after_ordering(self):
        class Foo(metaclass=service.Meta):
            pass

        class Bar(metaclass=service.Meta):
            SERVICE_AFTER = [Foo]

        class Baz(metaclass=service.Meta):
            SERVICE_AFTER = [Bar]

        self.assertSetEqual(
            {Foo},
            Bar.SERVICE_AFTER
        )
        self.assertSetEqual(
            {Foo, Bar},
            Baz.SERVICE_AFTER
        )
        self.assertSetEqual(
            {Bar, Baz},
            Foo.SERVICE_BEFORE
        )
        self.assertSetEqual(
            {Baz},
            Bar.SERVICE_BEFORE
        )
        self.assertSetEqual(
            set(),
            Foo.SERVICE_AFTER
        )
        self.assertSetEqual(
            set(),
            Baz.SERVICE_BEFORE
        )

    def test_loop_detect(self):
        class Foo(metaclass=service.Meta):
            pass

        class Bar(metaclass=service.Meta):
            SERVICE_AFTER = [Foo]

        with self.assertRaisesRegexp(
                ValueError,
                "dependency loop: Fnord loops through .*\.(Foo|Bar)"):

            class Fnord(metaclass=service.Meta):
                SERVICE_BEFORE = [Foo]
                SERVICE_AFTER = [Bar]

            print(Fnord.SERVICE_BEFORE)
            print(Fnord.SERVICE_AFTER)

    def test_partial_dependency_ordering_puts_earliest_first(self):
        class Foo(metaclass=service.Meta):
            pass

        class Bar(metaclass=service.Meta):
            SERVICE_BEFORE = [Foo]

        class Baz(metaclass=service.Meta):
            SERVICE_BEFORE = [Bar]

        class Fourth(metaclass=service.Meta):
            SERVICE_BEFORE = [Bar]

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
            SERVICE_BEFORE = [Foo]
            SERVICE_AFTER = [Bar]

        class B(A):
            pass

        self.assertSetEqual(A.SERVICE_BEFORE, B.SERVICE_BEFORE)
        self.assertSetEqual(A.SERVICE_AFTER, B.SERVICE_AFTER)

        self.assertIsNot(A.SERVICE_BEFORE, B.SERVICE_BEFORE)
        self.assertIsNot(A.SERVICE_AFTER, B.SERVICE_AFTER)

    def test_inheritance_ignores_non_service_classes(self):
        class Foo(metaclass=service.Meta):
            pass

        class Bar:
            SERVICE_BEFORE = [Foo]

        class Baz(Bar, metaclass=service.Meta):
            pass

        self.assertSetEqual(set(), Baz.SERVICE_BEFORE)

    def test_diamond_inheritance(self):
        class Foo(metaclass=service.Meta):
            pass

        class Bar(metaclass=service.Meta):
            pass

        class Baz(metaclass=service.Meta):
            pass

        class A(metaclass=service.Meta):
            SERVICE_BEFORE = [Foo]

        class B1(A):
            SERVICE_AFTER = [Bar]

        class B2(A):
            SERVICE_BEFORE = [Baz]

        class D(B1, B2):
            pass

        self.assertSetEqual(
            {A, B1, B2, D},
            Foo.SERVICE_AFTER
        )
        self.assertSetEqual(
            {B1, D},
            Bar.SERVICE_BEFORE
        )
        self.assertSetEqual(
            {B2, D},
            Baz.SERVICE_AFTER
        )
        self.assertSetEqual(
            {Foo, Baz},
            D.SERVICE_BEFORE
        )
        self.assertSetEqual(
            {Foo, Baz},
            B2.SERVICE_BEFORE
        )
        self.assertSetEqual(
            {Bar},
            D.SERVICE_AFTER
        )
        self.assertSetEqual(
            {Bar},
            B1.SERVICE_AFTER
        )

    def test_inherit_dependencies_False(self):
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
            Foo.SERVICE_AFTER
        )
        self.assertSetEqual(
            {B},
            Foo.SERVICE_BEFORE
        )
        self.assertSetEqual(
            {Foo, A, Bar},
            B.SERVICE_AFTER
        )
        self.assertSetEqual(
            set(),
            B.SERVICE_BEFORE
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
        s = service.Service(None, logger=l)
        self.assertIs(s.logger, l)

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
