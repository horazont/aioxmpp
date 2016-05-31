import contextlib
import copy
import itertools
import operator
import unittest
import unittest.mock

import aioxmpp.xso.query as xso_query
import aioxmpp.xso as xso


class FooXSO(xso.XSO):
    TAG = (None, "foo")

    attr = xso.Attr(
        "attr"
    )


class BarXSO(xso.XSO):
    TAG = (None, "bar")

    child = xso.Child([
        FooXSO,
    ])


class BazXSO(FooXSO):
    TAG = (None, "baz")

    attr2 = xso.Attr(
        "attr2"
    )


class RootXSO(xso.XSO):
    TAG = (None, "root")

    children = xso.ChildList([
        FooXSO,
        BarXSO,
    ])

    attr = xso.Attr(
        "attr"
    )


class TestEvaluationContext(unittest.TestCase):
    def setUp(self):
        self.ec = xso_query.EvaluationContext()

    def tearDown(self):
        del self.ec

    def test_get_toplevel_object_raises_KeyError_for_undefined(self):
        class Foo:
            pass

        with self.assertRaises(KeyError):
            self.ec.get_toplevel_object(Foo)

    def test_get_toplevel_object_returns_set_object(self):
        class Foo:
            pass

        self.ec.set_toplevel_object(
            unittest.mock.sentinel.instance,
            class_=Foo,
        )

        self.assertIs(
            self.ec.get_toplevel_object(Foo),
            unittest.mock.sentinel.instance
        )

    def test_set_toplevel_object_autodetects_type(self):
        class Foo:
            pass

        instance = Foo()

        self.ec.set_toplevel_object(
            instance,
        )

        self.assertIs(
            self.ec.get_toplevel_object(Foo),
            instance
        )

        with self.assertRaises(KeyError):
            self.ec.get_toplevel_object(object())

    def test_copy_copies_toplevels(self):
        obj1 = object()

        self.ec.set_toplevel_object(obj1)
        ec2 = copy.copy(self.ec)
        self.assertIs(
            self.ec.get_toplevel_object(object),
            ec2.get_toplevel_object(object),
        )

        ec2.set_toplevel_object(object())

        self.assertIsNot(
            self.ec.get_toplevel_object(object),
            ec2.get_toplevel_object(object),
        )
        self.assertIs(
            self.ec.get_toplevel_object(object),
            obj1
        )

    def test_eval_simply_forwards_result(self):
        expr = unittest.mock.Mock()

        result = self.ec.eval(expr)

        expr.eval.assert_called_with(self.ec)

        self.assertEqual(result, expr.eval())

    def test_eval_bool_with_false_generator(self):
        def generator():
            return
            yield

        expr = unittest.mock.Mock()
        expr.eval.return_value = generator()

        result = self.ec.eval_bool(expr)

        expr.eval.assert_called_with(self.ec)

        self.assertFalse(result)

    def test_eval_bool_with_true_generator(self):
        aborted = False

        def generator():
            nonlocal aborted
            try:
                yield
            except GeneratorExit:
                aborted = True
                raise

        expr = unittest.mock.Mock()
        expr.eval.return_value = generator()

        result = self.ec.eval_bool(expr)

        expr.eval.assert_called_with(self.ec)

        self.assertTrue(result)
        self.assertTrue(aborted)

    def test_eval_bool_with_false_sequence(self):
        expr = unittest.mock.Mock()
        expr.eval.return_value = []

        result = self.ec.eval_bool(expr)

        expr.eval.assert_called_with(self.ec)

        self.assertFalse(result)

    def test_eval_bool_with_true_sequence(self):
        expr = unittest.mock.Mock()
        expr.eval.return_value = ["1"]

        result = self.ec.eval_bool(expr)

        expr.eval.assert_called_with(self.ec)

        self.assertTrue(result)


