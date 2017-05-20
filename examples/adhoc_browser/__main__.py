########################################################################
# File name: __main__.py
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
import gc
import sys

try:
    import quamash
    import PyQt5.Qt as Qt
except ImportError as exc:
    print(exc, file=sys.stderr)
    print("This example requires quamash and PyQt5.", file=sys.stderr)

from adhoc_browser.main import AdHocBrowser

qapp = Qt.QApplication(sys.argv)
qapp.setQuitOnLastWindowClosed(False)
asyncio.set_event_loop(quamash.QEventLoop(app=qapp))
loop = asyncio.get_event_loop()
try:
    example = AdHocBrowser()
    example.prepare_argparse()
    example.configure()
    loop.run_until_complete(example.run_example())
finally:
    loop.close()
asyncio.set_event_loop(None)
del example, loop, qapp
gc.collect()
