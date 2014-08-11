from .stringprep import nodeprep, resourceprep, nameprep

class JID:
    """
    Represent Jabber Identifier (JID) objects (see `RFC 6122`_).
    """

    @classmethod
    def fromstr(cls, jidstr):
        if isinstance(jidstr, JID):
            return jidstr

        addr, _, resource = jidstr.partition("/")

        parts = addr.split("@")
        if len(parts) == 1:
            domainpart, = parts
            localpart = None
        elif len(parts) == 2:
            localpart, domainpart = parts
        else:
            raise ValueError("@ must not occur outside the resource part")

        return cls(localpart=localpart,
                   domainpart=domainpart,
                   resource=resource)

    def __init__(self, localpart, domainpart, resource):
        if not domainpart:
            raise ValueError("Domainpart must not be None")

        localpart = localpart or None
        resource = resource or None

        if localpart is not None:
            localpart = nodeprep(localpart)
        domainpart = nameprep(domainpart)
        if resource is not None:
            resource = resourceprep(resource)

        self.__localpart = localpart
        self.__domainpart = domainpart
        self.__resource = resource

    @property
    def bare(self):
        if self.is_bare:
            return self
        return JID(self.__localpart, self.__domainpart)

    @property
    def localpart(self):
        return self.__localpart

    @property
    def domainpart(self):
        return self.__domainpart

    @property
    def resource(self):
        return self.__resource

    @property
    def is_domain(self):
        return not self.__localpart and not self.__resource

    @property
    def is_bare(self):
        return self.__resource is None

    def replace(self, **kwargs):
        """
        Replace any part of the JID with another value. *localpart*,
        *domainpart* and *resource* are supported as keywords, which may be
        :data:`None` to remove the corresponding part from the JID.

        Return a new :class:`JID` instance.
        """

        localpart = kwargs.pop("localpart", self.__localpart)
        domainpart = kwargs.pop("domainpart", self.__domainpart)
        resource = kwargs.pop("resource", self.__resource)

        if kwargs:
            raise TypeError("replace() got an unexpected keyword "
                            "argument '{}'".format(kwargs.popitem()[0]))

        return JID(localpart=localpart,
                   domainpart=domainpart,
                   resource=resource)

    def __str__(self):
        if self.__localpart:
            result = "{}@{}".format(self.__localpart,
                                    self.__domainpart)
        if self.__resource:
            result += "/"+self.__resource

        return result

    def __hash__(self):
        hashvalue = self.__hash
        if hashvalue is None:
            self.__hash = hash((self.__localpart,
                                self.__domainpart,
                                self.__resource))
            return self.__hash
        return hashvalue

    def __eq__(self, other):
        return (self.__localpart,
                self.__domainpart,
                self.__resource) == (other.__localpart,
                                     other.__domainpart,
                                     other.__resource)

    def __ne__(self, other):
        return (self.__localpart,
                self.__domainpart,
                self.__resource) != (other.__localpart,
                                     other.__domainpart,
                                     other.__resource)