class Test_SoftExprMixin(unittest.TestCase):
    def test_getitem_uses_as_expr(self):
        index = unittest.mock.sentinel.index
        e = xso_query._SoftExprMixin()

        with contextlib.ExitStack() as stack:
            as_expr = stack.enter_context(
                unittest.mock.patch("aioxmpp.xso.query.as_expr")
            )

            Nth = stack.enter_context(
                unittest.mock.patch("aioxmpp.xso.query.Nth")
            )

            result = e[index]

        as_expr.assert_called_with(index)
        Nth.assert_called_with(
            e,
            as_expr(),
        )

        self.assertEqual(
            result,
            Nth(),
        )

    def test_getitem_with_number(self):
        e = xso_query._SoftExprMixin()

        with contextlib.ExitStack() as stack:
            Nth = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.xso.query.Nth",
                )
            )

            Constant = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.xso.query.Constant",
                )
            )

            result = e[10]

        Constant.assert_called_with(
            10,
        )

        Nth.assert_called_with(
            e,
            Constant()
        )

        self.assertEqual(
            result,
            Nth()
        )

    def test_getitem_with_slice(self):
        e = xso_query._SoftExprMixin()

        with contextlib.ExitStack() as stack:
            Nth = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.xso.query.Nth",
                )
            )

            Constant = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.xso.query.Constant",
                )
            )

            result = e[1:2:3]

        Constant.assert_called_with(
            slice(1, 2, 3),
        )

        Nth.assert_called_with(
            e,
            Constant()
        )

        self.assertEqual(
            result,
            Nth()
        )

    def test_expr_slash_PreExpr(self):
        e = xso_query._SoftExprMixin()

        pe = unittest.mock.Mock(spec=xso_query.PreExpr)

        with unittest.mock.patch(
                "aioxmpp.xso.query.as_expr") as as_expr:
            result = e / pe

        as_expr.assert_called_with(pe, lhs=e)
        self.assertEqual(
            result,
            as_expr(),
        )

    def test_expr_slash_Expr(self):
        e = xso_query._SoftExprMixin()

        e2 = unittest.mock.Mock(spec=xso_query.Expr)

        with unittest.mock.patch(
                "aioxmpp.xso.query.as_expr") as as_expr:
            result = e / e2

        as_expr.assert_called_with(e2, lhs=e)
        self.assertEqual(
            result,
            as_expr(),
        )

    def test_expr_getitem_where(self):
        expr = xso_query._SoftExprMixin()

        w = unittest.mock.Mock(spec=xso_query.where)
        w.expr = unittest.mock.Mock(spec=xso_query.Expr)

        with unittest.mock.patch(
                "aioxmpp.xso.query.ExprFilter") as ExprFilter:
            result = expr[w]

        ExprFilter.assert_called_with(expr, w.expr)
        self.assertEqual(
            result,
            ExprFilter(),
        )


class Test_ExprMixin(unittest.TestCase):
    def _test_cmp_op(self, operator_):
        expr1 = xso_query._ExprMixin()
        expr2 = xso_query._ExprMixin()

        def as_exprs():
            yield unittest.mock.sentinel.expr1
            yield unittest.mock.sentinel.expr2

        with contextlib.ExitStack() as stack:
            as_expr = stack.enter_context(
                unittest.mock.patch("aioxmpp.xso.query.as_expr")
            )
            as_expr.side_effect = as_exprs()

            CmpOp = stack.enter_context(
                unittest.mock.patch("aioxmpp.xso.query.CmpOp")
            )

            result = operator_(expr1, expr2)

        self.assertSequenceEqual(
            as_expr.mock_calls,
            [
                unittest.mock.call(expr1),
                unittest.mock.call(expr2),
            ]
        )

        CmpOp.assert_called_with(
            unittest.mock.sentinel.expr1,
            unittest.mock.sentinel.expr2,
            operator_,
        )

        self.assertEqual(
            result,
            CmpOp(),
        )

    def test_eq(self):
        self._test_cmp_op(operator.eq)

    def test_ne(self):
        self._test_cmp_op(operator.ne)

    def test_lt(self):
        self._test_cmp_op(operator.lt)

    def test_le(self):
        self._test_cmp_op(operator.le)

    def test_gt(self):
        self._test_cmp_op(operator.gt)

    def test_ge(self):
        self._test_cmp_op(operator.ge)

    def test_not(self):
        expr1 = xso_query._ExprMixin()

        def as_exprs():
            yield unittest.mock.sentinel.expr1

        with contextlib.ExitStack() as stack:
            as_expr = stack.enter_context(
                unittest.mock.patch("aioxmpp.xso.query.as_expr")
            )
            as_expr.side_effect = as_exprs()

            NotOp = stack.enter_context(
                unittest.mock.patch("aioxmpp.xso.query.NotOp")
            )

            result = xso_query.not_(expr1)

        self.assertSequenceEqual(
            as_expr.mock_calls,
            [
                unittest.mock.call(expr1),
            ]
        )

        NotOp.assert_called_with(
            unittest.mock.sentinel.expr1,
        )

        self.assertEqual(
            result,
            NotOp(),
        )


class TestExpr(unittest.TestCase):
    def setUp(self):
        class DummyExpr(xso_query.Expr):
            def __init__(self, *args, mock=None, **kwargs):
                super().__init__(*args, **kwargs)
                self.__mock = mock

            def eval(self, ec):
                return self.__mock.eval(ec)

        self.DummyExpr = DummyExpr

    def tearDown(self):
        del self.DummyExpr

    def test_is_abstract(self):
        with self.assertRaisesRegex(TypeError, "abstract"):
            xso_query.Expr()

    def test_has_ExprMixin(self):
        self.assertTrue(issubclass(
            xso_query.Expr,
            xso_query._ExprMixin,
        ))

    def test_eval_leaf_uses_eval(self):
        expr = unittest.mock.Mock()
        ec = unittest.mock.sentinel.ec

        e = self.DummyExpr(mock=expr)
        result = e.eval_leaf(ec)

        expr.eval.assert_called_with(ec)

        self.assertEqual(result, expr.eval())

    def test_eval_leaf_evaluates_generator(self):
        def generator():
            yield 1
            yield 2

        expr = unittest.mock.Mock()
        expr.eval.return_value = generator()
        ec = unittest.mock.sentinel.ec

        e = self.DummyExpr(mock=expr)
        result = e.eval_leaf(ec)

        expr.eval.assert_called_with(ec)

        self.assertSequenceEqual(
            result,
            [1, 2]
        )

    def test_eval_leaf_keeps_mappings(self):
        expr = unittest.mock.Mock()
        expr.eval.return_value = {"1": "2"}
        ec = unittest.mock.sentinel.ec

        e = self.DummyExpr(mock=expr)
        result = e.eval_leaf(ec)

        expr.eval.assert_called_with(ec)

        self.assertSequenceEqual(
            result,
            {"1": "2"}
        )


