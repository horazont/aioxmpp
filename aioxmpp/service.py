class Meta(type):
    @classmethod
    def transitive_collect(mcls, classes, attr, seen):
        for cls in classes:
            yield cls
            yield from mcls.transitive_collect(getattr(cls, attr), attr, seen)

    @classmethod
    def collect_and_inherit(mcls, bases, namespace, attr,
                            inherit_dependencies):
        classes = set(namespace.get(attr, []))
        if inherit_dependencies:
            for base in bases:
                if isinstance(base, mcls):
                    classes.update(getattr(base, attr))
        classes.update(
            mcls.transitive_collect(
                list(classes),
                attr,
                set())
        )
        return classes

    def __new__(mcls, name, bases, namespace, inherit_dependencies=True):
        before_classes = mcls.collect_and_inherit(
            bases,
            namespace,
            "SERVICE_BEFORE",
            inherit_dependencies)

        after_classes = mcls.collect_and_inherit(
            bases,
            namespace,
            "SERVICE_AFTER",
            inherit_dependencies)

        if before_classes & after_classes:
            raise TypeError("dependency loop: {} loops through {}".format(
                name,
                next(iter(before_classes & after_classes)).__qualname__
            ))

        namespace["SERVICE_BEFORE"] = set(before_classes)
        namespace["SERVICE_AFTER"] = set(after_classes)

        return super().__new__(mcls, name, bases, namespace)

    def __init__(self, name, bases, namespace, inherit_dependencies=True):
        super().__init__(name, bases, namespace)
        for cls in self.SERVICE_BEFORE:
            cls.SERVICE_AFTER.add(self)
        for cls in self.SERVICE_AFTER:
            cls.SERVICE_BEFORE.add(self)

    def __lt__(self, other):
        return other in self.SERVICE_BEFORE

    def __le__(self, other):
        return self < other
