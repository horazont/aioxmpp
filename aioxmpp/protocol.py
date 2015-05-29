import asyncio
import inspect
import logging

from enum import Enum

import xml.sax as sax
import xml.parsers.expat as pyexpat

from . import xml, errors, xso, stream_xsos, stanza
from .utils import namespaces


class Mode(Enum):
    C2S = namespaces.client


class State(Enum):
    CLOSED = 0
    STREAM_HEADER_SENT = 1
    OPEN = 2
    CLOSING = 3


class XMLStream(asyncio.Protocol):
    def __init__(self, to,
                 features_future,
                 sorted_attributes=False,
                 base_logger=logging.getLogger("aioxmpp")):
        self._to = to
        self._sorted_attributes = sorted_attributes
        self._state = State.CLOSED
        self._logger = base_logger.getChild("XMLStream")
        self._transport = None
        self._features_future = features_future
        self.stanza_parser = xso.XSOParser()
        self.stanza_parser.add_class(stream_xsos.StreamError,
                                     self._rx_stream_error)
        self.stanza_parser.add_class(stream_xsos.StreamFeatures,
                                     self._rx_stream_features)

    def _invalid_transition(self, to, via=None):
        text = "invalid state transition: from={} to={}".format(
            self._state,
            to)
        if via:
            text += " (via: {})".format(via)
        return RuntimeError(text)

    def _invalid_state(self, at=None):
        text = "invalid state: {}".format(self._state)
        if at:
            text += " (at: {})".format(at)
        return RuntimeError(text)

    def _rx_exception(self, exc):
        try:
            raise exc
        except stanza.PayloadParsingError as exc:
            iq_response = exc.partial_obj.make_reply(type_="error")
            iq_response.error = stanza.Error(
                condition=(namespaces.stanzas, "bad-request"),
                type_="modify",
                text=str(exc.__context__)
            )
            self._writer.send(iq_response)
        except stanza.UnknownIQPayload as exc:
            iq_response = exc.partial_obj.make_reply(type_="error")
            iq_response.error = stanza.Error(
                condition=(namespaces.stanzas, "feature-not-implemented"),
                type_="cancel",
            )
            self._writer.send(iq_response)
        except xso.UnknownTopLevelTag as exc:
            raise errors.StreamError(
                condition=(namespaces.streams, "unsupported-stanza-type"),
                text="unsupported stanza: {}".format(
                    xso.tag_to_str((exc.ev_args[0], exc.ev_args[1]))
                )) from None
        except:
            raise

    def _rx_stream_header(self):
        if self._processor.remote_version != (1, 0):
            raise errors.StreamError(
                (namespaces.streams, "unsupported-version"),
                text="unsupported version")

    def _rx_stream_error(self, err):
        self.connection_lost(err.to_exception())

    def _rx_stream_footer(self):
        self.connection_lost(None)

    def _rx_stream_features(self, features):
        self.stanza_parser.remove_class(stream_xsos.StreamFeatures)
        self._features_future.set_result(features)
        self._features_future = None

    def _rx_feed(self, blob):
        try:
            self._parser.feed(blob)
        except sax.SAXParseException as exc:
            if     (exc.getException().args[0].startswith(
                    pyexpat.errors.XML_ERROR_UNDEFINED_ENTITY)):
                # this will raise an appropriate stream error
                xml.XMPPLexicalHandler.startEntity("foo")
            raise errors.StreamError(
                condition=(namespaces.streams, "bad-format"),
                text=str(exc)
            )
        except errors.StreamError as exc:
            raise
        except Exception as exc:
            self._logger.exception(
                "unexpected exception while parsing stanza"
                " bubbled up through parser. stream so ded.")
            raise errors.StreamError(
                condition=(namespaces.streams, "internal-server-error"),
                text="Internal error while parsing XML. Client logs have more"
                     " details."
            )

    def connection_made(self, transport):
        if self._state != State.CLOSED:
            raise self._invalid_state("connection_made")

        self._transport = transport
        self._writer = None
        self.reset()

    def connection_lost(self, exc):
        if self._state == State.CLOSING:
            return
        self._state = State.CLOSING
        if exc is not None and not isinstance(exc, errors.StreamError):
            self._kill_state()
        else:
            self._writer.close()
            self._transport.write_eof()
            self._transport.close()
        self._writer = None
        self._transport = None

    def data_received(self, blob):
        try:
            self._rx_feed(blob)
        except errors.StreamError as exc:
            stanza_obj = stream_xsos.StreamError.from_exception(exc)
            self._writer.send(stanza_obj)
            self.connection_lost(exc)

    def close(self):
        self.connection_lost(None)

    def _kill_state(self):
        if self._writer:
            if inspect.getgeneratorstate(self._writer) == "GEN_SUSPENDED":
                try:
                    self._writer.throw(xml.AbortStream())
                except StopIteration:
                    pass
            else:
                self._writer = None

        self._processor = None
        self._parser = None

    def _reset_state(self):
        self._kill_state()

        self._processor = xml.XMPPXMLProcessor()
        self._processor.stanza_parser = self.stanza_parser
        self._processor.on_stream_header = self._rx_stream_header
        self._processor.on_stream_footer = self._rx_stream_footer
        self._processor.on_exception = self._rx_exception
        self._parser = xml.make_parser()
        self._parser.setContentHandler(self._processor)

        self._writer = xml.write_objects(
            self._transport,
            self._to,
            nsmap={None: "jabber:client"},
            sorted_attributes=self._sorted_attributes)

    def reset(self):
        self._reset_state()
        next(self._writer)
        self._state = State.STREAM_HEADER_SENT

    def send_stanza(self, obj):
        self._writer.send(obj)

    def can_starttls(self):
        return (hasattr(self._transport, "can_starttls") and
                self._transport.can_starttls())

    @asyncio.coroutine
    def starttls(self, ssl_context, post_handshake_callback=None):
        if not self.can_starttls():
            raise RuntimeError("no transport connected or "
                               "starttls not available")

        yield from self._transport.starttls(ssl_context,
                                            post_handshake_callback)
        self._reset_state()

    @property
    def transport(self):
        return self._transport


@asyncio.coroutine
def send_and_wait_for(xmlstream, send, wait_for, timeout=None):
    fut = asyncio.Future()
    wait_for = list(wait_for)

    def cleanup():
        for anticipated_cls in wait_for:
            xmlstream.stanza_parser.remove_class(anticipated_cls)

    def receive(obj):
        nonlocal fut
        fut.set_result(obj)
        cleanup()

    for anticipated_cls in wait_for:
        xmlstream.stanza_parser.add_class(
            anticipated_cls,
            receive)

    for to_send in send:
        xmlstream.send_stanza(to_send)

    try:
        if timeout is not None and timeout >= 0:
            return (yield from asyncio.wait_for(fut, timeout))

        return (yield from fut)
    except:
        cleanup()
        raise


@asyncio.coroutine
def reset_stream_and_get_features(xmlstream, timeout=None):
    fut = asyncio.Future()

    def cleanup():
        xmlstream.stanza_parser.remove_class(stream_xsos.StreamFeatures)

    def receive(obj):
        nonlocal fut
        fut.set_result(obj)
        cleanup()

    xmlstream.stanza_parser.add_class(
        stream_xsos.StreamFeatures,
        receive)

    xmlstream.reset()

    try:
        if timeout is not None and timeout >= 0:
            return (yield from asyncio.wait_for(fut, timeout))

        return (yield from fut)
    except:
        cleanup()
        raise
