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
