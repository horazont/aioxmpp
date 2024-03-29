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
from sphinx.domains.python import PyModule, PyMethod

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


class SignalAwareMethodDocumenter(MethodDocumenter):
    objtype = 'signal'
    priority = 4

    def import_object(self):
        ret = super().import_object()
        if not ret:
            return ret

        self.directivetype = "signal"

        return ret


class PySignal(PyMethod):
    def handle_signature(self, sig, signode):
        ret = super().handle_signature(sig, signode)
        signode.insert(0, addnodes.desc_annotation('signal ', 'signal '))
        return ret

    def run(self):
        self.name = 'py:method'
        return super().run()


class PySyncSignal(PyMethod):
    def handle_signature(self, sig, signode):
        ret = super().handle_signature(sig, signode)
        signode.insert(0, addnodes.desc_annotation('async signal ', 'async signal '))
        return ret

    def run(self):
        self.name = 'py:method'
        return super().run()


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
    app.add_directive_to_domain('py', 'signal', PySignal)
    app.add_directive_to_domain('py', 'syncsignal', PySyncSignal)
    app.add_autodocumenter(SignalAwareMethodDocumenter)
    return {'version': '1.0', 'parallel_read_safe': True}
