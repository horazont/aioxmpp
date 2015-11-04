import unittest

import aioxmpp.errors as errors
import aioxmpp.stream_xsos as stream_xsos
import aioxmpp.xso as xso

from aioxmpp.utils import namespaces


class TestStreamError(unittest.TestCase):
    def test_declare_ns(self):
        self.assertDictEqual(
            stream_xsos.StreamError.DECLARE_NS,
            {}
        )

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
        class FakeFeature(xso.XSO):
            TAG = ("uri:foo", "bar")

        self.assertNotIn(
            FakeFeature.TAG,
            stream_xsos.StreamFeatures.CHILD_MAP
        )

        FakeFeature = stream_xsos.StreamFeatures.as_feature_class(
            FakeFeature
        )

        self.assertTrue(issubclass(FakeFeature, xso.XSO))

        self.assertIn(
            FakeFeature.TAG,
            stream_xsos.StreamFeatures.CHILD_MAP
        )
        self.assertEqual(
            stream_xsos.StreamFeatures.features,
            stream_xsos.StreamFeatures.CHILD_MAP[FakeFeature.TAG]
        )

    def test_is_feature(self):
        class FakeFeature(xso.XSO):
            TAG = ("uri:foo", "baz")

        self.assertFalse(stream_xsos.StreamFeatures.is_feature(FakeFeature))

        stream_xsos.StreamFeatures.as_feature_class(FakeFeature)

        self.assertTrue(stream_xsos.StreamFeatures.is_feature(FakeFeature))

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


class TestStartTLSXSO(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            stream_xsos.StartTLSXSO,
            xso.XSO
        ))

    def test_declare_ns(self):
        self.assertDictEqual(
            stream_xsos.StartTLSXSO.DECLARE_NS,
            {
                None: namespaces.starttls
            }
        )


class TestStartTLSFeature(unittest.TestCase):
    def test_is_starttls_xso(self):
        self.assertTrue(issubclass(
            stream_xsos.StartTLSFeature,
            stream_xsos.StartTLSXSO
        ))

    def test_tag(self):
        self.assertEqual(
            stream_xsos.StartTLSFeature.TAG,
            (namespaces.starttls, "starttls")
        )

    def test_required(self):
        self.assertIsInstance(
            stream_xsos.StartTLSFeature.required,
            xso.Child
        )
        self.assertSetEqual(
            stream_xsos.StartTLSFeature.required._classes,
            {stream_xsos.StartTLSFeature.Required},
        )
        self.assertFalse(stream_xsos.StartTLSFeature.required.required)

    def test_is_registered_stream_feature(self):
        self.assertTrue(stream_xsos.StreamFeatures.is_feature(
            stream_xsos.StartTLSFeature
        ))


