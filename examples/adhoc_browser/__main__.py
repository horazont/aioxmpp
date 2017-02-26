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
