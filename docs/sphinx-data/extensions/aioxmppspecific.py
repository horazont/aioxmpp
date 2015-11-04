import asyncio

from sphinx import addnodes
from sphinx.domains.python import PyModulelevel, PyClassmember

from sphinx.ext.autodoc import (
    MethodDocumenter,
    FunctionDocumenter,
    ModuleLevelDocumenter
)


class PyCoroutineMixin(object):
    def handle_signature(self, sig, signode):
        ret = super(PyCoroutineMixin, self).handle_signature(sig, signode)
        signode.insert(0, addnodes.desc_annotation('coroutine ', 'coroutine '))
        return ret


class PyCoroutineFunction(PyCoroutineMixin, PyModulelevel):
    def run(self):
        self.name = 'py:function'
        return PyModulelevel.run(self)


class PyCoroutineMethod(PyCoroutineMixin, PyClassmember):
    def run(self):
        self.name = 'py:method'
        return PyClassmember.run(self)


class CoroutineAwareFunctionDocumenter(FunctionDocumenter):
    objtype = 'function'
    priority = 3

    def import_object(self):
        ret = ModuleLevelDocumenter.import_object(self)
        if not ret:
            return ret

        if asyncio.iscoroutinefunction(self.object):
            self.directivetype = "coroutinefunction"

        return ret


class CoroutineAwareMethodDocumenter(MethodDocumenter):
    objtype = 'method'
    priority = 4

    def import_object(self):
        ret = super().import_object()
        if not ret:
            return ret

        if     (self.directivetype == "method" and
                asyncio.iscoroutinefunction(self.object)):
            self.directivetype = "coroutinemethod"

        return ret


class PySignal(PyClassmember):
    def handle_signature(self, sig, signode):
        ret = super(PySignal, self).handle_signature(sig, signode)
        signode.insert(0, addnodes.desc_annotation('signal ', 'signal '))
        return ret

    def run(self):
        self.name = 'py:method'
        return PyClassmember.run(self)


class PySyncSignal(PyClassmember):
    def handle_signature(self, sig, signode):
        ret = super(PySyncSignal, self).handle_signature(sig, signode)
        signode.insert(0, addnodes.desc_annotation('coroutine signal ', 'coroutine signal '))
        return ret

    def run(self):
        self.name = 'py:method'
        return PyClassmember.run(self)


def setup(app):
    app.add_directive_to_domain('py', 'coroutinefunction', PyCoroutineFunction)
    app.add_directive_to_domain('py', 'coroutinemethod', PyCoroutineMethod)
    app.add_directive_to_domain('py', 'signal', PySignal)
    app.add_directive_to_domain('py', 'syncsignal', PySyncSignal)
    app.add_autodocumenter(CoroutineAwareFunctionDocumenter)
    app.add_autodocumenter(CoroutineAwareMethodDocumenter)
    return {'version': '1.0', 'parallel_read_safe': True}