class TestStartTLSFeature_Required(unittest.TestCase):
    def test_is_starttls_xso(self):
        self.assertTrue(issubclass(
            stream_xsos.StartTLSFeature.Required,
            xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(
            stream_xsos.StartTLSFeature.Required.TAG,
            (namespaces.starttls, "required")
        )


class TestStartTLS(unittest.TestCase):
    def test_is_starttls_xso(self):
        self.assertTrue(issubclass(
            stream_xsos.StartTLS,
            stream_xsos.StartTLSXSO
        ))

    def test_tag(self):
        self.assertEqual(
            stream_xsos.StartTLS.TAG,
            (namespaces.starttls, "starttls")
        )


class TestStartTLSFailure(unittest.TestCase):
    def test_is_starttls_xso(self):
        self.assertTrue(issubclass(
            stream_xsos.StartTLSFailure,
            stream_xsos.StartTLSXSO
        ))

    def test_tag(self):
        self.assertEqual(
            stream_xsos.StartTLSFailure.TAG,
            (namespaces.starttls, "failure")
        )


class TestStartTLSProceed(unittest.TestCase):
    def test_is_starttls_xso(self):
        self.assertTrue(issubclass(
            stream_xsos.StartTLSProceed,
            stream_xsos.StartTLSXSO
        ))

    def test_tag(self):
        self.assertEqual(
            stream_xsos.StartTLSProceed.TAG,
            (namespaces.starttls, "proceed")
        )


class TestSASLXSO(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            stream_xsos.SASLXSO,
            xso.XSO
        ))

    def test_declare_ns(self):
        self.assertDictEqual(
            stream_xsos.SASLXSO.DECLARE_NS,
            {
                None: namespaces.sasl
            }
        )


class TestSASLAuth(unittest.TestCase):
    def test_is_sasl_xso(self):
        self.assertTrue(issubclass(
            stream_xsos.SASLAuth,
            stream_xsos.SASLXSO
        ))

    def test_tag(self):
        self.assertEqual(
            stream_xsos.SASLAuth.TAG,
            (namespaces.sasl, "auth")
        )

    def test_mechanism(self):
        self.assertIsInstance(
            stream_xsos.SASLAuth.mechanism,
            xso.Attr
        )
        self.assertIs(stream_xsos.SASLAuth.mechanism.default,
                      xso.NO_DEFAULT)


    def test_payload(self):
        self.assertIsInstance(
            stream_xsos.SASLAuth.payload,
            xso.Text
        )
        self.assertIsInstance(
            stream_xsos.SASLAuth.payload.type_,
            xso.Base64Binary
        )
        self.assertIs(
            stream_xsos.SASLAuth.payload.default,
            None
        )

    def test_init(self):
        auth = stream_xsos.SASLAuth("foo")
        self.assertEqual(auth.mechanism, "foo")
        self.assertEqual(auth.payload, None)

        auth = stream_xsos.SASLAuth(mechanism="foo",
                                    payload=b"foobar")
        self.assertEqual(auth.mechanism, "foo")
        self.assertEqual(auth.payload, b"foobar")


class TestSASLChallenge(unittest.TestCase):
    def test_is_sasl_xso(self):
        self.assertTrue(issubclass(
            stream_xsos.SASLChallenge,
            stream_xsos.SASLXSO
        ))

    def test_tag(self):
        self.assertEqual(
            stream_xsos.SASLChallenge.TAG,
            (namespaces.sasl, "challenge")
        )

    def test_payload(self):
        self.assertIsInstance(
            stream_xsos.SASLChallenge.payload,
            xso.Text
        )
        self.assertIsInstance(
            stream_xsos.SASLChallenge.payload.type_,
            xso.Base64Binary
        )
        self.assertIs(
            stream_xsos.SASLChallenge.payload.default,
            xso.NO_DEFAULT
        )

    def test_init(self):
        challenge = stream_xsos.SASLChallenge(b"foo")
        self.assertEqual(challenge.payload, b"foo")

        challenge = stream_xsos.SASLChallenge(payload=b"foo")
        self.assertEqual(challenge.payload, b"foo")

        with self.assertRaisesRegexp(TypeError, "positional argument"):
            stream_xsos.SASLChallenge()


class TestSASLResponse(unittest.TestCase):
    def test_is_sasl_xso(self):
        self.assertTrue(issubclass(
            stream_xsos.SASLResponse,
            stream_xsos.SASLXSO
        ))

    def test_tag(self):
        self.assertEqual(
            stream_xsos.SASLResponse.TAG,
            (namespaces.sasl, "response")
        )

    def test_payload(self):
        self.assertIsInstance(
            stream_xsos.SASLResponse.payload,
            xso.Text
        )
        self.assertIsInstance(
            stream_xsos.SASLResponse.payload.type_,
            xso.Base64Binary
        )
        self.assertIs(
            stream_xsos.SASLResponse.payload.default,
            xso.NO_DEFAULT
        )

    def test_init(self):
        challenge = stream_xsos.SASLResponse(b"foo")
        self.assertEqual(challenge.payload, b"foo")

        challenge = stream_xsos.SASLResponse(payload=b"foo")
        self.assertEqual(challenge.payload, b"foo")

        with self.assertRaisesRegexp(TypeError, "positional argument"):
            stream_xsos.SASLResponse()


class TestSASLFailure(unittest.TestCase):
    def test_is_sasl_xso(self):
        self.assertTrue(issubclass(
            stream_xsos.SASLFailure,
            stream_xsos.SASLXSO
        ))

    def test_tag(self):
        self.assertEqual(
            stream_xsos.SASLFailure.TAG,
            (namespaces.sasl, "failure")
        )

    def test_condition(self):
        self.assertIsInstance(
            stream_xsos.SASLFailure.condition,
            xso.ChildTag
        )
        self.assertIsInstance(
            stream_xsos.SASLFailure.condition.validator,
            xso.RestrictToSet
        )
        self.assertSetEqual(
            stream_xsos.SASLFailure.condition.validator.values,
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
            stream_xsos.SASLFailure.condition.declare_prefix,
            None
        )
        self.assertIs(
            stream_xsos.SASLFailure.condition.default,
            xso.NO_DEFAULT
        )

    def test_text(self):
        self.assertIsInstance(
            stream_xsos.SASLFailure.text,
            xso.ChildText
        )
        self.assertEqual(
            stream_xsos.SASLFailure.text.tag,
            (namespaces.sasl, "text")
        )
        self.assertEqual(
            stream_xsos.SASLFailure.text.attr_policy,
            xso.UnknownAttrPolicy.DROP
        )
        self.assertIs(
            stream_xsos.SASLFailure.text.default,
            None
        )
        self.assertIs(
            stream_xsos.SASLFailure.text.declare_prefix,
            None
        )

    def test_init(self):
        fail = stream_xsos.SASLFailure()
        self.assertEqual(
            fail.condition,
            (namespaces.sasl, "temporary-auth-failure")
        )

        fail = stream_xsos.SASLFailure(
            condition=(namespaces.sasl, "invalid-authzid")
        )
        self.assertEqual(
            fail.condition,
            (namespaces.sasl, "invalid-authzid")
        )


class TestSASLSuccess(unittest.TestCase):
    def test_is_sasl_xso(self):
        self.assertTrue(issubclass(
            stream_xsos.SASLSuccess,
            stream_xsos.SASLXSO
        ))

    def test_tag(self):
        self.assertEqual(
            stream_xsos.SASLSuccess.TAG,
            (namespaces.sasl, "success")
        )

    def test_payload(self):
        self.assertIsInstance(
            stream_xsos.SASLSuccess.payload,
            xso.Text
        )
        self.assertIsInstance(
            stream_xsos.SASLSuccess.payload.type_,
            xso.Base64Binary
        )
        self.assertIs(
            stream_xsos.SASLSuccess.payload.default,
            None
        )


class TestSASLAbort(unittest.TestCase):
    def test_is_sasl_xso(self):
        self.assertTrue(issubclass(
            stream_xsos.SASLAbort,
            stream_xsos.SASLXSO
        ))

    def test_tag(self):
        self.assertEqual(
            stream_xsos.SASLAbort.TAG,
            (namespaces.sasl, "abort")
        )



class TestSMXSO(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            stream_xsos.SMXSO,
            xso.XSO
        ))

    def test_declare_ns(self):
        self.assertDictEqual(
            stream_xsos.SMXSO.DECLARE_NS,
            {
                None: namespaces.stream_management
            }
        )


