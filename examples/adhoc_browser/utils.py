########################################################################
# File name: utils.py
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
import functools

import PyQt5.Qt as Qt


def asyncified_done(parent, task):
    try:
        task.result()
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        if parent is not None:
            Qt.QMessageBox.critical(
                parent,
                "Job failed",
                str(exc),
            )


def asyncified_unblock(dlg, cursor, task):
    dlg.setCursor(cursor)
    dlg.setEnabled(True)


def asyncify(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        task = asyncio.async(fn(*args, **kwargs))
        task.add_done_callback(functools.partial(asyncified_done, None))
    return wrapper


def asyncify_blocking(fn):
    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        prev_cursor = self.cursor()
        self.setEnabled(False)
        self.setCursor(Qt.Qt.WaitCursor)
        try:
            task = asyncio.async(fn(self, *args, **kwargs))
        except:
            self.setEnabled(True)
            self.setCursor(prev_cursor)
            raise
        task.add_done_callback(functools.partial(
            asyncified_done,
            self))
        task.add_done_callback(functools.partial(
            asyncified_unblock,
            self, prev_cursor))

    return wrapper
