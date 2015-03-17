"""
:mod:`aioxmpp.plugins.base` --- Base classes for plugin implementations
############################################################################

This module provides a base class useful for plugin development.

.. autoclass:: Service([node...], [loop=None], [logger=None])

"""

import asyncio
import logging

logger = logging.getLogger(__name__)

class Service:
    """
    Base class for services (see the services user guide :ref:`ug-services`).

    On construction, the :class:`aioxmpp.node.Client` on which the service
    is supposed to work has to be passed. The Service is then bound to that
    specific node.

    To disconnect a service from a node, call :meth:`close`. Note that a closed
    service cannot be used anymore. To detect a closed service, check the
    :attr:`node` attriubte against :data:`None`.

    .. automethod:: close

    .. autoattribute:: node

    The remaining methods are only relevant to developers subclassing
    :class:`Service` to implement their own services:

    .. automethod:: _start_task

    .. automethod:: _handle_task_done

    .. automethod:: _on_task_error

    .. automethod:: _on_task_success
    """

    def __init__(self, node, loop=None, logger=None):
        self.logger = logging.getLogger(type(self).__module__ +
                                        "." + type(self).__qualname__)
        self._loop = loop or asyncio.get_event_loop()
        self._node = node
        self._tasks = set()

    def _handle_task_done(self, task):
        """
        This callback is attached to all tasks spawned using
        :meth:`_start_task`. If the task terminates by a way other than being
        cancelled, :meth:`_on_task_error` (if the task terminated with an
        exception) or :meth:`_on_task_success` (if the task terminated
        normally) is called.
        """
        self._tasks.discard(task)
        try:
            result = task.result()
        except asyncio.CancelledError:
            pass
        except Exception as err:
            self._on_task_error(task, err)
        else:
            self._on_task_success(task, result)

    def _on_task_error(self, task, error):
        """
        This method is called by :meth:`_handle_task_done` with the *error*
        value of the *task*.

        The default implementation logs the task and the exception as
        :data:`~logging.ERROR` message.
        """

        if hasattr(error, "__traceback__"):
            tb = error.__traceback__
        else:
            tb = None

        self.logger.error(
            "task %s failed:",
            task,
            exc_info=(type(error), error, error.__traceback__)
        )

    def _on_task_success(self, task, result):
        """
        This method is called by :meth:`_handle_task_done` with the *result*
        value of the *task*.

        The default implementation logs the task and the result as
        :data:`~logging.INFO` message.
        """
        self.logger.info(
            "unhandled task (%s) result: %r",
            task, result
        )

    def _start_task(self, coro):
        """
        Spawn a coroutine and add the method :meth:`_handle_task_done` as
        callback. Return the :class:`asyncio.Task` object.
        """
        task = asyncio.async(coro, loop=self._loop)
        task.add_done_callback(self._handle_task_done)
        self._tasks.add(task)
        return task

    def close(self):
        """
        Detach the service from a node and stop any coroutines the service has
        spawned.
        """
        for task in self._tasks:
            if not task.done():
                task.cancel()
        self._node = None

    @property
    def node(self):
        return self._node
