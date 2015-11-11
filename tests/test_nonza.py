import unittest

import aioxmpp.errors as errors
import aioxmpp.nonza as nonza
import aioxmpp.xso as xso

from aioxmpp.utils import namespaces


class TestStreamError(unittest.TestCase):
    def test_declare_ns(self):
        self.assertDictEqual(
            nonza.StreamError.DECLARE_NS,
            {}
        )

    def test_from_exception(self):
        obj = nonza.StreamError.from_exception(errors.StreamError(
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
        obj = nonza.StreamError()
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
        obj = nonza.StreamError()
        self.assertEqual(
            (namespaces.streams, "undefined-condition"),
            obj.condition
        )
        self.assertIsNone(obj.text)

    def test_init(self):
        obj = nonza.StreamError(
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
            nonza.StreamFeatures.TAG
        )
        self.assertDictEqual(
            {
                None: namespaces.xmlstream,
            },
            nonza.StreamFeatures.DECLARE_NS
        )
        self.assertEqual(
            xso.UnknownChildPolicy.DROP,
            nonza.StreamFeatures.UNKNOWN_CHILD_POLICY
        )

    def test_as_feature_class_decorator(self):
        class FakeFeature(xso.XSO):
            TAG = ("uri:foo", "bar")

        self.assertNotIn(
            FakeFeature.TAG,
            nonza.StreamFeatures.CHILD_MAP
        )

        FakeFeature = nonza.StreamFeatures.as_feature_class(
            FakeFeature
        )

        self.assertTrue(issubclass(FakeFeature, xso.XSO))

        self.assertIn(
            FakeFeature.TAG,
            nonza.StreamFeatures.CHILD_MAP
        )
        self.assertEqual(
            nonza.StreamFeatures.features,
            nonza.StreamFeatures.CHILD_MAP[FakeFeature.TAG]
        )

    def test_is_feature(self):
        class FakeFeature(xso.XSO):
            TAG = ("uri:foo", "baz")

        self.assertFalse(nonza.StreamFeatures.is_feature(FakeFeature))

        nonza.StreamFeatures.as_feature_class(FakeFeature)

        self.assertTrue(nonza.StreamFeatures.is_feature(FakeFeature))

    def test__getitem__(self):
        class FakeFeature(xso.XSO):
            TAG = ("uri:foo", "foo")

        class NotAFeature(xso.XSO):
            TAG = ("uri:foo", "bar")

        instance = FakeFeature()

        features = nonza.StreamFeatures()
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

        features = nonza.StreamFeatures()
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

        features = nonza.StreamFeatures()
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

        features = nonza.StreamFeatures()
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

        features = nonza.StreamFeatures()
        features.features[FakeFeature.TAG].append(FakeFeature())

        self.assertTrue(features.has_feature(FakeFeature))
        self.assertFalse(features.has_feature(NotAFeature))

    def test_contains(self):
        features = nonza.StreamFeatures()
        with self.assertRaisesRegexp(TypeError,
                                     "membership test not supported"):
            "foo" in features

    def test_iter_features(self):
        class FakeFeatureA(xso.XSO):
            TAG = ("uri:foo", "foo")

        class FakeFeatureB(xso.XSO):
            TAG = ("uri:foo", "bar")

        instance1, instance2 = FakeFeatureA(), FakeFeatureB()

        features = nonza.StreamFeatures()
        features[...] = instance1
        features[...] = instance2

        self.assertSetEqual(
            {
                instance1,
                instance2
            },
            set(features)
        )


class TestStartTLSXSO(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            nonza.StartTLSXSO,
            xso.XSO
        ))

    def test_declare_ns(self):
        self.assertDictEqual(
            nonza.StartTLSXSO.DECLARE_NS,
            {
                None: namespaces.starttls
            }
        )


class TestStartTLSFeature(unittest.TestCase):
    def test_is_starttls_xso(self):
        self.assertTrue(issubclass(
            nonza.StartTLSFeature,
            nonza.StartTLSXSO
        ))

    def test_tag(self):
        self.assertEqual(
            nonza.StartTLSFeature.TAG,
            (namespaces.starttls, "starttls")
        )

    def test_required(self):
        self.assertIsInstance(
            nonza.StartTLSFeature.required,
            xso.Child
        )
        self.assertSetEqual(
            nonza.StartTLSFeature.required._classes,
            {nonza.StartTLSFeature.Required},
        )
        self.assertFalse(nonza.StartTLSFeature.required.required)

    def test_is_registered_stream_feature(self):
        self.assertTrue(nonza.StreamFeatures.is_feature(
            nonza.StartTLSFeature
        ))


class TestStartTLSFeature_Required(unittest.TestCase):
    def test_is_starttls_xso(self):
        self.assertTrue(issubclass(
            nonza.StartTLSFeature.Required,
            xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(
            nonza.StartTLSFeature.Required.TAG,
            (namespaces.starttls, "required")
        )


class TestStartTLS(unittest.TestCase):
    def test_is_starttls_xso(self):
        self.assertTrue(issubclass(
            nonza.StartTLS,
            nonza.StartTLSXSO
        ))

    def test_tag(self):
        self.assertEqual(
            nonza.StartTLS.TAG,
            (namespaces.starttls, "starttls")
        )


class TestStartTLSFailure(unittest.TestCase):
    def test_is_starttls_xso(self):
        self.assertTrue(issubclass(
            nonza.StartTLSFailure,
            nonza.StartTLSXSO
        ))

    def test_tag(self):
        self.assertEqual(
            nonza.StartTLSFailure.TAG,
            (namespaces.starttls, "failure")
        )


class TestStartTLSProceed(unittest.TestCase):
    def test_is_starttls_xso(self):
        self.assertTrue(issubclass(
            nonza.StartTLSProceed,
            nonza.StartTLSXSO
        ))

    def test_tag(self):
        self.assertEqual(
            nonza.StartTLSProceed.TAG,
            (namespaces.starttls, "proceed")
        )


class TestSASLXSO(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            nonza.SASLXSO,
            xso.XSO
        ))

    def test_declare_ns(self):
        self.assertDictEqual(
            nonza.SASLXSO.DECLARE_NS,
            {
                None: namespaces.sasl
            }
        )


class TestSASLAuth(unittest.TestCase):
    def test_is_sasl_xso(self):
        self.assertTrue(issubclass(
            nonza.SASLAuth,
            nonza.SASLXSO
        ))

    def test_tag(self):
        self.assertEqual(
            nonza.SASLAuth.TAG,
            (namespaces.sasl, "auth")
        )

    def test_mechanism(self):
        self.assertIsInstance(
            nonza.SASLAuth.mechanism,
            xso.Attr
        )
        self.assertIs(nonza.SASLAuth.mechanism.default,
                      xso.NO_DEFAULT)


    def test_payload(self):
        self.assertIsInstance(
            nonza.SASLAuth.payload,
            xso.Text
        )
        self.assertIsInstance(
            nonza.SASLAuth.payload.type_,
            xso.Base64Binary
        )
        self.assertIs(
            nonza.SASLAuth.payload.default,
            None
        )

    def test_init(self):
        auth = nonza.SASLAuth("foo")
        self.assertEqual(auth.mechanism, "foo")
        self.assertEqual(auth.payload, None)

        auth = nonza.SASLAuth(mechanism="foo",
                                    payload=b"foobar")
        self.assertEqual(auth.mechanism, "foo")
        self.assertEqual(auth.payload, b"foobar")


class TestSASLChallenge(unittest.TestCase):
    def test_is_sasl_xso(self):
        self.assertTrue(issubclass(
            nonza.SASLChallenge,
            nonza.SASLXSO
        ))

    def test_tag(self):
        self.assertEqual(
            nonza.SASLChallenge.TAG,
            (namespaces.sasl, "challenge")
        )

    def test_payload(self):
        self.assertIsInstance(
            nonza.SASLChallenge.payload,
            xso.Text
        )
        self.assertIsInstance(
            nonza.SASLChallenge.payload.type_,
            xso.Base64Binary
        )
        self.assertIs(
            nonza.SASLChallenge.payload.default,
            xso.NO_DEFAULT
        )

    def test_init(self):
        challenge = nonza.SASLChallenge(b"foo")
        self.assertEqual(challenge.payload, b"foo")

        challenge = nonza.SASLChallenge(payload=b"foo")
        self.assertEqual(challenge.payload, b"foo")

        with self.assertRaisesRegexp(TypeError, "positional argument"):
            nonza.SASLChallenge()


class TestSASLResponse(unittest.TestCase):
    def test_is_sasl_xso(self):
        self.assertTrue(issubclass(
            nonza.SASLResponse,
            nonza.SASLXSO
        ))

    def test_tag(self):
        self.assertEqual(
            nonza.SASLResponse.TAG,
            (namespaces.sasl, "response")
        )

    def test_payload(self):
        self.assertIsInstance(
            nonza.SASLResponse.payload,
            xso.Text
        )
        self.assertIsInstance(
            nonza.SASLResponse.payload.type_,
            xso.Base64Binary
        )
        self.assertIs(
            nonza.SASLResponse.payload.default,
            xso.NO_DEFAULT
        )

    def test_init(self):
        challenge = nonza.SASLResponse(b"foo")
        self.assertEqual(challenge.payload, b"foo")

        challenge = nonza.SASLResponse(payload=b"foo")
        self.assertEqual(challenge.payload, b"foo")

        with self.assertRaisesRegexp(TypeError, "positional argument"):
            nonza.SASLResponse()


class TestSASLFailure(unittest.TestCase):
    def test_is_sasl_xso(self):
        self.assertTrue(issubclass(
            nonza.SASLFailure,
            nonza.SASLXSO
        ))

    def test_tag(self):
        self.assertEqual(
            nonza.SASLFailure.TAG,
            (namespaces.sasl, "failure")
        )

    def test_condition(self):
        self.assertIsInstance(
            nonza.SASLFailure.condition,
            xso.ChildTag
        )
        self.assertIsInstance(
            nonza.SASLFailure.condition.validator,
            xso.RestrictToSet
        )
        self.assertSetEqual(
            nonza.SASLFailure.condition.validator.values,
            {
                (namespaces.sasl, key)
                for key in [
                        "aborted",
                        "account-disabled",
                        "credentials-expired",
                        "encryption-required",
                        "incorrect-encoding",
                        "invalid-authzid",
                        "invalid-mechanism",
                        "malformed-request",
                        "mechanism-too-weak",
                        "not-authorized",
                        "temporary-auth-failure",
                ]
            }
        )
        self.assertEqual(
            nonza.SASLFailure.condition.declare_prefix,
            None
        )
        self.assertIs(
            nonza.SASLFailure.condition.default,
            xso.NO_DEFAULT
        )

    def test_text(self):
        self.assertIsInstance(
            nonza.SASLFailure.text,
            xso.ChildText
        )
        self.assertEqual(
            nonza.SASLFailure.text.tag,
            (namespaces.sasl, "text")
        )
        self.assertEqual(
            nonza.SASLFailure.text.attr_policy,
            xso.UnknownAttrPolicy.DROP
        )
        self.assertIs(
            nonza.SASLFailure.text.default,
            None
        )
        self.assertIs(
            nonza.SASLFailure.text.declare_prefix,
            None
        )

    def test_init(self):
        fail = nonza.SASLFailure()
        self.assertEqual(
            fail.condition,
            (namespaces.sasl, "temporary-auth-failure")
        )

        fail = nonza.SASLFailure(
            condition=(namespaces.sasl, "invalid-authzid")
        )
        self.assertEqual(
            fail.condition,
            (namespaces.sasl, "invalid-authzid")
        )


class TestSASLSuccess(unittest.TestCase):
    def test_is_sasl_xso(self):
        self.assertTrue(issubclass(
            nonza.SASLSuccess,
            nonza.SASLXSO
        ))

    def test_tag(self):
        self.assertEqual(
            nonza.SASLSuccess.TAG,
            (namespaces.sasl, "success")
        )

    def test_payload(self):
        self.assertIsInstance(
            nonza.SASLSuccess.payload,
            xso.Text
        )
        self.assertIsInstance(
            nonza.SASLSuccess.payload.type_,
            xso.Base64Binary
        )
        self.assertIs(
            nonza.SASLSuccess.payload.default,
            None
        )


class TestSASLAbort(unittest.TestCase):
    def test_is_sasl_xso(self):
        self.assertTrue(issubclass(
            nonza.SASLAbort,
            nonza.SASLXSO
        ))

    def test_tag(self):
        self.assertEqual(
            nonza.SASLAbort.TAG,
            (namespaces.sasl, "abort")
        )



class TestSMXSO(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            nonza.SMXSO,
            xso.XSO
        ))

    def test_declare_ns(self):
        self.assertDictEqual(
            nonza.SMXSO.DECLARE_NS,
            {
                None: namespaces.stream_management
            }
        )


class TestStreamManagementFeature(unittest.TestCase):
    def test_is_sm_xso(self):
        self.assertTrue(issubclass(
            nonza.StreamManagementFeature,
            nonza.SMXSO
        ))

    def test_tag(self):
        self.assertEqual(
            nonza.StreamManagementFeature.TAG,
            (namespaces.stream_management, "sm")
        )

    def test_required(self):
        self.assertIsInstance(
            nonza.StreamManagementFeature.required,
            xso.Child
        )
        self.assertSetEqual(
            nonza.StreamManagementFeature.required._classes,
            {nonza.StreamManagementFeature.Required},
        )
        self.assertFalse(nonza.StreamManagementFeature.required.required)

    def test_optional(self):
        self.assertIsInstance(
            nonza.StreamManagementFeature.optional,
            xso.Child
        )
        self.assertSetEqual(
            nonza.StreamManagementFeature.optional._classes,
            {nonza.StreamManagementFeature.Optional},
        )
        self.assertFalse(nonza.StreamManagementFeature.optional.required)

    def test_is_registered_stream_feature(self):
        self.assertTrue(nonza.StreamFeatures.is_feature(
            nonza.StreamManagementFeature
        ))


class TestStreamManagementFeature_Required(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            nonza.StreamManagementFeature.Required,
            xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(
            nonza.StreamManagementFeature.Required.TAG,
            (namespaces.stream_management, "required")
        )


class TestStreamManagementFeature_Optional(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            nonza.StreamManagementFeature.Optional,
            xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(
            nonza.StreamManagementFeature.Optional.TAG,
            (namespaces.stream_management, "optional")
        )


class TestSMRequest(unittest.TestCase):
    def test_is_sm_xso(self):
        self.assertTrue(issubclass(
            nonza.SMRequest,
            nonza.SMXSO
        ))

    def test_tag(self):
        self.assertEqual(
            nonza.SMRequest.TAG,
            (namespaces.stream_management, "r")
        )


class TestSMAcknowledgement(unittest.TestCase):
    def test_is_sm_xso(self):
        self.assertTrue(issubclass(
            nonza.SMAcknowledgement,
            nonza.SMXSO
        ))

    def test_tag(self):
        self.assertEqual(
            nonza.SMAcknowledgement.TAG,
            (namespaces.stream_management, "a")
        )

    def test_default_init(self):
        obj = nonza.SMAcknowledgement()
        self.assertEqual(0, obj.counter)

    def test_init(self):
        obj = nonza.SMAcknowledgement(counter=1234)
        self.assertEqual(1234, obj.counter)


class TestSMEnable(unittest.TestCase):
    def test_is_sm_xso(self):
        self.assertTrue(issubclass(
            nonza.SMEnable,
            nonza.SMXSO
        ))

    def test_tag(self):
        self.assertEqual(
            nonza.SMEnable.TAG,
            (namespaces.stream_management, "enable")
        )

    def test_default_init(self):
        obj = nonza.SMEnable()
        self.assertFalse(obj.resume)

    def test_init(self):
        obj = nonza.SMEnable(resume=True)
        self.assertTrue(obj.resume)

    def test_resume(self):
        self.assertIsInstance(
            nonza.SMEnable.resume,
            xso.Attr
        )
        self.assertEqual(
            (None, "resume"),
            nonza.SMEnable.resume.tag
        )
        self.assertIsInstance(
            nonza.SMEnable.resume.type_,
            xso.Bool
        )
        self.assertIs(
            nonza.SMEnable.resume.default,
            False
        )


class TestSMEnabled(unittest.TestCase):
    def test_is_sm_xso(self):
        self.assertTrue(issubclass(
            nonza.SMEnabled,
            nonza.SMXSO
        ))

    def test_tag(self):
        self.assertEqual(
            nonza.SMEnabled.TAG,
            (namespaces.stream_management, "enabled")
        )

    def test_default_init(self):
        obj = nonza.SMEnabled()
        self.assertFalse(obj.resume)
        self.assertIsNone(obj.id_)
        self.assertIsNone(obj.location)
        self.assertIsNone(obj.max_)

    def test_init(self):
        obj = nonza.SMEnabled(
            resume=True,
            id_="foobar",
            location=("bar", 1234),
            max_=1023)
        self.assertTrue(obj.resume)
        self.assertEqual("foobar", obj.id_)
        self.assertEqual(("bar", 1234), obj.location)
        self.assertEqual(1023, obj.max_)

    def test_id(self):
        self.assertIsInstance(
            nonza.SMEnabled.id_,
            xso.Attr
        )
        self.assertEqual(
            (None, "id"),
            nonza.SMEnabled.id_.tag
        )
        self.assertIs(
            nonza.SMEnabled.id_.default,
            xso.NO_DEFAULT
        )

    def test_location(self):
        self.assertIsInstance(
            nonza.SMEnabled.location,
            xso.Attr
        )
        self.assertEqual(
            (None, "location"),
            nonza.SMEnabled.location.tag
        )
        self.assertIsInstance(
            nonza.SMEnabled.location.type_,
            xso.ConnectionLocation
        )
        self.assertIs(
            nonza.SMEnabled.location.default,
            None
        )

    def test_max(self):
        self.assertIsInstance(
            nonza.SMEnabled.max_,
            xso.Attr
        )
        self.assertEqual(
            (None, "max"),
            nonza.SMEnabled.max_.tag
        )
        self.assertIsInstance(
            nonza.SMEnabled.max_.type_,
            xso.Integer
        )
        self.assertIs(
            nonza.SMEnabled.max_.default,
            None
        )

    def test_resume(self):
        self.assertIsInstance(
            nonza.SMEnabled.resume,
            xso.Attr
        )
        self.assertEqual(
            (None, "resume"),
            nonza.SMEnabled.resume.tag
        )
        self.assertIsInstance(
            nonza.SMEnabled.resume.type_,
            xso.Bool
        )
        self.assertIs(
            nonza.SMEnabled.resume.default,
            False
        )


class TestSMResume(unittest.TestCase):
    def test_is_sm_xso(self):
        self.assertTrue(issubclass(
            nonza.SMResume,
            nonza.SMXSO
        ))

    def test_tag(self):
        self.assertEqual(
            nonza.SMResume.TAG,
            (namespaces.stream_management, "resume")
        )

    def test_default_init_not_possible(self):
        with self.assertRaises(TypeError):
            nonza.SMResume()

    def test_init(self):
        obj = nonza.SMResume(
            counter=1,
            previd="foobar")
        self.assertEqual(1, obj.counter)
        self.assertEqual("foobar", obj.previd)

    def test_resume(self):
        self.assertIsInstance(
            nonza.SMResume.counter,
            xso.Attr
        )
        self.assertEqual(
            (None, "h"),
            nonza.SMResume.counter.tag
        )
        self.assertIsInstance(
            nonza.SMResume.counter.type_,
            xso.Integer
        )

    def test_previd(self):
        self.assertIsInstance(
            nonza.SMResume.previd,
            xso.Attr
        )
        self.assertEqual(
            (None, "previd"),
            nonza.SMResume.previd.tag
        )


class TestSMResumed(unittest.TestCase):
    def test_is_sm_xso(self):
        self.assertTrue(issubclass(
            nonza.SMResumed,
            nonza.SMXSO
        ))

    def test_tag(self):
        self.assertEqual(
            nonza.SMResumed.TAG,
            (namespaces.stream_management, "resumed")
        )

    def test_default_init(self):
        with self.assertRaises(TypeError):
            nonza.SMResumed()

    def test_init(self):
        obj = nonza.SMResumed(
            counter=1,
            previd="foobar")
        self.assertEqual(1, obj.counter)
        self.assertEqual("foobar", obj.previd)

    def test_resume(self):
        self.assertIsInstance(
            nonza.SMResumed.counter,
            xso.Attr
        )
        self.assertEqual(
            (None, "h"),
            nonza.SMResumed.counter.tag
        )
        self.assertIsInstance(
            nonza.SMResumed.counter.type_,
            xso.Integer
        )

    def test_previd(self):
        self.assertIsInstance(
            nonza.SMResumed.previd,
            xso.Attr
        )
        self.assertEqual(
            (None, "previd"),
            nonza.SMResumed.previd.tag
        )


class TestSMFailed(unittest.TestCase):
    def test_is_sm_xso(self):
        self.assertTrue(issubclass(
            nonza.SMFailed,
            nonza.SMXSO
        ))

    def test_tag(self):
        self.assertEqual(
            nonza.SMFailed.TAG,
            (namespaces.stream_management, "failed")
        )

    def test_default_init(self):
        obj = nonza.SMFailed()
        self.assertEqual(
            (namespaces.stanzas, "undefined-condition"),
            obj.condition
        )

    def test_init(self):
        obj = nonza.SMFailed(
            condition=(namespaces.stanzas, "item-not-found")
        )
        self.assertEqual(
            (namespaces.stanzas, "item-not-found"),
            obj.condition
        )