class TestContextInstance(unittest.TestCase):
    def setUp(self):
        class Cls:
            pass

        self.Cls = Cls
        self.toplevel = Cls()

        self.ec = unittest.mock.Mock()
        self.ec.get_toplevel_object.return_value = self.toplevel

    def tearDown(self):
        del self.ec
        del self.Cls
        del self.toplevel

    def test_is_Expr(self):
        self.assertTrue(issubclass(
            xso_query.ContextInstance,
            xso_query.Expr,
        ))

    def test_eval_returns_toplevel_object_of_class(self):
        ci = xso_query.ContextInstance(self.Cls)

        self.assertEqual(
            ci.eval(self.ec),
            [self.toplevel],
        )

        self.ec.get_toplevel_object.assert_called_with(self.Cls)

    def test_eval_returns_empty_sequence_for_unset_toplevel(self):
        self.ec.get_toplevel_object.side_effect = KeyError

        ci = xso_query.ContextInstance(self.Cls)

        self.assertEqual(
            ci.eval(self.ec),
            [],
        )

        self.ec.get_toplevel_object.assert_called_with(self.Cls)


class TestGetDescriptor(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_is_Expr(self):
        self.assertTrue(issubclass(
            xso_query.GetDescriptor,
            xso_query.Expr,
        ))

    def test_update_values_appends(self):
        v = unittest.mock.Mock()
        vnew = unittest.mock.Mock()

        gd = xso_query.GetDescriptor(
            unittest.mock.sentinel.expr,
            unittest.mock.sentinel.descriptor,
        )

        gd.update_values(v, vnew)

        v.append.assert_called_with(vnew)

    def test_new_values_creates_empty_sequence(self):
        gd = xso_query.GetDescriptor(
            unittest.mock.sentinel.expr,
            unittest.mock.sentinel.descriptor,
        )

        s1 = gd.new_values()
        s2 = gd.new_values()

        self.assertSequenceEqual(
            s1,
            []
        )

        self.assertSequenceEqual(
            s2,
            []
        )

        self.assertIsNot(s1, s2)

    def test_eval_gets_descriptor(self):
        class Bar:
            pass

        i1 = Bar()
        i2 = Bar()

        def values():
            yield unittest.mock.sentinel.v1
            yield unittest.mock.sentinel.v2

        descriptor = unittest.mock.PropertyMock()
        descriptor.side_effect = values()

        expr = unittest.mock.Mock()
        ec = unittest.mock.sentinel

        expr.eval.return_value = [
            i1,
            i2,
        ]

        gd = xso_query.GetDescriptor(expr, descriptor)

        with contextlib.ExitStack() as stack:
            new_values = stack.enter_context(
                unittest.mock.patch.object(gd, "new_values")
            )

            update_values = stack.enter_context(
                unittest.mock.patch.object(gd, "update_values")
            )

            new_values.return_value = unittest.mock.sentinel.vs

            result = gd.eval(ec)

        self.assertEqual(
            result,
            unittest.mock.sentinel.vs,
        )

        self.assertSequenceEqual(
            update_values.mock_calls,
            [
                unittest.mock.call(
                    unittest.mock.sentinel.vs,
                    unittest.mock.sentinel.v1,
                ),
                unittest.mock.call(
                    unittest.mock.sentinel.vs,
                    unittest.mock.sentinel.v2,
                ),
            ]
        )

        expr.eval.assert_called_with(ec)

    def test_eval_skips_on_AttributeError(self):
        class Bar:
            pass

        i1 = Bar()
        i2 = Bar()

        def values():
            yield AttributeError
            yield unittest.mock.sentinel.v2

        descriptor = unittest.mock.PropertyMock()
        descriptor.side_effect = values()

        expr = unittest.mock.Mock()
        ec = unittest.mock.sentinel

        expr.eval.return_value = [
            i1,
            i2,
        ]

        gd = xso_query.GetDescriptor(expr, descriptor)

        with contextlib.ExitStack() as stack:
            new_values = stack.enter_context(
                unittest.mock.patch.object(gd, "new_values")
            )

            update_values = stack.enter_context(
                unittest.mock.patch.object(gd, "update_values")
            )

            new_values.return_value = unittest.mock.sentinel.vs

            result = gd.eval(ec)

        self.assertEqual(
            result,
            unittest.mock.sentinel.vs,
        )

        self.assertSequenceEqual(
            update_values.mock_calls,
            [
                unittest.mock.call(
                    unittest.mock.sentinel.vs,
                    unittest.mock.sentinel.v2,
                ),
            ]
        )

        expr.eval.assert_called_with(ec)


class TestGetMappingDescriptor(unittest.TestCase):
    def test_is_GetDescriptor(self):
        self.assertTrue(issubclass(
            xso_query.GetMappingDescriptor,
            xso_query.GetDescriptor,
        ))

    def test_new_values_returns_result_of_mapping_factory(self):
        expr = unittest.mock.sentinel.expr
        descriptor = unittest.mock.sentinel.descriptor
        mf = unittest.mock.Mock()

        gmd = xso_query.GetMappingDescriptor(
            expr,
            descriptor,
            mapping_factory=mf
        )

        vs = gmd.new_values()
        mf.assert_called_with()
        self.assertEqual(vs, mf())

    def test_update_values_uses_update(self):
        expr = unittest.mock.sentinel.expr
        descriptor = unittest.mock.sentinel.descriptor

        v = unittest.mock.Mock()
        vnew = unittest.mock.sentinel.vnew

        gmd = xso_query.GetMappingDescriptor(
            expr,
            descriptor,
        )

        gmd.update_values(v, vnew)

        v.update.assert_called_with(vnew)


class TestGetSequenceDescriptor(unittest.TestCase):
    def test_is_GetDescriptor(self):
        self.assertTrue(issubclass(
            xso_query.GetSequenceDescriptor,
            xso_query.GetDescriptor,
        ))

    def test_new_values_returns_result_of_sequence_factory(self):
        expr = unittest.mock.sentinel.expr
        descriptor = unittest.mock.sentinel.descriptor
        sf = unittest.mock.Mock()

        gsd = xso_query.GetSequenceDescriptor(
            expr,
            descriptor,
            sequence_factory=sf
        )

        vs = gsd.new_values()
        sf.assert_called_with()
        self.assertEqual(vs, sf())

    def test_update_values_uses_extend(self):
        expr = unittest.mock.sentinel.expr
        descriptor = unittest.mock.sentinel.descriptor

        v = unittest.mock.Mock()
        vnew = unittest.mock.sentinel.vnew

        gsd = xso_query.GetSequenceDescriptor(
            expr,
            descriptor,
        )

        gsd.update_values(v, vnew)

        v.extend.assert_called_with(vnew)


class TestGetInstances(unittest.TestCase):
    def test_is_Expr(self):
        self.assertTrue(issubclass(
            xso_query.GetInstances,
            xso_query.Expr,
        ))

    def test_eval_filters_for_class(self):
        class Foo:
            pass

        class Bar:
            pass

        expr = unittest.mock.Mock()
        ec = unittest.mock.sentinel

        gi = xso_query.GetInstances(expr, Bar)

        expr.eval.return_value = [
            Foo(),
            Foo(),
            Foo(),
        ]

        self.assertSequenceEqual(
            list(gi.eval(ec)),
            [],
        )

        expr.eval.assert_called_with(ec)

    def test_eval_returns_instances(self):
        class Foo:
            pass

        class Bar:
            pass

        i1 = Bar()
        i2 = Bar()

        expr = unittest.mock.Mock()
        ec = unittest.mock.sentinel

        gi = xso_query.GetInstances(expr, Bar)

        expr.eval.return_value = [
            i1,
            Foo(),
            Foo(),
            Foo(),
            i2,
        ]

        self.assertSequenceEqual(
            list(gi.eval(ec)),
            [i1, i2],
        )

        expr.eval.assert_called_with(ec)


class TestNth(unittest.TestCase):
    def test_is_Expr(self):
        self.assertTrue(issubclass(
            xso_query.Nth,
            xso_query.Expr,
        ))

    def test_eval_returns_only_nth(self):
        expr = unittest.mock.Mock()
        nth_expr = unittest.mock.Mock()
        nth_expr.eval.return_value = [2]

        ec = unittest.mock.sentinel

        nth = xso_query.Nth(expr, nth_expr)

        expr.eval.return_value = [
            getattr(unittest.mock.sentinel, "v{}".format(i))
            for i in range(10)
        ]

        self.assertSequenceEqual(
            list(nth.eval(ec)),
            [unittest.mock.sentinel.v2]
        )

        nth_expr.eval.assert_called_with(ec)
        expr.eval.assert_called_with(ec)

    def test_eval_works_with_slice(self):
        expr = unittest.mock.Mock()
        nth_expr = unittest.mock.Mock()
        nth_expr.eval.return_value = [slice(1, 8, 2)]
        ec = unittest.mock.sentinel

        nth = xso_query.Nth(expr, nth_expr)

        expr.eval.return_value = [
            getattr(unittest.mock.sentinel, "v{}".format(i))
            for i in range(10)
        ]

        self.assertSequenceEqual(
            list(nth.eval(ec)),
            [
                unittest.mock.sentinel.v1,
                unittest.mock.sentinel.v3,
                unittest.mock.sentinel.v5,
                unittest.mock.sentinel.v7,
            ]
        )

        nth_expr.eval.assert_called_with(ec)
        expr.eval.assert_called_with(ec)


class TestExprFilter(unittest.TestCase):
    def test_is_Expr(self):
        self.assertTrue(issubclass(
            xso_query.ExprFilter,
            xso_query.Expr,
        ))

    def test_eval(self):
        ec = unittest.mock.Mock()
        filter_expr = unittest.mock.Mock()
        expr = unittest.mock.Mock()

        ef = xso_query.ExprFilter(
            expr,
            filter_expr
        )

        expr.eval.return_value = [
            unittest.mock.sentinel.v1,
            unittest.mock.sentinel.v2,
        ]

        def values():
            yield True
            yield False

        with unittest.mock.patch("copy.copy") as copy_:
            copy_().eval_bool.side_effect = values()
            copy_.mock_calls.clear()

            result = ef.eval(ec)

            self.assertSequenceEqual(
                list(result),
                [
                    unittest.mock.sentinel.v1,
                ]
            )

        expr.eval.assert_called_with(ec)

        self.assertSequenceEqual(
            copy_.mock_calls,
            [
                unittest.mock.call(ec),
                unittest.mock.call().set_toplevel_object(
                    unittest.mock.sentinel.v1,
                ),
                unittest.mock.call().eval_bool(
                    filter_expr,
                ),
                unittest.mock.call(ec),
                unittest.mock.call().set_toplevel_object(
                    unittest.mock.sentinel.v2,
                ),
                unittest.mock.call().eval_bool(
                    filter_expr,
                ),
            ]
        )


class Testwhere(unittest.TestCase):
    def test_init(self):
        w = xso_query.where(unittest.mock.sentinel.expr)
        self.assertIs(w.expr, unittest.mock.sentinel.expr)


class TestCmpOp(unittest.TestCase):
    def test_is_Expr(self):
        self.assertTrue(issubclass(
            xso_query.CmpOp,
            xso_query.Expr,
        ))

    def test_eval_leaf_returns_true_if_any_matches(self):
        ec = unittest.mock.sentinel.ec

        def results():
            yield False
            yield True
            yield False

        op = unittest.mock.Mock()
        op.side_effect = results()

        expr = unittest.mock.Mock()
        expr.eval_leaf.return_value = [
            unittest.mock.sentinel.v1,
            unittest.mock.sentinel.v2,
            unittest.mock.sentinel.v3,
        ]

        ref_expr = unittest.mock.Mock()
        ref_expr.eval_leaf.return_value = [
            unittest.mock.sentinel.rv
        ]

        co = xso_query.CmpOp(expr, ref_expr, op)

        result = co.eval_leaf(ec)

        self.assertTrue(result)

        self.assertSequenceEqual(
            expr.mock_calls,
            [
                unittest.mock.call.eval_leaf(ec),
            ]
        )

        self.assertSequenceEqual(
            ref_expr.mock_calls,
            [
                unittest.mock.call.eval_leaf(ec),
            ]
        )

        self.assertSequenceEqual(
            op.mock_calls,
            [
                unittest.mock.call(
                    unittest.mock.sentinel.v1,
                    unittest.mock.sentinel.rv,
                ),
                unittest.mock.call(
                    unittest.mock.sentinel.v2,
                    unittest.mock.sentinel.rv,
                ),
            ]
        )

    def test_eval_leaf_returns_false_if_none_matches(self):
        ec = unittest.mock.sentinel.ec

        def results():
            return
            yield

        op = unittest.mock.Mock()
        op.side_effect = results()

        expr = unittest.mock.Mock()
        expr.eval_leaf.return_value = [
        ]

        ref_expr = unittest.mock.Mock()
        ref_expr.eval_leaf.return_value = [
            unittest.mock.sentinel.rv
        ]

        co = xso_query.CmpOp(expr, ref_expr, op)

        result = co.eval_leaf(ec)

        self.assertFalse(result)

        self.assertSequenceEqual(
            expr.mock_calls,
            [
                unittest.mock.call.eval_leaf(ec),
            ]
        )

        self.assertSequenceEqual(
            ref_expr.mock_calls,
            [
                unittest.mock.call.eval_leaf(ec),
            ]
        )

        self.assertSequenceEqual(
            op.mock_calls,
            [
            ]
        )

    def test_eval_leaf_returns_false_if_no_ref_values(self):
        ec = unittest.mock.sentinel.ec

        def results():
            return
            yield

        op = unittest.mock.Mock()
        op.side_effect = results()

        expr = unittest.mock.Mock()
        expr.eval_leaf.return_value = [
            unittest.mock.sentinel.v1,
            unittest.mock.sentinel.v2,
            unittest.mock.sentinel.v3,
        ]

        ref_expr = unittest.mock.Mock()
        ref_expr.eval_leaf.return_value = [
        ]

        co = xso_query.CmpOp(expr, ref_expr, op)

        result = co.eval_leaf(ec)

        self.assertFalse(result)

        self.assertSequenceEqual(
            expr.mock_calls,
            [
                unittest.mock.call.eval_leaf(ec),
            ]
        )

        self.assertSequenceEqual(
            ref_expr.mock_calls,
            [
                unittest.mock.call.eval_leaf(ec),
            ]
        )

        self.assertSequenceEqual(
            op.mock_calls,
            [
            ]
        )

    def test_eval_leaf_cartesian_product(self):
        ec = unittest.mock.sentinel.ec

        def results():
            while True:
                yield False

        op = unittest.mock.Mock()
        op.side_effect = results()

        expr = unittest.mock.Mock()
        expr.eval_leaf.return_value = [
            unittest.mock.sentinel.v1,
            unittest.mock.sentinel.v2,
            unittest.mock.sentinel.v3,
        ]

        ref_expr = unittest.mock.Mock()
        ref_expr.eval_leaf.return_value = [
            unittest.mock.sentinel.rv1,
            unittest.mock.sentinel.rv2,
            unittest.mock.sentinel.rv3,
        ]

        co = xso_query.CmpOp(expr, ref_expr, op)

        result = co.eval_leaf(ec)

        self.assertFalse(result)

        self.assertSequenceEqual(
            expr.mock_calls,
            [
                unittest.mock.call.eval_leaf(ec),
            ]
        )

        self.assertSequenceEqual(
            ref_expr.mock_calls,
            [
                unittest.mock.call.eval_leaf(ec),
            ]
        )

        self.assertSequenceEqual(
            op.mock_calls,
            [
                unittest.mock.call(v1, v2)
                for v1, v2 in itertools.product(
                    expr.eval_leaf.return_value,
                    ref_expr.eval_leaf.return_value,
                )
            ]
        )

    def test_eval_returns_empty_list_on_false(self):
        ec = unittest.mock.sentinel.ec
        expr = unittest.mock.sentinel.expr
        ref_expr = unittest.mock.sentinel.ref_expr
        op = unittest.mock.sentinel.op

        co = xso_query.CmpOp(expr, ref_expr, op)

        with unittest.mock.patch.object(co, "eval_leaf") as eval_leaf:
            eval_leaf.return_value = False

            self.assertSequenceEqual(
                list(co.eval(ec)),
                []
            )

        eval_leaf.assert_called_with(ec)

    def test_eval_returns_list_with_single_True_on_true(self):
        ec = unittest.mock.sentinel.ec
        expr = unittest.mock.sentinel.expr
        ref_expr = unittest.mock.sentinel.ref_expr
        op = unittest.mock.sentinel.op

        co = xso_query.CmpOp(expr, ref_expr, op)

        with unittest.mock.patch.object(co, "eval_leaf") as eval_leaf:
            eval_leaf.return_value = True

            self.assertSequenceEqual(
                list(co.eval(ec)),
                [True]
            )

        eval_leaf.assert_called_with(ec)


class TestNotOp(unittest.TestCase):
    def test_is_Expr(self):
        self.assertTrue(issubclass(
            xso_query.NotOp,
            xso_query.Expr,
        ))

    def test_eval_leaf_uses_eval_bool(self):
        ec = unittest.mock.Mock()
        expr = unittest.mock.sentinel.expr

        no = xso_query.NotOp(expr)

        ec.eval_bool.return_value = True
        result = no.eval_leaf(ec)
        self.assertFalse(result)

        ec.eval_bool.assert_called_with(expr)

        ec.eval_bool.return_value = False
        result = no.eval_leaf(ec)
        self.assertTrue(result)

        ec.eval_bool.assert_called_with(expr)

    def test_eval_returns_empty_list_on_false(self):
        ec = unittest.mock.sentinel.ec
        expr = unittest.mock.sentinel.expr

        no = xso_query.NotOp(expr)

        with unittest.mock.patch.object(no, "eval_leaf") as eval_leaf:
            eval_leaf.return_value = False

            self.assertSequenceEqual(
                list(no.eval(ec)),
                []
            )

        eval_leaf.assert_called_with(ec)

    def test_eval_returns_list_with_single_True_on_true(self):
        ec = unittest.mock.sentinel.ec
        expr = unittest.mock.sentinel.expr

        no = xso_query.NotOp(expr)

        with unittest.mock.patch.object(no, "eval_leaf") as eval_leaf:
            eval_leaf.return_value = True

            self.assertSequenceEqual(
                list(no.eval(ec)),
                [True]
            )

        eval_leaf.assert_called_with(ec)


class Testnot_(unittest.TestCase):
    def test_uses_as_expr(self):
        expr = unittest.mock.sentinel.expr

        with contextlib.ExitStack() as stack:
            as_expr = stack.enter_context(
                unittest.mock.patch("aioxmpp.xso.query.as_expr")
            )

            NotOp = stack.enter_context(
                unittest.mock.patch("aioxmpp.xso.query.NotOp")
            )

            result = xso_query.not_(expr)

        as_expr.assert_called_with(expr)

        NotOp.assert_called_with(as_expr())

        self.assertEqual(result, NotOp())


class TestConstant(unittest.TestCase):
    def test_is_Expr(self):
        self.assertTrue(issubclass(
            xso_query.Constant,
            xso_query.Expr,
        ))

    def test_eval_returns_value(self):
        ec = unittest.mock.sentinel.ec

        c = xso_query.Constant(unittest.mock.sentinel.value)
        self.assertEqual(
            c.eval(ec),
            [unittest.mock.sentinel.value],
        )


class TestPreExpr(unittest.TestCase):
    def setUp(self):
        class DummyPreExpr(xso_query.PreExpr):
            def __init__(self, *args, mock=None, **kwargs):
                super().__init__(*args, **kwargs)
                self.__mock = mock or unittest.mock.Mock()

            def xq_instantiate(self, ec):
                return self.__mock.xq_instantiate(ec)

        self.DummyPreExpr = DummyPreExpr

    def tearDown(self):
        del self.DummyPreExpr

    def test_has_SoftExprMixin(self):
        self.assertTrue(issubclass(
            xso_query.PreExpr,
            xso_query._SoftExprMixin,
        ))


class TestClass(unittest.TestCase):
    def test_is_PreExpr(self):
        self.assertTrue(issubclass(
            xso_query.Class,
            xso_query.PreExpr,
        ))

    def test_init(self):
        xso_query.Class()

    def test_forwards_all_arguments(self):
        m = unittest.mock.Mock()

        class Foo:
            def __init__(self, *args, **kwargs):
                super().__init__()
                m(args, kwargs)

        class Bar(xso_query.Class, Foo):
            pass

        Bar("a", 1, bar="2")

        m.assert_called_with(("a", 1), {"bar": "2"})

    def test_xq_instantiate(self):
        expr = unittest.mock.sentinel.expr
        cls = xso_query.Class()

        with contextlib.ExitStack() as stack:
            GetInstances = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.xso.query.GetInstances"
                )
            )

            result = cls.xq_instantiate(expr)

        GetInstances.assert_called_with(
            expr,
            cls,
        )

        self.assertEqual(
            result,
            GetInstances()
        )

    def test_xq_instantiate_without_expr(self):
        cls = xso_query.Class()

        with contextlib.ExitStack() as stack:
            ContextInstance = stack.enter_context(
                unittest.mock.patch(
                    "aioxmpp.xso.query.ContextInstance"
                )
            )

            result = cls.xq_instantiate()

        ContextInstance.assert_called_with(
            cls,
        )

        self.assertEqual(
            result,
            ContextInstance()
        )


