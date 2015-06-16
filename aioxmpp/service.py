class Meta(type):
    @classmethod
    def transitive_collect(mcls, classes, attr, seen):
        for cls in classes:
            yield cls
            yield from mcls.transitive_collect(getattr(cls, attr), attr, seen)

    @classmethod
    def collect_and_inherit(mcls, bases, namespace, attr):
        classes = set(namespace.get(attr, []))
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

    def __new__(mcls, name, bases, namespace):
        before_classes = mcls.collect_and_inherit(
            bases,
            namespace,
            "SERVICE_BEFORE")

        after_classes = mcls.collect_and_inherit(
            bases,
            namespace,
            "SERVICE_AFTER")

        if before_classes & after_classes:
            raise TypeError("dependency loop: {} loops through {}".format(
                name,
                next(iter(before_classes & after_classes)).__qualname__
            ))

        namespace["SERVICE_BEFORE"] = set(before_classes)
        namespace["SERVICE_AFTER"] = set(after_classes)

        new_cls = super().__new__(mcls, name, bases, namespace)

        for cls in before_classes:
            cls.SERVICE_AFTER.add(new_cls)
        for cls in after_classes:
            cls.SERVICE_BEFORE.add(new_cls)

        return new_cls

    def __lt__(self, other):
        return other in self.SERVICE_BEFORE

    def __le__(self, other):
        return self < other
