"""
:mod:`asyncio_xmpp.plugins.base` --- Base classes for plugin implementations
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

    On construction, the nodes passed via *nodes* are automatically added to the
    service.

    The public user interface for any :class:`Service` consists of the following
    methods:

    .. automethod:: add_node

    .. automethod:: remove_node

    The remaining methods are only relevant to developers subclassing
    :class:`Service` to implement their own services:

    .. automethod:: _add_node

    .. automethod:: _remove_node

    .. automethod:: _start_task

    .. automethod:: _handle_task_done

    .. automethod:: _on_task_error

    .. automethod:: _on_task_success
    """

    def __init__(self, *nodes, loop=None, logger=None):
        self.logger = logging.getLogger(type(self).__module__ +
                                        "." + type(self).__qualname__)
        self._loop = loop or asyncio.get_event_loop()
        self._nodes = set()

        for node in nodes:
            self.add_node(node)

    def _add_node(self, node):
        """
        Subclasses have to implement :meth:`_add_node`. It is called whenever
        :meth:`add_node` is called with a *new* node, that is, a node which has
        not been added yet.
        """

    def _handle_task_done(self, task):
        """
        This callback is attached to all tasks spawned using
        :meth:`_start_task`. If the task terminates by a way other than being
        cancelled, :meth:`_on_task_error` (if the task terminated with an
        exception) or :meth:`_on_task_success` (if the task terminated
        normally) is called.
        """
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

    def _remove_node(self, node):
        """
        Subclasses have to implement :meth:`_remove_node`. It is called whenever
        :meth:`remove_node` is called on a node which is currently registered
        with the Service.
        """

    def _start_task(self, coro):
        """
        Spawn a coroutine and add the method :meth:`_handle_task_done` as
        callback. Return the :class:`asyncio.Task` object.
        """
        task = asyncio.async(coro, loop=self._loop)
        task.add_done_callback(self._handle_task_done)
        return task

    def add_node(self, node):
        """
        Attach the service to the given :class:`~.node.Client` *node*. The exact
        meaning of having the service attached to a node is dependent on the
        service. In general, services will handle IQ requests or other stanzas
        and process them in a meaningful way. To do this, they have to be
        attached to one or more nodes whose stanzas they are supposed to
        handle.

        Attempts to add the same node multiple times will be ignored.
        """
        if node in self._nodes:
            return

        self._nodes.add(node)
        self._add_node(node)

    def remove_node(self, node):
        """
        Detach the service from a *node*. The node must have been added via
        :meth:`add_node` before, otherwise :class:`KeyError` is raised.
        """
        if node in self._nodes:
            self._remove_node(node)
        self._nodes.remove(node)