class TestBoundDescriptor(unittest.TestCase):
    def test_is_PreExpr(self):
        self.assertTrue(issubclass(
            xso_query.BoundDescriptor,
            xso_query.PreExpr,
        ))

    def test_has_ExprMixin(self):
        self.assertTrue(issubclass(
            xso_query.BoundDescriptor,
            xso_query._ExprMixin,
        ))

    def test_init(self):
        bd = xso_query.BoundDescriptor(
            unittest.mock.sentinel.class_,
            unittest.mock.sentinel.descriptor,
            unittest.mock.sentinel.expr_class,
        )

        self.assertEqual(
            bd.xq_xso_class,
            unittest.mock.sentinel.class_,
        )

        self.assertEqual(
            bd.xq_descriptor,
            unittest.mock.sentinel.descriptor,
        )
        self.assertEqual(
            bd.xq_expr_class,
            unittest.mock.sentinel.expr_class,
        )

    def test_xq_instantiate(self):
        expr = unittest.mock.sentinel.expr
        class_ = unittest.mock.Mock()
        expr_class = unittest.mock.Mock()

        bd = xso_query.BoundDescriptor(
            class_,
            unittest.mock.sentinel.descriptor,
            expr_class,
        )

        result = bd.xq_instantiate(expr)

        class_.xq_instantiate.assert_called_with(expr)

        expr_class.assert_called_with(
            class_.xq_instantiate(),
            unittest.mock.sentinel.descriptor,
        )

        self.assertEqual(
            result,
            expr_class()
        )

    def test_xq_instantiate_with_extra_args(self):
        expr = unittest.mock.sentinel.expr
        class_ = unittest.mock.Mock()
        expr_class = unittest.mock.Mock()

        bd = xso_query.BoundDescriptor(
            class_,
            unittest.mock.sentinel.descriptor,
            expr_class,
            expr_kwargs={"mapping_type": unittest.mock.sentinel.mt}
        )

        result = bd.xq_instantiate(expr)

        class_.xq_instantiate.assert_called_with(expr)

        expr_class.assert_called_with(
            class_.xq_instantiate(),
            unittest.mock.sentinel.descriptor,
            mapping_type=unittest.mock.sentinel.mt
        )

        self.assertEqual(
            result,
            expr_class()
        )


