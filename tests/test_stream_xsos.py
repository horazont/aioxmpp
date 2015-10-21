import unittest

import aioxmpp.errors as errors
import aioxmpp.stream_xsos as stream_xsos
import aioxmpp.xso as xso

from aioxmpp.utils import namespaces


class TestStreamError(unittest.TestCase):
    def test_from_exception(self):
        obj = stream_xsos.StreamError.from_exception(errors.StreamError(
            (namespaces.streams, "undefined-condition"),
            text="foobar"))
        self.assertEqual(
            (namespaces.streams, "undefined-condition"),
            obj.condition
        )
        self.assertEqual(
            "foobar",
            obj.text
        )

    def test_to_exception(self):
        obj = stream_xsos.StreamError()
        obj.condition = (namespaces.streams, "restricted-xml")
        obj.text = "foobar"

        exc = obj.to_exception()
        self.assertIsInstance(
            exc,
            errors.StreamError)
        self.assertEqual(
            (namespaces.streams, "restricted-xml"),
            exc.condition
        )
        self.assertEqual(
            "foobar",
            exc.text
        )

    def test_default_init(self):
        obj = stream_xsos.StreamError()
        self.assertEqual(
            (namespaces.streams, "undefined-condition"),
            obj.condition
        )
        self.assertIsNone(obj.text)

    def test_init(self):
        obj = stream_xsos.StreamError(
            condition=(namespaces.streams, "reset"),
            text="foobar"
        )
        self.assertEqual(
            (namespaces.streams, "reset"),
            obj.condition
        )
        self.assertEqual(
            "foobar",
            obj.text
        )


class TestStreamFeatures(unittest.TestCase):
    def test_setup(self):
        self.assertEqual(
            (namespaces.xmlstream, "features"),
            stream_xsos.StreamFeatures.TAG
        )
        self.assertDictEqual(
            {
                None: namespaces.xmlstream,
            },
            stream_xsos.StreamFeatures.DECLARE_NS
        )
        self.assertEqual(
            xso.UnknownChildPolicy.DROP,
            stream_xsos.StreamFeatures.UNKNOWN_CHILD_POLICY
        )

    def test_as_feature_class_decorator(self):
        @stream_xsos.StreamFeatures.as_feature_class
        class FakeFeature(xso.XSO):
            TAG = ("uri:foo", "bar")

        self.assertTrue(issubclass(FakeFeature, xso.XSO))

        self.assertIn(
            FakeFeature.TAG,
            stream_xsos.StreamFeatures.CHILD_MAP
        )
        self.assertEqual(
            stream_xsos.StreamFeatures.features,
            stream_xsos.StreamFeatures.CHILD_MAP[FakeFeature.TAG]
        )

    def test__getitem__(self):
        class FakeFeature(xso.XSO):
            TAG = ("uri:foo", "foo")

        class NotAFeature(xso.XSO):
            TAG = ("uri:foo", "bar")

        instance = FakeFeature()

        features = stream_xsos.StreamFeatures()
        features.features[FakeFeature.TAG].append(instance)

        self.assertIs(
            instance,
            features[FakeFeature]
        )

        with self.assertRaises(KeyError) as ctx:
            features[NotAFeature]

        self.assertEqual(
            (NotAFeature,),
            ctx.exception.args
        )
        self.assertIsNone(ctx.exception.__cause__)
        self.assertTrue(ctx.exception.__suppress_context__)

    def test___delitem__(self):
        class FakeFeature(xso.XSO):
            TAG = ("uri:foo", "foo")

        instance = FakeFeature()

        features = stream_xsos.StreamFeatures()
        features.features[FakeFeature.TAG].append(instance)

        del features[FakeFeature]

        with self.assertRaises(KeyError):
            features[FakeFeature]

        with self.assertRaises(KeyError):
            del features[FakeFeature]

    def test___setitem__(self):
        class FakeFeature(xso.XSO):
            TAG = ("uri:foo", "foo")

        class NotAFeature(xso.XSO):
            TAG = ("uri:foo", "foo")  # using the same tag here!

        instance = FakeFeature()

        features = stream_xsos.StreamFeatures()
        features[...] = instance

        self.assertIs(
            instance,
            features[FakeFeature]
        )

        with self.assertRaisesRegexp(ValueError, "incorrect XSO class"):
            features[NotAFeature] = instance

        del features[FakeFeature]


    def test_get_feature(self):
        class FakeFeature(xso.XSO):
            TAG = ("uri:foo", "foo")

        class NotAFeature(xso.XSO):
            TAG = ("uri:foo", "bar")

        instance = FakeFeature()

        default = object()

        features = stream_xsos.StreamFeatures()
        features.features[FakeFeature.TAG].append(instance)

        self.assertIs(instance, features.get_feature(FakeFeature))
        self.assertIsNone(features.get_feature(NotAFeature))
        self.assertIs(
            default,
            features.get_feature(NotAFeature, default=default)
        )

    def test_has_feature(self):
        class FakeFeature(xso.XSO):
            TAG = ("uri:foo", "foo")

        class NotAFeature(xso.XSO):
            TAG = ("uri:foo", "bar")

        features = stream_xsos.StreamFeatures()
        features.features[FakeFeature.TAG].append(FakeFeature())

        self.assertTrue(features.has_feature(FakeFeature))
        self.assertFalse(features.has_feature(NotAFeature))

    def test_contains(self):
        features = stream_xsos.StreamFeatures()
        with self.assertRaisesRegexp(TypeError,
                                     "membership test not supported"):
            "foo" in features

    def test_iter_features(self):
        class FakeFeatureA(xso.XSO):
            TAG = ("uri:foo", "foo")

        class FakeFeatureB(xso.XSO):
            TAG = ("uri:foo", "bar")

        instance1, instance2 = FakeFeatureA(), FakeFeatureB()

        features = stream_xsos.StreamFeatures()
        features[...] = instance1
        features[...] = instance2

        self.assertSetEqual(
            {
                instance1,
                instance2
            },
            set(features)
        )


