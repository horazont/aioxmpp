import unittest
import unittest.mock

from aioxmpp.callbacks import (
    TagDispatcher,
    TagListener,
    OneshotTagListener,
)


class TestTagListener(unittest.TestCase):
    def test_data(self):
        ondata = unittest.mock.Mock()

        obj = object()

        listener = TagListener(ondata=ondata)
        listener.data(obj)
        ondata.assert_called_once_with(obj)

    def test_uninitialized_error(self):
        ondata = unittest.mock.Mock()

        listener = TagListener(ondata=ondata)
        listener.error(ValueError())

    def test_error(self):
        ondata = unittest.mock.Mock()
        onerror = unittest.mock.Mock()

        exc = ValueError()

        listener = TagListener(ondata, onerror)
        listener.error(exc)

        ondata.assert_not_called()
        onerror.assert_called_once_with(exc)


class TestTagDispatcher(unittest.TestCase):
    def test_add_callback(self):
        mock = unittest.mock.Mock()

        nh = TagDispatcher()
        nh.add_callback("tag", mock)
        with self.assertRaisesRegexp(ValueError,
                                     "only one listener is allowed"):
            nh.add_callback("tag", mock)

    def test_add_listener(self):
        mock = unittest.mock.Mock()

        l = TagListener(mock)

        nh = TagDispatcher()
        nh.add_listener("tag", l)
        with self.assertRaisesRegexp(ValueError,
                                     "only one listener is allowed"):
            nh.add_listener("tag", l)

    def test_add_future(self):
        mock = unittest.mock.Mock()
        obj = object()

        nh = TagDispatcher()
        nh.add_future("tag", mock)
        nh.unicast("tag", obj)
        with self.assertRaises(KeyError):
            # futures must be oneshots
            nh.unicast("tag", obj)

        nh.add_future("tag", mock)
        nh.broadcast_error(obj)
        with self.assertRaises(KeyError):
            # futures must be oneshots
            nh.unicast("tag", obj)

        self.assertSequenceEqual(
            [
                unittest.mock.call.set_result(obj),
                unittest.mock.call.set_exception(obj),
            ],
            mock.mock_calls
        )

    def test_unicast(self):
        mock = unittest.mock.Mock()
        mock.return_value = False
        obj = object()

        nh = TagDispatcher()
        nh.add_callback("tag", mock)
        nh.unicast("tag", obj)
        nh.unicast("tag", obj)

        self.assertSequenceEqual(
            [
                unittest.mock.call(obj),
                unittest.mock.call(obj),
            ],
            mock.mock_calls
        )

    def test_unicast_fails_for_nonexistent(self):
        obj = object()
        nh = TagDispatcher()
        with self.assertRaises(KeyError):
            nh.unicast("tag", obj)

    def test_unicast_to_oneshot(self):
        mock = unittest.mock.Mock()
        obj = object()

        l = OneshotTagListener(mock)

        nh = TagDispatcher()
        nh.add_future("tag", mock)

        nh.unicast("tag", obj)
        with self.assertRaises(KeyError):
            nh.unicast("tag", obj)

        self.assertSequenceEqual(
            [
                unittest.mock.call(obj)
            ],
            mock.mock_calls
        )

    def test_unicast_removes_for_true_result(self):
        mock = unittest.mock.Mock()
        mock.return_value = True
        obj = object()

        nh = TagDispatcher()
        nh.add_callback("tag", mock)
        nh.unicast("tag", obj)
        with self.assertRaises(KeyError):
            nh.unicast("tag", obj)

        mock.assert_called_once_with(obj)

    def test_broadcast_error_to_oneshot(self):
        mock = unittest.mock.Mock()
        obj = object()

        l = OneshotTagListener(mock)

        nh = TagDispatcher()
        nh.add_future("tag", mock)

        nh.broadcast_error(obj)
        with self.assertRaises(KeyError):
            nh.unicast("tag", obj)

        self.assertSequenceEqual(
            [
                unittest.mock.call(obj)
            ],
            mock.mock_calls
        )

    def test_remove_listener(self):
        mock = unittest.mock.Mock()
        nh = TagDispatcher()
        nh.add_callback("tag", mock)
        nh.remove_listener("tag")
        with self.assertRaises(KeyError):
            nh.unicast("tag", object())
        mock.assert_not_called()

    def test_broadcast_error(self):
        data = unittest.mock.Mock()
        error1 = unittest.mock.Mock()
        error1.return_value = False
        error2 = unittest.mock.Mock()
        error2.return_value = False

        l1 = TagListener(data, error1)
        l2 = TagListener(data, error2)

        obj = object()

        nh = TagDispatcher()
        nh.add_listener("tag1", l1)
        nh.add_listener("tag2", l2)

        nh.broadcast_error(obj)
        nh.broadcast_error(obj)

        data.assert_not_called()
        self.assertSequenceEqual(
            [
                unittest.mock.call(obj),
                unittest.mock.call(obj),
            ],
            error1.mock_calls
        )
        self.assertSequenceEqual(
            [
                unittest.mock.call(obj),
                unittest.mock.call(obj),
            ],
            error2.mock_calls
        )

    def test_broadcast_error_removes_on_true_result(self):
        data = unittest.mock.Mock()
        error1 = unittest.mock.Mock()
        error1.return_value = True

        l1 = TagListener(data, error1)

        obj = object()

        nh = TagDispatcher()
        nh.add_listener("tag1", l1)

        nh.broadcast_error(obj)
        nh.broadcast_error(obj)

        data.assert_not_called()
        self.assertSequenceEqual(
            [
                unittest.mock.call(obj),
            ],
            error1.mock_calls
        )

    def test_close(self):
        data = unittest.mock.Mock()
        error1 = unittest.mock.Mock()
        error2 = unittest.mock.Mock()

        l1 = TagListener(data, error1)
        l2 = TagListener(data, error2)

        obj = object()

        nh = TagDispatcher()
        nh.add_listener("tag1", l1)
        nh.add_listener("tag2", l2)

        nh.close_all(obj)

        data.assert_not_called()
        error1.assert_called_once_with(obj)
        error2.assert_called_once_with(obj)

        with self.assertRaises(KeyError):
            nh.remove_listener("tag1")
        with self.assertRaises(KeyError):
            nh.remove_listener("tag2")
        with self.assertRaises(KeyError):
            nh.unicast("tag1", None)
        with self.assertRaises(KeyError):
            nh.unicast("tag2", None)
