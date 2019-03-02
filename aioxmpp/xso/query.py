########################################################################
# File name: query.py
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
import abc
import copy
import itertools
import inspect
import operator


class _SoftExprMixin:
    """
    This mixin is used for metaclasses and descriptors.

    It defines the operators ``/`` and ``[]``, which are rarely used for either
    classes or descriptors.

    .. seealso::

       :class:`_ExprMixin`
          which inherits from this class and defines more operators, some of
          which would be unsafe to implement on classes or descriptors, such as
          ``==``.

    """

    def __truediv__(self, other):
        if isinstance(other, PreExpr):
            return as_expr(other, lhs=self)
        elif isinstance(other, Expr):
            return as_expr(other, lhs=self)
        return NotImplemented

    def __getitem__(self, index):
        if isinstance(index, where):
            return ExprFilter(self, as_expr(index.expr))
        return Nth(self, as_expr(index))


class _ExprMixin(_SoftExprMixin):
    """
    This mixin defines operators which are only "safe" to overload in
    constrained situations. These operators often have meanings and may be
    implicitly used by the python language; thus, they are only defined on
    :class:`Expr` subclasses and some :class:`PreExpr` subclasses.

    The defined operators currently are:

    * Comparison: ``==``, ``<``, ``<=``, ``>=``, ``>``, ``!=``
    """

    def __eq__(self, other):
        return CmpOp(
            as_expr(self),
            as_expr(other),
            operator.eq,
        )

    def __ne__(self, other):
        return CmpOp(
            as_expr(self),
            as_expr(other),
            operator.ne,
        )

    def __lt__(self, other):
        return CmpOp(
            as_expr(self),
            as_expr(other),
            operator.lt,
        )

    def __gt__(self, other):
        return CmpOp(
            as_expr(self),
            as_expr(other),
            operator.gt,
        )

    def __ge__(self, other):
        return CmpOp(
            as_expr(self),
            as_expr(other),
            operator.ge,
        )

    def __le__(self, other):
        return CmpOp(
            as_expr(self),
            as_expr(other),
            operator.le,
        )


class EvaluationContext:
    """
    The evaluation context holds contextual information for the evaluation of a
    query expression.

    Most notably, it provides the methods for acquiring and replacing the
    toplevel objects of classes:

    .. automethod:: get_toplevel_object()

    .. automethod:: set_toplevel_object()

    In addition, it provides shortcuts for evaluating expressions:

    .. automethod:: eval

    .. automethod:: eval_bool
    """

    def __init__(self, *args, **kwargs):
        super().__init__()
        self._toplevels = {}

    def __copy__(self):
        result = type(self).__new__(type(self))
        result._toplevels = dict(self._toplevels)
        return result

    def get_toplevel_object(self, class_):
        """
        Return the toplevel object for the given `class_`. Only exact matches
        are returned.
        """
        return self._toplevels[class_]

    def set_toplevel_object(self, instance, class_=None):
        """
        Set the toplevel object to return from :meth:`get_toplevel_object` when
        asked for `class_` to `instance`.

        If `class_` is :data:`None`, the :func:`type` of the `instance` is
        used.
        """
        if class_ is None:
            class_ = type(instance)
        self._toplevels[class_] = instance

    def eval(self, expr):
        """
        Evaluate the expression `expr` and return the result.

        The result of an expression is always an iterable.
        """
        return expr.eval(self)

    def eval_bool(self, expr):
        """
        Evaluate the expression `expr` and return the truthness of its result.
        A result of an expression is said to be true if it contains at least
        one value. It has the same semantics as :func:`bool` on sequences.s
        """
        result = expr.eval(self)
        iterator = iter(result)
        try:
            next(iterator)
        except StopIteration:
            return False
        else:
            return True
        finally:
            if hasattr(iterator, "close"):
                iterator.close()


class Expr(_ExprMixin, metaclass=abc.ABCMeta):
    """
    Base class for things which are solely expressions and nothing else.
    """

    @abc.abstractmethod
    def eval(self, ec):
        pass

    def eval_leaf(self, ec):
        result = self.eval(ec)
        if inspect.isgenerator(result):
            return list(result)
        return result

    def __repr__(self):
        return "<{}.{} {!r}>".format(
            type(self).__module__,
            type(self).__qualname__,
            self.__dict__,
        )


class ContextInstance(Expr):
    def __init__(self, class_, **kwargs):
        super().__init__(**kwargs)
        self.class_ = class_

    def eval(self, ec):
        """
        Retrieve the current toplevel instance of `class_` from the
        :class:`EvaluationContext`. `
        """
        try:
            return [ec.get_toplevel_object(self.class_)]
        except KeyError:
            return []


class GetDescriptor(Expr):
    """
    Represents a descriptor bound to a class.

    As an expression, it represents the query for all values of the
    `descriptor` on an all instances of `class_` in the result set of `expr`.
    """

    def __init__(self, expr, descriptor):
        super().__init__()
        self.expr = expr
        self.descriptor = descriptor

    def new_values(self):
        return []

    def update_values(self, v, vnew):
        v.append(vnew)

    def eval(self, ec):
        vs = self.new_values()
        for instance in self.expr.eval(ec):
            try:
                vnew = self.descriptor.__get__(instance, type(instance))
            except AttributeError:
                continue
            self.update_values(
                vs,
                vnew
            )
        return vs