class TestSMAcknowledgement(unittest.TestCase):
    def test_default_init(self):
        obj = stream_xsos.SMAcknowledgement()
        self.assertEqual(0, obj.counter)

    def test_init(self):
        obj = stream_xsos.SMAcknowledgement(counter=1234)
        self.assertEqual(1234, obj.counter)


class TestSMEnable(unittest.TestCase):
    def test_default_init(self):
        obj = stream_xsos.SMEnable()
        self.assertFalse(obj.resume)

    def test_init(self):
        obj = stream_xsos.SMEnable(resume=True)
        self.assertTrue(obj.resume)


class TestSMEnabled(unittest.TestCase):
    def test_default_init(self):
        obj = stream_xsos.SMEnabled()
        self.assertFalse(obj.resume)
        self.assertIsNone(obj.id_)
        self.assertIsNone(obj.location)
        self.assertIsNone(obj.max_)

    def test_init(self):
        obj = stream_xsos.SMEnabled(
            resume=True,
            id_="foobar",
            location=("bar", 1234),
            max_=1023)
        self.assertTrue(obj.resume)
        self.assertEqual("foobar", obj.id_)
        self.assertEqual(("bar", 1234), obj.location)
        self.assertEqual(1023, obj.max_)


class TestSMResume(unittest.TestCase):
    def test_default_init_not_possible(self):
        with self.assertRaises(TypeError):
            stream_xsos.SMResume()

    def test_init(self):
        obj = stream_xsos.SMResume(
            counter=1,
            previd="foobar")
        self.assertEqual(1, obj.counter)
        self.assertEqual("foobar", obj.previd)


class TestSMResumed(unittest.TestCase):
    def test_default_init(self):
        with self.assertRaises(TypeError):
            stream_xsos.SMResumed()

    def test_init(self):
        obj = stream_xsos.SMResumed(
            counter=1,
            previd="foobar")
        self.assertEqual(1, obj.counter)
        self.assertEqual("foobar", obj.previd)


class TestSMFailed(unittest.TestCase):
    def test_default_init(self):
        obj = stream_xsos.SMFailed()
        self.assertEqual(
            (namespaces.stanzas, "undefined-condition"),
            obj.condition
        )

    def test_init(self):
        obj = stream_xsos.SMFailed(
            condition=(namespaces.stanzas, "item-not-found")
        )
        self.assertEqual(
            (namespaces.stanzas, "item-not-found"),
            obj.condition
        )
