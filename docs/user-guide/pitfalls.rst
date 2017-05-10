Pitfalls to avoid
#################

These are corner cases which should not happen in the common usages, but if they
do, what happens may be very confusing. Here are some tips.

When my application exits uncleanly, it still appears to be online to other resources
=====================================================================================

Congratulations! You are using a server with support for
:xep:`Stream Management <198>`. As you might know, :mod:`aioxmpp` transparently
and automatically uses Stream Management whenever it is available. This means
that :class:`aioxmpp.Client` instances must *always* be
:meth:`aioxmpp.Client.stop`\ -ed properly, so that the stream can be shut down
to prevent it from lingering on the server side. The preferred way to do this
is to use the :meth:`aioxmpp.Client.connected`
:term:`asynchronous context manager`:

.. code-block:: python

    client = aioxmpp.Client()
    with client.connected() as stream:
        # stream is the aioxmpp.stream.StanzaStream of the client
        # do something

When the context manager is left (either with an exception or normally), the
connection is closed cleanly.

If the context manager cannot be used, other means to ensure that
:meth:`aioxmpp.Client.stop` is called and the client is given enough time to
shut the connection down cleanly need to be applied. This can be done in the
following manner:

.. code-block:: python

    if client.running:
        fut = asyncio.Future()
        client.on_stopped.connect(fut, client.on_stopped.AUTO_FUTURE)
        client.on_failure.connect(fut, client.on_failure.AUTO_FUTURE)
        try:
            yield from fut
        except:
            # we are shutting down, ignore any exceptions from on_failure
            pass

Ensure that this snippet is executed before the application exits, even in
the case that an error occured.

.. note::

   You may be asking "But why is the Connection Reset by Peer the server must
   be getting after my application crashed not enough?". The whole reason for
   Stream Management is to make it possible for the server to ignore such
   errors which may very well occur if network connectivity is briefly
   interrupted (for example when switching between networks, or your ISP has a
   power failure, or you reboot your modem or something like that). Stream
   Management allows to resume an uncleanly closed stream up to a certain
   timeout (as (possibly dynamically) determined by the server). Making errors
   such as Connection Reset by Peer break such a stream would defeat the
   purpose of Stream Management.

I am trying to connect to a bare IP and I get a DNS error
=========================================================

For example, when trying to connect to ``192.168.122.1``, you may see::

    Traceback (most recent call last):
      File "/home/horazont/aioxmpp/aioxmpp/network.py", line 272, in repeated_query
        raise_on_no_answer=False
      File "/usr/lib/python3.4/asyncio/futures.py", line 388, in __iter__
        yield self  # This tells Task to wait for completion.
      File "/usr/lib/python3.4/asyncio/tasks.py", line 286, in _wakeup
        value = future.result()
      File "/usr/lib/python3.4/asyncio/futures.py", line 277, in result
        raise self._exception
      File "/usr/lib/python3.4/concurrent/futures/thread.py", line 54, in run
        result = self.fn(*self.args, **self.kwargs)
      File "/home/horazont/.local/lib/python3.4/site-packages/dns/resolver.py", line 1051, in query
        raise NXDOMAIN(qnames=qnames_to_try, responses=nxdomain_responses)
    dns.resolver.NXDOMAIN: None of DNS query names exist: _xmpp-client._tcp.192.168.122.1., _xmpp-client._tcp.192.168.122.1.

    During handling of the above exception, another exception occurred:

    Traceback (most recent call last):
      File "/home/horazont/aioxmpp/aioxmpp/node.py", line 710, in _on_main_done
        task.result()
      File "/usr/lib/python3.4/asyncio/futures.py", line 277, in result
        raise self._exception
      File "/usr/lib/python3.4/asyncio/tasks.py", line 233, in _step
        result = coro.throw(exc)
      File "/home/horazont/aioxmpp/aioxmpp/node.py", line 868, in _main
        yield from self._main_impl()
      File "/home/horazont/aioxmpp/aioxmpp/node.py", line 830, in _main_impl
        logger=self.logger)
      File "/home/horazont/aioxmpp/aioxmpp/node.py", line 337, in connect_xmlstream
        logger=logger,
      File "/home/horazont/aioxmpp/aioxmpp/node.py", line 142, in discover_connectors
        "xmpp-client",
      File "/home/horazont/aioxmpp/aioxmpp/network.py", line 318, in lookup_srv
        **kwargs)
      File "/home/horazont/aioxmpp/aioxmpp/network.py", line 280, in repeated_query
        "nameserver error, most likely DNSSEC validation failed",
    aioxmpp.network.ValidationError: nameserver error, most likely DNSSEC validation failed

You should be using :attr:`aioxmpp.Client.override_peer` or an equivalent
mechansim. Note that the exception will still occur if the connection attempt to
the override fails. Bare IPs as target hosts are generally not a good idea.
