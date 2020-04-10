########################################################################
# File name: aioxmppspecific.py
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
# General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this program.  If not, see
# <http://www.gnu.org/licenses/>.
#
########################################################################
import asyncio

from sphinx import addnodes
from sphinx.domains.python import PyModulelevel, PyClassmember

from docutils import nodes, utils
from docutils.parsers.rst import roles

from sphinx.locale import _

from sphinx.environment import default_settings

from sphinx.ext.autodoc import (
    MethodDocumenter,
    FunctionDocumenter,
    ModuleLevelDocumenter
)

from sphinx.util.nodes import (
    split_explicit_title
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


class DecoratorDocumenter(FunctionDocumenter):
    objtype = 'decorator'
    priority = 3


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


class SignalAwareMethodDocumenter(MethodDocumenter):
    objtype = 'signal'
    priority = 4

    def import_object(self):
        ret = super().import_object()
        if not ret:
            return ret

        self.directivetype = "signal"

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


def xep_role(typ, rawtext, text, lineno, inliner,
             options={}, content=[]):
    """Role for PEP/RFC references that generate an index entry."""
    env = inliner.document.settings.env
    if not typ:
        typ = env.config.default_role
    else:
        typ = typ.lower()
    has_explicit_title, title, target = split_explicit_title(text)
    title = utils.unescape(title)
    target = utils.unescape(target)
    targetid = 'index-%s' % env.new_serialno('index')
    anchor = ''
    anchorindex = target.find('#')
    if anchorindex > 0:
        target, anchor = target[:anchorindex], target[anchorindex:]
    try:
        xepnum = int(target)
    except ValueError:
        msg = inliner.reporter.error('invalid XEP number %s' % target,
                                     line=lineno)
        prb = inliner.problematic(rawtext, rawtext, msg)
        return [prb], [msg]
    target = "{:04d}".format(xepnum)
    if not has_explicit_title:
        title = "XEP-" + target
    indexnode = addnodes.index()
    targetnode = nodes.target('', '', ids=[targetid])
    inliner.document.note_explicit_target(targetnode)
    indexnode['entries'] = [
        ('single', _('XMPP Extension Protocols (XEPs); XEP %s') % target,
         targetid, '', None)]
    ref = inliner.document.settings.xep_base_url + 'xep-%04d.html' % xepnum
    rn = nodes.reference(title, title, internal=False, refuri=ref+anchor,
                         classes=[typ])
    return [indexnode, targetnode, rn], []


roles.register_local_role("xep", xep_role)


default_settings["xep_base_url"] = "https://xmpp.org/extensions/"


def setup(app):
    app.add_directive_to_domain('py', 'coroutinefunction', PyCoroutineFunction)
    app.add_directive_to_domain('py', 'coroutinemethod', PyCoroutineMethod)
    app.add_directive_to_domain('py', 'signal', PySignal)
    app.add_directive_to_domain('py', 'syncsignal', PySyncSignal)
    app.add_autodocumenter(CoroutineAwareFunctionDocumenter)
    app.add_autodocumenter(CoroutineAwareMethodDocumenter)
    app.add_autodocumenter(SignalAwareMethodDocumenter)
    app.add_autodocumenter(DecoratorDocumenter)
    return {'version': '1.0', 'parallel_read_safe': True}
