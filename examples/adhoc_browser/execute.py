########################################################################
# File name: execute.py
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
import html

import PyQt5.Qt as Qt

import aioxmpp.adhoc

from .utils import asyncify, asyncify_blocking
from .ui.form import Ui_FormDialog


class Executor(Qt.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_FormDialog()
        self.ui.setupUi(self)
        self.base_title = self.windowTitle()
        self.session = None

        self.action_buttons = {
            aioxmpp.adhoc.ActionType.NEXT: self.ui.btn_next,
            aioxmpp.adhoc.ActionType.PREV: self.ui.btn_prev,
            aioxmpp.adhoc.ActionType.CANCEL: self.ui.btn_cancel,
            aioxmpp.adhoc.ActionType.COMPLETE: self.ui.btn_complete,
        }

        self.ui.btn_close.clicked.connect(self._close)
        self.ui.btn_next.clicked.connect(self._next)
        self.ui.btn_prev.clicked.connect(self._prev)
        self.ui.btn_cancel.clicked.connect(self._cancel)
        self.ui.btn_complete.clicked.connect(self._complete)

        self.fieldmap = {}
        self.form_area = None

    def _close(self):
        self.close()

    def _next(self):
        self._action(aioxmpp.adhoc.ActionType.NEXT)

    def _prev(self):
        self._action(aioxmpp.adhoc.ActionType.PREV)

    def _cancel(self):
        self.close()

    def _complete(self):
        self._action(aioxmpp.adhoc.ActionType.COMPLETE)

    @asyncify_blocking
    async def run_with_session_fut(self, name, session_fut):
        self.setWindowTitle("{} - {}".format(
            name,
            self.base_title
        ))
        self.show()
        try:
            self.session = await session_fut
        except Exception as exc:
            self.fail(exc)
            return
        self.response_received()

    def _update_buttons(self):
        status = self.session.status
        if status != aioxmpp.adhoc.CommandStatus.EXECUTING:
            self.ui.btn_cancel.hide()
            self.ui.btn_next.hide()
            self.ui.btn_prev.hide()
            self.ui.btn_complete.hide()
            self.ui.btn_close.show()
        else:
            self.ui.btn_close.hide()
            allowed_actions = self.session.allowed_actions
            for action, btn in self.action_buttons.items():
                if action in allowed_actions:
                    btn.show()
                else:
                    btn.hide()

    def _update_notes(self):
        notes = self.session.response.notes
        if not notes:
            self.ui.notes_area.hide()
            return

        self.ui.notes_area.show()
        source_parts = []
        for note in notes:
            print(note.type_, note.body)
            source_parts.append("<p><b>{}: </b>{}</p>".format(
                html.escape(note.type_.value),
                "</p><p>".join(html.escape(note.body or "").split("\n"))
            ))

        self.ui.notes_area.setText("\n".join(source_parts))

    def _update_form(self):
        payload = self.session.first_payload
        if not isinstance(payload, aioxmpp.forms.Data):
            self.ui.form_widget.hide()
            return

        self.ui.form_widget.show()
        if payload.title:
            self.ui.title.show()
            self.ui.title.setText(payload.title)
        else:
            self.ui.title.hide()

        if payload.instructions:
            self.ui.instructions.show()
            self.ui.instructions.setText(
                "<p>{}</p>".format(
                    "</p><p>".join(map(html.escape, payload.instructions))
                )
            )
        else:
            self.ui.instructions.hide()

        if self.form_area is not None:
            self.ui.form_widget.layout().removeWidget(self.form_area)
            self.ui.form_widget.children().remove(self.form_area)
            self.form_area.deleteLater()

        self.form_area = Qt.QScrollArea()
        layout = Qt.QFormLayout()
        self.form_area.setLayout(layout)
        self.ui.form_widget.layout().addWidget(self.form_area)

        self.fieldmap = {}
        for field in payload.fields:
            if field.var == "FORM_TYPE":
                continue
            label, widget = None, None
            if field.type_ == aioxmpp.forms.FieldType.FIXED:
                label = Qt.QLabel(field.values[0])
                layout.addRow(
                    label
                )
            elif field.type_ in {aioxmpp.forms.FieldType.LIST_SINGLE,
                                 aioxmpp.forms.FieldType.LIST_MULTI}:
                label = Qt.QLabel(field.label)
                widget = Qt.QListWidget()
                for opt_value, opt_label in sorted(field.options.items()):
                    item = Qt.QListWidgetItem(opt_label, widget)
                    item.setData(Qt.Qt.UserRole, opt_value)
                    widget.addItem(item)

                if field.type_.is_multivalued:
                    widget.setSelectionMode(
                        Qt.QAbstractItemView.MultiSelection
                    )
                else:
                    widget.setSelectionMode(
                        Qt.QAbstractItemView.SingleSelection
                    )
                layout.addRow(label, widget)

            elif field.type_ in {aioxmpp.forms.FieldType.TEXT_SINGLE,
                                 aioxmpp.forms.FieldType.JID_SINGLE}:
                label = Qt.QLabel(field.label)
                widget = Qt.QLineEdit()
                if field.values:
                    widget.setText(field.values[0])
                layout.addRow(label, widget)

            elif field.type_ in {aioxmpp.forms.FieldType.TEXT_PRIVATE}:
                label = Qt.QLabel(field.label)
                widget = Qt.QLineEdit()
                widget.setEchoMode(Qt.QLineEdit.Password)
                widget.setInputMethodHints(Qt.Qt.ImhHiddenText |
                                           Qt.Qt.ImhNoPredictiveText |
                                           Qt.Qt.ImhNoAutoUppercase)
                if field.values:
                    widget.setText(field.values[0])
                layout.addRow(label, widget)

            elif field.type_ in {aioxmpp.forms.FieldType.TEXT_MULTI,
                                 aioxmpp.forms.FieldType.JID_MULTI}:
                label = Qt.QLabel(field.label)
                widget = Qt.QTextEdit()
                widget.setText("\n".join(field.values))
                widget.setAcceptRichText(False)
                layout.addRow(label, widget)

            else:
                self.fail("unhandled field type: {}".format(field.type_))

            self.fieldmap[field.var] = label, widget

    def _fill_form(self):
        for field in self.session.first_payload.fields:
            try:
                _, widget = self.fieldmap[field.var]
            except KeyError:
                continue
            if widget is None:
                continue

            if field.type_ in {aioxmpp.forms.FieldType.LIST_SINGLE,
                               aioxmpp.forms.FieldType.LIST_MULTI}:
                # widget is list widget
                selected = []
                for index in widget.selectionModel().selectedIndexes():
                    selected.append(
                        widget.model().data(
                            index,
                            Qt.Qt.UserRole
                        )
                    )

                field.values[:] = selected

            elif field.type_ in {aioxmpp.forms.FieldType.JID_SINGLE,
                                 aioxmpp.forms.FieldType.TEXT_SINGLE,
                                 aioxmpp.forms.FieldType.TEXT_PRIVATE}:
                # widget is line edit
                field.values[:] = [widget.text()]

            elif field.type_ in {aioxmpp.forms.FieldType.JID_MULTI,
                                 aioxmpp.forms.FieldType.TEXT_MULTI}:
                field.values[:] = widget.toPlainText().split("\n")

    def _action(self, type_):
        self._fill_form()
        self._submit_action(type_)

    @asyncify_blocking
    async def _submit_action(self, type_):
        await self.session.proceed(action=type_)
        self.response_received()

    def response_received(self):
        try:
            self.ui.status.setText(str(self.session.status))
            self._update_buttons()
            self._update_notes()
            self._update_form()
        except Exception as exc:
            self.fail(str(exc))

    def fail(self, message):
        Qt.QMessageBox.critical(
            self.parent(),
            "Error",
            message,
        )
        self.close()

    @asyncify
    async def closeEvent(self, ev):
        if self.session is not None:
            await self.session.close()
        return super().closeEvent(ev)
