import collections

from .stringprep import nodeprep, resourceprep, nameprep


class JID(collections.namedtuple("JID", ["localpart", "domain", "resource"])):
    __slots__ = []

    def __new__(cls, localpart, domain, resource):
        if not domain:
            raise ValueError("domain must not be empty or None")

        localpart = localpart or None
        resource = resource or None

        if localpart is not None:
            localpart = nodeprep(localpart)
        domain = nameprep(domain)
        if resource is not None:
            resource = resourceprep(resource)
        return super().__new__(cls, localpart, domain, resource)

    def replace(self, **kwargs):
        try:
            localpart = kwargs["localpart"]
        except KeyError:
            pass
        else:
            if localpart:
                kwargs["localpart"] = nodeprep(localpart)

        try:
            domain = kwargs["domain"]
        except KeyError:
            pass
        else:
            if not domain:
                raise ValueError("domain must not be empty or None")
            kwargs["domain"] = nameprep(domain)

        try:
            resource = kwargs["resource"]
        except KeyError:
            pass
        else:
            if resource:
                kwargs["resource"] = resourceprep(resource)

        return super()._replace(**kwargs)

    def __str__(self):
        result = self.domain
        if self.localpart:
            result = self.localpart + "@" + result
        if self.resource:
            result += "/" + self.resource
        return result

    @property
    def bare(self):
        return self.replace(resource=None)

    @property
    def is_bare(self):
        return not self.resource

    @property
    def is_domain(self):
        return not self.resource and not self.localpart

    @classmethod
    def fromstr(cls, s):
        localpart, sep, domain = s.partition("@")
        if not sep:
            domain = localpart
            localpart = None

        domain, _, resource = domain.partition("/")
        return cls(localpart, domain, resource)