class TestStreamManagementFeature(unittest.TestCase):
    def test_is_sm_xso(self):
        self.assertTrue(issubclass(
            stream_xsos.StreamManagementFeature,
            stream_xsos.SMXSO
        ))

    def test_tag(self):
        self.assertEqual(
            stream_xsos.StreamManagementFeature.TAG,
            (namespaces.stream_management, "sm")
        )

    def test_required(self):
        self.assertIsInstance(
            stream_xsos.StreamManagementFeature.required,
            xso.Child
        )
        self.assertSetEqual(
            stream_xsos.StreamManagementFeature.required._classes,
            {stream_xsos.StreamManagementFeature.Required},
        )
        self.assertFalse(stream_xsos.StreamManagementFeature.required.required)

    def test_optional(self):
        self.assertIsInstance(
            stream_xsos.StreamManagementFeature.optional,
            xso.Child
        )
        self.assertSetEqual(
            stream_xsos.StreamManagementFeature.optional._classes,
            {stream_xsos.StreamManagementFeature.Optional},
        )
        self.assertFalse(stream_xsos.StreamManagementFeature.optional.required)

    def test_is_registered_stream_feature(self):
        self.assertTrue(stream_xsos.StreamFeatures.is_feature(
            stream_xsos.StreamManagementFeature
        ))


