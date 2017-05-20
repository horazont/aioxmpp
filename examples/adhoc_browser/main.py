########################################################################
# File name: main.py
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
import asyncio
import sys

import PyQt5.Qt as Qt

import aioxmpp

from framework import Example

from .utils import asyncify_blocking
try:
    from .ui.main import Ui_MainWindow
except ImportError:
    print("You didn’t run make, I’ll try to do it for you...",
          file=sys.stderr)
    import subprocess
    try:
        subprocess.check_call(["make"])
        from .ui.main import Ui_MainWindow
    except Exception:
        print("Nope, that didn’t work out. "
              "You’ll have to fix that yourself. Sorry.",
              file=sys.stderr)
        raise

from .execute import Executor

if not hasattr(asyncio, "async"):
    setattr(asyncio, "async", asyncio.ensure_future)


class DiscoItemsModel(Qt.QAbstractTableModel):
    COLUMN_NAME = 0
    COLUMN_JID = 1
    COLUMN_NODE = 2
    COLUMN_COUNT = 3

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []

    def replace(self, items):
        self.beginResetModel()
        self._items[:] = items
        self.endResetModel()

    def rowCount(self, parent):
        if parent.isValid():
            return 0
        return len(self._items)

    def columnCount(self, parent):
        return self.COLUMN_COUNT

    def data(self, index, role):
        if role != Qt.Qt.DisplayRole:
            return
        if not index.isValid():
            return

        item = self._items[index.row()]
        return {
            self.COLUMN_NAME: item.name,
            self.COLUMN_JID: str(item.jid),
            self.COLUMN_NODE: item.node or "",
        }.get(index.column())

    def headerData(self, section, orientation, role):
        if orientation != Qt.Qt.Horizontal:
            return
        if role != Qt.Qt.DisplayRole:
            return
        return {
            self.COLUMN_NAME: "Name",
            self.COLUMN_JID: "JID",
            self.COLUMN_NODE: "Node",
        }.get(section)


class MainWindow(Qt.QMainWindow):
    def __init__(self, close_fut):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.ui.btn_scan.clicked.connect(
            self.scan
        )

        self.disco_model = DiscoItemsModel()
        self.ui.disco_items.setModel(self.disco_model)
        self.ui.disco_items.activated.connect(self.disco_item_activated)

        self.commands_model = DiscoItemsModel()
        self.ui.commands.setModel(self.commands_model)
        self.ui.commands.activated.connect(self.command_activated)

        self._close_fut = close_fut

    def disco_item_activated(self, index):
        if not index.isValid():
            return

        jid = self.disco_model.data(
            self.disco_model.index(
                index.row(),
                self.disco_model.COLUMN_JID,
                index.parent(),
            ),
            Qt.Qt.DisplayRole)

        self.ui.target_jid.setText(jid)
        self.scan()

    @asyncify_blocking
    @asyncio.coroutine
    def command_activated(self, index):
        if not index.isValid():
            return

        jid = aioxmpp.JID.fromstr(
            self.commands_model.data(
                self.commands_model.index(
                    index.row(),
                    self.disco_model.COLUMN_JID,
                    index.parent(),
                ),
                Qt.Qt.DisplayRole)
        )

        node = self.commands_model.data(
            self.commands_model.index(
                index.row(),
                self.disco_model.COLUMN_NODE,
                index.parent(),
            ),
            Qt.Qt.DisplayRole)

        session_fut = asyncio.ensure_future(
            self.adhoc_svc.execute(jid, node)
        )
        dlg = Executor(self)
        dlg.run_with_session_fut(node, session_fut)

    @asyncify_blocking
    @asyncio.coroutine
    def scan(self, *args, **kwargs):
        jid = aioxmpp.JID.fromstr(self.ui.target_jid.text())
        items = yield from self.disco_svc.query_items(
            jid
        )
        commands = yield from self.adhoc_svc.get_commands(
            jid
        )

        self.disco_model.replace(items.items)
        self.commands_model.replace(commands)

    def closeEvent(self, ev):
        if self._close_fut.done():
            return super().closeEvent(ev)
        self._close_fut.set_result(None)


class AdHocBrowser(Example):
    def __init__(self):
        super().__init__()
        self._close = asyncio.Future()
        self._mainwindow = MainWindow(self._close)

    @asyncio.coroutine
    def _main(self):
        self._mainwindow.client = self.client
        self._mainwindow.disco_svc = self.disco_svc
        self._mainwindow.adhoc_svc = self.adhoc_svc
        self._mainwindow.show()
        try:
            yield from self._close
        except:
            self._mainwindow.close()

    def _established(self):
        self._mainwindow.statusBar().showMessage(
            "connected as {}".format(self.client.local_jid)
        )
        if not self._mainwindow.ui.target_jid.text():
            self._mainwindow.ui.target_jid.setText(
                str(self.client.local_jid.domain)
            )

    @asyncio.coroutine
    def run_example(self):
        def kill(*args):
            nonlocal task
            if task is not None:
                task.cancel()

        self.client = self.make_simple_client()
        self.disco_svc = self.client.summon(aioxmpp.DiscoClient)
        self.adhoc_svc = self.client.summon(aioxmpp.AdHocClient)
        self.client.on_failure.connect(kill)
        self.client.on_stream_established.connect(self._established)

        cm = self.client.connected()
        aexit = cm.__aexit__
        yield from cm.__aenter__()
        try:
            task = asyncio.ensure_future(self._main())
            yield from task
        except:
            if not (yield from aexit(*sys.exc_info())):
                raise
        else:
            yield from aexit(None, None, None)
