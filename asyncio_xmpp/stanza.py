import asyncio

from . import jid
from .utils import etree, namespaces

class StanzaMeta(type):
    pass

class Stanza(etree.ElementBase):
    @property
    def id(self):
        return self.get("id")

    @id.setter
    def id(self, value):
        self.set("id", value)

    @property
    def from_(self):
        return jid.JID.fromstr(self.get("from"))

    @from_.setter
    def from_(self, value):
        self.set("from", str(value))

    @property
    def to(self):
        return jid.JID.fromstr(self.get("to"))

    @to.setter
    def to(self, value):
        self.set("to", str(value))

class Message(Stanza):
    TAG = "{jabber:client}message"

    @property
    def type(self):
        return self.get("type")

    @type.setter
    def type(self, value):
        self.set("type", value)

class Presence(Stanza):
    TAG = "{jabber:client}presence"

    @Stanza.to.deleter
    def to(self):
        del self.attrib["to"]

class IQ(Stanza):
    TAG = "{jabber:client}iq"
    _VALID_TYPES = {"set", "get", "error", "result"}

    @property
    def type(self):
        return self.get("type")

    @type.setter
    def type(self, value):
        if value not in self._VALID_TYPES:
            raise ValueError("Incorrect iq@type: {}".format(value))

        self.set("type", value)

    @property
    def data(self):
        try:
            return self[0]
        except IndexError:
            return None

    @data.setter
    def data(self, value):
        if len(self):
            self.remove(0)
        self.append(value)

    def make_reply(self, type):
        if self.type not in {"set", "get"}:
            raise ValueError("Cannot construct reply to iq@type={!r}".format(
                type))

        obj = IQ()
        obj.from_ = self.to
        obj.to = self.from_
        obj.id = self.id
        obj.type = type

        return obj


class Error(etree.ElementBase):
    TAG = "{jabber:client}error"
    _VALID_TYPES = {"auth", "cancel", "continue", "modify", "wait"}
    _TEXT_ELEMENT = "{{{}}}text".format(namespaces.stanzas)
    _VALID_CONDITIONS = frozenset(
        "{{{}}}{}".format(
            namespaces.stanzas,
            condition)
        for condition in [
                "bad-request",
                "conflict",
                "feature-not-implemented",
                "forbidden",
                "gone",
                "internal-server-error",
                "item-not-found",
                "jid-malformed",
                "not-acceptable",
                "not-allowed",
                "not-authorized",
                "policy-violation",
                "recipient-unavailable",
                "redirect",
                "registration-required",
                "remote-server-not-found",
                "remote-server-timeout",
                "resource-constraint",
                "service-unavailable",
                "subscription-required",
                "undefined-condition",
                "unexpected-request",
        ]
    )

    def _init(self):
        super()._init()
        if len(self) > 3:
            raise ValueError("Malformed error element (too many children)")

        condition_el = None
        text_el = None
        data_el = None
        for item in self:
            if item.tag in self._VALID_CONDITIONS:
                if condition_el is not None:
                    raise ValueError("Malformed error element "
                                     "(multiple conditions)")
                condition_el = item
                continue
            if item.tag == self._TEXT_ELEMENT:
                if text_el is not None:
                    raise ValueError("Malformed error element "
                                     "(multiple texts)")
                text_el = item
                continue
            if not item.tag.startswith("{{{}}}".format(namespaces.stanzas)):
                if data_el is not None:
                    raise ValueError("Malformed error element "
                                     "(multiple application defined conditions)")
                data_el = item
                continue
            raise ValueError("Malformed error element (unspecified condition)")

        if condition_el is None:
            condition_el = self.makeelement(
                "{urn:ietf:params:xml:ns:xmpp-stanzas}undefined-condition")
            self.insert(0, condition_el)
        else:
            self.remove(condition_el)
            self.insert(0, condition_el)
        if text_el is not None and data_el is not None:
            self.remove(text_el)
            self.insert(1, text_el)

    @property
    def type(self):
        return self.get("type")

    @type.setter
    def type(self, value):
        if value not in self._VALID_TYPES:
            raise ValueError("Not a valid error@type: {!r}".format(value))

        self.set("type", value)

    @property
    def condition(self):
        el = self[0]
        if el.tag not in self._VALID_CONDITIONS:
            raise ValueError("Malformed error element")

        return el.tag[len(namespaces.stanzas)+2:]

    @condition.setter
    def condition(self, value):
        tag = "{{{}}}{}".format(namespaces.stanzas, value)
        if tag not in self._VALID_CONDITIONS:
            raise ValueError("Invalid error condition: {}".format(value))
        el = self[0]
        el.tag = tag

    def _find_text_element(self):
        el = self.find(self._TEXT_ELEMENT)
        if el is None or el.text is None:
            return None
        return el

    def _find_or_make_text_element(self):
        el = self._find_text_element()
        if el is None:
            el = self.makeelement(self._TEXT_ELEMENT)
            self.insert(1, el)
        return el

    @property
    def text(self):
        el = self._find_text_element()
        if el is None:
            return None
        return el.text

    @text.setter
    def text(self, value):
        el = self._find_or_make_text_element()
        el.text = value

    @text.deleter
    def text(self):
        el = self.find(self._TEXT_ELEMENT)
        if el is not None:
            self.remove(el)

    @property
    def text_lang(self):
        el = self._find_text_element()
        if el is None:
            return None
        return el.get("{http://www.w3.org/XML/1998/namespace}lang")

    @property
    def text_lang(self, value):
        el = self._find_or_make_text_element()
        el.set("{http://www.w3.org/XML/1998/namespace}lang", value)

    @property
    def application_defined_condition(self):
        el = self[-1]
        if el.tag not in self._VALID_CONDITIONS and el.tag != self._TEXT_ELEMENT:
            return el
        return None

    @application_defined_condition.setter
    def application_defined_condition(self, value):
        existing = self.application_defined_condition
        if existing is None:
            self.append(value)
        else:
            self[-1] = value

    @application_defined_condition.deleter
    def application_defined_condition(self):
        existing = self.application_defined_condition
        if existing is not None:
            del self[-1]