class TestStreamManagementFeature_Required(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            stream_xsos.StreamManagementFeature.Required,
            xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(
            stream_xsos.StreamManagementFeature.Required.TAG,
            (namespaces.stream_management, "required")
        )


class TestStreamManagementFeature_Optional(unittest.TestCase):
    def test_is_xso(self):
        self.assertTrue(issubclass(
            stream_xsos.StreamManagementFeature.Optional,
            xso.XSO,
        ))

    def test_tag(self):
        self.assertEqual(
            stream_xsos.StreamManagementFeature.Optional.TAG,
            (namespaces.stream_management, "optional")
        )


class TestSMRequest(unittest.TestCase):
    def test_is_sm_xso(self):
        self.assertTrue(issubclass(
            stream_xsos.SMRequest,
            stream_xsos.SMXSO
        ))

    def test_tag(self):
        self.assertEqual(
            stream_xsos.SMRequest.TAG,
            (namespaces.stream_management, "r")
        )


class TestSMAcknowledgement(unittest.TestCase):
    def test_is_sm_xso(self):
        self.assertTrue(issubclass(
            stream_xsos.SMAcknowledgement,
            stream_xsos.SMXSO
        ))

    def test_tag(self):
        self.assertEqual(
            stream_xsos.SMAcknowledgement.TAG,
            (namespaces.stream_management, "a")
        )

    def test_default_init(self):
        obj = stream_xsos.SMAcknowledgement()
        self.assertEqual(0, obj.counter)

    def test_init(self):
        obj = stream_xsos.SMAcknowledgement(counter=1234)
        self.assertEqual(1234, obj.counter)


class TestSMEnable(unittest.TestCase):
    def test_is_sm_xso(self):
        self.assertTrue(issubclass(
            stream_xsos.SMEnable,
            stream_xsos.SMXSO
        ))

    def test_tag(self):
        self.assertEqual(
            stream_xsos.SMEnable.TAG,
            (namespaces.stream_management, "enable")
        )

    def test_default_init(self):
        obj = stream_xsos.SMEnable()
        self.assertFalse(obj.resume)

    def test_init(self):
        obj = stream_xsos.SMEnable(resume=True)
        self.assertTrue(obj.resume)

    def test_resume(self):
        self.assertIsInstance(
            stream_xsos.SMEnable.resume,
            xso.Attr
        )
        self.assertEqual(
            (None, "resume"),
            stream_xsos.SMEnable.resume.tag
        )
        self.assertIsInstance(
            stream_xsos.SMEnable.resume.type_,
            xso.Bool
        )
        self.assertIs(
            stream_xsos.SMEnable.resume.default,
            False
        )


class TestSMEnabled(unittest.TestCase):
    def test_is_sm_xso(self):
        self.assertTrue(issubclass(
            stream_xsos.SMEnabled,
            stream_xsos.SMXSO
        ))

    def test_tag(self):
        self.assertEqual(
            stream_xsos.SMEnabled.TAG,
            (namespaces.stream_management, "enabled")
        )

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

    def test_id(self):
        self.assertIsInstance(
            stream_xsos.SMEnabled.id_,
            xso.Attr
        )
        self.assertEqual(
            (None, "id"),
            stream_xsos.SMEnabled.id_.tag
        )
        self.assertIs(
            stream_xsos.SMEnabled.id_.default,
            xso.NO_DEFAULT
        )

    def test_location(self):
        self.assertIsInstance(
            stream_xsos.SMEnabled.location,
            xso.Attr
        )
        self.assertEqual(
            (None, "location"),
            stream_xsos.SMEnabled.location.tag
        )
        self.assertIsInstance(
            stream_xsos.SMEnabled.location.type_,
            xso.ConnectionLocation
        )
        self.assertIs(
            stream_xsos.SMEnabled.location.default,
            None
        )

    def test_max(self):
        self.assertIsInstance(
            stream_xsos.SMEnabled.max_,
            xso.Attr
        )
        self.assertEqual(
            (None, "max"),
            stream_xsos.SMEnabled.max_.tag
        )
        self.assertIsInstance(
            stream_xsos.SMEnabled.max_.type_,
            xso.Integer
        )
        self.assertIs(
            stream_xsos.SMEnabled.max_.default,
            None
        )

    def test_resume(self):
        self.assertIsInstance(
            stream_xsos.SMEnabled.resume,
            xso.Attr
        )
        self.assertEqual(
            (None, "resume"),
            stream_xsos.SMEnabled.resume.tag
        )
        self.assertIsInstance(
            stream_xsos.SMEnabled.resume.type_,
            xso.Bool
        )
        self.assertIs(
            stream_xsos.SMEnabled.resume.default,
            False
        )


class TestSMResume(unittest.TestCase):
    def test_is_sm_xso(self):
        self.assertTrue(issubclass(
            stream_xsos.SMResume,
            stream_xsos.SMXSO
        ))

    def test_tag(self):
        self.assertEqual(
            stream_xsos.SMResume.TAG,
            (namespaces.stream_management, "resume")
        )

    def test_default_init_not_possible(self):
        with self.assertRaises(TypeError):
            stream_xsos.SMResume()

    def test_init(self):
        obj = stream_xsos.SMResume(
            counter=1,
            previd="foobar")
        self.assertEqual(1, obj.counter)
        self.assertEqual("foobar", obj.previd)

    def test_resume(self):
        self.assertIsInstance(
            stream_xsos.SMResume.counter,
            xso.Attr
        )
        self.assertEqual(
            (None, "h"),
            stream_xsos.SMResume.counter.tag
        )
        self.assertIsInstance(
            stream_xsos.SMResume.counter.type_,
            xso.Integer
        )

    def test_previd(self):
        self.assertIsInstance(
            stream_xsos.SMResume.previd,
            xso.Attr
        )
        self.assertEqual(
            (None, "previd"),
            stream_xsos.SMResume.previd.tag
        )


class TestSMResumed(unittest.TestCase):
    def test_is_sm_xso(self):
        self.assertTrue(issubclass(
            stream_xsos.SMResumed,
            stream_xsos.SMXSO
        ))

    def test_tag(self):
        self.assertEqual(
            stream_xsos.SMResumed.TAG,
            (namespaces.stream_management, "resumed")
        )

    def test_default_init(self):
        with self.assertRaises(TypeError):
            stream_xsos.SMResumed()

    def test_init(self):
        obj = stream_xsos.SMResumed(
            counter=1,
            previd="foobar")
        self.assertEqual(1, obj.counter)
        self.assertEqual("foobar", obj.previd)

    def test_resume(self):
        self.assertIsInstance(
            stream_xsos.SMResumed.counter,
            xso.Attr
        )
        self.assertEqual(
            (None, "h"),
            stream_xsos.SMResumed.counter.tag
        )
        self.assertIsInstance(
            stream_xsos.SMResumed.counter.type_,
            xso.Integer
        )

    def test_previd(self):
        self.assertIsInstance(
            stream_xsos.SMResumed.previd,
            xso.Attr
        )
        self.assertEqual(
            (None, "previd"),
            stream_xsos.SMResumed.previd.tag
        )


class TestSMFailed(unittest.TestCase):
    def test_is_sm_xso(self):
        self.assertTrue(issubclass(
            stream_xsos.SMFailed,
            stream_xsos.SMXSO
        ))

    def test_tag(self):
        self.assertEqual(
            stream_xsos.SMFailed.TAG,
            (namespaces.stream_management, "failed")
        )

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