class GetMappingDescriptor(GetDescriptor):
    def __init__(self, expr, descriptor, mapping_factory=dict, **kwargs):
        super().__init__(expr, descriptor, **kwargs)
        self.mapping_factory = mapping_factory

    def new_values(self):
        return self.mapping_factory()

    def update_values(self, v, vnew):
        v.update(vnew)


class GetSequenceDescriptor(GetDescriptor):
    def __init__(self, expr, descriptor, sequence_factory=list, **kwargs):
        super().__init__(expr, descriptor, **kwargs)
        self.sequence_factory = sequence_factory

    def new_values(self):
        return self.sequence_factory()

    def update_values(self, v, vnew):
        v.extend(vnew)


class GetInstances(Expr):
    def __init__(self, expr, class_):
        super().__init__()
        self.expr = expr
        self.class_ = class_

    def eval(self, ec):
        for obj in self.expr.eval(ec):
            if isinstance(obj, self.class_):
                yield obj


class Nth(Expr):
    def __init__(self, expr, nth_expr):
        super().__init__()
        self.expr = expr
        self.nth_expr = nth_expr

    def eval(self, ec):
        n, = self.nth_expr.eval(ec)
        iterable = self.expr.eval(ec)
        if isinstance(n, slice):
            return itertools.islice(
                iterable,
                n.start, n.stop, n.step,
            )

        return itertools.islice(
            self.expr.eval(ec),
            n, n+1,
        )


class ExprFilter(Expr):
    def __init__(self, expr, filter_expr):
        super().__init__()
        self.expr = expr
        self.filter_expr = filter_expr

    def eval(self, ec):
        for value in self.expr.eval(ec):
            sub_ec = copy.copy(ec)
            sub_ec.set_toplevel_object(value)
            filter_result = sub_ec.eval_bool(self.filter_expr)
            if filter_result:
                yield value


class where:
    """
    Wrap the expression `expr` so that it can be used as a filter in ``[]``.
    """

    def __init__(self, expr):
        self.expr = expr


class _BoolOpMixin:
    def eval(self, ec):
        if self.eval_leaf(ec):
            yield True


class CmpOp(_BoolOpMixin, Expr):
    def __init__(self, operand1, operand2, operator):
        super().__init__()
        self.operand1 = operand1
        self.operand2 = operand2
        self.operator = operator

    def eval_leaf(self, ec):
        vs1 = self.operand1.eval_leaf(ec)
        vs2 = self.operand2.eval_leaf(ec)

        for v1 in vs1:
            for v2 in vs2:
                if self.operator(v1, v2):
                    return True
        return False


class NotOp(_BoolOpMixin, Expr):
    def __init__(self, operand):
        super().__init__()
        self.operand = operand

    def eval_leaf(self, ec):
        return not ec.eval_bool(self.operand)


def not_(expr):
    """
    Return the boolean-not of the value of `expr`. A expression value is true
    if it contains at least one element and false otherwise.

    .. seealso::

       :meth:`EvaluationContext.eval_bool`
          which is used behind the scenes to calculate the boolean value of
          `expr`.
       :class:`NotOp`
          which actually implements the operator.
    """
    return NotOp(as_expr(expr))


class Constant(Expr):
    def __init__(self, value):
        super().__init__()
        self.value = value

    def eval(self, ec):
        return [self.value]


# Here be dragons: if you use metaclass=abc.ABCMeta with this class, very
# interesting things will blow up
class PreExpr(_SoftExprMixin):
    @abc.abstractmethod
    def xq_instantiate(self, expr=None):
        pass


class Class(PreExpr):
    def xq_instantiate(self, expr=None):
        if expr is None:
            return ContextInstance(self)
        return GetInstances(expr, self)


class BoundDescriptor(_ExprMixin, PreExpr):
    def __init__(self, class_, descriptor, expr_class, expr_kwargs={},
                 **kwargs):
        super().__init__(**kwargs)
        self.xq_xso_class = class_
        self.xq_descriptor = descriptor
        self.xq_expr_class = expr_class
        self.xq_expr_kwargs = expr_kwargs

    def xq_instantiate(self, expr=None):
        return self.xq_expr_class(
            self.xq_xso_class.xq_instantiate(expr),
            self.xq_descriptor,
            **self.xq_expr_kwargs
        )

    def __getattr__(self, name):
        try:
            return super().__getattr__(name)
        except AttributeError:
            if not name.startswith("xq_"):
                return getattr(self.xq_descriptor, name)
            raise


def as_expr(thing, lhs=None):
    if isinstance(thing, Expr):
        if hasattr(thing, "expr"):
            thing.expr = as_expr(thing.expr, lhs=lhs)
        return thing

    if isinstance(thing, PreExpr):
        return thing.xq_instantiate(lhs)

    return Constant(thing)