class Testas_expr(unittest.TestCase):
    def test_arbitrary_type(self):
        vs = [
            unittest.mock.sentinel.thing,
            1,
            2,
            "foo",
            1.2,
        ]

        for v in vs:
            with unittest.mock.patch("aioxmpp.xso.query.Constant") as C:
                result = xso_query.as_expr(v)

            C.assert_called_with(v)
            self.assertEqual(
                result,
                C()
            )

    def test_PreExpr(self):
        pe = unittest.mock.Mock(spec=xso_query.PreExpr)
        result = xso_query.as_expr(pe)

        pe.xq_instantiate.assert_called_with(None)

        self.assertEqual(
            result,
            pe.xq_instantiate(),
        )

    def test_PreExpr_with_context(self):
        expr = unittest.mock.sentinel.expr
        pe = unittest.mock.Mock(spec=xso_query.PreExpr)
        result = xso_query.as_expr(pe, expr)

        pe.xq_instantiate.assert_called_with(expr)

        self.assertEqual(
            result,
            pe.xq_instantiate(),
        )

    def test_Expr(self):
        e = unittest.mock.Mock(spec=xso_query.Expr)
        result = xso_query.as_expr(e)

        self.assertIs(result, e)

    def test_Expr_with_Expr_in_expr_attribute(self):
        as_expr = unittest.mock.Mock()
        as_expr.side_effect = xso_query.as_expr

        e_nested = unittest.mock.sentinel.e_nested

        e = unittest.mock.Mock(spec=xso_query.Expr)
        e.expr = e_nested
        self.assertTrue(hasattr(e, "expr"))

        with unittest.mock.patch(
                "aioxmpp.xso.query.as_expr",
                new=as_expr):
            result = xso_query.as_expr(
                e,
                lhs=unittest.mock.sentinel.lhs
            )

        self.assertIs(result, e)

        self.assertSequenceEqual(
            as_expr.mock_calls,
            [
                unittest.mock.call(e,
                                   lhs=unittest.mock.sentinel.lhs),
                unittest.mock.call(e_nested,
                                   lhs=unittest.mock.sentinel.lhs),
            ]
        )


