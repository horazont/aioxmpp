import asyncio


class NodeHooks:
    def __init__(self, *, loop=None):
        super().__init__()
        self._loop = loop
        self._map = dict()

    def _setdefault(self, key):
        return self._map.setdefault(key, (set(), set()))

    def __contains__(self, key):
        try:
            queues, futures = self._map[key]
        except KeyError:
            return False
        return queues or futures

    def add_future(self, key, future):
        """
        Add a one-shot *future* listener for the given *key*.
        """
        _, futures = self._setdefault(key)
        futures.add(future)

    def add_queue(self, key, queue):
        """
        Add a *queue* as listener for the given *key*.

        If the queue is full when an element is about to be submitted to the
        queue, the element will be dropped (and no error will be raised from
        :meth:`broadcast`).
        """
        queues, _ = self._setdefault(key)
        queues.add(queue)

    def broadcast_error(self, exc):
        """
        Broadcast an error to all listeners. For futures, the exception given by
        *exc* is set as exception. For queues, nothing is done (there is no
        out-of-band mechanism for posting exceptions).

        Queues remain listening to their respective keys (use :meth:`close` to
        broadcast errors and remove queues).
        """
        to_remove = set()

        for key, (queues, futures) in self._map.items():
            for future in futures:
                future.set_exception(exc)
            futures.clear()
            if not queues:
                to_remove.add(key)

        for key in to_remove:
            del self._map[key]

    def _close_key(self, queues, futures, exc):
        for future in futures:
            future.set_exception(exc)
        futures.clear()
        queues.clear()

    def close(self, key, exc):
        """
        Close all listeners to *key*. For futures, the exception *exc* is
        posted. Queues are simply removed (there is no out-of-band failure
        signalling mechanism for queues).
        """
        try:
            queues, futures = self._map[key]
        except KeyError:
            return
        del self._map[key]

        self._close_key(queues, futures, exc)

    def close_all(self, exc):
        """
        Close all listeners. The same rules as for :meth:`close` apply.
        """
        for queues, futures in self._map.values():
            self._close_key(queues, futures, exc)
        self._map.clear()

    def remove_future(self, key, future):
        """
        Remove a one-shot *future* listener from listening to *key*.

        Raise :class:`KeyError`, if *key* does not exist or *future* was not
        registered for listening to *key*.
        """
        _, futures = self._map[key]
        try:
            futures.remove(future)
        except ValueError:
            raise KeyError(key)

    def remove_queue(self, key, queue):
        """
        Remove a persistent *queue* listener from listening to *key*.

        Raise :class:`KeyError`, if *key* does not exist or *future* was not
        registered for listening to *key*.
        """
        queues, _ = self._map[key]
        try:
            queues.remove(queue)
        except ValueError:
            raise KeyError(key)

    def unicast(self, key, value):
        """
        Unicast a *value* to all listeners for a given *key*. If no listeners
        are registered for *key*, :class:`KeyError` will be raised.

        Return :data:`True` if *value* could be submitted to all targets,
        :data:`False` otherwise (e.g. if a queue ran full).
        """
        queues, futures = self._map[key]
        if not queues and not futures:
            del self._map[key]
            # raise KeyError :)
            self._map[key]
        copied_futures = futures.copy()
        futures.clear()

        some_failed = False
        for queue in queues:
            try:
                queue.put_nowait(value)
            except asyncio.QueueFull:
                some_failed = True

        for future in copied_futures:
            future.set_result(value)

        return not some_failed
