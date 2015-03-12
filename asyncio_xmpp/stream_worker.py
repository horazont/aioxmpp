import asyncio
import functools
import logging

from . import stanza, errors

from .utils import namespaces


class StanzaBroker:
    def __init__(self,
                 on_send_stanza,
                 *,
                 loop=None,
                 base_logger=logging.getLogger("asyncio_xmpp")):
        super().__init__()
        self._loop = loop or asyncio.get_event_loop()
        self._active_queue = asyncio.Queue(loop=self._loop)
        self._incoming_queue = asyncio.Queue(loop=self._loop)

        self._iq_response_map = {}
        self._iq_request_map = {}
        self._logger = base_logger.getChild("StanzaBroker")

        self._on_send_stanza = on_send_stanza

    def _done_handler(self, task):
        try:
            task.result()
        except asyncio.CancelledError:
            # normal termination
            pass
        except Exception as err:
            self._loop.call_exception_handler({
                "message": str(err),
                "exception": err,
            })
            # FIXME: do something more sane here. This *will* cause a lockup. We
            # need a way to report errors on a client-level.

    def _iq_request_coro_done(self, request, task):
        try:
            response = task.result()
        except errors.XMPPError as err:
            response = request.make_reply(type_="error")
            response.error = stanza.Error.from_exception(err)
        except Exception as exc:
            response = request.make_reply(type_="error")
            response.error = stanza.Error(
                condition=(namespaces.stanzas, "undefined-condition"),
                type_="cancel",
            )
        self.enqueue_stanza(response)

    def _process_incoming(self, stanza_obj):
        if isinstance(stanza_obj, stanza.IQ):
            if stanza_obj.type_ == "result" or stanza_obj.type_ == "error":
                # iq response
                key = (stanza_obj.from_, stanza_obj.id_)
                try:
                    cb = self._iq_response_map.pop(key)
                except KeyError:
                    self._logger.warning(
                        "unexpected IQ response: from=%r, id=%r",
                        *key)
                    return
                try:
                    cb(stanza_obj)
                except:
                    self._logger.warning(
                        "while handling IQ response",
                        exc_info=True)
            else:
                # iq request
                key = (stanza_obj.type_, type(stanza_obj.payload))
                try:
                    coro = self._iq_request_map[key]
                except KeyError:
                    self._logger.warning(
                        "unhandleable IQ request: from=%r, id=%r, payload=%r",
                        stanza_obj.from_,
                        stanza_obj.id_,
                        stanza_obj.payload
                    )
                    response = stanza_obj.make_reply(type_="error")
                    response.error = stanza.Error(
                        condition=(namespaces.stanzas,
                                   "feature-not-implemented"),
                    )
                    self.enqueue_stanza(response)
                    return

                task = asyncio.async(coro(stanza_obj))
                task.add_done_callback(
                    functools.partial(
                        self._iq_request_coro_done,
                        stanza_obj))

    def register_iq_response_callback(self, from_, id_, cb):
        key = (from_, id_)
        self._iq_response_map[key] = cb

    def register_iq_request_coro(self, type_, payload_cls, coro):
        key = (type_, payload_cls)
        self._iq_request_map[key] = coro

    def start(self):
        self._task = asyncio.async(self._run(), loop=self._loop)
        self._task.add_done_callback(self._done_handler)

    def stop(self):
        self._task.cancel()

    @asyncio.coroutine
    def _run(self):
        active_fut = asyncio.async(self._active_queue.get(),
                                   loop=self._loop)
        incoming_fut = asyncio.async(self._incoming_queue.get(),
                                     loop=self._loop)

        while True:
            done, pending = yield from asyncio.wait(
                [
                    active_fut,
                    incoming_fut,
                ],
                return_when=asyncio.FIRST_COMPLETED)

            if active_fut in done:
                self._on_send_stanza(active_fut.result())
                active_fut = asyncio.async(
                    self._active_queue.get(),
                    loop=self._loop)

            if incoming_fut in done:
                self._process_incoming(incoming_fut.result())
                incoming_fut = asyncio.async(
                    self._incoming_queue.get(),
                    loop=self._loop)

    def recv_stanza(self, stanza):
        self._incoming_queue.put_nowait(stanza)

    def enqueue_stanza(self, stanza):
        self._active_queue.put_nowait(stanza)