class Test__integration__(unittest.TestCase):
    def test_as_expr_recursively_resolves_lhses(self):
        new_lhs = unittest.mock.sentinel.new_lhs

        cls = xso_query.Class()
        descriptor = xso_query.BoundDescriptor(
            cls,
            unittest.mock.sentinel.descriptor,
            xso_query.GetDescriptor,
        )

        result = xso_query.as_expr(descriptor, lhs=new_lhs)

        self.assertIsInstance(
            result,
            xso_query.GetDescriptor,
        )

        self.assertEqual(
            result.descriptor,
            unittest.mock.sentinel.descriptor,
        )

        self.assertIsInstance(
            result.expr,
            xso_query.GetInstances,
        )

        self.assertEqual(
            result.expr.class_,
            cls,
        )

        self.assertEqual(
            result.expr.expr,
            new_lhs,
        )

    def test_xsopath(self):
        xso = RootXSO()
        xso.attr = "root"

        f = FooXSO()
        f.attr = "foo1"
        xso.children.append(f)

        f = BazXSO()
        f.attr2 = "baz1"
        xso.children.append(f)

        f = FooXSO()
        f.attr = "foo2"
        xso.children.append(f)

        f = FooXSO()
        f.attr = "bar1/foo"
        b = BarXSO()
        b.child = f
        xso.children.append(b)

        ec = xso_query.EvaluationContext()
        ec.set_toplevel_object(xso)

        query = xso_query.as_expr(
            RootXSO.children / BarXSO.child / FooXSO.attr
        )

        self.assertSequenceEqual(
            list(query.eval(ec)),
            ["bar1/foo"]
        )

        query = xso_query.as_expr(
            RootXSO.children / FooXSO.attr
        )

        self.assertSequenceEqual(
            list(query.eval(ec)),
            ["foo1", "foo2"]
        )

        query = xso_query.as_expr(
            RootXSO.children / FooXSO
        )

        self.assertSequenceEqual(
            list(query.eval(ec)),
            list(filter(lambda x: isinstance(x, FooXSO), xso.children))
        )

        query = xso_query.as_expr(
            RootXSO.children / FooXSO[::2]
        )

        self.assertSequenceEqual(
            list(query.eval(ec)),
            [
                xso.children[0],
                xso.children[2],
            ]
        )

        query = xso_query.as_expr(
            RootXSO.children / FooXSO[xso_query.where(FooXSO.attr)][:2]
        )

        self.assertSequenceEqual(
            list(query.eval(ec)),
            [
                xso.children[0],
                xso.children[2],
            ]
        )

        query = xso_query.as_expr(
            RootXSO.children / FooXSO[:2][xso_query.where(FooXSO.attr)]
        )

        self.assertSequenceEqual(
            list(query.eval(ec)),
            [
                xso.children[0],
            ]
        )

        query = xso_query.as_expr(
            RootXSO.children / FooXSO[xso_query.where(FooXSO.attr)][:2] /
            FooXSO.attr
        )

        self.assertSequenceEqual(
            list(query.eval(ec)),
            [
                "foo1",
                "foo2",
            ]
        )

        query = xso_query.as_expr(
            RootXSO.children / FooXSO[:2][xso_query.where(FooXSO.attr)] /
            FooXSO.attr
        )

        self.assertSequenceEqual(
            list(query.eval(ec)),
            [
                "foo1",
            ]
        )

        query = xso_query.as_expr(
            RootXSO.children / FooXSO[:2][
                xso_query.where(xso_query.not_(FooXSO.attr))
            ]
        )

        self.assertSequenceEqual(
            list(query.eval(ec)),
            [
                xso.children[1]
            ]
        )

        query = xso_query.as_expr(
            RootXSO.children / FooXSO[xso_query.where(FooXSO.attr == "foo1")] /
            FooXSO.attr
        )

        self.assertSequenceEqual(
            list(query.eval(ec)),
            [
                "foo1",
            ]
        )

# foo
